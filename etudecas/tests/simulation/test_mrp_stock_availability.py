"""Pure in-memory oracles for held opening stock; no filesystem fixtures."""
from __future__ import annotations

from copy import deepcopy
import csv
from io import StringIO
import pytest

from etudecas.simulation.engine import run_first_simulation as engine


PAIR = ("M-1", "item:1")


def make_state(*, quantity=4, release_day=3, knowledge_date="2025-01-01", assumption="", rows=None):
    stock = {PAIR: 10.0}
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock=stock, item_unit_map={"item:1": "UN"})
    payload = {
        "schema_version": 1,
        "knowledge_date": knowledge_date,
        "assumption": assumption,
        "rows": rows if rows is not None else [{
            "node_id": "M-1", "item_id": "item:1", "quantity": quantity,
            "uom": "UN", "release_day": release_day, "source_row": "MRP!J2",
        }],
    }
    availability = engine.InitialStockAvailability(
        payload, stock=stock, item_unit_map={"item:1": "UN"}, origin_date="2025-01-01"
    )
    availability.initialize(stock=stock, ledger=ledger)
    return stock, ledger, availability


def test_held_stock_release_conserves_physical_lot_and_blocks_reservation():
    stock, ledger, availability = make_state()
    lot_id = next(iter(ledger.lots))
    assert stock[PAIR] == 6
    assert availability.held_by_pair[PAIR] == 4
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 10
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=0, node_id=PAIR[0], item_id=PAIR[1], qty=7,
                       event_type="shipment_reserve", uom="UN")
    assert len(ledger.lots) == 1
    assert availability.release(2, stock=stock, ledger=ledger) == {}
    assert availability.release(3, stock=stock, ledger=ledger) == {PAIR: 4}
    assert stock[PAIR] == 10
    assert availability.held_by_pair[PAIR] == 0
    assert list(ledger.lots) == [lot_id]
    assert ledger.lots[lot_id]["qty_remaining"] == 10
    assert availability.release(3, stock=stock, ledger=ledger) == {}
    assert [row["event_type"] for row in ledger.event_rows] == [
        "opening_stock", "stock_availability_hold", "stock_availability_release"
    ]
    assert {row["qty_after"] for row in ledger.event_rows} == {10}
    assert ledger.genealogy_rows == []


def test_fifo_skips_held_stock_then_reuses_same_lot_after_release():
    stock, ledger, availability = make_state(quantity=10)
    opening_id = next(iter(ledger.lots))
    later_id = ledger.create_lot(day=1, node_id=PAIR[0], item_id=PAIR[1], qty=3,
                                 source_type="lane_receipt", event_type="lane_receipt", uom="UN")
    allocations = ledger.consume(day=1, node_id=PAIR[0], item_id=PAIR[1], qty=3,
                                 event_type="production_consume", uom="UN")
    assert [(row["lot_id"], row["qty"]) for row in allocations] == [(later_id, 3)]
    assert ledger.lots[opening_id]["qty_remaining"] == 10
    availability.release(3, stock=stock, ledger=ledger)
    allocations = ledger.consume(day=3, node_id=PAIR[0], item_id=PAIR[1], qty=4,
                                 event_type="production_consume", uom="UN")
    assert [(row["lot_id"], row["qty"]) for row in allocations] == [(opening_id, 4)]
    assert ledger.lots[opening_id]["qty_remaining"] == 6


def test_planner_counts_only_known_releases_within_dated_cover():
    stock, ledger, availability = make_state()
    assert availability.planning_quantity(PAIR, decision_day=0, through_day=2) == 0
    assert availability.planning_quantity(PAIR, decision_day=0, through_day=3) == 4
    availability.release(3, stock=stock, ledger=ledger)
    assert availability.planning_quantity(PAIR, decision_day=3, through_day=9) == 0
    assert stock[PAIR] == 10


