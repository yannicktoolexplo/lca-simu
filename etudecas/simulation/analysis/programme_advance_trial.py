"""Bounded experiment with the date of one existing production order.

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


@contextmanager
def programme_advance_trial(scenario: ProgrammeAdvance):
    """Revise the date of one order until its native freeze.

    An explicit alternative assumes that the factory keeps this one
    commitment when it reviews surplus frozen orders.
    """
    native_reconcile = FrozenProductionBook.reconcile
    native_reducible = FrozenProductionBook.reducible_unstarted_orders
    audit = []
    native_order_before_advance = None
    freeze_checked = False
    advanced_book = None
    preserved_days = set()

    def reconcile(book, pair, day, proposals):
        nonlocal native_order_before_advance, freeze_checked, advanced_book
        if pair != scenario.pair or day < scenario.known_day or freeze_checked:
            return native_reconcile(book, pair, day, proposals)

        horizon = book.horizons_by_node[pair[0]]
        freeze_day = scenario.target_release_day - horizon + 1
        identity = scenario.order_id
        current = book.orders.get(identity)
        if not current or (current["node_id"], current["item_id"]) != pair:
            raise ValueError("The designated existing manufacturing order is absent")
        if day >= freeze_day:
            if (book is not advanced_book or day != freeze_day
                    or not _has_expected_freeze(book, scenario, freeze_day)):
                raise ValueError("The designated order did not enter the native freeze as expected")
            result = native_reconcile(book, pair, day, proposals)
            audit.append(dict(day=day, event="native_freeze_confirmed", order_id=identity,
                              target_release_day=scenario.target_release_day,
                              target_available_day=scenario.target_available_day,
                              qty=scenario.qty))
            freeze_checked = True
            return result
        if (current["state"] != "planned" or current["qty"] != scenario.qty
                or current["created_day"] >= scenario.known_day or current["known_day"] > day
                or current["actual_release_day"] is not None or current["executed_qty"] != 0
                or current["campaign_id"]):
            raise ValueError("Only an existing, unstarted planned lot of the same quantity can advance")
        if native_order_before_advance is None and (day != scenario.known_day or not any(
                event["order_id"] == identity and event["event"] == "created_outside_zone"
                for event in book.events)):
            raise ValueError("The first eligible review must follow the origin of a simulated lot")

        # Keep the unmodified dates for matching only. This mirrors the
        # association native reconcile would make on this day's proposals.
        proposals = tuple(proposals)
        reference = _preview_book(book)
        if native_order_before_advance is not None:
            reference.orders[identity] = native_order_before_advance.copy()
        native_reconcile(reference, pair, day, proposals)
        natural = reference.orders[identity]
        signature = _order_signature(natural)
        matches = [proposal for proposal in proposals if
                   (proposal.release_day, proposal.available_day, proposal.requested_day, proposal.qty) == signature]
        if (natural["state"] != "planned" or len(matches) != 1 or natural["qty"] != scenario.qty
                or natural["planned_release_day"] <= scenario.target_release_day
                or natural["planned_available_day"] - natural["planned_release_day"]
                != scenario.target_available_day - scenario.target_release_day):
            raise ValueError("No unambiguous equivalent lot with the original planning span to advance")
        original = matches[0]
        advanced = replace(original, release_day=scenario.target_release_day,
                           available_day=scenario.target_available_day)
        adjusted = tuple(advanced if proposal is original else proposal for proposal in proposals)
        preview = _preview_book(book)
        native_reconcile(preview, pair, day, adjusted)
        revised = preview.orders[identity]
        expected = (advanced.release_day, advanced.available_day, advanced.requested_day, advanced.qty)
        if (preview.orders.keys() != reference.orders.keys() or preview.sequence != reference.sequence
                or _order_signature(revised) != expected or revised["state"] != "planned"
                or any(row != reference.orders[key] for key, row in preview.orders.items() if key != identity)):
            raise ValueError("Advancing this lot would alter other identities, quantities or commitments")

        result = native_reconcile(book, pair, day, adjusted)
        native_order_before_advance = natural.copy()
        advanced_book = book
        audit.append(dict(day=day, event="existing_lot_date_advanced", order_id=identity,
            known_day=scenario.known_day, source_evidence=list(scenario.source_evidence),
            from_proposal_id=original.proposal_id, native_release_day=original.release_day,
            native_available_day=original.available_day, requested_day=original.requested_day,
            target_release_day=advanced.release_day, target_available_day=advanced.available_day,
            qty=scenario.qty, freeze_day=freeze_day, same_day_proposal_count=len(proposals),
            same_day_proposal_qty=sum(proposal.qty for proposal in proposals)))
        return result

    def reducible_unstarted_orders(book):
        candidates = native_reducible(book)
        if book is not advanced_book or not any(row["order_id"] == scenario.order_id for row in candidates):
            return candidates
        freeze_day = scenario.target_release_day - book.horizons_by_node[scenario.pair[0]] + 1
        if book.day < freeze_day or not _has_expected_freeze(book, scenario, freeze_day):
            raise ValueError("The commitment can only be preserved after its traced native freeze")
        if book.day not in preserved_days:
            preserved_days.add(book.day)
            audit.append(dict(day=book.day, event="advanced_commitment_preserved_from_reduction",
                order_id=scenario.order_id, qty=scenario.qty, known_day=scenario.known_day,
                freeze_day=freeze_day, reason="scenario_assumes_known_factory_programme_is_firm"))
        return tuple(row for row in candidates if row["order_id"] != scenario.order_id)

    FrozenProductionBook.reconcile = reconcile
    if scenario.preserve_frozen_commitment:
        FrozenProductionBook.reducible_unstarted_orders = reducible_unstarted_orders
    try:
        yield audit
    finally:
        FrozenProductionBook.reconcile = native_reconcile
        if scenario.preserve_frozen_commitment:
            FrozenProductionBook.reducible_unstarted_orders = native_reducible
