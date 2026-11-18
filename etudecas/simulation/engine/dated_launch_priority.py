"""Pure capacity/material ordering for a hypothetical physical launch.

The persistent order book is never modified. Successor dates below are a
conditional capacity projection, not a new firm promise or a stock receipt.
"""
import math


def _quantity(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Priority projection requires finite nonnegative quantities")
    return float(value)


def frozen_material_requirement_links(orders, bom_by_pair):
    """Join exact native requirement identities without parsing an order ID."""
    links = {}
    for order in orders:
        if order['state'] != 'frozen':
            continue
        output = order['node_id'], order['item_id']
        for component, _ in bom_by_pair.get(output, ()):
            identity = 'frozen_material:' + order['order_id'] + ':' + '|'.join(component)
            key = component, identity
            if key in links:
                raise ValueError("Duplicate structured frozen-component link")
            links[key] = dict(frozen_order_id=order['order_id'],
                frozen_output_node_id=output[0], frozen_output_item_id=output[1],
                frozen_component_requirement_id=identity,
                frozen_planned_release_day=order['planned_release_day'],
                frozen_created_day=order['created_day'])
    return links


def project_dated_launch_priority(*, decision_day, capacity_by_day, candidate_work,
        own_order_id, output_pair, frozen_orders, opening_work, frozen_work, other_requirements):
    """Keep native order priority in both capacity and component obligations.

    Only later orders of the same output pair can be projected after the
    candidate. At most one new campaign for that pair starts on a date: any
    unused capacity on its last day cannot start the next campaign.
    """
    rows = tuple(dict(row) for row in frozen_orders)
    by_id = {}
    for row in rows:
        identity = row['order_id']
        if (not isinstance(identity, str) or not identity or identity in by_id
                or row['state'] != 'frozen'
                or any(type(row[k]) is not int or row[k] < 0
                       for k in ('planned_release_day', 'created_day', 'known_day'))
                or row['created_day'] > decision_day or row['known_day'] > decision_day
                or _quantity(row['qty']) <= 0):
            raise ValueError("Invalid or future frozen priority metadata")
        by_id[identity] = row
    if own_order_id not in by_id:
        return dict(allowed=False, reason='missing_candidate_priority_metadata',
            capacity_reservations=[], other_requirements=list(other_requirements),
            priority_orders=[], retimed_requirements=[])
    own = by_id[own_order_id]
    if ((own['node_id'], own['item_id']) != tuple(output_pair)
            or own['planned_release_day'] > decision_day
            or own['qty'] != math.fsum(candidate_work.values())):
        return dict(allowed=False, reason='inconsistent_candidate_priority_metadata',
            capacity_reservations=[], other_requirements=list(other_requirements),
            priority_orders=[], retimed_requirements=[])
    same_pair = {identity: row for identity, row in by_id.items()
                 if (row['node_id'], row['item_id']) == tuple(output_pair)}
    expected = {}
    for identity, earliest, quantity in frozen_work:
        if identity in expected:
            raise ValueError("Duplicate native frozen reservation")
        expected[identity] = earliest, _quantity(quantity)
    if set(expected) != set(same_pair) or any(
            expected[identity] != (max(decision_day, row['planned_release_day']), row['qty'])
            for identity, row in same_pair.items()):
        raise ValueError("Structured priority must reconcile every native frozen reservation exactly")
    key = lambda row: (row['planned_release_day'], row['created_day'], row['order_id'])
    ordered = sorted(same_pair.values(), key=key)
    own_key = key(own)
    initial = tuple(opening_work)
    initial_ids = set()
    for identity, earliest, quantity in initial:
        if (not identity or identity in initial_ids or identity in same_pair
                or type(earliest) is not int):
            raise ValueError("Initial and frozen capacity reservations must have disjoint identities")
        initial_ids.add(identity)
        _quantity(quantity)
    days = tuple(sorted(capacity_by_day))
    if not days or days[0] != decision_day or not candidate_work:
        raise ValueError("Priority projection needs the current dated capacity trajectory")
    capacities = {d: _quantity(capacity_by_day[d]) for d in days}
    reserved = {d: 0.0 for d in days}
    reservations = []
    projected = {}
    finish = max(candidate_work)

    def reserve(identity, earliest, quantity, stage):
        remaining = float(quantity)
        allocations = []
        for d in days:
            if d < max(decision_day, earliest):
                continue
            amount = min(remaining, max(0.0, capacities[d] - reserved[d]))
            if amount > 0:
                reserved[d] += amount
                remaining -= amount
                allocations.append(dict(day=d, qty=amount))
            if remaining <= 0:
                break
        start = allocations[0]['day'] if allocations else None
        end = allocations[-1]['day'] if allocations and remaining <= 0 else None
        row = dict(order_id=identity, earliest_day=earliest, qty=quantity,
            allocations=allocations, unplaced_qty=remaining, priority_stage=stage,
            projected_start_day=start, projected_finish_day=end)
        if identity in same_pair:
            source = same_pair[identity]
            row.update(planned_release_day=source['planned_release_day'], created_day=source['created_day'],
                priority_key=list(key(source)), projected_launch_delay_days=(
                    max(0, start - source['planned_release_day']) if start is not None else None))
        reservations.append(row)
        projected[identity] = row
        return end

    # Initial observed commitments remain prior claims, even if their future
    # physical due date overlaps the candidate's uninterrupted trajectory.
    for identity, earliest, quantity in sorted(initial, key=lambda row: (row[1], row[0])):
        reserve(identity, earliest, quantity, 'initial')
    prior_finish = decision_day - 1
    for row in ordered:
        if key(row) >= own_key:
            continue
        end = reserve(row['order_id'], max(row['planned_release_day'], prior_finish + 1),
            row['qty'], 'earlier_frozen')
        prior_finish = end if end is not None else days[-1]
    conflicts = [dict(day=d, batch_work=q, other_reserved=reserved[d], capacity=capacities[d])
        for d, q in candidate_work.items() if q + reserved[d] > capacities[d]]
    prior_launches_today = [row['order_id'] for row in reservations
        if row['priority_stage'] == 'earlier_frozen' and row['projected_start_day'] == decision_day]
    candidate_blocked = bool(conflicts or prior_launches_today or any(key(row) < own_key for row in ordered))
    # The following projection is conditional on candidate admission. It never
    # erases a successor, even if a higher-priority conflict refuses that admission.
    for d, quantity in candidate_work.items():
        reserved[d] += quantity
    successor_earliest = finish + 1
    for row in ordered:
        if key(row) <= own_key:
            continue
        end = reserve(row['order_id'], max(row['planned_release_day'], successor_earliest),
            row['qty'], 'later_same_output')
        successor_earliest = (end + 1) if end is not None else days[-1] + 1
    successors = {identity: row for identity, row in projected.items()
                  if row['priority_stage'] == 'later_same_output'}
    requirements = []
    retimed = []
    for original in other_requirements:
        row = dict(original)
        if row.get('basis') == 'other_frozen_order_components':
            identity = row.get('frozen_order_id')
            source = by_id.get(identity)
            if source is None:
                raise ValueError("Frozen material requirement needs an exact structured order link")
            expected_identity = 'frozen_material:' + identity + ':' + '|'.join((row['node_id'], row['item_id']))
            if (row.get('frozen_component_requirement_id') != expected_identity
                    or row['identity'] != 'other_frozen_order_components:' + expected_identity
                    or (row.get('frozen_output_node_id'), row.get('frozen_output_item_id'))
                       != (source['node_id'], source['item_id'])
                    or row.get('frozen_planned_release_day') != source['planned_release_day']
                    or row.get('frozen_created_day') != source['created_day']):
                raise ValueError("Frozen material link and original priority metadata disagree")
            if identity == own_order_id:
                raise ValueError("Candidate component needs must be excluded exactly once")
            if identity in successors:
                projection = successors[identity]
                start = projection['projected_start_day']
                new_day = max(row['due_day'], start if start is not None else days[-1] + 1)
                row.update(due_day=new_day, original_due_day=original['due_day'],
                    projected_order_start_day=start,
                    retiming_basis='same_output_successor_capacity_priority_only_no_book_revision')
                retimed.append(dict(identity=row['identity'], frozen_order_id=identity,
                    node_id=row['node_id'], item_id=row['item_id'], qty=row['qty'],
                    original_due_day=original['due_day'], projected_due_day=new_day,
                    planned_release_day=source['planned_release_day'], created_day=source['created_day']))
        requirements.append(row)
    return dict(allowed=not candidate_blocked,
        reason='known_capacity_commitment_conflict' if candidate_blocked else 'native_priority_projection',
        capacity_reservations=reservations, other_requirements=requirements,
        retimed_requirements=retimed, capacity_conflicts=conflicts,
        prior_launches_today=prior_launches_today,
        priority_orders=[dict(order_id=row['order_id'], priority_key=list(key(row)), qty=row['qty'],
            candidate=row['order_id'] == own_order_id) for row in ordered],
        candidate_excluded_count=1, successor_material_feasibility='not_certified_beyond_candidate_finish')
