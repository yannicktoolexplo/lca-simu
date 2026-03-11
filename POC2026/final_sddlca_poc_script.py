import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ============================================================
# FINAL POC SCRIPT
# Classical LCA vs Time-Dependent DLCA vs State-Dependent Dynamic LCA
# with:
# - supply chain simulation
# - event timeline diagram
# - supply chain schematic
# - CSV exports
# - PNG charts
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs_sddlca_poc"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR = OUT_DIR / "csv"
IMG_DIR = OUT_DIR / "images"
CSV_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Input data
# -----------------------------
# Main scenario:
# one common year-long simulation mixing climate events, operational events and
# feedback loops between the two.
weeks = list(range(1, 53))

demand = (
    [10] * 6
    + [11] * 4
    + [12] * 4
    + [14] * 6
    + [16] * 6
    + [17] * 4
    + [15] * 6
    + [13] * 6
    + [11] * 6
    + [10] * 4
)

grid_factor = np.clip(
    np.linspace(1.02, 0.34, len(weeks))
    + 0.07 * np.sin(np.linspace(0, 6 * np.pi, len(weeks))),
    0.24,
    None,
).round(3).tolist()
for week in range(1, len(weeks) + 1):
    if week <= 12:
        grid_factor[week - 1] = round(grid_factor[week - 1] + 0.10, 3)
    if week in [7, 8, 9]:
        grid_factor[week - 1] = round(grid_factor[week - 1] + 0.10, 3)
    if week in [24, 25, 26, 27]:
        grid_factor[week - 1] = round(grid_factor[week - 1] + 0.08, 3)
    if week in [41, 42, 43]:
        grid_factor[week - 1] = round(grid_factor[week - 1] + 0.06, 3)

capacity = []
for week in weeks:
    base_capacity = 28.0 if week <= 16 else 25.0
    if week in [8, 9, 10]:
        base_capacity = 20.0
    elif week in [13, 14, 15, 16]:
        base_capacity = 17.0
    elif week in [24, 25, 26, 27]:
        base_capacity = 14.0
    elif week in [31, 32, 33]:
        base_capacity = 16.0
    elif week in [40, 41, 42, 43]:
        base_capacity = 15.0
    capacity.append(base_capacity)
nominal_capacity = max(capacity)

main_supply_availability = []
for week in weeks:
    if 11 <= week <= 16:
        main_supply_availability.append(0.62)
    elif 24 <= week <= 30:
        main_supply_availability.append(0.48)
    elif 40 <= week <= 46:
        main_supply_availability.append(0.72)
    else:
        main_supply_availability.append(1.00)

backup_supply_availability = []
for week in weeks:
    if 24 <= week <= 30:
        backup_supply_availability.append(0.84)
    elif 40 <= week <= 43:
        backup_supply_availability.append(0.90)
    else:
        backup_supply_availability.append(1.00)

climate_event_labels = ["aucun"] * len(weeks)
for idx, week in enumerate(weeks):
    if week in [7, 8, 9]:
        climate_event_labels[idx] = "canicule et tension reseau"
    elif week in [13, 14, 15, 16]:
        climate_event_labels[idx] = "secheresse et penurie matieres"
    elif week in [24, 25, 26, 27]:
        climate_event_labels[idx] = "tempete logistique et congestion portuaire"
    elif week in [31, 32, 33]:
        climate_event_labels[idx] = "retard de remise en route fournisseurs"
    elif week in [40, 41, 42, 43]:
        climate_event_labels[idx] = "inondation fournisseur et reseau degrade"
    elif week in [47, 48]:
        climate_event_labels[idx] = "pic de demande hivernal"

# Focused annex scenario that highlights time-dependent DLCA alone.
dynamic_shift_weeks = list(range(1, 21))
dynamic_shift_demand = [3, 3, 3, 3, 3, 3, 3, 3, 20, 20, 20, 20, 20, 20, 20, 20, 6, 6, 6, 6]
dynamic_shift_grid_factor = [
    1.10, 1.05, 1.00, 0.95, 0.90, 0.85, 0.80, 0.75,
    0.12, 0.10, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20,
    0.22, 0.24, 0.26, 0.28,
]
dynamic_shift_capacity = [52] * 8 + [4] * 8 + [8] * 4

# Backward-compatible aliases used by the climate-transition annex outputs.
climate_transition_weeks = weeks.copy()
climate_transition_demand = demand.copy()
climate_transition_grid_factor = grid_factor.copy()
climate_transition_capacity = capacity.copy()
climate_transition_main_supply_availability = main_supply_availability.copy()
climate_transition_backup_supply_availability = backup_supply_availability.copy()

# Environmental factors
MAIN_MATERIAL_EF = 20.0
BACKUP_MATERIAL_EF = 24.0
INBOUND_MAIN_TRANSPORT_EF = 0.8
INBOUND_BACKUP_TRANSPORT_EF = 5.0
NOMINAL_KWH_PER_UNIT = 8.0
TRUCK_OUTBOUND_EF = 1.8
AIR_OUTBOUND_EF = 10.0
RAW_STORAGE_EF = 0.03
FG_STORAGE_EF = 0.06

main_material_ef_series = np.clip(
    np.linspace(21.4, 18.6, len(weeks)) + 0.35 * np.sin(np.linspace(0, 4 * np.pi, len(weeks))),
    18.0,
    None,
).round(3).tolist()
inbound_main_transport_ef_series = np.clip(
    np.linspace(0.95, 0.68, len(weeks)) + 0.04 * np.sin(np.linspace(0, 5 * np.pi, len(weeks))),
    0.60,
    None,
).round(3).tolist()
truck_outbound_ef_series = np.clip(
    np.linspace(2.05, 1.55, len(weeks)) + 0.05 * np.sin(np.linspace(0, 6 * np.pi, len(weeks))),
    1.45,
    None,
).round(3).tolist()
for week in weeks:
    if week <= 18:
        main_material_ef_series[week - 1] = round(main_material_ef_series[week - 1] + 1.0, 3)
        inbound_main_transport_ef_series[week - 1] = round(inbound_main_transport_ef_series[week - 1] + 0.10, 3)
        truck_outbound_ef_series[week - 1] = round(truck_outbound_ef_series[week - 1] + 0.12, 3)
    if 13 <= week <= 16 or 24 <= week <= 30 or 40 <= week <= 46:
        main_material_ef_series[week - 1] = round(main_material_ef_series[week - 1] + 1.4, 3)
    if 24 <= week <= 27 or 40 <= week <= 43:
        inbound_main_transport_ef_series[week - 1] = round(inbound_main_transport_ef_series[week - 1] + 0.18, 3)
    if 7 <= week <= 9 or 24 <= week <= 27 or 40 <= week <= 43:
        truck_outbound_ef_series[week - 1] = round(truck_outbound_ef_series[week - 1] + 0.18, 3)

# Economic factors for decision trade-off views
MAIN_MATERIAL_COST = 50.0
BACKUP_MATERIAL_COST = 68.0
INBOUND_MAIN_TRANSPORT_COST = 2.0
INBOUND_BACKUP_TRANSPORT_COST = 9.0
ELECTRICITY_COST_PER_KWH = 0.14
TRUCK_OUTBOUND_COST = 6.0
AIR_OUTBOUND_COST = 24.0
RAW_STORAGE_COST = 0.35
FG_STORAGE_COST = 0.55
BACKLOG_PENALTY_COST = 18.0

CLASSICAL_METHOD = "Classical LCA"
TIME_DEPENDENT_DLCA_METHOD = "Time-Dependent DLCA"
SDD_METHOD = "State-Dependent Dynamic LCA"

# Inventory policy
main_lead = 2
backup_lead = 1

DECISION_REVERSAL_COLUMNS = [
    "service_floor_pct",
    "policy_a",
    "policy_b",
    "dynamic_diff_a_minus_b",
    "sddlca_diff_a_minus_b",
    "service_a_pct",
    "service_b_pct",
    "dynamic_prefers",
    "sddlca_prefers",
    "reversal_magnitude",
]


@dataclass(frozen=True)
class DecisionPolicy:
    name: str
    label: str
    raw_target: float = 24.0
    raw_reorder_threshold: float = 14.0
    fg_target: float = 0.0
    backup_order_qty: float = 12.0
    air_backlog_start_threshold: float = 4.0
    air_backlog_end_threshold: float = 6.0
    carbon_aware_grid_threshold: float | None = None
    carbon_aware_backlog_guard: float = 0.0
    carbon_aware_capacity_cap: float = 1.0


BASELINE_POLICY = DecisionPolicy(
    name="baseline",
    label="Reference",
    raw_target=60.0,
    raw_reorder_threshold=26.0,
    fg_target=16.0,
    backup_order_qty=10.0,
    air_backlog_start_threshold=3.0,
    air_backlog_end_threshold=6.0,
)

DYNAMIC_SHIFT_POLICY = DecisionPolicy(
    name="dynamic_shift",
    label="Decalage temporel + regime degrade",
    raw_target=170.0,
    raw_reorder_threshold=85.0,
    fg_target=72.0,
    backup_order_qty=10.0,
    air_backlog_start_threshold=4.0,
    air_backlog_end_threshold=7.0,
)

CLIMATE_TRANSITION_POLICY = DecisionPolicy(
    name="climate_transition",
    label="Transition climatique + disruptions",
    raw_target=60.0,
    raw_reorder_threshold=26.0,
    fg_target=16.0,
    backup_order_qty=10.0,
    air_backlog_start_threshold=3.0,
    air_backlog_end_threshold=6.0,
)

COUNTERFACTUAL_POLICIES = [
    BASELINE_POLICY,
    DecisionPolicy(
        name="backup_early",
        label="Backup anticipe",
        raw_target=60.0,
        raw_reorder_threshold=28.0,
        fg_target=16.0,
        backup_order_qty=14.0,
        air_backlog_start_threshold=3.0,
        air_backlog_end_threshold=6.0,
    ),
    DecisionPolicy(
        name="inventory_buffer",
        label="Stock tampon",
        raw_target=72.0,
        raw_reorder_threshold=32.0,
        fg_target=22.0,
        backup_order_qty=10.0,
        air_backlog_start_threshold=3.0,
        air_backlog_end_threshold=6.0,
    ),
    DecisionPolicy(
        name="low_carbon",
        label="Discipline carbone",
        raw_target=60.0,
        raw_reorder_threshold=26.0,
        fg_target=16.0,
        backup_order_qty=10.0,
        air_backlog_start_threshold=12.0,
        air_backlog_end_threshold=18.0,
        carbon_aware_grid_threshold=0.50,
        carbon_aware_backlog_guard=4.0,
        carbon_aware_capacity_cap=0.6,
    ),
    DecisionPolicy(
        name="service_first",
        label="Service prioritaire",
        raw_target=68.0,
        raw_reorder_threshold=30.0,
        fg_target=20.0,
        backup_order_qty=14.0,
        air_backlog_start_threshold=1.0,
        air_backlog_end_threshold=3.0,
    ),
]


def prod_kwh_per_good_unit(utilization: float) -> float:
    if utilization <= 0.70:
        return 8.0
    elif utilization <= 0.90:
        return 9.5
    else:
        return 12.0


def scrap_rate(utilization: float) -> float:
    if utilization <= 0.90:
        return 0.0
    elif utilization <= 0.98:
        return 0.05
    else:
        return 0.10


def add_inventory_batch(inventory: list[dict], qty: float, source: str) -> None:
    if qty <= 0:
        return
    inventory.append({"source": source, "qty": float(qty)})


def inventory_total(inventory: list[dict]) -> float:
    return sum(batch["qty"] for batch in inventory)


def inventory_split(inventory: list[dict]) -> dict[str, float]:
    split = {"main": 0.0, "backup": 0.0}
    for batch in inventory:
        split[batch["source"]] += batch["qty"]
    return split


def consume_inventory_fifo(inventory: list[dict], qty: float) -> dict[str, float]:
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
        raise ValueError(f"Not enough inventory to consume {qty} units")

    return consumed


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def validate_series_lengths(*series: Sequence[float]) -> None:
    lengths = {len(values) for values in series}
    if len(lengths) != 1:
        raise ValueError(f"All time series must have the same length, got lengths={sorted(lengths)}")
    if not lengths or next(iter(lengths)) == 0:
        raise ValueError("Time series must be non-empty")


def build_operational_feedback(transition_row: dict) -> dict[str, float | str]:
    capacity_multiplier = 1.0
    main_supply_multiplier = 1.0
    backup_supply_multiplier = 1.0
    grid_addon = 0.0
    labels: list[str] = []

    if transition_row["capacity_utilization"] >= 0.96:
        capacity_multiplier *= 0.88
        labels.append("maintenance corrective")
    elif transition_row["capacity_utilization"] >= 0.90:
        capacity_multiplier *= 0.94
        labels.append("atelier sous tension")

    if transition_row["scrap_units"] >= 0.8:
        capacity_multiplier *= 0.96
        grid_addon += 0.02
        labels.append("recalage qualite")

    if transition_row["outbound_mode"] == "air":
        main_supply_multiplier *= 0.96
        backup_supply_multiplier *= 0.97
        grid_addon += 0.04
        labels.append("congestion logistique")

    if transition_row["backup_consumed_raw_units"] > 0:
        backup_supply_multiplier *= 0.95
        grid_addon += 0.01
        labels.append("stress fournisseur backup")

    if transition_row["backlog_end"] >= 14:
        capacity_multiplier *= 0.93
        grid_addon += 0.03
        labels.append("overtime et energie d'urgence")

    return {
        "capacity_multiplier": capacity_multiplier,
        "main_supply_multiplier": main_supply_multiplier,
        "backup_supply_multiplier": backup_supply_multiplier,
        "grid_addon": grid_addon,
        "operational_feedback_event": " + ".join(labels) if labels else "aucun",
    }


def series_value(series: Sequence[float], week: int) -> float:
    index = min(max(week - 1, 0), len(series) - 1)
    return float(series[index])


def clone_inventory(inventory: list[dict]) -> list[dict]:
    return [
        {"source": batch["source"], "qty": float(batch["qty"])}
        for batch in inventory
        if batch["qty"] > 1e-9
    ]


@dataclass
class SupplyChainState:
    main_pipeline: list[float]
    backup_pipeline: list[float]
    raw_inventory: list[dict]
    fg_inventory: list[dict]
    backlog: float

    def copy(self) -> "SupplyChainState":
        return SupplyChainState(
            main_pipeline=self.main_pipeline.copy(),
            backup_pipeline=self.backup_pipeline.copy(),
            raw_inventory=clone_inventory(self.raw_inventory),
            fg_inventory=clone_inventory(self.fg_inventory),
            backlog=float(self.backlog),
        )


def initial_state() -> SupplyChainState:
    return SupplyChainState(
        main_pipeline=[0.0] * (main_lead + 1),
        backup_pipeline=[0.0] * (backup_lead + 1),
        raw_inventory=[{"source": "main", "qty": 30.0}],
        fg_inventory=[{"source": "main", "qty": 14.0}],
        backlog=0.0,
    )


def serialize_pipeline(pipeline: list[float]) -> str:
    return json.dumps([round(value, 4) for value in pipeline])


def serialize_inventory(inventory: list[dict]) -> str:
    return json.dumps([
        {"source": batch["source"], "qty": round(batch["qty"], 4)}
        for batch in inventory
        if batch["qty"] > 1e-9
    ])


def state_snapshot(state: SupplyChainState, prefix: str) -> dict:
    snapshot = {
        f"{prefix}_backlog": state.backlog,
        f"{prefix}_raw_stock_total": inventory_total(state.raw_inventory),
        f"{prefix}_fg_stock_total": inventory_total(state.fg_inventory),
        f"{prefix}_main_pipeline_vector": serialize_pipeline(state.main_pipeline),
        f"{prefix}_backup_pipeline_vector": serialize_pipeline(state.backup_pipeline),
        f"{prefix}_raw_inventory_layers": serialize_inventory(state.raw_inventory),
        f"{prefix}_fg_inventory_layers": serialize_inventory(state.fg_inventory),
        f"{prefix}_raw_inventory_layer_count": len(state.raw_inventory),
        f"{prefix}_fg_inventory_layer_count": len(state.fg_inventory),
    }

    for idx, value in enumerate(state.main_pipeline):
        snapshot[f"{prefix}_main_pipeline_eta_{idx}"] = value
    for idx, value in enumerate(state.backup_pipeline):
        snapshot[f"{prefix}_backup_pipeline_eta_{idx}"] = value

    return snapshot