def test_partial_consumption_and_two_releases_keep_one_physical_lot():
    rows = [{"node_id": PAIR[0], "item_id": PAIR[1], "quantity": qty,
             "uom": "UN", "release_day": day, "source_row": source}
            for qty, day, source in [(4, 3, "MRP!J2"), (2, 5, "MRP!J3")]]
    stock, ledger, availability = make_state(rows=rows)
    assert stock[PAIR] == 4
    ledger.consume(day=1, node_id=PAIR[0], item_id=PAIR[1], qty=3,
                   event_type="demand_service", uom="UN")
    stock[PAIR] -= 3
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 7
    availability.release(3, stock=stock, ledger=ledger)
    assert (stock[PAIR], availability.held_by_pair[PAIR]) == (5, 2)
    ledger.consume(day=4, node_id=PAIR[0], item_id=PAIR[1], qty=5,
                   event_type="demand_service", uom="UN")
    stock[PAIR] -= 5
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 2
    availability.release(5, stock=stock, ledger=ledger)
    assert (stock[PAIR], availability.held_by_pair[PAIR]) == (2, 0)
    assert len(ledger.lots) == 1
    assert all(row["event_type"] != "stock_reconciliation" for row in ledger.event_rows)


@pytest.mark.parametrize("quantity,release_day", [(11, 3), (1.5, 3), (float("nan"), 3),
                                                (float("inf"), 3), (-1, 3), (4, -1), (4, 1.5)])
def test_invalid_physical_quantities_and_dates_are_rejected(quantity, release_day):
    with pytest.raises(ValueError):
        make_state(quantity=quantity, release_day=release_day)


def test_future_knowledge_requires_named_backcast_assumption():
    with pytest.raises(ValueError, match="knowledge"):
        make_state(knowledge_date="2025-01-05")
    _, _, availability = make_state(knowledge_date="2025-01-05", release_day=11,
        assumption="backcast_first_snapshot_for_separate_experiment")
    assert availability.knowledge_day == 4
    assert availability.effective_knowledge_day == 0
    assert availability.planning_quantity(PAIR, decision_day=0, through_day=11) == 4


def test_duplicate_source_and_cumulative_overallocation_are_rejected():
    row = {"node_id": PAIR[0], "item_id": PAIR[1], "quantity": 6,
           "uom": "UN", "release_day": 3, "source_row": "MRP!J2"}
    with pytest.raises(ValueError, match="source"):
        make_state(rows=[row, deepcopy(row)])
    other = {**row, "source_row": "MRP!J3"}
    with pytest.raises(ValueError, match="physical"):
        make_state(rows=[row, other])


def test_default_ledger_has_no_availability_fields_or_events():
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={PAIR: 10}, item_unit_map={PAIR[1]: "UN"})
    ledger.consume(day=0, node_id=PAIR[0], item_id=PAIR[1], qty=3,
                   event_type="demand_service", uom="UN")
    assert [row["qty_after"] for row in ledger.event_rows] == [10, 7]
    assert all("held_qty" not in row for row in ledger.event_rows)
    assert "qty_held" not in next(iter(ledger.lots.values()))


