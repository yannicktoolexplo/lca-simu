"""Research checks grouped by business scope; distinct protocols stay explicit."""
from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path
import pytest
from etudecas.prototypes.scan_2027_risk_control import supplier_holdout_curve_aggregator_v4 as aggregator
from etudecas.prototypes.scan_2027_risk_control import supplier_holdout_curve_sidecar_v4 as sidecar
from types import SimpleNamespace
from etudecas.prototypes.scan_2027_risk_control import supplier_balanced_product_delay_multiseed_refinement_v5 as refinement
from etudecas.prototypes.scan_2027_risk_control import supplier_holdout_curve_sidecar_v5 as sidecar_v5


# supplier_holdout_curve_aggregator_v4

def _csv_bytes(spec: sidecar.CsvSpec, horizon: int, *, seed_index: int) -> bytes:
    if spec.filename == "production_demand_service_daily.csv":
        identities = (("C-XXXXX", "item:268091"), ("C-XXXXX", "item:268967"))
    elif spec.filename == "production_output_products_daily.csv":
        identities = (("M-1810", "item:268091"), ("M-1430", "item:268967"))
    elif spec.filename == "production_input_stocks_daily.csv":
        identities = (("M-1810", "item:338929"),)
    elif spec.filename == "production_constraint_daily.csv":
        identities = (("M-1810", "item:268091"), ("M-1430", "item:268967"))
    else:
        identities = (("", ""),)
    days = range(horizon) if spec.dense_by_key else (0,)
    rows: list[dict[str, str]] = []
    for day in days:
        for node_id, item_id in identities:
            row = {column: "0" for column in spec.columns}
            row["day"] = str(day)
            if "node_id" in row:
                row["node_id"] = node_id
            if "item_id" in row:
                row["item_id"] = item_id
            if "output_item_id" in row:
                row["output_item_id"] = item_id
            if spec.filename == "production_demand_service_daily.csv":
                row["demand_qty"] = "10"
                row["required_with_backlog_qty"] = "10"
                row["served_qty"] = "10" if seed_index == 0 else "5"
                row["backlog_end_qty"] = "0" if seed_index == 0 else "5"
                row["available_before_service_qty"] = row["served_qty"]
            elif spec.filename == "production_output_products_daily.csv":
                row["released_qty"] = str(100 + seed_index * 100)
                row["produced_qty"] = str(80 + seed_index * 40)
                row["wip_end_qty"] = str(10 + seed_index * 20)
                row["stock_end_of_day"] = str(20 + seed_index * 20)
                row["executed_qty"] = row["produced_qty"]
                row["cum_produced_qty"] = str((day + 1) * int(row["produced_qty"]))
            elif spec.filename == "production_input_stocks_daily.csv":
                row["stock_before_production"] = str(50 + seed_index * 20)
                row["stock_end_of_day"] = str(50 + seed_index * 20)
            elif spec.filename == "production_constraint_daily.csv":
                row["capacity_limit_mode"] = "finite"
                row["binding_cause"] = "none"
                row["lot_policy_mode"] = "fixed"
            rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=spec.columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _captured_two_seed_run(tmp_path: Path, horizon: int = 30) -> Path:
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "sidecar"
    plan_dir.mkdir()
    run_dir.mkdir()
    (plan_dir / "refinement_plan.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text("{}\n", encoding="utf-8")
    cases = tuple(
        sidecar.ExpectedCase(
            target_group="op_93",
            candidate_key="candidate-key",
            candidate_id="candidate-id",
            seed=seed,
            graph_sha256="a" * 64,
        )
        for seed in (41, 42)
    )
    contract = sidecar.build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        cases=cases,
        horizon=horizon,
    )
    sidecar.register_contract(output_dir, contract)
    registered = json.loads(
        (output_dir / "capture_contract.json").read_text(encoding="utf-8")
    )
    for seed_index, case in enumerate(cases):
        case_dir = (
            run_dir
            / "engine_attempts"
            / "holdout"
            / f"digest-{seed_index}"
            / "attempt-1"
            / "cases"
            / case.candidate_id
            / f"seed_{case.seed}"
        )
        data_dir = case_dir / "data"
        summary_dir = case_dir / "summaries"
        data_dir.mkdir(parents=True)
        summary_dir.mkdir()
        for spec in sidecar.CSV_SPECS:
            if spec.required:
                (data_dir / spec.filename).write_bytes(
                    _csv_bytes(spec, horizon, seed_index=seed_index)
                )
        (summary_dir / "first_simulation_summary.json").write_text(
            json.dumps(
                {
                    "sim_days": horizon,
                    "scenario_id": "scn:BASE",
                    "input_sha256": case.graph_sha256,
                    "policy": {"seed": case.seed},
                }
            ),
            encoding="utf-8",
        )
    watcher = sidecar.CurveCaptureWatcher(
        contract=registered,
        output_dir=output_dir,
        poll_seconds=0.001,
        stability_seconds=0,
    )
    assert watcher.scan_once() == 2
    sidecar.finalize_capture(registered, output_dir)
    return output_dir


