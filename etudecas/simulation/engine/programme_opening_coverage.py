"""Pure reconciliation of initial manufacturing commitments before a new lot.

This is not an industrial pegging reconstruction. The existing dated MRP has
already netted firm output receipts; this proof binds those exact identities to
the remaining initial orders and protects their still-unconsumed components.
"""
from dataclasses import dataclass
from math import fsum, isfinite


OPENING_COVERAGE_POLICY = "net_remaining_opening_orders_v1"
# Runtime origins with an accepted dated quantity, not a revocable proposal.
# Unknown/estimated availability is deliberately not a credit in this oracle.
FIRM_COMPONENT_ORIGINS = frozenset({
    "held", "lane", "external", "production", "lane_release", "lane_release_min_annual_lot",
    "external_procurement", "external_procurement_supplier_delivery",
    "external_procurement_proactive", "external_procurement_source_boundary",
})


def reserve_known_component_backlogs(backlogs, *, decision_day, components):
    """Reserve only residual other-use debts already present before today.

    The runtime updates this queue after production. At a new-lot decision it
    is the unserved remainder from earlier days, not today's or future demand.
    No quantity is consumed, removed or recreated by this pure projection.
    """
    if type(decision_day) is not int or decision_day < 0:
        raise ValueError("Known component backlog requires a nonnegative decision day")
    reserved,audit={},[]
    for component in sorted(set(components)):
        rows=tuple(backlogs.get(component,()))
        seen=set()
        for row in rows:
            if (not isinstance(row.requirement_id,str) or not row.requirement_id
                    or row.requirement_id in seen or type(row.due_day) is not int
                    or not 0<=row.due_day<decision_day
                    or isinstance(row.qty,bool) or not isinstance(row.qty,(int,float))
                    or not isfinite(row.qty) or row.qty<0):
                raise ValueError("Known component backlog requires unique prior-day remaining requirements")
            seen.add(row.requirement_id)
        quantity=fsum(row.qty for row in rows)
        if quantity:
            reserved[component]=quantity
            audit.append(dict(node_id=component[0],item_id=component[1],reserved_qty=quantity,
                snapshot_day=decision_day,phase="before_production_before_other_use_service",
                basis="existing unserved prior-day component backlog only",
                requirements=[dict(requirement_id=r.requirement_id,due_day=r.due_day,remaining_qty=r.qty)
                              for r in rows]))
    return reserved,audit


@dataclass(frozen=True)
class CurrentComponentDemandSnapshot:
    decision_day: int
    estimated_due: dict
    known_due: dict
    deferred_closures: tuple

    def unresolved_for(self, components):
        pairs=set(components)
        return tuple(r for r in self.deferred_closures if (r["node_id"],r["item_id"]) in pairs)


def reveal_current_component_requirements(calendar, observed_execution, *, decision_day):
    """Read today's exogenous need once, without reading a future observation.

    Only the explicit pure preview API is allowed here. The cached estimates
    go through the normal merge/closing API once, after production. A closing
    residual depending on today's production is deliberately not known yet.
    """
    if type(decision_day) is not int or decision_day < 0:
        raise ValueError("Current component demand requires a nonnegative decision day")
    if calendar is None:
        if observed_execution is not None:
            raise ValueError("Observed component demand requires its estimate calendar")
        return CurrentComponentDemandSnapshot(decision_day,{}, {}, ())
    estimated={pair:tuple(rows) for pair,rows in calendar.due(decision_day).items()}
    due=estimated
    deferred=()
    if observed_execution is not None:
        preview=getattr(observed_execution,"preview_due",None)
        if not callable(preview):
            raise ValueError("Current component preview requires an explicit pure preview_due API")
        due,deferred=preview(decision_day,estimated)
    snapshot={pair:tuple(rows) for pair,rows in due.items()}
    # Validate the whole snapshot, including components outside this new lot.
    reserve_current_component_requirements(snapshot,backlogs={},decision_day=decision_day,
        components=snapshot)
    seen=set()
    for row in deferred:
        identity=(row.get("node_id"),row.get("item_id"),row.get("budget_id"))
        if (not all(isinstance(v,str) and v for v in identity) or identity in seen
                or type(row.get("closing_day")) is not int or row["closing_day"]!=decision_day
                or row.get("reason")!="quantity_depends_on_current_day_production"):
            raise ValueError("Deferred component closing requires a unique current-day identity")
        seen.add(identity)
    return CurrentComponentDemandSnapshot(decision_day,estimated,snapshot,tuple(dict(r) for r in deferred))


