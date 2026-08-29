from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

from etudecas.simulation.engine.run_first_simulation import (
    load_opening_observed_stock_scale_overrides,
    load_measurement_start_in_transit_scale_overrides,
    load_measurement_start_stock_scale_overrides,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "engine"
    / "run_first_simulation.py"
)
GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
MRP_SNAPSHOT_PAIR = ("M-1810", "item:338929")


def _run_engine(
    output_dir: Path,
    *,
    scale: float | None = None,
    scale_csv: Path | None = None,
    measurement_scale_csv: Path | None = None,
    measurement_in_transit_scale_csv: Path | None = None,
    lot_trace: bool = False,
    skip_lot_audit: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ENGINE),
        "--input",
        str(GRAPH),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        "1",
        "--warmup-days",
        "1",
        "--warmup-boundary-audit",
        "--seed",
        "9102",
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--lot-trace" if lot_trace else "--no-lot-trace",
    ]
    if skip_lot_audit:
        command.append("--skip-lot-audit")
    if scale is not None:
        command.extend(["--opening-observed-stock-scale", str(scale)])
    if scale_csv is not None:
        command.extend(
            ["--opening-observed-stock-scale-csv", str(scale_csv)]
        )
    if measurement_scale_csv is not None:
        command.extend(
            ["--measurement-start-stock-scale-csv", str(measurement_scale_csv)]
        )
    if measurement_in_transit_scale_csv is not None:
        command.extend(
            [
                "--measurement-start-in-transit-scale-csv",
                str(measurement_in_transit_scale_csv),
            ]
        )
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _summary(output_dir: Path) -> dict:
    return json.loads(
        (
            output_dir / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )


def _observed_rows(output_dir: Path) -> tuple[list[str], list[dict[str, str]]]:
    with (
        output_dir / "data" / "initialization_observed_stock.csv"
    ).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _snapshot_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next(
        row
        for row in rows
        if (row["node_id"], row["item_id"]) == MRP_SNAPSHOT_PAIR
    )


def test_absent_scale_preserves_historical_schema_and_scale_one_dynamics(
    tmp_path: Path,
) -> None:
    default_dir = tmp_path / "default"
    explicit_one_dir = tmp_path / "explicit_one"
    default_run = _run_engine(default_dir)
    explicit_one_run = _run_engine(explicit_one_dir, scale=1.0)
    assert default_run.returncode == 0, default_run.stderr or default_run.stdout
    assert explicit_one_run.returncode == 0, (
        explicit_one_run.stderr or explicit_one_run.stdout
    )

    default_summary = _summary(default_dir)
    explicit_one_summary = _summary(explicit_one_dir)
    assert "opening_observed_stock_scale" not in default_summary["policy"]
    assert "measurement_start_stock_scale" not in default_summary["policy"]
    assert "measurement_start_in_transit_scale" not in default_summary["policy"]
    assert not (
        default_dir / "data" / "measurement_start_stock_adjustments.csv"
    ).exists()
    assert not (
        default_dir
        / "data"
        / "measurement_start_in_transit_adjustments.csv"
    ).exists()
    default_fields, default_rows = _observed_rows(default_dir)
    assert default_fields == [
        "node_id",
        "node_type",
        "item_id",
        "opening_stock_qty",
        "uom",
        "source",
    ]
    assert float(_snapshot_row(default_rows)["opening_stock_qty"]) == pytest.approx(
        354_000.0
    )

    assert explicit_one_summary["policy"]["opening_observed_stock_scale"][
        "factor"
    ] == pytest.approx(1.0)
    assert default_summary["policy"]["warmup_boundary_audit"][
        "core_state_sha256"
    ] == explicit_one_summary["policy"]["warmup_boundary_audit"][
        "core_state_sha256"
    ]
    assert (
        default_dir / "data" / "first_simulation_daily.csv"
    ).read_bytes() == (
        explicit_one_dir / "data" / "first_simulation_daily.csv"
    ).read_bytes()


def test_scale_reduces_mrp_snapshot_and_is_audited_at_warmup_boundary(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "scaled_first"
    replay_dir = tmp_path / "scaled_replay"
    first_run = _run_engine(first_dir, scale=0.1)
    replay_run = _run_engine(replay_dir, scale=0.1)
    assert first_run.returncode == 0, first_run.stderr or first_run.stdout
    assert replay_run.returncode == 0, replay_run.stderr or replay_run.stdout

    fields, rows = _observed_rows(first_dir)
    assert "input_opening_stock_qty" in fields
    assert "effective_opening_stock_qty" in fields
    row = _snapshot_row(rows)
    assert float(row["input_opening_stock_qty"]) == pytest.approx(354_000.0)
    assert float(row["opening_observed_stock_scale"]) == pytest.approx(0.1)
    assert float(row["effective_opening_stock_qty"]) == pytest.approx(35_400.0)
    assert float(row["opening_stock_qty"]) == pytest.approx(35_400.0)
    assert float(row["base_stock_qty_after_scale"]) == pytest.approx(0.0)
    assert row["mrp_snapshot_state_only"] == "1"

    summary = _summary(first_dir)
    replay_summary = _summary(replay_dir)
    scale_audit = summary["policy"]["opening_observed_stock_scale"]
    assert scale_audit["application_stage"] == (
        "graph_inventory_initial_before_warmup"
    )
    assert scale_audit["scientific_interpretation"] == (
        "global_sensitivity_stress_test_not_calibrated_opening_state"
    )
    assert scale_audit["quantities_by_uom"]["UN"]["effective_qty"] == (
        pytest.approx(
            scale_audit["quantities_by_uom"]["UN"]["source_qty"] * 0.1,
            abs=1e-6,
        )
    )
    boundary = summary["policy"]["warmup_boundary_audit"]
    replay_boundary = replay_summary["policy"]["warmup_boundary_audit"]
    assert boundary["opening_observed_stock_scale"] == scale_audit
    assert boundary["core_state_sha256"] == replay_boundary["core_state_sha256"]
    assert boundary["component_sha256"] == replay_boundary["component_sha256"]
    assert len(boundary["core_state_sha256"]) == 64

    with (first_dir / "data" / "assumptions_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        assumption_rows = [
            entry
            for entry in csv.DictReader(handle)
            if entry["category"] == "opening_observed_stock_scale"
        ]
    assert len(assumption_rows) == 1
    assert assumption_rows[0]["source"] == "cli_sensitivity_assumption"
    assert json.loads(assumption_rows[0]["payload_json"]) == scale_audit


def test_pair_csv_scales_only_listed_opening_stock_and_audits_j0(
    tmp_path: Path,
) -> None:
    scale_csv = tmp_path / "targeted_opening_stock.csv"
    scale_csv.write_text(
        "node_id,item_id,scale\n"
        "SDC-1450,item:021081,0.1\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "targeted"
    result = _run_engine(output_dir, scale_csv=scale_csv)
    assert result.returncode == 0, result.stderr or result.stdout

    _, rows = _observed_rows(output_dir)
    target = next(
        row
        for row in rows
        if (row["node_id"], row["item_id"])
        == ("SDC-1450", "item:021081")
    )
    neighbor = next(
        row
        for row in rows
        if (row["node_id"], row["item_id"])
        == ("SDC-1450", "item:773474")
    )
    assert float(target["input_opening_stock_qty"]) == pytest.approx(
        1_142_100.0
    )
    assert float(target["effective_opening_stock_qty"]) == pytest.approx(
        114_210.0
    )
    assert float(target["opening_observed_stock_scale"]) == pytest.approx(0.1)
    assert float(neighbor["input_opening_stock_qty"]) == pytest.approx(
        9_600_000.0
    )
    assert float(neighbor["effective_opening_stock_qty"]) == pytest.approx(
        9_600_000.0
    )
    assert float(neighbor["opening_observed_stock_scale"]) == pytest.approx(1.0)

    summary = _summary(output_dir)
    scale_audit = summary["policy"]["opening_observed_stock_scale"]
    assert scale_audit["mode"] == "pair_csv_overrides"
    assert scale_audit["scope"] == (
        "listed_observed_graph_inventory_states_only"
    )
    assert scale_audit["default_unlisted_pair_factor"] == pytest.approx(1.0)
    assert scale_audit["scaled_positive_state_count"] == 1
    assert scale_audit["pair_overrides"] == [
        {
            "node_id": "SDC-1450",
            "item_id": "item:021081",
            "factor": 0.1,
        }
    ]
    boundary = summary["policy"]["warmup_boundary_audit"]
    assert boundary["opening_observed_stock_scale"] == scale_audit
    assert len(boundary["core_state_sha256"]) == 64

    with (output_dir / "data" / "assumptions_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        assumption_rows = [
            entry
            for entry in csv.DictReader(handle)
            if entry["category"] == "opening_observed_stock_scale"
        ]
    assert len(assumption_rows) == 1
    assert assumption_rows[0]["node_id"] == "SDC-1450"
    assert assumption_rows[0]["item_id"] == "item:021081"
    assert json.loads(assumption_rows[0]["payload_json"])["factor"] == (
        pytest.approx(0.1)
    )


@pytest.mark.parametrize(
    ("csv_text", "message"),
    [
        (
            "node_id,item_id,scale\nN,item:X,0.5\nN,item:X,0.4\n",
            "duplicate pair",
        ),
        ("node_id,item_id,scale\nN,item:X,nan\n", "scale must be finite"),
        (
            "node_id,item_id,scale\nMISSING,item:X,0.5\n",
            "is not an inventory state",
        ),
        (
            "node_id,item_id,scale,uom\nN,item:X,0.5,UN\n",
            "columns must be exactly",
        ),
    ],
)
@pytest.mark.parametrize(
    "loader",
    [
        load_opening_observed_stock_scale_overrides,
        load_measurement_start_in_transit_scale_overrides,
        load_measurement_start_stock_scale_overrides,
    ],
)
def test_pair_csv_validation_is_strict(
    tmp_path: Path,
    csv_text: str,
    message: str,
    loader,
) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        loader(
            csv_path,
            valid_pairs={("N", "item:X")},
        )


def test_global_and_pair_csv_scales_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    scale_csv = tmp_path / "targeted.csv"
    scale_csv.write_text(
        "node_id,item_id,scale\nSDC-1450,item:021081,0.1\n",
        encoding="utf-8",
    )
    result = _run_engine(
        tmp_path / "invalid_composition",
        scale=0.5,
        scale_csv=scale_csv,
    )
    assert result.returncode != 0
    assert "are mutually exclusive" in (result.stderr + result.stdout)


def test_measurement_start_scale_is_pair_scoped_pre_audit_and_lot_balanced(
    tmp_path: Path,
) -> None:
    scale_csv = tmp_path / "measurement_start.csv"
    scale_csv.write_text(
        "node_id,item_id,scale\nM-1810,item:338929,0.1\n",
        encoding="utf-8",
    )
    baseline_dir = tmp_path / "measurement_baseline"
    adjusted_dir = tmp_path / "measurement_adjusted"
    baseline = _run_engine(baseline_dir, lot_trace=True)
    adjusted = _run_engine(
        adjusted_dir,
        measurement_scale_csv=scale_csv,
        lot_trace=True,
        skip_lot_audit=False,
    )
    assert baseline.returncode == 0, baseline.stderr or baseline.stdout
    assert adjusted.returncode == 0, adjusted.stderr or adjusted.stdout

    baseline_summary = _summary(baseline_dir)
    adjusted_summary = _summary(adjusted_dir)
    baseline_boundary = baseline_summary["policy"]["warmup_boundary_audit"]
    adjusted_boundary = adjusted_summary["policy"]["warmup_boundary_audit"]
    audit = adjusted_summary["policy"]["measurement_start_stock_scale"]
    assert adjusted_boundary["measurement_start_stock_scale"] == audit
    assert audit["application_stage"] == (
        "after_warmup_and_optional_restore_before_j0_boundary_audit"
    )
    assert audit["restart_checkpoint_available"] is False
    assert audit["adjustment_rows"] == 1
    assert audit["pair_overrides"] == [
        {"node_id": "M-1810", "item_id": "item:338929", "factor": 0.1}
    ]
    assert baseline_boundary["core_state_sha256"] != adjusted_boundary[
        "core_state_sha256"
    ]
    assert baseline_boundary["component_sha256"]["stock"] != (
        adjusted_boundary["component_sha256"]["stock"]
    )
    assert baseline_boundary["component_sha256"]["lot_ledger"] != (
        adjusted_boundary["component_sha256"]["lot_ledger"]
    )
    unchanged_components = set(baseline_boundary["component_sha256"]) - {
        "stock",
        "lot_ledger",
    }
    assert unchanged_components
    for component in unchanged_components:
        assert baseline_boundary["component_sha256"][component] == (
            adjusted_boundary["component_sha256"][component]
        )

    with (
        adjusted_dir / "data" / "measurement_start_stock_adjustments.csv"
    ).open(encoding="utf-8", newline="") as handle:
        adjustment_rows = list(csv.DictReader(handle))
    assert len(adjustment_rows) == 1
    row = adjustment_rows[0]
    assert (row["node_id"], row["item_id"]) == MRP_SNAPSHOT_PAIR
    stock_before = float(row["stock_before_qty"])
    stock_after = float(row["stock_after_qty"])
    assert stock_before > 0.0
    assert stock_after == pytest.approx(stock_before * 0.1, abs=1e-6)
    assert float(row["stock_removed_qty"]) == pytest.approx(
        stock_before - stock_after,
        abs=1e-6,
    )
    assert float(row["lot_balance_after_qty"]) == pytest.approx(
        stock_after,
        abs=1e-6,
    )
    assert row["lot_balance_matches_stock_after"] == "1"

    with (
        adjusted_dir / "data" / "production_lot_events.csv"
    ).open(encoding="utf-8", newline="") as handle:
        lot_events = [
            event
            for event in csv.DictReader(handle)
            if event["event_type"] == "measurement_start_stock_reduction"
            and (event["node_id"], event["item_id"]) == MRP_SNAPSHOT_PAIR
        ]
    assert lot_events
    assert sum(float(event["qty"]) for event in lot_events) == pytest.approx(
        float(row["lot_removed_qty"]),
        abs=1e-6,
    )
    assert (adjusted_dir / "reports" / "lot_path_audit.md").exists()

    with (adjusted_dir / "data" / "assumptions_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        assumptions = [
            entry
            for entry in csv.DictReader(handle)
            if entry["category"] == "measurement_start_stock_scale"
        ]
    assert len(assumptions) == 1
    assert (assumptions[0]["node_id"], assumptions[0]["item_id"]) == (
        MRP_SNAPSHOT_PAIR
    )


def test_measurement_start_csv_uses_same_strict_validation(
    tmp_path: Path,
) -> None:
    duplicate_csv = tmp_path / "duplicate_measurement.csv"
    duplicate_csv.write_text(
        "node_id,item_id,scale\n"
        "M-1810,item:338929,0.1\n"
        "M-1810,item:338929,0.2\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate pair"):
        load_measurement_start_stock_scale_overrides(
            duplicate_csv,
            valid_pairs={MRP_SNAPSHOT_PAIR},
        )


def test_measurement_start_in_transit_scale_is_pre_audit_and_lot_aligned(
    tmp_path: Path,
) -> None:
    scale_csv = tmp_path / "measurement_start_in_transit.csv"
    scale_csv.write_text(
        "node_id,item_id,scale\nM-1810,item:338929,0.1\n",
        encoding="utf-8",
    )
    baseline_dir = tmp_path / "transit_baseline"
    adjusted_dir = tmp_path / "transit_adjusted"
    baseline = _run_engine(baseline_dir, lot_trace=True)
    adjusted = _run_engine(
        adjusted_dir,
        measurement_in_transit_scale_csv=scale_csv,
        lot_trace=True,
        skip_lot_audit=False,
    )
    assert baseline.returncode == 0, baseline.stderr or baseline.stdout
    assert adjusted.returncode == 0, adjusted.stderr or adjusted.stdout

    baseline_summary = _summary(baseline_dir)
    adjusted_summary = _summary(adjusted_dir)
    baseline_boundary = baseline_summary["policy"]["warmup_boundary_audit"]
    adjusted_boundary = adjusted_summary["policy"]["warmup_boundary_audit"]
    audit = adjusted_summary["policy"]["measurement_start_in_transit_scale"]
    assert adjusted_boundary["measurement_start_in_transit_scale"] == audit
    assert audit["application_stage"] == (
        "after_warmup_before_j0_boundary_audit"
    )
    assert audit["restart_checkpoint_available"] is False
    assert audit["external_pipeline_unchanged"] is True
    assert audit["estimated_source_pipeline_unchanged"] is True
    assert audit["pair_overrides"] == [
        {"node_id": "M-1810", "item_id": "item:338929", "factor": 0.1}
    ]
    assert baseline_boundary["core_state_sha256"] != adjusted_boundary[
        "core_state_sha256"
    ]
    for component in ("pipeline", "in_transit"):
        assert baseline_boundary["component_sha256"][component] != (
            adjusted_boundary["component_sha256"][component]
        )
    for component in (
        "external_pipeline",
        "external_in_transit",
        "estimated_source_pipeline",
        "estimated_source_in_transit",
        "stock",
    ):
        assert baseline_boundary["component_sha256"][component] == (
            adjusted_boundary["component_sha256"][component]
        )

    adjustment_path = (
        adjusted_dir / "data" / "measurement_start_in_transit_adjustments.csv"
    )
    with adjustment_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert (row["node_id"], row["item_id"]) == MRP_SNAPSHOT_PAIR
    in_transit_before = float(row["in_transit_before_qty"])
    pipeline_before = float(row["standard_pipeline_before_qty"])
    assert in_transit_before > 0.0
    assert pipeline_before == pytest.approx(in_transit_before, abs=1e-6)
    assert float(row["in_transit_after_qty"]) == pytest.approx(
        in_transit_before * 0.1,
        abs=1e-6,
    )
    assert float(row["standard_pipeline_after_qty"]) == pytest.approx(
        pipeline_before * 0.1,
        abs=1e-6,
    )
    assert row["pipeline_matches_in_transit_before"] == "1"
    assert row["pipeline_matches_in_transit_after"] == "1"
    assert int(row["arrival_day_count"]) > 0
    assert json.loads(row["arrival_days_json"])
    if int(row["lot_payload_count"]) > 0:
        assert baseline_boundary["component_sha256"]["lot_arrivals_pipeline"] != (
            adjusted_boundary["component_sha256"]["lot_arrivals_pipeline"]
        )
        assert float(row["lot_pipeline_after_qty"]) == pytest.approx(
            float(row["lot_pipeline_before_qty"]) * 0.1,
            abs=1e-6,
        )

    with (adjusted_dir / "data" / "assumptions_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        assumptions = [
            entry
            for entry in csv.DictReader(handle)
            if entry["category"] == "measurement_start_in_transit_scale"
        ]
    assert len(assumptions) == 1
    assert json.loads(assumptions[0]["payload_json"])[
        "standard_pipeline_removed_qty"
    ] > 0.0


def test_measurement_start_in_transit_scale_rejects_increase(
    tmp_path: Path,
) -> None:
    scale_csv = tmp_path / "invalid_transit_increase.csv"
    scale_csv.write_text(
        "node_id,item_id,scale\nM-1810,item:338929,1.1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        load_measurement_start_in_transit_scale_overrides(
            scale_csv,
            valid_pairs={MRP_SNAPSHOT_PAIR},
        )


@pytest.mark.parametrize("invalid", ["-0.1", "nan", "inf", "-inf"])
def test_scale_rejects_negative_and_non_finite_values(
    tmp_path: Path,
    invalid: str,
) -> None:
    command = [
        sys.executable,
        str(ENGINE),
        f"--opening-observed-stock-scale={invalid}",
        "--output-dir",
        str(tmp_path / invalid.replace("-", "minus")),
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "must be finite and greater than or equal to 0" in result.stderr
