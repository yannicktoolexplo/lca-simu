"""Independent arithmetic for optional protection exports; no engine imports.

This checks the reservation/service bridge and its linkage to executed lots.
It does not infer industrial priority or validate every substitution policy.
"""
from bisect import bisect_right
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING


def audit_active_batch_materials(claim_rows, allocation_rows, service_rows,
                                 plan_rows, issue_rows, evidence):
    def quantity(row, field):
        value = Decimal(str(row[field]))
        if not value.is_finite():
            raise ValueError('Nonfinite active batch material audit quantity')
        evidence.check('active_protection_nonnegative', value >= 0, [field, row])
        if row.get('uom') == 'UN':
            evidence.check('active_protection_integer_units', value == value.to_integral_value(), [field, row])
        return value

    def equal(name, actual, expected, context, unit):
        if unit == 'UN':
            evidence.check(name, actual == expected, context)
        else:
            evidence.close(name, float(actual), float(expected), context)

    # Daily closing work state; several intraday records can refer to one batch.
    states = defaultdict(dict)
    for row in plan_rows:
        if row.get('batch_id') and row.get('batch_target_qty') not in ('', None):
            target = Decimal(str(row['batch_target_qty']))
            if target > 0:
                states[row['batch_id']][int(row['day'])] = row
    issues = defaultdict(dict)
    for row in issue_rows:
        issues[row['batch_id'], row['component_item_id']][int(row['day'])] = row
    state_days = {key: sorted(records) for key, records in states.items()}
    issue_days = {key: sorted(records) for key, records in issues.items()}

    def latest(records, days, identity, day):
        ordered = days.get(identity, ())
        index = bisect_right(ordered, day) - 1
        return records[identity][ordered[index]] if index >= 0 else None

    groups = defaultdict(list)
    protected_totals = defaultdict(Decimal)
    physical_allocations = set()
    for row in claim_rows:
        day = int(row['day'])
        identity = (day, row['batch_id'], row['node_id'], row['required_item_id'])
        evidence.check('active_protection_policy', row['policy'] == 'engaged_remaining_v1', identity)
        requested = quantity(row, 'requested_remaining_qty')
        protected = quantity(row, 'protected_qty')
        uncovered = quantity(row, 'uncovered_qty')
        groups[identity].append((row, requested, protected, uncovered))
        kind = row['allocation_kind']
        evidence.check('active_protection_kind', kind in ('primary', 'authorized_substitute', 'uncovered'), identity)
        physical = row['physical_item_id']
        evidence.check('active_protection_physical_identity',
                       (kind == 'uncovered' and not physical and protected == 0)
                       or (kind == 'primary' and physical == row['required_item_id'] and uncovered == 0)
                       or (kind == 'authorized_substitute' and bool(physical) and physical != row['required_item_id'] and uncovered == 0), identity)
        if physical:
            allocation_key = (*identity, physical)
            evidence.check('active_protection_unique_allocation', allocation_key not in physical_allocations, allocation_key)
            physical_allocations.add(allocation_key)
            protected_totals[day, row['node_id'], physical] += protected

    for identity, records in groups.items():
        day, batch, node, required = identity
        requested = records[0][1]
        unit = records[0][0]['uom']
        evidence.check('active_protection_consistent_claim', all(r[1] == requested and r[0]['uom'] == unit for r in records), identity)
        equal('active_protection_claim_balance', sum((r[2] + r[3] for r in records), Decimal(0)), requested, identity, unit)
        state = latest(states, state_days, batch, day)
        issue = latest(issues, issue_days, (batch, required), day)
        evidence.check('active_protection_executed_batch_evidence', state is not None and issue is not None, identity)
        if state is None or issue is None:
            continue
        work = Decimal(str(state['batch_executed_end_qty']))
        target = Decimal(str(state['batch_target_qty']))
        evidence.check('active_protection_claim_unit_matches_BOM', unit == issue['component_uom'], identity)
        evidence.check('active_protection_only_incomplete_started_batch', 0 < work < target and state['node_id'] == node, identity)
        ratio = Decimal(str(issue['coefficient_per_output_unit']))
        issued = Decimal(str(issue['issued_after_qty']))
        needed = (max(Decimal(0), (target * ratio).to_integral_value(rounding=ROUND_CEILING) - issued)
                  if unit == 'UN' else max(Decimal(0), (target - work) * ratio))
        equal('active_protection_remaining_BOM', requested, needed, identity, unit)

    services = {}
    for row in service_rows:
        key = int(row['day']), row['node_id'], row['item_id']
        evidence.check('active_protection_unique_service_source', key not in services, key)
        services[key] = row
    expected_claims = set()
    issue_items_by_batch = defaultdict(set)
    for batch_id, item_id in issues:
        issue_items_by_batch[batch_id].add(item_id)
    # A missing reservation must not turn an active batch into unprotected free
    # stock merely because its whole claim was omitted from the new exports.
    for day in sorted({key[0] for key in services}):
        for batch_id in states:
            state = latest(states, state_days, batch_id, day)
            if state is None:
                continue
            work = Decimal(str(state['batch_executed_end_qty']))
            target = Decimal(str(state['batch_target_qty']))
            if not 0 < work < target:
                continue
            for item_id in issue_items_by_batch[batch_id]:
                issue = latest(issues, issue_days, (batch_id, item_id), day)
                if issue is None:
                    continue
                ratio = Decimal(str(issue['coefficient_per_output_unit']))
                issued = Decimal(str(issue['issued_after_qty']))
                needed = (max(Decimal(0), (target * ratio).to_integral_value(rounding=ROUND_CEILING) - issued)
                          if issue['component_uom'] == 'UN' else max(Decimal(0), (target-work)*ratio))
                if needed > 0:
                    expected_claims.add((day, batch_id, state['node_id'], item_id))
    evidence.check('active_protection_complete_claims', set(groups) == expected_claims,
                   {'missing': sorted(expected_claims-set(groups))[:5],
                    'unexpected': sorted(set(groups)-expected_claims)[:5]})
    for day in sorted({key[0] for key in services}):
        pool = {(node, item): Decimal(str(row['available_before_qty']))
                for (d, node, item), row in services.items() if d == day}
        def priority(identity):
            state = latest(states, state_days, identity[1], day)
            return (int(state['batch_started_day']) if state else -1, *identity[1:])
        for identity in sorted((key for key in groups if key[0] == day), key=priority):
            records = groups[identity]
            primary = identity[2], identity[3]
            requested = records[0][1]
            unit = records[0][0]['uom']
            # Only pools present in the independent external service export are
            # observable at this exact intraday phase. No missing pool is zero.
            if primary in pool:
                expected_primary = min(requested, max(Decimal(0), pool[primary]))
                actual_primary = sum((r[2] for r in records if r[0]['physical_item_id'] == primary[1]), Decimal(0))
                equal('active_protection_primary_priority', actual_primary, expected_primary, identity, unit)
            for row, _, protected, _ in records:
                physical = row['node_id'], row['physical_item_id']
                if physical in pool:
                    pool[physical] -= protected
    exported = {}
    for row in allocation_rows:
        key = int(row['day']), row['node_id'], row['item_id']
        evidence.check('active_protection_unique_daily_external', key not in exported, key)
        evidence.check('active_protection_external_policy', row['policy'] == 'engaged_remaining_v1', key)
        fields = ('available_before_qty', 'protected_qty', 'free_before_qty', 'external_required_qty',
                  'external_consumed_qty', 'external_remaining_qty', 'physical_after_qty', 'free_after_qty')
        values = {field: quantity(row, field) for field in fields}
        unit = row['uom']
        a, p, free, need, debit, waiting, after, free_after = (values[field] for field in fields)
        evidence.check('active_protection_within_usable', p <= a, key)
        equal('active_protection_shared_pool_sum', p, protected_totals[key], key, unit)
        equal('active_protection_free_before', free, a - p, key, unit)
        equal('active_protection_external_debit', debit, min(free, need), key, unit)
        equal('active_protection_residual_preserved', waiting, need - debit, key, unit)
        equal('active_protection_physical_balance', after, a - debit, key, unit)
        equal('active_protection_free_after', free_after, free - debit, key, unit)
        equal('active_protection_stock_contains_reserve', after, free_after + p, key, unit)
        source = services.get(key)
        evidence.check('active_protection_external_source_exists', source is not None, key)
        if source:
            for exported_name, native_name in (
                ('available_before_qty', 'available_before_qty'), ('external_required_qty', 'required_qty'),
                ('external_consumed_qty', 'consumed_qty'), ('external_remaining_qty', 'backlog_end_qty'),
                ('physical_after_qty', 'available_after_qty')):
                equal('active_protection_matches_external_' + native_name, values[exported_name],
                      Decimal(str(source[native_name])), key, unit)
        exported[key] = float(p)
    evidence.check('active_protection_complete_external_audit', set(exported) == set(services),
                   {'audit_rows': len(exported), 'service_rows': len(services)})
    return exported
