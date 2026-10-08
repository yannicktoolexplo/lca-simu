"""Memory-only oracles for experimental pegged internal transfer promises."""
import csv
import io
import json
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, InternalTransferCommitments, LotSizing, Requirement, StockProtection, plan_dated_requirements,
)
from etudecas.simulation.engine.run_first_simulation import (
    INTERNAL_TRANSFER_COMMITMENT_FIELDS, internal_transfer_commitment_scope,
    plan_component_network, reconcile_production_execution_snapshot, record_started_transfer_campaign,
    INTERNAL_TRANSFER_ADVANCEMENT_FIELDS, dated_supply_release_calendar,
    internal_transfer_advancement_requests, internal_transfer_dispatch_limit,
)

SOURCE, DEST, RAW = ("maker", "intermediate"), ("user", "intermediate"), ("maker", "raw")
CALENDAR = tuple((d, d+5) for d in range(0, 81))


def _network(*, day=4, source_stock=3200, held=(), needs=6400, promises=(), capture=True):
    return dict(decision_day=day, requirements_by_pair={DEST: [Requirement("use", 20, needs)]},
        available_by_pair={SOURCE: source_stock, RAW: 100000}, firm_receipts_by_pair={SOURCE: held},
        transport_sources_by_pair={DEST: [(SOURCE, 1.0)]}, bom_by_pair={SOURCE: [(RAW, 1.0)]},
        lead_days_by_pair={DEST: 5, SOURCE: 10, RAW: 1},
        lot_sizing_by_pair={DEST: LotSizing(multiple=3200, integer=True),
            SOURCE: LotSizing(multiple=3200, maximum=3200, integer=True), RAW: LotSizing()},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        availability_by_release_by_pair={DEST: tuple(p for p in CALENDAR if p[0] >= day)},
        **(dict(transfer_commitment_pairs={DEST}, transfer_commitment_rows=promises) if capture else {}))


def _started_book():
    plans, _, audit = plan_component_network(**_network())
    book = InternalTransferCommitments()
    snapshot = {"transfer_pegs": audit[SOURCE]["transfer_pegs"]}
    created = record_started_transfer_campaign(book, day=5, source_pair=SOURCE,
        campaign_id="C1", campaign_qty=3200, executed_qty=1600,
        new_plan=plans[SOURCE], snapshot=snapshot, uom="UN")
    assert created == ("internal_commitment:1",)
    return book, plans[SOURCE], snapshot


def test_internal_commitment_scope_is_structural_and_default_is_inactive():
    lanes = {DEST: [dict(src=SOURCE[0], reliability=1)],
             ("depot", "finished"): [dict(src="finished_maker", reliability=1)],
             RAW: [dict(src="supplier")]}
    args = dict(lanes_by_dest_item=lanes, produced_pairs={SOURCE, ("finished_maker", "finished")},
                production_input_pairs={DEST, RAW}, push_destinations={("depot", "finished")})
    assert internal_transfer_commitment_scope(None, **args) == set()
    assert internal_transfer_commitment_scope("upstream_launch_pegged_v1", **args) == {DEST}
    with pytest.raises(ValueError, match="Unknown"):
        internal_transfer_commitment_scope("automatic_firm_H", **args)
    old = plan_component_network(**_network(capture=False))
    explicit_off = plan_component_network(**_network(capture=False), transfer_commitment_pairs=None,
                                         transfer_commitment_rows=())
    assert old == explicit_off


def test_campaign_launch_pegs_only_fully_funded_transfer_once_without_physical_credit():
    book, plan, snapshot = _started_book()
    row = book.orders["internal_commitment:1"]
    assert row["qty"] == row["remaining_qty"] == 6400
    assert sum(a["qty"] for a in row["support_allocations"] if a["kind"] == "started_campaign") == 3200
    assert sum(a["qty"] for a in row["support_allocations"] if a["kind"] == "available") == 3200
    assert record_started_transfer_campaign(book, day=6, source_pair=SOURCE, campaign_id="C1",
        campaign_qty=3200, executed_qty=1600, new_plan=plan, snapshot=snapshot, uom="UN") == ()
    assert len(book.orders) == 1 and book.due_quantity(DEST, 14) == 0 and book.due_quantity(DEST, 15) == 6400
    rows = book.planning_rows(decision_day=5, calendars={DEST: CALENDAR})
    args = _network(day=5, held=[FirmReceipt("quality", 15, 3200, "held")], promises=rows)
    plans, requirements, _ = plan_component_network(**args)
    assert args["available_by_pair"][SOURCE] == 3200  # No physical reservation or manufactured stock added.
    assert plans[DEST].proposed_qty == plans[SOURCE].proposed_qty == plans[RAW].proposed_qty == 0
    assert [(r.requirement_id, r.qty) for r in requirements[SOURCE]] == [(row["commitment_id"], 6400)]


