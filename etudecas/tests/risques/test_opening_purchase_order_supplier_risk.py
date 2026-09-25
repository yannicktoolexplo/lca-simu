from __future__ import annotations

from collections import defaultdict

import pytest

from etudecas.simulation.engine.run_first_simulation import (
    LotLedger,
    materialize_opening_purchase_order_receipt_lot,
    opening_purchase_order_risk_overlay,
    parse_opening_purchase_order_lot_marker,
    parse_supplier_risk_event_row,
    seed_open_orders_from_metadata,
)


def _event(
    event_id: str,
    risk_type: str,
    multiplier: float,
    *,
    start_day: int = 10,
    end_day: int = 10,
    supplier_id: str = "SUP-A",
    item_id: str = "021081",
    dst_node_id: str = "SDC-1450",
) -> dict[str, object]:
    event, warning = parse_supplier_risk_event_row(
        {
            "event_id": event_id,
            "risk_type": risk_type,
            "multiplier": multiplier,
            "supplier_id": supplier_id,
            "item_id": item_id,
            "dst_node_id": dst_node_id,
            "start_day": start_day,
            "end_day": end_day,
        },
        source="test.csv",
        row_number=2,
    )
    assert warning is None
    assert event is not None
    return event


def _lane() -> dict[str, object]:
    return {
        "src": "SUP-A",
        "dst": "SDC-1450",
        "item_id": "item:021081",
        "edge_id": "EDGE-021081",
        "lead_days": 4,
        "standard_order_qty": 100.0,
        "mrp_share": 1.0,
    }


def test_opening_po_overlay_separates_transport_quality_and_quantity_losses() -> None:
    overlay = opening_purchase_order_risk_overlay(
        planned_qty=100.0,
        planned_physical_delivery_day=10,
        planned_usable_day=12,
        release_day=6,
        lane=_lane(),
        supplier_risk_events=[
            _event("transport", "lead_time_extra_days", 5.0),
            _event("quality-delay", "quality_delay", 7.0),
            _event("availability", "availability", 0.5),
            _event("reliability", "reliability", 0.8),
            _event("quality-yield", "quality_yield", 0.75),
        ],
    )

    assert overlay["risk_decision_day"] == 10
    assert overlay["physical_delivery_day"] == 15
    assert overlay["usable_day"] == 24
    assert overlay["receipt_release_days"] == 9
    assert overlay["pulled_qty"] == pytest.approx(100.0)
    assert overlay["physical_shipped_qty"] == pytest.approx(40.0)
    assert overlay["usable_qty"] == pytest.approx(30.0)
    assert overlay["unsupported_risk_types"] == []


def test_opening_po_overlay_uses_planned_physical_day_and_flags_capacity() -> None:
    overlay = opening_purchase_order_risk_overlay(
        planned_qty=100.0,
        planned_physical_delivery_day=10,
        planned_usable_day=12,
        release_day=6,
        lane=_lane(),
        supplier_risk_events=[
            _event("capacity", "capacity", 0.2),
            _event("wrong-date", "availability", 0.1, start_day=11, end_day=20),
            _event("wrong-supplier", "reliability", 0.1, supplier_id="SUP-B"),
        ],
    )

    assert overlay["event_ids"] == ["capacity"]
    assert overlay["unsupported_risk_types"] == ["capacity"]
    assert overlay["physical_delivery_day"] == 10
    assert overlay["usable_day"] == 12
    assert overlay["usable_qty"] == pytest.approx(100.0)


