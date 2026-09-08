from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_post_priority_extension_runner as runner,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_post_priority_extensions as planner,
)
from etudecas.prototypes.scan_2027_risk_control import (
    industrial_supply_bilan_dashboard as industrial_dashboard,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_network_post_priority_extensions import (
    _read_csv,
    _source_artifact,
    _write_csv,
    _write_json,
)


def _runner_fixture(
    tmp_path: Path,
    *,
    prune_source_baseline_data: bool = False,
) -> tuple[Path, Path, Path, Path, Path]:
    source = _source_artifact(tmp_path)
    if prune_source_baseline_data:
        baseline_root = source / "cases" / "baseline_nominal"
        for data_dir in baseline_root.glob("seed_*/data"):
            shutil.rmtree(data_dir)
    graph = tmp_path / "graph.json"
    engine = tmp_path / "engine.py"
    profile = tmp_path / "profile.json"
    lane_rows = _read_csv(source / "active_lane_reference.csv")
    graph.write_text(
        json.dumps(
            {
                "nodes": [],
                "edges": [
                    {
                        "id": row["edge_id"],
                        "from": row["supplier_id"],
                        "to": row["dst_node_id"],
                        "items": [row["item_id"]],
                        "order_terms": {"quantity_unit": "KG"},
                    }
                    for row in lane_rows
                ],
            }
        ),
        encoding="utf-8",
    )
    engine.write_text("# fake engine file used only for its hash\n", encoding="utf-8")
    profile.write_text(json.dumps({"args": []}), encoding="utf-8")

    metric_path = source / "confirmation_metrics.csv"
    metrics = _read_csv(metric_path)
    scenario_by_id = {
        row["scenario_id"]: row
        for row in _read_csv(source / "scenario_design.csv")
    }
    for row in metrics:
        row["resolved_lot_trace_enabled"] = row[
            "lot_trace_required_for_paired_seed_block"
        ]
        row.update(
            {
                "demand_qty_268091": 1000,
                "fill_rate_268091": 1,
                "on_due_volume_proxy_268091": 0.99,
                "backlog_qty_days_268091": 0,
                "backlog_end_qty_268091": 0,
                "demand_qty_268967": 1000,
                "fill_rate_268967": 1,
                "on_due_volume_proxy_268967": 0.99,
                "backlog_qty_days_268967": 0,
                "backlog_end_qty_268967": 0,
                "target_released_qty": 1000,
                "target_product_uom": "UN",
                "component_stock_uom": "KG",
                "active_window_pulled_qty": 100,
                "active_window_shipped_qty": 100,
            }
        )
        if row["scenario_id"] != "baseline_nominal":
            design = scenario_by_id[row["scenario_id"]]
            event_id = f"{row['scenario_id']}__lane1"
            risk_path = source / "inputs" / "risk_events" / f"{row['scenario_id']}.csv"
            risk_rows = [
                {
                    "event_id": event_id,
                    "risk_type": runner.network.MECHANISM_BY_KEY[
                        design["failure_mode"]
                    ].risk_type,
                    "supplier_id": design["supplier_id"],
                    "item_id": design["item_id"],
                    "dst_node_id": design["dst_node_id"],
                    # The real main campaign intentionally leaves this blank:
                    # supplier/item/destination are its targeting contract.
                    "edge_id": "",
                    "start_day": row["stress_start_day"],
                    "end_day": row["stress_end_day"],
                    "multiplier": design["mechanism_value"],
                    "notes": "fixture source retained case",
                }
            ]
            _write_csv(risk_path, risk_rows)
            _write_json(
                Path(row["run_dir"])
                / "summaries"
                / "first_simulation_summary.json",
                {
                    "input_sha256": "graph-hash",
                    "sim_days": 720,
                    "policy": {
                        "supplier_risk": {
                            "events_csv": str(risk_path),
                            "events_csv_sha256": planner._sha256(risk_path),
                            "event_count": 1,
                            "warnings": [],
                        }
                    },
                    "production_tracking": {
                        "supplier_risk_events": risk_rows,
                        "supplier_risk_event_application_rows": 1,
                    },
                },
            )
            row.update(
                {
                    "configured_event_count": 1,
                    "loaded_event_count": 1,
                    "risk_applied_rows": 1,
                    "lot_expected_risk_event_ids": event_id,
                }
            )
    _write_csv(metric_path, metrics)

    floor_rows = [
        {
            "supplier_id": "SDC-VD0519670A",
            "item_id": "item:001848",
            "dst_node_id": "M-1810",
            "tested_capacity_floor_qty_per_day": 100,
        }
    ]
    floor_path = source / "inputs" / "prepared_physical_supplier_floors.csv"
    _write_csv(floor_path, floor_rows)
    manifest_path = source / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "graph_sha256": planner._sha256(graph),
            "engine_sha256": planner._sha256(engine),
            "profile_sha256": planner._sha256(profile),
            "v4_extraction_core_sha256": planner._sha256(
                Path(runner.network.campaign_core.__file__)
            ),
            "prepared_supplier_floor_content_sha256": (
                runner.network.campaign_core.campaign_signature(
                    {"rows": _read_csv(floor_path)}
                )
            ),
        }
    )
    _write_json(manifest_path, manifest)
    plan = planner.create_plan(
        network_artifact=source, output_dir=tmp_path / "signed_plan"
    )
    return source, plan, graph, engine, profile


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[runner.PlannedCase] = []

    def __call__(
        self,
        case: runner.PlannedCase,
        context: runner.RunnerContext,
        risk_csv: Path | None,
    ) -> runner.CaseEvidence:
        self.calls.append(case)
        run_dir = ""
        event_ids = []
        if risk_csv is not None:
            event_ids = [row["event_id"] for row in _read_csv(risk_csv)]
        lot_events = []
        if case.extension == "baseline" and case.lot_trace_required:
            lot_events = [
                {
                    "event_type": "lane_receipt",
                    "lot_id": "BASE-LOT",
                    "node_id": "M-1810",
                    "item_id": "item:001848",
                    "shipment_id": "SHIP-STABLE",
                    "day": 10,
                    "qty": 100,
                    "uom": "KG",
                }
            ]
        elif case.extension == "causal_lot_attribution_subset":
            lane = case.lanes[0]
            lot_events = [
                {
                    "event_type": "lane_receipt",
                    "lot_id": "STRESS-LOT",
                    "node_id": lane.dst_node_id,
                    "item_id": lane.item_id,
                    "supplier_id": lane.supplier_id,
                    "shipment_id": "SHIP-STABLE",
                    "day": 12,
                    "qty": 90,
                    "uom": "KG",
                    "risk_event_ids": "|".join(event_ids),
                }
            ]
        if case.extension == "baseline":
            baseline_run = (
                context.output_dir
                / "fake_engine_cases"
                / case.case_id
                / f"seed_{case.seed}"
            )
            lanes = _read_csv(context.source_dir / "active_lane_reference.csv")
            shipment_rows = [
                {
                    "day": day,
                    "src_node_id": lane["supplier_id"],
                    "item_id": lane["item_id"],
                    "dst_node_id": lane["dst_node_id"],
                    "uom": "KG",
                    "pulled_qty": 10,
                    "shipped_qty": 10,
                }
                for lane in lanes
                for day in range(0, case.simulation_days, 15)
            ]
            _write_csv(
                baseline_run / "data" / "production_supplier_shipments_daily.csv",
                shipment_rows,
            )
            run_dir = str(baseline_run)
        product_metrics = [
            {
                "product_id": product,
                "uom": "UN",
                "demand_qty": 1000,
                "fill_rate": 0.98,
                "on_due_ratio": 0.97,
                "backlog_qty_days": 10,
                "backlog_end_qty": 0,
                "released_qty": 990,
            }
            for product in runner.PRODUCTS
        ]
        local_products = (
            runner.PRODUCTS if case.extension == "baseline" else case.products
        )
        local_metrics = [
            {
                "outcome_spec_id": str(spec["outcome_spec_id"]),
                "outcome_start_day": int(spec["outcome_start_day"]),
                "outcome_end_day": int(spec["outcome_end_day"]),
                "outcome_day_count": int(spec["outcome_day_count"]),
                "product_id": product,
                "uom": "UN",
                "demand_qty_denominator": 1000.0,
                "required_qty_denominator": 1000.0,
                "served_qty_numerator": 980.0,
                "fill_rate": 0.98,
                "served_on_due_qty_numerator": 970.0,
                "on_due_ratio": 0.97,
                "backlog_qty_days_numerator": 10.0,
                "normalized_backlog_days_per_demand_unit": 0.01,
                "backlog_end_qty": 0.0,
                "released_qty_numerator": 990.0,
                "series_day_count": int(spec["outcome_day_count"]),
                "series_complete": True,
                "recovery_metric_status": "excluded_not_redefined",
            }
            for spec in runner._case_outcome_specs(case)
            for product in local_products
        ]
        snapshots = []
        snapshot_specs = (
            runner._case_outcome_specs(case)
            if case.extension == "baseline"
            or (
                case.extension == "temporal_robustness"
                and case.outcome_spec_id != "full_horizon_J0_J719"
            )
            else ()
        )
        for spec in snapshot_specs:
            if "incident_start_day" not in spec:
                continue
            start = int(spec["incident_start_day"])
            payload = {
                "fixture_seed": case.seed,
                "outcome_spec_id": str(spec["outcome_spec_id"]),
                "snapshot_day": start - 1,
            }
            snapshots.append(
                {
                    "outcome_spec_id": str(spec["outcome_spec_id"]),
                    "incident_start_day": start,
                    "snapshot_day": start - 1,
                    "payload": payload,
                    "preincident_state_sha256": planner._canonical_signature(payload),
                }
            )
        loaded_rows = (
            [runner._normalized_risk_row(row) for row in _read_csv(risk_csv)]
            if risk_csv is not None
            else []
        )
        return runner.CaseEvidence(
            case_key=case.case_key,
            seed=case.seed,
            status="executed_by_fake",
            input_sha256="graph-hash",
            j0_state_sha256=f"j0-{case.seed}",
            resolved_lot_trace_enabled=case.lot_trace_required,
            valid=True,
            validation_errors=[],
            product_metrics=product_metrics,
            flow_metrics=[
                {
                    "chain_id": lane.chain_id,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "uom": "KG",
                    "pulled_qty": 100,
                    "shipped_qty": 90,
                }
                for lane in case.lanes
            ],
            applied_event_ids=event_ids,
            lot_events=lot_events,
            lot_genealogy=[],
            run_dir=run_dir,
            simulation_days=case.simulation_days,
            outcome_bundle_sha256=case.outcome_bundle_sha256,
            local_product_metrics=local_metrics,
            preincident_state_snapshots=snapshots,
            configured_event_ids=event_ids,
            loaded_event_rows=loaded_rows,
            risk_input_sha256=(planner._sha256(risk_csv) if risk_csv else ""),
            risk_application_rows=[{"event_ids": value} for value in event_ids],
            post_J719_extrapolation_policy=(
                planner.EXTENDED_HORIZON_INPUT_POLICY
                if case.simulation_days > planner.BASE_SIMULATION_DAYS
                else "not_applicable_fixed_J0_J719"
            ),
        )