@pytest.mark.parametrize("horizon_days,release_day", [(2, 5), (2, 1), (366, 365)])
def test_material_balance_includes_held_stock_until_its_dated_release(horizon_days, release_day):
    from etudecas.visualization.maps.simulation_payload import apply_physical_material_balances

    last = horizon_days - 1
    row = {"scope": "material", "node_id": "M", "item_id": "RM", "unit": "UN",
           "consumed_qty": 99, "planned_qty": 3, "yearly": {"1": {"consumed_qty": 99}}}
    if horizon_days > 365:
        row["yearly"]["2"] = {"consumed_qty": 99}
    def event(kind, qty, day):
        return {"node_id": "M", "item_id": "RM", "uom": "UN",
                "event_type": kind, "qty": qty, "day": day}
    events = [event("opening_stock", 10, 0), event("stock_availability_hold", 4, 0),
              event("stock_availability_release", 4, release_day),
              event("lane_receipt", 2, last), event("production_consume", 3, last)]
    stocks = [{"node_id": "M", "item_id": "RM", "day": last,
               "stock_end_of_day": 9 if release_day <= last else 5}]
    if horizon_days > 365:
        stocks.insert(0, {"node_id": "M", "item_id": "RM", "day": 364, "stock_end_of_day": 6})
    apply_physical_material_balances([row], events, stocks,
                                     horizon_days=horizon_days, source_available=True)
    assert row["balance_status"] == "reconciled"
    assert row["initial_qty"] == 10
    assert row["delivered_qty"] == 2
    assert row["consumed_qty"] == 3
    assert row["stock_outflow_qty"] == 0
    assert row["stock_adjustment_qty"] == 0
    assert row["final_stock_qty"] == 9  # Independent oracle: 10 + 2 - 3.
    assert row["balance_gap_qty"] == 0
    assert row["theoretical_consumed_qty"] == 99
    if horizon_days > 365:
        assert row["yearly"]["1"]["final_stock_qty"] == 10
        assert row["yearly"]["2"]["initial_qty"] == 10


def opening_purchase_row(*, quantity=100, physical_day=2, available_day=5, source_row=2):
    return {
        "order_type": "opening_purchase_order", "node_id": PAIR[0], "item_id": PAIR[1],
        "receipt_qty": quantity, "physical_delivery_day": physical_day,
        "arrival_day": available_day, "source_file": "orders.xlsx", "source_row": source_row,
        "src_node_id": "S-1", "edge_id": "S-1->M-1",
    }


def test_opening_purchase_physical_receipt_and_release_keep_one_lot():
    row = opening_purchase_row()
    original = deepcopy(row)
    ledger = engine.LotLedger(enabled=True)
    available = 0
    calendar = engine.OpeningPurchaseAvailability([row], item_unit_map={PAIR[1]: "UN"})
    marker = calendar.marker_for("orders.xlsx", 2)
    assert calendar.receive_physical(1, ledger=ledger) == {}
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 0
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 100}
    lot_id = next(iter(ledger.lots))
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 100
    assert calendar.held_by_pair[PAIR] == 100
    assert available + calendar.held_by_pair[PAIR] == 100
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=3, node_id=PAIR[0], item_id=PAIR[1], qty=1,
                       event_type="production_consume", uom="UN")
    assert calendar.receive_physical(4, ledger=ledger) == {}
    calendar.release(marker, 5, 100, ledger=ledger)
    available += 100  # The execution caller credits availability once at I.
    assert available + calendar.held_by_pair[PAIR] == 100
    assert list(ledger.lots) == [lot_id]
    assert ledger.lots[lot_id]["qty_remaining"] == 100
    assert ledger.lots[lot_id]["qty_held"] == 0
    assert [(e["event_type"], e["day"], e["qty"]) for e in ledger.event_rows] == [
        ("opening_purchase_order_receipt", 2, 100),
        ("stock_availability_hold", 2, 100),
        ("stock_availability_release", 5, 100),
    ]
    assert ledger.genealogy_rows == []
    assert row == original


def test_opening_purchase_hold_targets_new_lot_and_preserves_older_available_stock():
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={PAIR: 20}, item_unit_map={PAIR[1]: "UN"})
    old_id = next(iter(ledger.lots))
    calendar = engine.OpeningPurchaseAvailability([opening_purchase_row()], item_unit_map={PAIR[1]: "UN"})
    calendar.receive_physical(2, ledger=ledger)
    new_id = next(k for k in ledger.lots if k != old_id)
    allocations = ledger.consume(day=3, node_id=PAIR[0], item_id=PAIR[1], qty=20,
                                 event_type="production_consume", uom="UN")
    assert [(a["lot_id"], a["qty"]) for a in allocations] == [(old_id, 20)]
    assert ledger.lots[new_id]["qty_remaining"] == 100
    assert ledger.lots[new_id]["qty_held"] == 100
    calendar.release(calendar.marker_for("orders.xlsx", 2), 5, 100, ledger=ledger)
    allocations = ledger.consume(day=5, node_id=PAIR[0], item_id=PAIR[1], qty=7,
                                 event_type="production_consume", uom="UN")
    assert [(a["lot_id"], a["qty"]) for a in allocations] == [(new_id, 7)]
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 93


