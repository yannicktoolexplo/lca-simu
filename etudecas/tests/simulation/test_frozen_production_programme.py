"""Independent, memory-only acceptance examples for a rolling production freeze.

The launch-date convention is an explicit modelling assumption. Twenty-eight
and fifty-six calendar days come from the user, not from these implementation
helpers. Expected dates/quantities below are literal manual calculations.
No fixture, filesystem mutation, engine run or fabricated source file is used.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from etudecas.simulation.engine.frozen_production import (
    FrozenProductionBook, J0_NET_PLAN_HYPOTHESIS_POLICY,
)
from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, IndustrialPlanningWindow, LotSizing, OrderProposal, Requirement,
    UnreportedPlanningWindow, exclude_unreported_revocable_requirements,
    reconcile_industrial_requirements,
    plan_dated_requirements,
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


def initial_hypothesis_book():
    return FrozenProductionBook({"M-1810":28,"M-1430":56},
        bom_by_pair={PF1810:[(COMPONENT,2)]}, initial_book_policy=J0_NET_PLAN_HYPOTHESIS_POLICY)


def initial_admission_snapshot(*proposals):
    """Minimal in-memory proposal snapshot; netting has separate literal oracles."""
    empty = plan_dated_requirements(decision_day=0,available_qty=0,requirements=[],
        firm_receipts=[],lead_days=0,lot_sizing=LotSizing(integer=True))
    return replace(empty,proposals=tuple(proposals),proposed_qty=sum(p.qty for p in proposals))


@pytest.mark.parametrize("pair,horizon", [(PF1810,28),(PF1430,56)])
def test_j0_adoption_preserves_dates_and_quantities_only_inside_initial_window(pair,horizon):
    book=initial_hypothesis_book()
    plan=initial_admission_snapshot(proposal("today",0,10),proposal("first",1,20),
        proposal("last_inside",horizon-1,30),proposal("boundary",horizon,40),
        proposal("outside",horizon+1,50))
    before=deepcopy(plan)
    outside=book.adopt_initial_plan(pair,plan=plan,knowledge_cutoff_day=0,
        basis="first net J0 plan after observed opening books, finite calendar preserved")
    assert [p.proposal_id for p in outside] == ["today","boundary","outside"]
    assert plan == before
    rows=list(book.orders.values())
    assert [(r["planned_release_day"],r["qty"],r["state"]) for r in rows] == [
        (1,20,"frozen"),(horizon-1,30,"frozen")]
    assert [r["planned_available_day"] for r in rows] == [4,horizon+2]
    assert all(r["order_id"].startswith("BOOTSTRAP|") and r["frozen_day"] == 0 for r in rows)
    assert [r["source_proposal_id"] for r in rows] == ["first","last_inside"]
    assert all(r["origin"] == "hypothesized_initial_plan" and r["knowledge_cutoff_day"] == 0
               and r["basis"].startswith("first net J0 plan") for r in rows)
    assert [r["event"] for r in book.events] == ["initial_hypothesis_adopted"]*2
    # Passing only the remainder to ordinary review cannot create a second
    # reservation of either adopted quantity; J0 itself remains inadmissible.
    book.reconcile(pair,0,outside)
    assert sum(r["qty"] for r in book.orders.values()) == 140  #20+30+40+50.
    assert sum(r.qty for r in book.firm_receipts(pair,0)) == 50
    assert book.due(pair,0) is None


def test_j0_adoption_requires_explicit_policy_and_preserves_default_records():
    default=make_book()
    before=deepcopy(default.__dict__)
    with pytest.raises(ValueError):
        default.adopt_initial_plan(PF1810,plan=initial_admission_snapshot(proposal("net",10)),basis="test")
    assert default.__dict__ == before
    with pytest.raises(ValueError):
        FrozenProductionBook({"M-1810":28},initial_book_policy="unknown")
    enabled=initial_hypothesis_book()
    for book in (default,enabled):
        book.register_initial(PF1810,order_id="observed",release_day=7,available_day=10,qty=100)
        book.reconcile(PF1810,0,[proposal("future",60)])
    # Merely enabling the option must not relabel an observed order or change
    # ordinary events. Only adopt_initial_plan creates hypothesis provenance.
    assert default.orders == enabled.orders
    assert default.events == enabled.events
    assert "origin" not in enabled.orders["observed"]
    assert enabled.events[0]["event"] == "initial_observed"


@pytest.mark.parametrize("empty", [False,True])
def test_j0_adoption_is_once_per_pair_even_when_first_plan_has_no_net_order(empty):
    book=initial_hypothesis_book()
    plan=initial_admission_snapshot(*([] if empty else [proposal("net",10)]))
    book.adopt_initial_plan(PF1810,plan=plan,basis="net J0")
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        book.adopt_initial_plan(PF1810,plan=plan,basis="second attempt")
    assert book.__dict__ == before
    # The other factory has its own first plan, not a second initialization
    # of the first factory's order book.
    book.adopt_initial_plan(PF1430,plan=initial_admission_snapshot(proposal("other",43)),basis="other net J0")
    assert len({r["order_id"] for r in book.orders.values()}) == (1 if empty else 2)


@pytest.mark.parametrize("cutoff", [-1,1,True])
def test_j0_adoption_rejects_nonzero_or_noninteger_knowledge_without_mutation(cutoff):
    book=initial_hypothesis_book()
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        book.adopt_initial_plan(PF1810,plan=initial_admission_snapshot(proposal("net",10)),
            knowledge_cutoff_day=cutoff,basis="net J0")
    assert book.__dict__ == before


@pytest.mark.parametrize("late_clock", [False,True])
def test_j0_adoption_rejects_later_plan_or_later_execution_day_atomically(late_clock):
    book=initial_hypothesis_book()
    plan=initial_admission_snapshot(proposal("net",10))
    if late_clock:
        book.begin_day(1)
    else:
        plan=replace(plan,decision_day=1)
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        book.adopt_initial_plan(PF1810,plan=plan,basis="not a J0 initialization")
    assert book.__dict__ == before


@pytest.mark.parametrize("invalid", ["duplicate","negative_quantity","fractional_day","missing_identity","wrong_total"])
def test_j0_adoption_validates_whole_plan_before_first_order_or_event(invalid):
    book=initial_hypothesis_book()
    good=proposal("good",10)
    bad=proposal("bad",60)  #Invalid outside the adoption window must also fail.
    if invalid == "duplicate":
        bad=replace(bad,proposal_id="good")
    elif invalid == "negative_quantity":
        bad=replace(bad,qty=-1)
    elif invalid == "fractional_day":
        bad=replace(bad,release_day=60.5)
    elif invalid == "missing_identity":
        bad=replace(bad,proposal_id="")
    plan=initial_admission_snapshot(good,bad)
    if invalid == "wrong_total":
        plan=replace(plan,proposed_qty=201)
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        book.adopt_initial_plan(PF1810,plan=plan,basis="net J0")
    assert book.__dict__ == before


def test_j0_adoption_requires_basis_and_precedes_ordinary_review():
    book=initial_hypothesis_book()
    plan=initial_admission_snapshot(proposal("net",10))
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        book.adopt_initial_plan(PF1810,plan=plan,basis=" ")
    assert book.__dict__ == before
    book.reconcile(PF1810,0,[proposal("ordinary_future",50)])
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        book.adopt_initial_plan(PF1810,plan=plan,basis="too late after first review")
    assert book.__dict__ == before


def test_j0_adoption_uses_net130_after_stock20_and_observed_order100():
    book=initial_hypothesis_book()
    observed=FirmReceipt("source_OF_100",10,100,"confirmed")
    requirements=[Requirement("gross250",20,250)]
    plan=plan_dated_requirements(decision_day=0,available_qty=20,requirements=requirements,
        firm_receipts=[observed],lead_days=3,lot_sizing=LotSizing(integer=True))
    assert [(p.release_day,p.available_day,p.qty) for p in plan.proposals] == [(17,20,130)]
    outside=book.adopt_initial_plan(PF1810,plan=plan,basis="net source_OF_100 and usable20 at J0")
    assert outside == ()
    row,=book.orders.values()
    assert row["qty"] == 130 and row["executed_qty"] == 0 and row["campaign_id"] == ""
    assert sum(r.qty for r in book.material_requirements(0)[COMPONENT]) == 260
    assert sum(r.qty for r in book.firm_receipts(PF1810,0)) == 130
    # Native observed book remains separate. Credit it once beside the newly
    # adopted net requirement; current usable physical stock is still20.
    replanned=plan_dated_requirements(decision_day=0,available_qty=20,requirements=requirements,
        firm_receipts=[observed,*book.firm_receipts(PF1810,0)],lead_days=3,
        lot_sizing=LotSizing(integer=True))
    assert replanned.proposals == ()
    assert replanned.opening_available_qty == 20
    assert observed == FirmReceipt("source_OF_100",10,100,"confirmed")


def test_j0_adoption_adds_nothing_when_observed_order_and_stock_cover_every_need():
    book=initial_hypothesis_book()
    book.register_initial(PF1810,order_id="observed",release_day=7,available_day=10,qty=100)
    observed_before=deepcopy(book.orders["observed"])
    events_before=deepcopy(book.events)
    plan=plan_dated_requirements(decision_day=0,available_qty=20,
        requirements=[Requirement("gross120",20,120)],firm_receipts=book.firm_receipts(PF1810,0),
        lead_days=3,lot_sizing=LotSizing(integer=True))
    assert plan.proposals == ()
    assert book.adopt_initial_plan(PF1810,plan=plan,basis="full coverage by known opening state") == ()
    assert book.orders == {"observed":observed_before}
    assert book.events == events_before
    assert sum(r.qty for r in book.firm_receipts(PF1810,0)) == 100


def test_j0_adopted_order_hands_off_once_to_native_wip_without_double_credit():
    book=initial_hypothesis_book()
    book.adopt_initial_plan(PF1810,plan=initial_admission_snapshot(proposal("net100",10)),
        basis="net J0 with initial observed books already deducted")
    identity,=book.orders
    book.blocked(identity,day=10,reason="components_not_physically_available")
    assert book.orders[identity]["executed_qty"] == 0
    assert book.orders[identity]["campaign_id"] == ""
    assert sum(r.qty for r in book.firm_receipts(PF1810,10)) == 100
    book.bind(identity,day=12,campaign_id="native_campaign")
    book.bind(identity,day=12,campaign_id="native_campaign")
    book.execute(identity,day=12,qty=25)
    assert not book.firm_receipts(PF1810,12)
    assert not book.reserved_work(PF1810,12)
    assert not book.material_requirements(12)
    #25 executed WIP plus75 remaining work are one native receipt of100;
    # neither the unstarted book nor physical usable stock contributes again.
    plan=plan_dated_requirements(decision_day=12,available_qty=0,
        requirements=[Requirement("gross100",20,100)],
        firm_receipts=[FirmReceipt("campaign:native_campaign",15,100,"confirmed")],
        lead_days=3,lot_sizing=LotSizing(integer=True))
    assert plan.proposals == () and plan.opening_available_qty == 0
    assert sum(e["event"] == "first_physical_work" for e in book.events) == 1
    assert all(e["origin"] == "hypothesized_initial_plan" for e in book.events)
    assert all(e["event"] != "initial_observed" for e in book.events)
