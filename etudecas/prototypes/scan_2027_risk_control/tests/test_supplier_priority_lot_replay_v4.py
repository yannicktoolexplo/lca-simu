from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as replay,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _signed(payload: dict, field: str) -> dict:
    result = dict(payload)
    result[field] = replay.stable_sha256(result)
    return result


def _campaign_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    campaign = tmp_path / "campaign"
    results = tmp_path / "results"
    engine = campaign / "engine.py"
    graph = campaign / "op.json"
    profile = campaign / "profile.json"
    floors = campaign / "floors.csv"
    capacities = campaign / "capacities.csv"
    engine.parent.mkdir(parents=True)
    engine.write_text("# synthetic engine fixture\n", encoding="utf-8")
    _write_json(graph, {"nodes": [], "edges": []})
    _write_json(profile, {"args": ["--warmup-days", "2"]})
    _write_csv(floors, [], ["supplier_id", "item_id"])
    _write_csv(capacities, [], ["node_id", "item_id"])

    design = {
        "schema_version": replay.CAMPAIGN_SCHEMA_VERSION,
        "contract_revision": "synthetic-strict-v4",
        "minimum_case_days": 50,
        "engine": str(engine.resolve()),
        "engine_sha256": replay.sha256_file(engine),
        "engine_profile": str(profile.resolve()),
        "engine_profile_sha256": replay.sha256_file(profile),
        "managed_engine_args": ["--no-supplier-state-dependent-risks"],
        "states": [
            {
                "operating_point_id": "op_93",
                "graph": str(graph.resolve()),
                "graph_sha256": replay.sha256_file(graph),
                "supplier_floors": str(floors.resolve()),
                "supplier_floors_sha256": replay.sha256_file(floors),
                "factory_capacities": str(capacities.resolve()),
                "factory_capacities_sha256": replay.sha256_file(capacities),
            }
        ],
        "lanes": [
            {
                "lane_id": "lane-1",
                "supplier_id": "SUP-1",
                "item_id": "item:C1",
                "dst_node_id": "FAC-1",
                "edge_id": "EDGE-1",
                "target_product_id": "PF1",
            }
        ],
        "mechanisms": [
            {
                "key": "transport_delay",
                "risk_type": "lead_time_extra_days",
                "value": 120.0,
            },
            {
                "key": "planned_delivery_shortfall",
                "risk_type": "reliability",
                "value": 0.5,
            },
        ],
        "quality_branch_included": False,
        "quality_incident_included": False,
        "availability_incident_included": False,
        "capacity_incident_included": False,
        "stock_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
    }
    manifest = {
        **design,
        "campaign_signature": replay.stable_sha256(design),
        "status": "planned",
        "created_at_utc": "2026-09-05T00:00:00+00:00",
        "completed_at_utc": "",
    }
    manifest_path = campaign / "campaign_manifest.json"
    _write_json(manifest_path, manifest)

    priority = {
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": "lane-1",
        "supplier_id": "SUP-1",
        "item_id": "item:C1",
        "dst_node_id": "FAC-1",
        "edge_id": "EDGE-1",
        "target_product_id": "PF1",
        "priority_status": "dossier_to_investigate",
        "position": "1",
        "fixed360_effect_mean_pp": "2.0",
    }
    priority_path = results / "priority_lanes_by_cause_state.csv"
    _write_csv(priority_path, [priority], list(priority))

    warmup_hash = "c" * 64
    metric_rows: list[dict] = []
    effects = {101: 0.5, 102: 100.0 / 148.0, 103: 1.0}
    for seed, effect in effects.items():
        baseline_key = f"op_93__baseline__seed_{seed}"
        incident_key = f"op_93__lane-1__transport_delay__seed_{seed}"
        baseline_signature = replay.stable_sha256({"case": baseline_key})
        incident_signature = replay.stable_sha256({"case": incident_key})
        common = {
            "campaign_signature": manifest["campaign_signature"],
            "engine_sha256": manifest["engine_sha256"],
            "operating_point_id": "op_93",
            "seed": str(seed),
            "valid": "true",
            "status": "valid",
            "warmup_core_state_sha256": warmup_hash,
        }
        baseline_row = {
            **common,
            "stage": "baseline",
            "mechanism": "",
            "lane_id": "",
            "case_key": baseline_key,
            "case_signature": baseline_signature,
            "baseline_case_signature": baseline_signature,
            "simulation_days": "150",
        }
        incident_row = {
            **common,
            "stage": "incident",
            "mechanism": "transport_delay",
            "lane_id": "lane-1",
            "case_key": incident_key,
            "case_signature": incident_signature,
            "baseline_case_signature": baseline_signature,
            "required_simulation_days": "150",
            "simulation_days": "150",
            "incident_physically_exercised": "true",
            "risk_start_day": "2",
            "risk_end_day": "43",
            "impact_window_start_day": "2",
            "impact_window_end_day": "149",
            "target_latest_baseline_arrival_day": "3",
            "target_latest_stressed_arrival_day": "123",
            "impact_service_loss_fed_product_pp": str(effect),
            "impact_on_due_loss_fed_product_qty": "1" if seed == 102 else "",
            "impact_production_loss_fed_product_qty": "0" if seed == 102 else "",
        }
        metric_rows.extend([baseline_row, incident_row])

        baseline_evidence = _signed(
            {
                "schema_version": replay.CASE_SCHEMA_VERSION,
                "campaign_signature": manifest["campaign_signature"],
                "engine_sha256": manifest["engine_sha256"],
                "case_key": baseline_key,
                "case_signature": baseline_signature,
                "operating_point_id": "op_93",
                "stage": "baseline",
                "seed": seed,
                "simulation_days": 150,
                "valid": True,
                "status": "valid",
                "quality_branch_included": False,
                "availability_incident_included": False,
                "supplier_state_dependent_risks_enabled": False,
                "metrics": {"warmup_core_state_sha256": warmup_hash},
            },
            "evidence_signature",
        )
        _write_json(
            campaign / "shards" / "one" / "case_evidence" / f"{baseline_key}.json",
            baseline_evidence,
        )
        risk_row = {
            "event_id": f"risk-{seed}",
            "risk_type": "lead_time_extra_days",
            "supplier_id": "SUP-1",
            "item_id": "item:C1",
            "dst_node_id": "FAC-1",
            "edge_id": "EDGE-1",
            "start_day": 2,
            "end_day": 43,
            "multiplier": 120.0,
            "notes": "hypothese conditionnelle sans qualite",
        }
        risk_bytes = replay._risk_csv_bytes(risk_row)
        risk_path = (
            campaign
            / "shards"
            / "one"
            / "inputs"
            / "risk_events"
            / f"{incident_key}.csv"
        )
        risk_path.parent.mkdir(parents=True, exist_ok=True)
        risk_path.write_bytes(risk_bytes)
        incident_evidence = _signed(
            {
                "schema_version": replay.CASE_SCHEMA_VERSION,
                "campaign_signature": manifest["campaign_signature"],
                "engine_sha256": manifest["engine_sha256"],
                "case_key": incident_key,
                "case_signature": incident_signature,
                "operating_point_id": "op_93",
                "stage": "incident",
                "seed": seed,
                "simulation_days": 150,
                "valid": True,
                "status": "valid",
                "quality_branch_included": False,
                "availability_incident_included": False,
                "supplier_state_dependent_risks_enabled": False,
                "metrics": {"warmup_core_state_sha256": warmup_hash},
                "risk_row": risk_row,
                "risk_csv_sha256": replay.sha256_file(risk_path),
            },
            "evidence_signature",
        )
        _write_json(
            campaign / "shards" / "one" / "case_evidence" / f"{incident_key}.json",
            incident_evidence,
        )

    metrics_path = campaign / "shards" / "one" / "campaign_metrics.csv"
    fields = []
    for row in metric_rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    _write_csv(metrics_path, metric_rows, fields)
    validation = {
        "schema_version": "etudecas.synthetic.v4.finalizer",
        "status": "complete_validated",
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "expected_contract": {
            "quality_branch_included": False,
            "availability_incident_included": False,
        },
        "comparability_checks": {
            "quality_or_availability_incident_count": 0,
            "targeted_priority_lot_and_cascade_replay_required": True,
        },
        "inputs": {
            "campaign_manifest_sha256": replay.sha256_file(manifest_path),
            "metrics_csv_sha256": {
                str(metrics_path.relative_to(campaign)): replay.sha256_file(
                    metrics_path
                )
            },
        },
        "outputs": {
            priority_path.name: {
                "row_count": 1,
                "sha256": replay.sha256_file(priority_path),
            }
        },
    }
    _write_json(results / "campaign_validation.json", validation)
    return campaign, results, {"priority": priority, "warmup_hash": warmup_hash}


