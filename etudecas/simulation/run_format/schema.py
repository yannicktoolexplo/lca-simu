"""Schema declarations for the generic etudecas run package."""

from __future__ import annotations

from dataclasses import dataclass


RUN_PACKAGE_SCHEMA_VERSION = "etudecas.simulation_run.v1"


@dataclass(frozen=True)
class ArtifactSpec:
    """A known simulation artifact and how generic consumers should read it."""

    filename: str
    group: str
    domain: str
    grain: str
    required: bool = False


CANONICAL_DATA_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("first_simulation_daily.csv", "timeseries", "global_kpi", "day", True),
    ArtifactSpec("production_demand_service_daily.csv", "timeseries", "customer_service", "day_node_item"),
    ArtifactSpec("production_output_products_daily.csv", "timeseries", "production_output", "day_node_item"),
    ArtifactSpec("production_input_stocks_daily.csv", "timeseries", "factory_input_stock", "day_node_item"),
    ArtifactSpec(
        "component_immobilized_stock_daily.csv",
        "timeseries",
        "component_immobilized_stock",
        "day_node_product",
    ),
    ArtifactSpec(
        "component_immobilized_stock_components_daily.csv",
        "timeseries",
        "component_immobilized_stock_component",
        "day_node_product_item",
    ),
    ArtifactSpec(
        "component_immobilized_stock_summary.csv",
        "diagnostics",
        "component_immobilized_stock_summary",
        "node_product_item",
    ),
    ArtifactSpec(
        "finished_goods_stock_value_daily.csv",
        "timeseries",
        "finished_goods_stock_value",
        "day_node_product",
    ),
    ArtifactSpec(
        "finished_goods_stock_value_summary.csv",
        "diagnostics",
        "finished_goods_stock_value_summary",
        "product_location",
    ),
    ArtifactSpec("production_input_consumption_daily.csv", "timeseries", "factory_input_consumption", "day_node_item"),
    ArtifactSpec(
        "production_input_replenishment_arrivals_daily.csv",
        "timeseries",
        "factory_input_arrivals",
        "day_node_item",
    ),
    ArtifactSpec(
        "production_input_replenishment_shipments_daily.csv",
        "timeseries",
        "factory_input_shipments",
        "day_node_item",
    ),
    ArtifactSpec("production_dc_stocks_daily.csv", "timeseries", "distribution_stock", "day_node_item"),
    ArtifactSpec("production_supplier_stocks_daily.csv", "timeseries", "supplier_stock", "day_node_item"),
    ArtifactSpec("production_supplier_stock_flows_daily.csv", "timeseries", "supplier_stock_flow", "day_node_item"),
    ArtifactSpec("production_supplier_shipments_daily.csv", "timeseries", "supplier_shipments", "day_node_item"),
    ArtifactSpec("production_supplier_capacity_daily.csv", "timeseries", "supplier_capacity", "day_node_item"),
    ArtifactSpec("production_constraint_daily.csv", "timeseries", "production_constraint", "day_node_item"),
    ArtifactSpec("mrp_trace_daily.csv", "events", "mrp_trace", "day_node_item"),
    ArtifactSpec("mrp_orders_daily.csv", "events", "mrp_orders", "day_node_item"),
    ArtifactSpec(
        "opening_production_order_component_consumption.csv",
        "events",
        "opening_production_component_issue",
        "day_node_item",
    ),
    ArtifactSpec("production_plan_events.csv", "events", "production_plan", "event"),
    ArtifactSpec("production_campaigns.csv", "events", "production_campaigns", "campaign"),
    ArtifactSpec("production_factory_nervousness.csv", "diagnostics", "factory_nervousness", "node_item"),
    ArtifactSpec("production_lot_events.csv", "lots", "lot_events", "event", True),
    ArtifactSpec("production_lot_genealogy.csv", "lots", "lot_genealogy", "genealogy", True),
    ArtifactSpec("lot_path_audit_issues.csv", "diagnostics", "lot_path_audit", "issue"),
    ArtifactSpec("supplier_risk_events_applied_daily.csv", "events", "supplier_risk_applied", "day_node_item"),
    ArtifactSpec("supplier_state_dependent_risk_events.csv", "events", "supplier_risk_configured", "event"),
    ArtifactSpec("supplier_local_criticality_ranking.csv", "diagnostics", "supplier_local_criticality", "node_item"),
    ArtifactSpec("supplier_nominal_parameters.csv", "diagnostics", "supplier_nominal_parameters", "node_item"),
    ArtifactSpec(
        "production_capacity_nominal_parameters.csv",
        "diagnostics",
        "factory_nominal_capacities",
        "node_process",
    ),
    ArtifactSpec("initialization_state.csv", "diagnostics", "initialization_state", "run"),
    ArtifactSpec("initialization_observed_stock.csv", "diagnostics", "initialization_observed_stock", "node_item"),
    ArtifactSpec("initialization_pipeline.csv", "diagnostics", "initialization_pipeline", "lane_item"),
    ArtifactSpec("assumptions_ledger.csv", "diagnostics", "assumptions_ledger", "assumption"),
    ArtifactSpec("physics_of_decision_kpi_daily.csv", "timeseries", "decision_physics", "day"),
)


DAY_FIELD_CANDIDATES = ("day", "jour")


NODE_FIELD_CANDIDATES = (
    "node_id",
    "source_node_id",
    "src_node_id",
    "from_node_id",
    "supplier_id",
)


ITEM_FIELD_CANDIDATES = (
    "item_id",
    "output_item_id",
    "parent_item_id",
    "child_item_id",
)