def reserve_current_component_requirements(due, *, backlogs, decision_day, components):
    """Protect today's already revealed need separately from prior-day debt."""
    if type(decision_day) is not int or decision_day < 0:
        raise ValueError("Current component demand requires a nonnegative decision day")
    reserved,audit={},[]
    for component in sorted(set(components)):
        rows=tuple(due.get(component,()))
        prior_ids={r.requirement_id for r in backlogs.get(component,())}
        seen=set()
        for row in rows:
            if (not isinstance(row.requirement_id,str) or not row.requirement_id
                    or row.requirement_id in seen or row.requirement_id in prior_ids
                    or type(row.due_day) is not int or row.due_day!=decision_day
                    or isinstance(row.qty,bool) or not isinstance(row.qty,(int,float))
                    or not isfinite(row.qty) or row.qty<0):
                raise ValueError("Current component demand requires unique current-day requirements disjoint from backlog")
            seen.add(row.requirement_id)
        quantity=fsum(row.qty for row in rows)
        if quantity:
            reserved[component]=quantity
            audit.append(dict(node_id=component[0],item_id=component[1],reserved_qty=quantity,
                snapshot_day=decision_day,phase="revealed_before_production_served_after_production",
                basis="current-day exogenous demand; no future observation",
                requirements=[dict(requirement_id=r.requirement_id,due_day=r.due_day,remaining_qty=r.qty)
                              for r in rows]))
    return reserved,audit


@dataclass(frozen=True)
class OpeningProgrammeCoverage:
    pair: tuple
    decision_day: int
    valid: bool
    reason: str
    pending_qty: float
    orders: tuple
    net_proposals: tuple
    component_firm_receipts: tuple = ()

    def matches(self, *, pair, decision_day, pending_qty, proposals):
        return (self.valid and self.pair == pair and self.decision_day == decision_day
                and abs(self.pending_qty - pending_qty) <= 1e-8
                and self.net_proposals == tuple((p.proposal_id, p.release_day, p.available_day,
                    p.requested_day, p.qty) for p in proposals))

    def component_reservations(self, through_day):
        values = {}
        for _identity, _pair, physical, _available, _qty, components in self.orders:
            if physical > through_day:
                continue
            for node, item, quantity in components:
                key = (node, item)
                values[key] = values.get(key, 0.0) + quantity
        return values

    def future_material_protection(self):
        """Stock which must remain now to cover every known initial prefix.

        An accepted future receipt can cover only initial work on/after its
        usable date. A purchase proposal or an uncertain pending receipt never
        releases current stock. Other engaged campaigns are protected by the
        selector as a separate current-stock deduction.
        """
        if not self.valid:
            return {},[],[]
        needs = {}
        for identity, _pair, physical, _available, _qty, components in self.orders:
            for node,item,quantity in components:
                if quantity > 0:
                    needs.setdefault((node,item),[]).append((physical,quantity,identity))
        accepted,excluded = {},[]
        for identity,pair,available,qty,origin,known in self.component_firm_receipts:
            if origin not in FIRM_COMPONENT_ORIGINS:
                reason="unproven_or_revocable_receipt_origin"
            elif available<=self.decision_day:
                reason="already_due_not_a_second_future_credit"
            else:
                accepted.setdefault(pair,[]).append((available,qty,identity,origin,known))
                continue
            excluded.append(dict(receipt_id=identity,node_id=pair[0],item_id=pair[1],
                available_day=available,qty=qty,origin=origin,known_day=known,reason=reason))
        reserve,projection={},[]
        for pair,initial in sorted(needs.items()):
            receipts=accepted.get(pair,())
            peak=0.0;points=[]
            for day in sorted({d for d,_q,_i in initial}):
                needed=fsum(q for d,q,_i in initial if d<=day)
                supplied=fsum(q for d,q,_i,_o,_k in receipts if d<=day)
                prefix=max(0.0,needed-supplied);peak=max(peak,prefix)
                points.append(dict(day=day,cumulative_initial_requirement_qty=needed,
                    cumulative_known_firm_receipt_qty=supplied,uncovered_prefix_qty=prefix,
                    initial_order_ids=[i for d,_q,i in initial if d<=day],
                    credited_receipt_ids=[i for d,_q,i,_o,_k in receipts if d<=day]))
            reserve[pair]=peak
            projection.append(dict(node_id=pair[0],item_id=pair[1],required_current_stock_qty=peak,
                dates=points,known_firm_receipts=[dict(receipt_id=i,available_day=d,qty=q,
                    origin=o,known_day=k) for d,q,i,o,k in receipts]))
        return reserve,projection,excluded

    def audit(self, *, pair_uoms=None):
        _reserve,projection,excluded=self.future_material_protection()
        for row in projection:
            row["uom"]=(pair_uoms or {}).get((row["node_id"],row["item_id"]))
        return dict(policy=OPENING_COVERAGE_POLICY, valid=self.valid, reason=self.reason,
            decision_day=self.decision_day, pending_initial_qty=self.pending_qty,
            initial_orders=[dict(receipt_id=i, node_id=p[0], item_id=p[1],
                planned_work_day=d, available_day=a, remaining_qty=q,
                remaining_components=[dict(node_id=n, item_id=c, qty=v) for n,c,v in cs])
                for i,p,d,a,q,cs in self.orders],
            net_proposals=[dict(proposal_id=i, release_day=r, available_day=a, requested_day=d, qty=q)
                           for i,r,a,d,q in self.net_proposals],
            finished_quantity_basis="existing dated MRP, exact initial firm identities netted once",
            material_protection_basis="maximum dated initial requirement prefix minus known accepted usable receipt prefix",
            dated_initial_material_projection=projection,excluded_component_receipts=excluded)


