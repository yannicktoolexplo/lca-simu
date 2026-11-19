"""Whole-lot material admission without inferring a shared production rate.

This opt-in path uses the existing single-day work convention when physical
duration is not modelled. It neither invents a measured duration nor limits
how much work other admissible lots can perform on the same day.
"""
from decimal import Decimal
import math

from etudecas.simulation.engine.dated_launch_substitution import assess_primary_only_transitions
from etudecas.simulation.engine.production_component_issues import incremental_component_issue
from etudecas.simulation.engine.programme_opening_coverage import FIRM_COMPONENT_ORIGINS
from etudecas.simulation.lot_policy.models import normalize_uom


UNCONSTRAINED_MATERIAL_KIT_POLICY = "known_material_kit_unconstrained_v1"


def _qty(value, unit=None):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError("Material admission needs finite nonnegative quantities")
    if unit is not None and normalize_uom(unit) == "UN" and value != int(value):
        raise ValueError("Physical component units must remain integer")
    return Decimal(str(value))


def _priority_orders(orders, *, decision_day, output_pair, own_order_id, batch_qty):
    by_id = {}
    for original in orders:
        row = dict(original)
        identity = row.get('order_id')
        if (not isinstance(identity, str) or not identity or identity in by_id
                or row.get('state') != 'frozen'
                or any(type(row.get(k)) is not int or row[k] < 0
                       for k in ('planned_release_day', 'created_day', 'known_day'))
                or row['created_day'] > decision_day or row['known_day'] > decision_day
                or _qty(row.get('qty'), 'UN') <= 0):
            raise ValueError("Invalid or future frozen priority metadata")
        by_id[identity] = row
    key = lambda row: (row['planned_release_day'], row['created_day'], row['order_id'])
    pair = tuple(output_pair) if output_pair is not None else None
    ordered = sorted((r for r in by_id.values()
                      if (r['node_id'], r['item_id']) == pair), key=key)
    if own_order_id is None and not ordered:
        return by_id, (), None
    own = by_id.get(own_order_id)
    if own is None:
        return by_id, (), 'missing_candidate_priority_metadata'
    if ((own['node_id'], own['item_id']) != pair
            or own['planned_release_day'] > decision_day or own['qty'] != batch_qty):
        return by_id, (), 'inconsistent_candidate_priority_metadata'
    if any(key(row) < key(own) for row in ordered):
        return by_id, ordered, 'earlier_frozen_order_unlaunched'
    return by_id, ordered, None


def _frozen_link(row, orders, own_order_id):
    identity = row.get('frozen_order_id')
    source = orders.get(identity)
    if source is None:
        raise ValueError("Frozen material requirement needs an exact structured order link")
    expected = 'frozen_material:' + identity + ':' + '|'.join((row['node_id'], row['item_id']))
    if (row.get('frozen_component_requirement_id') != expected
            or row['identity'] != 'other_frozen_order_components:' + expected
            or (row.get('frozen_output_node_id'), row.get('frozen_output_item_id'))
                != (source['node_id'], source['item_id'])
            or row.get('frozen_planned_release_day') != source['planned_release_day']
            or row.get('frozen_created_day') != source['created_day']):
        raise ValueError("Frozen material link and original priority metadata disagree")
    if identity == own_order_id:
        raise ValueError("Candidate component needs must be excluded exactly once")
    return identity