def test_direct_runner_help_works_from_repository_root():
    script = Path(runner.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[3],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--mode" in completed.stdout
    assert "--plan-dir" in completed.stdout


def test_full_mode_refuses_custom_executor_before_creating_output(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    output = tmp_path / "forbidden_full_custom"
    with pytest.raises(ValueError, match="exécuteur moteur intégré"):
        runner.run_extensions(
            plan_dir=plan,
            mode="full",
            output_dir=output,
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=FakeExecutor(),
        )
    assert not output.exists()


def test_runner_refuses_execution_scenario_different_from_signed_plan(
    tmp_path: Path,
):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    output = tmp_path / "wrong_scenario"
    with pytest.raises(ValueError, match="Scénario d'exécution incompatible"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=output,
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            scenario_id="scn:OTHER",
            case_executor=FakeExecutor(),
        )
    assert not output.exists()


def test_smoke_executes_only_new_cases_and_references_exact_source_cases(
    tmp_path: Path,
):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    fake = FakeExecutor()
    output = tmp_path / "runner_smoke"
    result = runner.run_extensions(
        plan_dir=plan,
        mode="smoke",
        output_dir=output,
        graph_path=graph,
        engine_path=engine,
        profile_path=profile,
        workers=2,
        case_executor=fake,
    )
    assert result["status"] == "complete"
    assert fake.calls
    assert all(case.action == "new_run_required" for case in fake.calls)
    reference_rows = _read_csv(output / "execution_case_reference.csv")
    action_by_key = {row["case_key"]: row["action"] for row in reference_rows}
    assert all(
        action_by_key[case.case_key]
        == (
            "materialize_runner_baseline"
            if case.extension == "baseline"
            else "new_run_required"
        )
        for case in fake.calls
    )
    assert any(action == "reuse_exact_source_case" for action in action_by_key.values())
    common_risk_files = list(
        (output / "inputs" / "risk_events" / "multi_lane_supplier_common_cause").rglob(
            "*.csv"
        )
    )
    assert len(common_risk_files) == 1
    assert len(_read_csv(common_risk_files[0])) == 2
    assert (output / "multi_lane_supplier_common_cause_manifest.json").is_file()
    assert (output / "temporal_robustness_manifest.json").is_file()
    assert (output / "priority_four_business_causes_manifest.json").is_file()
    assert (output / "causal_lot_attribution_manifest.json").is_file()
    causal_manifest = json.loads(
        (output / "causal_lot_attribution_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert causal_manifest["all_pairs_counterfactually_evaluated"] is False
    assert causal_manifest["counterfactual_entity_identity_validated"] is False
    assert causal_manifest["causal_lot_attribution_available"] is False
    assert not any("ranking" in path.name for path in output.iterdir())
    promotion = json.loads(
        (output / "promotion_controls.json").read_text(encoding="utf-8")
    )
    assert promotion["promotion_allowed"] is False


def test_identical_signature_resumes_without_reexecuting_cases(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    fake = FakeExecutor()
    output = tmp_path / "runner_smoke"
    kwargs = {
        "plan_dir": plan,
        "mode": "smoke",
        "output_dir": output,
        "graph_path": graph,
        "engine_path": engine,
        "profile_path": profile,
        "workers": 1,
        "case_executor": fake,
    }
    first = runner.run_extensions(**kwargs)
    first_call_count = len(fake.calls)
    second = runner.run_extensions(**kwargs)
    assert first["runner_signature"] == second["runner_signature"]
    assert len(fake.calls) == first_call_count


def test_summary_source_materializes_30_shared_baselines_and_aliases_causal_pair(
    tmp_path: Path,
):
    _source, plan, _graph, _engine, _profile = _runner_fixture(
        tmp_path,
        prune_source_baseline_data=True,
    )
    _manifest, baselines, stress = runner.load_signed_plan(plan)
    selected_baselines, selected_stress = runner._selected_cases(
        "full", baselines, stress
    )
    owners, owner_by_case = runner._baseline_materialization_plan(
        selected_baselines
    )
    assert len(selected_baselines) == 31
    assert len(owners) == 30
    assert len(set(owner_by_case.values())) == 30
    assert sum(case.action == "new_run_required" for case in selected_stress) == 780
    assert len(owners) + sum(
        case.action == "new_run_required" for case in selected_stress
    ) == 810
    causal_baseline = next(
        case
        for case in selected_baselines
        if case.case_id.startswith("baseline_causal_lot")
    )
    metric_baseline = next(
        case
        for case in selected_baselines
        if case.seed == causal_baseline.seed
        and case.case_id.startswith("baseline_metrics")
    )
    assert owner_by_case[causal_baseline.case_key] == metric_baseline.case_key


def test_baseline_fingerprint_never_aliases_different_horizons_or_outcomes(
    tmp_path: Path,
):
    _source, plan, _graph, _engine, _profile = _runner_fixture(tmp_path)
    _manifest, baselines, _stress = runner.load_signed_plan(plan)
    base = baselines[0]
    same = replace(
        base,
        case_key=f"{base.case_key}::alias",
        case_id=f"{base.case_id}__alias",
    )
    extended = replace(
        base,
        case_key=f"{base.case_key}::extended",
        case_id=f"{base.case_id}__extended",
        simulation_days=1063,
        outcome_end_day=1062,
        outcome_day_count=1063,
        outcome_bundle_sha256="different-outcome-bundle",
    )
    owners, owner_by_case = runner._baseline_materialization_plan(
        [base, same, extended]
    )
    assert len(owners) == 2
    assert owner_by_case[same.case_key] == owner_by_case[base.case_key]
    assert owner_by_case[extended.case_key] != owner_by_case[base.case_key]


def _checkpoint_case(
    *,
    extension: str,
    case_id: str,
    seed: int,
    action: str = "new_run_required",
) -> runner.PlannedCase:
    return runner.PlannedCase(
        case_key=f"{extension}::{case_id}::seed_{seed}",
        extension=extension,
        case_id=case_id,
        seed=seed,
        pairing_block_id=f"block_{seed}",
        paired_baseline_case_id=f"baseline_{seed}",
        mechanism_key=("baseline" if extension == "baseline" else "transport_delay"),
        risk_type=("" if extension == "baseline" else "lead_time_extra_days"),
        mechanism_value=(1.0 if extension == "baseline" else 120.0),
        mechanism_unit=("ratio" if extension == "baseline" else "jours_ajoutes"),
        start_day=0,
        end_day=0,
        lot_trace_required=False,
        lanes=(),
        products=("268091",),
        action=action,
        outcome_bundle_sha256="outcome",
    )


def test_full_checkpoint_uses_a_cumulative_signed_seed_prefix():
    seeds = tuple(range(340282, 340312))
    stress = [
        _checkpoint_case(extension=extension, case_id=f"{extension}_case", seed=seed)
        for extension in (
            "multi_lane_supplier_common_cause",
            "temporal_robustness",
            "priority_four_business_causes",
        )
        for seed in seeds
    ]
    stress.append(
        _checkpoint_case(
            extension="causal_lot_attribution_subset",
            case_id="lot_case",
            seed=seeds[0],
            action="reuse_exact_source_case",
        )
    )
    signed = runner._signed_full_seed_ids(
        plan_manifest={"confirmation_seeds": list(seeds)},
        stress_cases=stress,
    )
    first_half, is_checkpoint = runner._execution_seed_target(
        mode="full",
        signed_seed_ids=signed,
        checkpoint_after_repetitions=15,
    )
    full, is_full = runner._execution_seed_target(
        mode="full",
        signed_seed_ids=signed,
        checkpoint_after_repetitions=None,
    )
    assert first_half == seeds[:15]
    assert is_checkpoint is True
    assert full == seeds
    assert is_full is False
    with pytest.raises(ValueError, match="exactement 15"):
        runner._execution_seed_target(
            mode="full",
            signed_seed_ids=signed,
            checkpoint_after_repetitions=14,
        )
    with pytest.raises(ValueError, match="Matrice signée incomplète"):
        runner._signed_full_seed_ids(
            plan_manifest={"confirmation_seeds": list(seeds)},
            stress_cases=[
                case
                for case in stress
                if not (
                    case.extension == "temporal_robustness"
                    and case.seed == seeds[-1]
                )
            ],
        )


def test_preliminary_checkpoint_is_exact_hashed_and_non_promotable(tmp_path: Path):
    seeds = tuple(range(340282, 340312))
    completed = seeds[:15]
    baseline_rows = [
        _checkpoint_case(
            extension="baseline",
            case_id=f"baseline_{horizon}_{seed}",
            seed=seed,
        )
        for seed in completed
        for horizon in (720, 1063)
    ]
    baseline_rows.append(
        replace(
            baseline_rows[0],
            case_key=f"{baseline_rows[0].case_key}::logical_lot_alias",
            case_id=f"{baseline_rows[0].case_id}__logical_lot_alias",
        )
    )
    owners = baseline_rows[:30]
    stress: list[runner.PlannedCase] = []
    stress.extend(
        _checkpoint_case(
            extension="multi_lane_supplier_common_cause",
            case_id=f"common_{case_index}",
            seed=seed,
        )
        for case_index in range(8)
        for seed in completed
    )
    stress.extend(
        _checkpoint_case(
            extension="temporal_robustness",
            case_id=f"temporal_{case_index}",
            seed=seed,
        )
        for case_index in range(16)
        for seed in completed
    )
    stress.extend(
        _checkpoint_case(
            extension="priority_four_business_causes",
            case_id=f"cause_{case_index}",
            seed=seed,
            action=(
                "reuse_exact_source_case" if case_index < 8 else "new_run_required"
            ),
        )
        for case_index in range(16)
        for seed in completed
    )
    stress.extend(
        _checkpoint_case(
            extension="causal_lot_attribution_subset",
            case_id=f"lot_{case_index}",
            seed=completed[0],
            action="reuse_exact_source_case",
        )
        for case_index in range(4)
    )
    evidence_by_key: dict[str, runner.CaseEvidence] = {}
    case_files: dict[str, str] = {}
    case_hashes: dict[str, str] = {}
    for case in [*owners, *stress]:
        evidence = runner.CaseEvidence(
            case_key=case.case_key,
            seed=case.seed,
            status=(
                "reused_exact_source_case"
                if case.action == "reuse_exact_source_case"
                else "complete"
            ),
            input_sha256="input",
            j0_state_sha256="j0",
            resolved_lot_trace_enabled=case.lot_trace_required,
            valid=True,
            validation_errors=[],
            product_metrics=[],
            flow_metrics=[],
            applied_event_ids=[],
            lot_events=[],
            lot_genealogy=[],
            reused_source_case=case.action == "reuse_exact_source_case",
        )
        evidence_by_key[case.case_key] = evidence
        relative = runner._canonical_ledger_relative_path(case.case_key)
        _write_json(tmp_path / relative, {"case_key": case.case_key})
        case_files[case.case_key] = relative.as_posix()
        case_hashes[case.case_key] = planner._sha256(tmp_path / relative)
    _write_json(
        tmp_path / runner.LEDGER_FILE,
        {
            "runner_signature": "runner-signature",
            "case_files": case_files,
            "case_file_sha256": case_hashes,
        },
    )
    ledger_hash = planner._sha256(tmp_path / runner.LEDGER_FILE)
    plan_manifest = {
        "plan_signature": "plan-signature",
        "priority_selection_lineage_sha256": "lineage",
        "planned_case_counts": {"expected_engine_physical_run_count": 1020},
    }
    checkpoint = runner._write_preliminary_checkpoint(
        output_dir=tmp_path,
        runner_signature="runner-signature",
        plan_manifest=plan_manifest,
        plan_manifest_sha256="plan-manifest-hash",
        signed_seed_ids=seeds,
        completed_seed_ids=completed,
        selected_baselines=baseline_rows,
        selected_stress=stress,
        baseline_owners=owners,
        evidence_by_case_key=evidence_by_key,
        case_files=case_files,
        case_file_hashes=case_hashes,
        ledger_sha256=ledger_hash,
    )
    assert checkpoint["status"] == "paused_preliminary"
    assert checkpoint["executed_engine_physical_run_count"] == 510
    assert checkpoint["ledger_evidence_case_count"] == 634
    assert checkpoint["promotion_allowed"] is False
    assert checkpoint["canonical_results_written"] is False
    assert (
        runner._validate_preliminary_checkpoint(
            output_dir=tmp_path,
            runner_signature="runner-signature",
            plan_manifest_sha256="plan-manifest-hash",
            expected_signed_seed_ids=seeds,
            expected_evidence_keys=set(evidence_by_key),
        )["checkpoint_signature"]
        == checkpoint["checkpoint_signature"]
    )
    checkpoint_path = tmp_path / runner.PRELIMINARY_CHECKPOINT_MANIFEST
    original_checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
    forged = json.loads(original_checkpoint_text)
    forged_key = next(iter(forged["case_evidence_file_sha256"]))
    forged["case_evidence_file_sha256"][forged_key]["relative_path"] = (
        "../outside.json"
    )
    forged.pop("checkpoint_signature")
    forged["checkpoint_signature"] = runner.network.campaign_core.campaign_signature(
        forged
    )
    _write_json(checkpoint_path, forged)
    with pytest.raises(RuntimeError, match="non canonique"):
        runner._validate_preliminary_checkpoint(
            output_dir=tmp_path,
            runner_signature="runner-signature",
            plan_manifest_sha256="plan-manifest-hash",
            expected_signed_seed_ids=seeds,
            expected_evidence_keys=set(evidence_by_key),
        )
    checkpoint_path.write_text(original_checkpoint_text, encoding="utf-8")
    ledger_path = tmp_path / runner.LEDGER_FILE
    original_ledger_text = ledger_path.read_text(encoding="utf-8")
    incomplete_ledger = json.loads(original_ledger_text)
    removed_key = next(iter(incomplete_ledger["case_files"]))
    incomplete_ledger["case_files"].pop(removed_key)
    incomplete_ledger["case_file_sha256"].pop(removed_key)
    _write_json(ledger_path, incomplete_ledger)
    with pytest.raises(RuntimeError, match="sous-ensemble exact"):
        runner._validate_preliminary_checkpoint(
            output_dir=tmp_path,
            runner_signature="runner-signature",
            plan_manifest_sha256="plan-manifest-hash",
            expected_signed_seed_ids=seeds,
            expected_evidence_keys=set(evidence_by_key),
        )
    ledger_path.write_text(original_ledger_text, encoding="utf-8")
    tampered = tmp_path / case_files[next(iter(case_files))]
    tampered.write_text(tampered.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="altérée"):
        runner._validate_preliminary_checkpoint(
            output_dir=tmp_path,
            runner_signature="runner-signature",
            plan_manifest_sha256="plan-manifest-hash",
            expected_signed_seed_ids=seeds,
            expected_evidence_keys=set(evidence_by_key),
        )


def test_process_liveness_probe_does_not_terminate_a_live_child():
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        creationflags=(
            subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        ),
    )
    try:
        assert runner._process_is_running(child.pid) is True
        assert child.poll() is None
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=10)
    assert runner._process_is_running(child.pid) is False


def test_flow_output_uses_loaded_source_event_id_instead_of_synthetic_id():
    lane = runner.LaneSpec(
        chain_id="chain",
        supplier_id="SUP",
        item_id="item:X",
        dst_node_id="M",
        edge_id="edge:X",
        target_product_id="268091",
    )
    case = runner.PlannedCase(
        case_key="priority_four_business_causes::case::seed_1",
        extension="priority_four_business_causes",
        case_id="new-case-id",
        seed=1,
        pairing_block_id="metrics_seed_1",
        paired_baseline_case_id="baseline_metrics__seed_1",
        mechanism_key="transport_delay",
        risk_type="lead_time",
        mechanism_value=120,
        mechanism_unit="days",
        start_day=45,
        end_day=224,
        lot_trace_required=False,
        lanes=(lane,),
        products=("268091",),
        action="reuse_exact_source_case",
    )
    evidence = runner.CaseEvidence(
        case_key=case.case_key,
        seed=1,
        status="reused_exact_source_case",
        input_sha256="graph",
        j0_state_sha256="j0",
        resolved_lot_trace_enabled=False,
        valid=True,
        validation_errors=[],
        product_metrics=[],
        flow_metrics=[
            {
                "chain_id": "chain",
                "supplier_id": "SUP",
                "item_id": "item:X",
                "dst_node_id": "M",
                "uom": "KG",
                "pulled_qty": 10,
                "shipped_qty": 9,
            }
        ],
        applied_event_ids=["source-event-id"],
        lot_events=[],
        lot_genealogy=[],
        loaded_event_rows=[
            {
                "event_id": "source-event-id",
                "supplier_id": "SUP",
                "item_id": "item:X",
                "dst_node_id": "M",
            }
        ],
    )
    rows = runner._flow_rows(
        case=case,
        evidence=evidence,
        baseline_flow=[
            {
                "chain_id": "chain",
                "supplier_id": "SUP",
                "item_id": "item:X",
                "dst_node_id": "M",
                "uom": "KG",
                "pulled_qty": 10,
                "shipped_qty": 10,
            }
        ],
    )
    assert rows[0]["risk_event_applied_on_lane"] is True


def test_risk_event_parser_supports_comma_and_rejects_duplicate_token():
    assert runner._risk_event_tokens([{"event_ids": "A,B|C"}]) == ["A", "B", "C"]
    assert runner._tokens("A,B|C;D") == {"A", "B", "C", "D"}
    with pytest.raises(ValueError, match="dupliqu"):
        runner._risk_event_tokens([{"event_ids": "A,B,A"}])


def test_reused_source_empty_edge_resolves_only_on_unique_locked_graph_edge():
    row = {
        "event_id": "SOURCE-EVENT",
        "risk_type": "lead_time_extra_days",
        "supplier_id": "SUP",
        "item_id": "item:X",
        "dst_node_id": "M",
        "edge_id": "",
        "start_day": 1,
        "end_day": 2,
        "multiplier": 120,
        "notes": "source",
    }
    unique_graph = {
        "edges": [
            {
                "id": "edge:EXPECTED",
                "from": "SUP",
                "to": "M",
                "items": ["item:X"],
            }
        ]
    }
    resolved, errors = runner._resolve_reused_source_risk_edges(
        [row], unique_graph
    )
    assert errors == []
    assert resolved[0]["edge_id"] == "edge:EXPECTED"

    ambiguous_graph = {
        "edges": [
            *unique_graph["edges"],
            {
                "id": "edge:OTHER",
                "from": "SUP",
                "to": "M",
                "items": ["item:X"],
            },
        ]
    }
    unresolved, errors = runner._resolve_reused_source_risk_edges(
        [row], ambiguous_graph
    )
    assert unresolved[0]["edge_id"] == ""
    assert errors and "non résolue de façon unique" in errors[0]


def test_reused_source_explicit_wrong_edge_is_rejected():
    row = {
        "supplier_id": "SUP",
        "item_id": "item:X",
        "dst_node_id": "M",
        "edge_id": "edge:WRONG",
    }
    graph = {
        "edges": [
            {
                "id": "edge:EXPECTED",
                "from": "SUP",
                "to": "M",
                "items": ["item:X"],
            }
        ]
    }
    resolved, errors = runner._resolve_reused_source_risk_edges([row], graph)
    assert resolved[0]["edge_id"] == "edge:WRONG"
    assert errors and "hors du triplet planifié" in errors[0]


def test_summary_source_smoke_persists_compact_flows_and_resumes_after_pruning(
    tmp_path: Path,
):
    _source, plan, graph, engine, profile = _runner_fixture(
        tmp_path,
        prune_source_baseline_data=True,
    )
    fake = FakeExecutor()
    output = tmp_path / "runner_summary_smoke"
    kwargs = {
        "plan_dir": plan,
        "mode": "smoke",
        "output_dir": output,
        "graph_path": graph,
        "engine_path": engine,
        "profile_path": profile,
        "workers": 2,
        "case_executor": fake,
    }
    first = runner.run_extensions(**kwargs)
    baseline_calls = [case for case in fake.calls if case.extension == "baseline"]
    assert len(baseline_calls) == 1
    first_call_count = len(fake.calls)
    manifest = json.loads((output / runner.RUNNER_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["runner_generated_baseline_physical_run_count"] == 1
    assert manifest["runner_generated_baseline_alias_count"] == 1
    assert manifest["executed_baseline_physical_run_count"] == 1
    assert manifest["executed_engine_case_count"] == first["executed_engine_case_count"]
    ledger = json.loads((output / runner.LEDGER_FILE).read_text(encoding="utf-8"))
    assert set(ledger["case_files"]) == set(ledger["case_file_sha256"])
    baseline_key = next(
        key for key in ledger["case_files"] if key.startswith("baseline::")
    )
    baseline_evidence = json.loads(
        (output / ledger["case_files"][baseline_key]).read_text(encoding="utf-8")
    )
    assert baseline_evidence["flow_metrics"]
    assert all(
        "baseline_window_start_day" in row
        and "baseline_window_end_day" in row
        for row in baseline_evidence["flow_metrics"]
    )
    run_dir = Path(baseline_evidence["run_dir"])
    assert not (run_dir / "data").exists()
    second = runner.run_extensions(**kwargs)
    assert second["runner_signature"] == first["runner_signature"]
    assert len(fake.calls) == first_call_count


def test_materialized_baseline_without_daily_or_compact_flow_fails_closed(
    tmp_path: Path,
):
    _source, plan, graph, engine, profile = _runner_fixture(
        tmp_path,
        prune_source_baseline_data=True,
    )

    class MissingFlowExecutor(FakeExecutor):
        def __call__(self, case, context, risk_csv):
            evidence = super().__call__(case, context, risk_csv)
            if case.extension == "baseline":
                shutil.rmtree(Path(evidence.run_dir) / "data")
            return evidence

    with pytest.raises(FileNotFoundError, match="Flux quotidien absent"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=tmp_path / "runner_missing_baseline_flow",
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=MissingFlowExecutor(),
        )


def test_resume_rejects_tampered_case_evidence(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    output = tmp_path / "runner_tamper"
    kwargs = {
        "plan_dir": plan,
        "mode": "smoke",
        "output_dir": output,
        "graph_path": graph,
        "engine_path": engine,
        "profile_path": profile,
        "case_executor": FakeExecutor(),
    }
    runner.run_extensions(**kwargs)
    ledger = json.loads((output / runner.LEDGER_FILE).read_text(encoding="utf-8"))
    first_relative = next(iter(ledger["case_files"].values()))
    evidence_path = output / first_relative
    evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="Empreinte de preuve de reprise invalide"):
        runner.run_extensions(**kwargs)


def test_runner_rejects_tampered_retained_causal_evidence(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    causal_rows = _read_csv(plan / "causal_lot_attribution_design.csv")
    source_case = Path(causal_rows[0]["source_incident_case_key"])
    evidence_path = source_case / "data" / "production_lot_events.csv"
    evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Empreinte de preuve lot source invalide"):
        runner.run_extensions(
            plan_dir=plan,
            mode="plan",
            output_dir=tmp_path / "runner_bad_causal_provenance",
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
        )


def test_resume_with_different_signature_is_rejected(tmp_path: Path):
    class DifferentSmokeExecutor(FakeExecutor):
        pass

    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    output = tmp_path / "runner"
    runner.run_extensions(
        plan_dir=plan,
        mode="smoke",
        output_dir=output,
        graph_path=graph,
        engine_path=engine,
        profile_path=profile,
        case_executor=FakeExecutor(),
    )
    with pytest.raises(RuntimeError, match="signature runner différente"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=output,
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=DifferentSmokeExecutor(),
        )


def test_modified_source_is_rejected_before_output_creation(tmp_path: Path):
    source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    source_manifest = source / "campaign_manifest.json"
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    payload["status"] = "tampered"
    _write_json(source_manifest, payload)
    output = tmp_path / "runner"
    with pytest.raises(ValueError, match="campagne source ne correspond plus"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=output,
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=FakeExecutor(),
        )
    assert not output.exists()


def test_modified_signed_plan_is_rejected(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    design = plan / "temporal_robustness_design.csv"
    design.write_text(design.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Empreinte"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=tmp_path / "runner",
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=FakeExecutor(),
        )


def test_plan_mode_never_calls_executor(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)
    fake = FakeExecutor()
    result = runner.run_extensions(
        plan_dir=plan,
        mode="plan",
        output_dir=tmp_path / "runner_plan",
        graph_path=graph,
        engine_path=engine,
        profile_path=profile,
        case_executor=fake,
    )
    assert result["status"] == "planned"
    assert result["executed_engine_case_count"] == 0
    assert fake.calls == []


def test_pairing_guard_rejects_a_different_j0_state(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)

    class BadJ0Executor(FakeExecutor):
        def __call__(self, case, context, risk_csv):
            evidence = super().__call__(case, context, risk_csv)
            evidence.j0_state_sha256 = "different-j0"
            return evidence

    output = tmp_path / "runner"
    with pytest.raises(ValueError, match="état J0 différent"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=output,
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=BadJ0Executor(),
        )
    manifest = json.loads(
        (output / runner.RUNNER_MANIFEST).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "failed"


def test_pairing_guard_rejects_a_different_input(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)

    class BadInputExecutor(FakeExecutor):
        def __call__(self, case, context, risk_csv):
            evidence = super().__call__(case, context, risk_csv)
            evidence.input_sha256 = "different-input"
            return evidence

    with pytest.raises(ValueError, match="empreinte entrée différente"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=tmp_path / "runner_bad_input",
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=BadInputExecutor(),
        )


def test_unit_guard_rejects_a_flow_unit_different_from_graph(tmp_path: Path):
    _source, plan, graph, engine, profile = _runner_fixture(tmp_path)

    class BadUnitExecutor(FakeExecutor):
        def __call__(self, case, context, risk_csv):
            evidence = super().__call__(case, context, risk_csv)
            for row in evidence.flow_metrics:
                row["uom"] = "G"
            return evidence

    with pytest.raises(ValueError, match="différente du graphe"):
        runner.run_extensions(
            plan_dir=plan,
            mode="smoke",
            output_dir=tmp_path / "runner_bad_unit",
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            case_executor=BadUnitExecutor(),
        )


def test_missing_causal_root_is_only_genealogical_and_fails_root_gate():
    case = runner.PlannedCase(
        case_key="causal::case::seed_1",
        extension="causal_lot_attribution_subset",
        case_id="case",
        seed=1,
        pairing_block_id="block",
        paired_baseline_case_id="baseline",
        mechanism_key="quality_hold",
        risk_type="quality_delay",
        mechanism_value=90.0,
        mechanism_unit="jours_ajoutes",
        start_day=45,
        end_day=224,
        lot_trace_required=True,
        lanes=(
            runner.LaneSpec(
                "chain",
                "supplier",
                "item:component",
                "factory",
                "edge",
                "268091",
            ),
        ),
        products=("268091",),
        action="new_run_required",
    )
    evidence = runner.CaseEvidence(
        case_key=case.case_key,
        seed=1,
        status="fake",
        input_sha256="input",
        j0_state_sha256="j0",
        resolved_lot_trace_enabled=True,
        valid=True,
        validation_errors=[],
        product_metrics=[],
        flow_metrics=[],
        applied_event_ids=[],
        lot_events=[],
        lot_genealogy=[],
    )
    summary, rows = runner._genealogical_exposure(case=case, evidence=evidence)
    assert rows == []
    assert summary["root_gate_pass"] is False
    assert summary["descendant_quantity_is_upper_bound"] is True
    assert summary["causal_delay_or_loss_claimed_from_genealogy"] is False


def test_ambiguous_heuristic_lot_key_does_not_relabel_execution_as_failed():
    gates = runner._causal_lot_gate_summary(
        mode="full",
        expected_pair_count=1,
        pair_rows=[
            {
                "root_gate_pass": True,
                "genealogy_integrity_pass": True,
                "technical_event_heuristic_pairing_integrity_pass": False,
                "heuristic_comparison_display_allowed": False,
                "ambiguous_technical_key_count": 1,
            }
        ],
    )
    assert gates["causal_lot_execution_integrity_pass"] is True
    assert gates["technical_event_heuristic_pairing_integrity_pass"] is False
    assert gates["heuristic_comparison_evaluable_pass"] is False
    assert gates["causal_comparison_evaluable_pass"] is False
    assert gates["heuristic_comparison_display_allowed"] is False


def test_active_exposure_requires_effective_risk_application_on_the_lane():
    case = runner.PlannedCase(
        case_key="temporal_robustness::case::seed_1",
        extension="temporal_robustness",
        case_id="case",
        seed=1,
        pairing_block_id="block",
        paired_baseline_case_id="baseline",
        mechanism_key="transport_delay",
        risk_type="lead_time",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=0,
        lot_trace_required=False,
        lanes=(
            runner.LaneSpec(
                "chain", "supplier", "item:X", "M", "edge:X", "268091"
            ),
        ),
        products=("268091",),
        action="new_run_required",
    )
    manifest = runner._extension_manifest(
        extension=case.extension,
        mode="full",
        cases=[case],
        product_rows=[{"case_key": case.case_key}],
        flow_rows=[
            {
                "case_id": case.case_id,
                "seed": case.seed,
                "supplier_id": "supplier",
                "item_id": "item:X",
                "dst_node_id": "M",
                "baseline_flow_evidence_available": True,
                "baseline_flow_exercised": True,
                "risk_event_applied_on_lane": False,
            }
        ],
        lineage={},
    )
    assert manifest["execution_integrity_pass"] is True
    assert manifest["baseline_active_flow_pass"] is True
    assert manifest["risk_application_exposure_pass"] is False
    assert manifest["active_exposure_interpretability_pass"] is False


def test_active_exposure_uses_the_joint_seed_intersection():
    base = runner.PlannedCase(
        case_key="temporal_robustness::case::seed_1",
        extension="temporal_robustness",
        case_id="case",
        seed=1,
        pairing_block_id="metrics_seed_1",
        paired_baseline_case_id="baseline_metrics__seed_1",
        mechanism_key="transport_delay",
        risk_type="lead_time",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=179,
        lot_trace_required=False,
        lanes=(
            runner.LaneSpec(
                "chain", "supplier", "item:X", "M", "edge:X", "268091"
            ),
        ),
        products=("268091",),
        action="new_run_required",
    )
    cases = [
        replace(
            base,
            case_key=f"temporal_robustness::case::seed_{seed}",
            seed=seed,
            pairing_block_id=f"metrics_seed_{seed}",
            paired_baseline_case_id=f"baseline_metrics__seed_{seed}",
        )
        for seed in range(1, 31)
    ]
    manifest = runner._extension_manifest(
        extension=base.extension,
        mode="full",
        cases=cases,
        product_rows=[{"case_key": case.case_key} for case in cases],
        flow_rows=[
            {
                "case_id": base.case_id,
                "seed": seed,
                "supplier_id": "supplier",
                "item_id": "item:X",
                "dst_node_id": "M",
                "baseline_flow_evidence_available": True,
                "baseline_flow_exercised": seed <= 29,
                "risk_event_applied_on_lane": seed >= 2,
            }
            for seed in range(1, 31)
        ],
        lineage={},
    )
    gate = manifest["active_flow_gate_by_case_lane"][0]
    assert gate["baseline_flow_exercised_seed_count"] == 29
    assert gate["distinct_risk_applied_seed_count"] == 29
    assert gate["distinct_joint_active_exposure_seed_count"] == 28
    assert manifest["baseline_active_flow_pass"] is True
    assert manifest["risk_application_exposure_pass"] is True
    assert manifest["active_exposure_interpretability_pass"] is False


def test_common_cause_exposure_intersects_all_lanes_within_each_seed():
    lanes = (
        runner.LaneSpec(
            "chain-A", "supplier", "item:A", "M", "edge:A", "268091"
        ),
        runner.LaneSpec(
            "chain-B", "supplier", "item:B", "M", "edge:B", "268091"
        ),
    )
    base = runner.PlannedCase(
        case_key="multi_lane_supplier_common_cause::case::seed_1",
        extension="multi_lane_supplier_common_cause",
        case_id="case",
        seed=1,
        pairing_block_id="metrics_seed_1",
        paired_baseline_case_id="baseline_metrics__seed_1",
        mechanism_key="transport_delay",
        risk_type="lead_time",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=179,
        lot_trace_required=False,
        lanes=lanes,
        products=("268091",),
        action="new_run_required",
    )
    cases = [
        replace(
            base,
            case_key=f"multi_lane_supplier_common_cause::case::seed_{seed}",
            seed=seed,
            pairing_block_id=f"metrics_seed_{seed}",
            paired_baseline_case_id=f"baseline_metrics__seed_{seed}",
        )
        for seed in range(1, 31)
    ]
    flow_rows = []
    for seed in range(1, 31):
        for lane, active in ((lanes[0], seed <= 29), (lanes[1], seed >= 2)):
            flow_rows.append(
                {
                    "case_id": base.case_id,
                    "seed": seed,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "baseline_flow_evidence_available": True,
                    "baseline_flow_exercised": active,
                    "risk_event_applied_on_lane": active,
                }
            )
    manifest = runner._extension_manifest(
        extension=base.extension,
        mode="full",
        cases=cases,
        product_rows=[{"case_key": case.case_key} for case in cases],
        flow_rows=flow_rows,
        lineage={},
    )
    assert all(
        row["active_exposure_interpretability_pass"]
        for row in manifest["active_flow_gate_by_case_lane"]
    )
    joint = manifest[
        "all_lanes_joint_active_exposure_gate_by_case_supplier"
    ][0]
    assert joint["expected_affected_lane_count"] == 2
    assert joint["distinct_all_lanes_joint_active_exposure_seed_count"] == 28
    assert manifest["all_lanes_joint_active_exposure_pass"] is False
    assert manifest["active_exposure_interpretability_pass"] is False


def test_configured_but_not_applied_event_cannot_be_a_lot_root():
    case = runner.PlannedCase(
        case_key="causal_lot_attribution_subset::case::seed_1",
        extension="causal_lot_attribution_subset",
        case_id="case",
        seed=1,
        pairing_block_id="block",
        paired_baseline_case_id="baseline",
        mechanism_key="quality_hold",
        risk_type="quality_delay",
        mechanism_value=90.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=179,
        lot_trace_required=True,
        lanes=(
            runner.LaneSpec(
                "chain", "supplier", "item:X", "M", "edge:X", "268091"
            ),
        ),
        products=("268091",),
        action="new_run_required",
    )
    evidence = runner.CaseEvidence(
        case_key=case.case_key,
        seed=1,
        status="fixture",
        input_sha256="input",
        j0_state_sha256="j0",
        resolved_lot_trace_enabled=True,
        valid=True,
        validation_errors=[],
        product_metrics=[],
        flow_metrics=[],
        applied_event_ids=[],
        configured_event_ids=["EVENT-1"],
        lot_events=[
            {
                "event_type": "lane_receipt",
                "lot_id": "LOT-1",
                "node_id": "M",
                "item_id": "item:X",
                "risk_event_ids": "EVENT-1",
                "qty": 1,
                "uom": "KG",
            }
        ],
        lot_genealogy=[],
    )
    summary, exposed = runner._genealogical_exposure(case=case, evidence=evidence)
    assert summary["root_gate_pass"] is False
    assert summary["applied_expected_risk_event_ids"] == ""
    assert exposed == []

    evidence.applied_event_ids = ["EVENT-1"]
    evidence.lot_events[0]["risk_event_ids"] = "EVENT-1,FOREIGN"
    foreign_summary, foreign_exposed = runner._genealogical_exposure(
        case=case, evidence=evidence
    )
    assert foreign_summary["root_gate_pass"] is False
    assert foreign_exposed == []


def test_duplicate_genealogy_edge_is_reported_and_fails_integrity():
    case = runner.PlannedCase(
        case_key="causal_lot_attribution_subset::case::seed_1",
        extension="causal_lot_attribution_subset",
        case_id="case",
        seed=1,
        pairing_block_id="block",
        paired_baseline_case_id="baseline",
        mechanism_key="quality_hold",
        risk_type="quality_delay",
        mechanism_value=90.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=179,
        lot_trace_required=True,
        lanes=(
            runner.LaneSpec(
                "chain", "supplier", "item:X", "M", "edge:X", "268091"
            ),
        ),
        products=("268091",),
        action="new_run_required",
    )
    evidence = runner.CaseEvidence(
        case_key=case.case_key,
        seed=1,
        status="fixture",
        input_sha256="input",
        j0_state_sha256="j0",
        resolved_lot_trace_enabled=True,
        valid=True,
        validation_errors=[],
        product_metrics=[],
        flow_metrics=[],
        applied_event_ids=["EVENT-1"],
        configured_event_ids=["EVENT-1"],
        lot_events=[
            {
                "event_type": "lane_receipt",
                "lot_id": "ROOT",
                "node_id": "M",
                "item_id": "item:X",
                "risk_event_ids": "EVENT-1",
                "qty": 1,
                "uom": "KG",
            },
            {"event_type": "consume", "lot_id": "CHILD", "qty": 1, "uom": "KG"},
        ],
        lot_genealogy=[
            {"parent_lot_id": "ROOT", "child_lot_id": "CHILD"},
            {"parent_lot_id": "ROOT", "child_lot_id": "CHILD"},
        ],
    )
    summary, exposed = runner._genealogical_exposure(case=case, evidence=evidence)
    assert summary["root_gate_pass"] is True
    assert summary["duplicate_genealogy_edge_count"] == 1
    assert summary["genealogy_integrity_pass"] is False
    detail = runner._lot_genealogical_exposure_detail_rows(
        case=case,
        exposed_rows=exposed,
    )
    assert [row["exposure_role"] for row in detail] == [
        "risk_tagged_usable_receipt_root",
        "genealogical_descendant",
    ]
    assert all(row["causal_delay_or_loss_claimed"] is False for row in detail)
    assert all(row["industrial_lot_number_claimed"] is False for row in detail)


def test_genealogical_quantity_rejects_missing_unit_or_invalid_value():
    with pytest.raises(ValueError, match="Unit"):
        runner._quantity_by_uom([{"qty": 1, "uom": ""}])
    with pytest.raises(ValueError, match="invalide"):
        runner._quantity_by_uom([{"qty": -1, "uom": "KG"}])


def test_local_metrics_for_a_single_lane_do_not_add_the_other_product(
    tmp_path: Path,
):
    case = runner.PlannedCase(
        case_key="temporal_robustness::case::seed_1",
        extension="temporal_robustness",
        case_id="case",
        seed=1,
        pairing_block_id="block",
        paired_baseline_case_id="baseline",
        mechanism_key="transport_delay",
        risk_type="lead_time",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=0,
        lot_trace_required=False,
        lanes=(
            runner.LaneSpec(
                "chain", "supplier", "item:X", "M", "edge:X", "268091"
            ),
        ),
        products=("268091",),
        action="new_run_required",
        simulation_days=1,
        outcome_spec_id="local_day_0",
        outcome_start_day=0,
        outcome_end_day=0,
        outcome_day_count=1,
    )
    data = tmp_path / "data"
    _write_csv(
        data / "production_demand_service_daily.csv",
        [
            {
                "day": 0,
                "node_id": "C-XXXXX",
                "item_id": "item:268091",
                "demand_qty": 10,
                "required_with_backlog_qty": 10,
                "served_qty": 9,
                "backlog_end_qty": 1,
            }
        ],
    )
    _write_csv(
        data / "production_output_products_daily.csv",
        [
            {
                "day": 0,
                "node_id": "M",
                "item_id": "item:268091",
                "released_qty": 9,
            }
        ],
    )
    graph = {
        "nodes": [
            {
                "id": "M",
                "inventory": {
                    "states": [{"item_id": "item:268091", "uom": "UN"}]
                },
            }
        ]
    }
    rows = runner._extract_local_product_metrics(
        case_dir=tmp_path, graph=graph, case=case
    )
    assert [row["product_id"] for row in rows] == ["268091"]
    assert runner._local_metric_contract_errors(
        case, replace(
            runner.CaseEvidence(
                case_key=case.case_key,
                seed=1,
                status="fixture",
                input_sha256="input",
                j0_state_sha256="j0",
                resolved_lot_trace_enabled=False,
                valid=True,
                validation_errors=[],
                product_metrics=[],
                flow_metrics=[],
                applied_event_ids=[],
                lot_events=[],
                lot_genealogy=[],
            ),
            local_product_metrics=rows,
        )
    ) == []


def test_additive_dashboard_consolidation_copies_only_small_results_and_real_gates(
    tmp_path: Path,
):
    source, _plan, _graph, _engine, _profile = _runner_fixture(tmp_path)
    ranking = [
        {
            "supplier_id": f"S{rank}",
            "supplier_sensitivity_rank": rank,
            "top3_presence_seed_count": 30 if rank <= 3 else 0,
            "confirmation_seed_count": 30,
        }
        for rank in range(1, 5)
    ]
    _write_csv(source / "supplier_sensitivity_ranking.csv", ranking)
    _write_csv(
        source / "failure_mode_sensitivity_summary.csv",
        [{"failure_mode": "transport_delay", "failure_mode_sensitivity_rank": 1}],
    )
    _write_csv(
        source / "confirmed_top3_stability.csv",
        [
            {
                "supplier_id": f"S{rank}",
                "aggregate_confirmation_rank": rank,
                "top3_presence_seed_count": 30,
                "confirmation_seed_count": 30,
            }
            for rank in range(1, 4)
        ],
    )
    runner_dir = tmp_path / "extension_results"
    runner_dir.mkdir()
    source_manifest_sha256 = planner._sha256(source / "campaign_manifest.json")
    _write_json(
        runner_dir / runner.RUNNER_MANIFEST,
        {
            "status": "complete",
            "mode": "full",
            "runner_signature": "runner-signature",
            "plan_signature": "plan-signature",
            "source_dir": str(source.resolve()),
            "source_campaign_manifest_sha256": source_manifest_sha256,
        },
    )
    states = {
        "multi_lane_supplier_common_cause_manifest.json": True,
        "temporal_robustness_manifest.json": False,
        "priority_four_business_causes_manifest.json": True,
        "causal_lot_attribution_manifest.json": True,
    }
    for name, passed in states.items():
        _write_json(
            runner_dir / name,
            {
                "status": "complete",
                "release_gate_pass": passed,
                "execution_integrity_pass": True,
                "active_exposure_interpretability_pass": passed,
                "runner_signature": "runner-signature",
                "plan_signature": "plan-signature",
                "source_campaign_manifest_sha256": source_manifest_sha256,
            },
        )
    for name in runner.CONSOLIDATED_SMALL_EXTENSION_FILES:
        path = runner_dir / name
        if path.is_file():
            continue
        if path.suffix == ".json":
            _write_json(path, {"status": "complete"})
        else:
            _write_csv(path, [{"case_id": "case-1", "value": 1}])
    source_hashes_before = {
        path.relative_to(source).as_posix(): planner._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }
    consolidated = runner.consolidate_dashboard_network_artifact(
        source_dir=source,
        runner_dir=runner_dir,
        output_dir=tmp_path / "consolidated",
    )
    manifest = json.loads(
        (consolidated / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["mode"] == "full"
    assert manifest["large_case_directories_copied"] is False
    assert manifest["extensions_required"]["multi_lane_supplier_common_cause"][
        "execution_integrity_pass"
    ] is True
    assert manifest["extensions_required"]["multi_lane_supplier_common_cause"][
        "pass"
    ] is False
    assert manifest["extensions_required"]["temporal_robustness"]["pass"] is False
    assert not (consolidated / "cases").exists()
    assert (consolidated / "priority_four_business_causes_summary.csv").is_file()
    assert (consolidated / "causal_lot_attribution_detail.csv").is_file()
    state = industrial_dashboard._campaign_state(consolidated, kind="network")
    assert state["state"] != industrial_dashboard.NETWORK_STABILIZED_STATE
    source_hashes_after = {
        path.relative_to(source).as_posix(): planner._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }
    assert source_hashes_after == source_hashes_before
    assert (
        runner.consolidate_dashboard_network_artifact(
            source_dir=source,
            runner_dir=runner_dir,
            output_dir=consolidated,
        )
        == consolidated
    )
    copied_summary = consolidated / "priority_four_business_causes_summary.csv"
    copied_summary.write_text(
        copied_summary.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="Consolidation existante altérée"):
        runner.consolidate_dashboard_network_artifact(
            source_dir=source,
            runner_dir=runner_dir,
            output_dir=consolidated,
        )