def test_partial_handoff_nets_promise_held_and_transit_once_and_keeps_delay():
    book, _, _ = _started_book()
    assert book.handoff(pair=DEST, day=15, quantity=3200, shipment_id="S1", available_day=20) == 3200
    assert book.due_quantity(DEST, 16) == 3200
    pending = book.planning_rows(decision_day=16, calendars={DEST: CALENDAR})
    args = _network(day=16, source_stock=0, held=[FirmReceipt("quality", 22, 3200, "held")], promises=pending)
    args["firm_receipts_by_pair"][DEST] = [FirmReceipt("S1", 20, 3200, "in_transit")]
    plans, requirements, audit = plan_component_network(**args)
    assert plans[DEST].proposed_qty == plans[SOURCE].proposed_qty == plans[RAW].proposed_qty == 0
    assert sum(r.qty for r in requirements[SOURCE]) == 3200
    assert sum(r.qty for r in audit[DEST]["firm_receipts"]) == 6400
    promise = audit[DEST]["transfer_promises"][0]
    assert (promise["dispatch_day"], promise["promised_day"]) == (22, 27)
    assert plans[DEST].firm_late_qty == 3200 and plans[DEST].late_qty_days == 3200*7
    assert book.handoff(pair=DEST, day=22, quantity=3200, shipment_id="S2", available_day=27) == 3200
    assert book.planning_rows(decision_day=22, calendars={DEST: CALENDAR}) == ()
    assert book.handoff(pair=DEST, day=23, quantity=3200, shipment_id="unrelated", available_day=28) == 0


def test_blocked_authorization_uses_latest_campaign_allocation_when_work_really_starts():
    plans, _, audit = plan_component_network(**_network())
    book = InternalTransferCommitments()
    old = dict(transfer_pegs=audit[SOURCE]["transfer_pegs"])
    assert record_started_transfer_campaign(book, day=5, source_pair=SOURCE, campaign_id="blocked",
        campaign_qty=3200, executed_qty=0, new_plan=plans[SOURCE], snapshot=old, uom="UN") == ()
    assert not book.seen_campaigns and not book.orders
    # On the next evening the forecast becomes zero. The opened campaign is
    # still firm, but no longer allocated to an internal transfer: no old peg frozen.
    args = _network(day=6, needs=0)
    args["active_campaigns_by_pair"] = {SOURCE: ("blocked", 3200, 0, 16)}
    snapshots, _, _, _ = reconcile_production_execution_snapshot(args,
        available_by_pair=args["available_by_pair"], firm_receipts_by_pair={}, produced_pairs={SOURCE})
    assert record_started_transfer_campaign(book, day=7, source_pair=SOURCE, campaign_id="blocked",
        campaign_qty=3200, executed_qty=1600, new_plan=None, snapshot=snapshots[SOURCE], uom="UN") == ()
    assert book.seen_campaigns == {"blocked"} and not book.orders
    # A different campaign with the need still present uses its existing firm
    # output allocation, not a second newly proposed production quantity.
    args = _network(day=6)
    args["active_campaigns_by_pair"] = {SOURCE: ("started_later", 3200, 0, 16)}
    snapshots, _, _, _ = reconcile_production_execution_snapshot(args,
        available_by_pair=args["available_by_pair"], firm_receipts_by_pair={}, produced_pairs={SOURCE})
    assert record_started_transfer_campaign(book, day=7, source_pair=SOURCE, campaign_id="started_later",
        campaign_qty=3200, executed_qty=1600, new_plan=None, snapshot=snapshots[SOURCE], uom="UN")
    assert next(iter(book.orders.values()))["source_snapshot_day"] == 6


