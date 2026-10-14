"""Memory-only oracles: transport quantity is independent of production lots.

No files, fixture mutation, clock changes, disappearance probes or simulations.
The numerical answers below are fixed by stock conservation, not a production
helper used as its own oracle. KG examples mirror the separate G scenario.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, InternalTransferCommitments, LotSizing, Requirement,
)
from etudecas.simulation.engine.run_first_simulation import (
    apply_internal_component_lane_policies, mrp_purchase_order_quantity,
    plan_component_network, record_started_transfer_campaign,
    resolve_internal_component_policies,
)


SOURCE = ("SDC-1450", "item:693055")
DEST = ("M-1810", "item:693055")
RAW = ("SDC-1450", "item:virtual")
CALENDAR = tuple((day, day + 5) for day in range(81))


def _context(multiple=0, *, uom="KG"):
    row = dict(policy_id="explicit_transfer_quantity_candidate", node_id=DEST[0],
        item_id=DEST[1], source_node_id=SOURCE[0], uom=uom, receipt_days=7,
        receipt_calendar="monday_friday", delivery_reference_days=70,
        transfer_multiple_qty=multiple, status="candidate_not_inferred_ERP",
        source_refs=dict(receipt_days="source receipt: 7 working days",
            receipt_calendar="user confirmed Monday-Friday",
            delivery_reference="FIA reference: 70 days",
            transfer_multiple_qty="1190 kg transfer observed; 600 kg is a fabrication lot"))
    nodes = [dict(id=SOURCE[0], type="factory", processes=[dict(
        outputs=[dict(item_id=SOURCE[1])], inputs=[dict(item_id=RAW[1], ratio_per_batch=1)],
        lot_sizing=dict(fixed_lot_qty=600))]),
        dict(id=DEST[0], type="factory", processes=[dict(
            inputs=[dict(item_id=DEST[1], ratio_per_batch=1)],
            outputs=[dict(item_id="item:finished")])])]
    lanes = {DEST: [dict(src=SOURCE[0], lead_days_mean=70, standard_order_qty=600,
        physical_dispatch_multiple=600)]}
    return dict(schema_version=2, rows=[row]), dict(execution_mode="dated", nodes=nodes,
        lanes_by_dest_item=lanes, item_unit_map={DEST[1]: uom})


def _configured(multiple=0, *, uom="KG"):
    payload, context = _context(multiple, uom=uom)
    nodes_before = deepcopy(context["nodes"])
    policies = resolve_internal_component_policies(payload, **context)
    apply_internal_component_lane_policies(policies, context["lanes_by_dest_item"], schema_version=2)
    assert context["nodes"] == nodes_before  # Includes unchanged 600 fabrication lot.
    return policies[DEST], context["lanes_by_dest_item"][DEST][0]


@pytest.mark.parametrize("desired,available,old_expected,new_expected", [
    (600, 590, 0, 590), (1190, 1190, 600, 1190),
    (1190, 1790, 1200, 1190), (600, 600, 600, 600), (600, 0, 0, 0),
])
@pytest.mark.parametrize("uom,scale", [("KG", 1), ("G", 1000)])
def test_explicit_zero_transfer_quantum_preserves_mass_and_production_lot(
        desired, available, old_expected, new_expected, uom, scale):
    _, old_lane = _configured(600 * scale, uom=uom)
    policy, lane = _configured(0, uom=uom)
    assert mrp_purchase_order_quantity(desired * scale, available * scale,
        old_lane["internal_transfer_multiple_qty"], binding=True, uom=uom) == old_expected * scale
    actual = mrp_purchase_order_quantity(desired * scale, available * scale,
        lane["internal_transfer_multiple_qty"], binding=True, uom=uom)
    assert actual == new_expected * scale
    assert actual <= available * scale
    assert lane["standard_order_qty"] == lane["physical_dispatch_multiple"] == 0
    assert policy["receipt_days"] == 7 and policy["delivery_reference_days"] == 70


def test_omitted_transfer_quantum_and_documented_positive_quantum_are_preserved():
    payload, context = _context()
    del payload["rows"][0]["transfer_multiple_qty"]
    before = deepcopy(context["lanes_by_dest_item"])
    policies = resolve_internal_component_policies(payload, **context)
    apply_internal_component_lane_policies(policies, context["lanes_by_dest_item"], schema_version=2)
    assert context["lanes_by_dest_item"] == before
    _, lane = _configured(3200)
    assert mrp_purchase_order_quantity(6400, 6400, lane["internal_transfer_multiple_qty"],
        binding=True, uom="KG") == 6400
    assert mrp_purchase_order_quantity(3200, 3190, lane["internal_transfer_multiple_qty"],
        binding=True, uom="KG") == 0


@pytest.mark.parametrize("invalid", [-1, True, float("nan"), float("inf"), "0"])
def test_transfer_quantum_rejects_invalid_values(invalid):
    payload, context = _context(invalid)
    with pytest.raises(ValueError, match="nonnegative physical quantity"):
        resolve_internal_component_policies(payload, **context)


def test_zero_transfer_quantum_still_requires_provenance():
    payload, context = _context()
    del payload["rows"][0]["source_refs"]["transfer_multiple_qty"]
    with pytest.raises(ValueError, match="explicit provenance"):
        resolve_internal_component_policies(payload, **context)


def test_zero_transfer_quantum_never_dispatches_fractional_physical_UN():
    _, lane = _configured(0, uom="UN")
    assert mrp_purchase_order_quantity(600, 590.75, lane["internal_transfer_multiple_qty"],
        binding=True, uom="UN") == 590
    payload, context = _context(0.5, uom="UN")
    with pytest.raises(ValueError, match="physical quantity"):
        resolve_internal_component_policies(payload, **context)


def _network(*, day=4, stock=590, held=(), promises=()):
    policy, _ = _configured()
    return dict(decision_day=day,
        requirements_by_pair={DEST: [Requirement("dated_use", 20, 1190)]},
        available_by_pair={SOURCE: stock, RAW: 10000}, firm_receipts_by_pair={SOURCE: held},
        transport_sources_by_pair={DEST: [(SOURCE, 1.0)]}, bom_by_pair={SOURCE: [(RAW, 1.0)]},
        lead_days_by_pair={DEST: 5, SOURCE: 10, RAW: 1},
        lot_sizing_by_pair={DEST: LotSizing(multiple=policy["transfer_multiple_qty"]),
            SOURCE: LotSizing(minimum=600, multiple=600, maximum=600), RAW: LotSizing()},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        availability_by_release_by_pair={DEST: tuple(slot for slot in CALENDAR if slot[0] >= day)},
        transfer_commitment_pairs={DEST}, transfer_commitment_rows=promises)


def test_partial_nonmultiple_handoff_conserves_commitment_without_a_second_order():
    # Manual oracle: 590 existing + one 600 fabrication = one 1190 transfer.
    # After shipping 590, exactly 600 remains promised; neither side reorders.
    plans, _, audit = plan_component_network(**_network())
    assert plans[DEST].proposed_qty == 1190
    assert [proposal.qty for proposal in plans[SOURCE].proposals] == [600]
    book = InternalTransferCommitments()
    snapshot = dict(transfer_pegs=audit[SOURCE]["transfer_pegs"])
    start = dict(day=5, source_pair=SOURCE, campaign_id="fabrication_600", campaign_qty=600,
        executed_qty=600, new_plan=plans[SOURCE], snapshot=snapshot, uom="KG")
    assert record_started_transfer_campaign(book, **start) == ("internal_commitment:1",)
    assert record_started_transfer_campaign(book, **start) == ()
    assert book.handoff(pair=DEST, day=15, quantity=590, shipment_id="partial_590",
        available_day=20) == 590
    assert book.due_quantity(DEST, 16) == 600
    pending = book.planning_rows(decision_day=16, calendars={DEST: CALENDAR})
    args = _network(day=16, stock=0, held=[FirmReceipt("held_600", 22, 600, "held")], promises=pending)
    args["firm_receipts_by_pair"][DEST] = [FirmReceipt("partial_590", 20, 590, "in_transit")]
    after, requirements, after_audit = plan_component_network(**args)
    assert [after[pair].proposed_qty for pair in (DEST, SOURCE, RAW)] == [0, 0, 0]
    assert sum(row.qty for row in requirements[SOURCE]) == 600
    assert sum(row.qty for row in after_audit[DEST]["firm_receipts"]) == 1190
    assert len(book.orders) == 1
    assert book.handoff(pair=DEST, day=22, quantity=600, shipment_id="balance_600",
        available_day=27) == 600
    assert book.planning_rows(decision_day=22, calendars={DEST: CALENDAR}) == ()
    assert sum(row["event_qty"] for row in book.events if row["event"] == "handoff_to_shipment") == 1190
