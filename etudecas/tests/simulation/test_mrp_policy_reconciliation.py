"""Independent memory-only acceptance cases for candidate material policies.

The source provides20 working days, not a proved ERP stock-floor algorithm.
These cases check the chosen non-consumable floor contract, not calibration.
No workbook, disk fixture, simulation, timestamp or permission operation occurs.
"""
from copy import deepcopy
import csv
import io
import json

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, StockProtection,
    plan_dated_requirements, plan_with_stock_protection,
)
from etudecas.simulation.engine.run_first_simulation import supplier_receipt_available_day
from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.experiments.shared_components import revision_series


def protected(needs=(), *, stock=0, firms=(), points=(), lead=10, lots=None, day=0):
    return plan_with_stock_protection(
        decision_day=day, available_qty=stock, requirements=needs,
        firm_receipts=firms, lead_days=lead, lot_sizing=lots, protection=points,
    )


def arrivals(result):
    quantities = {}
    for row in result.plan.proposals:
        quantities[row.available_day] = quantities.get(row.available_day, 0) + row.qty
    return quantities


def test_protection_persists_after_consumption_without_becoming_consumption():
    # Need100 at10, then100 at25; maintain200 after each real withdrawal.
    result = protected([Requirement("first", 10, 100), Requirement("later", 25, 100)],
        points=[StockProtection("floor", 10, 200)])
    assert arrivals(result) == {10: 300, 25: 100}
    assert result.plan.proposed_qty == 400
    assert sum(r.qty for r in result.plan.allocations) == 200
    assert {r.requirement_id for r in result.plan.allocations} == {"first", "later"}
    assert sum(r.requirement_qty for r in result.plan.balances) == 200
    assert result.plan.closing_projected_qty == 200
    checked = {r.day: r for r in result.protection}
    for day in (10, 25):
        assert checked[day].target_qty == checked[day].projected_qty == 200
        assert checked[day].shortfall_qty == 0


def test_adding_a_later_need_never_reduces_the_same_earlier_floor():
    first = Requirement("first", 10, 100)
    floor = [StockProtection("floor", 10, 200)]
    before = protected([first], points=floor)
    after = protected([first, Requirement("new-later", 25, 100)], points=floor)
    assert arrivals(before) == {10: 300}
    assert arrivals(after)[10] == 300
    assert arrivals(after)[25] == 100
    assert before.plan.closing_projected_qty == after.plan.closing_projected_qty == 200


def test_repeated_protection_checkpoints_are_not_additive_daily_demand():
    result = protected(points=[StockProtection(f"floor-{d}", d, 200) for d in (10, 11, 12)])
    assert arrivals(result) == {10: 200}
    assert result.plan.allocations == ()
    assert sum(r.requirement_qty for r in result.plan.balances) == 0
    assert result.plan.closing_projected_qty == 200
    assert result.plan.late_qty == 0


def test_a_lower_future_floor_reuses_existing_stock_instead_of_buying_twice():
    result = protected([Requirement("real-use", 20, 100)],
        points=[StockProtection("raised", 10, 200), StockProtection("released", 20, 0)])
    assert arrivals(result) == {10: 200}
    assert result.plan.proposed_qty == 200 and result.plan.closing_projected_qty == 100
    at20 = next(r for r in result.protection if r.day == 20)
    assert at20.target_qty == 0 and at20.projected_qty == 100 and at20.shortfall_qty == 0


def test_available_stock_and_existing_commitments_each_cover_the_floor_once():
    result = protected([Requirement("real-use", 10, 100)], stock=100,
        firms=[FirmReceipt("committed", 10, 200)], points=[StockProtection("floor", 10, 200)])
    assert result.plan.proposals == ()
    assert result.plan.closing_projected_qty == 200
    assert sum(r.qty for r in result.plan.allocations) == 100
    assert all(r.shortfall_qty == 0 for r in result.protection)


def test_late_firm_is_not_rebought_and_unmet_protection_is_explicit():
    firms = [FirmReceipt("late-existing", 30, 400)]
    saved = deepcopy(firms)
    result = protected([Requirement("first", 10, 100), Requirement("later", 25, 100)],
        firms=firms, points=[StockProtection("floor", 10, 200)])
    assert result.plan.proposals == () and firms == saved
    assert result.plan.late_qty == 200 and result.plan.late_qty_days == 2500
    assert result.plan.closing_projected_qty == 200
    p = {r.day: r for r in result.protection}
    assert p[10].shortfall_qty > 0 and p[25].shortfall_qty > 0
    assert p[30].shortfall_qty == 0
    assert {r.available_day for r in result.plan.allocations} == {30}