def test_launch_budget_cannot_fund_the_same_campaign_twice_or_a_partial_transfer():
    plans, _, audit = plan_component_network(**_network(source_stock=0))
    book = InternalTransferCommitments()
    assert book.from_started_campaign(day=5, campaign_id="only_one_lot", source_pair=SOURCE,
        campaign_qty=3200, plan=plans[SOURCE], pegs=audit[SOURCE]["transfer_pegs"], uom="UN") == ()
    assert book.from_started_campaign(day=5, campaign_id="only_one_lot", source_pair=SOURCE,
        campaign_qty=6400, plan=plans[SOURCE], pegs=audit[SOURCE]["transfer_pegs"], uom="UN") == ()
    assert not book.orders


def test_committed_transfer_survives_forecast_revision_without_recreating_BOM():
    book, _, _ = _started_book()
    args = _network(day=6, needs=0, held=[FirmReceipt("quality", 15, 3200, "held")],
        promises=book.planning_rows(decision_day=6, calendars={DEST: CALENDAR}))
    plans, requirements, audit = plan_component_network(**args)
    assert plans[DEST].unallocated_firm_qty == 6400
    assert plans[SOURCE].proposed_qty == plans[RAW].proposed_qty == 0
    assert sum(r.qty for r in requirements[SOURCE]) == 6400
    assert len(audit[DEST]["firm_receipts"]) == 1


def test_weekly_promise_keeps_original_date_and_waits_for_actual_material_slot():
    book, _, _ = _started_book()
    weekly = ((14, 23), (21, 30), (28, 37), (35, 44), (42, 51))
    rows = book.planning_rows(decision_day=16, calendars={DEST: weekly})
    assert (rows[0]["release_day"], rows[0]["dispatch_day"], rows[0]["promised_day"]) == (15, 21, 30)
    args = _network(day=16, source_stock=0, held=[FirmReceipt("late_hold", 22, 6400, "held")], promises=rows)
    args["availability_by_release_by_pair"] = {DEST: weekly[1:]}
    plans, _, audit = plan_component_network(**args)
    promise = audit[DEST]["transfer_promises"][0]
    assert (promise["dispatch_day"], promise["promised_day"]) == (28, 37)
    assert plans[DEST].proposed_qty == 0 and plans[DEST].firm_late_qty == 6400
    assert next(iter(book.orders.values()))["release_day"] == 15


def test_transfer_lifecycle_CSV_is_explicit_and_integer_handoff_rejects_fraction():
    book, _, _ = _started_book()
    with pytest.raises(ValueError, match="integer"):
        book.handoff(pair=DEST, day=15, quantity=0.5, shipment_id="bad", available_day=20)
    book.record_pending(day=16, rows=book.planning_rows(decision_day=16, calendars={DEST: CALENDAR}))
    book.handoff(pair=DEST, day=17, quantity=3200, shipment_id="S", available_day=22)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=INTERNAL_TRANSFER_COMMITMENT_FIELDS)
    writer.writeheader()
    writer.writerows(dict(r, support_allocations=json.dumps(r["support_allocations"])) for r in book.events)
    rows = list(csv.DictReader(io.StringIO(buffer.getvalue())))
    assert [r["event"] for r in rows] == ["created_nonphysical_promise", "pending_nonphysical_promise", "handoff_to_shipment"]
    assert rows[-1]["late_dispatch_days"] == "2" and float(rows[-1]["remaining_qty"]) == 3200
    assert rows[-1]["shipment_id"] == "S" and rows[0]["campaign_id"] == "C1"


