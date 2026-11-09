"""Explicit dated-risk scope contracts and a source-purchase oracle in memory.

No simulation, filesystem fixture, integrity alteration, or time manipulation.
"""
from collections import defaultdict
from copy import deepcopy
import sys
from unittest.mock import patch

import pytest

from etudecas.simulation.engine import run_first_simulation as engine


def test_parser_preserves_risk_rejection_default_and_accepts_explicit_scope():
    with patch.object(sys, "argv", ["simulation"]):
        assert engine.parse_args().dated_mrp_risk_scope == "reject"
    with patch.object(sys, "argv", ["simulation", "--dated-mrp-risk-scope", "preserve_opening_orders"]):
        assert engine.parse_args().dated_mrp_risk_scope == "preserve_opening_orders"


def test_nominal_dated_scope_retains_baseline_restriction():
    policy = engine.resolve_dated_mrp_risk_scope(scenario_id="scn:BASE")
    assert policy["scope"] == "reject"
    assert policy["risk_effects_scope"] == "none"
    assert policy["opening_purchase_risk_overlay"] is False


@pytest.mark.parametrize("risks", [
    {"state_dependent_risks": True},
    {"events_csv": "explicit-risk-events.csv"},
    {"supplier_risk_events": [{"event_id": "graph-event"}]},
])
def test_dated_risks_require_explicit_scope(risks):
    with pytest.raises(ValueError, match="only for BASE without risk overlays"):
        engine.resolve_dated_mrp_risk_scope(scenario_id="scn:BASE", **risks)


@pytest.mark.parametrize("risks", [
    {"state_dependent_risks": True},
    {"events_csv": "explicit-risk-events.csv"},
    {"supplier_risk_events": [{"event_id": "graph-event"}]},
])
def test_explicit_scope_accepts_simulated_risks_and_discloses_hypothesis(risks):
    policy = engine.resolve_dated_mrp_risk_scope(
        scope="preserve_opening_orders", scenario_id="scn:BASE", **risks,
    )
    assert policy == {
        "scope": "preserve_opening_orders",
        "status": "experimental_hypothesis",
        "risk_effects_scope": "simulated_operational_flows_only",
        "opening_purchase_risk_overlay": False,
        "opening_source_dates_and_quantities": "unchanged_by_simulated_risks",
        "existing_source_execution_and_replanning_policies": "unchanged",
        "industrial_calibration_claimed": False,
    }


@pytest.mark.parametrize("scope", ["reject", "preserve_opening_orders"])
def test_opening_purchase_risk_overlay_remains_forbidden(scope):
    with pytest.raises(ValueError, match="forbids risk overlays on opening purchase orders"):
        engine.resolve_dated_mrp_risk_scope(
            scope=scope, scenario_id="scn:BASE", apply_to_opening_purchase_orders=True,
        )


@pytest.mark.parametrize("scope", ["reject", "preserve_opening_orders"])
def test_nonbase_scenario_remains_forbidden(scope):
    with pytest.raises(ValueError, match="requires scn:BASE"):
        engine.resolve_dated_mrp_risk_scope(scope=scope, scenario_id="scn:RISK")


def test_unknown_scope_is_rejected():
    with pytest.raises(ValueError, match="Unknown dated MRP risk scope"):
        engine.resolve_dated_mrp_risk_scope(scope="anything", scenario_id="scn:BASE")


def test_source_purchase_dates_quantity_and_lot_are_preserved_with_risks_present():
    """10 UN: physical receipt day7, usable day9; event must change neither."""
    payload = {"source_file": "fictional-source.xlsx", "rows": [{
        "order_type": "purchase_open_order", "src_node_id": "S-DEMO",
        "dst_node_id": "F-DEMO", "item_id": "item:PACK", "quantity": 10,
        "uom": "UN", "physical_delivery_day": 7, "usable_day": 9,
        "receipt_release_days": 2, "source_row": 23,
    }]}
    original = deepcopy(payload)
    events, warnings = engine.load_supplier_risk_events(csv_path=None, scenario={
        "supplier_risk_events": [{"event_id": "availability-test", "supplier_id": "S-DEMO",
            "risk_type": "availability", "start_day": 0, "end_day": 12, "multiplier": 0.25}],
    })
    assert not warnings and len(events) == 1

    def seed(risks):
        pipeline, transit = defaultdict(list), defaultdict(float)
        orders, shipments, initialization, assumptions, audit = [], [], [], [], []
        result = engine.seed_open_orders_from_metadata(
            pipeline, transit, opening_open_orders_payload=payload,
            lanes_by_dest_item={}, item_unit_map={"item:PACK": "UN"},
            pair_mrp_safety_time_days={}, total_timeline_days=20, warmup_days=0,
            opening_production_bom_issues_by_day=None,
            opening_production_order_bom_issue_mode="receipt", mrp_order_rows=orders,
            supplier_shipment_rows=shipments, initialization_pipeline_rows=initialization,
            assumptions_ledger_rows=assumptions, supplier_risk_events=risks,
            opening_purchase_order_risk_audit_rows=audit, dated_purchase_availability=True,
            # Deliberately use the existing default: do not apply risks to initial orders.
        )
        return result, dict(pipeline), dict(transit), orders, shipments, initialization, assumptions, audit

    baseline, risky = seed([]), seed(events)
    assert risky == baseline and payload == original
    (total, opening_rows, _), pipeline, transit, *_ = risky
    assert total == 10 and transit == {("F-DEMO", "item:PACK"): 10}
    row = opening_rows[0]
    assert (row["physical_delivery_day"], row["arrival_day"], row["receipt_qty"]) == (7, 9, 10)
    assert list(pipeline) == [9] and pipeline[9][0][:3] == ("F-DEMO", "item:PACK", 10)
    assert risky[-1] == []

    availability = engine.OpeningPurchaseAvailability(opening_rows, item_unit_map={"item:PACK": "UN"})
    ledger = engine.LotLedger(enabled=True, scenario_id="scn:BASE")
    pair = ("F-DEMO", "item:PACK")
    assert availability.receive_physical(6, ledger=ledger) == {}
    assert availability.receive_physical(7, ledger=ledger) == {pair: 10}
    assert availability.held_by_pair[pair] == 10
    received = availability.rows[0]
    lot_id = received["lot_id"]
    availability.release(received["marker"], 9, 10, ledger=ledger)
    assert availability.held_by_pair[pair] == 0
    assert len(ledger.lots) == 1 and received["lot_id"] == lot_id
    assert received["quantity"] == 10 and received["released"] is True
