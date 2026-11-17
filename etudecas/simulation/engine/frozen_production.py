"""Persistent experimental production commitments, separate from physical WIP.

The industrial information supplies the horizons. Launch-date anchoring and the
half-open boundary are explicit modelling conventions. A reservation never
creates physical stock, work, or consumption.
"""
from __future__ import annotations

from collections import defaultdict
import math

from .mrp_planning import FirmReceipt, Requirement

FROZEN_PRODUCTION_POLICY = "industrial_frozen_order_book_v1"


class FrozenProductionBook:
    def __init__(self, horizons_by_node, *, bom_by_pair=None):
        if not horizons_by_node or any(not isinstance(n, str) or not n or type(h) is not int or h <= 0
                                       for n, h in horizons_by_node.items()):
            raise ValueError("Frozen horizons require named sites and positive integer days")
        self.horizons_by_node = dict(horizons_by_node)
        self.bom_by_pair = dict(bom_by_pair or {})
        self.orders = {}
        self.events = []
        self.day = -1
        self.sequence = 0

    def _event(self, row, day, event):
        self.events.append(dict(row, day=day, event=event,
            decision_age_days=day-row["created_day"],
            estimated_available_day=self.estimated_available_day(row,day),
            availability_status="estimated_original_calendar_span_shift_not_material_guarantee",
            launch_delay_days=max(0, (row["actual_release_day"]
                if row["actual_release_day"] is not None else day)-row["planned_release_day"])
                if row["state"] in ("frozen", "active", "completed") else 0))

    @staticmethod
    def estimated_available_day(row, day):
        # Retain the original finite-capacity/control span when unstarted work
        # is late. This declared calendar-day bound is not an observed ETA and
        # does not claim feasibility against revised calendars/materials.
        return max(day+1, row["planned_available_day"]+max(0,day-row["planned_release_day"]))

    def begin_day(self, day):
        if type(day) is not int or day < 0 or day < self.day:
            raise ValueError("Order-book time must be nonnegative and monotone")
        self.day = day
        for row in self.orders.values():
            if (row["state"] == "planned"
                    and row["planned_release_day"] < day+self.horizons_by_node[row["node_id"]]):
                row.update(state="frozen", frozen_day=day)
                self._event(row, day, "frozen_before_review")

    def _new(self, pair, identity, day, release, available, requested, qty, state):
        if (pair[0] not in self.horizons_by_node or not identity or identity in self.orders
                or any(type(d) is not int for d in (day, release, available, requested))
                or release < 0 or available < release or not math.isfinite(qty) or qty <= 0):
            raise ValueError("Invalid production commitment")
        row = dict(order_id=identity, node_id=pair[0], item_id=pair[1],
            created_day=day, known_day=day, revised_day=day,
            frozen_day=day if state == "frozen" else None,
            planned_release_day=release, planned_available_day=available,
            requested_day=requested, qty=float(qty), executed_qty=0.0,
            state=state, campaign_id="", actual_release_day=None)
        self.orders[identity] = row
        self._event(row, day, "initial_observed" if state == "frozen" else "created_outside_zone")
        return row

    def register_initial(self, pair, *, order_id, release_day, available_day, qty, known_day=0):
        if known_day != 0 or self.day > 0:
            raise ValueError("Initial observed orders must be known at the simulation origin")
        return self._new(pair, order_id, 0, release_day, available_day, available_day, qty, "frozen")

    def reconcile(self, pair, day, proposals):
        self.begin_day(day)
        if pair[0] not in self.horizons_by_node:
            raise ValueError("Production review outside declared frozen-horizon scope")
        proposals = tuple(proposals)
        if len({p.proposal_id for p in proposals}) != len(proposals):
            raise ValueError("Duplicate proposal identities in a planning snapshot")
        boundary = day+self.horizons_by_node[pair[0]]
        if any(type(p.release_day) is not int or p.release_day < 0 or p.available_day < p.release_day
               or not math.isfinite(p.qty) or p.qty <= 0 for p in proposals):
            raise ValueError("Invalid production proposal")
        for p in proposals:
            if p.release_day < boundary:
                self.events.append(dict(day=day,event="new_proposal_rejected_inside_zone",
                    node_id=pair[0],item_id=pair[1],order_id="",planned_release_day=p.release_day,
                    planned_available_day=p.available_day,requested_day=p.requested_day,qty=p.qty,
                    block_reason="no_prior_commitment_inside_frozen_zone"))
        proposals = tuple(p for p in proposals if p.release_day >= boundary)
        old = sorted((r for r in self.orders.values() if (r["node_id"],r["item_id"]) == pair
                      and r["state"] == "planned"), key=lambda r:(r["planned_release_day"],r["order_id"]))
        # Snapshot ranks are not order identities. Preserve identities for exact
        # surviving proposals first, then revise unmatched future orders FIFO.
        unmatched = list(old)
        matches = {}
        for p in proposals:
            row = next((r for r in unmatched if (r["planned_release_day"],r["planned_available_day"],r["qty"])
                        == (p.release_day,p.available_day,p.qty)), None)
            if row is not None:
                matches[p.proposal_id] = row
                unmatched.remove(row)
        for p in sorted(proposals, key=lambda p:(p.release_day,p.proposal_id)):
            row = matches.get(p.proposal_id)
            if row is None and unmatched:
                row = unmatched[0]
                unmatched.remove(row)
            if row is None:
                self.sequence += 1
                self._new(pair, f"FROZEN|{pair[0]}|{pair[1]}|{self.sequence}", day,
                          p.release_day,p.available_day,p.requested_day,p.qty,"planned")
            else:
                changed = (row["planned_release_day"],row["planned_available_day"],row["qty"],row["requested_day"]) != (
                    p.release_day,p.available_day,p.qty,p.requested_day)
                if changed:
                    self._event(row, day, "before_outside_zone_revision")
                    row.update(planned_release_day=p.release_day,planned_available_day=p.available_day,
                               requested_day=p.requested_day,qty=float(p.qty),revised_day=day)
                    self._event(row, day, "outside_zone_revised")
        for row in unmatched:
            row["state"] = "cancelled"
            self._event(row,day,"outside_zone_cancelled")

    def _pending(self, pair=None):
        return sorted((r for r in self.orders.values() if r["state"] == "frozen"
            and (pair is None or (r["node_id"],r["item_id"]) == pair)),
            key=lambda r:(r["planned_release_day"],r["created_day"],r["order_id"]))

    def due(self, pair, day):
        self.begin_day(day)
        return next((r for r in self._pending(pair) if r["planned_release_day"] <= day), None)

    def bind(self, order_id, *, day, campaign_id):
        self.begin_day(day)
        row = self.orders[order_id]
        if row["state"] == "active" and row["campaign_id"] == campaign_id:
            return
        if (row["state"] != "frozen" or day < row["planned_release_day"] or not campaign_id
                or any(r["campaign_id"] == campaign_id for r in self.orders.values())):
            raise ValueError("A frozen order can launch once, never before its planned date")
        row.update(state="active",campaign_id=campaign_id,actual_release_day=day)
        self._event(row,day,"first_physical_work")

    def execute(self, order_id, *, day, qty):
        self.begin_day(day)
        row = self.orders[order_id]
        if (row["state"] != "active" or not math.isfinite(qty) or qty <= 0
                or row["executed_qty"]+qty > row["qty"]+1e-7):
            raise ValueError("Physical work requires an active order and cannot exceed its quantity")
        row["executed_qty"] += qty
        if row["executed_qty"] >= row["qty"]-1e-7:
            row["state"] = "completed"
        self._event(row,day,"physical_work")

    def firm_receipts(self, pair, day):
        # Active/completed outputs are represented by native WIP/held stock.
        # Overdue unstarted work remains a future commitment, never virtual stock.
        return tuple(FirmReceipt(r["order_id"],self.estimated_available_day(r,day),r["qty"],"confirmed")
                     for r in self._pending(pair))

    def reserved_work(self, pair, day):
        return tuple((r["order_id"],max(day,r["planned_release_day"]),r["qty"]) for r in self._pending(pair))

    def material_requirements(self, day):
        result = defaultdict(list)
        for row in self._pending():
            pair = row["node_id"],row["item_id"]
            for component, coefficient in self.bom_by_pair.get(pair, ()):
                result[component].append(Requirement("frozen_material:"+row["order_id"]+":"+"|".join(component),
                    max(day,row["planned_release_day"]),row["qty"]*coefficient))
        return {pair:tuple(rows) for pair,rows in result.items()}

    def planning_snapshot(self, day):
        pairs = {(r["node_id"],r["item_id"]) for r in self._pending()}
        return dict(receipts={p:self.firm_receipts(p,day) for p in pairs},
                    requirements=self.material_requirements(day))

    def blocked(self, order_id, *, day, reason):
        row = self.orders[order_id]
        if row["state"] == "frozen":
            self._event(dict(row,block_reason=reason),day,"physical_launch_delayed")