@pytest.mark.parametrize("shipment_qty,remaining_qty", [(10, 0), (8, 2)])
def test_rounded_shipment_settles_existing_future_promises_FIFO_without_reordering(shipment_qty, remaining_qty):
    # One actual campaign of10 backs two transfer needs:3 atD2 and7 atD9.
    # Its rounded shipment atD2 must also settle the later promise. This
    # changes no demand or dispatch trigger and creates no unknown promises.
    needs = [Requirement("early", 2, 3), Requirement("later", 9, 7)]
    plan = plan_dated_requirements(decision_day=0, available_qty=0, requirements=needs,
        firm_receipts=[], lead_days=2, lot_sizing=LotSizing(minimum=10, multiple=10, integer=True))
    pegs = {r.requirement_id: dict(source_pair=SOURCE, destination_pair=DEST,
        source_snapshot_day=0, proposal_id="transfer:"+r.requirement_id,
        release_day=r.due_day, available_day=r.due_day+5, qty=r.qty) for r in needs}
    book = InternalTransferCommitments()
    assert len(book.from_started_campaign(day=0, campaign_id="ten", source_pair=SOURCE,
        campaign_qty=10, plan=plan, pegs=pegs, uom="UN")) == 2
    assert book.due_quantity(DEST, 2) == 3
    assert book.handoff(pair=DEST, day=2, quantity=shipment_qty, shipment_id="rounded", available_day=7) == shipment_qty
    assert sum(r["remaining_qty"] for r in book.orders.values()) == remaining_qty
    assert book.due_quantity(DEST, 9) == remaining_qty
    handoffs = [r for r in book.events if r["event"] == "handoff_to_shipment"]
    assert [r["event_qty"] for r in handoffs] == [3, shipment_qty-3]
    assert [r["early_handoff_days"] for r in handoffs] == [0, 7]
    assert [r["original_dispatch_day"] for r in handoffs] == [2, 9]
    assert len(book.orders) == 2
    # Physical shipment and unshipped promise together cover precisely10.
    # No second transfer proposal; only the true unshipped source need remains.
    pending = book.planning_rows(decision_day=3, calendars={DEST: CALENDAR})
    args = _network(day=3, source_stock=remaining_qty, needs=10, promises=pending)
    args["firm_receipts_by_pair"][DEST] = [FirmReceipt("rounded", 7, shipment_qty, "in_transit")]
    plans, requirements, audit = plan_component_network(**args)
    assert plans[DEST].proposed_qty == plans[SOURCE].proposed_qty == plans[RAW].proposed_qty == 0
    assert sum(r.qty for r in requirements[SOURCE]) == remaining_qty
    assert sum(r.qty for r in audit[DEST]["firm_receipts"]) == 10


def test_UN_campaign_credit_canonicalizes_only_near_integer_total_and_preserves_BOM_work():
    args = _network(day=6, source_stock=0, needs=0)
    remaining = 107800.00000000003  # +2ULP, not a physical fraction of a unit.
    args["active_campaigns_by_pair"] = {SOURCE: ("near-integer", remaining, 0.0, 20)}
    plans, requirements, audit = plan_component_network(**args)
    assert audit[SOURCE]["firm_receipts"][0].qty == 107800
    assert audit[SOURCE]["campaign_credit_canonicalization"]["raw_qty"] == remaining
    assert audit[SOURCE]["campaign_credit_canonicalization"]["canonical_qty"] == 107800
    assert requirements[RAW][0].qty == remaining  # Do not round unfinished component work.
    assert plans[SOURCE].proposed_qty == 0


def test_UN_campaign_credit_rejects_real_fraction_with_campaign_context():
    args = _network(day=6, source_stock=0, needs=0)
    args["active_campaigns_by_pair"] = {SOURCE: ("real-fraction", 107800.25, 0.0, 20)}
    with pytest.raises(ValueError, match="campaign='real-fraction'.*day=6.*107800.25"):
        plan_component_network(**args)


def test_UN_campaign_fractional_work_and_WIP_with_integer_total_stay_unchanged():
    args = _network(day=6, source_stock=0, needs=0)
    args["active_campaigns_by_pair"] = {SOURCE: ("split-work", 107700.125, 99.875, 20)}
    _, requirements, audit = plan_component_network(**args)
    assert audit[SOURCE]["firm_receipts"][0].qty == 107800
    assert requirements[RAW][0].qty == 107700.125
    assert "campaign_credit_canonicalization" not in audit[SOURCE]
    # Continuous material output has no UN quantization at this boundary.
    args["lot_sizing_by_pair"][SOURCE] = LotSizing()
    args["active_campaigns_by_pair"] = {SOURCE: ("continuous-output", 12.25, 0.125, 20)}
    _, requirements, audit = plan_component_network(**args)
    assert audit[SOURCE]["firm_receipts"][0].qty == 12.375
    assert requirements[RAW][0].qty == 12.25


