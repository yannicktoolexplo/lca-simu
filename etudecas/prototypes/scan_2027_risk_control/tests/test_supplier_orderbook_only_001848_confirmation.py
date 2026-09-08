from __future__ import annotations

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_orderbook_only_001848_confirmation as confirmation,
)


def test_confirmation_scope_is_only_screening_effect() -> None:
    assert confirmation.LANE.lane_id == "vd0951020a_001848_m1810"
    assert confirmation.COVERS == (90.0, 30.0)
    assert [scenario.scenario_id for scenario in confirmation.SCENARIOS] == [
        "baseline_orderbook_replay",
        "delivery_availability_0p25",
    ]


def test_outcome_signature_normalizes_csv_numbers() -> None:
    row = {
        "opening_order_usable_qty": "1500.0",
        "descendant_signature_sha256": "abc",
        "product_on_due_volume_proxy": "0.999",
        "product_released_qty": "100",
    }
    typed = {
        "opening_order_usable_qty": 1500,
        "descendant_signature_sha256": "abc",
        "product_on_due_volume_proxy": 0.999,
        "product_released_qty": 100.0,
    }
    assert confirmation._outcome_signature(row) == confirmation._outcome_signature(
        typed
    )


def test_signature_detects_descendant_change_without_client_change() -> None:
    baseline = {
        "descendant_signature_sha256": "baseline",
        "product_on_due_volume_proxy": 0.99,
    }
    stress = {
        "descendant_signature_sha256": "stress",
        "product_on_due_volume_proxy": 0.99,
    }
    assert confirmation._outcome_signature(baseline) != confirmation._outcome_signature(
        stress
    )