def test_opening_purchase_same_day_delivery_and_availability_is_one_receipt():
    ledger = engine.LotLedger(enabled=True)
    calendar = engine.OpeningPurchaseAvailability(
        [opening_purchase_row(physical_day=0, available_day=0)], item_unit_map={PAIR[1]: "UN"})
    calendar.receive_physical(0, ledger=ledger)
    calendar.release(calendar.marker_for("orders.xlsx", 2), 0, 100, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0
    assert len(ledger.lots) == 1
    assert sum(e["qty"] for e in ledger.event_rows if e["event_type"] == "opening_purchase_order_receipt") == 100
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 100


@pytest.mark.parametrize("operation", ["duplicate_receipt", "early_release", "late_release", "wrong_quantity", "duplicate_release"])
def test_opening_purchase_invalid_repeated_transition_does_not_mutate_state(operation):
    ledger = engine.LotLedger(enabled=True)
    calendar = engine.OpeningPurchaseAvailability([opening_purchase_row()], item_unit_map={PAIR[1]: "UN"})
    marker = calendar.marker_for("orders.xlsx", 2)
    calendar.receive_physical(2, ledger=ledger)
    if operation == "duplicate_release":
        calendar.release(marker, 5, 100, ledger=ledger)
    snapshot = deepcopy((ledger.lots, ledger.event_rows, dict(calendar.held_by_pair), calendar.rows))
    with pytest.raises(ValueError):
        if operation == "duplicate_receipt":
            calendar.receive_physical(2, ledger=ledger)
        else:
            calendar.release(marker, 4 if operation == "early_release" else 6 if operation == "late_release" else 5,
                             101 if operation == "wrong_quantity" else 100, ledger=ledger)
    assert (ledger.lots, ledger.event_rows, dict(calendar.held_by_pair), calendar.rows) == snapshot


def test_two_opening_orders_keep_independent_lots_and_release_dates():
    rows = [opening_purchase_row(quantity=40, available_day=4),
            opening_purchase_row(quantity=60, available_day=7, source_row=3)]
    ledger = engine.LotLedger(enabled=True)
    calendar = engine.OpeningPurchaseAvailability(rows, item_unit_map={PAIR[1]: "UN"})
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 100}
    assert len(ledger.lots) == 2
    calendar.release(calendar.marker_for("orders.xlsx", 2), 4, 40, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 60
    allocations = ledger.consume(day=4, node_id=PAIR[0], item_id=PAIR[1], qty=40,
                                 event_type="production_consume", uom="UN")
    assert len(allocations) == 1
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 60
    calendar.release(calendar.marker_for("orders.xlsx", 3), 7, 60, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0
    assert sum(e["qty"] for e in ledger.event_rows if e["event_type"] == "opening_purchase_order_receipt") == 100


@pytest.mark.parametrize("field,value", [
    ("receipt_qty", None), ("receipt_qty", float("nan")), ("receipt_qty", float("inf")),
    ("receipt_qty", -1), ("receipt_qty", 1.5), ("receipt_qty", True),
    ("physical_delivery_day", None), ("physical_delivery_day", -1), ("physical_delivery_day", 2.5),
    ("physical_delivery_day", True), ("arrival_day", 1), ("arrival_day", None),
    ("source_file", None), ("source_file", ""), ("source_row", None), ("source_row", ""),
])
def test_opening_purchase_missing_or_invalid_source_fields_are_rejected(field, value):
    row = opening_purchase_row()
    row[field] = value
    with pytest.raises(ValueError):
        engine.OpeningPurchaseAvailability([row], item_unit_map={PAIR[1]: "UN"})


def test_opening_purchase_duplicate_source_rejected_but_identical_distinct_rows_preserved():
    row = opening_purchase_row()
    with pytest.raises(ValueError):
        engine.OpeningPurchaseAvailability([row, deepcopy(row)], item_unit_map={PAIR[1]: "UN"})
    second = {**row, "source_row": 3}
    calendar = engine.OpeningPurchaseAvailability([row, second], item_unit_map={PAIR[1]: "UN"})
    ledger = engine.LotLedger(enabled=True)
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 200}
    assert len(ledger.lots) == 2


def test_opening_purchase_noncountable_quantity_keeps_precision():
    ledger = engine.LotLedger(enabled=True)
    calendar = engine.OpeningPurchaseAvailability(
        [opening_purchase_row(quantity=1.25)], item_unit_map={PAIR[1]: "KG"})
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 1.25}
    calendar.release(calendar.marker_for("orders.xlsx", 2), 5, 1.25, ledger=ledger)
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 1.25


