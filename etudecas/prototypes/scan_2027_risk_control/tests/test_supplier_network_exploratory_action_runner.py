from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_exploratory_action_runner as runner,
)


def _case(seed: int, seed_index: int, lever: str) -> runner.ActionCase:
    if lever == "future_lane_transport_reduction":
        failure_mode = "transport_delay"
        risk_type = "lead_time_extra_days"
        value = 120.0
        unit = "jours_ajoutes"
        lead_days = -7
        raw = rounded = standard = None
        lot_count = None
        uom = ""
    elif lever == "prepositioned_free_stock_14d":
        failure_mode = "supply_availability"
        risk_type = "availability"
        value = 0.5
        unit = "part_disponible"
        lead_days = None
        raw = 85.555555556
        rounded = standard = 1100.0
        lot_count = 1
        uom = "KG"
    elif (
        lever == "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
    ):
        failure_mode = "quality_hold"
        risk_type = "quality_delay"
        value = 90.0
        unit = "jours_ajoutes"
        lead_days = -7
        raw = rounded = standard = None
        lot_count = None
        uom = ""
    else:  # pragma: no cover - fixture misuse
        raise AssertionError(lever)
    return runner.ActionCase(
        pairing_id=f"chain__{lever}__seed_{seed}",
        seed=seed,
        seed_prefix_index=seed_index,
        selection_slot=1,
        chain_id="chain",
        supplier_id="supplier",
        item_id="item:component",
        dst_node_id="factory",
        edge_id="edge:supplier_factory",
        target_product_id="268091",
        lever_id=lever,
        failure_mode=failure_mode,
        incident_source_case_id=f"source__{failure_mode}",
        incident_risk_type=risk_type,
        incident_value=value,
        incident_unit=unit,
        incident_start_day=44,
        incident_end_day=223,
        lead_time_adjustment_days=lead_days,
        buffer_raw_qty=raw,
        buffer_rounded_qty=rounded,
        procurement_standard_lot_qty=standard,
        buffer_procurement_lot_count=lot_count,
        buffer_uom=uom,
    )


def _plan(tmp_path: Path, *, seed_count: int = 30) -> runner.ActionPlan:
    tmp_path.mkdir(parents=True, exist_ok=True)
    seeds = tuple(range(1000, 1000 + seed_count))
    cases = tuple(
        _case(seed, index, lever)
        for index, seed in enumerate(seeds, 1)
        for lever in runner.EXECUTABLE_LEVERS
    )
    graph = {
        "nodes": [
            {"id": "supplier", "type": "supplier"},
            {"id": "factory", "type": "factory"},
            {"id": "C-XXXXX", "type": "client"},
        ],
        "edges": [
            {
                "id": "edge:supplier_factory",
                "from": "supplier",
                "to": "factory",
                "items": ["item:component"],
            }
        ],
    }
    graph_path = tmp_path / "graph.json"
    engine_path = tmp_path / "engine.py"
    profile_path = tmp_path / "profile.json"
    floors_path = tmp_path / "floors.csv"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    engine_path.write_text("# fixture\n", encoding="utf-8")
    profile_path.write_text("{}\n", encoding="utf-8")
    floors_path.write_text(
        "supplier_id,item_id,dst_node_id,tested_capacity_floor_qty_per_day\n"
        "supplier,item:component,factory,100\n",
        encoding="utf-8",
    )
    return runner.ActionPlan(
        plan_dir=tmp_path,
        manifest={
            "protocol_signature": "v5-protocol",
            "graph_sha256": runner._sha256(graph_path),
            "engine_sha256": runner._sha256(engine_path),
            "profile_sha256": runner._sha256(profile_path),
        },
        cases=cases,
        seeds=seeds,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
        graph=graph,
        source_dir=tmp_path / "v2",
        post_priority_plan_dir=tmp_path / "v3-plan",
        post_priority_plan_manifest={"plan_signature": "v3-plan"},
        supplier_floors_path=floors_path,
        physical_capacity_by_lane={("supplier", "item:component", "factory"): 100.0},
        profile_args=(),
    )