def reconcile_opening_programme(*, pair, decision_day, orders, firm_receipts, proposals,
                               component_firm_receipts=()):
    """Fail closed on missing, duplicate or stale residual output commitments.

An order row is (identity, output_pair, next_work_day, available_day,
remaining_output_qty, ((component_node, component_item, remaining_qty), ...)).
Only residual work/material is supplied: completed output is already physical
or a separately identified held receipt and must not be credited here again.
"""
    proposals = tuple(proposals)
    copied = tuple((i, tuple(p), d, a, q, tuple(tuple(c) for c in cs))
                   for i,p,d,a,q,cs in orders)
    pending = fsum(q for _i,p,_d,_a,q,_cs in copied if p == pair)
    component_firms=tuple((i,tuple(p),d,q,o,k) for i,p,d,q,o,k in component_firm_receipts)
    def result(valid, reason):
        return OpeningProgrammeCoverage(pair, decision_day, valid, reason, pending,
            copied, tuple((p.proposal_id,p.release_day,p.available_day,p.requested_day,p.qty) for p in proposals),
            component_firms)
    if type(decision_day) is not int or decision_day < 0:
        return result(False, "invalid_decision_day")
    component_ids=set()
    for identity,component,available,qty,origin,known in component_firms:
        if (not isinstance(identity,str) or not identity or (component,identity) in component_ids
                or len(component)!=2 or any(not isinstance(x,str) or not x for x in component)
                or type(available) is not int or type(known) is not int or not 0<=known<=decision_day
                or isinstance(qty,bool) or not isinstance(qty,(int,float)) or not isfinite(qty) or qty<0
                or not isinstance(origin,str) or not origin):
            return result(False,"invalid_duplicate_or_future_component_firm_receipt")
        component_ids.add((component,identity))
    ids = set()
    for identity, output_pair, physical, available, qty, components in copied:
        if (not isinstance(identity, str) or not identity or identity in ids
                or len(output_pair) != 2 or any(not isinstance(x,str) or not x for x in output_pair)
                or type(physical) is not int or physical <= decision_day
                or type(available) is not int or available < physical
                or isinstance(qty,bool) or not isinstance(qty,(int,float)) or not isfinite(qty) or qty <= 0
                or not components):
            return result(False, "invalid_or_duplicate_initial_order")
        ids.add(identity)
        seen = set()
        for node, item, amount in components:
            if ((node,item) in seen or node != output_pair[0] or not isinstance(item,str) or not item
                    or isinstance(amount,bool) or not isinstance(amount,(int,float))
                    or not isfinite(amount) or amount < 0):
                return result(False, "invalid_initial_component_remainder")
            seen.add((node,item))
    receipts = tuple(firm_receipts)
    receipt_ids = [r.receipt_id for r in receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        return result(False, "duplicate_firm_receipt")
    by_id = {r.receipt_id:r for r in receipts}
    for identity, output_pair, _physical, available, qty, _components in copied:
        if output_pair != pair:
            continue
        receipt = by_id.get(identity)
        if receipt is None:
            return result(False, "missing_initial_firm_receipt")
        if (receipt.available_day != available or abs(receipt.qty-qty) > 1e-8
                or receipt.available_day <= decision_day):
            return result(False, "stale_initial_firm_receipt")
    proposal_ids = [p.proposal_id for p in proposals]
    if len(proposal_ids) != len(set(proposal_ids)):
        return result(False, "duplicate_net_proposal")
    return result(True, "initial_residuals_reconciled_with_netted_firm_receipts")
