"""Map adapter for the generic etudecas simulation run package.

This module is the migration boundary between the historical map builder and
the generic `run/` contract.  It resolves artifacts by logical domain so callers
can pass `--run-package` instead of many CSV paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etudecas.simulation.run_format import RunPackage, load_run_package


@dataclass(frozen=True)
class MapRunInputs:
    package: RunPackage
    input_graph: Path | None
    output_root: Path
    sim_input_stocks_csv: Path
    sim_output_products_csv: Path
    demand_service_csv: Path
    supplier_shipments_csv: Path
    supplier_stocks_csv: Path
    supplier_stock_flows_csv: Path | None
    supplier_capacity_csv: Path
    supplier_nominal_parameters_csv: Path | None
    factory_nominal_capacities_csv: Path | None
    input_arrivals_csv: Path
    dc_stocks_csv: Path
    production_constraint_csv: Path
    lot_events_csv: Path
    lot_genealogy_csv: Path
    production_plan_events_csv: Path
    production_campaigns_csv: Path
    safety_reference_csv: Path | None
    daily_kpi_csv: Path
    supplier_local_criticality_csv: Path
    supplier_local_criticality_json: Path
    plots_dir: Path


def _optional(package: RunPackage, *, domain: str) -> Path | None:
    return package.artifact_path(domain=domain)


def _required(package: RunPackage, *, domain: str) -> Path:
    return package.require_artifact_path(domain=domain)


def map_inputs_from_run_package(package_dir: Path | str) -> MapRunInputs:
    package = load_run_package(package_dir)
    output_root = package.output_dir
    manifest = package.manifest
    source_graph = manifest.get("source_graph")
    input_graph = Path(str(source_graph)) if source_graph else None
    plots_dir = output_root / "plots"

    return MapRunInputs(
        package=package,
        input_graph=input_graph,
        output_root=output_root,
        sim_input_stocks_csv=_required(package, domain="factory_input_stock"),
        sim_output_products_csv=_required(package, domain="production_output"),
        demand_service_csv=_required(package, domain="customer_service"),
        supplier_shipments_csv=_required(package, domain="supplier_shipments"),
        supplier_stocks_csv=_required(package, domain="supplier_stock"),
        supplier_stock_flows_csv=_optional(package, domain="supplier_stock_flow"),
        supplier_capacity_csv=_required(package, domain="supplier_capacity"),
        supplier_nominal_parameters_csv=_optional(package, domain="supplier_nominal_parameters"),
        factory_nominal_capacities_csv=_optional(package, domain="factory_nominal_capacities"),
        input_arrivals_csv=_required(package, domain="factory_input_arrivals"),
        dc_stocks_csv=_optional(package, domain="distribution_stock") or (output_root / "data" / "production_dc_stocks_daily.csv"),
        production_constraint_csv=_required(package, domain="production_constraint"),
        lot_events_csv=_required(package, domain="lot_events"),
        lot_genealogy_csv=_required(package, domain="lot_genealogy"),
        production_plan_events_csv=_optional(package, domain="production_plan")
        or (output_root / "data" / "production_plan_events.csv"),
        production_campaigns_csv=_optional(package, domain="production_campaigns")
        or (output_root / "data" / "production_campaigns.csv"),
        safety_reference_csv=output_root / "reports" / "mrp_safety_stock_reference.csv",
        daily_kpi_csv=_required(package, domain="global_kpi"),
        supplier_local_criticality_csv=_optional(package, domain="supplier_local_criticality")
        or (output_root / "data" / "supplier_local_criticality_ranking.csv"),
        supplier_local_criticality_json=output_root / "summaries" / "supplier_local_criticality_summary.json",
        plots_dir=plots_dir,
    )


def run_contract_payload(inputs: MapRunInputs) -> dict[str, Any]:
    package = inputs.package
    return {
        "schema_version": package.manifest.get("schema_version"),
        "scenario_id": package.manifest.get("scenario_id"),
        "sim_days": package.manifest.get("sim_days"),
        "timeline_days": package.manifest.get("timeline_days"),
        "output_profile": package.manifest.get("output_profile"),
        "output_dir": str(inputs.output_root),
        "source_graph": str(inputs.input_graph) if inputs.input_graph else None,
        "artifact_counts": package.manifest.get("counts", {}),
        "artifacts": [
            {
                "name": row.get("name"),
                "domain": row.get("domain"),
                "group": row.get("group"),
                "grain": row.get("grain"),
                "path": row.get("path"),
                "row_count": row.get("row_count"),
            }
            for row in package.artifacts
            if isinstance(row, dict) and row.get("exists")
        ],
    }