ADVANCE = "advance_on_executable_need_v1"


def _advance_context(request, available):
    return dict(rescheduling_policy=ADVANCE, rescheduling_reason="executable_current_need",
        normal_release_today_qty=request["normal_release_today_qty"],
        counterfactual_release_today_qty=request["counterfactual_release_today_qty"],
        advancement_requested_qty=request["advancement_requested_qty"],
        available_source_before_dispatch_qty=available)


def _two_promise_book(destinations):
    # Both promises have real started-campaign support; neither owns stock.
    needs = [Requirement(f"need:{i}", 15, 6400) for i in range(len(destinations))]
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=needs, firm_receipts=[], lead_days=15,
        lot_sizing=LotSizing(multiple=6400, maximum=6400, integer=True))
    pegs = {r.requirement_id: dict(source_pair=SOURCE, destination_pair=dest,
        source_snapshot_day=0, proposal_id=f"transfer:{i}", release_day=15,
        available_day=20, qty=6400) for i, (r, dest) in enumerate(zip(needs, destinations))}
    book = InternalTransferCommitments()
    book.from_started_campaign(day=0, campaign_id="future-work", source_pair=SOURCE,
        campaign_qty=6400*len(destinations), plan=plan, pegs=pegs, uom="UN")
    return book


def test_transfer_advance_reuses_identity_and_does_not_execute_counterfactual_manufacture():
    book, _, _ = _started_book()
    args = _network(day=5, source_stock=6400,
        promises=book.planning_rows(decision_day=5, calendars={DEST: CALENDAR}))
    args["requirements_by_pair"][DEST] = [Requirement("earlier-use", 10, 6400)]
    before = deepcopy((args, book.orders, book.events))
    plans, _, _ = plan_component_network(**args)
    assert plans[DEST].proposed_qty == 0 and plans[DEST].firm_late_qty == 6400
    request = internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans)[DEST]
    assert request["advancement_requested_qty"] == 6400
    assert (args, book.orders, book.events) == before  # Intent changes no promise or physical stock.
    assert internal_transfer_dispatch_limit(request, available_qty=6400, already_dispatched_qty=0, uom="UN") == 6400
    assert book.handoff(pair=DEST, day=5, quantity=6400, shipment_id="advanced", available_day=10,
        advance_context=_advance_context(request, 6400)) == 6400
    assert len(book.orders) == 1 and book.orders["internal_commitment:1"]["remaining_qty"] == 0
    args = _network(day=6, source_stock=0, promises=book.planning_rows(decision_day=6, calendars={DEST: CALENDAR}))
    args["requirements_by_pair"][DEST] = [Requirement("earlier-use", 10, 6400)]
    args["firm_receipts_by_pair"][DEST] = [FirmReceipt("advanced", 10, 6400, "in_transit")]
    plans, requirements, _ = plan_component_network(**args)
    assert all(plan.proposed_qty == 0 for plan in plans.values())
    assert sum(row.qty for row in requirements[SOURCE]) == 0


def test_transfer_advance_protects_stock_floor_and_partial_remainder_keeps_original_date():
    book, _, _ = _started_book()
    args = _network(day=5, source_stock=3200,
        promises=book.planning_rows(decision_day=5, calendars={DEST: CALENDAR}))
    args["available_by_pair"][DEST] = 6400
    args["requirements_by_pair"][DEST] = [Requirement("use", 10, 6400)]
    args["protection_by_pair"] = {DEST: [StockProtection("safety", 10, 3200)]}
    plans, _, _ = plan_component_network(**args)
    request = internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans)[DEST]
    assert request["normal_release_today_qty"] == 0
    assert request["advancement_requested_qty"] == 3200
    assert book.handoff(pair=DEST, day=5, quantity=3200, shipment_id="partial", available_day=10,
        advance_context=_advance_context(request, 3200)) == 3200
    row = book.orders["internal_commitment:1"]
    assert (row["qty"], row["remaining_qty"], row["release_day"], row["available_day"]) == (6400, 3200, 15, 20)
    events = book.events[-2:]
    assert [r["event"] for r in events] == ["advanced_to_dispatch", "handoff_to_shipment"]
    assert [r["remaining_qty"] for r in events] == [6400, 3200]
    assert events[0]["quantity_event_role"] == "timing_only"
    assert events[0]["promised_dispatch_day"] == 5 and events[0]["promised_available_day"] == 10
    assert all(r["original_dispatch_day"] == 15 for r in events)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=INTERNAL_TRANSFER_COMMITMENT_FIELDS + INTERNAL_TRANSFER_ADVANCEMENT_FIELDS)
    writer.writeheader()
    writer.writerows(dict(r, support_allocations=json.dumps(r["support_allocations"])) for r in book.events)
    assert len(list(csv.DictReader(io.StringIO(buffer.getvalue())))) == len(book.events)


