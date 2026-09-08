from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as actions,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lot_replay,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_priority_lot_replay_v4 import (
    _campaign_fixture,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    ordered = list(fields or [])
    for row in rows:
        for field in row:
            if field not in ordered:
                ordered.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered)
        writer.writeheader()
        writer.writerows(rows)


def _sign(payload: dict, field: str) -> dict:
    result = dict(payload)
    result[field] = lot_replay.stable_sha256(result)
    return result


def _upgrade_fixture_for_actions(tmp_path: Path) -> tuple[Path, Path]:
    campaign, results, fixture = _campaign_fixture(tmp_path)
    manifest_path = campaign / "campaign_manifest.json"
    manifest = _read_json(manifest_path)
    manifest["lanes"][0]["target_product_id"] = "268091"
    signed_design = {
        key: value
        for key, value in manifest.items()
        if key not in lot_replay.CAMPAIGN_RUNTIME_FIELDS
    }
    manifest["campaign_signature"] = lot_replay.stable_sha256(signed_design)
    _write_json(manifest_path, manifest)

    priority_path = results / "priority_lanes_by_cause_state.csv"
    priority_rows = _read_csv(priority_path)
    priority_rows[0]["target_product_id"] = "268091"
    _write_csv(priority_path, priority_rows)

    metrics_path = campaign / "shards" / "one" / "campaign_metrics.csv"
    metric_rows = _read_csv(metrics_path)
    for row in metric_rows:
        row["campaign_signature"] = manifest["campaign_signature"]
        row["state_evaluation_days"] = "720"
        row["simulation_days"] = "720"
        if row["stage"] == "baseline":
            row.update(
                {
                    "service_output_product_268091_pct": "100",
                    "backlog_qty_days": "0",
                    "max_backlog_qty": "0",
                    "production_released_268091_qty": "150",
                }
            )
        if row["stage"] != "incident":
            continue
        row["required_simulation_days"] = "720"
        row["impact_window_start_day"] = "2"
        row["impact_window_end_day"] = "361"
        loss = float(row["impact_service_loss_fed_product_pp"])
        row.update(
            {
                "baseline_impact_service_268091_pct": "100",
                "baseline_impact_demand_268091_qty": "148",
                "impact_service_268091_pct": str(100.0 - loss),
                "impact_demand_268091_qty": "148",
                "service_output_product_268091_pct": str(100.0 - loss),
                "backlog_qty_days": "10",
                "max_backlog_qty": "2",
                "production_released_268091_qty": "100",
                # Deliberately absent: costs. They must remain unavailable/null,
                # never silently become zero.
                "total_cost": "",
                "total_transport_cost": "",
                "total_purchase_cost": "",
            }
        )
    _write_csv(metrics_path, metric_rows)

    evidence_root = campaign / "shards" / "one" / "case_evidence"
    for evidence_path in evidence_root.glob("*.json"):
        evidence = _read_json(evidence_path)
        evidence.pop("evidence_signature")
        evidence["campaign_signature"] = manifest["campaign_signature"]
        evidence["simulation_days"] = 720
        if evidence["stage"] == "incident":
            seed = int(evidence["seed"])
            evidence["baseline_case_signature"] = lot_replay.stable_sha256(
                {"case": f"op_93__baseline__seed_{seed}"}
            )
            evidence["lane"] = {
                "lane_id": "lane-1",
                "supplier_id": "SUP-1",
                "item_id": "item:C1",
                "dst_node_id": "FAC-1",
                "edge_id": "EDGE-1",
                "target_product_id": "268091",
            }
            evidence["mechanism"] = {
                "key": "transport_delay",
                "risk_type": "lead_time_extra_days",
                "value": 120.0,
            }
            evidence["incident_proof"] = {
                "incident_physically_exercised": True,
                "tagged_shipments": [
                    {
                        "shipment_id": "S1",
                        "risk_decision_day": 2,
                        "src_node_id": "SUP-1",
                        "dst_node_id": "FAC-1",
                        "item_id": "item:C1",
                        "edge_id": "EDGE-1",
                        "pulled_qty": 10,
                        "shipped_qty": 10,
                        "lead_days": 121,
                    }
                ],
            }
        _write_json(evidence_path, _sign(evidence, "evidence_signature"))

    seed = 102
    incident_key = f"op_93__lane-1__transport_delay__seed_{seed}"
    baseline_key = f"op_93__baseline__seed_{seed}"
    incident_path = evidence_root / f"{incident_key}.json"
    baseline_path = evidence_root / f"{baseline_key}.json"
    incident_evidence = _read_json(incident_path)
    baseline_evidence = _read_json(baseline_path)
    risk_path = (
        campaign / "shards" / "one" / "inputs" / "risk_events" / f"{incident_key}.csv"
    )
    selected = {
        "dossier_id": "dossier_01_action_test",
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": "lane-1",
        "supplier_id": "SUP-1",
        "item_id": "item:C1",
        "dst_node_id": "FAC-1",
        "edge_id": "EDGE-1",
        "target_product_id": "268091",
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
        "required_simulation_days": 720,
        "warmup_core_state_sha256": fixture["warmup_hash"],
        "risk_csv_sha256": incident_evidence["risk_csv_sha256"],
        "risk_csv_path": risk_path.relative_to(campaign).as_posix(),
        "incident_evidence_path": incident_path.relative_to(campaign).as_posix(),
        "incident_evidence_sha256": lot_replay.sha256_file(incident_path),
        "baseline_evidence_path": baseline_path.relative_to(campaign).as_posix(),
        "baseline_evidence_sha256": lot_replay.sha256_file(baseline_path),
    }
    selection = _sign(
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
    validation = _read_json(validation_path)
    validation["campaign_signature"] = manifest["campaign_signature"]
    validation["inputs"]["campaign_manifest_sha256"] = lot_replay.sha256_file(
        manifest_path
    )
    validation["inputs"]["metrics_csv_sha256"] = {
        str(metrics_path.relative_to(campaign)): lot_replay.sha256_file(metrics_path)
    }
    validation["outputs"][priority_path.name] = {
        "row_count": 1,
        "sha256": lot_replay.sha256_file(priority_path),
    }
    validation["outputs"][selection_path.name] = {
        "path": selection_path.name,
        "row_count": 1,
        "sha256": lot_replay.sha256_file(selection_path),
        "selection_signature": selection["selection_signature"],
    }
    _write_json(validation_path, validation)
    return campaign, results


def _write_action_run(command: list[str], run_dir: Path, plan: dict) -> SimpleNamespace:
    seed = int(command[command.index("--seed") + 1])
    dossier = plan["dossiers"][0]
    seed_plan = next(row for row in dossier["seed_plans"] if row["seed"] == seed)
    action_id = run_dir.name
    arm = seed_plan["arms"][action_id]
    event_id = seed_plan["incident_risk_contract"]["event_id"]
    summary = {
        "input_sha256": dossier["graph_sha256"],
        "sim_days": seed_plan["horizon_days"],
        "policy": {
            "seed": seed,
            "output_profile": "compact",
            "lot_trace_enabled": False,
            "common_random_numbers": True,
            "supplier_state_dependent_risk": {"enabled": False},
            "supplier_risk": {
                "enabled": True,
                "event_count": 1,
                "events_csv_sha256": arm["risk_csv_sha256"],
            },
            "control_schedule": {
                "enabled": True,
                "sha256": arm["action_input_sha256"],
                "schedule_rows": 42,
            },
            "control_provider": {
                "enabled": True,
                "mode": "daily_open_loop_schedule",
                "closed_loop_claimed": False,
            },
        },
        "kpis": {},
    }
    _write_json(run_dir / "summaries" / "first_simulation_summary.json", summary)
    data = run_dir / "data"
    _write_csv(
        data / "production_supplier_shipments_daily.csv",
        [
            {
                "day": 2,
                "shipment_id": "S1",
                "risk_decision_day": 2,
                "src_node_id": "SUP-1",
                "dst_node_id": "FAC-1",
                "item_id": "item:C1",
                "edge_id": "EDGE-1",
                "pulled_qty": "10.000000",
                "shipped_qty": "10.0",
                "lead_days": 107,
            }
        ],
    )
    _write_csv(
        data / "supplier_risk_events_applied_daily.csv",
        [
            {
                "day": 2,
                "supplier_id": "SUP-1",
                "dst_node_id": "FAC-1",
                "item_id": "item:C1",
                "edge_id": "EDGE-1",
                "event_ids": event_id,
                "stock_multiplier": 1,
                "capacity_multiplier": 1,
                "lead_time_multiplier": 1,
                "lead_time_extra_days": 120,
                "quality_delay_days": 0,
                "reliability_multiplier": 1,
                "quality_yield_multiplier": 1,
                "availability_multiplier": 1,
                "purchase_cost_multiplier": 1,
                "transport_cost_multiplier": 1,
                "external_capacity_multiplier": 1,
                "external_availability_multiplier": 1,
                "external_lead_time_multiplier": 1,
                "external_lead_time_extra_days": 0,
                "external_quality_yield_multiplier": 1,
                "external_cost_multiplier": 1,
                "stock_writeoff_fraction": 0,
            }
        ],
    )
    _write_csv(
        data / "supplier_state_dependent_risk_events.csv",
        [],
        ["event_id", "risk_family", "risk_type"],
    )
    demand_rows = [
        {
            "day": day,
            "node_id": "C-XXXXX",
            "item_id": "268091",
            "demand_qty": 1 if day < 150 else 0,
            "served_qty": 1 if day < 150 else 0,
            "required_with_backlog_qty": 1 if day < 150 else 0,
            "backlog_end_qty": 0,
        }
        for day in range(720)
    ]
    _write_csv(data / "production_demand_service_daily.csv", demand_rows)
    _write_csv(
        data / "production_output_products_daily.csv",
        [
            {
                "day": day,
                "node_id": "FAC-1",
                "item_id": "268091",
                "released_qty": 1,
            }
            for day in range(720)
        ],
    )
    _write_csv(
        data / "production_input_stocks_daily.csv",
        [
            {
                "day": day,
                "node_id": "FAC-1",
                "item_id": "item:C1",
                "stock_end_of_day": 1,
            }
            for day in range(720)
        ],
    )
    _write_csv(
        data / "production_factory_nervousness.csv",
        [
            {
                "node_id": "FAC-1",
                "output_item_id": "268091",
                "actual_churn_ratio": "",
                "production_start_count": "",
                "production_stop_count": "",
                "delay_day_count": "",
                "nervousness_level": "not_measured",
            }
        ],
    )
    ledger_rows = []
    for source_line, day in enumerate(range(2, 44), start=2):
        ledger_rows.append(
            {
                "source_line": source_line,
                "day": day,
                "action": "lead_time_adjustment_days",
                "source_supplier_id": "SUP-1",
                "source_item_id": "item:C1",
                "source_dst_node_id": "FAC-1",
                "effective": -14,
                "action_stage": "supplier_lane_execution",
                "status": "applied" if day == 2 else "resolved_no_flow",
                "executed_control_volume_qty": 10 if day == 2 else 0,
                "quantity_uom": "UN",
            }
        )
    _write_csv(data / "canonical_action_ledger.csv", ledger_rows)
    return SimpleNamespace(returncode=0, stdout="synthetic", stderr="")


def test_signed_reference_plan_executes_only_action_arms(tmp_path: Path) -> None:
    campaign, results = _upgrade_fixture_for_actions(tmp_path)
    root = tmp_path / "actions"
    plan = actions.create_action_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )

    assert plan["scientific_contract"]["reference_engine_reruns"] == 0
    assert plan["scientific_contract"]["only_action_arms_execute_the_engine"] is True
    assert plan["measurement_windows"]["state"] == {
        "metric_ids": [
            "state_window_service_gain_pp",
            "backlog_qty_days_avoided",
            "production_released_gain_qty",
        ],
        "start_day": 0,
        "end_day": 719,
        "day_count": 720,
    }
    assert plan["measurement_windows"]["impact_service"]["day_count"] == 360
    assert {
        (row["seed"], row["start_day"], row["end_day"], row["day_count"])
        for row in plan["measurement_windows"]["impact_service"]["ranges"]
    } == {(101, 2, 361, 360), (102, 2, 361, 360), (103, 2, 361, 360)}
    dossier = plan["dossiers"][0]
    assert dossier["eligible_action_ids"] == [actions.ACTION_LEAD]
    assert all(
        set(seed_plan["arms"]) == {actions.ACTION_LEAD}
        for seed_plan in dossier["seed_plans"]
    )
    assert all(
        "--lot-trace" not in arm["command"]
        for seed_plan in dossier["seed_plans"]
        for arm in seed_plan["arms"].values()
    )
    assert {
        row["action_id"] for row in dossier["action_catalog"] if not row["eligible"]
    } >= {
        actions.ACTION_STOCK,
        actions.ACTION_REALLOCATION,
        "identified_shipment_expedite",
        "new_supplier_or_capacity_creation",
        "targeted_closed_loop_regulation",
    }

    pending = actions.run_action_replay(root)
    assert pending["status"] == "validated_not_executed"
    assert pending["reference_engine_rerun_count"] == 0
    assert pending["planned_arm_count"] == 3


