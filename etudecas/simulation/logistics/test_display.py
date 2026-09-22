from etudecas.simulation.logistics.display import build_transport_context
from etudecas.simulation.logistics.models import ItemLogisticsProfile
from etudecas.simulation.logistics.engine_adapter import estimate_internal_truck_handling
from etudecas.case_config import LOT_TRACE_DEFAULT_LOGISTICS_ASSUMPTIONS


def event(identifier, day, qty=5000):
    return dict(event_id=identifier, event_type="lane_ship", day=day,
                departure_day=day, arrival_day=day+5, source_id="edge", node_id="S",
                item_id="item:338929", qty=qty, uom="UN", lot_id=identifier,
                shipment_id=identifier)


GRAPH = {"edges": [{"id": "edge", "from": "S", "to": "F", "mode": "truck"}]}


def test_four_shipments_are_three_weekly_groups_not_four_trucks():
    result = build_transport_context([event("203",60),event("204",62),
                                     event("251",48),event("252",50)], GRAPH)
    groups = result["groups"]
    assert len(groups) == 3
    assert next(g for g in groups if g["start_day"] == 56)["shipment_ids"] == ["203","204"]
    assert all(g["truck_count"] is None for g in groups)
    assert all(g["estimated_truck_count"] == 1 for g in groups)
    assert all(g["estimated_pallets"] >= 1 for g in groups)
    assert all("gross_weight_kg" in g["missing_dimensions"] for g in groups)
    assert all(any(b.startswith("hypothesis:") for b in g["estimate_basis"]) for g in groups)


def test_existing_finished_batch_is_eighteen_pallets_not_full_truck_capacity():
    estimate = estimate_internal_truck_handling(item_id="item:268967", quantity=107800,
        uom="UN", logistics_assumptions=LOT_TRACE_DEFAULT_LOGISTICS_ASSUMPTIONS)
    assert estimate.pallet_count == 18 and estimate.truck_count == 1
    assert "gross_weight" in estimate.missing_checks
    assert "item:338929" not in LOT_TRACE_DEFAULT_LOGISTICS_ASSUMPTIONS


def test_sourced_profile_can_dimension_real_capacity_proposals():
    profile = ItemLogisticsProfile(item_id="item:338929", uom="UN", kg_per_unit=1,
                                   pallets_per_unit=.001, source_reference="fixture:loaded")
    result = build_transport_context([event("A",60,10000),event("B",62,15000)],GRAPH,[profile])
    assert len(result["groups"]) == 2  # 25 tonnes cannot fit in 23 tonnes.
    assert all(g["truck_count"] == 1 and g["weight_kg"] <= 23000 and g["pallets"] <= 33
               for g in result["groups"])
