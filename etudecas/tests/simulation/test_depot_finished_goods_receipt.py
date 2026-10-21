"""In-memory contract for finished-goods receipt at the receiving DC."""
from datetime import date, timedelta
import gzip
import json

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.current_reference import ROOT


def test_current_reference_places_pf_receipt_delays_at_muret():
    graph_path = ROOT / "etudecas/config/mrp_reference_20261013/graph.json.gz"
    with gzip.open(graph_path, "rt", encoding="utf-8") as stream:
        graph = json.load(stream)
    nodes = graph["nodes"]
    produced = {(node["id"], output["item_id"])
                for node in nodes for process in node.get("processes", [])
                for output in process.get("outputs", [])}
    lanes = {}
    for edge in graph["edges"]:
        for item_id in edge.get("items", []):
            lanes.setdefault((edge["to"], item_id), []).append(
                {"src": edge["from"], "edge_id": edge["id"]})
    items = {"item:268091", "item:268967"}
    policies = engine.resolve_finished_goods_depot_receipt_policy(
        graph["meta"]["finished_goods_release_policy"], nodes=nodes,
        produced_pairs=produced, finished_item_ids=items, lanes_by_dest_item=lanes,
        item_unit_map={item_id: "UN" for item_id in items},
    )
    assert {pair: row["receipt_days"] for pair, row in policies.items()} == {
        ("DC-1920", "item:268091"): 10,
        ("DC-1920", "item:268967"): 15,
    }
    assert all(row["location_basis"] == "destination_after_transport" for row in policies.values())


@pytest.mark.parametrize("item_id,receipt_days", [("268091", 10), ("268967", 15)])
def test_finished_good_is_physically_held_at_dc_after_one_transport(item_id, receipt_days):
    factory_pair = ("M-1810", item_id)
    depot_pair = ("DC-1920", item_id)
    payload = {"schema_version": 1, "rows": [{
        "node_id": factory_pair[0], "item_id": item_id, "depot_node_id": depot_pair[0],
        "receipt_days": receipt_days, "receipt_calendar": "monday_friday",
        "location_basis": "destination_after_transport",
        "source_refs": {"receipt_days": "source MRP DC-1920", "receipt_calendar": "user-confirmed weekdays",
                        "location": "user-confirmed finished-goods receipt at Muret"},
    }]}
    nodes = [{"id": factory_pair[0], "type": "factory"},
             {"id": depot_pair[0], "type": "distribution_center"}]
    lanes = {depot_pair: [{"src": factory_pair[0], "edge_id": "factory-to-Muret"}]}
    policies = engine.resolve_finished_goods_depot_receipt_policy(
        payload, nodes=nodes, produced_pairs={factory_pair}, finished_item_ids={item_id},
        lanes_by_dest_item=lanes, item_unit_map={item_id: "UN"},
    )
    policy = policies[depot_pair]
    assert policy["factory_node_id"] == factory_pair[0]
    assert policy["location_basis"] == "destination_after_transport"
    assert policy["receipt_days"] == receipt_days

    # Physical transport arrives Friday 2025-01-10. Independently count the
    # configured Monday-Friday processing days after arrival (arrival excluded).
    physical_day = 9
    current = date(2025, 1, 1) + timedelta(days=physical_day)
    expected_available = physical_day
    remaining_days = receipt_days
    while remaining_days:
        expected_available += 1
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining_days -= 1
    assert engine.supplier_receipt_available_day(
        physical_day, receipt_days, origin_date="2025-01-01", calendar="monday_friday"
    ) == expected_available

    ledger = engine.LotLedger(enabled=True, scenario_id="memory")
    ledger.seed_opening_stock(day=0, stock={factory_pair: 100}, item_unit_map={item_id: "UN"})
    parents = ledger.consume(day=3, node_id=factory_pair[0], item_id=item_id, qty=100,
        event_type="lane_ship", source_id="factory-to-Muret", uom="UN",
        departure_day=3, arrival_day=physical_day)
    marker = "MRP-TRANSFER-1"
    availability = engine.OpeningPurchaseAvailability([], item_unit_map={item_id: "UN"})
    availability.add_order({
        "order_type": "internal_transfer_delivery", "mrp_order_id": marker,
        "node_id": depot_pair[0], "item_id": item_id, "src_node_id": factory_pair[0],
        "edge_id": "factory-to-Muret", "receipt_qty": 100,
        "physical_delivery_day": physical_day, "arrival_day": expected_available,
        "departure_day": 3, "shipment_id": "SHIP-1", "parent_allocations": parents,
        "source_file": "graph.meta.finished_goods_release_policy", "source_row": "dc-policy",
    })

    assert availability.receive_physical(physical_day, ledger=ledger) == {depot_pair: 100}
    assert availability.held_by_pair[depot_pair] == 100
    assert ledger.pair_balance(node_id=depot_pair[0], item_id=item_id) == 100
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=physical_day + 1, node_id=depot_pair[0], item_id=item_id, qty=1,
                       event_type="demand_service", uom="UN")

    availability.release(marker, expected_available, 100, ledger=ledger)
    assert availability.held_by_pair[depot_pair] == 0
    assert ledger.pair_balance(node_id=depot_pair[0], item_id=item_id) == 100
    assert [row["event_type"] for row in ledger.event_rows].count("lane_receipt") == 1
    assert [row["event_type"] for row in ledger.event_rows].count("stock_availability_release") == 1
    assert len(ledger.genealogy_rows) == 1
    assert ledger.genealogy_rows[0]["link_type"] == "transport"


def test_finished_goods_receipt_rejects_nonreceiving_location_and_ambiguous_route():
    item_id = "268091"
    factory_pair = ("M-1810", item_id)
    depot_pair = ("DC-1920", item_id)
    payload = {"schema_version": 1, "rows": [{
        "node_id": factory_pair[0], "item_id": item_id, "depot_node_id": depot_pair[0],
        "receipt_days": 10, "receipt_calendar": "monday_friday",
        "location_basis": "factory_before_push_hypothesis",
        "source_refs": {"receipt_days": "source", "receipt_calendar": "weekdays", "location": "old hypothesis"},
    }]}
    kwargs = dict(nodes=[{"id": factory_pair[0], "type": "factory"},
                        {"id": depot_pair[0], "type": "distribution_center"}],
        produced_pairs={factory_pair}, finished_item_ids={item_id},
        lanes_by_dest_item={depot_pair: [{"src": factory_pair[0]}]},
        item_unit_map={item_id: "UN"})
    with pytest.raises(ValueError, match="receiving depot"):
        engine.resolve_finished_goods_depot_receipt_policy(payload, **kwargs)
    payload["rows"][0]["location_basis"] = "destination_after_transport"
    kwargs["lanes_by_dest_item"][depot_pair].append({"src": "M-OTHER"})
    with pytest.raises(ValueError, match="exclusive manufactured"):
        engine.resolve_finished_goods_depot_receipt_policy(payload, **kwargs)