@pytest.mark.parametrize("unit", [None, "", " "])
def test_opening_purchase_missing_unit_is_not_inferred(unit):
    with pytest.raises(ValueError):
        engine.OpeningPurchaseAvailability([opening_purchase_row()], item_unit_map={PAIR[1]: unit})


def test_opening_purchase_disabled_ledger_keeps_operational_held_state():
    ledger = engine.LotLedger(enabled=False)
    calendar = engine.OpeningPurchaseAvailability([opening_purchase_row()], item_unit_map={PAIR[1]: "UN"})
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 100}
    assert calendar.held_by_pair[PAIR] == 100
    calendar.release(calendar.marker_for("orders.xlsx", 2), 5, 100, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0
    assert ledger.lots == {}
    assert ledger.event_rows == []


def opening_purchase_audit_records():
    # This is a plain in-memory CSV-shaped example, independent of the engine's
    # receipt register and marker helper. No files are created or modified.
    marker = 'OPENING_DATED_PURCHASE|["orders.xlsx","2"]'
    order = {"order_type": "opening_purchase_order", "mrp_order_id": marker,
             "source_file": "orders.xlsx", "source_row": "2", "node_id": PAIR[0], "item_id": PAIR[1],
             "physical_delivery_day": "2", "available_day": "5", "arrival_day": "5",
             "planned_receipt_qty": "100", "actual_physical_receipt_day": "2", "actual_available_day": "5"}
    events = [{"event_id": f"E-{i}", "event_type": kind, "source_id": marker, "lot_id": "LOT-1",
               "day": str(day), "qty": "100", "node_id": PAIR[0], "item_id": PAIR[1]}
              for i, (kind, day) in enumerate([
                  ("opening_purchase_order_receipt", 2), ("stock_availability_hold", 2),
                  ("stock_availability_release", 5)])]
    return order, events


def test_opening_purchase_audit_accepts_one_source_receipt_and_same_lot_release():
    from etudecas.testing.independent_review import Evidence, audit_opening_purchase_availability
    order, events = opening_purchase_audit_records()
    evidence = Evidence()
    assert audit_opening_purchase_availability([order], events, 10, evidence) == 1
    assert all(result["failed"] == 0 for result in evidence.checks.values())


@pytest.mark.parametrize("defect,expected_failure", [
    ("renamed_source", "opening_purchase_source_provenance"),
    ("empty_lot", "opening_purchase_nonempty_lot_identity"),
    ("zero_quantity", "opening_purchase_positive_quantity"),
])
def test_opening_purchase_audit_rejects_consistent_but_invalid_identity_or_quantity(defect, expected_failure):
    from etudecas.testing.independent_review import Evidence, audit_opening_purchase_availability
    order, events = opening_purchase_audit_records()
    if defect == "renamed_source":
        order["mrp_order_id"] = "ARBITRARY_MATCHING_ID"
        for event in events:
            event["source_id"] = "ARBITRARY_MATCHING_ID"
    elif defect == "empty_lot":
        for event in events:
            event["lot_id"] = ""
    else:
        order["planned_receipt_qty"] = "0"
        for event in events:
            event["qty"] = "0"
    evidence = Evidence()
    audit_opening_purchase_availability([order], events, 10, evidence)
    assert evidence.checks[expected_failure]["failed"] > 0


def test_opening_purchase_audit_does_not_require_release_beyond_horizon():
    from etudecas.testing.independent_review import Evidence, audit_opening_purchase_availability
    order, events = opening_purchase_audit_records()
    order["actual_available_day"] = ""
    evidence = Evidence()
    audit_opening_purchase_availability([order], events[:2], 5, evidence)
    assert all(result["failed"] == 0 for result in evidence.checks.values())


@pytest.mark.parametrize("physical_day,receipt_days,expected", [
    (2, 1, 5),   # Friday Jan03 -> Monday Jan06.
    (3, 1, 5),   # Saturday Jan04 -> Monday Jan06.
    (4, 0, 4),   # Zero delay does not move Sunday's physical arrival.
    (2, 5, 9),   # Friday Jan03 -> Friday Jan10.
    (42, 6, 50), # FIA42 once -> Wed Feb12; six weekdays -> Thu Feb20.
    (119, 1, 120), # Apr30 -> May01: this candidate excludes no holidays.
])
def test_supplier_receipt_calendar_counts_only_following_weekdays(physical_day, receipt_days, expected):
    assert engine.supplier_receipt_available_day(physical_day, receipt_days, origin_date="2025-01-01") == expected


@pytest.mark.parametrize("physical_day,receipt_days", [(None, 1), (1.5, 1), (True, 1), (-1, 1),
                                                     (2, None), (2, 1.5), (2, True), (2, -1)])
def test_supplier_receipt_calendar_does_not_impute_or_round_source_days(physical_day, receipt_days):
    with pytest.raises(ValueError):
        engine.supplier_receipt_available_day(physical_day, receipt_days, origin_date="2025-01-01")


@pytest.mark.parametrize("origin,calendar", [(None, "monday_friday"), ("invalid", "monday_friday"),
                                             ("2025-01-01", "calendar_days"), ("2025-01-01", "company_holidays")])
def test_supplier_receipt_calendar_requires_named_supported_convention(origin, calendar):
    with pytest.raises(ValueError):
        engine.supplier_receipt_available_day(2, 1, origin_date=origin, calendar=calendar)


def aggregate_supplier_order():
    return {**opening_purchase_row(physical_day=42, available_day=50),
            "order_type": "external_procurement_supplier_delivery", "mrp_order_id": "SUPPLIER-ORDER-1",
            "source_file": "FIA.xlsx;Flow_Data_MRP_results.xlsx", "source_row": "FIA!F2;Feuille1!E3"}


def test_aggregate_supplier_receipt_has_one_destination_lot_and_no_invented_departure():
    ledger = engine.LotLedger(enabled=True)
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={PAIR[1]: "UN"})
    raw = aggregate_supplier_order()
    original = deepcopy(raw)
    calendar.add_order(raw)
    assert calendar.receive_physical(41, ledger=ledger) == {}
    assert calendar.receive_physical(42, ledger=ledger) == {PAIR: 100}
    lot_id = next(iter(ledger.lots))
    assert calendar.held_by_pair[PAIR] == 100
    assert ledger.pair_balance(node_id="S-1", item_id=PAIR[1]) == 0
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 100
    receipt = next(e for e in ledger.event_rows if e["event_type"] == "external_procurement_receipt")
    assert receipt["source_type"] == "supplier_delivery_receipt"
    assert receipt["planned_order_id"] == "SUPPLIER-ORDER-1"
    assert receipt["supplier_id"] == "S-1"
    assert receipt["departure_day"] == ""
    assert receipt["shipment_id"] == ""
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=49, node_id=PAIR[0], item_id=PAIR[1], qty=1,
                       event_type="production_consume", uom="UN")
    calendar.release("SUPPLIER-ORDER-1", 50, 100, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0
    assert list(ledger.lots) == [lot_id]
    assert [(e["event_type"], e["day"]) for e in ledger.event_rows] == [
        ("external_procurement_receipt", 42), ("stock_availability_hold", 42), ("stock_availability_release", 50)]
    assert sum(e["qty"] for e in ledger.event_rows if e["event_type"] == "external_procurement_receipt") == 100
    assert raw == original


def test_aggregate_supplier_duplicate_order_is_rejected_without_adding_commitment():
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={PAIR[1]: "UN"})
    raw = aggregate_supplier_order()
    calendar.add_order(raw)
    before = deepcopy(calendar.rows)
    with pytest.raises(ValueError):
        calendar.add_order(deepcopy(raw))
    assert calendar.rows == before
    ledger = engine.LotLedger(enabled=True)
    assert calendar.receive_physical(42, ledger=ledger) == {PAIR: 100}


