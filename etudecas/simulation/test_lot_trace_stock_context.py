from __future__ import annotations

from pathlib import Path

from etudecas.simulation.lot_trace.stock_context import (
    LotTraceStockContextSources,
    build_lot_trace_stock_context,
)


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> Path:
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(value) for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_stock_context_uses_input_stock_before_after_and_filters_irrelevant_rows(tmp_path: Path) -> None:
    input_csv = _write_csv(
        tmp_path / "input.csv",
        ["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
        [
            [1, "M-1", "item:A", 10.5, 4.25],
            [1, "M-1", "item:OTHER", 999, 999],
        ],
    )
    events = [{"day": 1, "node_id": "M-1", "item_id": "item:A"}]

    context = build_lot_trace_stock_context(
        events,
        [],
        LotTraceStockContextSources(input_stocks_csv=input_csv),
    )

    assert context == {
        "M-1|item:A|1": {
            "node_id": "M-1",
            "item_id": "item:A",
            "day": 1,
            "label": "stock intrant usine",
            "before_qty": 10.5,
            "after_qty": 4.25,
            "delta_qty": -6.25,
        }
    }


def test_stock_context_end_of_day_uses_previous_day_or_zero_at_day_zero(tmp_path: Path) -> None:
    dc_csv = _write_csv(
        tmp_path / "dc.csv",
        ["day", "node_id", "item_id", "stock_end_of_day"],
        [
            [0, "DC-1", "item:PF", 50],
            [1, "DC-1", "item:PF", 75],
        ],
    )
    output_csv = _write_csv(
        tmp_path / "output.csv",
        ["day", "node_id", "item_id", "stock_end_of_day"],
        [[0, "M-1", "item:PF", 100]],
    )
    events = [
        {"day": 0, "node_id": "M-1", "item_id": "item:PF"},
    ]
    genealogy = [
        {
            "day": 1,
            "parent_node_id": "M-1",
            "parent_item_id": "item:PF",
            "child_node_id": "DC-1",
            "child_item_id": "item:PF",
        }
    ]

    context = build_lot_trace_stock_context(
        events,
        genealogy,
        LotTraceStockContextSources(output_products_csv=output_csv, dc_stocks_csv=dc_csv),
    )

    assert context["M-1|item:PF|0"]["label"] == "stock produit usine fin de jour"
    assert context["M-1|item:PF|0"]["before_qty"] == 0.0
    assert context["M-1|item:PF|0"]["after_qty"] == 100.0
    assert context["DC-1|item:PF|1"]["label"] == "stock DC fin de jour"
    assert context["DC-1|item:PF|1"]["before_qty"] == 50.0
    assert context["DC-1|item:PF|1"]["after_qty"] == 75.0
    assert context["DC-1|item:PF|1"]["delta_qty"] == 25.0


def test_stock_context_customer_service_payload(tmp_path: Path) -> None:
    demand_csv = _write_csv(
        tmp_path / "demand.csv",
        ["day", "node_id", "item_id", "available_before_service_qty", "served_qty", "backlog_end_qty"],
        [[3, "C-1", "item:PF", 50, 12.5, 4]],
    )
    events = [{"day": 3, "node_id": "C-1", "item_id": "item:PF"}]

    context = build_lot_trace_stock_context(
        events,
        [],
        LotTraceStockContextSources(demand_service_csv=demand_csv),
    )

    assert context["C-1|item:PF|3"] == {
        "node_id": "C-1",
        "item_id": "item:PF",
        "day": 3,
        "label": "stock client avant/apres service",
        "before_qty": 50.0,
        "after_qty": 37.5,
        "delta_qty": -12.5,
        "served_qty": 12.5,
        "backlog_end_qty": 4.0,
    }