def _read_aggregate(path: Path) -> list[dict[str, str]]:
    raw = gzip.decompress(path.read_bytes()).decode("utf-8")
    return list(csv.DictReader(io.StringIO(raw, newline="")))


def test_linear_quantile_uses_interpolation() -> None:
    assert aggregator.linear_quantile((0.5, 1.0), 0.10) == pytest.approx(0.55)
    assert aggregator.linear_quantile((0.5, 1.0), 0.50) == pytest.approx(0.75)
    assert aggregator.linear_quantile((0.5, 1.0), 0.90) == pytest.approx(0.95)


def test_rolling_functions_require_complete_windows() -> None:
    mean = aggregator.rolling_mean([1.0, 2.0, 3.0], 2)
    ratio = aggregator.rolling_ratio([1.0, 1.0, 2.0], [2.0, 2.0, 2.0], 2)
    assert mean == [None, 1.5, 2.5]
    assert ratio == [None, 0.5, 0.75]


def test_aggregate_capture_builds_seed_first_rolling_envelopes(tmp_path: Path) -> None:
    output_dir = _captured_two_seed_run(tmp_path)
    manifest = aggregator.aggregate_capture(output_dir)
    assert manifest["status"] == "complete"
    assert manifest["case_count"] == 2
    validation = aggregator.validate_aggregates(output_dir)
    assert validation == {
        "valid": True,
        "manifest_path": str(
            (
                output_dir
                / aggregator.AGGREGATE_SUBDIRECTORY
                / "aggregate_manifest.json"
            ).resolve()
        ),
        "manifest_signature": manifest["manifest_signature"],
        "case_count": 2,
        "state_count": 1,
        "file_count": 4,
    }

    aggregate_dir = output_dir / aggregator.AGGREGATE_SUBDIRECTORY
    service_rows = _read_aggregate(aggregate_dir / "service_quantiles_daily.csv.gz")
    service = next(
        row
        for row in service_rows
        if row["item_id"] == "item:268091"
        and row["metric"] == "on_due_service_ratio"
        and row["rolling_window_days"] == "28"
        and row["day"] == "27"
    )
    assert service["sample_count"] == "2"
    assert float(service["p10"]) == pytest.approx(0.55)
    assert float(service["median"]) == pytest.approx(0.75)
    assert float(service["p90"]) == pytest.approx(0.95)
    early = next(
        row
        for row in service_rows
        if row["item_id"] == "item:268091"
        and row["metric"] == "on_due_service_ratio"
        and row["rolling_window_days"] == "28"
        and row["day"] == "26"
    )
    assert early["sample_count"] == "0"
    assert early["median"] == ""

    production_rows = _read_aggregate(
        aggregate_dir / "production_quantiles_daily.csv.gz"
    )
    production = next(
        row
        for row in production_rows
        if row["item_id"] == "item:268091"
        and row["metric"] == "released_qty"
        and row["rolling_window_days"] == "28"
        and row["day"] == "27"
    )
    assert float(production["median"]) == pytest.approx(150.0)
    assert aggregator.aggregate_capture(output_dir) == manifest


def test_validate_detects_modified_aggregate(tmp_path: Path) -> None:
    output_dir = _captured_two_seed_run(tmp_path)
    aggregator.aggregate_capture(output_dir)
    path = (
        output_dir
        / aggregator.AGGREGATE_SUBDIRECTORY
        / "service_quantiles_daily.csv.gz"
    )
    path.write_bytes(b"altered")
    with pytest.raises(aggregator.CurveAggregationError, match="invalide"):
        aggregator.validate_aggregates(output_dir)