def test_protection_before_feasible_arrival_reports_gap_without_fake_receipt():
    result = protected(points=[StockProtection("floor", 1, 100)], lead=10)
    assert arrivals(result) == {10: 100}
    assert result.plan.late_qty == 0  # No real material use has been delayed.
    p = {r.day: r for r in result.protection}
    assert p[1].projected_qty == 0 and p[1].shortfall_qty == 100
    assert p[10].projected_qty == 100 and p[10].shortfall_qty == 0


def test_absent_protection_preserves_the_complete_legacy_plan():
    kwargs = dict(decision_day=0, available_qty=20,
        requirements=[Requirement("first", 3, 50), Requirement("second", 7, 50)],
        firm_receipts=[FirmReceipt("firm", 5, 60)], lead_days=2,
        lot_sizing=LotSizing(multiple=10))
    legacy = plan_dated_requirements(**kwargs)
    result = plan_with_stock_protection(**kwargs)
    assert result.plan == legacy and result.protection == ()


def test_600kg_lot_surplus_is_kept_and_covers_later_need_without_another_order():
    result = protected([Requirement("first", 10, 100), Requirement("second", 20, 100)],
        points=[StockProtection("floor", 10, 200)], lots=LotSizing(multiple=600))
    assert arrivals(result) == {10: 600}
    assert result.plan.closing_projected_qty == 400
    assert all(r.shortfall_qty == 0 for r in result.protection)


@pytest.mark.parametrize("multiple,expected", [(600, 1200), (1000, 2000)])
def test_quantity_step_is_not_a_maximum_order_capacity(multiple, expected):
    result = protected([Requirement("large", 20, 1100)], lots=LotSizing(multiple=multiple))
    assert result.plan.proposed_qty == expected
    assert arrivals(result) == {20: expected}
    assert result.plan.closing_projected_qty == expected - 1100


def test_fractional_forecasts_do_not_create_a_ghost_physical_UN_purchase():
    result = protected([Requirement(f"forecast-{i}", 10, 0.1) for i in range(30)],
        stock=3, points=[StockProtection("floor", 10, 2)], lots=LotSizing(integer=True))
    assert result.plan.proposed_qty == 2
    assert all(r.qty == int(r.qty) for r in result.plan.proposals)
    assert result.plan.closing_projected_qty == 2


def test_planning_never_mutates_physical_inputs_or_relabels_requirements():
    needs = [Requirement("use", 20, 100)]
    firms = [FirmReceipt("held", 10, 100, "held")]
    points = [StockProtection("floor", 10, 200)]
    saved = deepcopy((needs, firms, points))
    protected(needs, firms=firms, points=points)
    assert (needs, firms, points) == saved


@pytest.mark.parametrize("invalid", [None, True, -1, float("nan"), float("inf")])
def test_missing_or_invalid_protection_cannot_silently_become_zero(invalid):
    with pytest.raises(ValueError):
        protected(points=[StockProtection("floor", 10, invalid)])


@pytest.mark.parametrize("invalid_day", [True, 10.5, None])
def test_protection_date_must_be_an_explicit_integer_day(invalid_day):
    with pytest.raises(ValueError):
        protected(points=[StockProtection("floor", invalid_day, 100)])


def test_duplicate_protection_identity_is_rejected():
    with pytest.raises(ValueError):
        protected(points=[StockProtection("same", 10, 100), StockProtection("same", 20, 200)])


@pytest.mark.parametrize("physical_day,available_day", [(2, 13), (5, 14), (8, 19)])
def test_seven_working_receipt_days_are_added_once_after_physical_arrival(physical_day, available_day):
    # Origin Wednesday1Jan2025; Friday3Jan +7 Mon-Fri days =Tuesday14Jan.
    # Jan6 ->Jan15; Jan9 ->Jan20. No holiday calendar is being invented.
    assert supplier_receipt_available_day(physical_day, 7, origin_date="2025-01-01") == available_day


def test_receipt_delay_zero_keeps_the_physical_date():
    assert supplier_receipt_available_day(2, 0, origin_date="2025-01-01") == 2