def test_synthetic_action_run_finalizes_null_unmeasured_kpis_and_is_idempotent(
    tmp_path: Path,
) -> None:
    campaign, results = _upgrade_fixture_for_actions(tmp_path)
    root = tmp_path / "actions"
    plan = actions.create_action_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )

    receipt = actions.run_action_replay(
        root,
        execute=True,
        executor=lambda command, run_dir: _write_action_run(command, run_dir, plan),
    )
    assert receipt["status"] == "complete_validated"
    assert receipt["reference_engine_rerun_count"] == 0
    assert receipt["executed_action_arm_count"] == 3
    summary, validation = actions.finalize_action_replay(
        root, bootstrap_replicates=1_000, bootstrap_seed=17
    )
    assert summary["measurement_windows"] == plan["measurement_windows"]
    assert validation["measurement_windows"] == plan["measurement_windows"]
    assert validation["checks"]["only_incident_with_action_arms_executed"] is True
    assert validation["checks"]["signed_reference_triplets_paired_by_seed"] is True
    assert validation["checks"]["reference_engine_rerun_count"] == 0
    result = summary["action_results"][0]
    assert result["status"] == "estimated_on_physically_exercised_seeds"
    assert result["physically_exercised_seed_count"] == 3
    assert result["gain_statistics"]["service_gain_pp"]["count"] == 3
    assert "model_total_cost_delta" not in result["gain_statistics"]
    assert summary["unavailable_reference_curve_kpis"] == {
        "component_stock_delta": None,
        "nervousness_delta": None,
        "equal_volume_recovery_days": None,
        "reason": (
            "les courbes quotidiennes baseline/incident ne sont pas stockées "
            "dans les références compactes signées"
        ),
    }
    actions.validate_action_results(root)

    receipt_hash = actions.sha256_file(root / "action_replay_run_receipt.json")
    summary_hash = actions.sha256_file(root / "action_replay_summary.json")
    validation_hash = actions.sha256_file(root / "action_replay_validation.json")
    assert actions.run_action_replay(root, execute=True) == receipt
    assert actions.finalize_action_replay(
        root, bootstrap_replicates=1_000, bootstrap_seed=17
    ) == (summary, validation)
    assert actions.sha256_file(root / "action_replay_run_receipt.json") == receipt_hash
    assert actions.sha256_file(root / "action_replay_summary.json") == summary_hash
    assert (
        actions.sha256_file(root / "action_replay_validation.json") == validation_hash
    )


