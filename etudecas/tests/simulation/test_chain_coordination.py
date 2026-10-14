"""In-memory oracle: a blocked authorization is not yet a physical campaign.

No fixture files, timestamps, subprocesses, or simulated integrity failures.
The hand case is 100 PF requiring 200 units of a component, revised to zero
before any component is available. Already consumed material remains firm.
"""
from copy import deepcopy
from collections import defaultdict

import pytest

from etudecas.simulation.engine.mrp_planning import FirmReceipt, LotSizing, Requirement
from etudecas.simulation.engine.run_first_simulation import (
    dated_production_release, first_campaign_execution_quantity, plan_component_network,
    production_launch_support, OpeningPurchaseAvailability, LotLedger,
    initialize_opening_receipt_execution, advance_opening_receipt_execution,
)


OUTPUT = ("factory", "PF")
COMPONENT = ("factory", "tube")
LOT = dict(enabled=True, fixed_lot_qty=100.0, min_lot_qty=0.0, max_lot_qty=100.0,
           lot_multiple_qty=0.0, max_lots_per_week=20)


def executable(*, campaign=100, capacity=100, component=200, ratio=2, unit="UN"):
    return first_campaign_execution_quantity(campaign_qty=campaign, lot_policy=LOT,
        output_uom=unit, capacity_qty=capacity, component_feasible_qty=component / ratio,
        integer_input_limits=[(component, ratio, "UN")])


def network(*, needs=(), campaigns=None):
    return plan_component_network(decision_day=1, requirements_by_pair={OUTPUT: needs},
        available_by_pair={OUTPUT: 0, COMPONENT: 0}, firm_receipts_by_pair={},
        transport_sources_by_pair={}, bom_by_pair={OUTPUT: [(COMPONENT, 2)]},
        lead_days_by_pair={OUTPUT: 1, COMPONENT: 1},
        lot_sizing_by_pair={OUTPUT: LotSizing(minimum=100, multiple=100, maximum=100, integer=True)},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair=campaigns or {})


def test_zero_components_cannot_engage_output_or_reserve_weekly_slot():
    wanted, proposal = dated_production_release(decision_day=1, snapshot_day=0,
        requirements=[Requirement("client", 2, 100)], available_qty=0, firm_receipts=[], lead_days=1,
        lot_sizing=LotSizing(minimum=100, multiple=100, maximum=100, integer=True))
    assert wanted == 100
    assert executable(component=0) == 0
    # Reproduce the old false firm: no work yet, but 100 PF and 200 tubes become
    # a committed campaign even after the whole revocable need is withdrawn.
    old_plans, old_requirements, _ = network(campaigns={OUTPUT: ("not_physically_started", 100, 0, 2)})
    assert old_plans[OUTPUT].unallocated_firm_qty == 100
    assert sum(r.qty for r in old_requirements[COMPONENT]) == 200
    # The new authorization never enters this firm book until executable>0.
    new_plans, new_requirements, _ = network()
    assert new_plans[OUTPUT].unallocated_firm_qty == 0
    assert new_requirements[COMPONENT] == []
    assert new_plans[OUTPUT].proposals == ()


def test_revision_before_first_work_recalculates_the_new_quantity():
    assert executable(component=0) == 0
    # Tomorrow the material exists but only 40 PF are still required. A fixed
    # batch remains 100, not the two old proposed batches totalling 200.
    wanted, _ = dated_production_release(decision_day=2, snapshot_day=1,
        requirements=[Requirement("revised", 3, 40)], available_qty=0, firm_receipts=[], lead_days=1,
        lot_sizing=LotSizing(minimum=100, multiple=100, maximum=100, integer=True))
    assert wanted == 100
    assert executable(campaign=wanted) == 100


def test_zero_capacity_and_physical_dust_cannot_engage():
    assert executable(capacity=0) == 0
    assert executable(capacity=1e-8) == 0
    assert executable(campaign=0) == 0


def test_first_partial_work_keeps_the_complete_campaign_firm():
    assert executable(capacity=20, component=40) == 20
    # 20 PF-equivalent work has consumed 40 tubes. The remaining 80 PF need
    # 160 tubes; WIP20 + remaining80 promise exactly the original batch100.
    plans, requirements, _ = network(campaigns={OUTPUT: ("started", 80, 20, 3)})
    assert plans[OUTPUT].unallocated_firm_qty == 100
    assert sum(r.qty for r in requirements[COMPONENT]) == 160
    desired, refreshed = dated_production_release(decision_day=2, snapshot_day=1,
        requirements=[], available_qty=0, firm_receipts=[], lead_days=1, lot_sizing=LotSizing(),
        campaign_remaining_qty=80, executed_wip_qty=20)
    assert desired == 0 and refreshed is None