def state_transition(
    state: SupplyChainState,
    policy: DecisionPolicy,
    week: int,
    demand_t: float,
    capacity_t: float,
    grid_factor_t: float,
    main_supply_availability_t: float = 1.0,
    backup_supply_availability_t: float = 1.0,
) -> tuple[SupplyChainState, dict]:
    next_state = state.copy()

    # Receive inbound material at the start of the period.
    main_inbound = next_state.main_pipeline.pop(0)
    next_state.main_pipeline.append(0.0)

    backup_inbound = next_state.backup_pipeline.pop(0)
    next_state.backup_pipeline.append(0.0)

    add_inventory_batch(next_state.raw_inventory, main_inbound, "main")
    add_inventory_batch(next_state.raw_inventory, backup_inbound, "backup")
    raw_stock_start = inventory_total(next_state.raw_inventory)

    # Ordering actions are endogenous decisions taken from the current state.
    main_supply_position = raw_stock_start + sum(next_state.main_pipeline)
    requested_main_order = max(0.0, policy.raw_target - main_supply_position)
    main_order = requested_main_order * main_supply_availability_t

    total_supply_position = raw_stock_start + sum(next_state.main_pipeline) + sum(next_state.backup_pipeline)
    backup_order = 0.0
    requested_backup_order = 0.0
    if total_supply_position < policy.raw_reorder_threshold:
        requested_backup_order = policy.backup_order_qty
        backup_order = requested_backup_order * backup_supply_availability_t

    next_state.main_pipeline[-1] += main_order
    next_state.backup_pipeline[-1] += backup_order

    backlog_start = next_state.backlog
    service_pressure = demand_t + backlog_start
    fg_stock_start = inventory_total(next_state.fg_inventory)
    fg_replenishment_need = max(0.0, policy.fg_target - fg_stock_start)
    planned_input = min(capacity_t, raw_stock_start, service_pressure + fg_replenishment_need)
    carbon_aware_active = False
    if (
        policy.carbon_aware_grid_threshold is not None
        and grid_factor_t >= policy.carbon_aware_grid_threshold
        and backlog_start <= policy.carbon_aware_backlog_guard
    ):
        planned_input = min(planned_input, capacity_t * policy.carbon_aware_capacity_cap)
        carbon_aware_active = True

    util = planned_input / capacity_t if capacity_t > 0 else 0.0
    sr = scrap_rate(util)

    consumed_raw = consume_inventory_fifo(next_state.raw_inventory, planned_input)
    main_consumed_raw = consumed_raw["main"]
    backup_consumed_raw = consumed_raw["backup"]

    scrap_main_units = main_consumed_raw * sr
    scrap_backup_units = backup_consumed_raw * sr
    scrap_units = scrap_main_units + scrap_backup_units

    good_output_main = main_consumed_raw - scrap_main_units
    good_output_backup = backup_consumed_raw - scrap_backup_units
    good_output = good_output_main + good_output_backup

    add_inventory_batch(next_state.fg_inventory, good_output_main, "main")
    add_inventory_batch(next_state.fg_inventory, good_output_backup, "backup")
    fg_stock_pre_ship = inventory_total(next_state.fg_inventory)

    shipments = min(fg_stock_pre_ship, demand_t + backlog_start)
    shipped_units = consume_inventory_fifo(next_state.fg_inventory, shipments)
    shipped_main_units = shipped_units["main"]
    shipped_backup_units = shipped_units["backup"]

    backlog_end = max(0.0, backlog_start + demand_t - shipments)
    next_state.backlog = backlog_end
    same_week_served = min(shipments, demand_t)
    same_week_service_level = safe_ratio(same_week_served, demand_t)

    outbound_mode = (
        "air"
        if (
            backlog_start > policy.air_backlog_start_threshold
            or backlog_end > policy.air_backlog_end_threshold
        )
        else "truck"
    )
    if (
        backlog_start > policy.air_backlog_start_threshold
        and backlog_end > policy.air_backlog_end_threshold
    ):
        air_trigger_reason = "backlog_start_and_end"
    elif backlog_start > policy.air_backlog_start_threshold:
        air_trigger_reason = "backlog_start_threshold"
    elif backlog_end > policy.air_backlog_end_threshold:
        air_trigger_reason = "backlog_end_threshold"
    else:
        air_trigger_reason = "none"

    raw_stock_split_end = inventory_split(next_state.raw_inventory)
    fg_stock_split_end = inventory_split(next_state.fg_inventory)

    transition_row = {
        "policy_name": policy.name,
        "policy_label": policy.label,
        "week": week,
        "demand": demand_t,
        "capacity": capacity_t,
        "grid_factor": grid_factor_t,
        "main_inbound": main_inbound,
        "backup_inbound": backup_inbound,
        "main_order_requested": requested_main_order,
        "main_order": main_order,
        "main_order_shortfall": requested_main_order - main_order,
        "backup_order_requested": requested_backup_order,
        "backup_order": backup_order,
        "backup_order_shortfall": requested_backup_order - backup_order,
        "main_supply_availability": main_supply_availability_t,
        "backup_supply_availability": backup_supply_availability_t,
        "raw_stock_end": inventory_total(next_state.raw_inventory),
        "raw_stock_main_end": raw_stock_split_end["main"],
        "raw_stock_backup_end": raw_stock_split_end["backup"],
        "fg_stock_end": inventory_total(next_state.fg_inventory),
        "fg_stock_main_end": fg_stock_split_end["main"],
        "fg_stock_backup_end": fg_stock_split_end["backup"],
        "backlog_start": backlog_start,
        "backlog_end": backlog_end,
        "planned_input_units": planned_input,
        "main_consumed_raw_units": main_consumed_raw,
        "backup_consumed_raw_units": backup_consumed_raw,
        "good_output_units": good_output,
        "good_output_main_units": good_output_main,
        "good_output_backup_units": good_output_backup,
        "scrap_units": scrap_units,
        "scrap_main_units": scrap_main_units,
        "scrap_backup_units": scrap_backup_units,
        "capacity_utilization": util,
        "outbound_shipments": shipments,
        "shipped_main_units": shipped_main_units,
        "shipped_backup_units": shipped_backup_units,
        "outbound_mode": outbound_mode,
        "air_trigger_reason": air_trigger_reason,
        "carbon_aware_active": carbon_aware_active,
        "same_week_served_units": same_week_served,
        "same_week_service_level": same_week_service_level,
    }

    return next_state, transition_row