def test_interrupted_partial_action_arm_is_archived_then_replayed(
    tmp_path: Path,
) -> None:
    campaign, results = _upgrade_fixture_for_actions(tmp_path)
    root = tmp_path / "actions"
    plan = actions.create_action_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )
    dossier = plan["dossiers"][0]
    seed_plan = dossier["seed_plans"][0]
    action_id = actions.ACTION_LEAD
    run_dir = Path(seed_plan["arms"][action_id]["run_dir"])
    partial_summary = run_dir / "summaries" / "first_simulation_summary.json"
    partial_summary.parent.mkdir(parents=True, exist_ok=True)
    partial_summary.write_text('{"partial": true}', encoding="utf-8")
    partial_sha = actions.sha256_file(partial_summary)
    executed: list[Path] = []

    def executor(command: list[str], target: Path) -> SimpleNamespace:
        executed.append(target.resolve())
        return _write_action_run(command, target, plan)

    receipt = actions.run_action_replay(
        root,
        execute=True,
        workers=1,
        executor=executor,
    )

    assert receipt["status"] == "complete_validated"
    assert run_dir.resolve() in executed
    archives = list((root / "recovery" / "partial_action_arms").iterdir())
    assert len(archives) == 1
    recovery = _read_json(archives[0] / "recovery_manifest.json")
    actions._verify_signed(
        recovery,
        "recovery_signature",
        "preuve de reprise du bras partiel",
    )
    assert recovery["original_run_dir"] == str(run_dir.resolve())
    assert recovery["dossier_id"] == dossier["dossier_id"]
    assert recovery["seed"] == seed_plan["seed"]
    assert recovery["arm_id"] == action_id
    assert recovery["pre_archive_files"] == [
        {
            "relative_path": "summaries/first_simulation_summary.json",
            "size_bytes": len('{"partial": true}'.encode("utf-8")),
            "sha256": partial_sha,
        }
    ]
    assert (archives[0] / "summaries" / "first_simulation_summary.json").is_file()
    actions.validate_run_arm(
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=action_id,
        arm=seed_plan["arms"][action_id],
    )