def test_aggregate_supplier_two_orders_from_same_policy_are_not_deduplicated():
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={PAIR[1]: "UN"})
    first = aggregate_supplier_order()
    second = {**first, "mrp_order_id": "SUPPLIER-ORDER-2", "receipt_qty": 50}
    calendar.add_order(first)
    calendar.add_order(second)
    ledger = engine.LotLedger(enabled=True)
    assert calendar.receive_physical(42, ledger=ledger) == {PAIR: 150}
    assert len(ledger.lots) == 2
    calendar.release("SUPPLIER-ORDER-1", 50, 100, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 50
    calendar.release("SUPPLIER-ORDER-2", 50, 50, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0


@pytest.mark.parametrize("field,value", [("mrp_order_id", ""), ("mrp_order_id", None),
                                        ("src_node_id", ""), ("source_row", None),
                                        ("arrival_day", 41), ("receipt_qty", 1.5)])
def test_aggregate_supplier_missing_identity_or_invalid_state_is_rejected(field, value):
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={PAIR[1]: "UN"})
    row = aggregate_supplier_order()
    row[field] = value
    with pytest.raises(ValueError):
        calendar.add_order(row)
    assert calendar.rows == []


@pytest.mark.parametrize("aggregate", [False, True])
def test_dated_receipt_and_descendant_export_roundtrip_uses_real_writer_fields(aggregate):
    # Real registry and inherited genealogy, exported only into memory. The
    # schema helper is also the one called by both production CSV writers.
    raw = aggregate_supplier_order() if aggregate else opening_purchase_row()
    ledger = engine.LotLedger(enabled=True)
    calendar = engine.OpeningPurchaseAvailability(
        [] if aggregate else [raw], item_unit_map={PAIR[1]: "UN"})
    if aggregate:
        calendar.add_order(raw)
    marker = raw["mrp_order_id"] if aggregate else calendar.marker_for(raw["source_file"], raw["source_row"])
    calendar.receive_physical(raw["physical_delivery_day"], ledger=ledger)
    calendar.release(marker, raw["arrival_day"], 100, ledger=ledger)
    parent_id = next(iter(ledger.lots))
    allocations = ledger.consume(day=raw["arrival_day"], node_id=PAIR[0], item_id=PAIR[1],
                                 qty=50, event_type="production_consume", source_id="campaign", uom="UN")
    child_id = ledger.create_child_lot(day=raw["arrival_day"], node_id=PAIR[0], item_id="item:PF", qty=10,
        source_type="production", source_id="campaign", parent_allocations=allocations,
        link_type="production", uom="UN", production_campaign_id="campaign")
    fields = engine.lot_trace_csv_fields(dated_availability=True)
    for table, rows in (("events", ledger.event_rows), ("genealogy", ledger.genealogy_rows)):
        stream = StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields[table])
        writer.writeheader()
        writer.writerows(rows)  # Default extrasaction='raise' catches omitted columns.
        stream.seek(0)
        restored = list(csv.DictReader(stream))
        assert len(restored) == len(rows)
        for expected, actual in zip(rows, restored):
            assert all(actual[key] == ("" if value is None else str(value)) for key, value in expected.items())
        assert {"source_row", "supplier_id"} <= set(fields[table])
    assert len(ledger.genealogy_rows) == 1
    link = ledger.genealogy_rows[0]
    assert (link["parent_lot_id"], link["child_lot_id"], link["parent_qty"], link["child_qty"]) == (parent_id, child_id, 50, 10)
    assert link["source_row"] == str(raw["source_row"])
    assert link["supplier_id"] == raw["src_node_id"]


