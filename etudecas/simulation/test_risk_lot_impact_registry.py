from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from etudecas.simulation.engine.run_first_simulation import (
    LotLedger,
    _attach_shipment_trace_ids,
)
from etudecas.simulation.lot_trace.risk_impact_registry import (
    PROVENANCE_VERSION,
    REGISTRY_VERSION,
    RiskImpactProvenanceError,
    RiskImpactUnitError,
    build_risk_impact_registry,
    build_risk_impact_registry_from_directory,
    write_risk_impact_registry,
)


def _event(
    event_id: str,
    day: int,
    event_type: str,
    lot_id: str,
    node: str,
    item: str,
    qty: float,
    *,
    source_id: str = "",
    campaign: str = "",
    shipment_id: str = "",
    risk_event_ids: str = "",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "day": day,
        "event_type": event_type,
        "lot_id": lot_id,
        "node_id": node,
        "item_id": item,
        "qty": qty,
        "qty_after": qty,
        "uom": "UN",
        "source_type": event_type,
        "source_id": source_id,
        "shipment_id": shipment_id,
        "risk_decision_day": 1 if shipment_id == "SHIP-1" else "",
        "risk_event_ids": risk_event_ids,
        "production_campaign_id": campaign,
        "notes": "",
    }


def _link(
    day: int,
    link_type: str,
    parent: str,
    parent_node: str,
    parent_item: str,
    child: str,
    child_node: str,
    child_item: str,
    parent_qty: float,
    child_qty: float,
    *,
    source_id: str,
    campaign: str = "",
    shipment_id: str = "",
) -> dict[str, object]:
    return {
        "day": day,
        "link_type": link_type,
        "parent_lot_id": parent,
        "parent_node_id": parent_node,
        "parent_item_id": parent_item,
        "child_lot_id": child,
        "child_node_id": child_node,
        "child_item_id": child_item,
        "parent_qty": parent_qty,
        "child_qty": child_qty,
        "allocation_share": parent_qty / child_qty,
        "source_id": source_id,
        "shipment_id": shipment_id,
        "risk_decision_day": 1 if shipment_id == "SHIP-1" else "",
        "risk_event_ids": "E1" if shipment_id == "SHIP-1" else "",
        "production_campaign_id": campaign,
        "notes": "",
    }