# supplier_holdout_curve_sidecar_v4

def _snapshot_csv_bytes(spec: sidecar.CsvSpec, horizon: int) -> bytes:
    rows: list[dict[str, str]] = []
    if spec.filename == "production_demand_service_daily.csv":
        identities = (("C-XXXXX", "item:268091"), ("C-XXXXX", "item:268967"))
    elif spec.filename == "production_output_products_daily.csv":
        identities = (("M-1810", "item:268091"), ("M-1430", "item:268967"))
    elif spec.filename == "production_input_stocks_daily.csv":
        identities = (("M-1810", "item:338929"),)
    elif spec.filename == "production_constraint_daily.csv":
        identities = (("M-1810", "item:268091"), ("M-1430", "item:268967"))
    else:
        identities = (("", ""),)

    days = range(horizon) if spec.dense_by_key else (0,)
    for day in days:
        for node_id, item_id in identities:
            row = {column: "0" for column in spec.columns}
            row["day"] = str(day)
            if "node_id" in row:
                row["node_id"] = node_id
            if "item_id" in row:
                row["item_id"] = item_id
            if "output_item_id" in row:
                row["output_item_id"] = item_id
            if "capacity_limit_mode" in row:
                row["capacity_limit_mode"] = "finite"
            if "binding_cause" in row:
                row["binding_cause"] = "none"
            if "lot_policy_mode" in row:
                row["lot_policy_mode"] = "fixed"
            rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=spec.columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _setup_contract(tmp_path: Path, *, horizon: int = 4):
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "sidecar"
    plan_dir.mkdir()
    run_dir.mkdir()
    (plan_dir / "refinement_plan.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text("{}\n", encoding="utf-8")
    case = sidecar.ExpectedCase(
        target_group="op_93",
        candidate_key="candidate-key",
        candidate_id="candidate-id",
        seed=42,
        graph_sha256="a" * 64,
    )
    contract = sidecar.build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        cases=(case,),
        horizon=horizon,
    )
    sidecar.register_contract(output_dir, contract)
    registered = json.loads(
        (output_dir / "capture_contract.json").read_text(encoding="utf-8")
    )
    case_dir = (
        run_dir
        / "engine_attempts"
        / "holdout"
        / "digest"
        / "attempt-1"
        / "cases"
        / case.candidate_id
        / f"seed_{case.seed}"
    )
    data_dir = case_dir / "data"
    data_dir.mkdir(parents=True)
    return registered, case, run_dir, output_dir, case_dir, data_dir


def _write_summary(case_dir: Path, case: sidecar.ExpectedCase, horizon: int) -> None:
    path = case_dir / "summaries" / "first_simulation_summary.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "sim_days": horizon,
                "scenario_id": "scn:BASE",
                "input_sha256": case.graph_sha256,
                "policy": {"seed": case.seed},
            }
        ),
        encoding="utf-8",
    )


def test_validate_csv_rejects_truncated_dense_series() -> None:
    spec = sidecar.SPEC_BY_FILENAME["production_demand_service_daily.csv"]
    complete = _snapshot_csv_bytes(spec, 4)
    validation = sidecar.validate_csv_bytes(complete, spec, 4)
    assert validation["row_count"] == 8
    assert validation["day_count"] == 4

    rows = complete.decode("utf-8").splitlines()
    truncated = ("\n".join(rows[:-1]) + "\n").encode("utf-8")
    with pytest.raises(sidecar.CurveSidecarError, match="incomplète"):
        sidecar.validate_csv_bytes(truncated, spec, 4)


def test_watcher_recovers_after_partial_source_and_finalizes(tmp_path: Path) -> None:
    horizon = 4
    contract, case, _, output_dir, case_dir, data_dir = _setup_contract(
        tmp_path, horizon=horizon
    )
    for spec in sidecar.CSV_SPECS:
        if spec.required:
            (data_dir / spec.filename).write_bytes(_snapshot_csv_bytes(spec, horizon))
    service = sidecar.SPEC_BY_FILENAME["production_demand_service_daily.csv"]
    (data_dir / service.filename).write_bytes(
        _snapshot_csv_bytes(service, horizon).splitlines(keepends=True)[0]
    )
    _write_summary(case_dir, case, horizon)
    watcher = sidecar.CurveCaptureWatcher(
        contract=contract,
        output_dir=output_dir,
        poll_seconds=0.001,
        stability_seconds=0,
    )
    assert watcher.scan_once() == 0

    (data_dir / service.filename).write_bytes(_snapshot_csv_bytes(service, horizon))
    assert watcher.scan_once() == 1
    inventory = sidecar.finalize_capture(contract, output_dir)
    assert inventory["status"] == "complete"
    assert inventory["case_count"] == 1
    snapshot, metadata = sidecar._snapshot_paths(output_dir, case, service.filename)
    assert gzip.decompress(snapshot.read_bytes()) == _snapshot_csv_bytes(service, horizon)
    assert metadata.is_file()