def test_historical_lot_export_schema_stays_identical_when_dated_mode_is_off():
    fields = engine.lot_trace_csv_fields()
    assert fields["events"] == engine.PRODUCTION_LOT_EVENT_FIELDS
    assert fields["genealogy"] == engine.PRODUCTION_LOT_GENEALOGY_FIELDS
    assert "source_row" not in fields["events"]
    assert "supplier_id" not in fields["genealogy"]
    for table, columns in engine.lot_trace_csv_fields(dated_availability=True, opening_purchase_risks=True).items():
        assert len(columns) == len(set(columns))
        assert columns.count("source_row") == columns.count("supplier_id") == 1


@pytest.mark.parametrize("capacity,aggregate,expected", [(20400, 20400, 0), (20407, 20400, 7),
                                                       (120000, 120000, 0), (7, 0, 7), (0, 0, 0)])
def test_supplier_aggregate_capacity_charge_is_not_a_physical_stock_withdrawal(capacity, aggregate, expected):
    outgoing = engine.supplier_physical_outgoing_qty(capacity_used_qty=capacity, aggregate_delivery_order_qty=aggregate)
    assert outgoing == expected
    # J37 actual case: 180 units remain at the modeled supplier. Its 20,400
    # units promised by the aggregate boundary create no fictional stock loss.
    assert 180 - outgoing == 180 - expected