def test_more_than_one_batch_probes_only_the_first_physical_batch():
    assert executable(campaign=300, capacity=250, component=600) == 100


def test_physical_UN_target_stays_integer_but_fractional_work_remains_valid():
    assert executable(capacity=0.5, component=1) == 0.5
    invalid = dict(LOT, fixed_lot_qty=100.5)
    with pytest.raises(ValueError, match="Physical UN"):
        first_campaign_execution_quantity(campaign_qty=100.5, lot_policy=invalid,
            output_uom="UN", capacity_qty=101, component_feasible_qty=101, integer_input_limits=[])


def test_support_freezes_snapshot_without_creating_a_transfer_commitment():
    snapshot = dict(decision_day=0, requirements=(Requirement("derived:destination:proposal:1", 2, 80),),
                    protection=())
    original = deepcopy(snapshot)
    _, plan = dated_production_release(decision_day=1, snapshot_day=0,
        requirements=snapshot["requirements"], available_qty=0, firm_receipts=[], lead_days=1,
        lot_sizing=LotSizing(minimum=100, multiple=100, maximum=100, integer=True))
    trace = production_launch_support(plan, decision_day=1, snapshot=snapshot, campaign_qty=100)
    assert trace["planned_due_qty"] == 100
    assert sum(a["qty"] for a in trace["allocations"]) == 80
    assert trace["requirements"] == [dict(requirement_id="derived:destination:proposal:1", due_day=2, qty=80)]
    assert trace["snapshot_day"] == 0
    assert trace["downstream_commitment"] == "none_created_no_forced_transfer"
    assert trace["identities"] == "snapshot_ranks_not_industrial_order_ids"
    trace["requirements"][0]["qty"] = 7
    assert snapshot == original


def test_zero_demand_and_existing_firm_cannot_create_duplicate_fabrication():
    wanted, plan = dated_production_release(decision_day=1, snapshot_day=0,
        requirements=[Requirement("need", 2, 100)], available_qty=0,
        firm_receipts=[FirmReceipt("already_started", 5, 100)], lead_days=1,
        lot_sizing=LotSizing(minimum=100, multiple=100, maximum=100, integer=True))
    assert wanted == 0 and plan.proposals == () and plan.firm_late_qty == 100


def receipt_inputs(*, extra_original=None):
    original = dict(node_id="factory", item_id="material", order_type="opening_purchase_order",
        src_node_id="supplier", edge_id="route", source_file="memory_Extract.xlsx", source_row=7,
        receipt_qty=10, physical_delivery_day=1, arrival_day=3, receipt_release_days=2)
    rows = [original] + ([extra_original] if extra_original is not None else [])
    units = {row["item_id"]: "UN" for row in rows}
    availability = OpeningPurchaseAvailability(rows, item_unit_map=units)
    marker = availability.rows[0]["marker"]
    pipeline = defaultdict(list, {3: [("factory", "material", 10, marker)]})
    shipments = [dict(transport_cost_basis="opening_order_book", dst_node_id="factory", item_id="material")]
    if extra_original is not None:
        extra = availability.rows[1]
        pipeline[extra["arrival_day"]].append((extra["node_id"], extra["item_id"], extra["quantity"], extra["marker"]))
        shipments.append(dict(transport_cost_basis="opening_order_book", dst_node_id=extra["node_id"],
                              item_id=extra["item_id"]))
    payload = dict(schema_version=1, mode="known_weekly_receipts_fifo_v1", calendar="monday_friday",
        pairs=[dict(node_id="factory", item_id="material")], events=[dict(node_id="factory", item_id="material",
            known_day=5, quantity=4, uom="UN", source_file="memory_movements.xlsx", source_row=9, source_cell="H9")])
    return original, marker, availability, pipeline, shipments, payload, rows, units


def receipt_case():
    original, marker, availability, pipeline, shipments, payload, rows, units = receipt_inputs()
    replay = initialize_opening_receipt_execution(payload, opening_rows=[original], item_unit_map={"material": "UN"},
        origin_date="2025-01-01", availability=availability, pipeline=pipeline, shipment_rows=shipments)
    return original, marker, availability, pipeline, shipments, replay