def test_snapshot_is_refreshed_before_summary_confirms_case(tmp_path: Path) -> None:
    horizon = 3
    contract, case, _, output_dir, case_dir, data_dir = _setup_contract(
        tmp_path, horizon=horizon
    )
    for spec in sidecar.CSV_SPECS:
        if spec.required:
            (data_dir / spec.filename).write_bytes(_snapshot_csv_bytes(spec, horizon))
    watcher = sidecar.CurveCaptureWatcher(
        contract=contract,
        output_dir=output_dir,
        poll_seconds=0.001,
        stability_seconds=0,
    )
    assert watcher.scan_once() == 0
    service = sidecar.SPEC_BY_FILENAME["production_demand_service_daily.csv"]
    _, meta_path = sidecar._snapshot_paths(output_dir, case, service.filename)
    before = json.loads(meta_path.read_text(encoding="utf-8"))["source_sha256"]

    changed = _snapshot_csv_bytes(service, horizon).replace(b",0,0,0,0,0\n", b",1,1,1,0,1\n", 1)
    (data_dir / service.filename).write_bytes(changed)
    _write_summary(case_dir, case, horizon)
    assert watcher.scan_once() == 1
    after = json.loads(meta_path.read_text(encoding="utf-8"))["source_sha256"]
    assert before != after


def test_finalizer_fails_closed_after_snapshot_corruption(tmp_path: Path) -> None:
    horizon = 2
    contract, case, _, output_dir, case_dir, data_dir = _setup_contract(
        tmp_path, horizon=horizon
    )
    for spec in sidecar.CSV_SPECS:
        if spec.required:
            (data_dir / spec.filename).write_bytes(_snapshot_csv_bytes(spec, horizon))
    _write_summary(case_dir, case, horizon)
    watcher = sidecar.CurveCaptureWatcher(
        contract=contract,
        output_dir=output_dir,
        poll_seconds=0.001,
        stability_seconds=0,
    )
    assert watcher.scan_once() == 1
    service = sidecar.SPEC_BY_FILENAME["production_demand_service_daily.csv"]
    snapshot, _ = sidecar._snapshot_paths(output_dir, case, service.filename)
    snapshot.write_bytes(b"corrompu")
    with pytest.raises(sidecar.CurveSidecarError, match="altéré"):
        sidecar.finalize_capture(contract, output_dir)


