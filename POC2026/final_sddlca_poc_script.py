import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ============================================================
# FINAL POC SCRIPT
# Classical LCA vs Dynamic LCA vs State-Dependent Dynamic LCA
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
weeks = list(range(1, 21))

# Demand signal
demand = [10, 11, 12, 10, 11, 12, 13, 14, 15, 13, 12, 11, 10, 11, 12, 13, 12, 11, 10, 9]

# Time-varying electricity carbon intensity (kgCO2e/kWh)
grid_factor = [0.42, 0.38, 0.35, 0.40, 0.45, 0.48, 0.52, 0.56, 0.60, 0.58,
               0.50, 0.44, 0.36, 0.30, 0.28, 0.32, 0.34, 0.36, 0.40, 0.38]

# Capacity disruption
base_capacity = 12
capacity = [base_capacity] * 20
for i in [7, 8, 9]:   # weeks 8-10
    capacity[i] = 7
for i in [10, 11]:    # weeks 11-12
    capacity[i] = 10

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

# Inventory policy
raw_target = 24
raw_reorder_threshold = 14
main_lead = 2
backup_lead = 1


@dataclass(frozen=True)
class DecisionPolicy:
    name: str
    label: str
    raw_target: float = 24.0
    raw_reorder_threshold: float = 14.0
    backup_order_qty: float = 12.0
    air_backlog_start_threshold: float = 4.0
    air_backlog_end_threshold: float = 6.0
    carbon_aware_grid_threshold: float | None = None
    carbon_aware_backlog_guard: float = 0.0
    carbon_aware_capacity_cap: float = 1.0


BASELINE_POLICY = DecisionPolicy(
    name="baseline",
    label="Baseline",
)