def test_disjoint_initial_execution_and_postponement_policies_coexist():
    other = dict(node_id="other_factory", item_id="other_material", order_type="opening_purchase_order",
        src_node_id="supplier", edge_id="other_route", source_file="memory_Extract.xlsx", source_row=8,
        receipt_qty=20, physical_delivery_day=1, arrival_day=3, receipt_release_days=2)
    original, marker, availability, pipeline, shipments, payload, rows, units = receipt_inputs(extra_original=other)
    other_row = availability.rows[1]
    other_marker = other_row["marker"]
    permissions = {other_marker: dict(marker=other_marker, node_id="other_factory", item_id="other_material")}
    before_other = deepcopy(other_row)
    replay = initialize_opening_receipt_execution(payload, opening_rows=rows, item_unit_map=units,
        origin_date="2025-01-01", availability=availability, pipeline=pipeline, shipment_rows=shipments,
        postponement_permissions=permissions)
    assert replay.managed_markers == frozenset({marker})
    assert pipeline[3] == [("other_factory", "other_material", 20, other_marker)]
    assert availability.by_delivery_day[1] == [other_row]
    assert other_row == before_other
    assert shipments == [dict(transport_cost_basis="opening_order_book", dst_node_id="other_factory",
                              item_id="other_material")]
    assert set(permissions) == {other_marker}


def test_overlapping_initial_policies_fail_before_any_calendar_mutation():
    _, marker, availability, pipeline, shipments, payload, rows, units = receipt_inputs()
    permissions = {marker: dict(marker=marker, node_id="factory", item_id="material")}
    before = deepcopy((pipeline, availability.by_delivery_day, availability.rows, shipments, permissions))
    with pytest.raises(ValueError, match="cannot manage the same initial order"):
        initialize_opening_receipt_execution(payload, opening_rows=rows, item_unit_map=units,
            origin_date="2025-01-01", availability=availability, pipeline=pipeline, shipment_rows=shipments,
            postponement_permissions=permissions)
    assert (pipeline, availability.by_delivery_day, availability.rows, shipments, permissions) == before


def test_initial_promise_does_not_execute_before_receipt_is_known():
    original, marker, availability, pipeline, shipments, replay = receipt_case()
    commitments, audit = {}, []
    for day in range(5):
        advance_opening_receipt_execution(replay, day=day, availability=availability,
            pipeline=pipeline, commitments=commitments, audit_rows=audit)
    assert pipeline[3] == [] and availability.by_delivery_day[1] == [] and shipments == []
    assert audit == [] and len(availability.rows) == 1
    assert commitments["factory", "material"][marker] == (7, 10, "opening_execution_unknown")
    assert availability.by_marker[marker]["received"] is False
    assert (original["physical_delivery_day"], original["arrival_day"], original["receipt_qty"]) == (1, 3, 10)


def test_known_fragment_preserves_original_quantity_once_and_lot_provenance():
    original, marker, availability, pipeline, shipments, replay = receipt_case()
    commitments, audit = {}, []
    ledger = LotLedger(enabled=True, scenario_id="memory")
    for day in range(6):
        advance_opening_receipt_execution(replay, day=day, availability=availability,
            pipeline=pipeline, commitments=commitments, audit_rows=audit)
    # Receipt Monday 6 January; two working days -> Wednesday 8 January.
    assert len(audit) == 1 and audit[0]["arrival_day"] == 7 and audit[0]["quantity"] == 4
    fragment_marker = audit[0]["marker"]
    assert commitments["factory", "material"][marker] == (8, 6, "opening_execution_unknown")
    assert commitments["factory", "material"][fragment_marker] == (7, 4, "held")
    assert sum(row[1] for row in commitments["factory", "material"].values()) == 10
    assert availability.receive_physical(5, ledger=ledger) == {("factory", "material"): 4}
    assert availability.held_by_pair["factory", "material"] == 4
    lot = ledger.lots[availability.by_marker[fragment_marker]["lot_id"]]
    assert lot["qty_remaining"] == 4 and lot["qty_held"] == 4
    assert lot["planned_order_id"] == marker and lot["baseline_reference_id"] == marker
    availability.release(fragment_marker, 7, 4, ledger=ledger)
    assert lot["qty_remaining"] == 4 and lot["qty_held"] == 0
    assert replay.pending_by_marker()[marker] == 6
    assert availability.held_by_pair["factory", "material"] == 0


def test_repeated_known_day_cannot_duplicate_receipt_or_initial_credit():
    _, marker, availability, pipeline, _, replay = receipt_case()
    commitments, audit = {}, []
    for day in range(6):
        advance_opening_receipt_execution(replay, day=day, availability=availability,
            pipeline=pipeline, commitments=commitments, audit_rows=audit)
    first = deepcopy((pipeline, commitments, audit))
    advance_opening_receipt_execution(replay, day=5, availability=availability,
        pipeline=pipeline, commitments=commitments, audit_rows=audit)
    assert (pipeline, commitments, audit) == first
    assert len(availability.rows) == 2