def _base_rows(
    *, native: bool = True, two_events: bool = False
) -> dict[str, list[dict[str, object]]]:
    event_ids = "E1,E2" if two_events else "E1"
    risk_events = [
        {
            "event_id": "E1",
            "trigger_day": 0,
            "start_day": 1,
            "end_day": 5,
            "supplier_id": "SUP-1",
            "dst_node_id": "M-1",
            "item_id": "item:C",
            "edge_id": "edge:SUP-1_TO_M-1_C",
            "risk_family": "quality",
            "risk_type": "quality_yield",
            "trigger_metric": "quarantine",
            "effect": "quality yield reduced",
        }
    ]
    if two_events:
        risk_events.append(
            {
                **risk_events[0],
                "event_id": "E2",
                "risk_family": "lead",
                "risk_type": "lead_time",
            }
        )
    applied = [
        {
            "day": 1,
            "supplier_id": "SUP-1",
            "dst_node_id": "M-1",
            "item_id": "item:C",
            "edge_id": "edge:SUP-1_TO_M-1_C",
            "event_ids": event_ids,
            "quality_yield_multiplier": 0.8,
            "purchase_cost_multiplier": 1.1,
            "transport_cost_multiplier": 1.0,
        }
    ]
    shipment = {
        "day": 1,
        "src_node_id": "SUP-1",
        "dst_node_id": "M-1",
        "item_id": "item:C",
        "edge_id": "edge:SUP-1_TO_M-1_C",
        "shipped_qty": 100,
        "pulled_qty": 100,
        "lead_days": 2,
        "arrival_day": 3,
        "reliability": 1,
        "uom": "UN",
        "transport_cost": 10,
    }
    if native:
        shipment.update(
            {
                "shipment_id": "SHIP-1",
                "risk_decision_day": 1,
                "risk_event_ids": event_ids,
                "purchase_cost": 220,
            }
        )
    lot_events = [
        _event("L1-CREATE", -2, "opening_stock", "SRC", "SUP-1", "item:C", 100),
        _event(
            "L1-SHIP",
            1,
            "lane_ship",
            "SRC",
            "SUP-1",
            "item:C",
            100,
            source_id="edge:SUP-1_TO_M-1_C",
            shipment_id="SHIP-1" if native else "",
            risk_event_ids=event_ids if native else "",
        ),
        _event(
            "L2-RECEIPT",
            3,
            "lane_receipt",
            "MAT",
            "M-1",
            "item:C",
            100,
            source_id="edge:SUP-1_TO_M-1_C",
        ),
        _event(
            "L2-CONSUME",
            4,
            "production_consume",
            "MAT",
            "M-1",
            "item:C",
            100,
            campaign="CMP-1",
        ),
        _event(
            "L3-OUTPUT",
            4,
            "production_output",
            "FG",
            "M-1",
            "item:FG",
            50,
            campaign="CMP-1",
        ),
        _event(
            "L3-SHIP",
            5,
            "lane_ship",
            "FG",
            "M-1",
            "item:FG",
            50,
            source_id="edge:M-1_TO_DC-1_FG",
        ),
        _event(
            "L4-RECEIPT",
            6,
            "lane_receipt",
            "DCLOT",
            "DC-1",
            "item:FG",
            50,
            source_id="edge:M-1_TO_DC-1_FG",
        ),
        _event(
            "L4-SHIP",
            7,
            "lane_ship",
            "DCLOT",
            "DC-1",
            "item:FG",
            50,
            source_id="edge:DC-1_TO_C-1_FG",
        ),
        _event(
            "L5-RECEIPT",
            8,
            "lane_receipt",
            "CLOT",
            "C-1",
            "item:FG",
            50,
            source_id="edge:DC-1_TO_C-1_FG",
        ),
        _event(
            "L5-SERVICE",
            9,
            "demand_service",
            "CLOT",
            "C-1",
            "item:FG",
            20,
            source_id="customer_demand",
        ),
    ]
    genealogy = [
        _link(
            3,
            "transport",
            "SRC",
            "SUP-1",
            "item:C",
            "MAT",
            "M-1",
            "item:C",
            100,
            100,
            source_id="edge:SUP-1_TO_M-1_C",
            shipment_id="SHIP-1" if native else "",
        ),
        _link(
            4,
            "production",
            "MAT",
            "M-1",
            "item:C",
            "FG",
            "M-1",
            "item:FG",
            100,
            50,
            source_id="M-1|item:FG",
            campaign="CMP-1",
        ),
        _link(
            6,
            "transport",
            "FG",
            "M-1",
            "item:FG",
            "DCLOT",
            "DC-1",
            "item:FG",
            50,
            50,
            source_id="edge:M-1_TO_DC-1_FG",
        ),
        _link(
            8,
            "transport",
            "DCLOT",
            "DC-1",
            "item:FG",
            "CLOT",
            "C-1",
            "item:FG",
            50,
            50,
            source_id="edge:DC-1_TO_C-1_FG",
        ),
    ]
    return {
        "risk_event_rows": risk_events,
        "applied_risk_rows": applied,
        "shipment_rows": [shipment],
        "lot_event_rows": lot_events,
        "genealogy_rows": genealogy,
        "campaign_rows": [
            {
                "campaign_id": "CMP-1",
                "node_id": "M-1",
                "output_item_id": "item:FG",
                "first_event_day": 4,
                "actual_qty": 50,
                "status": "completed_without_delay",
            }
        ],
        "demand_service_rows": [
            {
                "day": 9,
                "node_id": "C-1",
                "item_id": "item:FG",
                "demand_qty": 20,
                "served_qty": 20,
                "backlog_end_qty": 0,
            }
        ],
        "supplier_parameter_rows": [
            {
                "supplier_id": "SUP-1",
                "dst_node_id": "M-1",
                "item_id": "item:C",
                "unit_purchase_cost": 2,
            }
        ],
    }


