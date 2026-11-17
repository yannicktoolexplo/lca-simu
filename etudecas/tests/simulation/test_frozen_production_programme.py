"""Independent, memory-only acceptance examples for a rolling production freeze.

The launch-date convention is an explicit modelling assumption. Twenty-eight
and fifty-six calendar days come from the user, not from these implementation
helpers. Expected dates/quantities below are literal manual calculations.
No fixture, filesystem mutation, engine run or fabricated source file is used.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.frozen_production import FrozenProductionBook
from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, IndustrialPlanningWindow, LotSizing, OrderProposal, Requirement,
    UnreportedPlanningWindow, exclude_unreported_revocable_requirements,
    reconcile_industrial_requirements,
)
from etudecas.simulation.engine.run_first_simulation import dated_production_release


PF1810 = ("M-1810", "item:268091")
PF1430 = ("M-1430", "item:268967")
COMPONENT = ("M-1810", "component")


def make_book():
    return FrozenProductionBook({"M-1810": 28, "M-1430": 56},
                                bom_by_pair={PF1810: [(COMPONENT, 2)]})


def proposal(identity, release, qty=100, available=None):
    available = release + 3 if available is None else available
    return OrderProposal(identity, release, available, available, qty)


def open_rows(book, pair):
    return [r for r in book.orders.values()
            if (r["node_id"], r["item_id"]) == pair
            and r["state"] not in {"cancelled", "completed"}]


@pytest.mark.parametrize("pair,inside,boundary", [
    (PF1810, 37, 38), (PF1430, 65, 66),
])
def test_new_order_requires_launch_outside_28_or_56_day_zone(pair, inside, boundary):
    # At J10 the intervals are [10,38) and [10,66), respectively.
    book = make_book()
    book.reconcile(pair, 10, [proposal("inside", inside), proposal("boundary", boundary)])
    assert [(r["planned_release_day"], r["qty"]) for r in open_rows(book, pair)] == [(boundary, 100)]
    assert book.due(pair, inside) is None
    book.begin_day(boundary)
    due = book.due(pair, boundary)
    assert due["planned_release_day"] == boundary and due["qty"] == 100


@pytest.mark.parametrize("pair,first_new_day", [(PF1810, 28), (PF1430, 56)])
def test_empty_opening_book_does_not_invent_orders_inside_first_horizon(pair, first_new_day):
    book = make_book()
    book.reconcile(pair, 0, [proposal("opening_shortfall", 0),
                             proposal("day_before_boundary", first_new_day - 1),
                             proposal("outside", first_new_day)])
    assert [(r["planned_release_day"], r["qty"]) for r in open_rows(book, pair)] == [(first_new_day, 100)]
    assert book.due(pair, 0) is None
    # Absence of imported orders is not asserted to be absence in the factory.


def test_previous_boundary_order_freezes_before_recalculation_and_does_not_slide():
    book = make_book()
    book.reconcile(PF1810, 0, [proposal("previous", 28)])
    old, = open_rows(book, PF1810)
    identity = old["order_id"]
    assert old["state"] == "planned" and old["frozen_day"] is None
    # reconcile must freeze the previous plan before removing/replacing it.
    book.reconcile(PF1810, 1, [])
    for day in (2, 7, 14, 27):
        book.reconcile(PF1810, day, [])
    retained, = open_rows(book, PF1810)
    assert retained["order_id"] == identity
    assert (retained["planned_release_day"], retained["qty"], retained["frozen_day"]) == (28, 100, 1)
    assert book.due(PF1810, 27) is None
    book.begin_day(28)
    assert book.due(PF1810, 28)["order_id"] == identity


def test_skipped_reviews_keep_a_previous_order_that_is_already_overdue():
    book = make_book()
    book.reconcile(PF1810, 0, [proposal("previous", 28)])
    identity = open_rows(book, PF1810)[0]["order_id"]
    book.reconcile(PF1810, 30, [])
    due = book.due(PF1810, 30)
    assert (due["order_id"], due["planned_release_day"], due["qty"]) == (identity, 28, 100)
    assert due["frozen_day"] == 30


def test_order_outside_protected_interval_remains_revisable():
    book = make_book()
    book.reconcile(PF1810, 0, [proposal("far", 100, 100)])
    book.reconcile(PF1810, 1, [proposal("revised", 110, 130)])
    row, = open_rows(book, PF1810)
    assert (row["planned_release_day"], row["qty"], row["state"]) == (110, 130, "planned")
    book.begin_day(100)
    assert book.due(PF1810, 100) is None
    book.begin_day(110)
    assert book.due(PF1810, 110)["qty"] == 130


def test_fixed_order_keeps_date_and_quantity_when_later_net_proposal_changes():
    book = make_book()
    book.reconcile(PF1810, 0, [proposal("initial_plan", 28, 100)])
    book.reconcile(PF1810, 1, [])
    frozen_id = open_rows(book, PF1810)[0]["order_id"]
    # These are alternative NET needs outside the fence, not replacements for
    # the frozen100. A demand revision cannot silently rewrite that100.
    for day, net_qty in ((2, 300), (3, 600)):
        book.reconcile(PF1810, day, [proposal("outside_revision", 100, net_qty)])
        fixed = book.orders[frozen_id]
        assert (fixed["planned_release_day"], fixed["qty"], fixed["frozen_day"]) == (28, 100, 1)
    outside = [r for r in open_rows(book, PF1810) if r["order_id"] != frozen_id]
    assert len(outside) == 1 and outside[0]["qty"] == 600


def test_launch_date_controls_freeze_and_release_not_receipt_date():
    book = make_book()
    book.reconcile(PF1810, 0, [proposal("slow_receipt", 28, available=60)])
    book.begin_day(1)
    assert book.due(PF1810, 27) is None
    row = book.due(PF1810, 28)
    assert (row["planned_release_day"], row["planned_available_day"]) == (28, 60)


def test_new_due_order_and_advancement_into_protected_zone_are_refused():
    book = make_book()
    book.reconcile(PF1810, 10, [proposal("due_now", 10), proposal("future", 50)])
    assert book.due(PF1810, 10) is None
    assert [(r["planned_release_day"], r["qty"]) for r in open_rows(book, PF1810)] == [(50, 100)]
    book.reconcile(PF1810, 11, [proposal("advanced", 11)])
    assert book.due(PF1810, 11) is None
    assert not any(r["planned_release_day"] == 11 for r in open_rows(book, PF1810))


def test_known_initial_firm_is_preserved_and_executable_inside_zone():
    book = make_book()
    book.register_initial(PF1810, order_id="source_initial", release_day=10,
                          available_day=30, qty=100, known_day=0)
    book.reconcile(PF1810, 1, [])
    assert book.due(PF1810, 9) is None
    row = book.due(PF1810, 10)
    assert (row["planned_release_day"], row["planned_available_day"], row["qty"]) == (10, 30, 100)
    book.bind(row["order_id"], day=10, campaign_id="physical_campaign")
    assert book.orders[row["order_id"]]["actual_release_day"] == 10


def test_future_known_order_cannot_be_invented_as_an_opening_firm_order():
    book = make_book()
    with pytest.raises(ValueError):
        book.register_initial(PF1810, order_id="future_source", release_day=10,
                              available_day=30, qty=100, known_day=1)
    assert not book.orders


def test_backwards_review_cannot_rewrite_known_history():
    book = make_book()
    book.reconcile(PF1810, 10, [proposal("later", 50)])
    before = deepcopy(book.orders)
    with pytest.raises(ValueError):
        book.reconcile(PF1810, 9, [])
    assert book.orders == before


def test_net_need_credits_usable20_and_firm100_once_leaving130():
    book = make_book()
    book.register_initial(PF1810, order_id="firm100", release_day=10,
                          available_day=30, qty=100, known_day=0)
    book.begin_day(20)
    receipts = book.firm_receipts(PF1810, 20)
    assert sum(r.qty for r in receipts) == 100
    _, plan = dated_production_release(decision_day=20, snapshot_day=19,
        requirements=[Requirement("gross250", 60, 250)], available_qty=20,
        firm_receipts=receipts, lead_days=0, lot_sizing=LotSizing(integer=True))
    assert sum(r.qty for r in plan.proposals) == 130  #250-20-100.
    book.reconcile(PF1810, 20, plan.proposals)
    assert sum(r["qty"] for r in open_rows(book, PF1810)) == 230


def test_late_unexecuted_firm_stays_covered_without_becoming_physical_stock():
    book = make_book()
    book.register_initial(PF1810, order_id="late", release_day=10,
                          available_day=20, qty=100, known_day=0)
    book.begin_day(30)
    receipts = book.firm_receipts(PF1810, 30)
    assert len(receipts) == 1 and receipts[0].qty == 100
    # Planned calendar span20-10=10 days, shifted to day30 =>40, not stock now.
    # This is a scenario estimate, not proof that physical delivery can occur.
    assert receipts[0].available_day == 40
    assert book.orders["late"]["planned_available_day"] == 20
    _, plan = dated_production_release(decision_day=30, snapshot_day=29,
        requirements=[Requirement("unserved100", 30, 100)], available_qty=0,
        firm_receipts=receipts, lead_days=0, lot_sizing=LotSizing(integer=True))
    assert not plan.proposals and plan.late_qty == 100
    assert book.due(PF1810, 30)["qty"] == 100


@pytest.mark.parametrize("first40_usable", [False, True])
def test_partial_order_credits_received40_and_remaining60_exactly_once(first40_usable):
    book = make_book()
    book.register_initial(PF1810, order_id="remaining60", release_day=10,
                          available_day=30, qty=60, known_day=0)
    book.begin_day(20)
    firms = list(book.firm_receipts(PF1810, 20))
    stock = 20
    if first40_usable:
        stock += 40
    else:
        firms.append(FirmReceipt("already_received_in_quality", 25, 40, "held"))
    _, plan = dated_production_release(decision_day=20, snapshot_day=19,
        requirements=[Requirement("gross250", 60, 250)], available_qty=stock,
        firm_receipts=firms, lead_days=0, lot_sizing=LotSizing(integer=True))
    assert sum(r.qty for r in plan.proposals) == 130  #250-20-40-60, never250-20-40-100.


def test_active_work_is_not_credited_again_as_unlaunched_order():
    book = make_book()
    book.register_initial(PF1810, order_id="initial", release_day=10,
                          available_day=30, qty=100, known_day=0)
    book.begin_day(10)
    assert sum(r.qty for r in book.firm_receipts(PF1810, 10)) == 100
    book.bind("initial", day=10, campaign_id="campaign")
    book.execute("initial", day=10, qty=25)
    book.begin_day(11)  #A zero-capacity day must not cancel or recreate75.
    assert book.due(PF1810, 11) is None
    assert not book.firm_receipts(PF1810, 11)
    assert not book.reserved_work(PF1810, 11)
    assert not book.material_requirements(11).get(COMPONENT, ())
    row = book.orders["initial"]
    assert (row["qty"], row["executed_qty"], row["state"], row["planned_release_day"]) == (100, 25, "active", 10)
    book.execute("initial", day=12, qty=75)
    assert (row["qty"], row["executed_qty"], row["state"]) == (100, 100, "completed")


def test_reservations_do_not_double_or_consume_before_physical_launch():
    book = make_book()
    book.register_initial(PF1810, order_id="reserved", release_day=10,
                          available_day=30, qty=100, known_day=0)
    book.begin_day(1)
    first = deepcopy(book.orders)
    for _ in range(2):
        material = book.material_requirements(1)
        assert sum(r.qty for r in material[COMPONENT]) == 200  #100PF times2.
        work = book.reserved_work(PF1810, 1)
        assert sum(r[2] for r in work) == 100
    assert book.orders == first
    assert book.orders["reserved"]["executed_qty"] == 0


def test_physical_execution_needs_binding_and_cannot_exceed_firm_quantity():
    book = make_book()
    book.register_initial(PF1810, order_id="protected", release_day=10,
                          available_day=30, qty=100, known_day=0)
    before = deepcopy(book.orders)
    with pytest.raises(ValueError):
        book.execute("protected", day=10, qty=25)
    assert book.orders == before
    book.bind("protected", day=10, campaign_id="campaign")
    before = deepcopy(book.orders)
    with pytest.raises((ValueError, ArithmeticError)):
        book.execute("protected", day=10, qty=101)
    assert book.orders == before


def test_binding_does_not_advance_a_frozen_launch():
    book = make_book()
    book.register_initial(PF1810, order_id="future", release_day=10,
                          available_day=30, qty=100, known_day=0)
    before = deepcopy(book.orders)
    with pytest.raises(ValueError):
        book.bind("future", day=9, campaign_id="too_early")
    assert book.orders == before


def test_proposals_are_not_mutated_by_reconciliation():
    book = make_book()
    inputs = [proposal("kept", 28), proposal("future", 40)]
    before = deepcopy(inputs)
    book.reconcile(PF1810, 0, inputs)
    book.reconcile(PF1810, 1, [])
    assert inputs == before


@pytest.mark.parametrize("keep_second", [False, True])
def test_exact_survivor_keeps_identity_before_fifo_revisions_are_assigned(keep_second):
    book = make_book()
    book.reconcile(PF1810, 0, [proposal("A", 100), proposal("B", 110)])
    exact_id = next(r["order_id"] for r in open_rows(book, PF1810)
                    if r["planned_release_day"] == 100)
    other_id = next(r["order_id"] for r in open_rows(book, PF1810)
                    if r["planned_release_day"] == 110)
    # A survives unchanged. B either moves to95 or stays110 with a new order95.
    revised = [proposal("earlier", 95), proposal("same_A", 100)]
    if keep_second:
        revised.append(proposal("same_B", 110))
    book.reconcile(PF1810, 1, revised)
    assert book.orders[exact_id]["planned_release_day"] == 100
    assert book.orders[other_id]["planned_release_day"] == (110 if keep_second else 95)
    assert len(open_rows(book, PF1810)) == (3 if keep_second else 2)


@pytest.mark.parametrize("source_qty,expected_total", [(0, 200), (100, 200), (300, 300)])
def test_frozen_bom_is_committed_floor_not_a_revocable_forecast(source_qty, expected_total):
    book = make_book()
    book.register_initial(PF1810, order_id="firm", release_day=12,
                          available_day=30, qty=100, known_day=0)
    book.begin_day(4)
    fixed, = book.material_requirements(4)[COMPONENT]
    assert fixed.requirement_id.startswith("frozen_material:")
    assert (fixed.due_day, fixed.qty) == (12, 200)  #100PF times2.
    original = [fixed, Requirement("derived:revocable", 13, 80),
                Requirement("reserve:floor", 11, 10)]
    window = IndustrialPlanningWindow(11, 11, 18, source_qty, 4, "memory", "budget")
    result, audit = reconcile_industrial_requirements(original, [window],
        pair=COMPONENT, decision_day=4, policy="source_weekly_with_committed_floor_v1")
    assert fixed in result and original[2] in result
    assert not any(r.requirement_id == "derived:revocable" for r in result)
    # The residual forecast is continuous and distributed over seven days;
    # 200 engaged units stay exact, but seven binary floats need a tiny tolerance.
    assert sum(r.qty for r in result if not r.requirement_id.startswith("reserve:")) == pytest.approx(
        expected_total, rel=0, abs=1e-9)
    assert audit[0]["committed_qty"] == 200


def test_unreported_source_week_preserves_frozen_bom_instead_of_assuming_zero():
    fixed = Requirement("frozen_material:firm:component", 12, 200)
    reserve = Requirement("reserve:floor", 11, 10)
    original = [fixed, Requirement("derived:revocable", 13, 80), reserve]
    window = UnreportedPlanningWindow(11, 11, 18, 4, 11, 18, "memory", "coverage")
    retained, audit = exclude_unreported_revocable_requirements(original, [window], decision_day=4)
    assert retained == [fixed, reserve]
    assert sum(r.qty for r in retained) == 210
    assert audit[0]["preserved_committed_qty"] == 200
    assert audit[0]["removed_revocable_qty"] == 80
    assert audit[0]["status"] == "unreported_week_assumed_no_revocable_need_not_observed_zero"


def test_launch_delay_stays_fixed_after_actual_start_and_completion():
    book = make_book()
    book.register_initial(PF1810, order_id="delay", release_day=10,
                          available_day=20, qty=100, known_day=0)
    book.begin_day(11)
    book.blocked("delay", day=11, reason="no_material_yet")
    assert book.events[-1]["launch_delay_days"] == 1
    book.bind("delay", day=12, campaign_id="campaign")
    book.execute("delay", day=12, qty=25)
    book.execute("delay", day=13, qty=25)
    book.execute("delay", day=14, qty=50)
    work = [r for r in book.events if r["event"] in ("first_physical_work", "physical_work")]
    assert [r["day"] for r in work] == [12, 12, 13, 14]
    assert [r["launch_delay_days"] for r in work] == [2, 2, 2, 2]
    assert work[-1]["state"] == "completed"
    assert book.orders["delay"]["planned_release_day"] == 10
    assert book.orders["delay"]["actual_release_day"] == 12