def test_native_application_ledgers_require_real_physical_effect(
    tmp_path: Path,
) -> None:
    stock_path = tmp_path / "stock.csv"
    action_ledger = tmp_path / "ledger.csv"
    dossier = {
        "priority": {
            "supplier_id": "SUP-1",
            "item_id": "item:C1",
            "dst_node_id": "FAC-1",
        },
        "action_catalog": [
            {
                "action_id": actions.ACTION_STOCK,
                "parameters": {"measurement_start_stock_scale": 1.25},
            },
            {
                "action_id": actions.ACTION_LEAD,
                "parameters": {"lead_time_adjustment_days": -14},
            },
            {
                "action_id": actions.ACTION_REALLOCATION,
                "physical_scope": {"active_alternatives": [{"supplier_id": "SUP-2"}]},
            },
        ],
    }
    seed_plan = {"risk_start_day": 2, "risk_end_day": 43}

    _write_csv(
        stock_path,
        [
            {
                "node_id": "FAC-1",
                "item_id": "item:C1",
                "scale": 1.25,
                "stock_before_qty": 40,
                "stock_added_qty": 10,
                "stock_after_qty": 50,
                "uom": "UN",
            }
        ],
    )
    stock = actions._action_application(
        files={"stock_adjustments": stock_path},
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=actions.ACTION_STOCK,
        arm={},
    )
    assert stock["physically_exercised"] is True
    assert stock["stock_before_j0_qty"] == 40
    assert stock["executed_quantity"] == 10
    assert stock["quantity_uom"] == "UN"
    assert stock["not_a_purchase_realized"] is True

    rows = _read_csv(stock_path)
    rows[0].update(
        {"stock_before_qty": "0", "stock_added_qty": "0", "stock_after_qty": "0"}
    )
    _write_csv(stock_path, rows)
    stock_zero = actions._action_application(
        files={"stock_adjustments": stock_path},
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=actions.ACTION_STOCK,
        arm={},
    )
    assert stock_zero["physically_exercised"] is False
    assert stock_zero["reason"] == "non_exercised_zero_j0_stock"

    lead_rows = [
        {
            "source_line": line,
            "day": day,
            "action": "lead_time_adjustment_days",
            "source_supplier_id": "SUP-1",
            "source_item_id": "item:C1",
            "source_dst_node_id": "FAC-1",
            "effective": -14,
            "action_stage": "supplier_lane_execution",
            "status": "applied" if day == 2 else "resolved_no_flow",
            "executed_control_volume_qty": 8 if day == 2 else 0,
            "quantity_uom": "UN",
        }
        for line, day in enumerate(range(2, 44), start=2)
    ]
    _write_csv(action_ledger, lead_rows)
    lead = actions._action_application(
        files={"action_ledger": action_ledger},
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=actions.ACTION_LEAD,
        arm={},
    )
    assert lead["physically_exercised"] is True
    assert lead["executed_quantity"] == 8
    assert lead["named_shipment_targeted"] is False

    reallocation_rows = [
        {
            "source_line": line,
            "day": day,
            "action": "priority_weight",
            "source_supplier_id": "SUP-1",
            "source_item_id": "item:C1",
            "source_dst_node_id": "FAC-1",
            "action_stage": "supplier_allocation_priority",
            "status": "applied" if day == 2 else "resolved_no_flow",
            "q_before_priority_allocation_qty": 20 if day == 2 else 0,
            "q_after_priority_allocation_qty": 12 if day == 2 else 0,
            "quantity_uom": "UN",
        }
        for line, day in enumerate(range(2, 44), start=2)
    ]
    _write_csv(action_ledger, reallocation_rows)
    reallocation = actions._action_application(
        files={"action_ledger": action_ledger},
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=actions.ACTION_REALLOCATION,
        arm={},
    )
    assert reallocation["physically_exercised"] is True
    assert reallocation["quantity_shifted_away_from_incident_lane"] == 8
    assert reallocation["eligible_alternative_supplier_ids"] == ["SUP-2"]