def test_default_revision_mass_unit_preserves_legacy_KG_and_year_end_prorata():
    records = [
        {"known_day": 354, "day": 354, "qty": 999, "unit": "KG", "row": 1},
        {"known_day": 354, "day": 361, "qty": 70, "unit": "KG", "row": 2},
        {"known_day": 354, "day": 368, "qty": 140, "unit": "KG", "row": 3},
    ]
    result = revision_series(records, [354], "001757/1810", 0.5)
    assert result == revision_series(records, [354], "001757/1810", 0.5, output_uom="KG")
    assert result["uom"] == "KG"
    rows = result["versions"][0]["rows"]
    assert [(r["period_start_day"], r["period_days"], r["qty"]) for r in rows] == [(361, 4, 20)]
    assert rows[0]["source_cells"] == "Feuille1!I2"
    assert json.loads(rows[0]["estimation_basis"])["fraction"] == 0.5


def test_G_revision_converts_canonical_KG_once_preserving_dates_and_provenance():
    records = [
        {"known_day": 4, "day": 4, "qty": 999, "unit": "KG", "row": 10},
        {"known_day": 4, "day": 11, "qty": 600, "unit": "KG", "row": 11},
        {"known_day": 4, "day": 368, "qty": 1200, "unit": "KG", "row": 12},
        {"known_day": 4, "day": 375, "qty": 1800, "unit": "KG", "row": 13},
    ]
    saved = deepcopy(records)
    kg = revision_series(records, [4], "693055/1810", 0.25, planning_horizon_days=364)
    grams = revision_series(records, [4], "693055/1810", 0.25,
        planning_horizon_days=364, output_uom="G")
    assert records == saved and grams["uom"] == "G"
    rows = grams["versions"][0]["rows"]
    assert [(r["period_start_day"], r["period_days"], r["qty"]) for r in rows] == [
        (11, 7, 150000), (368, 7, 300000)]
    equivalent = deepcopy(grams)
    equivalent["uom"] = "KG"
    for row in equivalent["versions"][0]["rows"]:
        row["qty"] /= 1000
    assert equivalent == kg
    for row in rows:
        assert json.loads(row["estimation_basis"])["fraction"] == 0.25
    assert [r["source_cells"] for r in rows] == ["Feuille1!I11", "Feuille1!I12"]


PAIR = ("M-1810", "item:693055")
ORIGIN_PAIR = ("SDC-1450", PAIR[1])


def internal_policy():
    return {"schema_version": 1, "rows": [{
        "policy_id": "candidate", "node_id": PAIR[0], "item_id": PAIR[1],
        "source_node_id": ORIGIN_PAIR[0], "uom": "G", "transfer_multiple_qty": 600000,
        "receipt_days": 7, "receipt_calendar": "monday_friday", "protection_mode": "dated_stock_floor",
        "source_refs": {"safety": "20working days, candidate floor interpretation"},
        "status": "candidate_not_inferred_ERP"}]}


def resolve_policy(payload, *, mode="dated"):
    return engine.resolve_internal_component_policies(payload, execution_mode=mode,
        lanes_by_dest_item={PAIR: [{"src": ORIGIN_PAIR[0], "lead_days": 70}]},
        item_unit_map={PAIR[1]: "G"})


def test_internal_policy_absent_preserves_legacy_and_present_is_narrowly_scoped():
    assert resolve_policy(None, mode="historical") == {}
    data = internal_policy()
    saved = deepcopy(data)
    result = resolve_policy(data)
    assert set(result) == {PAIR}
    assert result[PAIR]["transfer_multiple_qty"] == 600000
    assert data == saved


@pytest.mark.parametrize("fault", ["other_item", "other_source", "KG_unit", "lot50000", "receipt_calendar", "historical", "duplicate"])
def test_internal_policy_cannot_generalize_or_silently_change_source_conventions(fault):
    data = internal_policy()
    if fault == "other_item": data["rows"][0]["item_id"] = "item:001757"
    elif fault == "other_source": data["rows"][0]["source_node_id"] = "M-1430"
    elif fault == "KG_unit": data["rows"][0]["uom"] = "KG"
    elif fault == "lot50000": data["rows"][0]["transfer_multiple_qty"] = 50000
    elif fault == "receipt_calendar": data["rows"][0]["receipt_calendar"] = "calendar_days"
    elif fault == "duplicate": data["rows"].append(deepcopy(data["rows"][0]))
    with pytest.raises(ValueError):
        resolve_policy(data, mode="historical" if fault == "historical" else "dated")


