"""Customer service in quantity, separate from days with no remaining backlog.

Read-only arithmetic on homogeneous physical quantities (UN for the current
reference). It measures service during the window, including catch-up, not OTIF
or stock availability at the distribution centre.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation

EPS = Decimal('0.000001')


def customer_service_scope(graph, scenario_id):
    """Identify customer/item pairs and their unit from the scenario and sources."""
    scenarios = [r for r in graph.get('scenarios', []) if r.get('id') == scenario_id]
    unknown = dict(expected_pairs=None, uom=None, status='unknown_customer_service_scope')
    if len(scenarios) != 1:
        return unknown
    nodes = {r.get('id'): r for r in graph.get('nodes', [])}
    pairs = {(r.get('node_id'), r.get('item_id')) for r in scenarios[0].get('demand', [])}
    if not pairs or any(not all(pair) or nodes.get(pair[0], {}).get('type') != 'customer' for pair in pairs):
        return unknown
    units = defaultdict(set)
    for node, item in pairs:
        for state in (nodes[node].get('inventory') or {}).get('states', []):
            if state.get('item_id') == item and state.get('uom'):
                units[node, item].add(str(state['uom']).strip().upper())
    for row in ((graph.get('meta') or {}).get('customer_demand_history') or {}).get('rows', []):
        pair = row.get('node_id'), row.get('item_id')
        if pair in pairs and row.get('uom'):
            units[pair].add(str(row['uom']).strip().upper())
    if any(len(units[pair]) != 1 for pair in pairs):
        return unknown
    homogeneous = set().union(*(units[pair] for pair in pairs))
    if len(homogeneous) != 1:
        raise ValueError('Cannot aggregate customer demand with different physical units')
    return dict(expected_pairs=sorted(pairs), uom=next(iter(homogeneous)),
        status='identified_homogeneous_customer_scope')


def customer_service_metrics(rows, *, expected_days=None, expected_pairs=None, expected_uom=None):
    """Quantity served / (new demand + opening backlog counted once per pair).

    Missing coverage is unknown. Physically contradictory rows are refused.
    The caller must identify the expected customer/item scope and common unit;
    absence of an entire pair cannot be inferred from the remaining rows.
    """
    result = dict(quantity_service_rate=None, product_availability=None,
        quantity_service_demand_qty=None, quantity_service_served_qty=None,
        quantity_service_opening_backlog_qty=None, quantity_service_ending_backlog_qty=None,
        fully_served_customer_item_days=None, active_customer_item_days=None,
        customer_service_semantics_status='missing_customer_service_history',
        quantity_service_basis='served_over_new_demand_and_opening_backlog_v1',
        quantity_service_uom=expected_uom)
    rows = list(rows)
    if not rows:
        return result
    if expected_days is not None and (type(expected_days) is not int or expected_days < 1):
        raise ValueError('Expected customer service horizon must be a positive integer')
    units = {str(r['uom']).strip().upper() for r in rows if r.get('uom')}
    if len(units) > 1 or (units and expected_uom is not None and units != {expected_uom}):
        raise ValueError('Customer service quantities must share a physical unit')
    required_fields = ('day', 'node_id', 'item_id', 'demand_qty',
        'required_with_backlog_qty', 'served_qty', 'backlog_end_qty')
    if any(any(r.get(key) is None or r.get(key) == '' for key in required_fields) for r in rows):
        result['customer_service_semantics_status'] = 'incomplete_customer_service_fields'
        return result
    def number(value):
        if isinstance(value, bool):
            raise ValueError('Customer service quantities must be numeric')
        try:
            value = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError('Customer service quantity is not numeric') from error
        if not value.is_finite() or value < 0:
            raise ValueError('Customer service quantities must be finite and nonnegative')
        return value
    grouped = defaultdict(dict)
    for row in rows:
        day = number(row['day'])
        if day != day.to_integral_value():
            raise ValueError('Customer service dates must be integer days')
        pair = str(row['node_id']), str(row['item_id'])
        if int(day) in grouped[pair]:
            raise ValueError('Duplicate customer/item/day observation')
        grouped[pair][int(day)] = tuple(number(row[k]) for k in required_fields[3:])
    if expected_pairs is not None and set(grouped) != {tuple(pair) for pair in expected_pairs}:
        result['customer_service_semantics_status'] = 'incomplete_customer_service_pairs'
        return result
    observed_ranges = []
    demand = served = opening = ending = Decimal(0)
    active = cleared = 0
    for observations in grouped.values():
        days = sorted(observations)
        expected = list(range(expected_days)) if expected_days is not None else list(range(days[0], days[-1] + 1))
        if days != expected:
            result['customer_service_semantics_status'] = 'incomplete_customer_service_days'
            return result
        observed_ranges.append((days[0], days[-1]))
        previous = None
        for day in days:
            new, needed, delivered, backlog = observations[day]
            if previous is None:
                initial = needed - new
                if initial < -EPS:
                    raise ValueError('Customer requirement is below new demand')
                opening += max(Decimal(0), initial)
                previous = max(Decimal(0), initial)
            if abs(needed - new - previous) > EPS or abs(needed - delivered - backlog) > EPS:
                raise ValueError('Customer backlog balance is inconsistent')
            if delivered - needed > EPS:
                raise ValueError('Customer service exceeds the requirement')
            demand += new
            served += delivered
            if needed > EPS:
                active += 1
                cleared += delivered + EPS >= needed
            previous = backlog
        ending += previous
    if len(set(observed_ranges)) != 1:
        result['customer_service_semantics_status'] = 'inconsistent_customer_service_windows'
        return result
    denominator = demand + opening
    result.update(quantity_service_rate=float(served / denominator) if denominator else None,
        product_availability=cleared / active if active else None,
        quantity_service_demand_qty=float(demand), quantity_service_served_qty=float(served),
        quantity_service_opening_backlog_qty=float(opening), quantity_service_ending_backlog_qty=float(ending),
        fully_served_customer_item_days=cleared, active_customer_item_days=active,
        customer_service_semantics_status='identified_quantity_service_and_daily_clearance')
    return result
