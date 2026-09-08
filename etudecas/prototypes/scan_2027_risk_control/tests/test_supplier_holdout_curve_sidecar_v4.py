from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as sidecar,
)


def _csv_bytes(spec: sidecar.CsvSpec, horizon: int) -> bytes:
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
    complete = _csv_bytes(spec, 4)
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
            (data_dir / spec.filename).write_bytes(_csv_bytes(spec, horizon))
    service = sidecar.SPEC_BY_FILENAME["production_demand_service_daily.csv"]
    (data_dir / service.filename).write_bytes(
        _csv_bytes(service, horizon).splitlines(keepends=True)[0]
    )
    _write_summary(case_dir, case, horizon)
    watcher = sidecar.CurveCaptureWatcher(
        contract=contract,
        output_dir=output_dir,
        poll_seconds=0.001,
        stability_seconds=0,
    )
    assert watcher.scan_once() == 0

    (data_dir / service.filename).write_bytes(_csv_bytes(service, horizon))
    assert watcher.scan_once() == 1
    inventory = sidecar.finalize_capture(contract, output_dir)
    assert inventory["status"] == "complete"
    assert inventory["case_count"] == 1
    snapshot, metadata = sidecar._snapshot_paths(output_dir, case, service.filename)
    assert gzip.decompress(snapshot.read_bytes()) == _csv_bytes(service, horizon)
    assert metadata.is_file()


def test_snapshot_is_refreshed_before_summary_confirms_case(tmp_path: Path) -> None:
    horizon = 3
    contract, case, _, output_dir, case_dir, data_dir = _setup_contract(
        tmp_path, horizon=horizon
    )
    for spec in sidecar.CSV_SPECS:
        if spec.required:
            (data_dir / spec.filename).write_bytes(_csv_bytes(spec, horizon))
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

    changed = _csv_bytes(service, horizon).replace(b",0,0,0,0,0\n", b",1,1,1,0,1\n", 1)
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
            (data_dir / spec.filename).write_bytes(_csv_bytes(spec, horizon))
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