def transferred_material(*, parent_quantities=(700000,), transfer_qty=600000):
    ledger = engine.LotLedger(enabled=True)
    for quantity in parent_quantities:
        ledger.seed_opening_stock(day=0, stock={ORIGIN_PAIR: quantity}, item_unit_map={PAIR[1]: "G"})
    parent = next(iter(ledger.lots))
    allocations = ledger.consume(day=0, node_id=ORIGIN_PAIR[0], item_id=PAIR[1], qty=transfer_qty,
        event_type="lane_ship", uom="G", shipment_id="SHIP1", source_id="lane1",
        planned_order_id="ORDER1", departure_day=0, arrival_day=2)
    raw = {"order_type": "internal_transfer_delivery", "mrp_order_id": "ORDER1",
        "node_id": PAIR[0], "item_id": PAIR[1], "src_node_id": ORIGIN_PAIR[0],
        "edge_id": "lane1", "shipment_id": "SHIP1", "departure_day": 0,
        "receipt_qty": transfer_qty, "physical_delivery_day": 2, "arrival_day": 13,
        "parent_allocations": allocations, "source_file": "graph.meta.internal_component_policy",
        "source_row": "candidate"}
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={PAIR[1]: "G"})
    calendar.add_order(raw)
    return ledger, calendar, raw, parent


def test_internal_delivery_keeps_parent_genealogy_and_one_physical_receipt_G_then_I():
    ledger, calendar, raw, parent = transferred_material()
    original = deepcopy(raw)
    assert calendar.receive_physical(1, ledger=ledger) == {}
    assert ledger.pair_balance(node_id=ORIGIN_PAIR[0], item_id=PAIR[1]) == 100000
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 0
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 600000}
    child = calendar.by_marker["ORDER1"]["lot_id"]
    assert child != parent and calendar.held_by_pair[PAIR] == 600000
    assert len(ledger.genealogy_rows) == 1
    link = ledger.genealogy_rows[0]
    assert (link["parent_lot_id"], link["child_lot_id"], link["parent_qty"], link["child_qty"]) == (
        parent, child, 600000, 600000)
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=3, node_id=PAIR[0], item_id=PAIR[1], qty=1,
            event_type="production_consume", uom="G")
    calendar.release("ORDER1", 13, 600000, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0 and len(ledger.lots) == 2
    assert [(r["event_type"], r["day"], r["qty"]) for r in ledger.event_rows if r["lot_id"] == child] == [
        ("lane_receipt", 2, 600000), ("stock_availability_hold", 2, 600000),
        ("stock_availability_release", 13, 600000)]
    ledger.consume(day=13, node_id=PAIR[0], item_id=PAIR[1], qty=100000,
        event_type="production_consume", uom="G")
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 500000
    assert raw == original


@pytest.mark.parametrize("fault", ["duplicate_order", "duplicate_G", "early_I", "wrong_I_quantity"])
def test_internal_delivery_rejects_duplicate_or_invalid_transition_without_mutation(fault):
    ledger, calendar, raw, _ = transferred_material()
    calendar.receive_physical(2, ledger=ledger)
    before = deepcopy((ledger.event_rows, ledger.genealogy_rows, ledger.lots, calendar.held_by_pair))
    with pytest.raises(ValueError):
        if fault == "duplicate_order": calendar.add_order(raw)
        elif fault == "duplicate_G": calendar.receive_physical(2, ledger=ledger)
        elif fault == "early_I": calendar.release("ORDER1", 12, 600000, ledger=ledger)
        else: calendar.release("ORDER1", 13, 600001, ledger=ledger)
    assert (ledger.event_rows, ledger.genealogy_rows, ledger.lots, calendar.held_by_pair) == before


def native_internal_evidence(*, horizon=20):
    ledger, calendar, raw, _ = transferred_material()
    calendar.receive_physical(2, ledger=ledger)
    if horizon > 13:
        calendar.release("ORDER1", 13, 600000, ledger=ledger)
    order = {**raw, "order_type": "lane_release", "planned_receipt_qty": "600000",
        "available_day": "13", "actual_physical_receipt_day": "2",
        "actual_available_day": "13" if horizon > 13 else ""}
    return order, ledger


@pytest.mark.parametrize("horizon", [10, 20])
def test_native_internal_audit_accepts_actual_child_lot_and_future_availability(horizon):
    from etudecas.testing.independent_review import Evidence, audit_internal_transfer_availability
    order, ledger = native_internal_evidence(horizon=horizon)
    evidence = Evidence()
    assert audit_internal_transfer_availability([order], ledger.event_rows, ledger.genealogy_rows,
        horizon, {PAIR}, evidence) == 1
    assert all(r["failed"] == 0 for r in evidence.checks.values())


@pytest.mark.parametrize("fault,failed_check", [
    ("second_receipt", "internal_transfer_single_physical"),
    ("wrong_I", "internal_transfer_availability_date"),
    ("new_lot_at_I", "internal_transfer_same_lot_G_I"),
    ("unlinked_parent", "internal_transfer_transported_parents"),
    ("orphan_hold", "internal_transfer_no_orphan_availability"),
])
def test_native_internal_audit_rejects_broken_date_or_material_identity_in_memory(fault, failed_check):
    from etudecas.testing.independent_review import Evidence, audit_internal_transfer_availability
    order, ledger = native_internal_evidence()
    events, links = deepcopy(ledger.event_rows), deepcopy(ledger.genealogy_rows)
    receipt = next(r for r in events if r["event_type"] == "lane_receipt")
    release = next(r for r in events if r["event_type"] == "stock_availability_release")
    if fault == "second_receipt": events.append(deepcopy(receipt))
    elif fault == "wrong_I": release["day"] = 12
    elif fault == "new_lot_at_I": release["lot_id"] = "NONEXISTENT"
    elif fault == "unlinked_parent": links[0]["parent_lot_id"] = "OTHER"
    else:
        orphan = deepcopy(next(r for r in events if r["event_type"] == "stock_availability_hold"))
        orphan["source_id"] = "NO_ORDER"
        events.append(orphan)
    evidence = Evidence()
    audit_internal_transfer_availability([order], events, links, 20, {PAIR}, evidence)
    assert evidence.checks[failed_check]["failed"] > 0


def test_internal_held_lot_events_export_in_memory_with_the_real_writer_columns():
    _, ledger = native_internal_evidence()
    fields = engine.lot_trace_csv_fields(dated_availability=True)
    for kind, rows in (("events", ledger.event_rows), ("genealogy", ledger.genealogy_rows)):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=fields[kind])
        writer.writeheader()
        writer.writerows(rows)
        exported = list(csv.DictReader(io.StringIO(stream.getvalue())))
        assert len(exported) == len(rows)
        assert all(r.get("shipment_id", "") == str(original.get("shipment_id", ""))
                   for r, original in zip(exported, rows))