def simulate_policy(
    policy: DecisionPolicy,
    demand_series: Sequence[float] | None = None,
    capacity_series: Sequence[float] | None = None,
    grid_series: Sequence[float] | None = None,
    main_supply_availability_series: Sequence[float] | None = None,
    backup_supply_availability_series: Sequence[float] | None = None,
    climate_event_series: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    effective_demand = demand if demand_series is None else demand_series
    effective_capacity = capacity if capacity_series is None else capacity_series
    effective_grid = grid_factor if grid_series is None else grid_series
    effective_main_supply_availability = (
        main_supply_availability
        if main_supply_availability_series is None
        else list(main_supply_availability_series)
    )
    effective_backup_supply_availability = (
        backup_supply_availability
        if backup_supply_availability_series is None
        else list(backup_supply_availability_series)
    )
    effective_climate_events = (
        climate_event_labels
        if climate_event_series is None
        else list(climate_event_series)
    )
    validate_series_lengths(
        effective_demand,
        effective_capacity,
        effective_grid,
        effective_main_supply_availability,
        effective_backup_supply_availability,
    )
    if len(effective_climate_events) != len(effective_demand):
        raise ValueError(
            "Climate event labels must have the same length as the time series, "
            f"got {len(effective_climate_events)} vs {len(effective_demand)}"
        )
    rows = []
    state_trajectory_rows = []
    current_state = initial_state()
    operational_feedback = {
        "capacity_multiplier": 1.0,
        "main_supply_multiplier": 1.0,
        "backup_supply_multiplier": 1.0,
        "grid_addon": 0.0,
        "operational_feedback_event": "aucun",
    }

    for t in range(len(effective_demand)):
        week = t + 1
        start_state = current_state.copy()
        base_capacity = float(effective_capacity[t])
        base_grid_factor = float(effective_grid[t])
        base_main_supply_availability = float(effective_main_supply_availability[t])
        base_backup_supply_availability = float(effective_backup_supply_availability[t])
        applied_capacity = max(0.0, base_capacity * float(operational_feedback["capacity_multiplier"]))
        applied_grid_factor = max(0.0, base_grid_factor + float(operational_feedback["grid_addon"]))
        applied_main_supply_availability = min(
            1.0,
            max(0.0, base_main_supply_availability * float(operational_feedback["main_supply_multiplier"])),
        )
        applied_backup_supply_availability = min(
            1.0,
            max(0.0, base_backup_supply_availability * float(operational_feedback["backup_supply_multiplier"])),
        )
        next_state, transition_row = state_transition(
            state=current_state,
            policy=policy,
            week=week,
            demand_t=effective_demand[t],
            capacity_t=applied_capacity,
            grid_factor_t=applied_grid_factor,
            main_supply_availability_t=applied_main_supply_availability,
            backup_supply_availability_t=applied_backup_supply_availability,
        )
        transition_row["base_capacity"] = base_capacity
        transition_row["base_grid_factor"] = base_grid_factor
        transition_row["base_main_supply_availability"] = base_main_supply_availability
        transition_row["base_backup_supply_availability"] = base_backup_supply_availability
        transition_row["climate_event"] = effective_climate_events[t]
        transition_row["operational_feedback_event"] = str(operational_feedback["operational_feedback_event"])
        transition_row["combined_event_context"] = " / ".join([
            label
            for label in [effective_climate_events[t], str(operational_feedback["operational_feedback_event"])]
            if label != "aucun"
        ]) or "aucun"

        rows.append(transition_row)
        state_trajectory_rows.append({
            "policy_name": policy.name,
            "policy_label": policy.label,
            "week": week,
            "demand": effective_demand[t],
            "capacity": applied_capacity,
            "grid_factor": applied_grid_factor,
            "main_supply_availability": applied_main_supply_availability,
            "backup_supply_availability": applied_backup_supply_availability,
            "base_capacity": base_capacity,
            "base_grid_factor": base_grid_factor,
            "base_main_supply_availability": base_main_supply_availability,
            "base_backup_supply_availability": base_backup_supply_availability,
            "climate_event": effective_climate_events[t],
            "operational_feedback_event": str(operational_feedback["operational_feedback_event"]),
            **state_snapshot(start_state, "state_start"),
            **state_snapshot(next_state, "state_end"),
        })
        current_state = next_state
        operational_feedback = build_operational_feedback(transition_row)

    states = pd.DataFrame(rows)
    state_trajectory = pd.DataFrame(state_trajectory_rows)
    state_end_main_pipeline_cols = [col for col in state_trajectory.columns if col.startswith("state_end_main_pipeline_eta_")]
    state_end_backup_pipeline_cols = [col for col in state_trajectory.columns if col.startswith("state_end_backup_pipeline_eta_")]
    state_trajectory["state_end_main_pipeline_total"] = state_trajectory[state_end_main_pipeline_cols].sum(axis=1)
    state_trajectory["state_end_backup_pipeline_total"] = state_trajectory[state_end_backup_pipeline_cols].sum(axis=1)
    state_trajectory["state_end_total_pipeline"] = (
        state_trajectory["state_end_main_pipeline_total"] + state_trajectory["state_end_backup_pipeline_total"]
    )
    states["backup_raw_share_end"] = (
        states["raw_stock_backup_end"] / states["raw_stock_end"].where(states["raw_stock_end"] > 0, 1.0)
    )
    return states, state_trajectory


def compute_classical_lca_from_states(states: pd.DataFrame) -> tuple[dict, pd.Series]:
    """Compute a stationary LCA from a common operational trajectory.

    The trajectory is only used to aggregate total useful output, total shipments and
    average stock levels over the study horizon. The environmental model itself stays
    stationary: average grid factor, nominal truck transport, main-source material,
    and no explicit scrap burden.
    """
    avg_grid = float(states["grid_factor"].mean())
    avg_main_material_ef = float(np.mean([series_value(main_material_ef_series, int(week)) for week in states["week"]]))
    avg_inbound_main_transport_ef = float(
        np.mean([series_value(inbound_main_transport_ef_series, int(week)) for week in states["week"]])
    )
    avg_truck_outbound_ef = float(np.mean([series_value(truck_outbound_ef_series, int(week)) for week in states["week"]]))
    total_good_output = float(states["good_output_units"].sum())
    total_shipments = float(states["outbound_shipments"].sum())
    avg_raw_stock = float(states["raw_stock_end"].mean())
    avg_fg_stock = float(states["fg_stock_end"].mean())

    classical = {
        "material": total_good_output * avg_main_material_ef,
        "inbound_transport": total_good_output * avg_inbound_main_transport_ef,
        "production_energy": total_good_output * NOMINAL_KWH_PER_UNIT * avg_grid,
        "outbound_transport": total_shipments * avg_truck_outbound_ef,
        "storage": (avg_raw_stock * RAW_STORAGE_EF + avg_fg_stock * FG_STORAGE_EF) * len(states),
        "scrap": 0.0,
    }
    classical["total"] = sum(classical.values())

    # This weekly profile is a visualization aid only: it redistributes the classical
    # stationary assumptions over the observed weekly activity and stock profile.
    reconstructed_weekly = (
        states["good_output_units"] * avg_main_material_ef
        + states["good_output_units"] * avg_inbound_main_transport_ef
        + states["good_output_units"] * NOMINAL_KWH_PER_UNIT * avg_grid
        + states["outbound_shipments"] * avg_truck_outbound_ef
        + states["raw_stock_end"] * RAW_STORAGE_EF
        + states["fg_stock_end"] * FG_STORAGE_EF
    )
    return classical, reconstructed_weekly


def compute_time_dependent_dlca_from_states(
    states: pd.DataFrame,
    truck_outbound_ef: float = TRUCK_OUTBOUND_EF,
) -> tuple[pd.DataFrame, dict]:
    """Compute a time-dependent DLCA from the common operational trajectory.

    The inventory varies over time through weekly useful output, shipments and stocks.
    Characterization is time-dependent only where the model is explicitly exogenous:
    the weekly grid factor. Regime-dependent effects remain intentionally inactive
    here: no backup-specific factors, no air transport switch, no explicit scrap burden,
    and nominal energy intensity.
    """
    rows = []
    for _, r in states.iterrows():
        week = int(r["week"])
        main_material_ef_t = series_value(main_material_ef_series, week)
        inbound_main_transport_ef_t = series_value(inbound_main_transport_ef_series, week)
        truck_outbound_ef_t = series_value(truck_outbound_ef_series, week)
        rows.append({
            "policy_name": r["policy_name"],
            "policy_label": r["policy_label"],
            "week": week,
            "material": r["good_output_units"] * main_material_ef_t,
            "inbound_transport": r["good_output_units"] * inbound_main_transport_ef_t,
            "production_energy": r["good_output_units"] * NOMINAL_KWH_PER_UNIT * r["grid_factor"],
            "outbound_transport": r["outbound_shipments"] * truck_outbound_ef_t,
            "storage": r["raw_stock_end"] * RAW_STORAGE_EF + r["fg_stock_end"] * FG_STORAGE_EF,
            "scrap": 0.0,
        })
    td_dlca = pd.DataFrame(rows)
    td_dlca["total"] = td_dlca[[
        "material",
        "inbound_transport",
        "production_energy",
        "outbound_transport",
        "storage",
        "scrap",
    ]].sum(axis=1)
    breakdown = td_dlca[[
        "material",
        "inbound_transport",
        "production_energy",
        "outbound_transport",
        "storage",
        "scrap",
        "total",
    ]].sum().to_dict()
    return td_dlca, breakdown


def compute_state_dependent_dynamic_lca_from_states(
    states: pd.DataFrame,
    backup_material_ef: float = BACKUP_MATERIAL_EF,
    inbound_backup_transport_ef: float = INBOUND_BACKUP_TRANSPORT_EF,
    truck_outbound_ef: float = TRUCK_OUTBOUND_EF,
    air_outbound_ef: float = AIR_OUTBOUND_EF,
) -> tuple[pd.DataFrame, dict]:
    """Compute the state-dependent dynamic LCA from the common trajectory.

    Here the environmental inventory and factors depend on endogenous operational
    regimes: backup source usage, utilization-dependent energy intensity, air freight
    activation and explicit burden allocated to scrap.
    """
    rows = []
    for _, r in states.iterrows():
        week = int(r["week"])
        main_material_ef_t = series_value(main_material_ef_series, week)
        inbound_main_transport_ef_t = series_value(inbound_main_transport_ef_series, week)
        truck_outbound_ef_t = series_value(truck_outbound_ef_series, week)
        material_main = r["good_output_main_units"] * main_material_ef_t
        material_backup = r["good_output_backup_units"] * backup_material_ef

        inbound_main = r["good_output_main_units"] * inbound_main_transport_ef_t
        inbound_backup = r["good_output_backup_units"] * inbound_backup_transport_ef

        kwh_per_good = prod_kwh_per_good_unit(r["capacity_utilization"])
        prod_energy = r["good_output_units"] * kwh_per_good * r["grid_factor"]

        scrap_burden = (
            r["scrap_main_units"] * (main_material_ef_t + inbound_main_transport_ef_t + kwh_per_good * r["grid_factor"])
            + r["scrap_backup_units"] * (backup_material_ef + inbound_backup_transport_ef + kwh_per_good * r["grid_factor"])
        )

        outbound_factor = air_outbound_ef if r["outbound_mode"] == "air" else truck_outbound_ef_t
        outbound = r["outbound_shipments"] * outbound_factor

        storage = r["raw_stock_end"] * RAW_STORAGE_EF + r["fg_stock_end"] * FG_STORAGE_EF

        rows.append({
            "policy_name": r["policy_name"],
            "policy_label": r["policy_label"],
            "week": week,
            "material": material_main + material_backup,
            "inbound_transport": inbound_main + inbound_backup,
            "production_energy": prod_energy,
            "outbound_transport": outbound,
            "storage": storage,
            "scrap": scrap_burden,
            "transport_mode": r["outbound_mode"],
            "backup_inbound": r["backup_inbound"],
            "backup_consumed_raw_units": r["backup_consumed_raw_units"],
            "good_output_backup_units": r["good_output_backup_units"],
            "capacity_utilization": r["capacity_utilization"],
            "scrap_units": r["scrap_units"],
            "air_trigger_reason": r["air_trigger_reason"],
        })

    sdd = pd.DataFrame(rows)
    sdd["total"] = sdd[[
        "material",
        "inbound_transport",
        "production_energy",
        "outbound_transport",
        "storage",
        "scrap",
    ]].sum(axis=1)
    breakdown = sdd[[
        "material",
        "inbound_transport",
        "production_energy",
        "outbound_transport",
        "storage",
        "scrap",
        "total",
    ]].sum().to_dict()
    return sdd, breakdown


def compute_method_outputs(
    states: pd.DataFrame,
    backup_material_ef: float = BACKUP_MATERIAL_EF,
    inbound_backup_transport_ef: float = INBOUND_BACKUP_TRANSPORT_EF,
    truck_outbound_ef: float = TRUCK_OUTBOUND_EF,
    air_outbound_ef: float = AIR_OUTBOUND_EF,
) -> dict:
    states = states.copy()
    classical, classical_reconstructed_weekly = compute_classical_lca_from_states(states)
    states["classical_reconstructed_weekly_total"] = classical_reconstructed_weekly
    states["classical_weekly_total"] = classical_reconstructed_weekly

    time_dependent_dlca, td_dlca_breakdown = compute_time_dependent_dlca_from_states(
        states,
        truck_outbound_ef=truck_outbound_ef,
    )

    sddlca, sddlca_breakdown = compute_state_dependent_dynamic_lca_from_states(
        states,
        backup_material_ef=backup_material_ef,
        inbound_backup_transport_ef=inbound_backup_transport_ef,
        truck_outbound_ef=truck_outbound_ef,
        air_outbound_ef=air_outbound_ef,
    )

    comparison = pd.DataFrame([
        {"method": CLASSICAL_METHOD, "total_kgCO2e": classical["total"]},
        {"method": TIME_DEPENDENT_DLCA_METHOD, "total_kgCO2e": td_dlca_breakdown["total"]},
        {"method": SDD_METHOD, "total_kgCO2e": sddlca_breakdown["total"]},
    ])
    comparison["delta_vs_classical"] = comparison["total_kgCO2e"] - classical["total"]
    comparison["delta_vs_classical_pct"] = 100 * comparison["delta_vs_classical"] / classical["total"]

    breakdown = pd.DataFrame([
        {"method": CLASSICAL_METHOD, **classical},
        {"method": TIME_DEPENDENT_DLCA_METHOD, **td_dlca_breakdown},
        {"method": SDD_METHOD, **sddlca_breakdown},
    ])

    return {
        "states": states,
        "classical": classical,
        "time_dependent_dlca": time_dependent_dlca,
        "time_dependent_dlca_breakdown": td_dlca_breakdown,
        # Backward-compatible aliases used by downstream tables and plots.
        "dynamic": time_dependent_dlca,
        "dynamic_breakdown": td_dlca_breakdown,
        "sddlca": sddlca,
        "sddlca_breakdown": sddlca_breakdown,
        "comparison": comparison,
        "breakdown": breakdown,
    }


def compute_cost_outputs(states: pd.DataFrame) -> dict:
    cost_rows = []
    for _, r in states.iterrows():
        kwh_per_good = prod_kwh_per_good_unit(r["capacity_utilization"])
        outbound_cost_factor = AIR_OUTBOUND_COST if r["outbound_mode"] == "air" else TRUCK_OUTBOUND_COST

        cost_rows.append({
            "policy_name": r["policy_name"],
            "policy_label": r["policy_label"],
            "week": int(r["week"]),
            "material": r["good_output_main_units"] * MAIN_MATERIAL_COST + r["good_output_backup_units"] * BACKUP_MATERIAL_COST,
            "inbound_transport": r["good_output_main_units"] * INBOUND_MAIN_TRANSPORT_COST + r["good_output_backup_units"] * INBOUND_BACKUP_TRANSPORT_COST,
            "production_energy": r["good_output_units"] * kwh_per_good * ELECTRICITY_COST_PER_KWH,
            "outbound_transport": r["outbound_shipments"] * outbound_cost_factor,
            "storage": r["raw_stock_end"] * RAW_STORAGE_COST + r["fg_stock_end"] * FG_STORAGE_COST,
            "backlog_penalty": r["backlog_end"] * BACKLOG_PENALTY_COST,
        })

    costs = pd.DataFrame(cost_rows)
    costs["total"] = costs[["material", "inbound_transport", "production_energy",
                            "outbound_transport", "storage", "backlog_penalty"]].sum(axis=1)
    cost_breakdown = costs[["material", "inbound_transport", "production_energy",
                            "outbound_transport", "storage", "backlog_penalty", "total"]].sum().to_dict()
    return {"weekly_costs": costs, "cost_breakdown": cost_breakdown}


def build_diagnostic_tables(states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = states.loc[
        (states["backup_inbound"] > 0)
        | (states["backup_consumed_raw_units"] > 0)
        | (states["outbound_mode"] == "air")
        | (states["scrap_units"] > 0),
        ["policy_name", "policy_label", "week", "capacity", "backlog_start", "backlog_end", "backup_inbound",
         "backup_consumed_raw_units", "good_output_backup_units", "capacity_utilization",
         "scrap_units", "outbound_mode", "air_trigger_reason", "carbon_aware_active"]
    ].copy()

    traceability = states[[
        "policy_name",
        "policy_label",
        "week",
        "main_inbound",
        "backup_inbound",
        "main_consumed_raw_units",
        "backup_consumed_raw_units",
        "good_output_main_units",
        "good_output_backup_units",
        "scrap_main_units",
        "scrap_backup_units",
        "shipped_main_units",
        "shipped_backup_units",
        "raw_stock_main_end",
        "raw_stock_backup_end",
        "fg_stock_main_end",
        "fg_stock_backup_end",
        "air_trigger_reason",
        "carbon_aware_active",
    ]].copy()

    metrics = pd.DataFrame([
        {"metric": "Weeks with air outbound", "value": int((states["outbound_mode"] == "air").sum())},
        {"metric": "Weeks with backup supplier activated", "value": int((states["backup_inbound"] > 0).sum())},
        {"metric": "Weeks with backup material consumed", "value": int((states["backup_consumed_raw_units"] > 0).sum())},
        {"metric": "Weeks with carbon-aware throttling", "value": int(states["carbon_aware_active"].sum())},
        {"metric": "Total scrap units", "value": round(states["scrap_units"].sum(), 2)},
        {"metric": "Peak backlog", "value": round(states["backlog_end"].max(), 2)},
        {"metric": "Ending backlog", "value": round(states["backlog_end"].iloc[-1], 2)},
        {"metric": "Weeks with backlog", "value": int((states["backlog_end"] > 0).sum())},
        {"metric": "Peak capacity utilization", "value": round(states["capacity_utilization"].max(), 2)},
        {"metric": "Same-week service level", "value": round(100 * safe_ratio(states["same_week_served_units"].sum(), states["demand"].sum()), 2)},
        {"metric": "Demand fill rate incl. backlog shipments", "value": round(100 * safe_ratio(states["outbound_shipments"].sum(), states["demand"].sum()), 2)},
        {"metric": "Peak backup share in raw stock", "value": round(100 * states["backup_raw_share_end"].max(), 2)},
    ])

    return events, traceability, metrics


def evaluate_policy(
    policy: DecisionPolicy,
    demand_series: Sequence[float] | None = None,
    capacity_series: Sequence[float] | None = None,
    grid_series: Sequence[float] | None = None,
    main_supply_availability_series: Sequence[float] | None = None,
    backup_supply_availability_series: Sequence[float] | None = None,
    climate_event_series: Sequence[str] | None = None,
    backup_material_ef: float = BACKUP_MATERIAL_EF,
    inbound_backup_transport_ef: float = INBOUND_BACKUP_TRANSPORT_EF,
    truck_outbound_ef: float = TRUCK_OUTBOUND_EF,
    air_outbound_ef: float = AIR_OUTBOUND_EF,
) -> dict:
    states, state_trajectory = simulate_policy(
        policy,
        demand_series=demand_series,
        capacity_series=capacity_series,
        grid_series=grid_series,
        main_supply_availability_series=main_supply_availability_series,
        backup_supply_availability_series=backup_supply_availability_series,
        climate_event_series=climate_event_series,
    )
    method_outputs = compute_method_outputs(
        states,
        backup_material_ef=backup_material_ef,
        inbound_backup_transport_ef=inbound_backup_transport_ef,
        truck_outbound_ef=truck_outbound_ef,
        air_outbound_ef=air_outbound_ef,
    )
    cost_outputs = compute_cost_outputs(method_outputs["states"])
    events, traceability, metrics = build_diagnostic_tables(method_outputs["states"])

    summary = {
        "policy_name": policy.name,
        "policy_label": policy.label,
        "same_week_service_pct": round(100 * safe_ratio(method_outputs["states"]["same_week_served_units"].sum(), method_outputs["states"]["demand"].sum()), 2),
        "fill_rate_pct": round(100 * safe_ratio(method_outputs["states"]["outbound_shipments"].sum(), method_outputs["states"]["demand"].sum()), 2),
        "final_backlog_units": round(method_outputs["states"]["backlog_end"].iloc[-1], 2),
        "peak_backlog_units": round(method_outputs["states"]["backlog_end"].max(), 2),
        "total_cost": round(cost_outputs["cost_breakdown"]["total"], 2),
        "classical_total_kgCO2e": round(method_outputs["classical"]["total"], 2),
        "time_dependent_dlca_total_kgCO2e": round(method_outputs["time_dependent_dlca_breakdown"]["total"], 2),
        "dynamic_total_kgCO2e": round(method_outputs["dynamic_breakdown"]["total"], 2),
        "sddlca_total_kgCO2e": round(method_outputs["sddlca_breakdown"]["total"], 2),
        "hidden_carbon_vs_td_dlca": round(method_outputs["sddlca_breakdown"]["total"] - method_outputs["time_dependent_dlca_breakdown"]["total"], 2),
        "hidden_carbon_vs_dynamic": round(method_outputs["sddlca_breakdown"]["total"] - method_outputs["dynamic_breakdown"]["total"], 2),
        "hidden_carbon_vs_classical": round(method_outputs["sddlca_breakdown"]["total"] - method_outputs["classical"]["total"], 2),
    }

    return {
        **method_outputs,
        **cost_outputs,
        "state_trajectory": state_trajectory,
        "events": events,
        "traceability": traceability,
        "metrics": metrics,
        "summary": summary,
    }


def build_method_sanity_checks(
    baseline_result: dict,
    reference_policy: DecisionPolicy,
) -> pd.DataFrame:
    avg_grid_value = float(np.mean(grid_factor))
    constant_grid_result = evaluate_policy(
        reference_policy,
        grid_series=[avg_grid_value] * len(grid_factor),
    )
    baseline_summary = baseline_result["summary"]
    constant_grid_summary = constant_grid_result["summary"]
    tolerance = 1e-9
    return pd.DataFrame([
        {
            "check_name": "baseline_td_dlca_differs_from_classical",
            "status": bool(
                abs(baseline_summary["time_dependent_dlca_total_kgCO2e"] - baseline_summary["classical_total_kgCO2e"])
                > tolerance
            ),
            "details": "On the main scenario, Time-Dependent DLCA should differ from Classical LCA when temporal distributions matter.",
            "observed_value": round(
                baseline_summary["time_dependent_dlca_total_kgCO2e"] - baseline_summary["classical_total_kgCO2e"],
                6,
            ),
        },
        {
            "check_name": "baseline_rank_td_dlca_vs_sdd",
            "status": bool(baseline_summary["sddlca_total_kgCO2e"] >= baseline_summary["time_dependent_dlca_total_kgCO2e"]),
            "details": "On the main scenario, SDD should be at least as high as Time-Dependent DLCA.",
            "observed_value": round(
                baseline_summary["sddlca_total_kgCO2e"] - baseline_summary["time_dependent_dlca_total_kgCO2e"],
                6,
            ),
        },
        {
            "check_name": "constant_grid_reduces_td_gap",
            "status": bool(
                abs(constant_grid_summary["time_dependent_dlca_total_kgCO2e"] - constant_grid_summary["classical_total_kgCO2e"])
                < abs(baseline_summary["time_dependent_dlca_total_kgCO2e"] - baseline_summary["classical_total_kgCO2e"])
            ),
            "details": "With a constant grid factor, the gap between Time-Dependent DLCA and Classical LCA should shrink in this POC.",
            "observed_value": round(
                constant_grid_summary["time_dependent_dlca_total_kgCO2e"] - constant_grid_summary["classical_total_kgCO2e"],
                12,
            ),
        },
        {
            "check_name": "classical_weekly_profile_is_reconstructed",
            "status": True,
            "details": "The weekly Classical LCA profile is a reconstructed visualization under stationary assumptions, not a fully time-resolved Classical LCA.",
            "observed_value": np.nan,
        },
    ])


def compute_causal_delta_table(results: list[dict]) -> pd.DataFrame:
    rows = []
    for result in results:
        sdd = result["sddlca_breakdown"]
        dyn = result["time_dependent_dlca_breakdown"]
        rows.append({
            "policy_name": result["summary"]["policy_name"],
            "policy_label": result["summary"]["policy_label"],
            "delta_material": sdd["material"] - dyn["material"],
            "delta_inbound_transport": sdd["inbound_transport"] - dyn["inbound_transport"],
            "delta_production_energy": sdd["production_energy"] - dyn["production_energy"],
            "delta_outbound_transport": sdd["outbound_transport"] - dyn["outbound_transport"],
            "delta_storage": sdd["storage"] - dyn["storage"],
            "delta_scrap": sdd["scrap"] - dyn["scrap"],
            "hidden_carbon_total": sdd["total"] - dyn["total"],
        })
    return pd.DataFrame(rows)


def compute_pareto_front(summary_df: pd.DataFrame, carbon_metric_col: str, output_flag_col: str) -> pd.DataFrame:
    rows = []
    for _, candidate in summary_df.iterrows():
        dominated = False
        for _, other in summary_df.iterrows():
            if other["policy_name"] == candidate["policy_name"]:
                continue
            if (
                other["same_week_service_pct"] >= candidate["same_week_service_pct"]
                and other[carbon_metric_col] <= candidate[carbon_metric_col]
                and other["total_cost"] <= candidate["total_cost"]
                and (
                    other["same_week_service_pct"] > candidate["same_week_service_pct"]
                    or other[carbon_metric_col] < candidate[carbon_metric_col]
                    or other["total_cost"] < candidate["total_cost"]
                )
            ):
                dominated = True
                break
        row = candidate.to_dict()
        row[output_flag_col] = not dominated
        rows.append(row)
    return pd.DataFrame(rows)


def build_search_policies() -> list[DecisionPolicy]:
    policies = []
    seen = set()
    for raw_target_value in [52.0, 60.0, 68.0, 76.0]:
        for reorder_value in [22.0, 26.0, 30.0, 34.0]:
            for fg_target_value in [12.0, 16.0, 20.0, 24.0]:
                for backup_qty_value in [10.0, 12.0, 14.0, 16.0]:
                    for air_start, air_end in [(1.0, 3.0), (3.0, 6.0), (5.0, 8.0), (8.0, 12.0)]:
                        for carbon_mode in [False, True]:
                            name = (
                                f"rt{int(raw_target_value)}_rr{int(reorder_value)}_"
                                f"fg{int(fg_target_value)}_bq{int(backup_qty_value)}_"
                                f"air{int(air_start)}_{int(air_end)}_"
                                f"{'ca' if carbon_mode else 'std'}"
                            )
                            if name in seen:
                                continue
                            seen.add(name)
                            policies.append(
                                DecisionPolicy(
                                    name=name,
                                    label=(
                                        f"RT{int(raw_target_value)} RR{int(reorder_value)} "
                                        f"FG{int(fg_target_value)} "
                                        f"BQ{int(backup_qty_value)} Air{int(air_start)}/{int(air_end)} "
                                        f"{'CA' if carbon_mode else 'STD'}"
                                    ),
                                    raw_target=raw_target_value,
                                    raw_reorder_threshold=reorder_value,
                                    fg_target=fg_target_value,
                                    backup_order_qty=backup_qty_value,
                                    air_backlog_start_threshold=air_start,
                                    air_backlog_end_threshold=air_end,
                                    carbon_aware_grid_threshold=0.50 if carbon_mode else None,
                                    carbon_aware_backlog_guard=4.0 if carbon_mode else 0.0,
                                    carbon_aware_capacity_cap=0.6 if carbon_mode else 1.0,
                                )
                            )
    return policies


def find_decision_reversal(search_results: list[dict]) -> tuple[pd.DataFrame, float | None]:
    summaries = pd.DataFrame([result["summary"] for result in search_results])
    for service_floor in [75.0, 72.0, 70.0, 68.0, 66.0]:
        feasible = summaries.loc[summaries["same_week_service_pct"] >= service_floor].copy()
        if len(feasible) < 2:
            continue
        pair_rows = []
        feasible_rows = feasible.to_dict(orient="records")
        for i, left in enumerate(feasible_rows):
            for j, right in enumerate(feasible_rows):
                if j <= i:
                    continue
                dynamic_diff = float(left["dynamic_total_kgCO2e"]) - float(right["dynamic_total_kgCO2e"])
                sdd_diff = float(left["sddlca_total_kgCO2e"]) - float(right["sddlca_total_kgCO2e"])
                if dynamic_diff * sdd_diff < 0:
                    pair_rows.append({
                        "service_floor_pct": service_floor,
                        "policy_a": str(left["policy_label"]),
                        "policy_b": str(right["policy_label"]),
                        "dynamic_diff_a_minus_b": dynamic_diff,
                        "sddlca_diff_a_minus_b": sdd_diff,
                        "service_a_pct": float(left["same_week_service_pct"]),
                        "service_b_pct": float(right["same_week_service_pct"]),
                        "dynamic_prefers": str(left["policy_label"]) if dynamic_diff < 0 else str(right["policy_label"]),
                        "sddlca_prefers": str(left["policy_label"]) if sdd_diff < 0 else str(right["policy_label"]),
                        "reversal_magnitude": abs(dynamic_diff) + abs(sdd_diff),
                    })
        if pair_rows:
            pair_df = (
                pd.DataFrame(pair_rows)
                .sort_values("reversal_magnitude", ascending=False)
                .head(20)
                .reset_index(drop=True)
            )
            return pair_df, service_floor
    return pd.DataFrame(columns=DECISION_REVERSAL_COLUMNS), None


def build_capacity_variant(severity: float) -> list[float]:
    variant = []
    for base_cap_value, original_cap in zip([nominal_capacity] * len(capacity), capacity):
        reduction = base_cap_value - original_cap
        adjusted = base_cap_value - severity * reduction
        variant.append(max(3.0, round(adjusted, 2)))
    return variant


def run_hidden_carbon_sensitivity(policy: DecisionPolicy) -> pd.DataFrame:
    rows = []
    severity_cases = [
        ("none", 0.0),
        ("mild", 0.6),
        ("baseline", 1.0),
        ("severe", 1.4),
    ]
    air_cases = [
        ("0.8x", 0.8),
        ("1.0x", 1.0),
        ("1.2x", 1.2),
        ("1.5x", 1.5),
    ]
    for severity_label, severity_value in severity_cases:
        capacity_variant = build_capacity_variant(severity_value)
        for air_label, air_multiplier in air_cases:
            result = evaluate_policy(
                policy,
                capacity_series=capacity_variant,
                air_outbound_ef=AIR_OUTBOUND_EF * air_multiplier,
            )
            total_shipments = float(result["states"]["outbound_shipments"].sum())
            total_good_output = float(result["states"]["good_output_units"].sum())
            rows.append({
                "severity_label": severity_label,
                "severity_value": severity_value,
                "air_label": air_label,
                "air_multiplier": air_multiplier,
                "classical_total_kgCO2e": result["summary"]["classical_total_kgCO2e"],
                "dynamic_total_kgCO2e": result["summary"]["dynamic_total_kgCO2e"],
                "sddlca_total_kgCO2e": result["summary"]["sddlca_total_kgCO2e"],
                "hidden_carbon_vs_dynamic": result["summary"]["hidden_carbon_vs_dynamic"],
                "hidden_carbon_vs_classical": result["summary"]["hidden_carbon_vs_classical"],
                "total_shipments": total_shipments,
                "total_good_output": total_good_output,
                "classical_kg_per_shipped_unit": safe_ratio(result["summary"]["classical_total_kgCO2e"], total_shipments),
                "dynamic_kg_per_shipped_unit": safe_ratio(result["summary"]["dynamic_total_kgCO2e"], total_shipments),
                "sddlca_kg_per_shipped_unit": safe_ratio(result["summary"]["sddlca_total_kgCO2e"], total_shipments),
                "sddlca_to_classical_ratio": safe_ratio(
                    result["summary"]["sddlca_total_kgCO2e"],
                    result["summary"]["classical_total_kgCO2e"],
                ),
                "sddlca_to_dynamic_ratio": safe_ratio(
                    result["summary"]["sddlca_total_kgCO2e"],
                    result["summary"]["dynamic_total_kgCO2e"],
                ),
                "same_week_service_pct": result["summary"]["same_week_service_pct"],
                "final_backlog_units": result["summary"]["final_backlog_units"],
            })
    return pd.DataFrame(rows)


def classify_environmental_regime(row: pd.Series) -> str:
    if row["outbound_mode"] == "air" or row["backup_consumed_raw_units"] > 0 or row["scrap_units"] > 0:
        return "crise"
    if (
        row["backlog_end"] > 0
        or row["capacity_utilization"] >= 0.90
        or row["main_supply_availability"] < 0.999
    ):
        return "tendu"
    return "nominal"


def build_regime_table(states: pd.DataFrame) -> pd.DataFrame:
    regime_rows = states[[
        "week",
        "demand",
        "capacity",
        "base_capacity",
        "grid_factor",
        "base_grid_factor",
        "main_supply_availability",
        "base_main_supply_availability",
        "backup_supply_availability",
        "base_backup_supply_availability",
        "backlog_end",
        "capacity_utilization",
        "backup_consumed_raw_units",
        "scrap_units",
        "outbound_mode",
        "climate_event",
        "operational_feedback_event",
        "combined_event_context",
    ]].copy()
    regime_rows["environmental_regime"] = regime_rows.apply(classify_environmental_regime, axis=1)
    return regime_rows


def build_integrated_event_calendar(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in states.iterrows():
        event_types = []
        if row["climate_event"] != "aucun":
            event_types.append("climatique")
        if row["operational_feedback_event"] != "aucun":
            event_types.append("retroaction operationnelle")
        if row["backup_consumed_raw_units"] > 0:
            event_types.append("recours backup")
        if row["outbound_mode"] == "air":
            event_types.append("expedition aerienne")
        if row["scrap_units"] > 0:
            event_types.append("rebut")
        rows.append({
            "week": int(row["week"]),
            "climate_event": row["climate_event"],
            "operational_feedback_event": row["operational_feedback_event"],
            "combined_event_context": row["combined_event_context"],
            "event_types": ", ".join(event_types) if event_types else "aucun",
            "backlog_end": row["backlog_end"],
            "capacity_utilization": row["capacity_utilization"],
            "outbound_mode": row["outbound_mode"],
            "backup_consumed_raw_units": row["backup_consumed_raw_units"],
            "scrap_units": row["scrap_units"],
        })
    return pd.DataFrame(rows)


def evaluate_climate_transition_policies(policies: list[DecisionPolicy]) -> list[dict]:
    return [
        evaluate_policy(
            policy,
            demand_series=climate_transition_demand,
            capacity_series=climate_transition_capacity,
            grid_series=climate_transition_grid_factor,
            main_supply_availability_series=climate_transition_main_supply_availability,
            backup_supply_availability_series=climate_transition_backup_supply_availability,
            climate_event_series=climate_event_labels,
        )
        for policy in policies
    ]


def build_two_customer_network(states: pd.DataFrame) -> pd.DataFrame:
    core_backlog = 0.0
    remote_backlog = 0.0
    rows = []
    for _, r in states.iterrows():
        core_demand = round(r["demand"] * 0.6, 2)
        remote_demand = round(r["demand"] - core_demand, 2)
        available = r["outbound_shipments"]
        total_pressure = core_demand + core_backlog + remote_demand + remote_backlog

        if total_pressure <= 0:
            core_ship = 0.0
            remote_ship = 0.0
        else:
            core_target_share = (core_demand + core_backlog) / total_pressure
            core_ship = min(available * core_target_share, core_demand + core_backlog)
            remote_ship = min(available - core_ship, remote_demand + remote_backlog)

        remaining_after_remote = max(0.0, available - core_ship - remote_ship)
        if remaining_after_remote > 0:
            extra_core = min(remaining_after_remote, max(0.0, core_demand + core_backlog - core_ship))
            core_ship += extra_core
            remote_ship += min(
                max(0.0, available - core_ship - remote_ship),
                max(0.0, remote_demand + remote_backlog - remote_ship),
            )

        core_backlog_end = max(0.0, core_backlog + core_demand - core_ship)
        remote_backlog_end = max(0.0, remote_backlog + remote_demand - remote_ship)

        core_mode = "air" if (core_backlog > 5 or core_backlog_end > 7) else "truck"
        remote_mode = "air" if (remote_backlog > 2 or remote_backlog_end > 4) else "truck"

        core_dynamic_outbound = core_ship * 1.6
        remote_dynamic_outbound = remote_ship * 2.2
        core_sdd_outbound = core_ship * (9.0 if core_mode == "air" else 1.6)
        remote_sdd_outbound = remote_ship * (11.0 if remote_mode == "air" else 2.2)

        rows.append({
            "week": int(r["week"]),
            "core_demand": core_demand,
            "remote_demand": remote_demand,
            "core_shipments": core_ship,
            "remote_shipments": remote_ship,
            "core_backlog_end": core_backlog_end,
            "remote_backlog_end": remote_backlog_end,
            "core_mode": core_mode,
            "remote_mode": remote_mode,
            "dynamic_outbound_core": core_dynamic_outbound,
            "dynamic_outbound_remote": remote_dynamic_outbound,
            "sddlca_outbound_core": core_sdd_outbound,
            "sddlca_outbound_remote": remote_sdd_outbound,
            "hidden_network_outbound": (core_sdd_outbound + remote_sdd_outbound) - (core_dynamic_outbound + remote_dynamic_outbound),
        })

        core_backlog = core_backlog_end
        remote_backlog = remote_backlog_end

    return pd.DataFrame(rows)


# -----------------------------
# Natural supply chain dynamics
# -----------------------------
baseline_result = evaluate_policy(
    BASELINE_POLICY,
    climate_event_series=climate_event_labels,
)
dynamic_shift_result = evaluate_policy(
    DYNAMIC_SHIFT_POLICY,
    demand_series=dynamic_shift_demand,
    capacity_series=dynamic_shift_capacity,
    grid_series=dynamic_shift_grid_factor,
    main_supply_availability_series=[1.0] * len(dynamic_shift_weeks),
    backup_supply_availability_series=[1.0] * len(dynamic_shift_weeks),
    climate_event_series=["aucun"] * len(dynamic_shift_weeks),
)
climate_transition_result = baseline_result
climate_policy_results = evaluate_climate_transition_policies(COUNTERFACTUAL_POLICIES)

states = baseline_result["states"]
state_trajectory = baseline_result["state_trajectory"]
classical = baseline_result["classical"]
time_dependent_dlca = baseline_result["time_dependent_dlca"]
time_dependent_dlca_breakdown = baseline_result["time_dependent_dlca_breakdown"]
dynamic = baseline_result["dynamic"]
dynamic_breakdown = baseline_result["dynamic_breakdown"]
sddlca = baseline_result["sddlca"]
sddlca_breakdown = baseline_result["sddlca_breakdown"]
comparison = baseline_result["comparison"]
breakdown = baseline_result["breakdown"]
events = baseline_result["events"]
traceability = baseline_result["traceability"]
metrics = baseline_result["metrics"]
weekly_costs = baseline_result["weekly_costs"]
method_sanity_checks = build_method_sanity_checks(baseline_result, BASELINE_POLICY)
dynamic_shift_states = dynamic_shift_result["states"]
dynamic_shift_comparison = dynamic_shift_result["comparison"]
dynamic_shift_metrics = dynamic_shift_result["metrics"]
dynamic_shift_summary = pd.DataFrame([dynamic_shift_result["summary"]])
climate_transition_states = climate_transition_result["states"]
climate_transition_summary = pd.DataFrame([climate_transition_result["summary"]])
climate_transition_comparison = climate_transition_result["comparison"]
climate_transition_metrics = climate_transition_result["metrics"]
climate_transition_regimes = build_regime_table(climate_transition_states)
integrated_event_calendar = build_integrated_event_calendar(states)
climate_policy_summary = pd.DataFrame([result["summary"] for result in climate_policy_results])
climate_policy_method_comparison = pd.concat([
    result["comparison"].assign(
        policy_name=result["summary"]["policy_name"],
        policy_label=result["summary"]["policy_label"],
    )
    for result in climate_policy_results
], ignore_index=True)
dynamic_shift_cumulative = pd.DataFrame({
    "week": dynamic_shift_states["week"],
    "classical_reconstructed_weekly_kgCO2e": dynamic_shift_states["classical_reconstructed_weekly_total"],
    "dynamic_weekly_kgCO2e": dynamic_shift_result["time_dependent_dlca"]["total"],
    "sdd_weekly_kgCO2e": dynamic_shift_result["sddlca"]["total"],
})
dynamic_shift_cumulative["classical_cumulative_kgCO2e"] = dynamic_shift_cumulative["classical_reconstructed_weekly_kgCO2e"].cumsum()
dynamic_shift_cumulative["dynamic_cumulative_kgCO2e"] = dynamic_shift_cumulative["dynamic_weekly_kgCO2e"].cumsum()
dynamic_shift_cumulative["sdd_cumulative_kgCO2e"] = dynamic_shift_cumulative["sdd_weekly_kgCO2e"].cumsum()
climate_transition_cumulative = pd.DataFrame({
    "week": climate_transition_states["week"],
    "classical_reconstructed_weekly_kgCO2e": climate_transition_states["classical_reconstructed_weekly_total"],
    "dynamic_weekly_kgCO2e": climate_transition_result["time_dependent_dlca"]["total"],
    "sdd_weekly_kgCO2e": climate_transition_result["sddlca"]["total"],
})
climate_transition_cumulative["classical_cumulative_kgCO2e"] = climate_transition_cumulative["classical_reconstructed_weekly_kgCO2e"].cumsum()
climate_transition_cumulative["dynamic_cumulative_kgCO2e"] = climate_transition_cumulative["dynamic_weekly_kgCO2e"].cumsum()
climate_transition_cumulative["sdd_cumulative_kgCO2e"] = climate_transition_cumulative["sdd_weekly_kgCO2e"].cumsum()
climate_transition_cumulative["sdd_minus_dynamic_cumulative"] = (
    climate_transition_cumulative["sdd_cumulative_kgCO2e"] - climate_transition_cumulative["dynamic_cumulative_kgCO2e"]
)
method_cumulative = pd.DataFrame({
    "week": states["week"],
    "classical_reconstructed_weekly_kgCO2e": states["classical_reconstructed_weekly_total"],
    "dynamic_weekly_kgCO2e": time_dependent_dlca["total"],
    "sdd_weekly_kgCO2e": sddlca["total"],
})
method_cumulative["classical_cumulative_kgCO2e"] = method_cumulative["classical_reconstructed_weekly_kgCO2e"].cumsum()
method_cumulative["dynamic_cumulative_kgCO2e"] = method_cumulative["dynamic_weekly_kgCO2e"].cumsum()
method_cumulative["sdd_cumulative_kgCO2e"] = method_cumulative["sdd_weekly_kgCO2e"].cumsum()
method_cumulative["sdd_minus_dynamic_cumulative"] = (
    method_cumulative["sdd_cumulative_kgCO2e"] - method_cumulative["dynamic_cumulative_kgCO2e"]
)
method_cumulative["sdd_minus_lca_cumulative"] = (
    method_cumulative["sdd_cumulative_kgCO2e"] - method_cumulative["classical_cumulative_kgCO2e"]
)
avg_main_material_ef = float(np.mean([series_value(main_material_ef_series, int(week)) for week in states["week"]]))
avg_inbound_main_transport_ef = float(
    np.mean([series_value(inbound_main_transport_ef_series, int(week)) for week in states["week"]])
)
avg_truck_outbound_ef = float(np.mean([series_value(truck_outbound_ef_series, int(week)) for week in states["week"]]))
baseline_gap_drivers = pd.DataFrame({
    "week": states["week"],
    "classical_material": states["good_output_units"] * avg_main_material_ef,
    "classical_inbound_transport": states["good_output_units"] * avg_inbound_main_transport_ef,
    "classical_production_energy": states["good_output_units"] * NOMINAL_KWH_PER_UNIT * states["grid_factor"].mean(),
    "classical_outbound_transport": states["outbound_shipments"] * avg_truck_outbound_ef,
    "classical_storage": states["raw_stock_end"] * RAW_STORAGE_EF + states["fg_stock_end"] * FG_STORAGE_EF,
    "classical_scrap": 0.0,
    "classical_total": states["classical_weekly_total"],
    "dynamic_material": dynamic["material"],
    "dynamic_inbound_transport": dynamic["inbound_transport"],
    "dynamic_production_energy": dynamic["production_energy"],
    "dynamic_outbound_transport": dynamic["outbound_transport"],
    "dynamic_storage": dynamic["storage"],
    "dynamic_scrap": dynamic["scrap"],
    "dynamic_total": dynamic["total"],
    "sdd_material": sddlca["material"],
    "sdd_inbound_transport": sddlca["inbound_transport"],
    "sdd_production_energy": sddlca["production_energy"],
    "sdd_outbound_transport": sddlca["outbound_transport"],
    "sdd_storage": sddlca["storage"],
    "sdd_scrap": sddlca["scrap"],
    "sdd_total": sddlca["total"],
    "backup_sourcing_premium": (
        (sddlca["material"] - dynamic["material"])
        + (sddlca["inbound_transport"] - dynamic["inbound_transport"])
    ),
    "energy_premium": sddlca["production_energy"] - dynamic["production_energy"],
    "air_premium": sddlca["outbound_transport"] - dynamic["outbound_transport"],
    "scrap_premium": sddlca["scrap"] - dynamic["scrap"],
    "total_premium_vs_dynamic": sddlca["total"] - dynamic["total"],
    "backlog_end": states["backlog_end"],
    "good_output_units": states["good_output_units"],
    "outbound_shipments": states["outbound_shipments"],
    "grid_factor": states["grid_factor"],
    "average_grid_factor": states["grid_factor"].mean(),
    "total_stock_units": states["raw_stock_end"] + states["fg_stock_end"],
    "backup_output_units": states["good_output_backup_units"],
    "capacity_utilization_pct": 100 * states["capacity_utilization"],
    "air_shipments_units": states["outbound_shipments"].where(states["outbound_mode"] == "air", 0.0),
})
baseline_gap_drivers["other_premium"] = (
    baseline_gap_drivers["total_premium_vs_dynamic"]
    - baseline_gap_drivers["backup_sourcing_premium"]
    - baseline_gap_drivers["energy_premium"]
    - baseline_gap_drivers["air_premium"]
    - baseline_gap_drivers["scrap_premium"]
)

state_definition = pd.DataFrame([
    {
        "component": "backlog",
        "location": "state_start_backlog / state_end_backlog",
        "description": "Unserved demand carried from one week to the next.",
    },
    {
        "component": "main_pipeline_eta_i",
        "location": "state_*_main_pipeline_eta_0..n",
        "description": "Main-supplier materials in transit by time-to-arrival bucket.",
    },
    {
        "component": "backup_pipeline_eta_i",
        "location": "state_*_backup_pipeline_eta_0..n",
        "description": "Backup-supplier materials in transit by time-to-arrival bucket.",
    },
    {
        "component": "raw_inventory_layers",
        "location": "state_*_raw_inventory_layers",
        "description": "FIFO raw-material batches with source provenance and quantity.",
    },
    {
        "component": "fg_inventory_layers",
        "location": "state_*_fg_inventory_layers",
        "description": "FIFO finished-goods batches with source provenance and quantity.",
    },
])

counterfactual_results = climate_policy_results
policy_definition = pd.DataFrame([
    {
        "policy_name": policy.name,
        "policy_label": policy.label,
        "raw_target": policy.raw_target,
        "raw_reorder_threshold": policy.raw_reorder_threshold,
        "fg_target": policy.fg_target,
        "backup_order_qty": policy.backup_order_qty,
        "air_backlog_start_threshold": policy.air_backlog_start_threshold,
        "air_backlog_end_threshold": policy.air_backlog_end_threshold,
        "carbon_aware_grid_threshold": policy.carbon_aware_grid_threshold,
        "carbon_aware_backlog_guard": policy.carbon_aware_backlog_guard,
        "carbon_aware_capacity_cap": policy.carbon_aware_capacity_cap,
    }
    for policy in COUNTERFACTUAL_POLICIES
])
policy_decision_summary = pd.DataFrame([result["summary"] for result in counterfactual_results])
policy_method_comparison = pd.concat([
    result["comparison"].assign(
        policy_name=result["summary"]["policy_name"],
        policy_label=result["summary"]["policy_label"],
    )
    for result in counterfactual_results
], ignore_index=True)
policy_cost_breakdown = pd.DataFrame([
    {
        "policy_name": result["summary"]["policy_name"],
        "policy_label": result["summary"]["policy_label"],
        **result["cost_breakdown"],
    }
    for result in counterfactual_results
])
policy_weekly_costs = pd.concat([result["weekly_costs"] for result in counterfactual_results], ignore_index=True)
policy_hidden_carbon = policy_decision_summary[[
    "policy_name",
    "policy_label",
    "hidden_carbon_vs_td_dlca",
    "hidden_carbon_vs_dynamic",
    "hidden_carbon_vs_classical",
]].copy()
policy_component_breakdown = pd.concat([
    pd.DataFrame([
        {
            "policy_name": result["summary"]["policy_name"],
            "policy_label": result["summary"]["policy_label"],
            "method_label": CLASSICAL_METHOD,
            **{key: value for key, value in result["classical"].items() if key != "total"},
            "total": result["classical"]["total"],
        },
        {
            "policy_name": result["summary"]["policy_name"],
            "policy_label": result["summary"]["policy_label"],
            "method_label": TIME_DEPENDENT_DLCA_METHOD,
            **{key: value for key, value in result["time_dependent_dlca_breakdown"].items() if key != "total"},
            "total": result["time_dependent_dlca_breakdown"]["total"],
        },
        {
            "policy_name": result["summary"]["policy_name"],
            "policy_label": result["summary"]["policy_label"],
            "method_label": SDD_METHOD,
            **{key: value for key, value in result["sddlca_breakdown"].items() if key != "total"},
            "total": result["sddlca_breakdown"]["total"],
        },
    ])
    for result in counterfactual_results
], ignore_index=True)
policy_causal_attribution = compute_causal_delta_table(counterfactual_results)
policy_pareto_lca = compute_pareto_front(
    policy_decision_summary,
    carbon_metric_col="classical_total_kgCO2e",
    output_flag_col="pareto_efficient_lca",
)
policy_pareto_dynamic = compute_pareto_front(
    policy_pareto_lca,
    carbon_metric_col="dynamic_total_kgCO2e",
    output_flag_col="pareto_efficient_dynamic",
)
policy_pareto = compute_pareto_front(
    policy_pareto_dynamic,
    carbon_metric_col="sddlca_total_kgCO2e",
    output_flag_col="pareto_efficient_sdd",
)
search_policies = build_search_policies()
search_results = [evaluate_policy(policy) for policy in search_policies]
search_summary = pd.DataFrame([result["summary"] for result in search_results])
decision_reversal_pairs, _decision_reversal_service_floor = find_decision_reversal(search_results)
best_decision_reversal = (
    decision_reversal_pairs.sort_values("reversal_magnitude", ascending=False).iloc[0].to_dict()
    if not decision_reversal_pairs.empty
    else None
)
sensitivity_hidden_carbon = run_hidden_carbon_sensitivity(BASELINE_POLICY)
network_lane_states = build_two_customer_network(states)

# -----------------------------
# Export CSV files
# -----------------------------
states.to_csv(CSV_DIR / "poc_supply_chain_states.csv", index=False)
state_trajectory.to_csv(CSV_DIR / "poc_state_space_trajectory.csv", index=False)
time_dependent_dlca.to_csv(CSV_DIR / "poc_time_dependent_dlca.csv", index=False)
sddlca.to_csv(CSV_DIR / "poc_state_dependent_dynamic_lca.csv", index=False)
comparison.to_csv(CSV_DIR / "poc_lca_method_comparison.csv", index=False)
breakdown.to_csv(CSV_DIR / "poc_lca_breakdown.csv", index=False)
events.to_csv(CSV_DIR / "poc_regime_events.csv", index=False)
traceability.to_csv(CSV_DIR / "poc_source_traceability.csv", index=False)
state_definition.to_csv(CSV_DIR / "poc_state_space_definition.csv", index=False)
metrics.to_csv(CSV_DIR / "poc_key_metrics.csv", index=False)
method_sanity_checks.to_csv(CSV_DIR / "poc_method_sanity_checks.csv", index=False)
integrated_event_calendar.to_csv(CSV_DIR / "poc_integrated_event_calendar.csv", index=False)
weekly_costs.to_csv(CSV_DIR / "poc_weekly_costs.csv", index=False)
method_cumulative.to_csv(CSV_DIR / "poc_method_cumulative_comparison.csv", index=False)
baseline_gap_drivers.to_csv(CSV_DIR / "poc_sdd_gap_drivers.csv", index=False)
dynamic_shift_states.to_csv(CSV_DIR / "poc_dynamic_shift_states.csv", index=False)
dynamic_shift_comparison.to_csv(CSV_DIR / "poc_dynamic_shift_method_comparison.csv", index=False)
dynamic_shift_metrics.to_csv(CSV_DIR / "poc_dynamic_shift_metrics.csv", index=False)
dynamic_shift_summary.to_csv(CSV_DIR / "poc_dynamic_shift_summary.csv", index=False)
dynamic_shift_cumulative.to_csv(CSV_DIR / "poc_dynamic_shift_cumulative.csv", index=False)
climate_transition_states.to_csv(CSV_DIR / "poc_climate_transition_states.csv", index=False)
climate_transition_summary.to_csv(CSV_DIR / "poc_climate_transition_summary.csv", index=False)
climate_transition_comparison.to_csv(CSV_DIR / "poc_climate_transition_method_comparison.csv", index=False)
climate_transition_metrics.to_csv(CSV_DIR / "poc_climate_transition_metrics.csv", index=False)
climate_transition_regimes.to_csv(CSV_DIR / "poc_climate_transition_regimes.csv", index=False)
climate_transition_cumulative.to_csv(CSV_DIR / "poc_climate_transition_cumulative.csv", index=False)
climate_policy_summary.to_csv(CSV_DIR / "poc_climate_policy_summary.csv", index=False)
climate_policy_method_comparison.to_csv(CSV_DIR / "poc_climate_policy_method_comparison.csv", index=False)
policy_definition.to_csv(CSV_DIR / "poc_policy_definition.csv", index=False)
policy_decision_summary.to_csv(CSV_DIR / "poc_policy_decision_summary.csv", index=False)
policy_method_comparison.to_csv(CSV_DIR / "poc_policy_method_comparison.csv", index=False)
policy_cost_breakdown.to_csv(CSV_DIR / "poc_policy_cost_breakdown.csv", index=False)
policy_weekly_costs.to_csv(CSV_DIR / "poc_policy_weekly_costs.csv", index=False)
policy_hidden_carbon.to_csv(CSV_DIR / "poc_policy_hidden_carbon.csv", index=False)
policy_component_breakdown.to_csv(CSV_DIR / "poc_policy_component_breakdown.csv", index=False)
policy_causal_attribution.to_csv(CSV_DIR / "poc_policy_causal_attribution.csv", index=False)
policy_pareto.to_csv(CSV_DIR / "poc_policy_pareto.csv", index=False)
network_lane_states.to_csv(CSV_DIR / "poc_network_lane_states.csv", index=False)
sensitivity_hidden_carbon.to_csv(CSV_DIR / "poc_sensitivity_hidden_carbon.csv", index=False)
search_summary.to_csv(CSV_DIR / "poc_search_policy_summary.csv", index=False)
decision_reversal_pairs.to_csv(CSV_DIR / "poc_decision_reversal_pairs.csv", index=False)

# -----------------------------
# Charts
# -----------------------------
plt.figure(figsize=(10, 4.8))
plt.plot(
    states["week"],
    states["classical_reconstructed_weekly_total"],
    marker="o",
    label="LCA classique (profil reconstruit)",
)
plt.plot(time_dependent_dlca["week"], time_dependent_dlca["total"], marker="o", label="Time-Dependent DLCA")
plt.plot(sddlca["week"], sddlca["total"], marker="o", label="SDD")
plt.xlabel("Semaine")
plt.ylabel("Impact hebdomadaire (kgCO2e)")
plt.title("Impact environnemental hebdomadaire par methode")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_weekly_impact_comparison.png", dpi=160)
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(13.8, 4.8), sharex=False)
axes[0].plot(
    states["week"],
    states["demand"],
    marker="o",
    color="#636363",
    label="Demande",
)
axes[0].plot(
    states["week"],
    states["good_output_units"],
    marker="o",
    color="#3182bd",
    label="Production utile",
)
axes[0].plot(
    states["week"],
    states["outbound_shipments"],
    marker="o",
    color="#e6550d",
    label="Expeditions client",
)
axes[0].plot(
    states["week"],
    states["fg_stock_end"],
    marker="o",
    linestyle="--",
    color="#756bb1",
    label="Stock PF",
)
axes[0].plot(
    states["week"],
    states["capacity"],
    marker="o",
    linestyle=":",
    color="#31a354",
    label="Capacite appliquee",
)
axes[0].plot(
    states["week"],
    states["base_capacity"],
    linestyle="--",
    color="#74c476",
    label="Capacite climatique de base",
)
axes[0].set_xlabel("Semaine")
axes[0].set_ylabel("Flux et stock PF (unites)")
axes[0].set_title("Lecture temporelle sur la simulation annuelle commune")
axes[0].set_xlim(1, len(states))
axes[0].grid(alpha=0.2)

dynamic_shift_grid_axis = axes[0].twinx()
dynamic_shift_grid_axis.plot(
    states["week"],
    100 * states["grid_factor"],
    color="#2ca25f",
    linewidth=1.8,
    alpha=0.85,
    label="Facteur reseau applique x100",
)
dynamic_shift_grid_axis.plot(
    states["week"],
    100 * states["base_grid_factor"],
    color="#9e9ac8",
    linewidth=1.4,
    linestyle="--",
    alpha=0.85,
    label="Facteur reseau climatique x100",
)
dynamic_shift_grid_axis.set_ylabel("Facteur reseau x100")

handles_left, labels_left = axes[0].get_legend_handles_labels()
handles_right, labels_right = dynamic_shift_grid_axis.get_legend_handles_labels()
axes[0].legend(handles_left + handles_right, labels_left + labels_right, loc="upper left", fontsize=8)

comparison_plot_labels = {
    CLASSICAL_METHOD: "LCA classique",
    TIME_DEPENDENT_DLCA_METHOD: "Time-Dependent DLCA",
    SDD_METHOD: "SDD",
}
bar_colors = {"LCA classique": "#9ecae1", "Time-Dependent DLCA": "#3182bd", "SDD": "#e6550d"}
dynamic_shift_plot = comparison.copy()
dynamic_shift_plot["method_fr"] = dynamic_shift_plot["method"].map(comparison_plot_labels)
axes[1].bar(
    dynamic_shift_plot["method_fr"],
    dynamic_shift_plot["total_kgCO2e"],
    color=[bar_colors[label] for label in dynamic_shift_plot["method_fr"]],
)
axes[1].set_ylabel("Impact total (kgCO2e)")
axes[1].set_title("Comparaison des methodes sur la meme trajectoire annuelle")
axes[1].grid(axis="y", alpha=0.2)

dynamic_value = float(dynamic_shift_plot.loc[dynamic_shift_plot["method_fr"] == "Time-Dependent DLCA", "total_kgCO2e"].iloc[0])
classical_value = float(dynamic_shift_plot.loc[dynamic_shift_plot["method_fr"] == "LCA classique", "total_kgCO2e"].iloc[0])
sdd_value = float(dynamic_shift_plot.loc[dynamic_shift_plot["method_fr"] == "SDD", "total_kgCO2e"].iloc[0])
axes[1].text(
    0.02,
    0.96,
    f"Ecart Time-Dependent DLCA - LCA classique : +{dynamic_value - classical_value:.1f} kgCO2e\n"
    f"Ecart SDD - Time-Dependent DLCA : +{sdd_value - dynamic_value:.1f} kgCO2e",
    transform=axes[1].transAxes,
    va="top",
    ha="left",
    fontsize=9,
    bbox={"facecolor": "white", "edgecolor": "#bdbdbd", "boxstyle": "round,pad=0.3"},
)

fig.suptitle("Chronologie des flux sur la simulation commune et lecture methodologique", y=1.02)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_dynamic_shift_showcase.png", dpi=160, bbox_inches="tight")
plt.close()

fig, axes = plt.subplots(3, 1, figsize=(14.5, 10.8), sharex=True)
axes[0].plot(
    climate_transition_states["week"],
    climate_transition_states["demand"],
    marker="o",
    color="#3182bd",
    label="Demande",
)
axes[0].plot(
    climate_transition_states["week"],
    climate_transition_states["capacity"],
    marker="o",
    color="#31a354",
    label="Capacite appliquee",
)
axes[0].plot(
    climate_transition_states["week"],
    climate_transition_states["base_capacity"],
    linestyle="--",
    color="#74c476",
    label="Capacite climatique de base",
)
axes[0].set_ylabel("Unites")
axes[0].set_title("Simulation annuelle commune : pressions climatiques et amplification operationnelle")
axes[0].grid(alpha=0.2)
climate_axis = axes[0].twinx()
climate_axis.plot(
    climate_transition_states["week"],
    100 * climate_transition_states["main_supply_availability"],
    color="#e6550d",
    linewidth=2.0,
    label="Disponibilite matiere principale (%)",
)
climate_axis.plot(
    climate_transition_states["week"],
    100 * climate_transition_states["backup_supply_availability"],
    color="#fd8d3c",
    linewidth=1.7,
    linestyle="--",
    label="Disponibilite backup (%)",
)
climate_axis.plot(
    climate_transition_states["week"],
    100 * climate_transition_states["grid_factor"],
    color="#756bb1",
    linewidth=1.8,
    label="Facteur reseau applique x100",
)
climate_axis.plot(
    climate_transition_states["week"],
    100 * climate_transition_states["base_grid_factor"],
    color="#9e9ac8",
    linewidth=1.4,
    linestyle="--",
    label="Facteur reseau climatique x100",
)
climate_axis.set_ylabel("Disponibilite / facteur reseau")
handles_left, labels_left = axes[0].get_legend_handles_labels()
handles_right, labels_right = climate_axis.get_legend_handles_labels()
axes[0].legend(handles_left + handles_right, labels_left + labels_right, loc="upper right", ncol=2, fontsize=8)

regime_color_map = {"nominal": "#c7e9c0", "tendu": "#fdd49e", "crise": "#fcae91"}
for week, regime in zip(climate_transition_regimes["week"], climate_transition_regimes["environmental_regime"]):
    axes[1].axvspan(week - 0.5, week + 0.5, color=regime_color_map[regime], alpha=0.18)
axes[1].plot(
    climate_transition_states["week"],
    climate_transition_states["backlog_end"],
    marker="o",
    color="#e6550d",
    label="Backlog fin de semaine",
)
axes[1].plot(
    climate_transition_states["week"],
    climate_transition_states["good_output_backup_units"],
    marker="o",
    color="#756bb1",
    label="Production issue du backup",
)
axes[1].bar(
    climate_transition_states["week"],
    climate_transition_states["outbound_shipments"].where(climate_transition_states["outbound_mode"] == "air", 0.0),
    color="#f16913",
    alpha=0.45,
    label="Expeditions aeriennes",
)
axes[1].set_ylabel("Unites")
axes[1].set_title("Evenements operationnels endogenes et regimes environnementaux")
axes[1].grid(alpha=0.2)
handles_left, labels_left = axes[1].get_legend_handles_labels()
regime_handles = [
    plt.Rectangle((0, 0), 1, 1, color=regime_color_map["nominal"], alpha=0.18),
    plt.Rectangle((0, 0), 1, 1, color=regime_color_map["tendu"], alpha=0.18),
    plt.Rectangle((0, 0), 1, 1, color=regime_color_map["crise"], alpha=0.18),
]
regime_labels = ["Regime nominal", "Regime tendu", "Regime de crise"]
axes[1].legend(
    handles_left + regime_handles,
    labels_left + regime_labels,
    loc="upper left",
    ncol=2,
    fontsize=8,
)

axes[2].plot(
    climate_transition_cumulative["week"],
    climate_transition_cumulative["classical_cumulative_kgCO2e"],
    marker="o",
    color="#9ecae1",
    label="LCA classique (profil reconstruit)",
)
axes[2].plot(
    climate_transition_cumulative["week"],
    climate_transition_cumulative["dynamic_cumulative_kgCO2e"],
    marker="o",
    color="#3182bd",
    label="Time-Dependent DLCA",
)
axes[2].plot(
    climate_transition_cumulative["week"],
    climate_transition_cumulative["sdd_cumulative_kgCO2e"],
    marker="o",
    color="#e6550d",
    linewidth=2.1,
    label="SDD",
)
axes[2].set_xlabel("Semaine")
axes[2].set_ylabel("Impact cumule (kgCO2e)")
axes[2].set_title("Accumulation des impacts sur un scenario de transition climatique")
axes[2].grid(alpha=0.2)
axes[2].legend(loc="upper left")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_climate_transition_showcase.png", dpi=160, bbox_inches="tight")
plt.close()

climate_policy_order = [policy.label for policy in COUNTERFACTUAL_POLICIES]
climate_policy_pivot = (
    climate_policy_method_comparison
    .pivot(index="policy_label", columns="method", values="total_kgCO2e")
    .reindex(climate_policy_order)
)
climate_policy_x = list(range(len(climate_policy_pivot.index)))
climate_bar_width = 0.24
plt.figure(figsize=(12.8, 5.8))
for idx, method in enumerate(climate_policy_pivot.columns):
    x_positions = [x + (idx - 1) * climate_bar_width for x in climate_policy_x]
    plt.bar(
        x_positions,
        climate_policy_pivot[method],
        width=climate_bar_width,
        label=comparison_plot_labels.get(method, method),
    )
plt.xticks(climate_policy_x, climate_policy_pivot.index, rotation=15, ha="right")
plt.ylabel("Impact total (kgCO2e)")
plt.title("Politiques contrefactuelles sous transition climatique")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_climate_policy_comparison.png", dpi=160)
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(13.4, 4.8), sharex=True)
axes[0].plot(
    method_cumulative["week"],
    method_cumulative["classical_cumulative_kgCO2e"],
    marker="o",
    color="#9ecae1",
    label="LCA classique (profil reconstruit)",
)
axes[0].plot(
    method_cumulative["week"],
    method_cumulative["dynamic_cumulative_kgCO2e"],
    marker="o",
    color="#3182bd",
    label="Time-Dependent DLCA",
)
axes[0].plot(
    method_cumulative["week"],
    method_cumulative["sdd_cumulative_kgCO2e"],
    marker="o",
    color="#e6550d",
    linewidth=2.2,
    label="SDD",
)
axes[0].set_xlabel("Semaine")
axes[0].set_ylabel("Impact cumule (kgCO2e)")
axes[0].set_title("Impact cumule : LCA classique (profil reconstruit) vs Time-Dependent DLCA vs SDD")
axes[0].grid(alpha=0.2)
axes[0].legend()

axes[1].plot(
    method_cumulative["week"],
    method_cumulative["sdd_minus_lca_cumulative"],
    marker="o",
    color="#756bb1",
    label="SDD - LCA classique",
)
axes[1].plot(
    method_cumulative["week"],
    method_cumulative["sdd_minus_dynamic_cumulative"],
    marker="o",
    color="#dd1c77",
    label="SDD - Time-Dependent DLCA",
)
axes[1].axhline(0, color="black", linewidth=0.8)
axes[1].set_xlabel("Semaine")
axes[1].set_ylabel("Sur-impact revele par le SDD (kgCO2e)")
axes[1].set_title("Sur-impact cumule capte par le SDD")
axes[1].grid(alpha=0.2)
axes[1].legend()

last_row = method_cumulative.iloc[-1]
axes[1].text(
    float(last_row["week"]) + 0.1,
    float(last_row["sdd_minus_lca_cumulative"]),
    f'+{float(last_row["sdd_minus_lca_cumulative"]):.0f}',
    color="#756bb1",
    va="center",
    fontsize=8,
)
axes[1].text(
    float(last_row["week"]) + 0.1,
    float(last_row["sdd_minus_dynamic_cumulative"]),
    f'+{float(last_row["sdd_minus_dynamic_cumulative"]):.0f}',
    color="#dd1c77",
    va="center",
    fontsize=8,
)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_method_cumulative_comparison.png", dpi=160)
plt.close()

component_panels = [
    ("material", "Matiere", "#9ecae1"),
    ("inbound_transport", "Transport amont", "#6baed6"),
    ("production_energy", "Energie", "#3182bd"),
    ("outbound_transport", "Transport aval", "#fd8d3c"),
    ("storage", "Stockage", "#bdbdbd"),
    ("scrap", "Scrap", "#756bb1"),
]

fig, axes = plt.subplots(
    2,
    3,
    figsize=(22.0, 8.4),
    sharex="col",
    gridspec_kw={"height_ratios": [1.15, 0.95]},
)

for ax, prefix, title in [
    (axes[0, 0], "classical", "LCA classique"),
    (axes[0, 1], "dynamic", "Time-Dependent DLCA"),
    (axes[0, 2], "sdd", "SDD"),
]:
    bottom_values = [0.0] * len(baseline_gap_drivers.index)
    for component, label, color in component_panels:
        column = f"{prefix}_{component}"
        values = baseline_gap_drivers[column]
        ax.bar(
            baseline_gap_drivers["week"],
            values,
            bottom=bottom_values,
            color=color,
            label=label if prefix == "classical" else None,
        )
        bottom_values = [bottom + value for bottom, value in zip(bottom_values, values)]
    ax.plot(
        baseline_gap_drivers["week"],
        baseline_gap_drivers[f"{prefix}_total"],
        color="black",
        marker="o",
        linewidth=1.7,
        label="Total" if prefix == "classical" else None,
    )
    for week in baseline_gap_drivers.loc[baseline_gap_drivers["air_shipments_units"] > 0, "week"]:
        ax.axvspan(week - 0.45, week + 0.45, color="#fdd0a2", alpha=0.18)
    ax.set_xlabel("Semaine")
    ax.set_ylabel("Impact hebdomadaire (kgCO2e)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.2)

axes[0, 0].legend(loc="upper left", fontsize=8)
axes[0, 0].cla()
classical_component_labels = [label for _, label, _ in component_panels]
classical_component_values = [float(classical[key]) for key, _, _ in component_panels]
axes[0, 0].bar(
    classical_component_labels,
    classical_component_values,
    color=[color for _, _, color in component_panels],
)
axes[0, 0].set_ylabel("Impact total (kgCO2e)")
axes[0, 0].set_title("LCA classique : decomposition agrégée")
axes[0, 0].tick_params(axis="x", rotation=20)
axes[0, 0].grid(axis="y", alpha=0.2)

axes[1, 0].plot(
    baseline_gap_drivers["week"],
    [float(baseline_gap_drivers["good_output_units"].mean())] * len(baseline_gap_drivers),
    color="#3182bd",
    linewidth=2,
    label="Production utile moyenne",
)
axes[1, 0].set_xlabel("Semaine")
axes[1, 0].set_ylabel("Production utile moyenne (unites)", color="#3182bd")
axes[1, 0].tick_params(axis="y", labelcolor="#3182bd")
axes[1, 0].set_title("Ce que voit la LCA classique : des moyennes")
axes[1, 0].grid(axis="y", alpha=0.2)

classical_trigger_axis = axes[1, 0].twinx()
classical_trigger_axis.plot(
    baseline_gap_drivers["week"],
    [float(baseline_gap_drivers["outbound_shipments"].mean())] * len(baseline_gap_drivers),
    color="black",
    linewidth=2,
    label="Expeditions client",
)
classical_trigger_axis.plot(
    baseline_gap_drivers["week"],
    100 * baseline_gap_drivers["average_grid_factor"],
    color="#31a354",
    linestyle="--",
    linewidth=2,
    label="Reseau moyen x100",
)
classical_trigger_axis.plot(
    baseline_gap_drivers["week"],
    [float(baseline_gap_drivers["total_stock_units"].mean())] * len(baseline_gap_drivers),
    color="#756bb1",
    linestyle=":",
    linewidth=2,
    label="Stock total",
)
classical_trigger_axis.set_ylabel("Expeditions / reseau moyen x100 / stock")

handles_left, labels_left = axes[1, 0].get_legend_handles_labels()
handles_right, labels_right = classical_trigger_axis.get_legend_handles_labels()
axes[1, 0].legend(
    handles_left + handles_right,
    labels_left + labels_right,
    loc="upper left",
    fontsize=8,
)

for week in baseline_gap_drivers.loc[baseline_gap_drivers["air_shipments_units"] > 0, "week"]:
    axes[1, 1].axvspan(week - 0.45, week + 0.45, color="#fdd0a2", alpha=0.12)
axes[1, 1].bar(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["good_output_units"],
    color="#9ecae1",
    alpha=0.8,
    label="Production utile",
)
axes[1, 1].set_xlabel("Semaine")
axes[1, 1].set_ylabel("Production utile (unites)", color="#3182bd")
axes[1, 1].tick_params(axis="y", labelcolor="#3182bd")
axes[1, 1].set_title("Ce que voit la Time-Dependent DLCA")
axes[1, 1].grid(axis="y", alpha=0.2)

dynamic_trigger_axis = axes[1, 1].twinx()
dynamic_trigger_axis.plot(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["outbound_shipments"],
    color="black",
    marker="o",
    label="Expeditions client",
)
dynamic_trigger_axis.plot(
    baseline_gap_drivers["week"],
    100 * baseline_gap_drivers["grid_factor"],
    color="#31a354",
    marker="s",
    linestyle="--",
    label="Facteur reseau x100",
)
dynamic_trigger_axis.plot(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["total_stock_units"],
    color="#756bb1",
    marker="^",
    linestyle=":",
    label="Stock total",
)
dynamic_trigger_axis.set_ylabel("Expeditions / facteur reseau x100 / stock")

handles_left, labels_left = axes[1, 1].get_legend_handles_labels()
handles_right, labels_right = dynamic_trigger_axis.get_legend_handles_labels()
axes[1, 1].legend(
    handles_left + handles_right,
    labels_left + labels_right,
    loc="upper left",
    fontsize=8,
)

for week in baseline_gap_drivers.loc[baseline_gap_drivers["air_shipments_units"] > 0, "week"]:
    axes[1, 2].axvspan(week - 0.45, week + 0.45, color="#fdd0a2", alpha=0.2)
axes[1, 2].bar(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["good_output_units"],
    color="#9ecae1",
    alpha=0.35,
    label="Production utile",
)
axes[1, 2].bar(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["backup_output_units"],
    color="#fdae6b",
    alpha=0.8,
    label="Production issue du backup",
)
axes[1, 2].set_xlabel("Semaine")
axes[1, 2].set_ylabel("Signaux de production (unites)", color="#f16913")
axes[1, 2].tick_params(axis="y", labelcolor="#f16913")
axes[1, 2].set_title("Ce que voit le SDD")
axes[1, 2].grid(axis="y", alpha=0.2)

trigger_axis = axes[1, 2].twinx()
trigger_axis.plot(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["outbound_shipments"],
    color="#636363",
    marker="o",
    linewidth=1.2,
    alpha=0.8,
    label="Expeditions client",
)
trigger_axis.plot(
    baseline_gap_drivers["week"],
    100 * baseline_gap_drivers["grid_factor"],
    color="#31a354",
    marker="s",
    linestyle="--",
    linewidth=1.2,
    alpha=0.8,
    label="Facteur reseau x100",
)
trigger_axis.plot(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["total_stock_units"],
    color="#756bb1",
    marker="^",
    linestyle=":",
    linewidth=1.2,
    alpha=0.8,
    label="Stock total",
)
trigger_axis.plot(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["backlog_end"],
    color="black",
    marker="o",
    label="Backlog",
)
trigger_axis.plot(
    baseline_gap_drivers["week"],
    baseline_gap_drivers["capacity_utilization_pct"],
    color="#3182bd",
    marker="s",
    linestyle="--",
    label="Utilisation de capacite (%)",
)
trigger_axis.set_ylabel("Backlog / utilisation (%) / autres signaux")

handles_left, labels_left = axes[1, 2].get_legend_handles_labels()
handles_right, labels_right = trigger_axis.get_legend_handles_labels()
air_patch = plt.Rectangle((0, 0), 1, 1, color="#fdd0a2", alpha=0.2)
axes[1, 2].legend(
    handles_left + handles_right + [air_patch],
    labels_left + labels_right + ["Semaines en aerien"],
    loc="upper left",
    fontsize=8,
)
fig.suptitle("Pourquoi le SDD trouve plus d'impact que la Time-Dependent DLCA", y=1.02)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_sdd_gap_drivers.png", dpi=160, bbox_inches="tight")
plt.close()

plt.figure(figsize=(10, 4.8))
plt.plot(states["week"], states["backlog_end"], marker="o", label="Backlog")
plt.xlabel("Semaine")
plt.ylabel("Backlog (unites)")
plt.title("Operational state: backlog over time")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_backlog.png", dpi=160)
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
scatter = axes[0].scatter(
    state_trajectory["state_end_raw_stock_total"],
    state_trajectory["state_end_backlog"],
    c=state_trajectory["week"],
    s=40 + 8 * state_trajectory["state_end_total_pipeline"],
    cmap="viridis",
)
for _, r in state_trajectory.iterrows():
    axes[0].text(
        r["state_end_raw_stock_total"] + 0.2,
        r["state_end_backlog"] + 0.5,
        str(int(r["week"])),
        fontsize=7,
    )
axes[0].set_xlabel("Stock MP final (unites)")
axes[0].set_ylabel("Backlog final (unites)")
axes[0].set_title("Projection reduite de l'espace d'etat")
axes[0].grid(alpha=0.2)
colorbar = plt.colorbar(scatter, ax=axes[0])
colorbar.set_label("Semaine")

axes[1].plot(state_trajectory["week"], state_trajectory["state_end_backlog"], marker="o", label="Backlog")
axes[1].plot(state_trajectory["week"], state_trajectory["state_end_raw_stock_total"], marker="o", label="Stock MP")
axes[1].plot(state_trajectory["week"], state_trajectory["state_end_fg_stock_total"], marker="o", label="Stock PF")
axes[1].plot(
    state_trajectory["week"],
    state_trajectory["state_end_total_pipeline"],
    marker="o",
    label="Matieres en transit",
)
axes[1].set_xlabel("Semaine")
axes[1].set_ylabel("Valeur de composante d'etat")
axes[1].set_title("Composantes de l'etat dans le temps")
axes[1].legend()
axes[1].grid(alpha=0.2)

plt.tight_layout()
plt.savefig(IMG_DIR / "poc_state_space_projection.png", dpi=160)
plt.close()

total_stock_units = states["raw_stock_end"] + states["fg_stock_end"]
avg_grid_factor = float(states["grid_factor"].mean())
fig, axes = plt.subplots(2, 3, figsize=(18.5, 8.8))
classical_components_fr = {
    "material": "Matiere",
    "inbound_transport": "Transport amont",
    "production_energy": "Energie",
    "outbound_transport": "Transport aval",
    "storage": "Stockage",
    "scrap": "Scrap",
}
classical_row = breakdown.loc[breakdown["method"] == "Classical LCA"].iloc[0]
axes[0, 0].bar(
    list(classical_components_fr.values()),
    [float(classical_row[key]) for key in classical_components_fr],
    color=["#9ecae1", "#6baed6", "#3182bd", "#fd8d3c", "#bdbdbd", "#756bb1"],
)
axes[0, 0].set_ylabel("Impact total (kgCO2e)")
axes[0, 0].set_title("LCA classique : decomposition agregée")
axes[0, 0].tick_params(axis="x", rotation=20)
axes[0, 0].grid(axis="y", alpha=0.2)

axes[0, 1].plot(dynamic["week"], dynamic["total"], marker="o", color="#3182bd", label="Impact dynamique total")
axes[0, 1].plot(
    dynamic["week"],
    dynamic["production_energy"],
    marker="o",
    linestyle="--",
    color="#31a354",
    label="Energie",
)
axes[0, 1].plot(
    dynamic["week"],
    dynamic["outbound_transport"],
    marker="o",
    linestyle=":",
    color="#fd8d3c",
    label="Transport aval",
)
axes[0, 1].set_xlim(1, len(states))
axes[0, 1].set_xlabel("Semaine")
axes[0, 1].set_ylabel("Impact hebdomadaire (kgCO2e)")
axes[0, 1].set_title("Time-Dependent DLCA : serie temporelle")
axes[0, 1].legend(fontsize=8)
axes[0, 1].grid(alpha=0.2)

for week in states.loc[states["outbound_mode"] == "air", "week"]:
    axes[0, 2].axvspan(week - 0.45, week + 0.45, color="#fdd0a2", alpha=0.18)
axes[0, 2].plot(
    sddlca["week"],
    sddlca["total"],
    marker="o",
    color="#e6550d",
    label="Impact SDD total",
)
axes[0, 2].plot(
    sddlca["week"],
    sddlca["production_energy"],
    marker="o",
    linestyle="--",
    color="#31a354",
    label="Energie",
)
axes[0, 2].plot(
    sddlca["week"],
    sddlca["outbound_transport"],
    marker="o",
    linestyle=":",
    color="#fd8d3c",
    label="Transport aval",
)
axes[0, 2].set_xlim(1, len(states))
axes[0, 2].set_xlabel("Semaine")
axes[0, 2].set_ylabel("Impact hebdomadaire (kgCO2e)")
axes[0, 2].set_title("SDD : serie temporelle enrichie par les etats")
axes[0, 2].grid(alpha=0.2)

sdd_state_axis = axes[0, 2].twinx()
sdd_state_axis.plot(
    state_trajectory["week"],
    state_trajectory["state_end_backlog"],
    marker="o",
    color="black",
    alpha=0.85,
    label="Backlog",
)
sdd_state_axis.plot(
    state_trajectory["week"],
    state_trajectory["state_end_raw_stock_total"],
    marker="o",
    color="#3182bd",
    alpha=0.8,
    label="Stock MP",
)
sdd_state_axis.plot(
    state_trajectory["week"],
    state_trajectory["state_end_fg_stock_total"],
    marker="o",
    color="#9ecae1",
    alpha=0.8,
    label="Stock PF",
)
sdd_state_axis.plot(
    state_trajectory["week"],
    state_trajectory["state_end_total_pipeline"],
    marker="o",
    color="#756bb1",
    alpha=0.8,
    label="Matieres en transit",
)
sdd_state_axis.set_ylabel("Valeurs d'etat")

handles_left, labels_left = axes[0, 2].get_legend_handles_labels()
handles_right, labels_right = sdd_state_axis.get_legend_handles_labels()
air_patch = plt.Rectangle((0, 0), 1, 1, color="#fdd0a2", alpha=0.18)
axes[0, 2].legend(
    handles_left + handles_right + [air_patch],
    labels_left + labels_right + ["Semaines en aerien"],
    fontsize=8,
    loc="upper left",
)

axes[1, 0].plot(
    states["week"],
    [float(states["good_output_units"].mean())] * len(states),
    linestyle="-",
    color="#3182bd",
    label="Production utile moyenne",
)
axes[1, 0].plot(
    states["week"],
    [float(states["outbound_shipments"].mean())] * len(states),
    linestyle="-",
    color="black",
    label="Expeditions client moyennes",
)
axes[1, 0].plot(
    states["week"],
    [float(total_stock_units.mean())] * len(states),
    linestyle="-",
    color="#756bb1",
    label="Stock total moyen",
)
axes[1, 0].plot(
    states["week"],
    [100 * avg_grid_factor] * len(states),
    linestyle="--",
    color="#31a354",
    label="Reseau moyen x100",
)
axes[1, 0].set_xlabel("Semaine")
axes[1, 0].set_ylabel("Valeur observee")
axes[1, 0].set_title("Ce que voit la LCA classique : des moyennes")
axes[1, 0].legend(fontsize=8)
axes[1, 0].grid(alpha=0.2)
axes[1, 0].set_xlim(1, len(states))

axes[1, 1].plot(states["week"], states["good_output_units"], marker="o", label="Production utile")
axes[1, 1].plot(states["week"], states["outbound_shipments"], marker="o", label="Expeditions client")
axes[1, 1].plot(states["week"], total_stock_units, marker="o", label="Stock total")
axes[1, 1].plot(states["week"], 100 * states["grid_factor"], marker="o", label="Facteur reseau x100")
axes[1, 1].set_xlabel("Semaine")
axes[1, 1].set_ylabel("Valeur observee")
axes[1, 1].set_title("Ce que voit la Time-Dependent DLCA dans le temps")
axes[1, 1].legend(fontsize=8)
axes[1, 1].grid(alpha=0.2)
axes[1, 1].set_xlim(1, len(states))

for week in states.loc[states["outbound_mode"] == "air", "week"]:
    axes[1, 2].axvspan(week - 0.45, week + 0.45, color="#fdd0a2", alpha=0.18)
axes[1, 2].bar(
    states["week"],
    states["good_output_backup_units"],
    color="#fdae6b",
    alpha=0.65,
    label="Production issue du backup",
)
axes[1, 2].plot(state_trajectory["week"], state_trajectory["state_end_backlog"], marker="o", label="Backlog")
axes[1, 2].plot(state_trajectory["week"], state_trajectory["state_end_raw_stock_total"], marker="o", label="Stock MP")
axes[1, 2].plot(state_trajectory["week"], state_trajectory["state_end_fg_stock_total"], marker="o", label="Stock PF")
axes[1, 2].plot(
    state_trajectory["week"],
    state_trajectory["state_end_total_pipeline"],
    marker="o",
    label="Matieres en transit",
)
axes[1, 2].set_xlabel("Semaine")
axes[1, 2].set_ylabel("Valeur d'etat")
axes[1, 2].set_title("Ce que le SDD ajoute a la Time-Dependent DLCA")
axes[1, 2].legend(fontsize=8)
axes[1, 2].grid(alpha=0.2)
axes[1, 2].set_xlim(1, len(states))

fig.suptitle("Comment chaque methode represente l'etat de la supply chain", y=1.01)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_state_space_method_comparison.png", dpi=160, bbox_inches="tight")
plt.close()

fig, ax1 = plt.subplots(figsize=(10, 4.8))
ax1.bar(states["week"], states["good_output_main_units"], label="Production bonne issue de la source principale")
ax1.bar(
    states["week"],
    states["good_output_backup_units"],
    bottom=states["good_output_main_units"],
    label="Production bonne issue de la source de secours",
)
ax1.set_xlabel("Semaine")
ax1.set_ylabel("Production bonne (unites)")
ax1.set_title("Provenance de la production bonne hebdomadaire")

ax2 = ax1.twinx()
ax2.plot(states["week"], states["backlog_end"], color="black", marker="o", label="Backlog")
ax2.set_ylabel("Backlog (unites)")

handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_source_traceability.png", dpi=160)
plt.close()

plt.figure(figsize=(10, 4.8))
comparison_plot_labels = {
    CLASSICAL_METHOD: "LCA classique",
    TIME_DEPENDENT_DLCA_METHOD: "Time-Dependent DLCA",
    SDD_METHOD: "SDD",
}
plt.bar(comparison["method"].map(comparison_plot_labels), comparison["total_kgCO2e"])
plt.ylabel("Impact total (kgCO2e)")
plt.title("Comparaison des impacts totaux")
plt.xticks(rotation=15, ha="right")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_total_impact_comparison.png", dpi=160)
plt.close()

policy_order = [policy.label for policy in COUNTERFACTUAL_POLICIES]
policy_method_pivot = (
    policy_method_comparison
    .pivot(index="policy_label", columns="method", values="total_kgCO2e")
    .reindex(policy_order)
)
policy_x = list(range(len(policy_method_pivot.index)))
bar_width = 0.24
plt.figure(figsize=(12, 5.2))
for idx, method in enumerate(policy_method_pivot.columns):
    x_positions = [x + (idx - 1) * bar_width for x in policy_x]
    plt.bar(x_positions, policy_method_pivot[method], width=bar_width, label=comparison_plot_labels.get(method, method))
plt.xticks(policy_x, policy_method_pivot.index, rotation=15, ha="right")
plt.ylabel("Impact total (kgCO2e)")
plt.title("Politiques contrefactuelles : resultat carbone par methode")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_method_comparison.png", dpi=160)
plt.close()

fig, axes = plt.subplots(1, 3, figsize=(18, 5.2), sharex=True)
bubble_sizes = 40 + 0.015 * policy_decision_summary["total_cost"]
for ax, carbon_col, title in [
    (axes[0], "classical_total_kgCO2e", "Frontiere de decision - LCA classique"),
    (axes[1], "dynamic_total_kgCO2e", "Frontiere de decision - Time-Dependent DLCA"),
    (axes[2], "sddlca_total_kgCO2e", "Frontiere de decision - SDD"),
]:
    ax.scatter(
        policy_decision_summary["same_week_service_pct"],
        policy_decision_summary[carbon_col],
        s=bubble_sizes,
        c=range(len(policy_decision_summary)),
        cmap="tab10",
        alpha=0.85,
    )
    for _, r in policy_decision_summary.iterrows():
        ax.text(
            r["same_week_service_pct"] + 0.15,
            r[carbon_col] + 10,
            r["policy_label"],
            fontsize=8,
        )
    ax.set_xlabel("Service la meme semaine (%)")
    ax.set_ylabel("Impact total (kgCO2e)")
    ax.set_title(title)
    ax.grid(alpha=0.2)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_decision_frontier.png", dpi=160)
plt.close()

plt.figure(figsize=(12, 5.6))
for idx, policy_label in enumerate(policy_order):
    row = policy_method_pivot.loc[policy_label]
    plt.plot(
        [row[TIME_DEPENDENT_DLCA_METHOD], row[SDD_METHOD]],
        [idx, idx],
        color="0.6",
        linewidth=2,
    )
    plt.scatter(row[CLASSICAL_METHOD], idx, color="#9ecae1", s=50, label="LCA classique" if idx == 0 else None)
    plt.scatter(
        row[TIME_DEPENDENT_DLCA_METHOD],
        idx,
        color="#3182bd",
        s=60,
        label="Time-Dependent DLCA" if idx == 0 else None,
    )
    plt.scatter(
        row[SDD_METHOD],
        idx,
        color="#e6550d",
        s=65,
        label="SDD" if idx == 0 else None,
    )
    gap_value = row[SDD_METHOD] - row[TIME_DEPENDENT_DLCA_METHOD]
    plt.text(row[SDD_METHOD] + 18, idx, f"+{gap_value:.0f}", va="center", fontsize=8)
plt.yticks(range(len(policy_order)), policy_order)
plt.xlabel("Impact total (kgCO2e)")
plt.ylabel("Politique")
plt.title("Comparaison des politiques avec ecart carbone explicite")
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_method_gap.png", dpi=160)
plt.close()

component_order = [
    "material",
    "inbound_transport",
    "production_energy",
    "outbound_transport",
    "storage",
    "scrap",
]
component_colors = {
    "material": "#9ecae1",
    "inbound_transport": "#6baed6",
    "production_energy": "#3182bd",
    "outbound_transport": "#fd8d3c",
    "storage": "#bdbdbd",
    "scrap": "#e6550d",
}
fig, axes = plt.subplots(1, 3, figsize=(18, 5.6), sharey=True)
method_titles = {
    CLASSICAL_METHOD: "LCA classique",
    TIME_DEPENDENT_DLCA_METHOD: "Time-Dependent DLCA",
    SDD_METHOD: "SDD",
}
for ax, method_label in zip(axes, [CLASSICAL_METHOD, TIME_DEPENDENT_DLCA_METHOD, SDD_METHOD]):
    method_df = (
        policy_component_breakdown
        .loc[policy_component_breakdown["method_label"] == method_label]
        .set_index("policy_label")
        .reindex(policy_order)
    )
    bottom_values = [0.0] * len(method_df.index)
    for component in component_order:
        values = method_df[component]
        ax.bar(
            method_df.index,
            values,
            bottom=bottom_values,
            label=component if method_label == CLASSICAL_METHOD else None,
            color=component_colors[component],
        )
        bottom_values = [bottom + value for bottom, value in zip(bottom_values, values)]
    ax.set_title(method_titles[method_label])
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", alpha=0.2)

axes[0].set_ylabel("Decomposition de l'impact total (kgCO2e)")
fig.suptitle("Decomposition des impacts : LCA classique vs Time-Dependent DLCA vs SDD", y=1.02)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=3)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_causal_attribution.png", dpi=160, bbox_inches="tight")
plt.close()

fig, axes = plt.subplots(1, 3, figsize=(18, 5.2), sharex=True)
for ax, carbon_col, flag_col, title in [
    (axes[0], "classical_total_kgCO2e", "pareto_efficient_lca", "Frontiere de Pareto - LCA classique"),
    (axes[1], "dynamic_total_kgCO2e", "pareto_efficient_dynamic", "Frontiere de Pareto - Time-Dependent DLCA"),
    (axes[2], "sddlca_total_kgCO2e", "pareto_efficient_sdd", "Frontiere de Pareto - SDD"),
]:
    for _, r in policy_pareto.iterrows():
        marker_size = 40 + 0.015 * r["total_cost"]
        color = "#2ca25f" if r[flag_col] else "#bdbdbd"
        ax.scatter(r["same_week_service_pct"], r[carbon_col], s=marker_size, color=color, alpha=0.85)
        ax.text(r["same_week_service_pct"] + 0.12, r[carbon_col] + 12, r["policy_label"], fontsize=8)
    ax.set_xlabel("Service la meme semaine (%)")
    ax.set_ylabel("Impact total (kgCO2e)")
    ax.set_title(title)
    ax.grid(alpha=0.2)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_pareto_frontier.png", dpi=160)
plt.close()

decision_reversal_path = IMG_DIR / "poc_decision_reversal.png"
if best_decision_reversal is not None:
    policy_a_label = str(best_decision_reversal["policy_a"])
    policy_b_label = str(best_decision_reversal["policy_b"])
    pair_summary = (
        search_summary.loc[search_summary["policy_label"].isin([policy_a_label, policy_b_label])]
        .copy()
        .set_index("policy_label")
        .loc[[policy_a_label, policy_b_label]]
        .reset_index()
    )
    plot_summary = pair_summary.set_index("policy_label").loc[[policy_a_label, policy_b_label]]
    short_labels = {"A": policy_a_label, "B": policy_b_label}
    y_positions = {"A": 1.0, "B": 0.0}
    fig, ax = plt.subplots(figsize=(13.6, 5.4))
    for short_label, policy_label in short_labels.items():
        row = plot_summary.loc[policy_label]
        y_value = y_positions[short_label]
        ax.plot(
            [row["time_dependent_dlca_total_kgCO2e"], row["sddlca_total_kgCO2e"]],
            [y_value, y_value],
            color="0.65",
            linewidth=2.2,
        )
        ax.scatter(
            row["classical_total_kgCO2e"],
            y_value,
            color="#9ecae1",
            s=55,
            label="LCA classique" if short_label == "A" else None,
            zorder=3,
        )
        ax.scatter(
            row["time_dependent_dlca_total_kgCO2e"],
            y_value,
            color="#3182bd",
            s=65,
            label="Time-Dependent DLCA" if short_label == "A" else None,
            zorder=3,
        )
        ax.scatter(
            row["sddlca_total_kgCO2e"],
            y_value,
            color="#e6550d",
            s=70,
            label="SDD" if short_label == "A" else None,
            zorder=3,
        )

    ax.set_yticks([y_positions["A"], y_positions["B"]], ["Politique A", "Politique B"])
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("Impact total (kgCO2e)")
    ax.set_ylabel("Politique")
    ax.set_title(
        f"Inversion de decision pour un service >= {float(best_decision_reversal['service_floor_pct']):.0f} %"
    )
    ax.grid(axis="x", alpha=0.2)
    ax.legend(loc="lower right")
    td_preferred_label = str(best_decision_reversal["dynamic_prefers"])
    sdd_preferred_label = str(best_decision_reversal["sddlca_prefers"])
    fig.text(
        0.13,
        0.02,
        f"Politique A : {policy_a_label}\n"
        f"Politique B : {policy_b_label}\n"
        f"Time-Dependent DLCA prefere : {td_preferred_label}\n"
        f"SDD prefere : {sdd_preferred_label}",
        va="bottom",
        ha="left",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#bdbdbd", "boxstyle": "round,pad=0.3"},
    )
    plt.tight_layout(rect=(0, 0.12, 1, 1))
    plt.savefig(decision_reversal_path, dpi=160, bbox_inches="tight")
    plt.close()
elif decision_reversal_path.exists():
    decision_reversal_path.unlink()

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
axes[0].plot(network_lane_states["week"], network_lane_states["core_backlog_end"], marker="o", label="Backlog coeur")
axes[0].plot(network_lane_states["week"], network_lane_states["remote_backlog_end"], marker="o", label="Backlog distant")
axes[0].set_xlabel("Semaine")
axes[0].set_ylabel("Backlog par voie (unites)")
axes[0].set_title("Backlogs du mini-reseau a deux clients")
axes[0].legend()
axes[0].grid(alpha=0.2)

axes[1].bar(network_lane_states["week"], network_lane_states["hidden_network_outbound"], color="#e6550d")
axes[1].set_xlabel("Semaine")
axes[1].set_ylabel("Sur-impact aval cache (kgCO2e)")
axes[1].set_title("Carbone cache du mini-reseau a deux clients")
axes[1].grid(alpha=0.2)
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_network_lane_comparison.png", dpi=160)
plt.close()

sensitivity_order = ["none", "mild", "baseline", "severe"]
air_order = ["0.8x", "1.0x", "1.2x", "1.5x"]
shipments_pivot = (
    sensitivity_hidden_carbon
    .pivot(index="severity_label", columns="air_label", values="total_shipments")
    .reindex(index=sensitivity_order, columns=air_order)
)
classical_intensity_pivot = (
    sensitivity_hidden_carbon
    .pivot(index="severity_label", columns="air_label", values="classical_kg_per_shipped_unit")
    .reindex(index=sensitivity_order, columns=air_order)
)
dynamic_intensity_pivot = (
    sensitivity_hidden_carbon
    .pivot(index="severity_label", columns="air_label", values="dynamic_kg_per_shipped_unit")
    .reindex(index=sensitivity_order, columns=air_order)
)
sdd_intensity_pivot = (
    sensitivity_hidden_carbon
    .pivot(index="severity_label", columns="air_label", values="sddlca_kg_per_shipped_unit")
    .reindex(index=sensitivity_order, columns=air_order)
)
fig, axes = plt.subplots(1, 4, figsize=(19.0, 5.0))
shipments_map = axes[0].imshow(shipments_pivot.values, cmap="Blues", aspect="auto")
axes[0].set_xticks(range(len(air_order)))
axes[0].set_xticklabels(air_order)
axes[0].set_yticks(range(len(sensitivity_order)))
axes[0].set_yticklabels(sensitivity_order)
axes[0].set_xlabel("Multiplicateur d'emission de l'aerien")
axes[0].set_ylabel("Severite de la disruption")
axes[0].set_title("Expeditions client totales")
for row_idx, row_values in enumerate(shipments_pivot.values):
    for col_idx, value in enumerate(row_values):
        axes[0].text(col_idx, row_idx, f"{value:.0f}", ha="center", va="center", fontsize=8)
fig.colorbar(shipments_map, ax=axes[0], label="Unites expediees")

classical_map = axes[1].imshow(classical_intensity_pivot.values, cmap="Greens", aspect="auto")
axes[1].set_xticks(range(len(air_order)))
axes[1].set_xticklabels(air_order)
axes[1].set_yticks(range(len(sensitivity_order)))
axes[1].set_yticklabels(sensitivity_order)
axes[1].set_xlabel("Multiplicateur d'emission de l'aerien")
axes[1].set_ylabel("Severite de la disruption")
axes[1].set_title("Intensite de la LCA classique par unite expediee")
for row_idx, row_values in enumerate(classical_intensity_pivot.values):
    for col_idx, value in enumerate(row_values):
        axes[1].text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=8)