def _v2_baseline(case: runner.ActionCase) -> dict[str, Any]:
    prefix = f"baseline_chain__{case.chain_id}__ops__"
    return {
        "scenario_id": "baseline_nominal",
        "seed": case.seed,
        "input_sha256": "graph-hash",
        "j0_state_sha256": f"j0-{case.seed}",
        "demand_qty_268091": 100.0,
        "fill_rate_268091": 1.0,
        "on_due_volume_proxy_268091": 1.0,
        "backlog_qty_days_268091": 0.0,
        "backlog_end_qty_268091": 0.0,
        "backlog_max_qty_268091": 0.0,
        f"{prefix}component_input_stock_min": 10.0,
        f"{prefix}component_days_at_zero": 0.0,
        f"{prefix}target_released_qty": 100.0,
        f"{prefix}component_stock_uom": "KG",
    }


def _v2_incident(case: runner.ActionCase) -> dict[str, Any]:
    return {
        "scenario_id": case.incident_source_case_id,
        "seed": case.seed,
        "input_sha256": "graph-hash",
        "j0_state_sha256": f"j0-{case.seed}",
        "demand_qty_268091": 100.0,
        "fill_rate_268091": 0.8,
        "on_due_volume_proxy_268091": 0.75,
        "backlog_qty_days_268091": 20.0,
        "backlog_end_qty_268091": 5.0,
        "backlog_max_qty_268091": 8.0,
        "component_input_stock_min": 0.0,
        "component_days_at_zero": 4.0,
        "target_released_qty": 80.0,
        "component_stock_uom": "KG",
    }


def _source_risk(case: runner.ActionCase) -> dict[str, Any]:
    return {
        "event_id": f"original-source-event__{case.failure_mode}",
        "risk_type": case.incident_risk_type,
        "supplier_id": case.supplier_id,
        "item_id": case.item_id,
        "dst_node_id": case.dst_node_id,
        "edge_id": (case.edge_id if case.failure_mode == "quality_hold" else ""),
        "start_day": case.incident_start_day,
        "end_day": case.incident_end_day,
        "multiplier": case.incident_value,
        "notes": "exact source incident",
    }


def _sources(
    plan: runner.ActionPlan,
    target_seed_ids: Sequence[int],
    *,
    j0_qty: float = 100.0,
) -> runner.SourceBundle:
    v2: dict[tuple[str, int], Mapping[str, Any]] = {}
    quality: dict[tuple[str, int], Mapping[str, Any]] = {}
    quality_hashes: dict[str, str] = {}
    baseline_j0: dict[tuple[int, str], Mapping[str, Any]] = {}
    risk_rows: dict[tuple[str, int], tuple[Mapping[str, Any], ...]] = {}
    risk_hashes: dict[tuple[str, int], str] = {}
    for case in plan.cases:
        v2[("baseline_nominal", case.seed)] = _v2_baseline(case)
        v2[(case.incident_source_case_id, case.seed)] = _v2_incident(case)
        risk = _source_risk(case)
        risk_key = (case.incident_source_case_id, case.seed)
        risk_rows[risk_key] = (risk,)
        risk_hashes[risk_key] = runner._stable_sha256([risk])
        baseline_j0[(case.seed, case.chain_id)] = {
            "cutover_stock_before_day0_flows_qty": j0_qty,
            "warmup_component_sha256": {
                "stock": "stock-before",
                "lot_ledger": "lots-before",
                "backlog": "same-backlog",
                "rng_state": "same-rng",
            },
        }
        if case.failure_mode == "quality_hold":
            case_key = f"quality::{case.incident_source_case_id}::{case.seed}"
            quality[(case.incident_source_case_id, case.seed)] = {
                "case_key": case_key,
                "j0_state_sha256": f"j0-{case.seed}",
                "product_metrics": [
                    {
                        "product_id": "268091",
                        "uom": "UN",
                        "demand_qty": 100.0,
                        "fill_rate": 0.7,
                        "on_due_ratio": 0.65,
                        "backlog_qty_days": 30.0,
                        "backlog_end_qty": 7.0,
                        "released_qty": 70.0,
                    }
                ],
            }
            quality_hashes[case_key] = f"hash-{case.seed}"
    identity = {"frozen_sources": "same-for-checkpoint-and-final"}
    return runner.SourceBundle(
        source_dir=plan.source_dir,
        post_priority_results_dir=plan.post_priority_plan_dir,
        target_seed_ids=tuple(target_seed_ids),
        v2_rows=v2,
        v3_quality_evidence=quality,
        v3_baseline_evidence={},
        v3_evidence_hashes=quality_hashes,
        incident_risk_rows=risk_rows,
        incident_risk_semantic_sha256=risk_hashes,
        baseline_j0=baseline_j0,
        source_identity=identity,
        source_identity_signature=runner._stable_sha256(identity),
    )


