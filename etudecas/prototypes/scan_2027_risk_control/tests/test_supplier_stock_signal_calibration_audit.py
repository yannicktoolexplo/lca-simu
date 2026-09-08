from __future__ import annotations

import csv
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_stock_signal_calibration_audit as audit,
)


def _write(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fake_runner(tmp_path: Path, seed: int = 1) -> Path:
    runner = tmp_path / "runner"
    run = (
        runner
        / "cases"
        / "baseline"
        / f"baseline_metrics__seed_{seed}"
        / f"seed_{seed}"
    )
    focus = [
        ("M-1430", "item:038005", "KG", 20.0, "item:268967"),
        ("M-1810", "item:049371", "KG", 40.0, "item:268091"),
    ]
    safety = []
    stocks = []
    arrivals = []
    traces = []
    genealogy = []
    campaigns = []
    capacities = []
    for index, (node, item, uom, safety_days, output_item) in enumerate(focus):
        target = safety_days * 100.0
        safety.append(
            {
                "scope": "input_material",
                "node_id": node,
                "item_id": item,
                "uom": uom,
                "safety_time_days": safety_days,
                "planned_avg_daily_demand_qty": 100.0,
                "observed_avg_daily_flow_qty": 10.0,
                "stock_equiv_safety_time_qty": target,
                "explicit_safety_stock_qty": 0.0,
                "effective_reference_stock_qty": target,
                "safety_reference_basis": "mrp_trace_demand_signal",
            }
        )
        for day in range(audit.EXPECTED_DAYS):
            stocks.append(
                {
                    "day": day,
                    "node_id": node,
                    "item_id": item,
                    "stock_before_production": 10_000.0,
                    "stock_end_of_day": 9_990.0,
                }
            )
            arrivals.append(
                {
                    "day": day,
                    "node_id": node,
                    "item_id": item,
                    "arrived_qty": 0.0,
                    "uom": uom,
                }
            )
            traces.append(
                {
                    "day": day,
                    "node_id": node,
                    "item_id": item,
                    "target_demand_signal_qty": 100.0,
                    "bb_demand_signal_raw_qty": 10.0,
                    "gross_requirement_basis": "static_requirement_override",
                    "soft_safety_target_qty": target,
                    "recv_prev_future_qty": 0.0,
                    "inventory_position_qty": 10_000.0,
                }
            )
        campaign_id = f"CMP-{index}"
        genealogy.append(
            {
                "day": 1,
                "link_type": "production",
                "parent_node_id": node,
                "parent_item_id": item,
                "parent_qty": 7_200.0,
                "child_node_id": node,
                "child_item_id": output_item,
                "child_qty": 720_000.0,
                "production_campaign_id": campaign_id,
            }
        )
        campaigns.append(
            {
                "campaign_id": campaign_id,
                "node_id": node,
                "output_item_id": output_item,
                "actual_qty": 720_000.0,
            }
        )
        capacities.append(
            {
                "node_id": node,
                "output_item_id": output_item,
                "current_capacity_qty_per_day": 10_000.0,
            }
        )
    _write(run / "reports/mrp_safety_stock_reference.csv", list(safety[0]), safety)
    _write(run / "data/production_input_stocks_daily.csv", list(stocks[0]), stocks)
    _write(
        run / "data/production_input_replenishment_arrivals_daily.csv",
        list(arrivals[0]),
        arrivals,
    )
    _write(run / "data/mrp_trace_daily.csv", list(traces[0]), traces)
    _write(run / "data/production_lot_genealogy.csv", list(genealogy[0]), genealogy)
    _write(run / "data/production_campaigns.csv", list(campaigns[0]), campaigns)
    _write(
        run / "data/production_capacity_nominal_parameters.csv",
        list(capacities[0]),
        capacities,
    )
    return runner


def test_build_is_read_only_and_reconciles_focus(tmp_path: Path) -> None:
    runner = _fake_runner(tmp_path)
    source = runner / "cases/baseline/baseline_metrics__seed_1/seed_1/data/mrp_trace_daily.csv"
    before = audit._sha256(source)
    output = tmp_path / "audit"

    payload = audit.build(runner, output, (1,))

    assert payload["simulation_count"] == 1
    assert payload["material_count"] == 2
    assert payload["status_counts"] == {"ecart_majeur_de_calibration": 2}
    assert payload["lot_genealogy_simulation_count"] == 1
    assert payload["static_capacity_bom_formula_verified_material_count"] == 2
    assert all(row["reference_stock_cover_physical_days_mean"] in (200.0, 400.0) for row in payload["focus"])
    assert all(row["preincident_stock_covers_window_simulation_count"] == 1 for row in payload["focus"])
    assert audit._sha256(source) == before
    assert audit.validate(output)["engine_invoked"] is False


def test_build_refuses_to_overwrite(tmp_path: Path) -> None:
    runner = _fake_runner(tmp_path)
    output = tmp_path / "audit"
    audit.build(runner, output, (1,))
    with pytest.raises(FileExistsError, match="aucun écrasement"):
        audit.build(runner, output, (1,))


def test_validate_detects_modified_result(tmp_path: Path) -> None:
    runner = _fake_runner(tmp_path)
    output = tmp_path / "audit"
    audit.build(runner, output, (1,))
    (output / audit.RESULT_HTML).write_text("modifié", encoding="utf-8")
    with pytest.raises(ValueError, match="modifiée"):
        audit.validate(output)


def test_daily_series_must_be_complete_and_unique() -> None:
    complete = [{"day": str(day)} for day in range(audit.EXPECTED_DAYS)]
    assert len(audit._require_days(complete, context="test")) == audit.EXPECTED_DAYS
    with pytest.raises(ValueError, match="dupliqué"):
        audit._require_days(complete + [{"day": "0"}], context="test")
    with pytest.raises(ValueError, match="incomplète"):
        audit._require_days(complete[:-1], context="test")


def test_seed_parser_rejects_empty_value() -> None:
    assert audit._parse_seeds("1, 2") == (1, 2)
    with pytest.raises(Exception, match="Au moins une simulation"):
        audit._parse_seeds(" , ")