@pytest.mark.parametrize("parents", [(600000, 600000), (400000, 400000, 400000)])
def test_native_internal_audit_understands_total_child_quantity_on_each_parent_link(parents):
    from etudecas.testing.independent_review import Evidence, audit_internal_transfer_availability
    ledger, calendar, raw, _ = transferred_material(parent_quantities=parents, transfer_qty=1200000)
    calendar.receive_physical(2, ledger=ledger)
    calendar.release("ORDER1", 13, 1200000, ledger=ledger)
    order = {**raw, "order_type": "lane_release", "planned_receipt_qty": "1200000",
             "available_day": "13", "actual_physical_receipt_day": "2", "actual_available_day": "13"}
    assert len(ledger.genealogy_rows) == len(parents)
    assert [r["parent_qty"] for r in ledger.genealogy_rows] == list(parents)
    assert all(r["child_qty"] == 1200000 for r in ledger.genealogy_rows)
    evidence = Evidence()
    audit_internal_transfer_availability([order], ledger.event_rows, ledger.genealogy_rows, 20, {PAIR}, evidence)
    assert all(r["failed"] == 0 for r in evidence.checks.values())
    # A real missing parent quantity must still fail; only the interpretation
    # of the repeated child total changed. No disk files are altered.
    damaged_links = deepcopy(ledger.genealogy_rows)
    damaged_links[0]["parent_qty"] -= 1
    invalid = Evidence()
    audit_internal_transfer_availability([order], ledger.event_rows, damaged_links, 20, {PAIR}, invalid)
    assert invalid.checks["internal_transfer_genealogy_parent_quantity"]["failed"] == 1
