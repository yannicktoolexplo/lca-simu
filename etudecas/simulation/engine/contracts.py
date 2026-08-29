"""Shared simulation request contracts.

These helpers intentionally contain no execution logic. They translate business
parameter choices into the structured `SimulationRequest` payload accepted by
the engine API and by the optional HTTP server.
"""

from __future__ import annotations

from typing import Any


DEFAULT_INTERACTIVE_INPUT_PATH = "etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json"
DEFAULT_INTERACTIVE_SCENARIO_ID = "scn:BASE"
DEFAULT_INTERACTIVE_DAYS = 1825
DEFAULT_INTERACTIVE_OUTPUT_PROFILE = "diagnostic"


COMBINED_CAPACITY_DELAY_DEFAULTS = {
    "capacity": 0.75,
    "lead_time": 1.25,
}

COMBINED_STOCK_RELIABILITY_DEFAULTS = {
    "stock": 0.50,
    "reliability": 0.97,
}

COMBINED_UPSTREAM_DEFAULTS = {
    "external_procurement_daily_cap_days_scale": 0.75,
    "external_procurement_lead_days_scale": 1.25,
}


def empty_overrides() -> dict[str, Any]:
    return {
        "factors": {},
        "demand_item_scale": {},
        "capacity_node_scale": {},
        "supplier_node_scale": {},
        "supplier_capacity_node_scale": {},
        "edge_src_lead_time_scale": {},
        "edge_src_reliability_scale": {},
        "scenario_flags": {},
        "engine_args": [],
    }


def supplier_parameter_overrides(
    *,
    parameter_group: str,
    parameter_key: str = "",
    supplier_id: str = "",
    level: float = 1.0,
) -> dict[str, Any]:
    """Return API overrides for a supplier what-if parameter.

    The mapping mirrors the sensitivity campaign terminology. Unsupported
    groups return empty overrides rather than raising: the UI can still display
    the precomputed scenario while making clear that no live request is ready.
    """

    group = str(parameter_group or "")
    key = str(parameter_key or "")
    supplier = str(supplier_id or "")
    value = float(level)
    overrides = empty_overrides()

    if group == "supplier_stock_global" or key == "supplier_stock_scale":
        overrides["factors"]["supplier_stock_scale"] = value
    elif group == "supplier_capacity_global" or key == "supplier_capacity_scale":
        overrides["factors"]["supplier_capacity_scale"] = value
    elif group == "supplier_lead_time_global" or key == "supplier_lead_time_scale":
        overrides["factors"]["lead_time_scale"] = value
    elif group == "supplier_reliability_global" or key == "supplier_reliability_scale":
        overrides["factors"]["supplier_reliability_scale"] = value
    elif group == "supplier_stock_node" and supplier:
        overrides["supplier_node_scale"][supplier] = value
    elif group == "supplier_capacity_node" and supplier:
        overrides["supplier_capacity_node_scale"][supplier] = value
    elif group == "supplier_lead_time_node" and supplier:
        overrides["edge_src_lead_time_scale"][supplier] = value
    elif group == "supplier_reliability_node" and supplier:
        overrides["edge_src_reliability_scale"][supplier] = value
    elif group == "supplier_combined_capacity_delay_node" and supplier:
        overrides["supplier_capacity_node_scale"][supplier] = COMBINED_CAPACITY_DELAY_DEFAULTS["capacity"]
        overrides["edge_src_lead_time_scale"][supplier] = COMBINED_CAPACITY_DELAY_DEFAULTS["lead_time"]
    elif group == "supplier_combined_stock_reliability_node" and supplier:
        overrides["supplier_node_scale"][supplier] = COMBINED_STOCK_RELIABILITY_DEFAULTS["stock"]
        overrides["edge_src_reliability_scale"][supplier] = COMBINED_STOCK_RELIABILITY_DEFAULTS["reliability"]
    elif group == "supplier_upstream_supply":
        if key == "external_procurement_enabled":
            overrides["scenario_flags"]["external_procurement_enabled"] = value >= 0.5
        elif key == "external_procurement_daily_cap_days_scale":
            overrides["factors"]["external_procurement_daily_cap_days_scale"] = value
        elif key == "external_procurement_lead_days_scale":
            overrides["factors"]["external_procurement_lead_days_scale"] = value
    elif group == "supplier_combined_upstream_supply":
        overrides["factors"].update(COMBINED_UPSTREAM_DEFAULTS)

    return compact_overrides(overrides)


def compact_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in overrides.items()
        if value not in ({}, [], (), None)
    }


def simulation_request_payload(
    *,
    input_path: str = DEFAULT_INTERACTIVE_INPUT_PATH,
    scenario_id: str = DEFAULT_INTERACTIVE_SCENARIO_ID,
    days: int = DEFAULT_INTERACTIVE_DAYS,
    output_profile: str = DEFAULT_INTERACTIVE_OUTPUT_PROFILE,
    overrides: dict[str, Any] | None = None,
    run_id: str | None = None,
    control_schedule_csv: str | None = None,
    control_policy_json: str | None = None,
    seed: int | None = None,
    common_random_numbers: bool | None = None,
    demand_perturbation_csv: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "input_path": input_path,
        "scenario_id": scenario_id,
        "days": int(days),
        "output_profile": output_profile,
        "skip_map": True,
        "skip_plots": True,
        "overrides": compact_overrides(overrides or empty_overrides()),
    }
    if run_id:
        payload["run_id"] = run_id
    if control_schedule_csv:
        payload["control_schedule_csv"] = str(control_schedule_csv)
    if control_policy_json:
        payload["control_policy_json"] = str(control_policy_json)
    if seed is not None:
        payload["seed"] = int(seed)
    if common_random_numbers is not None:
        payload["common_random_numbers"] = bool(common_random_numbers)
    if demand_perturbation_csv:
        payload["demand_perturbation_csv"] = str(demand_perturbation_csv)
    return payload


def supplier_parameter_request_payload(
    *,
    parameter_group: str,
    parameter_key: str = "",
    supplier_id: str = "",
    level: float = 1.0,
    input_path: str = DEFAULT_INTERACTIVE_INPUT_PATH,
    scenario_id: str = DEFAULT_INTERACTIVE_SCENARIO_ID,
    days: int = DEFAULT_INTERACTIVE_DAYS,
    output_profile: str = DEFAULT_INTERACTIVE_OUTPUT_PROFILE,
    run_id: str | None = None,
    control_schedule_csv: str | None = None,
    control_policy_json: str | None = None,
    seed: int | None = None,
    common_random_numbers: bool | None = None,
    demand_perturbation_csv: str | None = None,
) -> dict[str, Any]:
    return simulation_request_payload(
        input_path=input_path,
        scenario_id=scenario_id,
        days=days,
        output_profile=output_profile,
        overrides=supplier_parameter_overrides(
            parameter_group=parameter_group,
            parameter_key=parameter_key,
            supplier_id=supplier_id,
            level=level,
        ),
        run_id=run_id,
        control_schedule_csv=control_schedule_csv,
        control_policy_json=control_policy_json,
        seed=seed,
        common_random_numbers=common_random_numbers,
        demand_perturbation_csv=demand_perturbation_csv,
    )


__all__ = [
    "DEFAULT_INTERACTIVE_DAYS",
    "DEFAULT_INTERACTIVE_INPUT_PATH",
    "DEFAULT_INTERACTIVE_OUTPUT_PROFILE",
    "DEFAULT_INTERACTIVE_SCENARIO_ID",
    "empty_overrides",
    "simulation_request_payload",
    "supplier_parameter_overrides",
    "supplier_parameter_request_payload",
]