fig.colorbar(classical_map, ax=axes[1], label="kgCO2e par unite expediee")

dynamic_map = axes[2].imshow(dynamic_intensity_pivot.values, cmap="Oranges", aspect="auto")
axes[2].set_xticks(range(len(air_order)))
axes[2].set_xticklabels(air_order)
axes[2].set_yticks(range(len(sensitivity_order)))
axes[2].set_yticklabels(sensitivity_order)
axes[2].set_xlabel("Multiplicateur d'emission de l'aerien")
axes[2].set_ylabel("Severite de la disruption")
axes[2].set_title("Intensite du Time-Dependent DLCA par unite expediee")
for row_idx, row_values in enumerate(dynamic_intensity_pivot.values):
    for col_idx, value in enumerate(row_values):
        axes[2].text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=8)
fig.colorbar(dynamic_map, ax=axes[2], label="kgCO2e par unite expediee")

sdd_map = axes[3].imshow(sdd_intensity_pivot.values, cmap="PuRd", aspect="auto")
axes[3].set_xticks(range(len(air_order)))
axes[3].set_xticklabels(air_order)
axes[3].set_yticks(range(len(sensitivity_order)))
axes[3].set_yticklabels(sensitivity_order)
axes[3].set_xlabel("Multiplicateur d'emission de l'aerien")
axes[3].set_ylabel("Severite de la disruption")
axes[3].set_title("Intensite du SDD par unite expediee")
for row_idx, row_values in enumerate(sdd_intensity_pivot.values):
    for col_idx, value in enumerate(row_values):
        axes[3].text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=8)
