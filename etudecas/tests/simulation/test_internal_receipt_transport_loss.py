"""Memory-only transport-loss oracles; no files, clocks or native simulations.

Dispatch quantities and receipt quantities are distinct. Every expected answer
below is fixed explicitly by stock conservation and cumulative integer shares.
"""
from copy import deepcopy
import json
import math

import pytest

from etudecas.simulation.engine import run_first_simulation as engine


ITEM = "item:transport-test"
SOURCE = "plant:source"
DEST = "plant:destination"


def _parent(identity, quantity, *, uom="UN"):
    return dict(lot_id=identity, node_id=SOURCE, item_id=ITEM, qty=quantity, uom=uom,
        shipment_id="shipment:test", business_batch_id="batch:" + identity,
        planned_order_id="transfer:test", origin_production_contributions={"order:" + identity: quantity},
        origin_production_contributions_json=json.dumps({"order:" + identity: quantity}))


def _receipt(parents, quantity, *, physical_day=2, available_day=5):
    return dict(order_type="internal_transfer_delivery", mrp_order_id="transfer:test",
        node_id=DEST, item_id=ITEM, src_node_id=SOURCE, edge_id="lane:test",
        shipment_id="shipment:test", departure_day=0, receipt_qty=quantity,
        physical_delivery_day=physical_day, arrival_day=available_day,
        parent_allocations=parents, source_file="memory:internal-policy", source_row="row:test")


def test_internal_receipt_loss_preserves_full_dispatch_and_holds_only_survivors():
    ledger = engine.LotLedger(enabled=True)
    ledger.create_lot(day=0, node_id=SOURCE, item_id=ITEM, qty=100, uom="UN",
        source_type="production", source_id="order:source", planned_order_id="order:source",
        origin_production_contributions={"order:source": 100})
    parents = ledger.consume(day=0, node_id=SOURCE, item_id=ITEM, qty=100,
        event_type="lane_ship", uom="UN", source_id="lane:test", shipment_id="shipment:test",
        planned_order_id="transfer:test", departure_day=0, arrival_day=2)
    dispatched = deepcopy(parents)
    received_parents = engine.transport_receipt_parent_allocations(
        parents, dispatched_qty=100, received_qty=50, uom="UN")
    assert parents == dispatched and parents[0]["qty"] == 100
    assert ledger.pair_balance(node_id=SOURCE, item_id=ITEM) == 0
    assert sum(row["qty"] for row in received_parents) == 50
    assert sum(row["qty"] for row in parents) - sum(row["qty"] for row in received_parents) == 50
    assert received_parents[0]["origin_production_contributions"] == {"order:source": 50}
    availability = engine.OpeningPurchaseAvailability([], item_unit_map={ITEM: "UN"})
    availability.add_order(_receipt(received_parents, 50))
    assert availability.receive_physical(1, ledger=ledger) == {}
    assert availability.receive_physical(2, ledger=ledger) == {(DEST, ITEM): 50}
    assert availability.held_by_pair[DEST, ITEM] == 50
    child = ledger.lots[availability.by_marker["transfer:test"]["lot_id"]]
    assert child["origin_production_contributions"] == {"order:source": 50}
    assert [(row["parent_qty"], row["child_qty"]) for row in ledger.genealogy_rows] == [(50, 50)]
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=4, node_id=DEST, item_id=ITEM, qty=1, event_type="production_consume", uom="UN")
    availability.release("transfer:test", 5, 50, ledger=ledger)
    assert availability.held_by_pair[DEST, ITEM] == 0
    assert ledger.pair_balance(node_id=DEST, item_id=ITEM) == 50
    assert sum(row["qty"] for row in ledger.event_rows if row["event_type"] == "lane_ship") == 100
    assert sum(row["qty"] for row in ledger.event_rows if row["event_type"] == "lane_receipt") == 50


