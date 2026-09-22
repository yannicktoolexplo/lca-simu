"""Compact truck-planning context for lot diagrams; never a vehicle identity."""
from .consolidation import consolidate_shipments
from .io import shipment_lines_from_events
from .models import TruckCapacity
from .engine_adapter import estimate_internal_truck_handling
import math


def build_transport_context(events, graph, profiles=()):
    from etudecas.case_config import build_lot_trace_config
    config = build_lot_trace_config(graph)
    assumptions = dict(config.get("logistics_assumptions", {}))
    for item, proxy in config.get("logistics_estimate_proxies", {}).items():
        source = proxy["source_item_id"]
        if source not in assumptions:
            raise ValueError(f"Missing transport estimate proxy source: {source}")
        # Pallet analogy only: never copy another article's mass or certification.
        assumptions[item] = {k: assumptions[source][k] for k in
            ("unitsPerCase", "centralCasesPerPallet", "truckPalletSlots")}
        assumptions[item]["sourceReference"] = proxy["source_reference"]
    capacity = TruckCapacity()
    result = consolidate_shipments(shipment_lines_from_events(events, graph),
                                  profiles=list(profiles), capacity=capacity)
    groups = []
    for group in result.fallback_groups:
        estimates = []
        bases = []
        for key, quantity in group.quantities_by_item_uom.items():
            item, unit = key.rsplit("|", 1)
            estimates.append(estimate_internal_truck_handling(item_id=item, quantity=quantity,
                uom=unit, logistics_assumptions=assumptions, capacity=capacity))
            profile = assumptions.get(item, {})
            bases.append(profile.get("sourceReference", "configured_profile:" + item) if profile else "unit:" + unit)
        pallets = (sum(e.pallet_count for e in estimates)
                   if estimates and all(e.pallet_count is not None for e in estimates) else None)
        weight = (sum(e.known_net_weight_kg for e in estimates)
                  if estimates and all(e.known_net_weight_kg is not None for e in estimates) else None)
        counts = ([math.ceil(pallets / capacity.max_pallets)] if pallets is not None else [])
        if weight is not None:
            counts.append(math.ceil(weight / capacity.max_weight_kg))
        groups.append(dict(id=group.group_id, origin=group.origin_node_id,
                           destination=group.destination_node_id,
                           start_day=group.window_start_day, end_day=group.window_end_day,
                           shipment_ids=list(group.shipment_ids), truck_count=None,
                           missing_dimensions=list(group.missing_dimensions),
                           estimated_truck_count=max(counts) if counts else None,
                           estimated_pallets=pallets, estimate_basis=bases,
                           estimated_quantities=dict(group.quantities_by_item_uom),
                           status="unknown_capacity"))
    for load in result.loads:
        groups.append(dict(id=load.load_id, origin=load.origin_node_id,
                           destination=load.destination_node_id,
                           start_day=load.window_start_day, end_day=load.window_end_day,
                           shipment_ids=sorted({a.shipment_id for a in load.allocations if a.shipment_id}),
                           truck_count=1, weight_kg=load.weight_kg, pallets=load.pallets,
                           missing_dimensions=[], status="loading_proposal"))
    return dict(capacity=capacity.to_dict(), groups=groups, audit=result.audit,
                scope="Planning proposals only. Original departure/arrival dates and lot genealogy remain unchanged.")