def _run_output(run_dir: Path, dossier: dict, arm: str) -> None:
    horizon = int(dossier["horizon_days"])
    is_incident = arm == "incident"
    risk_hash = dossier["risk_csv_sha256"] if is_incident else ""
    summary = {
        "input_sha256": dossier["graph_sha256"],
        "sim_days": horizon,
        "policy": {
            "seed": dossier["seed"],
            "output_profile": "compact",
            "lot_trace_enabled": True,
            "common_random_numbers": True,
            "warmup_boundary_audit": {
                "core_state_sha256": dossier["warmup_core_state_sha256"]
            },
            "supplier_state_dependent_risk": {"enabled": False},
            "supplier_risk": {
                "enabled": is_incident,
                "event_count": 1 if is_incident else 0,
                "events_csv_sha256": risk_hash,
                "warnings": [],
            },
        },
    }
    _write_json(run_dir / "summaries" / "first_simulation_summary.json", summary)
    data = run_dir / "data"
    shipment_fields = [
        "day",
        "shipment_id",
        "risk_decision_day",
        "risk_event_ids",
        "src_node_id",
        "dst_node_id",
        "item_id",
        "edge_id",
        "shipped_qty",
        "pulled_qty",
        "lead_days",
        "arrival_day",
        "reliability",
        "uom",
    ]
    base_shipments = [
        {
            "day": 0,
            "shipment_id": "S0",
            "risk_decision_day": 0,
            "risk_event_ids": "",
            "src_node_id": "SUP-1",
            "dst_node_id": "FAC-1",
            "item_id": "item:C1",
            "edge_id": "EDGE-1",
            "shipped_qty": 5,
            "pulled_qty": 5,
            "lead_days": 1,
            "arrival_day": 1,
            "reliability": 1,
            "uom": "UN",
        },
        {
            "day": 2,
            "shipment_id": "S1",
            "risk_decision_day": 2,
            "risk_event_ids": dossier["risk_row"]["event_id"] if is_incident else "",
            "src_node_id": "SUP-1",
            "dst_node_id": "FAC-1",
            "item_id": "item:C1",
            "edge_id": "EDGE-1",
            "shipped_qty": 10,
            "pulled_qty": 10,
            "lead_days": 121 if is_incident else 1,
            "arrival_day": 123 if is_incident else 3,
            "reliability": 1,
            "uom": "UN",
        },
    ]
    _write_csv(
        data / "production_supplier_shipments_daily.csv",
        base_shipments,
        shipment_fields,
    )

    applied_fields = [
        "day",
        "supplier_id",
        "dst_node_id",
        "item_id",
        "edge_id",
        "event_ids",
        "stock_multiplier",
        "capacity_multiplier",
        "lead_time_extra_days",
        "quality_delay_days",
        "reliability_multiplier",
        "quality_yield_multiplier",
        "availability_multiplier",
        "stock_writeoff_fraction",
    ]
    applied = []
    if is_incident:
        applied.append(
            {
                "day": 2,
                "supplier_id": "SUP-1",
                "dst_node_id": "FAC-1",
                "item_id": "item:C1",
                "edge_id": "EDGE-1",
                "event_ids": dossier["risk_row"]["event_id"],
                "stock_multiplier": 1,
                "capacity_multiplier": 1,
                "lead_time_extra_days": 120,
                "quality_delay_days": 0,
                "reliability_multiplier": 1,
                "quality_yield_multiplier": 1,
                "availability_multiplier": 1,
                "stock_writeoff_fraction": 0,
            }
        )
    _write_csv(data / "supplier_risk_events_applied_daily.csv", applied, applied_fields)
    _write_csv(
        data / "supplier_state_dependent_risk_events.csv",
        [],
        ["event_id", "risk_family", "risk_type"],
    )
    _write_csv(
        data / "lot_path_audit_issues.csv",
        [{"severity": "info", "kind": "synthetic", "details": "ok"}],
        ["severity", "kind", "details"],
    )

    event_fields = [
        "event_id",
        "day",
        "event_type",
        "lot_id",
        "node_id",
        "item_id",
        "qty",
        "qty_after",
        "uom",
        "source_type",
        "source_id",
        "shipment_id",
        "risk_decision_day",
        "risk_event_ids",
        "related_lot_id",
        "production_campaign_id",
        "notes",
    ]
    genealogy_fields = [
        "day",
        "link_type",
        "parent_lot_id",
        "parent_node_id",
        "parent_item_id",
        "child_lot_id",
        "child_node_id",
        "child_item_id",
        "parent_qty",
        "child_qty",
        "allocation_share",
        "source_id",
        "shipment_id",
        "risk_decision_day",
        "risk_event_ids",
        "production_campaign_id",
        "notes",
    ]
    if is_incident:
        event = dossier["risk_row"]["event_id"]
        events = [
            {
                "event_id": "E1",
                "day": 2,
                "event_type": "lane_ship",
                "lot_id": "LOT-I-SRC",
                "node_id": "SUP-1",
                "item_id": "item:C1",
                "qty": 10,
                "uom": "UN",
                "source_id": "EDGE-1",
                "shipment_id": "S1",
                "risk_decision_day": 2,
                "risk_event_ids": event,
            },
            {
                "event_id": "E2",
                "day": 123,
                "event_type": "lane_receipt",
                "lot_id": "LOT-I-MP",
                "node_id": "FAC-1",
                "item_id": "item:C1",
                "qty": 10,
                "uom": "UN",
                "shipment_id": "S1",
                "risk_decision_day": 2,
                "risk_event_ids": event,
            },
            {
                "event_id": "E3",
                "day": 124,
                "event_type": "production_consume",
                "lot_id": "LOT-I-MP",
                "node_id": "FAC-1",
                "item_id": "item:C1",
                "qty": 10,
                "uom": "UN",
                "production_campaign_id": "CAMP-1",
            },
            {
                "event_id": "E4",
                "day": 125,
                "event_type": "production_output",
                "lot_id": "LOT-I-PF",
                "node_id": "FAC-1",
                "item_id": "item:PF1",
                "qty": 10,
                "uom": "UN",
                "production_campaign_id": "CAMP-1",
            },
            {
                "event_id": "E5",
                "day": 127,
                "event_type": "demand_service",
                "lot_id": "LOT-I-CLIENT",
                "node_id": replay.V4_CLIENT_NODE_ID,
                "item_id": "item:PF1",
                "qty": 1,
                "uom": "UN",
            },
        ]
        genealogy = [
            {
                "day": 123,
                "link_type": "transport",
                "parent_lot_id": "LOT-I-SRC",
                "parent_node_id": "SUP-1",
                "parent_item_id": "item:C1",
                "child_lot_id": "LOT-I-MP",
                "child_node_id": "FAC-1",
                "child_item_id": "item:C1",
                "parent_qty": 10,
                "child_qty": 10,
                "allocation_share": 1,
                "source_id": "EDGE-1",
                "shipment_id": "S1",
                "risk_decision_day": 2,
                "risk_event_ids": event,
            },
            {
                "day": 125,
                "link_type": "production",
                "parent_lot_id": "LOT-I-MP",
                "parent_node_id": "FAC-1",
                "parent_item_id": "item:C1",
                "child_lot_id": "LOT-I-PF",
                "child_node_id": "FAC-1",
                "child_item_id": "item:PF1",
                "parent_qty": 10,
                "child_qty": 10,
                "production_campaign_id": "CAMP-1",
            },
            {
                "day": 127,
                "link_type": "transport",
                "parent_lot_id": "LOT-I-PF",
                "parent_node_id": "FAC-1",
                "parent_item_id": "item:PF1",
                "child_lot_id": "LOT-I-CLIENT",
                "child_node_id": replay.V4_CLIENT_NODE_ID,
                "child_item_id": "item:PF1",
                "parent_qty": 10,
                "child_qty": 10,
                "shipment_id": "S-PF",
            },
        ]
    else:
        events = []
        genealogy = []
    _write_csv(data / "production_lot_events.csv", events, event_fields)
    _write_csv(data / "production_lot_genealogy.csv", genealogy, genealogy_fields)
    plan_fields = [
        "day",
        "campaign_id",
        "batch_id",
        "wip_start_qty",
        "wip_end_qty",
        "released_qty",
        "released_lot_id",
        "binding_input_item_id",
        "reason",
    ]
    plan_rows = (
        [
            {
                "day": 124,
                "campaign_id": "CAMP-1",
                "batch_id": "BATCH-1",
                "wip_start_qty": 0,
                "wip_end_qty": 10,
                "released_qty": 0,
                "released_lot_id": "",
                "binding_input_item_id": "item:C1",
                "reason": "execution",
            }
        ]
        if is_incident
        else []
    )
    _write_csv(data / "production_plan_events.csv", plan_rows, plan_fields)
    campaign_fields = [
        "campaign_id",
        "status",
        "wip_qty",
        "blocked_lot_qty",
        "completed_lot_ids",
    ]
    campaign_rows = (
        [
            {
                "campaign_id": "CAMP-1",
                "status": "completed_after_delay",
                "wip_qty": 0,
                "blocked_lot_qty": 0,
                "completed_lot_ids": "LOT-I-PF",
            }
        ]
        if is_incident
        else []
    )
    _write_csv(data / "production_campaigns.csv", campaign_rows, campaign_fields)

    stocks = [
        {
            "day": day,
            "node_id": "FAC-1",
            "item_id": "item:C1",
            "stock_before_production": 20,
            "stock_end_of_day": 10 if is_incident and day >= 123 else 20,
        }
        for day in range(horizon)
    ]
    _write_csv(
        data / "production_input_stocks_daily.csv",
        stocks,
        ["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
    )
    production = [
        {
            "day": day,
            "node_id": "FAC-1",
            "item_id": "item:PF1",
            "produced_qty": 10 if day == (125 if is_incident else 4) else 0,
            "executed_qty": 10 if day == (125 if is_incident else 4) else 0,
            "released_qty": 10 if day == (125 if is_incident else 4) else 0,
            "wip_end_qty": 10 if is_incident and day in (123, 124) else 0,
            "cum_produced_qty": 0,
            "stock_end_of_day": 0,
        }
        for day in range(horizon)
    ]
    _write_csv(
        data / "production_output_products_daily.csv",
        production,
        [
            "day",
            "node_id",
            "item_id",
            "produced_qty",
            "executed_qty",
            "released_qty",
            "wip_end_qty",
            "cum_produced_qty",
            "stock_end_of_day",
        ],
    )
    demand = []
    for day in range(horizon):
        served = 0 if is_incident and day == 5 else 1
        demand.append(
            {
                "day": day,
                "node_id": replay.V4_CLIENT_NODE_ID,
                "item_id": "item:PF1",
                "demand_qty": 1,
                "required_with_backlog_qty": 2 if is_incident and day == 6 else 1,
                "served_qty": 2 if is_incident and day == 6 else served,
                "backlog_end_qty": 1 if is_incident and day == 5 else 0,
                "available_before_service_qty": served,
            }
        )
    _write_csv(
        data / "production_demand_service_daily.csv",
        demand,
        [
            "day",
            "node_id",
            "item_id",
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
            "available_before_service_qty",
        ],
    )


def test_plan_is_signed_bounded_and_selects_median_exercised_seed(
    tmp_path: Path,
) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    root = tmp_path / "replay"
    plan = replay.create_replay_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )
    assert plan["plan_signature"] == replay.stable_sha256(
        {key: value for key, value in plan.items() if key != "plan_signature"}
    )
    dossier = plan["dossiers"][0]
    assert dossier["seed"] == 102
    assert dossier["priority"]["priority_status"] == "dossier_to_investigate"
    assert dossier["horizon_days"] == 150
    baseline = dossier["arms"]["baseline"]["command"]
    incident = dossier["arms"]["incident"]["command"]
    for command in (baseline, incident):
        assert command.count("--lot-trace") == 1
        assert "--no-lot-trace" not in command
        assert "--skip-lot-audit" not in command
        assert command.count("--no-supplier-state-dependent-risks") == 1
        assert command[command.index("--days") + 1] == "150"
        assert command[command.index("--seed") + 1] == "102"
    assert "--supplier-risk-events-csv" not in baseline
    assert incident.count("--supplier-risk-events-csv") == 1
    assert replay.execute_replay(root)["status"] == "validated_not_executed"