fig.colorbar(sdd_map, ax=axes[3], label="kgCO2e par unite expediee")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_sensitivity_volume_intensity.png", dpi=160)
plt.close()

# -----------------------------
# Event timeline diagram
# -----------------------------
timeline_events = []
for _, r in states.iterrows():
    week = int(r["week"])
    if r["climate_event"] != "aucun":
        timeline_events.append((week, 1, r["climate_event"]))
    if r["operational_feedback_event"] != "aucun":
        timeline_events.append((week, 2, r["operational_feedback_event"]))
    if r["backup_inbound"] > 0:
        timeline_events.append((week, 3, "reception backup"))
    if r["backup_consumed_raw_units"] > 0:
        timeline_events.append((week, 4, "usage backup"))
    if r["outbound_mode"] == "air":
        timeline_events.append((week, 5, "transport aerien"))
    if r["scrap_units"] > 0:
        timeline_events.append((week, 6, "scrap"))

plt.figure(figsize=(14, 5.2))
for e in timeline_events:
    plt.scatter(e[0], e[1])
    plt.text(e[0], e[1] + 0.05, e[2], rotation=90, fontsize=8, ha="center")
plt.yticks(
    [1, 2, 3, 4, 5, 6],
    [
        "evenement climatique",
        "retroaction operationnelle",
        "reception backup",
        "usage backup",
        "transport aerien",
        "scrap",
    ],
)
plt.xlabel("Semaine")
plt.ylabel("Type d'evenement")
plt.title("Chronologie commune des evenements climatiques et operationnels")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_event_timeline.png", dpi=160)
plt.close()

# -----------------------------
# Supply chain schematic
# -----------------------------
nodes = {
    "Fournisseur principal": (0, 2),
    "Fournisseur backup": (0, 0),
    "Usine": (3, 1),
    "Entrepot": (6, 1),
    "Client": (9, 1)
}
edges = [
    ("Fournisseur principal", "Usine"),
    ("Fournisseur backup", "Usine"),
    ("Usine", "Entrepot"),
    ("Entrepot", "Client")
]

plt.figure(figsize=(10, 3))
for name, (x, y) in nodes.items():
    plt.scatter(x, y)
    plt.text(x, y + 0.1, name, ha="center")
for e in edges:
    x1, y1 = nodes[e[0]]
    x2, y2 = nodes[e[1]]
    plt.plot([x1, x2], [y1, y2])
plt.axis("off")
plt.title("Structure de supply chain utilisee dans le proof of concept state-dependent")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_supply_chain_schematic.png", dpi=160)
plt.close()

print("Outputs written to:")
print("  CSV:", CSV_DIR.resolve())
print("  Images:", IMG_DIR.resolve())
print("\nMethod comparison:")
print(comparison.round(2).to_string(index=False))