@pytest.mark.parametrize("quantities,received,expected", [
    ([33, 67], 50, [16, 34]),
    ([33, 33, 34], 50, [16, 17, 17]),
    ([1, 1, 1], 2, [1, 1]),
    ([1, 1, 1], 1, [1]),
])
def test_internal_receipt_units_follow_exact_cumulative_surviving_shares(quantities, received, expected):
    parents = [_parent(str(index), quantity) for index, quantity in enumerate(quantities)]
    original = deepcopy(parents)
    actual = engine.transport_receipt_parent_allocations(parents,
        dispatched_qty=sum(quantities), received_qty=received, uom="UN")
    assert [row["qty"] for row in actual] == expected
    assert sum(row["qty"] for row in actual) == received
    assert all(row["qty"].is_integer() for row in actual)
    assert all(row["qty"] <= original[int(row["lot_id"])]["qty"] for row in actual)
    assert parents == original
    if quantities == [1, 1, 1]:
        assert [row["lot_id"] for row in actual] == (["1", "2"] if received == 2 else ["2"])


def test_internal_receipt_fractional_mass_preserves_origin_quantities():
    parents = [_parent("A", .1, uom="KG"), _parent("B", .2, uom="KG")]
    original = deepcopy(parents)
    actual = engine.transport_receipt_parent_allocations(
        parents, dispatched_qty=.3, received_qty=.15, uom="KG")
    assert [row["qty"] for row in actual] == pytest.approx([.05, .10])
    assert math.fsum(row["qty"] for row in actual) == pytest.approx(.15)
    assert actual[0]["origin_production_contributions"]["order:A"] == pytest.approx(.05)
    assert json.loads(actual[1]["origin_production_contributions_json"])["order:B"] == pytest.approx(.10)
    assert parents == original


def test_internal_receipt_whole_units_allow_fractional_order_attribution():
    parent = _parent("mixed", 33)
    parent["origin_production_contributions"] = {"order:A": 11, "order:B": 22}
    actual = engine.transport_receipt_parent_allocations([parent], dispatched_qty=33, received_qty=16, uom="UN")
    assert actual[0]["qty"] == 16
    assert actual[0]["origin_production_contributions"] == pytest.approx({"order:A": 16 / 3, "order:B": 32 / 3})
    assert sum(actual[0]["origin_production_contributions"].values()) == pytest.approx(16)


@pytest.mark.parametrize("uom,quantities", [("UN", [33, 67]), ("KG", [.1, .2])])
def test_internal_receipt_without_loss_preserves_parent_structures_exactly(uom, quantities):
    parents = [_parent(str(index), quantity, uom=uom) for index, quantity in enumerate(quantities)]
    original = deepcopy(parents)
    quantity = math.fsum(quantities)
    actual = engine.transport_receipt_parent_allocations(
        parents, dispatched_qty=quantity, received_qty=quantity, uom=uom)
    assert actual is parents and actual == original


def test_internal_receipt_zero_survivors_creates_no_receipt_parent_and_keeps_positive_guard():
    parents = [_parent("source", 100)]
    assert engine.transport_receipt_parent_allocations(parents, dispatched_qty=100, received_qty=0, uom="UN") == []
    assert parents[0]["qty"] == 100
    with pytest.raises(ValueError, match="positive"):
        engine.OpeningPurchaseAvailability([_receipt([], 0)], item_unit_map={ITEM: "UN"})


def test_internal_receipt_conservation_guard_still_rejects_full_parents_for_partial_delivery():
    with pytest.raises(ValueError, match="conserved dispatched parent allocations"):
        engine.OpeningPurchaseAvailability([_receipt([_parent("source", 100)], 50)], item_unit_map={ITEM: "UN"})


@pytest.mark.parametrize("parents,dispatched,received,uom", [
    ([_parent("source", 100)], 100, 101, "UN"),
    ([_parent("source", 100)], 100, 50.5, "UN"),
    ([_parent("source", 100)], 100, True, "UN"),
    ([_parent("source", 90)], 100, 50, "UN"),
    ([], 100, 50, "UN"),
])
def test_internal_receipt_loss_rejects_nonconserving_or_nonphysical_inputs(parents, dispatched, received, uom):
    with pytest.raises(ValueError):
        engine.transport_receipt_parent_allocations(parents,
            dispatched_qty=dispatched, received_qty=received, uom=uom)