def test_plan_fails_closed_on_forbidden_quality_contract(tmp_path: Path) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    manifest_path = campaign / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["quality_incident_included"] = True
    signed_design = {
        key: value
        for key, value in manifest.items()
        if key not in replay.CAMPAIGN_RUNTIME_FIELDS
    }
    manifest["campaign_signature"] = replay.stable_sha256(signed_design)
    _write_json(manifest_path, manifest)
    with pytest.raises(replay.ReplayContractError, match="quality_incident_included"):
        replay.create_replay_plan(
            campaign_root=campaign,
            results_dir=results,
            output_root=tmp_path / "replay",
            max_dossiers=1,
        )


def test_plan_fails_closed_when_a_hashed_metric_changes(tmp_path: Path) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    metrics = campaign / "shards" / "one" / "campaign_metrics.csv"
    metrics.write_text(metrics.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(replay.ReplayContractError, match="SHA-256 mismatch"):
        replay.create_replay_plan(
            campaign_root=campaign,
            results_dir=results,
            output_root=tmp_path / "replay",
            max_dossiers=1,
        )


def test_plan_prefers_and_revalidates_signed_finalizer_selection(
    tmp_path: Path,
) -> None:
    campaign, results, fixture = _campaign_fixture(tmp_path)
    seed = 102
    baseline_key = f"op_93__baseline__seed_{seed}"
    incident_key = f"op_93__lane-1__transport_delay__seed_{seed}"
    baseline_path = (
        campaign / "shards" / "one" / "case_evidence" / f"{baseline_key}.json"
    )
    incident_path = (
        campaign / "shards" / "one" / "case_evidence" / f"{incident_key}.json"
    )
    risk_path = (
        campaign / "shards" / "one" / "inputs" / "risk_events" / f"{incident_key}.csv"
    )
    baseline_evidence = json.loads(baseline_path.read_text(encoding="utf-8"))
    incident_evidence = json.loads(incident_path.read_text(encoding="utf-8"))
    selected = {
        "dossier_id": "dossier_01_123456789abc",
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": "lane-1",
        "supplier_id": "SUP-1",
        "item_id": "item:C1",
        "dst_node_id": "FAC-1",
        "edge_id": "EDGE-1",
        "target_product_id": "PF1",
        "priority_status": "dossier_to_investigate",
        "position": 1,
        "valid_exercised_seed_count": 3,
        "representative_seed": seed,
        "representative_metric": "impact_service_loss_fed_product_pp",
        "representative_effect_pp": 100.0 / 148.0,
        "cell_median_effect_pp": 100.0 / 148.0,
        "incident_case_key": incident_key,
        "incident_case_signature": incident_evidence["case_signature"],
        "baseline_case_key": baseline_key,
        "baseline_case_signature": baseline_evidence["case_signature"],
        "required_simulation_days": 150,
        "warmup_core_state_sha256": fixture["warmup_hash"],
        "risk_csv_sha256": incident_evidence["risk_csv_sha256"],
        "risk_csv_path": risk_path.relative_to(campaign).as_posix(),
        "incident_evidence_path": incident_path.relative_to(campaign).as_posix(),
        "incident_evidence_sha256": replay.sha256_file(incident_path),
        "baseline_evidence_path": baseline_path.relative_to(campaign).as_posix(),
        "baseline_evidence_sha256": replay.sha256_file(baseline_path),
    }
    manifest = json.loads(
        (campaign / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    selection = _signed(
        {
            "schema_version": (
                "etudecas.supplier_operating_point_full_campaign.v4."
                "lot_replay_selection.v1"
            ),
            "status": "complete_selected",
            "campaign_signature": manifest["campaign_signature"],
            "engine_sha256": manifest["engine_sha256"],
            "generated_at_utc": "2026-09-05T01:00:00+00:00",
            "selection_contract": {
                "evidence_paths_relative_to_campaign_root": True,
                "risk_paths_relative_to_campaign_root": True,
                "mechanisms_kept_separate": True,
                "maximum_dossiers": 3,
                "replay_executes_simulation": False,
                "quality_included": False,
                "state_dependent_supplier_risks_enabled": False,
            },
            "selected_dossiers": [selected],
        },
        "selection_signature",
    )
    selection_path = results / "lot_replay_plan.json"
    _write_json(selection_path, selection)
    validation_path = results / "campaign_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["lot_replay_plan"] = {
        "path": "lot_replay_plan.json",
        "row_count": 1,
        "sha256": replay.sha256_file(selection_path),
        "selection_signature": selection["selection_signature"],
    }
    _write_json(validation_path, validation)

    # The non-reusable smoke deliberately shares its case identity with the
    # first real shard.  Signed paths must win over a repository-wide search.
    smoke_evidence = campaign / "smoke" / "same" / "case_evidence"
    smoke_evidence.mkdir(parents=True)
    (smoke_evidence / baseline_path.name).write_bytes(baseline_path.read_bytes())
    (smoke_evidence / incident_path.name).write_bytes(incident_path.read_bytes())
    smoke_risk = campaign / "smoke" / "same" / "inputs" / "risk_events"
    smoke_risk.mkdir(parents=True)
    (smoke_risk / risk_path.name).write_bytes(risk_path.read_bytes())

    plan = replay.create_replay_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=tmp_path / "replay",
        max_dossiers=3,
    )
    assert plan["selection_contract"]["source"] == "signed_finalizer_lot_replay_plan"
    assert plan["dossiers"][0]["dossier_id"] == selected["dossier_id"]


def test_fake_execution_native_trace_kpis_and_standalone_html(tmp_path: Path) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    root = tmp_path / "replay"
    plan = replay.create_replay_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )
    dossier = plan["dossiers"][0]

    def fake_executor(command: list[str], _cwd: Path) -> int:
        run_dir = Path(command[command.index("--output-dir") + 1])
        arm = run_dir.name
        _run_output(run_dir, dossier, arm)
        return 0

    receipt = replay.execute_replay(root, execute=True, executor=fake_executor)
    assert receipt["status"] == "complete_validated"
    validation = replay.finalize_replay(root)
    assert validation["status"] == "complete_validated"
    assert validation["dossiers"][0]["status"] == "native_trace_to_client"
    assert validation["dossiers"][0]["cross_arm_lot_matching_used"] is False

    dossier_dir = root / "finalized" / "dossiers" / dossier["dossier_id"]
    finished = replay._read_csv(dossier_dir / "exposed_finished_lots.csv")
    clients = replay._read_csv(dossier_dir / "exposed_client_events.csv")
    assert finished[0]["finished_lot_id"] == "incident::LOT-I-PF"
    assert clients[0]["client_lot_id"] == "incident::LOT-I-CLIENT"
    assert all("baseline::" not in json.dumps(row) for row in finished + clients)
    kpis = json.loads((dossier_dir / "dossier_kpis.json").read_text(encoding="utf-8"))
    assert kpis["cross_arm_lot_matching_used"] is False
    assert kpis["on_due_units_lost"] == pytest.approx(1.0)
    assert kpis["service_loss_pp"] == pytest.approx(100.0 / 148.0)
    lags = replay._read_csv(dossier_dir / "cumulative_release_lag.csv")
    assert all(row["claim"] == "equal_cumulative_volume_not_same_lot" for row in lags)
    html_path = root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html"
    page = html_path.read_text(encoding="utf-8")
    assert "Aucun incident qualité" in page
    assert "jamais en prétendant suivre « le même lot »" in page
    assert "répétitions sur 30 où le flux a réellement été exposé" in page
    assert "ni un incident moyen ni sa probabilité" in page
    assert "aucun client réel ni aucune commande réelle" in page
    assert "https://" not in page