def test_lead_effect_is_bounded_and_shipment_id_is_not_an_actuator() -> None:
    dossier = {
        "priority": {
            "supplier_id": "SUP-1",
            "item_id": "item:C1",
            "dst_node_id": "FAC-1",
            "edge_id": "EDGE-1",
        },
        "action_catalog": [
            {
                "action_id": actions.ACTION_LEAD,
                "parameters": {"lead_time_adjustment_days": -14},
            }
        ],
    }
    common = {
        "shipment_id": "S1",
        "risk_decision_day": 2,
        "src_node_id": "SUP-1",
        "item_id": "item:C1",
        "dst_node_id": "FAC-1",
        "edge_id": "EDGE-1",
    }
    proof = actions._lead_effect_evidence(
        incident_shipments=[
            {**common, "pulled_qty": 10, "shipped_qty": 10, "lead_days": 121}
        ],
        action_shipments=[
            {
                **common,
                "pulled_qty": "10.000000",
                "shipped_qty": "10.0",
                "lead_days": 107,
            }
        ],
        dossier=dossier,
        seed_plan={"risk_start_day": 2, "risk_end_day": 43},
    )
    assert proof["bounded_effect_proven"] is True
    assert proof["maximum_observed_lead_reduction_days"] == 14
    assert (
        proof["comparison_uses_shipment_id_only_as_crn_diagnostic_not_as_actuator"]
        is True
    )