def assess_unconstrained_material_launch(*, decision_day, batch_qty, components,
        available_by_pair, item_uoms, firm_receipts, other_requirements,
        own_order_id=None, nonprojectable_substitutions=(),
        policy=UNCONSTRAINED_MATERIAL_KIT_POLICY, output_pair=None, frozen_orders=(),
        physical_batch_quantities=()):
    """Check a complete current kit, preserving dated lower-priority obligations.

    The caller supplies usable stock after actual receipts/held-stock releases.
    Future receipts remain audit evidence and cannot fund today's kit. The
    native caller already excludes the candidate's component requirement; its
    presence here is rejected. Later same-output orders retain their identities,
    dates and quantities, but cannot reserve stock before this earlier order.
    Their unfinanced quantity is an audit projection, never an erased order.
    """
    if type(decision_day) is not int or decision_day < 0 or _qty(batch_qty, 'UN') <= 0:
        raise ValueError("Invalid unconstrained material launch decision")
    if policy != UNCONSTRAINED_MATERIAL_KIT_POLICY:
        raise ValueError("Unknown unconstrained material launch policy")
    physical_batch_quantities = tuple(physical_batch_quantities) or (batch_qty,)
    physical_quantities = tuple(_qty(q, 'UN') for q in physical_batch_quantities)
    if (any(q <= 0 for q in physical_quantities)
            or sum(physical_quantities, Decimal(0)) != _qty(batch_qty, 'UN')):
        raise ValueError("Physical batches must exactly partition the positive whole order quantity")
    components = tuple(components)
    firm_receipts = tuple(dict(row) for row in firm_receipts)
    other_requirements = tuple(dict(row) for row in other_requirements)
    frozen_orders = tuple(dict(row) for row in frozen_orders)
    transitions = tuple(dict(row) for row in nonprojectable_substitutions
        if row.get('start_day', decision_day) <= decision_day <= row.get('end_day', decision_day))
    pairs = {pair for pair, _ in components}
    if len(pairs) != len(components):
        raise ValueError("A complete kit requires a unique component BOM")
    if not pairs:
        raise ValueError("A complete kit requires explicit components")
    for pair, ratio in components:
        if _qty(ratio) <= 0:
            raise ValueError("BOM coefficients must be positive")
        _qty(available_by_pair.get(pair, 0), item_uoms[pair[1]])
    by_id, ordered, refusal = _priority_orders(frozen_orders,
        decision_day=decision_day, output_pair=output_pair,
        own_order_id=own_order_id, batch_qty=batch_qty)
    ordered_ids = [r['order_id'] for r in ordered]
    successors = (set(ordered_ids[ordered_ids.index(own_order_id) + 1:])
                  if own_order_id in ordered_ids else set())
    result = dict(policy=policy, snapshot_known_day=decision_day,
        applicable=True, allowed=False, reason='', batch_qty=batch_qty,
        physical_batch_quantities=list(physical_batch_quantities),
        projected_finish_day=decision_day, work_allocations=[dict(day=decision_day, qty=batch_qty)],
        capacity_reservations=[], capacity_constraint='not_modelled_no_shared_daily_rate',
        work_convention='whole_batch_in_launch_day_not_measured_physical_duration',
        conditional_on='current_usable_stock_and_known_due_material_obligations;future_receipts_do_not_fund_today',
        excluded_own_order_id=own_order_id, component_projection=[],
        firm_receipts=[], other_requirements=[], successor_material_obligations=[],
        priority_projection=dict(policy='native_frozen_order_priority_without_capacity_retiming',
            priority_orders=[dict(order_id=r['order_id'],
                priority_key=[r['planned_release_day'], r['created_day'], r['order_id']],
                qty=r['qty'], candidate=r['order_id'] == own_order_id) for r in ordered],
            candidate_excluded_count=int(own_order_id is not None), retimed_requirements=[]))
    balance = {pair: _qty(available_by_pair.get(pair, 0), item_uoms[pair[1]]) for pair in pairs}
    # Decimal subtraction below is exact, but its inputs came from native
    # binary floats. Keep an explicit one-ULP representation allowance for
    # each exposed non-UN stock/claim and each rounded product/sum. This is a
    # comparison budget only: it never changes stock or physical issue work.
    input_roundoff = {pair: (Decimal(0) if normalize_uom(item_uoms[pair[1]]) == 'UN'
        else Decimal.from_float(math.ulp(float(available_by_pair.get(pair, 0))))) for pair in pairs}
    result['usable_stock_snapshot'] = [dict(node_id=p[0], item_id=p[1],
        qty=float(balance[p]), uom=item_uoms[p[1]]) for p in sorted(pairs)]
    result['bom'] = [dict(node_id=p[0], item_id=p[1], ratio=ratio,
        uom=item_uoms[p[1]]) for p, ratio in components]
    seen = set()
    pending_successors = []
    for kind, records, date_field in (('receipt', firm_receipts, 'available_day'),
                                     ('requirement', other_requirements, 'due_day')):
        for row in records:
            pair = row['node_id'], row['item_id']
            identity, known, when = row['identity'], row['known_day'], row[date_field]
            if (not isinstance(identity, str) or not identity or (kind, pair, identity) in seen
                    or type(known) is not int or known < 0 or known > decision_day
                    or type(when) is not int):
                raise ValueError("Material identity/date is invalid or not known at decision")
            seen.add((kind, pair, identity))
            quantity = _qty(row['qty'], item_uoms[pair[1]])
            if kind == 'receipt':
                if when <= decision_day or row.get('origin') not in FIRM_COMPONENT_ORIGINS:
                    raise ValueError("Only future usable firm receipts are additional to current stock")
                if pair in pairs:
                    result['firm_receipts'].append(dict(row, funds_current_kit=False))
                continue
            frozen_id = (_frozen_link(row, by_id, own_order_id)
                         if row.get('basis') == 'other_frozen_order_components' else None)
            if pair not in pairs:
                continue
            is_successor = frozen_id in successors
            result['other_requirements'].append(dict(row,
                priority_role='later_same_output' if is_successor else 'preserved_other_obligation'))
            if is_successor:
                pending_successors.append(row)
            elif when <= decision_day:
                balance[pair] -= quantity
                if normalize_uom(item_uoms[pair[1]]) != 'UN':
                    input_roundoff[pair] += Decimal.from_float(math.ulp(float(row['qty'])))
    # Missing lower-priority requirements must not silently disappear merely
    # because they do not fund or constrain this candidate's current admission.
    expected = {(identity, pair) for identity in successors for pair in pairs}
    found = {(row['frozen_order_id'], (row['node_id'], row['item_id'])) for row in pending_successors}
    if found != expected:
        raise ValueError("Every successor component obligation must remain present exactly once")
    ratios = dict(components)
    for row in pending_successors:
        pair = row['node_id'], row['item_id']
        expected_qty = incremental_component_issue(0, by_id[row['frozen_order_id']]['qty'],
            ratios[pair], item_uoms[pair[1]], 0)
        if row['qty'] != expected_qty:
            raise ValueError("Successor component quantity differs from its unchanged whole frozen order")
    if refusal:
        result['reason'] = refusal
        return result
    if transitions:
        projected = assess_primary_only_transitions(assess=assess_unconstrained_material_launch,
            arguments=dict(decision_day=decision_day, batch_qty=batch_qty, components=components,
                available_by_pair=available_by_pair, item_uoms=item_uoms,
                firm_receipts=firm_receipts, other_requirements=other_requirements,
                own_order_id=own_order_id, output_pair=output_pair, frozen_orders=frozen_orders,
                physical_batch_quantities=physical_batch_quantities),
            transitions=transitions, base_result=result, result_policy=policy, projection_policy=policy)
        proof = projected['substitution_projection']
        proof['method'] = 'primary_only_unconstrained_complete_current_kit'
        if projected['applicable'] is not True:
            projected.update(applicable=True, allowed=False,
                native_fallback_allowed=False, reason='unproven_primary_material_kit')
        return projected
    debits = {}
    for pair, ratio in components:
        unit = item_uoms[pair[1]]
        # Each native physical batch rounds its own countable debit. Rounding
        # the campaign total would understate the kit for fractional UN BOMs.
        issues = tuple(incremental_component_issue(0, q, ratio, unit, 0)
                       for q in physical_batch_quantities)
        debit = math.fsum(issues)
        debits[pair] = Decimal(str(debit))
        available = balance[pair]
        product_roundoff = (sum((Decimal.from_float(math.ulp(q)) for q in issues), Decimal(0))
                            if normalize_uom(unit) != 'UN' else Decimal(0))
        sum_roundoff = (Decimal.from_float(math.ulp(debit))
                       if normalize_uom(unit) != 'UN' and len(issues) > 1 else Decimal(0))
        # Cancellation between a large stock and large claims must not turn
        # their coarse ULPs into usable material at a tiny/zero final balance.
        input_bound = (min(input_roundoff[pair], Decimal.from_float(math.ulp(float(available))))
                       if available > 0 else Decimal(0))
        comparison_budget = (input_bound + product_roundoff + sum_roundoff
                             if available > 0 else Decimal(0))
        shortfall = max(Decimal(0), debits[pair] - available)
        result['component_projection'].append(dict(day=decision_day,
            node_id=pair[0], item_id=pair[1], uom=unit,
            usable_after_other_requirements=float(available), batch_issue_qty=debit,
            cumulative_batch_work=batch_qty,
            shortfall_qty=float(shortfall), material_shortfall=shortfall > comparison_budget,
            comparison_roundoff_bound_qty=float(comparison_budget),
            accepted_roundoff_gap_qty=float(shortfall if shortfall <= comparison_budget else Decimal(0)),
            roundoff_bound=dict(policy='strict_UN_else_input_ULPs_bounded_by_positive_balance_ULP_plus_products_and_sum',
                input_qty=float(input_bound), exposed_input_qty=float(input_roundoff[pair]),
                product_qty=float(product_roundoff),
                sum_qty=float(sum_roundoff), physical_stock_changed=False)))
    shortage = next((row for row in result['component_projection'] if row['material_shortfall']), None)
    if shortage is not None:
        result.update(reason='dated_material_shortfall', first_shortage=dict(day=decision_day,
            node_id=shortage['node_id'], item_id=shortage['item_id'],
            required_qty=shortage['batch_issue_qty'], available_qty=shortage['usable_after_other_requirements']))
    else:
        result.update(allowed=True, reason='known_current_material_kit', projected_completed_qty=batch_qty)
    # Conditional residual funding is reported even if a candidate is refused;
    # dates and quantities are never rewritten to make a successor look funded.
    after_candidate = {p: balance[p] - debits[p] for p in pairs}
    ranks = {r['order_id']: index for index, r in enumerate(ordered)}
    for row in sorted(pending_successors, key=lambda r: (ranks[r['frozen_order_id']], r['node_id'], r['item_id'])):
        pair = row['node_id'], row['item_id']
        available = max(Decimal(0), after_candidate[pair])
        quantity = Decimal(str(row['qty']))
        result['successor_material_obligations'].append(dict(row,
            usable_after_candidate_qty=float(available),
            unfunded_current_stock_qty=float(max(Decimal(0), quantity - available)),
            status='conditional_current_stock_after_candidate_not_a_retimed_order_or_physical_debt'))
        after_candidate[pair] -= quantity
    return result
