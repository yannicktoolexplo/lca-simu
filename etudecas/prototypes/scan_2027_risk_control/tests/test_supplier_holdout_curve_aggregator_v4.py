from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_aggregator_v4 as aggregator,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as sidecar,
)


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
