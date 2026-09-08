from __future__ import annotations

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as base,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_stock773_baseline_calibration as calibration,
)


def test_stock_states_change_only_intermediate_opening_stock() -> None:
    states = calibration.stock_states(base.read_json(base.DEFAULT_GRAPH), (180,))
    assert len(states) == 1
    state = states[0]
    assert state.regime_id == "intermediate_stock_only_180d"
    assert state.component_scale == 1
    assert state.intermediate_scale < 1
    assert state.production_open_order_removed is False
    assert state.reduced_layers == ("stock:item:773474",)


def test_candidate_selection_never_interpolates_between_lot_steps() -> None:
    rows = [
        {
            "scenario_id": "baseline_observed_order_book",
            "state_regime": "stock_180",
            "state_regime_target_cover_days": 180,
            "product_on_due_volume_proxy": 0.79,
        },
        {
            "scenario_id": "baseline_observed_order_book",
            "state_regime": "stock_240",
            "state_regime_target_cover_days": 240,
            "product_on_due_volume_proxy": 0.94,
        },
    ]
    result = calibration.target_candidate_rows(
        rows,
        targets=(0.93, 0.80),
        tolerance=0.015,
    )
    target_93, target_80 = result
    assert target_93["nearest_cover_days"] == 240
    assert target_93["within_tolerance"] is True
    assert target_80["nearest_cover_days"] == 180
    assert target_80["within_tolerance"] is True
    assert all(row["interpolation_claim_allowed"] is False for row in result)


def test_unattained_target_reports_bracket_not_fabricated_value() -> None:
    rows = [
        {
            "scenario_id": "baseline_observed_order_book",
            "state_regime": "stock_180",
            "state_regime_target_cover_days": 180,
            "product_on_due_volume_proxy": 0.70,
        },
        {
            "scenario_id": "baseline_observed_order_book",
            "state_regime": "stock_240",
            "state_regime_target_cover_days": 240,
            "product_on_due_volume_proxy": 0.96,
        },
    ]
    result = calibration.target_candidate_rows(
        rows,
        targets=(0.80,),
        tolerance=0.01,
    )[0]
    assert result["within_tolerance"] is False
    assert result["lower_bracket_cover_days"] == 180
    assert result["upper_bracket_cover_days"] == 240
    assert "bracket" in result["interpretation"]


@pytest.mark.parametrize("raw", ["", "-1", "10,-2"])
def test_invalid_cover_lists_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        calibration.parse_float_list(raw)