def _write_csv_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_registry_source_data(data: Path) -> None:
    rows = _base_rows(native=True)
    mapping = {
        "assumptions_ledger.csv": [],
        "supplier_state_dependent_risk_events.csv": rows["risk_event_rows"],
        "supplier_risk_events_applied_daily.csv": rows["applied_risk_rows"],
        "production_supplier_shipments_daily.csv": rows["shipment_rows"],
        "production_lot_events.csv": rows["lot_event_rows"],
        "production_lot_genealogy.csv": rows["genealogy_rows"],
        "production_campaigns.csv": rows["campaign_rows"],
        "production_demand_service_daily.csv": rows["demand_service_rows"],
        "supplier_nominal_parameters.csv": rows["supplier_parameter_rows"],
    }
    for filename, table_rows in mapping.items():
        _write_csv_rows(data / filename, table_rows)


def _write_campaign_fixture(tmp_path: Path) -> dict[str, Path]:
    campaign = tmp_path / "campaign"
    run_root = campaign / "runs" / "C1" / "incident_no_action" / "seed_7"
    data = run_root / "data"
    _write_registry_source_data(data)

    risk_path = campaign / "prepared_inputs" / "C1" / "supplier_risk_events.csv"
    _write_csv_rows(risk_path, _base_rows(native=True)["risk_event_rows"])
    risk_hash = _sha256(risk_path)
    j0_hash = "a" * 64
    component_hashes = {"stock": "b" * 64}
    summary = {
        "scenario_id": "scn:BASE",
        "sim_days": 30,
        "timeline_days": 30,
        "policy": {
            "seed": 7,
            "output_profile": "full",
            "lot_trace_enabled": True,
            "supplier_risk": {
                "enabled": True,
                "events_csv": str(risk_path.resolve()),
                "events_csv_sha256": risk_hash,
                "event_count": 1,
            },
            "warmup_boundary_audit": {
                "core_state_sha256": j0_hash,
                "component_sha256": component_hashes,
            },
        },
    }
    summary_path = run_root / "summaries" / "first_simulation_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    run_manifest_path = run_root / "run" / "run_manifest.json"
    run_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    run_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "etudecas.simulation_run.v1",
                "output_dir": str(run_root.resolve()),
                "scenario_id": "scn:BASE",
                "sim_days": 30,
                "timeline_days": 30,
                "output_profile": "full",
                "capabilities": {"lot_trace_enabled": True},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config_path = campaign / "canonical_cascade_config_snapshot.json"
    config_path.write_text(
        json.dumps(
            {
                "campaign": {"scenario_id": "scn:BASE", "days": 30},
                "cascades": [
                    {
                        "id": "C1",
                        "incident": {"risk_events": _base_rows()["risk_event_rows"]},
                        "solutions": [],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    runs_path = campaign / "canonical_cascade_runs.csv"
    _write_csv_rows(
        runs_path,
        [
            {
                "cascade_id": "C1",
                "variant_id": "incident_no_action",
                "case_type": "incident_no_action",
                "solution_id": "",
                "seed": 7,
                "status": "ok",
                "result_dir": str(run_root.resolve()),
                "days": 30,
                "scenario_id": "scn:BASE",
                "risk_events_sha256": risk_hash,
                "control_schedule_sha256": "",
                "measurement_start_state_sha256": j0_hash,
                "measurement_start_component_sha256_json": json.dumps(
                    component_hashes, sort_keys=True
                ),
            }
        ],
    )
    commands_path = campaign / "canonical_cascade_commands.json"
    commands_path.write_text(
        json.dumps(
            [
                {
                    "cascade_id": "C1",
                    "variant_id": "incident_no_action",
                    "case_type": "incident_no_action",
                    "solution_id": "",
                    "seed": 7,
                    "result_dir": str(run_root.resolve()),
                    "risk_events_csv": str(risk_path.resolve()),
                    "control_schedule_csv": "",
                    "command": [
                        "python",
                        "engine.py",
                        "--supplier-risk-events-csv",
                        str(risk_path.resolve()),
                    ],
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest_path = campaign / "canonical_cascade_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_cascade_manifest.v2",
                "status": "complete",
                "failure_count": 0,
                "skipped_fail_fast_count": 0,
                "run_count": 1,
                "scenario_id": "scn:BASE",
                "days": 30,
                "seeds": [7],
                "cascade_ids": ["C1"],
                "variant_ids": ["incident_no_action"],
                "config": {
                    "snapshot": str(config_path.resolve()),
                    "sha256": _sha256(config_path),
                },
                "outputs": {
                    "runs": str(runs_path.resolve()),
                    "commands": str(commands_path.resolve()),
                    "config_snapshot": str(config_path.resolve()),
                },
                "output_sha256": {
                    "runs": _sha256(runs_path),
                    "commands": _sha256(commands_path),
                    "config_snapshot": _sha256(config_path),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "campaign": campaign,
        "run_root": run_root,
        "data": data,
        "risk": risk_path,
        "summary": summary_path,
        "run_manifest": run_manifest_path,
        "config": config_path,
        "runs": runs_path,
        "commands": commands_path,
        "manifest": manifest_path,
    }


def test_native_incident_propagates_to_campaign_client_and_cost_without_false_service_claim() -> (
    None
):
    registry = build_risk_impact_registry(**_base_rows(native=True))

    assert registry.quality["registry_version"] == REGISTRY_VERSION
    assert registry.quality["counts"]["native_transaction_bundle_count"] == 1
    assert registry.quality["counts"]["scope_day_association_bundle_count"] == 0
    assert registry.quality["quantity_reconciliation"][
        "source_allocation_coverage_ratio"
    ] == pytest.approx(1)
    assert registry.quality["quantity_reconciliation"][
        "receipt_lineage_coverage_ratio"
    ] == pytest.approx(1)

    incident = registry.incidents[0]
    assert incident["causality_level"] == "native_transaction"
    assert incident["causal_claim_allowed"] == 1
    assert incident["exposed_finished_lot_count"] == 1
    assert incident["exposed_client_count"] == 1
    assert json.loads(incident["served_exposed_qty_lower_by_uom_json"])[
        "UN"
    ] == pytest.approx(20)
    assert incident["pre_horizon_origin_present"] == 1

    campaign = next(
        row for row in registry.entities if row["entity_type"] == "production_campaign"
    )
    assert campaign["entity_id"] == "CMP-1"
    assert campaign["attributed_qty_lower"] == pytest.approx(50)
    customer = registry.client_service[0]
    assert customer["served_exposed_qty_lower"] == pytest.approx(20)
    assert (
        customer["service_impact_claim"]
        == "lineage_exposure_only_not_counterfactual_service_degradation"
    )

    cost = registry.costs[0]
    assert cost["transport_cost_actual_exposed"] == pytest.approx(10)
    assert cost["purchase_cost_actual_exposed"] == pytest.approx(220)
    assert (
        cost["incremental_total_cost_status"]
        == "not_identified_without_matched_counterfactual"
    )


def test_legacy_run_is_explicitly_association_not_native_causality() -> None:
    registry = build_risk_impact_registry(**_base_rows(native=False))

    assert registry.quality["counts"]["native_transaction_bundle_count"] == 0
    assert registry.quality["counts"]["scope_day_association_bundle_count"] == 1
    assert registry.incidents[0]["causality_level"] == "scope_day_association"
    assert registry.incidents[0]["causal_claim_allowed"] == 0
    assert (
        registry.bundles[0]["association_basis"]
        == "exact supplier/destination/item/decision-day scope"
    )
    assert (
        registry.costs[0]["purchase_cost_basis"]
        == "reconstructed_from_engine_formula_and_nominal_lane_cost"
    )
    assert registry.costs[0]["purchase_cost_actual_exposed"] == pytest.approx(220)


def test_overlapping_events_share_one_bundle_and_must_not_be_summed() -> None:
    registry = build_risk_impact_registry(**_base_rows(native=True, two_events=True))

    assert len(registry.bundles) == 1
    assert len(registry.bundle_events) == 2
    assert {row["overlap_group_id"] for row in registry.bundle_events} == {
        registry.bundles[0]["exposure_bundle_id"]
    }
    assert sum(
        row["event_exposure_qty_non_additive"] for row in registry.bundle_events
    ) == pytest.approx(200)
    assert registry.bundles[0]["shipped_qty"] == pytest.approx(100)
    assert all(
        row["do_not_sum_across_incidents"] == 1 for row in registry.bundle_events
    )


def test_component_merge_uses_union_bounds_instead_of_adding_incompatible_units() -> (
    None
):
    rows = _base_rows(native=True)
    # Only 40% of component C comes from the exposed material lot; an unrelated
    # second component is merged into the same output lot.
    rows["lot_event_rows"].append(
        _event("OTHER", 0, "opening_stock", "OTHER", "M-1", "item:X", 10)
    )
    rows["genealogy_rows"][1]["parent_qty"] = 40
    rows["genealogy_rows"].insert(
        2,
        _link(
            4,
            "production",
            "OTHER",
            "M-1",
            "item:X",
            "FG",
            "M-1",
            "item:FG",
            10,
            50,
            source_id="M-1|item:FG",
            campaign="CMP-1",
        ),
    )
    # The remaining 60 units of the same component are explicitly unexposed.
    rows["lot_event_rows"].append(
        _event("CLEAN", 0, "opening_stock", "CLEAN", "M-1", "item:C", 60)
    )
    rows["genealogy_rows"].insert(
        2,
        _link(
            4,
            "production",
            "CLEAN",
            "M-1",
            "item:C",
            "FG",
            "M-1",
            "item:FG",
            60,
            50,
            source_id="M-1|item:FG",
            campaign="CMP-1",
        ),
    )

    registry = build_risk_impact_registry(**rows)
    fg = next(
        row
        for row in registry.entities
        if row["entity_type"] == "finished_product_lot" and row["entity_id"] == "FG"
    )
    assert fg["attributed_share_lower"] == pytest.approx(0.4)
    assert fg["attributed_share_upper"] == pytest.approx(0.4)
    assert fg["attribution_method"] == "component_mix_union_bounds"


def test_edges_carry_each_endpoint_uom_without_cross_stage_conversion() -> None:
    rows = _base_rows(native=True)
    rows["shipment_rows"][0]["uom"] = "KG"
    for event in rows["lot_event_rows"]:
        event["uom"] = "KG" if event["item_id"] == "item:C" else "UN"

    registry = build_risk_impact_registry(**rows)

    risk_transport = next(
        row for row in registry.edges if row["link_type"] == "risk_exposed_transport"
    )
    assert risk_transport["source_uom"] == "KG"
    assert risk_transport["target_uom"] == "KG"

    production = next(row for row in registry.edges if row["link_type"] == "production")
    assert production["source_lot_id"] == "MAT"
    assert production["target_lot_id"] == "FG"
    assert production["source_qty_lower"] == pytest.approx(100)
    assert production["source_uom"] == "KG"
    assert production["target_qty_lower"] == pytest.approx(50)
    assert production["target_uom"] == "UN"

    downstream_transport = next(
        row
        for row in registry.edges
        if row["link_type"] == "transport" and row["source_lot_id"] == "FG"
    )
    assert downstream_transport["source_uom"] == "UN"
    assert downstream_transport["target_uom"] == "UN"
    assert registry.quality["edge_unit_integrity"] == {
        "status": "verified",
        "edge_count": len(registry.edges),
        "edges_with_both_endpoint_uoms": len(registry.edges),
        "production_edge_count": 1,
        "mixed_uom_production_edge_count": 1,
        "contract": (
            "Source and target quantities retain their own lot UOM. No endpoint "
            "conversion and no cross-stage quantity summation is performed."
        ),
    }


def test_transport_with_incompatible_endpoint_uoms_fails_closed() -> None:
    rows = _base_rows(native=True)
    rows["shipment_rows"][0]["uom"] = "KG"
    for event in rows["lot_event_rows"]:
        if event["lot_id"] == "SRC":
            event["uom"] = "KG"
        elif event["lot_id"] == "MAT":
            event["uom"] = "G"

    with pytest.raises(RiskImpactUnitError, match="changes UOM.*no conversion"):
        build_risk_impact_registry(**rows)


def test_edge_with_missing_entity_uom_fails_closed() -> None:
    rows = _base_rows(native=True)
    for event in rows["lot_event_rows"]:
        if event["lot_id"] == "FG":
            event["uom"] = ""

    with pytest.raises(RiskImpactUnitError, match="lot 'FG' has no UOM"):
        build_risk_impact_registry(**rows)


def test_writer_refuses_overwrite_and_emits_all_contract_files(tmp_path: Path) -> None:
    registry = build_risk_impact_registry(**_base_rows(native=True))
    output = tmp_path / "registry_v1"
    written = write_risk_impact_registry(registry, output)

    assert set(written) == {
        "incidents",
        "bundles",
        "bundle_events",
        "entities",
        "edges",
        "client_service",
        "costs",
        "quality",
    }
    with written["bundles"].open(encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle))[0]["shipment_id"] == "SHIP-1"
    with pytest.raises(FileExistsError):
        write_risk_impact_registry(registry, output)


def test_standalone_directory_hashes_exact_sources_and_written_registry_csvs(
    tmp_path: Path,
) -> None:
    data = tmp_path / "legacy_standalone" / "data"
    _write_registry_source_data(data)

    registry = build_risk_impact_registry_from_directory(data)
    provenance = registry.quality["provenance"]
    assert provenance["schema_version"] == PROVENANCE_VERSION
    assert provenance["verification_status"] == "standalone_data_sources_hashed"
    assert provenance["parent_campaign"] == {"detected": False}
    assert provenance["identity"]["cascade_id"] is None
    lot_source = provenance["source_files"]["lot_events"]
    assert lot_source["sha256"] == _sha256(data / "production_lot_events.csv")
    assert lot_source["row_count"] == len(_base_rows()["lot_event_rows"])
    assert lot_source["read_status"] == "read_from_single_byte_snapshot"

    output = tmp_path / "registry"
    written = write_risk_impact_registry(registry, output)
    quality = json.loads(written["quality"].read_text(encoding="utf-8"))
    for table_name, record in quality["registry_outputs"]["csv_artifacts"].items():
        assert record["sha256"] == _sha256(written[table_name])
        assert record["row_count"] == len(getattr(registry, table_name))
    quality_record = quality["registry_outputs"]["quality_json"]
    assert quality_record["sha256"] is None
    assert quality_record["self_hash_status"] == (
        "intentionally_excluded_to_avoid_recursive_self_hash"
    )


def test_legacy_standalone_run_keeps_missing_external_risk_input_explicit(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "legacy_run"
    data = run_root / "data"
    _write_registry_source_data(data)
    summary_path = run_root / "summaries" / "first_simulation_summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(
        json.dumps(
            {
                "scenario_id": "legacy",
                "policy": {
                    "seed": 3,
                    "supplier_risk": {
                        "enabled": True,
                        "events_csv": str(tmp_path / "no-longer-available.csv"),
                        "events_csv_sha256": "d" * 64,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    registry = build_risk_impact_registry_from_directory(data)
    provenance = registry.quality["provenance"]
    assert provenance["verification_status"] == "standalone_run_sources_hashed"
    missing = provenance["parent_run"]["configured_risk_events"]
    assert missing["exists"] is False
    assert missing["declared_sha256"] == "d" * 64
    assert missing["read_status"] == "unavailable_legacy_external_input"


def test_campaign_provenance_reconciles_identity_manifest_risk_and_j0(
    tmp_path: Path,
) -> None:
    paths = _write_campaign_fixture(tmp_path)

    registry = build_risk_impact_registry_from_directory(paths["data"])
    provenance = registry.quality["provenance"]
    assert provenance["verification_status"] == "campaign_run_verified"
    assert provenance["identity"] == {
        "campaign_id": "campaign",
        "cascade_id": "C1",
        "variant_id": "incident_no_action",
        "case_type": "incident_no_action",
        "solution_id": None,
        "seed": 7,
        "scenario_id": "scn:BASE",
    }
    critical = provenance["critical_hashes"]
    assert critical["campaign_manifest_sha256"] == _sha256(paths["manifest"])
    assert critical["campaign_config_snapshot_sha256"] == _sha256(paths["config"])
    assert critical["risk_events_sha256"] == _sha256(paths["risk"])
    assert critical["measurement_start_state_sha256"] == "a" * 64
    assert critical["run_summary_sha256"] == _sha256(paths["summary"])
    assert critical["run_manifest_sha256"] == _sha256(paths["run_manifest"])
    assert provenance["parent_campaign"]["runs"]["row_count"] == 1
    assert provenance["parent_campaign"]["risk_events"]["row_count"] == 1


def test_campaign_provenance_fails_closed_when_config_snapshot_is_tampered(
    tmp_path: Path,
) -> None:
    paths = _write_campaign_fixture(tmp_path)
    paths["config"].write_text('{"cascades": []}\n', encoding="utf-8")

    with pytest.raises(RiskImpactProvenanceError, match="campaign config_snapshot"):
        build_risk_impact_registry_from_directory(paths["data"])


def test_campaign_provenance_fails_closed_when_j0_identity_disagrees(
    tmp_path: Path,
) -> None:
    paths = _write_campaign_fixture(tmp_path)
    run_rows = list(csv.DictReader(paths["runs"].open(encoding="utf-8", newline="")))
    run_rows[0]["measurement_start_state_sha256"] = "c" * 64
    _write_csv_rows(paths["runs"], run_rows)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["output_sha256"]["runs"] = _sha256(paths["runs"])
    paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with pytest.raises(
        RiskImpactProvenanceError,
        match="Measurement-start state hash differs",
    ):
        build_risk_impact_registry_from_directory(paths["data"])


def test_engine_lot_ledger_carries_native_risk_context_through_receipt_genealogy() -> (
    None
):
    ledger = LotLedger(enabled=True)
    ledger.create_lot(
        day=0,
        node_id="SUP-1",
        item_id="item:C",
        qty=100,
        source_type="opening_stock",
        uom="UN",
        event_type="opening_stock",
    )
    allocations = ledger.consume(
        day=1,
        node_id="SUP-1",
        item_id="item:C",
        qty=100,
        event_type="lane_ship",
        source_id="edge:SUP-1_TO_M-1_C",
        shipment_id="SHIP-1",
        risk_decision_day=1,
        risk_event_ids="E1,E2",
        uom="UN",
    )
    child = ledger.create_child_lot(
        day=3,
        node_id="M-1",
        item_id="item:C",
        qty=100,
        source_type="lane_receipt",
        source_id="edge:SUP-1_TO_M-1_C",
        shipment_id="SHIP-1",
        risk_decision_day=1,
        risk_event_ids="E1,E2",
        parent_allocations=allocations,
        link_type="transport",
        uom="UN",
    )

    ship_event = next(
        row for row in ledger.event_rows if row["event_type"] == "lane_ship"
    )
    receipt_event = next(row for row in ledger.event_rows if row["lot_id"] == child)
    genealogy = ledger.genealogy_rows[0]
    for row in (ship_event, receipt_event, genealogy):
        assert row["shipment_id"] == "SHIP-1"
        assert row["risk_decision_day"] == 1
        assert row["risk_event_ids"] == "E1,E2"


def test_multi_chunk_schedule_has_one_unique_join_key_per_physical_chunk() -> None:
    traced, final_sequence = _attach_shipment_trace_ids(
        [(10, 40.0, 38.0), (12, 40.0, 38.0), (14, 20.0, 19.0)],
        start_sequence=7,
        risk_event_ids=["E1", "E2", "E1"],
    )

    assert final_sequence == 10
    assert [row[3] for row in traced] == [
        "SHIP-00000008",
        "SHIP-00000009",
        "SHIP-00000010",
    ]
    assert len({row[3] for row in traced}) == len(traced)
    assert {row[4] for row in traced} == {"E1,E2"}


def test_engine_smoke_emits_native_transaction_join_and_registry_counts_bundle_once(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    engine = (
        repo_root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
    )
    graph = (
        repo_root
        / "etudecas"
        / "simulation_prep"
        / "result"
        / "reference_baseline"
        / "_mrp_bom_tests"
        / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
    )
    risk_csv = tmp_path / "native_risk.csv"
    risk_csv.write_text(
        "event_id,risk_type,supplier_id,item_id,dst_node_id,edge_id,start_day,end_day,multiplier,notes\n"
        "DEMO-LEAD,lead_time_extra_days,DC-1920,item:268967,C-XXXXX,"
        "edge:DC-1910_TO_C-XXXXX_268967,0,9,2,Native lineage smoke\n",
        encoding="utf-8",
    )
    output = tmp_path / "engine_output"
    result = subprocess.run(
        [
            sys.executable,
            str(engine),
            "--input",
            str(graph),
            "--output-dir",
            str(output),
            "--scenario-id",
            "scn:BASE",
            "--days",
            "10",
            "--warmup-days",
            "0",
            "--seed",
            "320270",
            "--output-profile",
            "compact",
            "--skip-map",
            "--skip-plots",
            "--lot-trace",
            "--skip-lot-audit",
            "--supplier-risk-events-csv",
            str(risk_csv),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    data = output / "data"
    with (data / "production_supplier_shipments_daily.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        risk_shipments = [
            row
            for row in csv.DictReader(handle)
            if "DEMO-LEAD" in row["risk_event_ids"]
        ]
    assert risk_shipments
    shipment_ids = [row["shipment_id"] for row in risk_shipments]
    assert all(shipment_ids)
    assert len(shipment_ids) == len(set(shipment_ids))

    with (data / "production_lot_events.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        lot_events = list(csv.DictReader(handle))
    lane_ship_ids = {
        row["shipment_id"]
        for row in lot_events
        if row["event_type"] == "lane_ship" and "DEMO-LEAD" in row["risk_event_ids"]
    }
    assert set(shipment_ids) <= lane_ship_ids
    lane_ship_qty_by_id: dict[str, float] = {}
    for row in lot_events:
        if row["event_type"] != "lane_ship" or row["shipment_id"] not in shipment_ids:
            continue
        lane_ship_qty_by_id[row["shipment_id"]] = lane_ship_qty_by_id.get(
            row["shipment_id"], 0.0
        ) + float(row["qty"])
    for shipment in risk_shipments:
        assert lane_ship_qty_by_id[shipment["shipment_id"]] == pytest.approx(
            float(shipment["pulled_qty"])
        )

    with (data / "production_lot_genealogy.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        genealogy = list(csv.DictReader(handle))
    receipt_qty_by_id: dict[str, float] = {}
    for row in genealogy:
        if row["link_type"] != "transport" or row["shipment_id"] not in shipment_ids:
            continue
        receipt_qty_by_id[row["shipment_id"]] = receipt_qty_by_id.get(
            row["shipment_id"], 0.0
        ) + float(row["parent_qty"])
    for shipment in risk_shipments:
        if int(shipment["arrival_day"]) > 9:
            continue
        assert receipt_qty_by_id[shipment["shipment_id"]] == pytest.approx(
            float(shipment["shipped_qty"])
        )

    registry = build_risk_impact_registry_from_directory(data)
    assert registry.quality["counts"]["native_transaction_bundle_count"] == len(
        risk_shipments
    )
    assert registry.quality["counts"]["scope_day_association_bundle_count"] == 0
    assert registry.incidents[0]["supplier_id"] == "DC-1920"
    assert registry.incidents[0]["risk_type"] == "lead_time_extra_days"
    assert registry.incidents[0]["event_source"]
    assert len(registry.bundles) == len(
        {row["exposure_bundle_id"] for row in registry.bundles}
    )
    assert sum(float(row["shipped_qty"]) for row in registry.bundles) == pytest.approx(
        sum(float(row["shipped_qty"]) for row in risk_shipments)
    )