def test_transfer_advance_preserves_real_held_transit_and_due_promises_without_double_subtraction():
    book = _two_promise_book([DEST, DEST])
    first = book.orders["internal_commitment:1"]
    first.update(release_day=5, available_day=10)
    args = _network(day=5, source_stock=12800, needs=16000,
        promises=book.planning_rows(decision_day=5, calendars={DEST: CALENDAR}))
    args["requirements_by_pair"][DEST] = [Requirement("now-earlier", 10, 16000)]
    args["firm_receipts_by_pair"][DEST] = [FirmReceipt("real-held", 10, 1600, "held"),
        FirmReceipt("real-transit", 10, 1600, "in_transit")]
    plans, _, _ = plan_component_network(**args)
    request = internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans)[DEST]
    assert request["normal_release_today_qty"] == 0
    assert request["counterfactual_release_today_qty"] == 6400  # 16000 - 3200 real - 6400 already due.
    assert request["advancement_requested_qty"] == 6400
    assert book.due_quantity(DEST, 5) + request["advancement_requested_qty"] == 12800
    args["firm_receipts_by_pair"][DEST].append(FirmReceipt("another-real", 10, 6400, "confirmed"))
    plans, _, _ = plan_component_network(**args)
    assert internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args,
        plans=plans)[DEST]["advancement_requested_qty"] == 0


def test_transfer_advance_adds_only_increment_above_normal_new_order():
    book, _, _ = _started_book()
    args = _network(day=5, source_stock=16000,
        promises=book.planning_rows(decision_day=5, calendars={DEST: CALENDAR}))
    args["requirements_by_pair"][DEST] = [Requirement("use", 10, 16000)]
    plans, _, _ = plan_component_network(**args)
    request = internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans)[DEST]
    assert request["normal_release_today_qty"] == 9600
    assert request["counterfactual_release_today_qty"] == 16000
    assert request["advancement_requested_qty"] == 6400
    assert request["physical_authorization_qty"] == 16000


@pytest.mark.parametrize("needs,need_day", [(0, 10), (6400, 20)])
def test_transfer_advance_leaves_zero_need_and_timely_promise_unchanged(needs, need_day):
    book, _, _ = _started_book()
    args = _network(day=5, source_stock=6400, needs=needs,
        promises=book.planning_rows(decision_day=5, calendars={DEST: CALENDAR}))
    args["requirements_by_pair"][DEST] = [Requirement("use", need_day, needs)]
    plans, _, _ = plan_component_network(**args)
    before = deepcopy(book.orders)
    assert internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args,
        plans=plans)[DEST]["advancement_requested_qty"] == 0
    assert book.orders == before and len(book.events) == 1


def test_transfer_advance_uses_available_stock_only_and_skips_closed_dispatch_slots():
    book, _, _ = _started_book()
    args = _network(day=5, source_stock=0, held=[FirmReceipt("held", 15, 6400, "held")],
        promises=book.planning_rows(decision_day=5, calendars={DEST: CALENDAR}))
    args["requirements_by_pair"][DEST] = [Requirement("use", 10, 6400)]
    plans, _, _ = plan_component_network(**args)
    assert internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans) == {}
    args["available_by_pair"][SOURCE] = 6400
    args["availability_by_release_by_pair"][DEST] = tuple((d,d+5) for d in range(6,81,7))
    plans, _, _ = plan_component_network(**args)
    assert internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans) == {}
    assert len(book.events) == 1  # No timing event for blocked intent.
    assert internal_transfer_advancement_requests(None, book=None, network_inputs={}, plans={}) == {}