@pytest.mark.parametrize("value", [None, True, float('nan'), float('inf'), -1])
@pytest.mark.parametrize("field", ["capacity_used_qty", "aggregate_delivery_order_qty"])
def test_supplier_physical_withdrawal_rejects_missing_or_invalid_counter(field, value):
    arguments = {"capacity_used_qty": 10, "aggregate_delivery_order_qty": 5}
    arguments[field] = value
    with pytest.raises(ValueError):
        engine.supplier_physical_outgoing_qty(**arguments)


def test_supplier_aggregate_counter_cannot_exceed_total_used_capacity():
    with pytest.raises(ValueError):
        engine.supplier_physical_outgoing_qty(capacity_used_qty=10, aggregate_delivery_order_qty=11)


def test_known_future_purchase_pair_is_visible_from_day_zero_without_inventing_source_stock():
    future_pair = ("M-1430", "item:001848")
    stock = {PAIR: 20}
    orders = [{**opening_purchase_row(physical_day=22, available_day=42),
               "node_id": future_pair[0], "item_id": future_pair[1]}]
    original = deepcopy((stock, orders))
    population = engine.availability_export_pairs(stock_pairs=set(stock), opening_order_rows=orders)
    assert population == {PAIR, future_pair}
    ledger = engine.LotLedger(enabled=True)
    availability = engine.OpeningPurchaseAvailability(orders, item_unit_map={future_pair[1]: "UN"})
    for day in (0, 21):
        assert availability.receive_physical(day, ledger=ledger) == {}
        assert stock.get(future_pair, 0) == 0
        assert availability.held_by_pair.get(future_pair, 0) == 0
        assert future_pair in population
    assert ledger.event_rows == []
    assert future_pair not in stock  # Export coverage alone never changes state.
    assert (stock, orders) == original


def test_availability_population_keeps_distinct_sites_and_rejects_missing_identity():
    other_site = ("M-2", PAIR[1])
    assert engine.availability_export_pairs(stock_pairs={PAIR}, opening_order_rows=[], planning_pairs={other_site}) == {PAIR, other_site}
    with pytest.raises(ValueError):
        engine.availability_export_pairs(stock_pairs={PAIR}, opening_order_rows=[{"node_id": "M-2"}])