def test_output_must_not_overlap_plan_or_run(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    plan_dir.mkdir()
    run_dir.mkdir()
    (plan_dir / "refinement_plan.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text("{}", encoding="utf-8")
    case = sidecar.ExpectedCase("op_93", "key", "candidate", 1, "a" * 64)
    with pytest.raises(sidecar.CurveSidecarError, match="extérieure"):
        sidecar.build_contract(
            plan_dir=plan_dir,
            run_dir=run_dir,
            output_dir=run_dir / "sidecar",
            cases=(case,),
            horizon=2,
        )

# supplier_holdout_curve_sidecar_v5

def _candidates():
    return (
        refinement.Candidate("op100_source", "v5-op100", "op_100", 0, 0, "x", ""),
        refinement.Candidate("op93", "v5-op93", "op_93", 8, 81, "x", ""),
        refinement.Candidate("op80", "v5-op80", "op_80", 19, 97, "x", ""),
    )


def _cases() -> tuple[sidecar_v5.ExpectedCase, ...]:
    return tuple(
        sidecar_v5.ExpectedCase(
            target_group=candidate.target_group,
            candidate_key=candidate.key,
            candidate_id=candidate.candidate_id,
            seed=seed,
            graph_sha256=(candidate.key[2:] + "a" * 64)[:64],
        )
        for candidate in _candidates()
        for seed in refinement.EXPECTED_HOLDOUT_SEEDS
    )


def test_load_cases_uses_v5_validator_and_requires_exact_three_by_thirty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candidates = _candidates()
    plan = SimpleNamespace(
        manifest={
            "inventory": {
                candidate.key: {"graph_sha256": (candidate.key + "a" * 64)[:64]}
                for candidate in candidates
            }
        }
    )
    monkeypatch.setattr(refinement, "validate_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        refinement,
        "_stage_jobs",
        lambda *args: tuple(
            (candidate, seed)
            for candidate in candidates
            for seed in refinement.EXPECTED_HOLDOUT_SEEDS
        ),
    )
    cases = sidecar_v5.load_official_cases(tmp_path / "plan", tmp_path / "run")
    assert len(cases) == 90
    assert {case.target_group for case in cases} == {"op_100", "op_93", "op_80"}
    assert all(
        len({case.seed for case in cases if case.target_group == group}) == 30
        for group in sidecar_v5.EXPECTED_TARGET_GROUPS
    )

    monkeypatch.setattr(refinement, "_stage_jobs", lambda *args: tuple())
    with pytest.raises(sidecar_v5.CurveSidecarError, match="3 x 30"):
        sidecar_v5.load_official_cases(tmp_path / "plan", tmp_path / "run")


def test_contract_and_ready_receipt_are_v5_signed(tmp_path: Path) -> None:
    plan = tmp_path / "plan"
    run = tmp_path / "run"
    output = tmp_path / "sidecar"
    plan.mkdir()
    run.mkdir()
    (plan / "refinement_plan.json").write_text("{}\n", encoding="utf-8")
    (run / "run_manifest.json").write_text("{}\n", encoding="utf-8")
    contract = sidecar_v5.build_contract(
        plan_dir=plan,
        run_dir=run,
        output_dir=output,
        cases=_cases(),
    )
    assert contract["schema_version"] == sidecar_v5.CONTRACT_SCHEMA_VERSION
    assert contract["producer_protocol"] == refinement.SCHEMA_VERSION
    assert contract["expected_case_count"] == 90
    assert contract["fresh_execution_contract"]["engine_execution"].startswith(
        "fresh_after"
    )
    sidecar._verify_signature(  # noqa: SLF001
        contract, "contract_signature", "test"
    )
    assert sidecar_v5.validate_contract(contract) == contract

    wrong_contract = dict(contract)
    wrong_contract["expected_case_count"] = 89
    with pytest.raises(sidecar_v5.CurveSidecarError, match="Signature invalide"):
        sidecar_v5.validate_contract(wrong_contract)

    ready = sidecar_v5._ready_payload(contract, output_dir=output)  # noqa: SLF001
    output.mkdir()
    sidecar._atomic_write_json(output / "watcher_ready.json", ready)  # noqa: SLF001
    validated = sidecar_v5.validate_ready(
        output / "watcher_ready.json",
        expected_output_dir=output,
        expected_watcher_pid=ready["watcher_pid"],
    )
    assert validated["expected_case_count"] == 90

    tampered = json.loads((output / "watcher_ready.json").read_text(encoding="utf-8"))
    tampered["expected_case_count"] = 89
    (output / "watcher_ready.json").write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(sidecar_v5.CurveSidecarError, match="Signature invalide"):
        sidecar_v5.validate_ready(output / "watcher_ready.json")


def test_v5_inventory_wraps_the_compatible_base_inventory(tmp_path: Path) -> None:
    output = tmp_path / "sidecar"
    output.mkdir()
    base_path = output / "capture_inventory.json"
    base_path.write_text('{"case_count": 90}\n', encoding="utf-8")
    contract = {"contract_signature": "c" * 64}
    base = {"case_count": 90, "inventory_signature": "i" * 64}
    inventory = sidecar_v5._write_v5_inventory(  # noqa: SLF001
        output_dir=output,
        contract=contract,
        base_inventory=base,
    )
    assert inventory["schema_version"] == sidecar_v5.INVENTORY_SCHEMA_VERSION
    assert inventory["case_count"] == 90
    assert (output / "capture_inventory_v5.json").is_file()
    sidecar._verify_signature(  # noqa: SLF001
        inventory, "inventory_signature", "test"
    )