COUNTERFACTUAL_POLICIES = [
    BASELINE_POLICY,
    DecisionPolicy(
        name="backup_early",
        label="Backup early",
        raw_reorder_threshold=18.0,
        backup_order_qty=14.0,
    ),
    DecisionPolicy(
        name="inventory_buffer",
        label="Inventory buffer",
        raw_target=32.0,
        raw_reorder_threshold=18.0,
    ),
    DecisionPolicy(
        name="low_carbon",
        label="Low-carbon discipline",
        air_backlog_start_threshold=12.0,
        air_backlog_end_threshold=18.0,
        carbon_aware_grid_threshold=0.50,
        carbon_aware_backlog_guard=4.0,
        carbon_aware_capacity_cap=0.6,
    ),
    DecisionPolicy(
        name="service_first",
        label="Service first",
        raw_target=32.0,
        raw_reorder_threshold=18.0,
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
    main_order = max(0.0, policy.raw_target - main_supply_position)

    total_supply_position = raw_stock_start + sum(next_state.main_pipeline) + sum(next_state.backup_pipeline)
    backup_order = 0.0
    if total_supply_position < policy.raw_reorder_threshold:
        backup_order = policy.backup_order_qty

    next_state.main_pipeline[-1] += main_order
    next_state.backup_pipeline[-1] += backup_order

    backlog_start = next_state.backlog
    service_pressure = demand_t + backlog_start
    planned_input = min(capacity_t, raw_stock_start, service_pressure)
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
        "main_order": main_order,
        "backup_order": backup_order,
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


def simulate_policy(policy: DecisionPolicy) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    state_trajectory_rows = []
    current_state = initial_state()

    for t in range(len(weeks)):
        week = t + 1
        start_state = current_state.copy()
        next_state, transition_row = state_transition(
            state=current_state,
            policy=policy,
            week=week,
            demand_t=demand[t],
            capacity_t=capacity[t],
            grid_factor_t=grid_factor[t],
        )

        rows.append(transition_row)
        state_trajectory_rows.append({
            "policy_name": policy.name,
            "policy_label": policy.label,
            "week": week,
            "demand": demand[t],
            "capacity": capacity[t],
            "grid_factor": grid_factor[t],
            **state_snapshot(start_state, "state_start"),
            **state_snapshot(next_state, "state_end"),
        })
        current_state = next_state

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


def compute_method_outputs(states: pd.DataFrame) -> dict:
    states = states.copy()

    avg_grid = states["grid_factor"].mean()
    total_good_output = states["good_output_units"].sum()
    total_shipments = states["outbound_shipments"].sum()
    avg_raw_stock = states["raw_stock_end"].mean()
    avg_fg_stock = states["fg_stock_end"].mean()

    classical = {
        "material": total_good_output * MAIN_MATERIAL_EF,
        "inbound_transport": total_good_output * INBOUND_MAIN_TRANSPORT_EF,
        "production_energy": total_good_output * NOMINAL_KWH_PER_UNIT * avg_grid,
        "outbound_transport": total_shipments * TRUCK_OUTBOUND_EF,
        "storage": (avg_raw_stock * RAW_STORAGE_EF + avg_fg_stock * FG_STORAGE_EF) * len(states),
        "scrap": 0.0,
    }
    classical["total"] = sum(classical.values())

    states["classical_weekly_total"] = (
        states["good_output_units"] * MAIN_MATERIAL_EF
        + states["good_output_units"] * INBOUND_MAIN_TRANSPORT_EF
        + states["good_output_units"] * NOMINAL_KWH_PER_UNIT * avg_grid
        + states["outbound_shipments"] * TRUCK_OUTBOUND_EF
        + states["raw_stock_end"] * RAW_STORAGE_EF
        + states["fg_stock_end"] * FG_STORAGE_EF
    )

    dynamic_rows = []
    for _, r in states.iterrows():
        dynamic_rows.append({
            "policy_name": r["policy_name"],
            "policy_label": r["policy_label"],
            "week": int(r["week"]),
            "material": r["good_output_units"] * MAIN_MATERIAL_EF,
            "inbound_transport": r["good_output_units"] * INBOUND_MAIN_TRANSPORT_EF,
            "production_energy": r["good_output_units"] * NOMINAL_KWH_PER_UNIT * r["grid_factor"],
            "outbound_transport": r["outbound_shipments"] * TRUCK_OUTBOUND_EF,
            "storage": r["raw_stock_end"] * RAW_STORAGE_EF + r["fg_stock_end"] * FG_STORAGE_EF,
            "scrap": 0.0,
        })
    dynamic = pd.DataFrame(dynamic_rows)
    dynamic["total"] = dynamic[["material", "inbound_transport", "production_energy",
                                "outbound_transport", "storage", "scrap"]].sum(axis=1)
    dynamic_breakdown = dynamic[["material", "inbound_transport", "production_energy",
                                 "outbound_transport", "storage", "scrap", "total"]].sum().to_dict()

    sddlca_rows = []
    for _, r in states.iterrows():
        material_main = r["good_output_main_units"] * MAIN_MATERIAL_EF
        material_backup = r["good_output_backup_units"] * BACKUP_MATERIAL_EF

        inbound_main = r["good_output_main_units"] * INBOUND_MAIN_TRANSPORT_EF
        inbound_backup = r["good_output_backup_units"] * INBOUND_BACKUP_TRANSPORT_EF

        kwh_per_good = prod_kwh_per_good_unit(r["capacity_utilization"])
        prod_energy = r["good_output_units"] * kwh_per_good * r["grid_factor"]

        scrap_burden = (
            r["scrap_main_units"] * (MAIN_MATERIAL_EF + INBOUND_MAIN_TRANSPORT_EF + kwh_per_good * r["grid_factor"])
            + r["scrap_backup_units"] * (BACKUP_MATERIAL_EF + INBOUND_BACKUP_TRANSPORT_EF + kwh_per_good * r["grid_factor"])
        )

        outbound_factor = AIR_OUTBOUND_EF if r["outbound_mode"] == "air" else TRUCK_OUTBOUND_EF
        outbound = r["outbound_shipments"] * outbound_factor

        storage = r["raw_stock_end"] * RAW_STORAGE_EF + r["fg_stock_end"] * FG_STORAGE_EF

        sddlca_rows.append({
            "policy_name": r["policy_name"],
            "policy_label": r["policy_label"],
            "week": int(r["week"]),
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

    sddlca = pd.DataFrame(sddlca_rows)
    sddlca["total"] = sddlca[["material", "inbound_transport", "production_energy",
                              "outbound_transport", "storage", "scrap"]].sum(axis=1)
    sddlca_breakdown = sddlca[["material", "inbound_transport", "production_energy",
                               "outbound_transport", "storage", "scrap", "total"]].sum().to_dict()

    comparison = pd.DataFrame([
        {"method": "Classical LCA", "total_kgCO2e": classical["total"]},
        {"method": "Dynamic LCA", "total_kgCO2e": dynamic_breakdown["total"]},
        {"method": "State-Dependent Dynamic LCA", "total_kgCO2e": sddlca_breakdown["total"]},
    ])
    comparison["delta_vs_classical"] = comparison["total_kgCO2e"] - classical["total"]
    comparison["delta_vs_classical_pct"] = 100 * comparison["delta_vs_classical"] / classical["total"]

    breakdown = pd.DataFrame([
        {"method": "Classical LCA", **classical},
        {"method": "Dynamic LCA", **dynamic_breakdown},
        {"method": "State-Dependent Dynamic LCA", **sddlca_breakdown},
    ])

    return {
        "states": states,
        "classical": classical,
        "dynamic": dynamic,
        "dynamic_breakdown": dynamic_breakdown,
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


def evaluate_policy(policy: DecisionPolicy) -> dict:
    states, state_trajectory = simulate_policy(policy)
    method_outputs = compute_method_outputs(states)
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
        "dynamic_total_kgCO2e": round(method_outputs["dynamic_breakdown"]["total"], 2),
        "sddlca_total_kgCO2e": round(method_outputs["sddlca_breakdown"]["total"], 2),
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


# -----------------------------
# Natural supply chain dynamics
# -----------------------------
baseline_result = evaluate_policy(BASELINE_POLICY)

states = baseline_result["states"]
state_trajectory = baseline_result["state_trajectory"]
classical = baseline_result["classical"]
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
cost_breakdown = baseline_result["cost_breakdown"]

state_definition = pd.DataFrame([
    {
        "component": "backlog",
        "location": "state_start_backlog / state_end_backlog",
        "description": "Unserved demand carried from one week to the next.",
    },
    {
        "component": "main_pipeline_eta_i",
        "location": "state_*_main_pipeline_eta_0..n",
        "description": "Main-supplier replenishment pipeline by time-to-arrival bucket.",
    },
    {
        "component": "backup_pipeline_eta_i",
        "location": "state_*_backup_pipeline_eta_0..n",
        "description": "Backup-supplier replenishment pipeline by time-to-arrival bucket.",
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

counterfactual_results = [evaluate_policy(policy) for policy in COUNTERFACTUAL_POLICIES]
policy_definition = pd.DataFrame([
    {
        "policy_name": policy.name,
        "policy_label": policy.label,
        "raw_target": policy.raw_target,
        "raw_reorder_threshold": policy.raw_reorder_threshold,
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
    "hidden_carbon_vs_dynamic",
    "hidden_carbon_vs_classical",
]].copy()

# -----------------------------
# Export CSV files
# -----------------------------
states.to_csv(CSV_DIR / "poc_supply_chain_states.csv", index=False)
state_trajectory.to_csv(CSV_DIR / "poc_state_space_trajectory.csv", index=False)
dynamic.to_csv(CSV_DIR / "poc_dynamic_lca.csv", index=False)
sddlca.to_csv(CSV_DIR / "poc_state_dependent_dynamic_lca.csv", index=False)
comparison.to_csv(CSV_DIR / "poc_lca_method_comparison.csv", index=False)
breakdown.to_csv(CSV_DIR / "poc_lca_breakdown.csv", index=False)
events.to_csv(CSV_DIR / "poc_regime_events.csv", index=False)
traceability.to_csv(CSV_DIR / "poc_source_traceability.csv", index=False)
state_definition.to_csv(CSV_DIR / "poc_state_space_definition.csv", index=False)
metrics.to_csv(CSV_DIR / "poc_key_metrics.csv", index=False)
weekly_costs.to_csv(CSV_DIR / "poc_weekly_costs.csv", index=False)
policy_definition.to_csv(CSV_DIR / "poc_policy_definition.csv", index=False)
policy_decision_summary.to_csv(CSV_DIR / "poc_policy_decision_summary.csv", index=False)
policy_method_comparison.to_csv(CSV_DIR / "poc_policy_method_comparison.csv", index=False)
policy_cost_breakdown.to_csv(CSV_DIR / "poc_policy_cost_breakdown.csv", index=False)
policy_weekly_costs.to_csv(CSV_DIR / "poc_policy_weekly_costs.csv", index=False)
policy_hidden_carbon.to_csv(CSV_DIR / "poc_policy_hidden_carbon.csv", index=False)

# -----------------------------
# Charts
# -----------------------------
plt.figure(figsize=(10, 4.8))
plt.plot(states["week"], states["classical_weekly_total"], marker="o", label="Classical LCA")
plt.plot(dynamic["week"], dynamic["total"], marker="o", label="Dynamic LCA")
plt.plot(sddlca["week"], sddlca["total"], marker="o", label="State-Dependent Dynamic LCA")
plt.xlabel("Week")
plt.ylabel("Weekly impact (kgCO2e)")
plt.title("Weekly environmental impact by method")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_weekly_impact_comparison.png", dpi=160)
plt.close()

plt.figure(figsize=(10, 4.8))
plt.plot(states["week"], states["backlog_end"], marker="o", label="Backlog")
plt.xlabel("Week")
plt.ylabel("Backlog (units)")
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
axes[1].plot(state_trajectory["week"], state_trajectory["state_end_total_pipeline"], marker="o", label="Pipeline total")
axes[1].set_xlabel("Semaine")
axes[1].set_ylabel("Valeur de composante d'etat")
axes[1].set_title("Composantes de l'etat dans le temps")
axes[1].legend()
axes[1].grid(alpha=0.2)

plt.tight_layout()
plt.savefig(IMG_DIR / "poc_state_space_projection.png", dpi=160)
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
plt.bar(comparison["method"], comparison["total_kgCO2e"])
plt.ylabel("Total impact (kgCO2e)")
plt.title("Total impact comparison")
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
    plt.bar(x_positions, policy_method_pivot[method], width=bar_width, label=method)
plt.xticks(policy_x, policy_method_pivot.index, rotation=15, ha="right")
plt.ylabel("Total impact (kgCO2e)")
plt.title("Counterfactual policies: carbon result by method")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_method_comparison.png", dpi=160)
plt.close()

plt.figure(figsize=(10.5, 5.2))
bubble_sizes = 40 + 0.015 * policy_decision_summary["total_cost"]
plt.scatter(
    policy_decision_summary["same_week_service_pct"],
    policy_decision_summary["sddlca_total_kgCO2e"],
    s=bubble_sizes,
    c=range(len(policy_decision_summary)),
    cmap="tab10",
    alpha=0.85,
)
for _, r in policy_decision_summary.iterrows():
    plt.text(
        r["same_week_service_pct"] + 0.15,
        r["sddlca_total_kgCO2e"] + 10,
        r["policy_label"],
        fontsize=8,
    )
plt.xlabel("Same-week service level (%)")
plt.ylabel("State-Dependent total impact (kgCO2e)")
plt.title("Decision frontier: service vs state-dependent carbon")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_decision_frontier.png", dpi=160)
plt.close()

policy_hidden_pivot = (
    policy_hidden_carbon
    .set_index("policy_label")[["hidden_carbon_vs_dynamic", "hidden_carbon_vs_classical"]]
    .reindex(policy_order)
)
policy_x = list(range(len(policy_hidden_pivot.index)))
plt.figure(figsize=(12, 5.2))
plt.bar(
    [x - 0.18 for x in policy_x],
    policy_hidden_pivot["hidden_carbon_vs_dynamic"],
    width=0.36,
    label="SDD-LCA minus Dynamic",
)
plt.bar(
    [x + 0.18 for x in policy_x],
    policy_hidden_pivot["hidden_carbon_vs_classical"],
    width=0.36,
    label="SDD-LCA minus Classical",
)
plt.axhline(0, color="black", linewidth=0.8)
plt.xticks(policy_x, policy_hidden_pivot.index, rotation=15, ha="right")
plt.ylabel("Hidden carbon premium (kgCO2e)")
plt.title("Carbon overlooked by simpler methods")
plt.legend()
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_policy_hidden_carbon.png", dpi=160)
plt.close()

# -----------------------------
# Event timeline diagram
# -----------------------------
timeline_events = []
for _, r in states.iterrows():
    week = int(r["week"])
    if r["backup_inbound"] > 0:
        timeline_events.append((week, 1, "backup receipt"))
    if r["backup_consumed_raw_units"] > 0:
        timeline_events.append((week, 2, "backup use"))
    if r["outbound_mode"] == "air":
        timeline_events.append((week, 3, "air transport"))
    if r["scrap_units"] > 0:
        timeline_events.append((week, 4, "scrap"))

plt.figure(figsize=(10, 4))
for e in timeline_events:
    plt.scatter(e[0], e[1])
    plt.text(e[0], e[1] + 0.05, e[2], rotation=90, fontsize=8, ha="center")
plt.yticks([1, 2, 3, 4], ["backup receipt", "backup use", "air transport", "scrap"])
plt.xlabel("Week")
plt.ylabel("Operational event")
plt.title("Timeline of operational events triggering environmental impact")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_event_timeline.png", dpi=160)
plt.close()

# -----------------------------
# Supply chain schematic
# -----------------------------
nodes = {
    "Main Supplier": (0, 2),
    "Backup Supplier": (0, 0),
    "Factory": (3, 1),
    "Warehouse": (6, 1),
    "Customer": (9, 1)
}
edges = [
    ("Main Supplier", "Factory"),
    ("Backup Supplier", "Factory"),
    ("Factory", "Warehouse"),
    ("Warehouse", "Customer")
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
plt.title("Supply chain structure used in the State-Dependent LCA proof-of-concept")
plt.tight_layout()
plt.savefig(IMG_DIR / "poc_supply_chain_schematic.png", dpi=160)
plt.close()

print("Outputs written to:")
print("  CSV:", CSV_DIR.resolve())
print("  Images:", IMG_DIR.resolve())
print("\nMethod comparison:")
print(comparison.round(2).to_string(index=False))
