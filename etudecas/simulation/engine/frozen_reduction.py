"""Optional whole-lot reductions: explicit hypothesis, not a new freeze default.

No work, receipt or consumption is executed here. A removed commitment is
tested by re-netting the network without its output, material needs and work
reservation. Its replacement, if needed later, remains outside the frozen zone.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from decimal import Decimal
from math import isfinite

from .frozen_external_coverage import assess_frozen_external_coverage


FROZEN_REDUCTION_POLICY = "unstarted_whole_lot_reduction_v1"
_EPS = Decimal("0.000001")


def _decimal(value):
    if isinstance(value, bool) or not isfinite(value):
        raise ValueError("Reduction evidence requires finite quantities")
    return Decimal(str(value))


def _step_at(points, when, initial):
    dates = sorted(points)
    index = bisect_right(dates, when) - 1
    return points[dates[index]] if index >= 0 else initial


def _evidence(result, pair, day, *, requirement_ids=None, allow_unprotected=False):
    _, plans, requirements, audits = result
    plan = plans.get(pair)
    audit = audits.get(pair, {})
    if plan is None or plan.decision_day != day or ("protection_points" not in audit and not allow_unprotected):
        raise ValueError("Missing dated plan or explicit protection checkpoints")
    needs = tuple(requirements.get(pair, ()))
    signature = tuple(sorted((r.requirement_id,r.due_day,_decimal(r.qty)) for r in needs))
    if len({row[0] for row in signature}) != len(signature):
        raise ValueError("Reduction requires unique physical requirement identities")
    points = audit.get("protection_points",())
    floors = {p.day: _decimal(p.minimum_qty) for p in points}
    if len(floors) != len(points):
        raise ValueError("Reduction requires unique protection checkpoint dates")
    balances = {b.day: _decimal(b.after_proposals_qty) for b in plan.balances}
    if len(balances) != len(plan.balances):
        raise ValueError("Reduction requires unique projected balance dates")
    allocations = defaultdict(list)
    known = {r.requirement_id: r for r in needs}
    for allocation in plan.allocations:
        if allocation.requirement_id not in known:
            raise ValueError("Allocation without a physical requirement")
        if allocation.due_day != known[allocation.requirement_id].due_day:
            raise ValueError("Allocation and physical requirement dates disagree")
        allocations[allocation.requirement_id].append((allocation.available_day,_decimal(allocation.qty)))
    if any(sum((qty for _,qty in allocations[r.requirement_id]), Decimal(0))
           > _decimal(r.qty) + _EPS for r in needs):
        raise ValueError("Reduction evidence overallocates a physical requirement")
    if requirement_ids is not None:
        if not requirement_ids <= set(known):
            raise ValueError("A declared external requirement disappeared during network netting")
        needs = tuple(r for r in needs if r.requirement_id in requirement_ids)
        signature = tuple(sorted((r.requirement_id,r.due_day,_decimal(r.qty)) for r in needs))
    return plan, needs, signature, floors, balances, allocations


def _compare_coverage(before, after, pair, day, *, requirement_ids=None, allow_unprotected=False):
    """Compare deficits at every relevant date, without compensating periods."""
    try:
        b = _evidence(before, pair, day,requirement_ids=requirement_ids,allow_unprotected=allow_unprotected)
        a = _evidence(after, pair, day,requirement_ids=requirement_ids,allow_unprotected=allow_unprotected)
    except ValueError as exc:
        return False, {"reason": "missing_or_invalid_dated_evidence", "detail": str(exc)}
    if b[2] != a[2]:
        return False, {"reason": "physical_requirements_changed"}
    if requirement_ids is None and b[3] != a[3]:
        return False, {"reason": "stock_protection_changed"}
    if abs(_decimal(b[0].opening_available_qty) - _decimal(a[0].opening_available_qty)) > _EPS:
        return False, {"reason": "opening_available_stock_changed"}
    dates = {day} | set(b[3]) | set(b[4]) | set(a[4])
    dates.update(max(day,r.due_day) for r in b[1])
    for evidence in (b,a):
        dates.update(when for rows in evidence[5].values() for when,_ in rows)
    dates = sorted(when for when in dates if when >= day)
    maximum_before = maximum_after = Decimal(0)
    first_worse = None
    for when in dates:
        floor = _step_at(b[3],when,Decimal(0))
        old_balance = _step_at(b[4],when,_decimal(b[0].opening_available_qty))
        new_balance = _step_at(a[4],when,_decimal(a[0].opening_available_qty))
        old_short = max(Decimal(0),floor-old_balance)
        new_short = max(Decimal(0),floor-new_balance)
        maximum_before = max(maximum_before,old_short)
        maximum_after = max(maximum_after,new_short)
        if requirement_ids is None and new_short > old_short + _EPS and first_worse is None:
            first_worse = {"day":when,"kind":"physical_or_protection_deficit",
                           "before_qty":float(old_short),"after_qty":float(new_short)}
        for need in b[1]:
            if max(day,need.due_day) > when:
                continue
            old_covered = sum((qty for available,qty in b[5][need.requirement_id]
                               if available <= when),Decimal(0))
            new_covered = sum((qty for available,qty in a[5][need.requirement_id]
                               if available <= when),Decimal(0))
            if new_covered + _EPS < old_covered and first_worse is None:
                first_worse = {"day":when,"kind":"physical_requirement_coverage",
                    "requirement_id":need.requirement_id,"before_uncovered_qty":float(_decimal(need.qty)-old_covered),
                    "after_uncovered_qty":float(_decimal(need.qty)-new_covered)}
    old_proposals = Counter((p.release_day,p.available_day,p.requested_day,p.qty) for p in b[0].proposals)
    additional_proposals = []
    for proposal in a[0].proposals:
        signature = (proposal.release_day,proposal.available_day,proposal.requested_day,proposal.qty)
        if old_proposals[signature]:
            old_proposals[signature] -= 1
        else:
            additional_proposals.append(dict(release_day=proposal.release_day,
                available_day=proposal.available_day,requested_day=proposal.requested_day,qty=proposal.qty))
    evidence = dict(reason="dated_coverage_not_worsened" if first_worse is None else "dated_coverage_worsened",
        checked_dates=len(dates), checked_requirements=len(b[1]), first_worsening=first_worse,
        before_max_shortfall_qty=float(maximum_before), after_max_shortfall_qty=float(maximum_after),
        before_late_qty=float(b[0].late_qty), after_late_qty=float(a[0].late_qty),
        before_late_qty_days=float(b[0].late_qty_days), after_late_qty_days=float(a[0].late_qty_days),
        before_proposed_qty=float(b[0].proposed_qty), after_proposed_qty=float(a[0].proposed_qty),
        new_outside_zone_proposals=additional_proposals)
    return first_worse is None, evidence


def _explicitly_unprotected(inputs, pair):
    """Absent client audits mean zero only when the input policy declares it."""
    maps = ("protection_by_pair","source_safety_by_pair","reserve_targets_by_pair",
            "prospective_safety_by_pair","coverage_days_by_pair","anticipated_need_by_pair")
    if not any(key in inputs for key in maps):
        return False
    if any((inputs.get(key) or {}).get(pair) for key in maps):
        return False
    return not any(pair in (inputs.get(key) or ()) for key in
        ("coverage_protection_pairs","anticipated_internal_pairs","industrial_internal_pairs"))


def _guarded_pairs(book, inputs, produced_pairs):
    """Exact guards for PF/clients; only exogenous demand for BOM components."""
    guarded = {pair: None for pair in produced_pairs if pair[0] in book.horizons_by_node}
    components = {component for rows in book.bom_by_pair.values() for component,_ in rows}
    components.update(component for rows in (inputs.get("bom_by_pair") or {}).values() for component,_ in rows)
    for pair, needs in (inputs.get("requirements_by_pair") or {}).items():
        if pair not in guarded:
            guarded[pair] = ({r.requirement_id for r in needs} if pair in components else None)
    return guarded


def _guard_normalized_external_coverage(before, after, pair, day, identities, *, allow_unprotected, network_inputs):
    """Keep raw identities, equal whole plans, or explicitly traced fixed supply.

    Industrial forecast reconciliation may already have replaced root IDs
    before the counterfactual. Equal normalized requirements let the stronger
    whole-pair guard protect every resulting need. Changed normalized needs
    require source-traced weekly revisions covered by fixed candidate supplies.
    Missing provenance remains a refusal, including an apparent reduction.
    """
    old = tuple(before[2].get(pair,()))
    new = tuple(after[2].get(pair,()))
    missing_old = sorted(identities - {r.requirement_id for r in old})
    missing_new = sorted(identities - {r.requirement_id for r in new})
    if not missing_old and not missing_new:
        allowed, evidence = _compare_coverage(before,after,pair,day,
            requirement_ids=identities,allow_unprotected=True)
        return allowed,evidence,"external_requirements_only"
    old_signature = tuple(sorted((r.requirement_id,r.due_day,r.qty) for r in old))
    new_signature = tuple(sorted((r.requirement_id,r.due_day,r.qty) for r in new))
    provenance = dict(missing_external_ids_before=missing_old,missing_external_ids_after=missing_new,
        normalized_before_requirement_count=len(old),normalized_after_requirement_count=len(new),
        normalized_before_qty=float(sum((_decimal(r.qty) for r in old),Decimal(0))),
        normalized_after_qty=float(sum((_decimal(r.qty) for r in new),Decimal(0))))
    if old_signature != new_signature:
        removed = sorted(set(old_signature)-set(new_signature))
        added = sorted(set(new_signature)-set(old_signature))
        def first(rows):
            return (dict(requirement_id=rows[0][0],due_day=rows[0][1],qty=rows[0][2]) if rows else None)
        allowed,fixed = assess_frozen_external_coverage(before=before,after=after,pair=pair,day=day,
            network_inputs=network_inputs,raw_requirement_ids=identities)
        return allowed,dict(provenance,**fixed,
            first_removed_or_changed_requirement=first(removed),
            first_added_or_changed_requirement=first(added)),"fixed_supply_revised_forecast"
    allowed,evidence = _compare_coverage(before,after,pair,day,allow_unprotected=allow_unprotected)
    return allowed,dict(evidence,**provenance),"normalized_whole_pair_identical"


def _without_order(book, network_inputs, day, order_id):
    """Remove all three planning contributions, leaving book/state untouched."""
    result = dict(network_inputs,
        frozen_production_snapshot=book.planning_snapshot(day,exclude_order_ids=(order_id,)))
    capacities = dict(network_inputs.get("manufacturing_capacity_by_pair") or {})
    for pair, context in capacities.items():
        if pair[0] in book.horizons_by_node:
            capacities[pair] = dict(context,
                frozen_work=book.reserved_work(pair,day,exclude_order_ids=(order_id,)))
    result["manufacturing_capacity_by_pair"] = capacities or None
    return result


def _order_audit(order, day):
    return dict(day=day,policy=FROZEN_REDUCTION_POLICY,order_id=order["order_id"],
        node_id=order["node_id"],item_id=order["item_id"],qty=order["qty"],
        planned_release_day=order["planned_release_day"],
        planned_available_day=order["planned_available_day"],accepted=False)


def reduce_unstarted_frozen_orders(book, *, day, network_inputs, available_by_pair,
                                  firm_receipts_by_pair, produced_pairs, reconcile, current_result):
    """Return retained inputs, planning result and auditable whole-lot decisions.

    The runtime activates this explicitly at weekly close after physical work.
    Existing native initial orders and active campaigns stay outside this book
    or are excluded by their creation provenance. Refused trials change nothing.
    """
    if type(day) is not int or day <= 0 or day != book.day or network_inputs.get("decision_day") != day:
        raise ValueError("Reduction requires the current post-work, noninitial decision day")
    retained_inputs, retained_result, rows = network_inputs, current_result, []
    candidates = tuple(order for order in book.reducible_unstarted_orders()
                       if (order["node_id"],order["item_id"]) in produced_pairs)
    native_ids = {receipt.receipt_id for receipts in firm_receipts_by_pair.values() for receipt in receipts}
    frozen_ids = {order["order_id"] for order in book.orders.values() if order["state"] == "frozen"}
    conflicting_ids = sorted(native_ids & frozen_ids)
    if conflicting_ids:
        # Even removing another order would leave the ambiguous credit in the
        # network. Refuse the whole review before any callback or book mutation.
        return retained_inputs,retained_result,[dict(_order_audit(order,day),
            reason="native_frozen_receipt_credit_conflict",conflicting_receipt_ids=conflicting_ids)
            for order in candidates]
    for order in candidates:
        pair = order["node_id"],order["item_id"]
        identity = order["order_id"]
        row = _order_audit(order,day)
        context = (retained_inputs.get("manufacturing_capacity_by_pair") or {}).get(pair)
        if (context is None or context.get("new_order_not_before",-1) < day+book.horizons_by_node[pair[0]]
                or not float(order["qty"]).is_integer()):
            rows.append(dict(row,reason="missing_frozen_boundary_or_integer_lot"))
            continue
        trial_inputs = _without_order(book,retained_inputs,day,identity)
        trial = reconcile(trial_inputs,available_by_pair=available_by_pair,
            firm_receipts_by_pair=firm_receipts_by_pair,produced_pairs=produced_pairs)
        offending = [dict(node_id=other_pair[0],item_id=other_pair[1],
                release_day=proposal.release_day,available_day=proposal.available_day,qty=proposal.qty)
            for other_pair,plan in trial[1].items()
            if other_pair in produced_pairs and other_pair[0] in book.horizons_by_node
            for proposal in plan.proposals
            if proposal.release_day < day+book.horizons_by_node[other_pair[0]]]
        if offending:
            rows.append(dict(row,reason="counterfactual_adds_order_inside_frozen_zone",
                offending_pair=[offending[0]["node_id"],offending[0]["item_id"]],
                offending_release_day=offending[0]["release_day"],offending_qty=offending[0]["qty"],
                offending_proposals=offending))
            continue
        accepted, evidence = _compare_coverage(retained_result,trial,pair,day)
        downstream = []
        if accepted:
            for guarded_pair, requirement_ids in sorted(_guarded_pairs(book,retained_inputs,produced_pairs).items()):
                if guarded_pair == pair or requirement_ids == set():
                    continue
                # A disconnected declared root with no plan in either calculation
                # cannot be affected by this network trial. Missing on one side is an error.
                if guarded_pair not in retained_result[1] and guarded_pair not in trial[1]:
                    continue
                unprotected = _explicitly_unprotected(retained_inputs,guarded_pair)
                if requirement_ids is not None:
                    allowed,guard,mode = _guard_normalized_external_coverage(retained_result,trial,guarded_pair,day,
                        requirement_ids,allow_unprotected=unprotected,network_inputs=retained_inputs)
                else:
                    allowed,guard = _compare_coverage(retained_result,trial,guarded_pair,day,
                        allow_unprotected=unprotected)
                    mode = "full_dated_coverage"
                downstream.append(dict(node_id=guarded_pair[0],item_id=guarded_pair[1],
                    mode=mode,
                    accepted=allowed,**guard))
                if not allowed:
                    accepted = False
            if not accepted:
                evidence = dict(evidence,reason="other_pf_or_external_demand_worsened_or_unverified")
        rows.append(dict(row,accepted=accepted,downstream_guards=downstream,**evidence))
        if accepted:
            book.cancel_unstarted_whole_lot(identity,day=day)
            retained_inputs,retained_result = trial_inputs,trial
    return retained_inputs,retained_result,rows