def test_plan_rejects_injected_reference_arm(tmp_path: Path) -> None:
    campaign, results = _upgrade_fixture_for_actions(tmp_path)
    root = tmp_path / "actions"
    plan = actions.create_action_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )
    plan_path = root / "action_replay_plan.json"
    plan = _read_json(plan_path)
    plan.pop("plan_signature")
    seed_plan = plan["dossiers"][0]["seed_plans"][0]
    seed_plan["arms"]["baseline"] = dict(seed_plan["arms"][actions.ACTION_LEAD])
    plan = _sign(plan, "plan_signature")
    _write_json(plan_path, plan)

    with pytest.raises(actions.ActionReplayError, match="Seuls les bras actions"):
        actions.load_and_validate_plan(root)


def test_plan_rejects_a_signed_but_mislabelled_measurement_window(
    tmp_path: Path,
) -> None:
    campaign, results = _upgrade_fixture_for_actions(tmp_path)
    root = tmp_path / "actions"
    actions.create_action_plan(
        campaign_root=campaign,
        results_dir=results,
        output_root=root,
        max_dossiers=1,
    )
    plan_path = root / "action_replay_plan.json"
    plan = _read_json(plan_path)
    plan.pop("plan_signature")
    plan["measurement_windows"]["state"]["end_day"] = 718
    _write_json(plan_path, _sign(plan, "plan_signature"))

    with pytest.raises(actions.ActionReplayError, match="fenêtres KPI actions"):
        actions.load_and_validate_plan(root)
