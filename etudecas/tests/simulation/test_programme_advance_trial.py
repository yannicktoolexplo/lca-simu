"""Pure in-memory contracts for the single existing order experiment."""
from copy import deepcopy
from dataclasses import replace

import pytest

from etudecas.simulation.analysis.programme_advance_trial import ProgrammeAdvance, programme_advance_trial
from etudecas.simulation.engine.frozen_production import FrozenProductionBook
from etudecas.simulation.engine.mrp_planning import OrderProposal


PAIR = ("factory", "item:product")
COMPONENT = ("factory", "item:component")
FIRST = "FROZEN|factory|item:product|1"
SECOND = "FROZEN|factory|item:product|2"


def proposal(identity, release, qty=100):
    return OrderProposal(identity, release, release + 3, release + 3, qty)


def scenario(identity=FIRST, *, known=2, target=8):
    return ProgrammeAdvance(PAIR, identity, known, target, target + 3, 100,
                            ("workbook!I214", "workbook!I431"))


def new_book():
    return FrozenProductionBook({"factory": 4}, bom_by_pair={PAIR: [(COMPONENT, 1.25)]})


def test_advance_changes_only_existing_identity_and_freezes_natively():
    native_method = FrozenProductionBook.reconcile
    book = new_book()
    with programme_advance_trial(scenario()) as audit:
        book.reconcile(PAIR, 0, [proposal("lot", 12), proposal("other", 17, 75)])
        book.reconcile(PAIR, 1, [proposal("lot", 12), proposal("other", 17, 75)])
        second = book.orders[SECOND].copy()
        assert not audit
        for day, natural_release in [(2, 13), (3, 14), (4, 12)]:
            book.reconcile(PAIR, day, [proposal("lot", natural_release), proposal("other", 17, 75)])
            assert set(book.orders) == {FIRST, SECOND}
            assert book.orders[SECOND] == second
            first = book.orders[FIRST]
            assert (first["created_day"], first["known_day"], first["qty"]) == (0, 0, 100)
            assert (first["planned_release_day"], first["planned_available_day"]) == (8, 11)
            assert not book.firm_receipts(PAIR, day)
            assert not book.material_requirements(day)
        # Independent arithmetic. At day 4, 8 is exactly four days ahead.
        # At day 5, day 8 enters the half-open four-day freeze window.
        book.begin_day(5)
        book.reconcile(PAIR, 5, [proposal("other", 17, 75)])
        credit, = book.firm_receipts(PAIR, 5)
        material, = book.material_requirements(5)[COMPONENT]
        assert (credit.receipt_id, credit.available_day, credit.qty) == (FIRST, 11, 100)
        assert (material.due_day, material.qty) == (8, 125)
        assert book.reserved_work(PAIR, 5) == ((FIRST, 8, 100),)
        assert book.due(PAIR, 7) is None
        assert book.due(PAIR, 8)["order_id"] == FIRST
        assert book.orders[FIRST]["executed_qty"] == 0
        assert [entry["day"] for entry in audit] == [2, 3, 4, 5]
        assert [entry["native_release_day"] for entry in audit[:-1]] == [13, 14, 12]
        assert audit[-1]["event"] == "native_freeze_confirmed"
    assert FrozenProductionBook.reconcile is native_method


def test_advance_refuses_ambiguous_native_proposals_before_mutation():
    book = new_book()
    book.reconcile(PAIR, 0, [proposal("lot", 12), proposal("other", 17)])
    before_orders, before_events = deepcopy(book.orders), deepcopy(book.events)
    with programme_advance_trial(scenario()) as audit:
        with pytest.raises(ValueError, match="unambiguous equivalent lot"):
            book.reconcile(PAIR, 2, [proposal("rank1", 13), proposal("rank2", 13)])
        assert not audit
    assert (book.orders, book.events, book.day) == (before_orders, before_events, 0)


def test_advance_refuses_identity_swap_before_mutation():
    book = new_book()
    book.reconcile(PAIR, 0, [proposal("other", 9), proposal("lot", 12)])
    before_orders, before_events = deepcopy(book.orders), deepcopy(book.events)
    with programme_advance_trial(scenario(SECOND)):
        with pytest.raises(ValueError, match="alter other identities"):
            book.reconcile(PAIR, 2, [proposal("other", 10), proposal("lot", 13)])
    assert (book.orders, book.events, book.day) == (before_orders, before_events, 0)


def test_advance_refuses_missing_original_lot_and_restores_native_method():
    book = new_book()
    book.reconcile(PAIR, 0, [proposal("lot", 12)])
    original = FrozenProductionBook.reconcile
    with pytest.raises(ValueError, match="unambiguous equivalent lot"):
        with programme_advance_trial(scenario()):
            book.reconcile(PAIR, 2, [])
    assert FrozenProductionBook.reconcile is original
    assert book.orders[FIRST]["planned_release_day"] == 12
    assert book.orders[FIRST]["state"] == "planned"


@pytest.mark.parametrize("preserve", [False, True], ids=["revocable", "preserved"])
def test_option_preserves_only_the_advanced_commitment(preserve):
    original_reducible = FrozenProductionBook.reducible_unstarted_orders
    book = new_book()
    trial = replace(scenario(), preserve_frozen_commitment=True) if preserve else scenario()
    with programme_advance_trial(trial) as audit:
        book.reconcile(PAIR, 0, [proposal("lot", 12), proposal("other", 17, 75)])
        for day in range(2, 5):
            book.reconcile(PAIR, day, [proposal("lot", 13), proposal("other", 17, 75)])
        assert book.reducible_unstarted_orders() == ()
        book.begin_day(5)
        # The daily reduction review can occur before the closing reconcile.
        assert bool(book.reducible_unstarted_orders()) is not preserve
        book.reconcile(PAIR, 5, [proposal("other", 10, 75)])
        book.begin_day(7)
        candidate_ids = {row["order_id"] for row in book.reducible_unstarted_orders()}
        assert candidate_ids == ({SECOND} if preserve else {FIRST, SECOND})
        book.cancel_unstarted_whole_lot(SECOND, day=7)
        assert book.orders[SECOND]["state"] == "cancelled"
        if preserve:
            with pytest.raises(ValueError, match="current, unstarted simulated frozen order"):
                book.cancel_unstarted_whole_lot(FIRST, day=7)
            credit, = book.firm_receipts(PAIR, 7)
            assert (credit.receipt_id, credit.available_day, credit.qty) == (FIRST, 11, 100)
        else:
            book.cancel_unstarted_whole_lot(FIRST, day=7)
            assert not book.firm_receipts(PAIR, 7)
        protection = [entry for entry in audit if entry["event"] == "advanced_commitment_preserved_from_reduction"]
        assert [entry["day"] for entry in protection] == ([5, 7] if preserve else [])
    assert FrozenProductionBook.reducible_unstarted_orders is original_reducible
