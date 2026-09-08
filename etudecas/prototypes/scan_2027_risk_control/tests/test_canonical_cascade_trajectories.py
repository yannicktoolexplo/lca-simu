from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_cascade_trajectories import (
    COMPACT_OUTPUT_NAME,
    LONG_OUTPUT_NAME,
    CascadeTrajectoryError,
    PathStage,
    _validate_path_continuity,
    export_cascade_trajectories,
)


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_run(result_dir: Path, *, offset: float, days: int = 3) -> None:
    data = result_dir / "data"
    _write_csv(
        data / "production_input_replenishment_arrivals_daily.csv",
        ["day", "node_id", "item_id", "arrived_qty", "uom"],
        [
            {
                "day": day,
                "node_id": "FAC",
                "item_id": "item:RAW",
                "arrived_qty": 10 + offset + day,
                "uom": "KG",
            }
            for day in range(days)
        ],
    )
    _write_csv(
        data / "production_input_stocks_daily.csv",
        ["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
        [
            {
                "day": day,
                "node_id": "FAC",
                "item_id": "item:RAW",
                "stock_before_production": 50 + offset + day,
                "stock_end_of_day": 45 + offset + day,
            }
            for day in range(days)
        ],
    )
    _write_csv(
        data / "production_output_products_daily.csv",
        [
            "day",
            "node_id",
            "item_id",
            "produced_qty",
            "executed_qty",
            "released_qty",
            "wip_end_qty",
            "stock_end_of_day",
        ],
        [
            {
                "day": day,
                "node_id": "FAC",
                "item_id": "item:FG",
                "produced_qty": 100 + offset + day,
                "executed_qty": 105 + offset + day,
                "released_qty": 100 + offset + day,
                "wip_end_qty": 5 + offset + day,
                "stock_end_of_day": 80 + offset + day,
            }
            for day in range(days)
        ],
    )
    _write_csv(
        data / "production_demand_service_daily.csv",
        [
            "day",
            "node_id",
            "item_id",
            "demand_qty",
            "served_qty",
            "backlog_end_qty",
            "available_before_service_qty",
        ],
        [
            {
                "day": day,
                "node_id": "CLIENT",
                "item_id": "item:FG",
                "demand_qty": 20 + day,
                "served_qty": 19 + offset + day,
                "backlog_end_qty": max(0, 1 - offset),
                "available_before_service_qty": 30 + offset + day,
            }
            for day in range(days)
        ],
    )
    _write_csv(
        data / "production_supplier_shipments_daily.csv",
        [
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "shipped_qty",
            "arrival_day",
            "uom",
        ],
        [
            {
                "day": 0,
                "src_node_id": "SUP",
                "dst_node_id": "FAC",
                "item_id": "item:RAW",
                "edge_id": "edge:SUP_FAC_RAW",
                "shipped_qty": 10 + offset,
                "arrival_day": 1,
                "uom": "KG",
            },
            {
                "day": 1,
                "src_node_id": "FAC",
                "dst_node_id": "DC",
                "item_id": "item:FG",
                "edge_id": "edge:FAC_DC_FG",
                "shipped_qty": 20 + offset,
                "arrival_day": 2,
                "uom": "UN",
            },
            {
                "day": 1,
                "src_node_id": "DC",
                "dst_node_id": "CLIENT",
                "item_id": "item:FG",
                "edge_id": "edge:DC_CLIENT_FG",
                "shipped_qty": 18 + offset,
                "arrival_day": 2,
                "uom": "UN",
            },
        ],
    )
    _write_csv(
        data / "mrp_orders_daily.csv",
        [
            "day",
            "node_id",
            "item_id",
            "src_node_id",
            "dst_node_id",
            "edge_id",
            "release_qty",
            "planned_receipt_qty",
            "arrival_day",
        ],
        [
            {
                "day": 0,
                "node_id": "FAC",
                "item_id": "item:RAW",
                "src_node_id": "SUP",
                "dst_node_id": "FAC",
                "edge_id": "edge:SUP_FAC_RAW",
                "release_qty": 11 + offset,
                "planned_receipt_qty": 10 + offset,
                "arrival_day": 1,
            },
            {
                "day": 1,
                "node_id": "DC",
                "item_id": "item:FG",
                "src_node_id": "FAC",
                "dst_node_id": "DC",
                "edge_id": "edge:FAC_DC_FG",
                "release_qty": 21 + offset,
                "planned_receipt_qty": 20 + offset,
                "arrival_day": 2,
            },
            {
                "day": 1,
                "node_id": "CLIENT",
                "item_id": "item:FG",
                "src_node_id": "DC",
                "dst_node_id": "CLIENT",
                "edge_id": "edge:DC_CLIENT_FG",
                "release_qty": 19 + offset,
                "planned_receipt_qty": 18 + offset,
                "arrival_day": 2,
            },
        ],
    )
    _write_csv(
        data / "production_supplier_stock_flows_daily.csv",
        [
            "day",
            "node_id",
            "item_id",
            "uom",
            "stock_start_of_day",
            "incoming_qty",
            "outgoing_shipped_qty",
            "stock_end_of_day",
        ],
        [
            {
                "day": day,
                "node_id": "SUP",
                "item_id": "item:RAW",
                "uom": "KG",
                "stock_start_of_day": 100 + offset + day,
                "incoming_qty": 5 + day,
                "outgoing_shipped_qty": 10 + offset if day == 0 else 0,
                "stock_end_of_day": 95 + day,
            }
            for day in range(days)
        ],
    )
    _write_csv(
        data / "production_dc_stocks_daily.csv",
        ["day", "node_id", "item_id", "stock_end_of_day"],
        [
            {
                "day": day,
                "node_id": "DC",
                "item_id": "item:FG",
                "stock_end_of_day": 40 + offset + day,
            }
            for day in range(days)
        ],
    )
    _write_csv(
        data / "production_lot_events.csv",
        ["item_id", "uom"],
        [
            {"item_id": "item:RAW", "uom": "KG"},
            {"item_id": "item:FG", "uom": "UN"},
        ],
    )


def _campaign_fixture(tmp_path: Path) -> tuple[Path, list[dict[str, object]]]:
    campaign = tmp_path / "campaign"
    campaign.mkdir(parents=True)
    config = {
        "schema_version": "scan.canonical_cascade_campaign.v1",
        "campaign": {"days": 3},
        "cascades": [
            {
                "id": "cascade_demo",
                "customer_id": "CLIENT",
                "finished_item_id": "item:FG",
                "path": [
                    {
                        "kind": "transport",
                        "from": "SUP",
                        "to": "FAC",
                        "item_id": "item:RAW",
                    },
                    {
                        "kind": "transform",
                        "node_id": "FAC",
                        "input_item_id": "item:RAW",
                        "output_item_id": "item:FG",
                    },
                    {
                        "kind": "transport",
                        "from": "FAC",
                        "to": "DC",
                        "item_id": "item:FG",
                    },
                    {
                        "kind": "transport",
                        "from": "DC",
                        "to": "CLIENT",
                        "item_id": "item:FG",
                    },
                ],
                "stock_selectors": [{"item_id": "item:RAW", "uom": "KG"}],
                "solutions": [{"id": "lever"}],
            }
        ],
    }
    (campaign / "canonical_cascade_config_snapshot.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    variants = [
        ("normal", "normal", "", 0.0),
        ("incident_no_action", "incident_no_action", "", 10.0),
        ("incident_lever", "incident_with_solution", "lever", 5.0),
    ]
    rows: list[dict[str, object]] = []
    for variant_id, case_type, solution_id, variant_offset in variants:
        for seed in (1, 2):
            result_dir = campaign / "runs" / variant_id / f"seed_{seed}"
            _write_run(result_dir, offset=variant_offset + seed)
            rows.append(
                {
                    "cascade_id": "cascade_demo",
                    "variant_id": variant_id,
                    "case_type": case_type,
                    "solution_id": solution_id,
                    "seed": seed,
                    "status": "ok",
                    "result_dir": str(result_dir.resolve()),
                    "days": 3,
                }
            )
    _write_csv(
        campaign / "canonical_cascade_runs.csv",
        [
            "cascade_id",
            "variant_id",
            "case_type",
            "solution_id",
            "seed",
            "status",
            "result_dir",
            "days",
        ],
        rows,
    )
    return campaign, rows


def test_exports_strict_long_table_and_compact_seed_envelopes(tmp_path: Path) -> None:
    campaign, _ = _campaign_fixture(tmp_path)
    runs_path = campaign / "canonical_cascade_runs.csv"
    runs_digest = _digest(runs_path)
    output = tmp_path / "trajectory-output"

    manifest_path = export_cascade_trajectories(
        campaign_dir=campaign,
        output_dir=output,
    )

    assert _digest(runs_path) == runs_digest
    long_rows = _read_csv(output / LONG_OUTPUT_NAME)
    assert long_rows
    metrics = {row["metric"] for row in long_rows}
    assert {
        "transport_shipment_qty",
        "transport_arrival_qty",
        "input_replenishment_arrival_qty",
        "input_stock_before_production_qty",
        "input_stock_end_qty",
        "production_executed_qty",
        "production_released_qty",
        "production_wip_end_qty",
        "output_stock_end_qty",
        "mrp_release_qty",
        "customer_demand_qty",
        "customer_served_qty",
        "customer_backlog_end_qty",
    }.issubset(metrics)
    zero_filled = next(
        row
        for row in long_rows
        if row["variant_id"] == "normal"
        and row["seed"] == "1"
        and row["path_stage_index"] == "0"
        and row["day"] == "2"
        and row["metric"] == "transport_shipment_qty"
    )
    assert float(zero_filled["value"]) == 0.0
    assert zero_filled["source_semantics"] == "sparse_event_zero_filled"
    assert {row["uom"] for row in long_rows if row["item_id"] == "item:RAW"} == {"KG"}
    assert {row["uom"] for row in long_rows if row["item_id"] == "item:FG"} == {"UN"}

    compact = json.loads((output / COMPACT_OUTPUT_NAME).read_text(encoding="utf-8"))
    assert compact["day_axis"] == [0, 1, 2]
    variants = compact["cascades"]["cascade_demo"]["variants"]
    assert set(variants) == {"normal", "incident_no_action", "incident_lever"}
    normal_series = next(
        series
        for series in variants["normal"]["series"]
        if series["path_stage_index"] == 1
        and series["metric"] == "production_released_qty"
    )
    assert normal_series["mean"] == pytest.approx([101.5, 102.5, 103.5])
    assert normal_series["min"] == pytest.approx([101.0, 102.0, 103.0])
    assert normal_series["max"] == pytest.approx([102.0, 103.0, 104.0])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["run_count"] == 6
    assert manifest["item_uoms"] == {"item:FG": "UN", "item:RAW": "KG"}
    assert manifest["long_row_count"] == len(long_rows)


def test_path_continuity_accepts_parallel_supplier_branches_that_converge() -> None:
    stages = (
        PathStage(
            index=0,
            kind="transport",
            from_node_id="SUP-A",
            to_node_id="FAC",
            item_id="item:RAW",
        ),
        PathStage(
            index=1,
            kind="transport",
            from_node_id="SUP-B",
            to_node_id="FAC",
            item_id="item:RAW",
        ),
        PathStage(
            index=2,
            kind="transform",
            node_id="FAC",
            input_item_id="item:RAW",
            output_item_id="item:FG",
        ),
        PathStage(
            index=3,
            kind="transport",
            from_node_id="FAC",
            to_node_id="CLIENT",
            item_id="item:FG",
        ),
    )

    _validate_path_continuity(
        "parallel_suppliers",
        stages,
        customer_id="CLIENT",
        finished_item_id="item:FG",
    )


def test_path_continuity_still_rejects_unconnected_transport() -> None:
    stages = (
        PathStage(
            index=0,
            kind="transport",
            from_node_id="SUP-A",
            to_node_id="FAC",
            item_id="item:RAW",
        ),
        PathStage(
            index=1,
            kind="transport",
            from_node_id="OTHER",
            to_node_id="CLIENT",
            item_id="item:FG",
        ),
    )

    with pytest.raises(CascadeTrajectoryError, match="discontinuous"):
        _validate_path_continuity(
            "broken_path",
            stages,
            customer_id="CLIENT",
            finished_item_id="item:FG",
        )


def test_refuses_to_overwrite_any_existing_output_directory(tmp_path: Path) -> None:
    campaign, _ = _campaign_fixture(tmp_path)
    output = tmp_path / "existing-output"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("historical", encoding="utf-8")

    with pytest.raises(CascadeTrajectoryError, match="Refusing to overwrite"):
        export_cascade_trajectories(campaign_dir=campaign, output_dir=output)

    assert marker.read_text(encoding="utf-8") == "historical"


def test_rejects_missing_dense_day_without_creating_output(tmp_path: Path) -> None:
    campaign, _ = _campaign_fixture(tmp_path)
    demand_path = (
        campaign
        / "runs"
        / "normal"
        / "seed_1"
        / "data"
        / "production_demand_service_daily.csv"
    )
    rows = _read_csv(demand_path)
    _write_csv(demand_path, list(rows[0]), [row for row in rows if row["day"] != "2"])
    output = tmp_path / "not-created"

    with pytest.raises(CascadeTrajectoryError, match="dense coverage invalid"):
        export_cascade_trajectories(campaign_dir=campaign, output_dir=output)

    assert not output.exists()


def test_rejects_missing_sparse_source_and_nonfinite_value(tmp_path: Path) -> None:
    campaign, _ = _campaign_fixture(tmp_path)
    missing_path = (
        campaign / "runs" / "normal" / "seed_1" / "data" / "mrp_orders_daily.csv"
    )
    missing_path.unlink()
    output = tmp_path / "missing-sparse-output"
    with pytest.raises(CascadeTrajectoryError, match="Required MRP orders not found"):
        export_cascade_trajectories(campaign_dir=campaign, output_dir=output)
    assert not output.exists()

    campaign_2, _ = _campaign_fixture(tmp_path / "second")
    product_path = (
        campaign_2
        / "runs"
        / "normal"
        / "seed_1"
        / "data"
        / "production_output_products_daily.csv"
    )
    rows = _read_csv(product_path)
    rows[0]["executed_qty"] = "NaN"
    _write_csv(product_path, list(rows[0]), rows)
    output_2 = tmp_path / "nonfinite-output"
    with pytest.raises(CascadeTrajectoryError, match="must be finite"):
        export_cascade_trajectories(campaign_dir=campaign_2, output_dir=output_2)
    assert not output_2.exists()


def test_rejects_cross_uom_and_incomplete_paired_seed_grid(tmp_path: Path) -> None:
    campaign, _ = _campaign_fixture(tmp_path)
    shipment_path = (
        campaign
        / "runs"
        / "incident_lever"
        / "seed_2"
        / "data"
        / "production_supplier_shipments_daily.csv"
    )
    rows = _read_csv(shipment_path)
    rows[0]["uom"] = "G"
    _write_csv(shipment_path, list(rows[0]), rows)
    with pytest.raises(CascadeTrajectoryError, match="Cross-UOM conflict"):
        export_cascade_trajectories(
            campaign_dir=campaign,
            output_dir=tmp_path / "cross-uom-output",
        )

    campaign_2, _ = _campaign_fixture(tmp_path / "paired")
    runs_path = campaign_2 / "canonical_cascade_runs.csv"
    run_rows = _read_csv(runs_path)
    _write_csv(
        runs_path,
        list(run_rows[0]),
        [
            row
            for row in run_rows
            if not (row["variant_id"] == "incident_lever" and row["seed"] == "2")
        ],
    )
    with pytest.raises(CascadeTrajectoryError, match="Incomplete paired seed grid"):
        export_cascade_trajectories(
            campaign_dir=campaign_2,
            output_dir=tmp_path / "unpaired-output",
        )