def test_on_due_service_clears_starting_backlog_before_current_demand(
    tmp_path: Path,
) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    root = tmp_path / "replay"
    dossier = replay.create_replay_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )["dossiers"][0]
    incident_dir = Path(dossier["arms"]["incident"]["run_dir"])
    _run_output(incident_dir, dossier, "incident")
    demand_path = incident_dir / "data" / "production_demand_service_daily.csv"
    demand_rows = replay._read_csv(demand_path)
    demand_rows[6].update(
        {
            "demand_qty": "1",
            "required_with_backlog_qty": "2",
            "served_qty": "1",
            "backlog_end_qty": "1",
        }
    )
    demand_rows[7].update(
        {
            "demand_qty": "1",
            "required_with_backlog_qty": "2",
            "served_qty": "2",
            "backlog_end_qty": "0",
        }
    )
    replay._write_csv(demand_path, demand_rows, list(demand_rows[0]))

    series = replay._daily_series(incident_dir, dossier=dossier)
    assert series["served_on_due"][6] == 0.0
    assert series["served_on_due"][7] == 1.0


def test_native_trace_rejects_receipt_before_declared_arrival(tmp_path: Path) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    root = tmp_path / "replay"
    dossier = replay.create_replay_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )["dossiers"][0]
    incident_dir = Path(dossier["arms"]["incident"]["run_dir"])
    _run_output(incident_dir, dossier, "incident")
    genealogy_path = incident_dir / "data" / "production_lot_genealogy.csv"
    genealogy = replay._read_csv(genealogy_path)
    genealogy[0]["day"] = "3"
    replay._write_csv(genealogy_path, genealogy, list(genealogy[0]))

    with pytest.raises(replay.ReplayContractError, match="timing"):
        replay.extract_native_trace(incident_dir, dossier=dossier)


def test_validation_rejects_nonempty_state_risk_ledger(tmp_path: Path) -> None:
    campaign, results, _ = _campaign_fixture(tmp_path)
    root = tmp_path / "replay"
    plan = replay.create_replay_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )
    dossier = plan["dossiers"][0]
    incident_dir = Path(dossier["arms"]["incident"]["run_dir"])
    _run_output(incident_dir, dossier, "incident")
    _write_csv(
        incident_dir / "data" / "supplier_state_dependent_risk_events.csv",
        [{"event_id": "STATE-1", "risk_family": "lead", "risk_type": "lead"}],
        ["event_id", "risk_family", "risk_type"],
    )
    with pytest.raises(replay.ReplayContractError, match="ledger is not empty"):
        replay.validate_arm(incident_dir, dossier=dossier, arm="incident")