def test_transfer_advance_two_destinations_share_one_physical_stock_and_never_duplicate_quantity():
    other = ("other-user", "intermediate")
    book = _two_promise_book([DEST, other])
    calendars = {DEST: CALENDAR, other: CALENDAR}
    args = _network(day=5, source_stock=9600,
        promises=book.planning_rows(decision_day=5, calendars=calendars))
    args["requirements_by_pair"] = {p: [Requirement("use:"+p[0], 10, 6400)] for p in (DEST, other)}
    args["transport_sources_by_pair"][other] = [(SOURCE, 1.)]
    args["lead_days_by_pair"][other] = 5
    args["lot_sizing_by_pair"][other] = LotSizing(multiple=3200, integer=True)
    args["availability_by_release_by_pair"][other] = args["availability_by_release_by_pair"][DEST]
    args["transfer_commitment_pairs"].add(other)
    plans, _, _ = plan_component_network(**args)
    requests = internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans)
    stock, shipped = 9600, []
    for pair in (DEST, other):
        assert requests[pair]["advancement_requested_qty"] == 6400
        qty = internal_transfer_dispatch_limit(requests[pair], available_qty=stock, already_dispatched_qty=0, uom="UN")
        before = stock
        stock -= qty
        book.handoff(pair=pair, day=5, quantity=qty, shipment_id=pair[0], available_day=10,
            advance_context=_advance_context(requests[pair], before))
        shipped.append(qty)
    assert shipped == [6400, 3200] and stock == 0
    assert sum(r["remaining_qty"] for r in book.orders.values()) == 3200
    assert len(book.orders) == 2
    assert internal_transfer_dispatch_limit(requests[other], available_qty=9600,
        already_dispatched_qty=6400, uom="UN") == 0  # No second full-lot authorization.


def test_transfer_advance_january_slot_includes_transport_and_weekday_receipt_time():
    # Reduced 773474 episode: a future 3200kg promise masks an earlier need.
    needs = [Requirement("later-transfer", 84, 3200)]
    plan = plan_dated_requirements(decision_day=11, available_qty=0, requirements=needs,
        firm_receipts=[], lead_days=73, lot_sizing=LotSizing(multiple=3200))
    book = InternalTransferCommitments()
    book.from_started_campaign(day=11, campaign_id="January-work", source_pair=SOURCE,
        campaign_qty=3200, plan=plan, uom="KG", pegs={"later-transfer": dict(source_pair=SOURCE,
            destination_pair=DEST, source_snapshot_day=10, proposal_id="future-transfer",
            release_day=84, available_day=103, qty=3200)})
    calendar = dated_supply_release_calendar(decision_day=21, through_day=140,
        physical_lead_days=10, receipt_days=6, review_days=7, origin_date="2025-01-01")
    assert calendar[:2] == ((21,40), (28,47))  # Jan22 -> Feb1 arrival -> Feb10 usable.
    args = _network(day=21, source_stock=9600,
        promises=book.planning_rows(decision_day=21, calendars={DEST: calendar}))
    args["requirements_by_pair"][DEST] = [Requirement("protected-need", 44, 3200)]
    args["lead_days_by_pair"][DEST] = 19
    args["availability_by_release_by_pair"][DEST] = calendar
    plans, _, _ = plan_component_network(**args)
    request = internal_transfer_advancement_requests(ADVANCE, book=book, network_inputs=args, plans=plans)[DEST]
    assert request["normal_release_today_qty"] == 0 and request["advancement_requested_qty"] == 3200
    assert book.orders["internal_commitment:1"]["release_day"] == 84
    book.handoff(pair=DEST, day=21, quantity=3200, shipment_id="Jan22", available_day=40,
        advance_context=_advance_context(request, 9600))
    event = book.events[-2]
    assert (event["original_dispatch_day"], event["original_available_day"],
        event["promised_dispatch_day"], event["promised_available_day"]) == (84,103,21,40)