def _signed_fake_evidence(
    case: runner.ActionCase,
    sources: runner.SourceBundle,
    inputs: runner.InputBundle,
    run_dir: Path,
) -> dict[str, Any]:
    payload = {
        "schema_version": runner.EVIDENCE_SCHEMA_VERSION,
        "contract_revision": runner.CONTRACT_REVISION,
        "case_key": case.key,
        "case": asdict(case),
        "status": "fixture",
        "valid": True,
        "validation_errors": [],
        "source_fingerprint": sources.fingerprint(case),
        "input_manifest_sha256": inputs.input_manifest_sha256,
        "risk_csv_sha256": inputs.risk_sha256,
        "control_schedule_csv_sha256": inputs.control_schedule_sha256,
        "measurement_start_stock_scale_csv_sha256": inputs.stock_scale_sha256,
        "stock_lot_trace_verified": (
            True
            if case.lever_id == "prepositioned_free_stock_14d"
            else "not_applicable"
        ),
        "stock_lot_event_rows": (
            [
                {
                    "lot_id": f"measurement-start-stock-{case.seed}",
                    "event_type": "measurement_start_stock_increase",
                    "node_id": case.dst_node_id,
                    "item_id": case.item_id,
                    "qty": case.buffer_rounded_qty,
                }
            ]
            if case.lever_id == "prepositioned_free_stock_14d"
            else []
        ),
        "action_application_verified": True,
        "quality_hold_days_preserved": (
            90 if case.failure_mode == "quality_hold" else ""
        ),
        "alternative_source_created": False,
        "industrial_action_cost": "",
        "industrial_action_cost_status": ("not_quantified_missing_industrial_inputs"),
        "metrics": {
            "demand_qty": 100.0,
            "fill_rate": 0.9,
            "on_due_ratio": 0.85,
            "backlog_qty_days": 10.0,
            "backlog_end_qty": 2.0,
            "backlog_max_qty": 5.0,
            "component_min_stock_qty": 1.0,
            "component_reached_zero": False,
            "component_zero_stock_day_count": 0,
            "component_stock_metric_status": "complete_daily_action_series",
            "target_released_qty": 90.0,
            "product_uom": "UN",
            "component_uom": "KG",
            "industrial_action_cost": "",
            "industrial_action_cost_status": (
                "not_quantified_missing_industrial_inputs"
            ),
        },
        "run_dir": str(run_dir),
    }
    return runner._signed_payload(payload, "evidence_signature")