def _seed(*, enabled: bool) -> dict[str, object]:
    pipeline: dict[int, list[tuple[str, str, float, str]]] = defaultdict(list)
    in_transit: dict[tuple[str, str], float] = defaultdict(float)
    mrp_rows: list[dict[str, object]] = []
    shipment_rows: list[dict[str, object]] = []
    init_rows: list[dict[str, object]] = []
    assumption_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    warnings: list[str] = []
    applied_rows: list[dict[str, object]] = []
    payload = {
        "source_file": "Extract_En_cours.xlsx",
        "rows": [
            {
                "source_row": 23,
                "order_type": "purchase_open_order",
                "src_node_id": "SUP-A",
                "dst_node_id": "SDC-1450",
                "item_id": "item:021081",
                "quantity": 100.0,
                "uom": "KG",
                "physical_delivery_day": 10,
                "usable_day": 12,
                "receipt_release_days": 2,
                "planning_element": "O.Achat",
            }
        ],
    }
    seeded_qty, open_rows, _ = seed_open_orders_from_metadata(
        pipeline,
        in_transit,
        opening_open_orders_payload=payload,
        lanes_by_dest_item={("SDC-1450", "item:021081"): [_lane()]},
        item_unit_map={"item:021081": "KG"},
        pair_mrp_safety_time_days={},
        total_timeline_days=40,
        warmup_days=0,
        opening_production_bom_issues_by_day=defaultdict(list),
        opening_production_order_bom_issue_mode="receipt",
        mrp_order_rows=mrp_rows,
        supplier_shipment_rows=shipment_rows,
        initialization_pipeline_rows=init_rows,
        assumptions_ledger_rows=assumption_rows,
        apply_supplier_risks_to_opening_purchase_orders=enabled,
        supplier_risk_events=[
            _event("transport", "lead_time_extra_days", 5.0),
            _event("quality", "quality_delay", 7.0),
            _event("availability", "availability", 0.5),
        ],
        opening_purchase_order_risk_audit_rows=audit_rows,
        opening_purchase_order_risk_warnings=warnings,
        supplier_risk_applied_rows=applied_rows,
    )
    return {
        "pipeline": pipeline,
        "in_transit": in_transit,
        "mrp": mrp_rows,
        "shipments": shipment_rows,
        "init": init_rows,
        "audit": audit_rows,
        "applied": applied_rows,
        "seeded_qty": seeded_qty,
        "open_rows": open_rows,
    }


def test_opening_po_risk_replay_is_strictly_opt_in() -> None:
    baseline = _seed(enabled=False)

    assert baseline["seeded_qty"] == pytest.approx(100.0)
    assert list(baseline["pipeline"]) == [12]
    assert baseline["pipeline"][12][0] == (
        "SDC-1450",
        "item:021081",
        100.0,
        "",
    )
    assert baseline["audit"] == []
    assert baseline["applied"] == []
    assert "shipment_id" not in baseline["shipments"][0]
    assert "risk_event_ids" not in baseline["mrp"][0]


def test_opening_po_risk_replay_seeds_traceable_receipt_lot() -> None:
    replay = _seed(enabled=True)

    assert replay["seeded_qty"] == pytest.approx(50.0)
    assert list(replay["pipeline"]) == [24]
    dst, item_id, qty, marker = replay["pipeline"][24][0]
    assert qty == pytest.approx(50.0)
    marker_payload = parse_opening_purchase_order_lot_marker(marker)
    assert marker_payload is not None
    assert marker_payload["source_row"] == "23"
    assert marker_payload["supplier_id"] == "SUP-A"
    assert marker_payload["shipment_id"] == "opening_po_sr23"
    assert marker_payload["risk_event_ids"] == "transport,quality,availability"

    shipment = replay["shipments"][0]
    assert shipment["pulled_qty"] == pytest.approx(100.0)
    assert shipment["shipped_qty"] == pytest.approx(50.0)
    assert shipment["arrival_day"] == 24
    assert replay["audit"][0]["physical_delivery_day_before"] == 10
    assert replay["audit"][0]["physical_delivery_day_after"] == 15
    assert replay["audit"][0]["usable_day_after"] == 24
    assert len(replay["applied"]) == 1

    ledger = LotLedger(enabled=True)
    lot_id = materialize_opening_purchase_order_receipt_lot(
        ledger,
        day=24,
        node_id=dst,
        item_id=item_id,
        qty=qty,
        uom="KG",
        marker=marker,
    )
    assert lot_id
    assert ledger.lots[lot_id]["source_row"] == "23"
    assert ledger.lots[lot_id]["supplier_id"] == "SUP-A"
    event = ledger.event_rows[-1]
    assert event["source_type"] == "opening_purchase_order_receipt"
    assert event["source_id"] == "Extract_En_cours.xlsx:row:23;supplier:SUP-A"
    assert event["risk_event_ids"] == "transport,quality,availability"

    allocations = ledger.consume(
        day=25,
        node_id=dst,
        item_id=item_id,
        qty=10.0,
        event_type="production_consume",
    )
    assert allocations[0]["source_row"] == "23"
    assert allocations[0]["supplier_id"] == "SUP-A"
