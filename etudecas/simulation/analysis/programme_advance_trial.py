"""Bounded experiment with dates of existing production orders.

The adapter is installed for one synchronous simulation in a dedicated
process. The native book still decides when the order becomes firm and
provides its work, receipt and material requirements.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass, replace

from etudecas.simulation.engine.frozen_production import FrozenProductionBook


@dataclass(frozen=True)
class ProgrammeAdvance:
    pair: tuple[str, str]
    order_id: str
    known_day: int
    target_release_day: int
    target_available_day: int
    qty: int
    source_evidence: tuple[str, ...]
    preserve_frozen_commitment: bool = False

    def __post_init__(self):
        if (not isinstance(self.pair, (tuple, list)) or len(self.pair) != 2
                or any(not isinstance(part, str) or not part.strip() for part in self.pair)
                or not isinstance(self.order_id, str) or not self.order_id.strip()):
            raise ValueError("The advance requires an explicit site, item and existing order identity")
        if (any(type(day) is not int for day in
                (self.known_day, self.target_release_day, self.target_available_day))
                or not 0 <= self.known_day < self.target_release_day <= self.target_available_day
                or type(self.qty) is not int or self.qty <= 0):
            raise ValueError("The advance requires ordered dates and a positive whole-lot quantity")
        if (not isinstance(self.source_evidence, (tuple, list)) or not self.source_evidence
                or any(not isinstance(cell, str) or not cell.strip() for cell in self.source_evidence)):
            raise ValueError("The advance requires references for the signal known at the decision date")
        if type(self.preserve_frozen_commitment) is not bool:
            raise ValueError("Preserving the advanced commitment must be an explicit boolean hypothesis")
        object.__setattr__(self, "pair", tuple(self.pair))
        object.__setattr__(self, "source_evidence", tuple(self.source_evidence))


def _preview_book(book):
    """Copy the state used by native reconcile without copying the full journal."""
    preview = copy(book)
    preview.orders = {identity: row.copy() for identity, row in book.orders.items()}
    preview.events = []
    preview._reviewed_pairs = book._reviewed_pairs.copy()
    return preview


def _order_signature(order):
    return (order["planned_release_day"], order["planned_available_day"],
            order["requested_day"], order["qty"])


def _has_expected_freeze(book, scenario, freeze_day):
    frozen = [event for event in book.events
              if event["order_id"] == scenario.order_id and event["event"] == "frozen_before_review"]
    return (len(frozen) == 1 and frozen[0]["day"] == freeze_day
            and _order_signature(frozen[0])[:2] == (scenario.target_release_day, scenario.target_available_day)
            and frozen[0]["qty"] == scenario.qty)


@dataclass
class _AdvanceState:
    scenario: ProgrammeAdvance
    natural_order: dict | None = None
    freeze_checked: bool = False
    book: FrozenProductionBook | None = None

    def freeze_day(self, book):
        return self.scenario.target_release_day - book.horizons_by_node[self.scenario.pair[0]] + 1


def _validate_existing_lot(state, book, pair, day):
    scenario = state.scenario
    identity = scenario.order_id
    current = book.orders.get(identity)
    if not current or (current["node_id"], current["item_id"]) != pair:
        raise ValueError("The designated existing manufacturing order is absent")
    if (current["state"] != "planned" or current["qty"] != scenario.qty
            or current["created_day"] >= scenario.known_day or current["known_day"] > day
            or current["actual_release_day"] is not None or current["executed_qty"] != 0
            or current["campaign_id"]):
        raise ValueError("Only an existing, unstarted planned lot of the same quantity can advance")
    if state.natural_order is None and (day != scenario.known_day or not any(
            event["order_id"] == identity and event["event"] == "created_outside_zone"
            for event in book.events)):
        raise ValueError("The first eligible review must follow the origin of a simulated lot")


def _matching_advance(scenario, natural, proposals):
    matches = [proposal for proposal in proposals if
               (proposal.release_day, proposal.available_day, proposal.requested_day, proposal.qty)
               == _order_signature(natural)]
    if (natural["state"] != "planned" or len(matches) != 1 or natural["qty"] != scenario.qty
            or natural["planned_release_day"] <= scenario.target_release_day
            or natural["planned_available_day"] - natural["planned_release_day"]
            != scenario.target_available_day - scenario.target_release_day):
        raise ValueError("No unambiguous equivalent lot with the original planning span to advance")
    original = matches[0]
    return original, replace(original, release_day=scenario.target_release_day,
                             available_day=scenario.target_available_day)


@contextmanager
def programme_advance_trial(scenario: ProgrammeAdvance | tuple[ProgrammeAdvance, ...]):
    """Revise one or two existing lots for one pair until their native freezes."""
    scenarios = (scenario,) if isinstance(scenario, ProgrammeAdvance) else tuple(scenario)
    if (len(scenarios) not in (1, 2) or len({row.order_id for row in scenarios}) != len(scenarios)
            or len({row.known_day for row in scenarios}) != len(scenarios)
            or len({row.pair for row in scenarios}) != 1):
        raise ValueError("Expected at most two distinct existing orders with separate knowledge dates for one pair")
    states = [_AdvanceState(row) for row in sorted(scenarios, key=lambda row: row.known_day)]
    protected = {state.scenario.order_id: state for state in states if state.scenario.preserve_frozen_commitment}
    native_reconcile = FrozenProductionBook.reconcile
    native_reducible = FrozenProductionBook.reducible_unstarted_orders
    audit = []
    preserved_reviews = set()

    def reconcile(book, pair, day, proposals):
        pending = [state for state in states if pair == state.scenario.pair
                   and day >= state.scenario.known_day and not state.freeze_checked]
        if not pending:
            return native_reconcile(book, pair, day, proposals)

        revising, freezing = [], []
        for state in pending:
            freeze_day = state.freeze_day(book)
            if day < freeze_day:
                _validate_existing_lot(state, book, pair, day)
                revising.append(state)
            else:
                if (book is not state.book or day != freeze_day
                        or not _has_expected_freeze(book, state.scenario, freeze_day)):
                    raise ValueError("The designated order did not enter the native freeze as expected")
                freezing.append(state)

        changes = []
        adjusted = proposals
        if revising:
            # Restore the unmodified dates only for native proposal matching.
            # The joint preview ensures that every unaffected identity survives.
            proposals = tuple(proposals)
            reference = _preview_book(book)
            for state in revising:
                if state.natural_order is not None:
                    reference.orders[state.scenario.order_id] = state.natural_order.copy()
            native_reconcile(reference, pair, day, proposals)
            for state in revising:
                natural = reference.orders[state.scenario.order_id]
                original, advanced = _matching_advance(state.scenario, natural, proposals)
                changes.append((state, natural, original, advanced))
            replacements = {old.proposal_id: new for _, _, old, new in changes}
            if len(replacements) != len(changes):
                raise ValueError("Each advanced lot requires its own native proposal")
            adjusted = tuple(replacements.get(proposal.proposal_id, proposal) for proposal in proposals)
            preview = _preview_book(book)
            native_reconcile(preview, pair, day, adjusted)
            expected = {state.scenario.order_id: (new.release_day, new.available_day, new.requested_day, new.qty)
                        for state, _, _, new in changes}
            if (preview.orders.keys() != reference.orders.keys() or preview.sequence != reference.sequence
                    or any(_order_signature(preview.orders[key]) != signature
                           or preview.orders[key]["state"] != "planned" for key, signature in expected.items())
                    or any(row != reference.orders[key] for key, row in preview.orders.items() if key not in expected)):
                raise ValueError("Advancing this lot would alter other identities, quantities or commitments")

        result = native_reconcile(book, pair, day, adjusted)
        for state in freezing:
            selected = state.scenario
            state.freeze_checked = True
            audit.append(dict(day=day, event="native_freeze_confirmed", order_id=selected.order_id,
                target_release_day=selected.target_release_day, target_available_day=selected.target_available_day,
                qty=selected.qty))
        for state, natural, original, advanced in changes:
            selected = state.scenario
            state.natural_order = natural.copy()
            state.book = book
            audit.append(dict(day=day, event="existing_lot_date_advanced", order_id=selected.order_id,
                known_day=selected.known_day, source_evidence=list(selected.source_evidence),
                from_proposal_id=original.proposal_id, native_release_day=original.release_day,
                native_available_day=original.available_day, requested_day=original.requested_day,
                target_release_day=advanced.release_day, target_available_day=advanced.available_day,
                qty=selected.qty, freeze_day=state.freeze_day(book), same_day_proposal_count=len(proposals),
                same_day_proposal_qty=sum(proposal.qty for proposal in proposals)))
        return result

    def reducible_unstarted_orders(book):
        candidates = native_reducible(book)
        retained = []
        for row in candidates:
            identity = row["order_id"]
            state = protected.get(identity)
            if state is None or book is not state.book:
                retained.append(row)
                continue
            selected = state.scenario
            freeze_day = state.freeze_day(book)
            if book.day < freeze_day or not _has_expected_freeze(book, selected, freeze_day):
                raise ValueError("The commitment can only be preserved after its traced native freeze")
            review = (identity, book.day)
            if review not in preserved_reviews:
                preserved_reviews.add(review)
                audit.append(dict(day=book.day, event="advanced_commitment_preserved_from_reduction",
                    order_id=identity, qty=selected.qty, known_day=selected.known_day,
                    freeze_day=freeze_day, reason="scenario_assumes_known_factory_programme_is_firm"))
        return tuple(retained)

    FrozenProductionBook.reconcile = reconcile
    if protected:
        FrozenProductionBook.reducible_unstarted_orders = reducible_unstarted_orders
    try:
        yield audit
    finally:
        FrozenProductionBook.reconcile = native_reconcile
        if protected:
            FrozenProductionBook.reducible_unstarted_orders = native_reducible
