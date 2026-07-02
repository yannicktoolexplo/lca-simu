from __future__ import annotations

from pathlib import Path

from etudecas.visualization.maps.sensitivity_payload import (
    align_series,
    baseline_sensitivity_row,
    case_multiplier_value,
    case_output_dir,
    case_rows_by_id,
    cumulative_series,
    first_case_row,
    kpi_from_case,
    local_signal_strength,
    multiplier_label,
    safe_case_token,
)


def test_case_lookup_keeps_only_ok_rows_and_finds_baseline() -> None:
    rows = [
        {"case_id": "baseline", "status": "ok", "value": "1"},
        {"case_id": "bad", "status": "failed", "value": "2"},
        {"case_id": "supplier_x_low", "status": "ok", "factor_value": "0,75"},
    ]

    by_case = case_rows_by_id(rows)

    assert set(by_case) == {"baseline", "supplier_x_low"}
    assert baseline_sensitivity_row(by_case) == rows[0]
    assert first_case_row(by_case, "missing", "supplier_x_low") == rows[2]
    assert case_multiplier_value(rows[2]) == 0.75


def test_case_output_dir_and_safe_token() -> None:
    assert case_output_dir({"case_output_dir": "some/run"}) == Path("some/run")
    assert case_output_dir({"case_output_dir": ""}) is None
    assert safe_case_token("SDC VD/001: item 42") == "SDC_VD_001_item_42"


def test_series_helpers() -> None:
    assert align_series([(0, 10.0), (2, 3.0)], [(1, 5.0), (2, 8.0)]) == [
        (0, -10.0),
        (1, 5.0),
        (2, 5.0),
    ]
    assert cumulative_series([(0, 2.0), (1, -0.5), (2, 3.0)]) == [
        (0, 2.0),
        (1, 1.5),
        (2, 4.5),
    ]
    assert multiplier_label(None, "fallback") == "fallback"
    assert multiplier_label(1.0, "fallback") == "Base"
    assert multiplier_label(0.75, "fallback") == "x0.75"


def test_kpi_and_local_signal_strength() -> None:
    baseline = {"kpi::fill_rate": "0.99", "kpi::ending_backlog": "10"}
    low = {"kpi::fill_rate": "0.92", "kpi::ending_backlog": "25"}
    high = {"kpi::fill_rate": "1.0", "kpi::ending_backlog": "6"}

    assert kpi_from_case(baseline, "fill_rate") == 0.99
    assert kpi_from_case({"kpi::fill_rate": "nan"}, "fill_rate") is None
    assert local_signal_strength(baseline, low, high) == (0.06999999999999995, 15.0)