def test_open_loop_and_quality_inputs_reuse_exact_incident(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    sources = _sources(plan, plan.seeds[:1])
    output = tmp_path / "output"
    transport = next(
        case
        for case in plan.cases
        if case.seed == plan.seeds[0]
        and case.lever_id == "future_lane_transport_reduction"
    )
    prepared = runner.prepare_case_inputs(transport, plan, sources, output)
    risks = runner._read_csv(prepared.risk_csv)
    controls = runner._read_csv(prepared.control_schedule_csv)  # type: ignore[arg-type]
    assert risks == [
        {key: str(value) for key, value in _source_risk(transport).items()}
    ]
    assert len(controls) == 180
    assert {int(row["day"]) for row in controls} == set(range(44, 224))
    assert {row["lead_time_adjustment_days"] for row in controls} == {"-7"}
    assert all(row["supplier_id"] == "supplier" for row in controls)
    assert prepared.stock_scale_csv is None

    quality = next(
        case
        for case in plan.cases
        if case.seed == plan.seeds[0] and case.failure_mode == "quality_hold"
    )
    quality_inputs = runner.prepare_case_inputs(quality, plan, sources, output)
    quality_risk = runner._read_csv(quality_inputs.risk_csv)
    assert quality_risk[0]["risk_type"] == "quality_delay"
    assert float(quality_risk[0]["multiplier"]) == 90.0
    assert (
        runner._read_csv(quality_inputs.control_schedule_csv)[0][  # type: ignore[arg-type]
            "lead_time_adjustment_days"
        ]
        == "-7"
    )


def test_source_incident_semantics_are_validated_fail_closed(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    case = next(
        row
        for row in plan.cases
        if row.seed == plan.seeds[0]
        and row.lever_id == "future_lane_transport_reduction"
    )
    validated = runner._validate_incident_risk_row(
        case=case,
        row=_source_risk(case),
        plan=plan,
    )
    assert validated["edge_id"] == ""  # unique V2 wildcard, same physical lane
    changed = {**_source_risk(case), "multiplier": 119.0}
    with pytest.raises(ValueError, match="Incident risk semantics differ"):
        runner._validate_incident_risk_row(case=case, row=changed, plan=plan)


def test_lotified_j0_stock_scale_and_zero_guard(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    stock = next(
        case
        for case in plan.cases
        if case.seed == plan.seeds[0]
        and case.lever_id == "prepositioned_free_stock_14d"
    )
    sources = _sources(plan, plan.seeds[:1], j0_qty=100.0)
    prepared = runner.prepare_case_inputs(stock, plan, sources, tmp_path / "out")
    rows = runner._read_csv(prepared.stock_scale_csv)  # type: ignore[arg-type]
    assert rows == [{"node_id": "factory", "item_id": "item:component", "scale": "12"}]
    manifest = runner._read_json(prepared.input_manifest)
    assert manifest["buffer_raw_qty"] == pytest.approx(85.555555556)
    assert manifest["buffer_rounded_qty"] == 1100.0
    assert manifest["procurement_standard_lot_qty"] == 1100.0
    assert manifest["buffer_procurement_lot_count"] == 1
    assert manifest["buffer_procurement_lot_count_semantics"] == (
        "procurement_rounding_count_not_engine_lot_segmentation"
    )
    assert manifest["engine_j0_stock_adjustment_semantics"] == (
        "aggregate_stock_scale_with_lot_ledger_reconciliation"
    )
    assert manifest["stock_present_at_measured_j0"] is True
    assert manifest["stock_acquisition_simulated"] is False
    assert manifest["stock_procurement_lead_time_simulated"] is False
    assert manifest["stock_procurement_cost_simulated"] is False
    assert manifest["alternative_source_created"] is False

    zero_sources = _sources(plan, plan.seeds[:1], j0_qty=0.0)
    with pytest.raises(ValueError, match="J0 stock is zero"):
        runner.prepare_case_inputs(
            stock,
            plan,
            zero_sources,
            tmp_path / "zero-out",
        )


def test_engine_commands_only_add_declared_actuator_flags(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    sources = _sources(plan, plan.seeds[:1])
    first_inputs: runner.InputBundle | None = None
    first_case: runner.ActionCase | None = None
    for case in [row for row in plan.cases if row.seed == plan.seeds[0]]:
        inputs = runner.prepare_case_inputs(case, plan, sources, tmp_path / "out")
        first_inputs = first_inputs or inputs
        first_case = first_case or case
        command = runner.build_engine_command(case, plan, tmp_path / "out", inputs)
        assert command.count("--input") == 1
        assert command[command.index("--input") + 1] == str(plan.graph_path)
        assert "--common-random-numbers" in command
        assert "--warmup-boundary-audit" in command
        assert "--lot-trace" in command
        assert "--supplier-risk-events-csv" in command
        assert "alternative" not in " ".join(command).lower()
        if case.lever_id == "prepositioned_free_stock_14d":
            assert "--measurement-start-stock-scale-csv" in command
            assert "--control-schedule-csv" not in command
        else:
            assert "--control-schedule-csv" in command
            assert "--measurement-start-stock-scale-csv" not in command
    assert first_case is not None and first_inputs is not None
    plan.engine_path.write_text("# changed fixture\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Hash mismatch for engine_sha256"):
        runner.build_engine_command(
            first_case,
            plan,
            tmp_path / "out",
            first_inputs,
        )


def test_summary_and_ledgers_prove_real_action_application(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    sources = _sources(plan, plan.seeds[:1])
    transport = next(
        row
        for row in plan.cases
        if row.seed == plan.seeds[0]
        and row.lever_id == "future_lane_transport_reduction"
    )
    inputs = runner.prepare_case_inputs(transport, plan, sources, tmp_path / "out")
    case_dir = tmp_path / "transport-case"
    (case_dir / "data").mkdir(parents=True)
    runner._write_csv(
        case_dir / "data" / "canonical_action_ledger.csv",
        [
            {
                "action": "lead_time_adjustment_days",
                "status": "applied",
                "source_supplier_id": transport.supplier_id,
                "source_item_id": transport.item_id,
                "source_dst_node_id": transport.dst_node_id,
                "effective": -7,
                "executed_control_volume_qty": 1100.0,
            }
        ],
    )
    summary = {
        "policy": {
            "control_schedule": {
                "enabled": True,
                "sha256": inputs.control_schedule_sha256,
                "schedule_rows": 180,
                "resolved_actions": 1,
            }
        }
    }
    errors, applied = runner._control_application_errors(
        transport, summary, inputs, case_dir
    )
    assert errors == []
    assert len(applied) == 1

    runner._write_csv(
        case_dir / "data" / "canonical_action_ledger.csv",
        [
            {
                "action": "lead_time_adjustment_days",
                "status": "applied",
                "source_supplier_id": transport.supplier_id,
                "source_item_id": transport.item_id,
                "source_dst_node_id": transport.dst_node_id,
                "effective": -7,
                "executed_control_volume_qty": 0.0,
            }
        ],
    )
    errors, _ = runner._control_application_errors(transport, summary, inputs, case_dir)
    assert errors

    runner._write_csv(
        case_dir / "data" / "canonical_action_ledger.csv",
        [
            {
                "action": "lead_time_adjustment_days",
                "status": "applied",
                "source_supplier_id": transport.supplier_id,
                "source_item_id": transport.item_id,
                "source_dst_node_id": "another-factory",
                "effective": -7,
                "executed_control_volume_qty": 1100.0,
            },
            {
                "action": "lead_time_adjustment_days",
                "status": "applied",
                "source_supplier_id": transport.supplier_id,
                "source_item_id": transport.item_id,
                "source_dst_node_id": transport.dst_node_id,
                "effective": -7,
                "executed_control_volume_qty": 1100.0,
            },
        ],
    )
    errors, _ = runner._control_application_errors(transport, summary, inputs, case_dir)
    assert "an undeclared control lever, lane or value was applied" in errors

    stock = next(
        row
        for row in plan.cases
        if row.seed == plan.seeds[0] and row.lever_id == "prepositioned_free_stock_14d"
    )
    stock_inputs = runner.prepare_case_inputs(stock, plan, sources, tmp_path / "out")
    stock_dir = tmp_path / "stock-case"
    (stock_dir / "data").mkdir(parents=True)
    runner._write_csv(
        stock_dir / "data" / "measurement_start_stock_adjustments.csv",
        [
            {
                "node_id": stock.dst_node_id,
                "item_id": stock.item_id,
                "stock_before_qty": 100.0,
                "stock_added_qty": 1100.0,
                "scale": 12.0,
                "lot_balance_matches_stock_after": 1,
            }
        ],
    )
    runner._write_csv(
        stock_dir / "data" / "production_lot_events.csv",
        [
            {
                "lot_id": "measurement-start-stock-lot-1",
                "event_type": "measurement_start_stock_increase",
                "node_id": stock.dst_node_id,
                "item_id": stock.item_id,
                "source_id": "measurement_start_stock_scale_csv",
                "qty": 1100.0,
            }
        ],
    )
    stock_summary = {
        "policy": {
            "measurement_start_stock_scale": {
                "enabled": True,
                "source_csv_sha256": stock_inputs.stock_scale_sha256,
                "adjustment_rows": 1,
            },
            "warmup_boundary_audit": {
                "component_sha256": {
                    "stock": "stock-after",
                    "lot_ledger": "lots-after",
                    "backlog": "same-backlog",
                    "rng_state": "same-rng",
                }
            },
        }
    }
    errors, adjusted, stock_lot_events = runner._stock_application_errors(
        stock,
        stock_summary,
        stock_inputs,
        sources,
        stock_dir,
    )
    assert errors == []
    assert len(adjusted) == 1
    assert stock_lot_events[0]["lot_id"] == "measurement-start-stock-lot-1"
    stock_summary["policy"]["warmup_boundary_audit"]["component_sha256"]["backlog"] = (
        "changed"
    )
    errors, _, _ = runner._stock_application_errors(
        stock,
        stock_summary,
        stock_inputs,
        sources,
        stock_dir,
    )
    assert "paired J0 state changed: backlog" in errors

    transport = next(
        row
        for row in plan.cases
        if row.seed == plan.seeds[0]
        and row.lever_id == "future_lane_transport_reduction"
    )
    non_lot_errors = runner._j0_component_errors(
        case=transport,
        sources=sources,
        actual_components={
            "stock": "stock-before",
            "lot_ledger": "instrumented-lots",
            "backlog": "same-backlog",
            "rng_state": "same-rng",
        },
        ignored_components={"lot_ledger"},
    )
    assert non_lot_errors == []


def test_v2_compact_metrics_keep_production_and_zero_day_count(
    tmp_path: Path,
) -> None:
    case = _case(1000, 1, "future_lane_transport_reduction")
    baseline = runner._v2_metrics(_v2_baseline(case), case, baseline=True)
    incident = runner._v2_metrics(_v2_incident(case), case, baseline=False)
    assert baseline["target_released_qty"] == 100.0
    assert incident["target_released_qty"] == 80.0
    assert baseline["component_zero_stock_day_count"] == 0.0
    assert incident["component_zero_stock_day_count"] == 4.0
    assert "retained_derived_horizon_count" in incident["component_stock_metric_status"]


def test_action_metrics_require_exact_daily_series_and_factory_scope(
    tmp_path: Path,
) -> None:
    case = _case(1000, 1, "future_lane_transport_reduction")
    data = tmp_path / "case" / "data"
    data.mkdir(parents=True)
    service_rows = [
        {
            "day": day,
            "node_id": runner.CLIENT_NODE_ID,
            "item_id": "item:268091",
            "demand_qty": 10.0,
            "required_with_backlog_qty": 10.0,
            "served_qty": 10.0,
            "backlog_end_qty": 0.0,
        }
        for day in range(runner.MEASURED_DAYS)
    ]
    stock_rows = [
        {
            "day": day,
            "node_id": case.dst_node_id,
            "item_id": case.item_id,
            "stock_end_of_day": 5.0,
        }
        for day in range(runner.MEASURED_DAYS)
    ]
    production_rows = [
        {
            "day": day,
            "node_id": case.dst_node_id,
            "item_id": "item:268091",
            "released_qty": 2.0,
        }
        for day in range(runner.MEASURED_DAYS)
    ]
    production_rows.extend(
        {
            "day": day,
            "node_id": "another-factory",
            "item_id": "item:268091",
            "released_qty": 1000.0,
        }
        for day in range(runner.MEASURED_DAYS)
    )
    runner._write_csv(data / "production_demand_service_daily.csv", service_rows)
    runner._write_csv(data / "production_input_stocks_daily.csv", stock_rows)
    runner._write_csv(data / "production_output_products_daily.csv", production_rows)
    metrics = runner._action_metrics(tmp_path / "case", case)
    assert metrics["target_released_qty"] == 2.0 * runner.MEASURED_DAYS

    stock_rows[-1]["day"] = 0
    runner._write_csv(data / "production_input_stocks_daily.csv", stock_rows)
    with pytest.raises(ValueError, match="stock series is not complete"):
        runner._action_metrics(tmp_path / "case", case)


def test_paired_result_rejects_missing_reference_metric(tmp_path: Path) -> None:
    plan = _plan(tmp_path / "plan")
    sources = _sources(plan, plan.seeds[:1])
    case = next(
        row
        for row in plan.cases
        if row.seed == plan.seeds[0]
        and row.lever_id == "future_lane_transport_reduction"
    )
    inputs = runner.prepare_case_inputs(case, plan, sources, tmp_path / "out")
    evidence = _signed_fake_evidence(case, sources, inputs, tmp_path / "fixture")
    incident = sources.v2_rows[(case.incident_source_case_id, case.seed)]
    assert isinstance(incident, dict)
    incident.pop("on_due_volume_proxy_268091")
    with pytest.raises(ValueError, match="Invalid comparable incident_no_action"):
        runner._paired_result(case, evidence, sources)


def test_checkpoint_15_resumes_to_30_without_recalculation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path / "plan")
    calls: list[str] = []

    monkeypatch.setattr(runner, "load_action_plan", lambda **_kwargs: plan)

    def source_loader(
        _plan_arg: runner.ActionPlan,
        *,
        post_priority_results_dir: Path,
        target_seed_ids: Sequence[int],
        j0_snapshot_dir: Path,
    ) -> runner.SourceBundle:
        del post_priority_results_dir, j0_snapshot_dir
        return _sources(plan, target_seed_ids)

    monkeypatch.setattr(runner, "validate_paired_sources", source_loader)

    def executor(
        case: runner.ActionCase,
        _plan_arg: runner.ActionPlan,
        sources: runner.SourceBundle,
        output_dir: Path,
        inputs: runner.InputBundle,
    ) -> Mapping[str, Any]:
        calls.append(case.key)
        return _signed_fake_evidence(
            case,
            sources,
            inputs,
            output_dir / "fixture-runs" / runner._case_digest(case.key),
        )

    output = tmp_path / "action-results"
    first = runner.run_action_campaign(
        plan_dir=tmp_path,
        post_priority_results_dir=tmp_path,
        output_dir=output,
        mode="full",
        checkpoint_after_repetitions=15,
        workers=4,
        engine_execution_authorized=True,
        case_executor=executor,
    )
    assert first["status"] == "paused_preliminary_15_of_30"
    assert len(calls) == 45
    checkpoint = runner._read_json(output / runner.CHECKPOINT_FILE)
    assert checkpoint["completed_seed_ids"] == list(plan.seeds[:15])
    assert checkpoint["signed_final_seed_ids"] == list(plan.seeds)
    assert checkpoint["case_count"] == 45
    first_evidence_hashes = dict(
        runner._read_json(output / runner.LEDGER_FILE)["case_file_sha256"]
    )

    final = runner.run_action_campaign(
        plan_dir=tmp_path,
        post_priority_results_dir=tmp_path,
        output_dir=output,
        mode="full",
        workers=4,
        engine_execution_authorized=True,
        case_executor=executor,
    )
    assert final["status"] == "complete_30_of_30"
    assert len(calls) == 90
    ledger = runner._read_json(output / runner.LEDGER_FILE)
    assert len(ledger["case_files"]) == 90
    assert all(
        ledger["case_file_sha256"][key] == value
        for key, value in first_evidence_hashes.items()
    )
    assert final["reused_valid_action_case_count"] == 45
    assert final["publishable_results"] is False  # fixture executor
    assert runner._read_csv(output / runner.FINAL_RESULTS_FILE)
    assert runner._read_csv(output / runner.FINAL_SUMMARY_FILE)

    runner.run_action_campaign(
        plan_dir=tmp_path,
        post_priority_results_dir=tmp_path,
        output_dir=output,
        mode="full",
        workers=2,
        engine_execution_authorized=True,
        case_executor=executor,
    )
    assert len(calls) == 90


def test_smoke_signature_is_non_reusable_in_full_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path / "plan")
    monkeypatch.setattr(runner, "load_action_plan", lambda **_kwargs: plan)
    monkeypatch.setattr(
        runner,
        "validate_paired_sources",
        lambda _plan, *, post_priority_results_dir, target_seed_ids, j0_snapshot_dir: _sources(
            plan, target_seed_ids
        ),
    )

    def executor(
        case: runner.ActionCase,
        _plan_arg: runner.ActionPlan,
        sources: runner.SourceBundle,
        output_dir: Path,
        inputs: runner.InputBundle,
    ) -> Mapping[str, Any]:
        return _signed_fake_evidence(case, sources, inputs, output_dir / "fixture")

    output = tmp_path / "smoke"
    smoke = runner.run_action_campaign(
        plan_dir=tmp_path,
        post_priority_results_dir=tmp_path,
        output_dir=output,
        mode="smoke",
        workers=1,
        engine_execution_authorized=True,
        case_executor=executor,
    )
    assert smoke["status"] == "smoke_complete_nonreusable"
    assert smoke["completed_case_count"] == 3
    assert smoke["smoke_reusable_in_full"] is False
    assert smoke["smoke_used_for_eta"] is False
    with pytest.raises(ValueError, match="different action campaign scope"):
        runner.run_action_campaign(
            plan_dir=tmp_path,
            post_priority_results_dir=tmp_path,
            output_dir=output,
            mode="full",
            checkpoint_after_repetitions=15,
            workers=1,
            engine_execution_authorized=True,
            case_executor=executor,
        )


def test_validate_waits_for_sources_and_never_starts_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path / "plan")
    monkeypatch.setattr(runner, "load_action_plan", lambda **_kwargs: plan)

    def not_ready(*_args: Any, **_kwargs: Any) -> runner.SourceBundle:
        raise runner.SourcesNotReadyError("V3 still running")

    monkeypatch.setattr(runner, "validate_paired_sources", not_ready)
    result = runner.run_action_campaign(
        plan_dir=tmp_path,
        post_priority_results_dir=tmp_path,
        output_dir=None,
        mode="validate",
        checkpoint_after_repetitions=15,
    )
    assert result == {
        "status": "sources_not_ready",
        "reason": "V3 still running",
        "requested_seed_count": 15,
        "engine_execution_started": False,
    }


def test_completed_v3_ledger_is_bound_to_final_manifest(tmp_path: Path) -> None:
    ledger_path = tmp_path / "execution_ledger.json"
    ledger = {
        "runner_signature": "v3",
        "case_files": {"case": "ledger_cases/case.json"},
        "case_file_sha256": {"case": "evidence-hash"},
    }
    runner._write_json(ledger_path, ledger)
    manifest = {
        "ledger_case_count": 1,
        "ledger_case_file_sha256_count": 1,
        "execution_ledger_sha256": runner._sha256(ledger_path),
    }
    runner._validate_completed_v3_ledger(
        manifest=manifest,
        ledger=ledger,
        ledger_path=ledger_path,
    )
    changed = {**ledger, "case_file_sha256": {"case": "changed"}}
    runner._write_json(ledger_path, changed)
    with pytest.raises(ValueError, match="Completed V3 ledger differs"):
        runner._validate_completed_v3_ledger(
            manifest=manifest,
            ledger=changed,
            ledger_path=ledger_path,
        )


def test_signed_payload_detects_tampering() -> None:
    signed = runner._signed_payload({"value": 1}, "signature")
    runner._validate_signed_payload(signed, "signature", label="fixture")
    signed["value"] = 2
    with pytest.raises(ValueError, match="Invalid fixture integrity signature"):
        runner._validate_signed_payload(signed, "signature", label="fixture")
