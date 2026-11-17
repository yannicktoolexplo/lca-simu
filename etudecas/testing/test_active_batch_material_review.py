"""Independent in-memory examples; never mutate filesystem fixtures."""
from copy import deepcopy

import pytest

from etudecas.testing.active_batch_material_review import audit_active_batch_materials
from etudecas.testing.independent_review import Evidence


def memory_case():
    claim = dict(day=2, policy='engaged_remaining_v1', batch_id='batch', node_id='M',
                 required_item_id='X', physical_item_id='X', uom='UN',
                 requested_remaining_qty=6, protected_qty=6, uncovered_qty=0, allocation_kind='primary')
    allocation = dict(day=2, policy='engaged_remaining_v1', node_id='M', item_id='X', uom='UN',
                      available_before_qty=10, protected_qty=6, free_before_qty=4,
                      external_required_qty=7, external_consumed_qty=4, external_remaining_qty=3,
                      physical_after_qty=6, free_after_qty=0)
    service = dict(day=2, node_id='M', item_id='X', available_before_qty=10,
                   required_qty=7, consumed_qty=4, backlog_end_qty=3, available_after_qty=6)
    work = dict(day=1, batch_id='batch', node_id='M', batch_started_day=1, batch_target_qty=10, batch_executed_end_qty=4)
    issue = dict(day=1, batch_id='batch', component_item_id='X', component_uom='UN', coefficient_per_output_unit=1,
                 issued_after_qty=4)
    return [claim], [allocation], [service], [work], [issue]


def evaluate(payload):
    evidence = Evidence()
    values = audit_active_batch_materials(*payload, evidence)
    failures = {name: entry for name, entry in evidence.checks.items() if entry['failed']}
    return values, failures


def test_protected_stock_and_competing_demand_conserved():
    values, failures = evaluate(memory_case())
    assert not failures
    assert values == {(2, 'M', 'X'): 6.0}


@pytest.mark.parametrize('fault', ['dropped_reserve', 'dropped_waiting', 'excess_claim', 'unstarted',
                                  'completed', 'duplicate_allocation', 'missing_external_audit', 'fractional_units',
                                  'omitted_active_claim', 'unused_primary_stock'])
def test_reject_inconsistent_memory_records(fault):
    records = deepcopy(memory_case())
    claim, allocation, service, work, issue = records
    if fault == 'dropped_reserve':
        allocation[0]['physical_after_qty'] = 0
        service[0]['available_after_qty'] = 0
    elif fault == 'dropped_waiting':
        allocation[0]['external_remaining_qty'] = 0
        service[0]['backlog_end_qty'] = 0
    elif fault == 'excess_claim':
        claim[0]['requested_remaining_qty'] = 8
        claim[0]['uncovered_qty'] = 2
    elif fault == 'unstarted':
        work[0]['batch_executed_end_qty'] = 0
    elif fault == 'completed':
        work[0]['batch_executed_end_qty'] = 10
    elif fault == 'duplicate_allocation':
        claim.append(deepcopy(claim[0]))
    elif fault == 'missing_external_audit':
        allocation.clear()
    elif fault == 'fractional_units':
        allocation[0]['protected_qty'] = 6.5
    elif fault == 'omitted_active_claim':
        claim.clear()
        allocation[0].update(protected_qty=0, free_before_qty=10, external_consumed_qty=7,
                             external_remaining_qty=0, physical_after_qty=3, free_after_qty=3)
        service[0].update(consumed_qty=7, backlog_end_qty=0, available_after_qty=3)
    elif fault == 'unused_primary_stock':
        claim[0].update(protected_qty=0, uncovered_qty=6, physical_item_id='', allocation_kind='uncovered')
        allocation[0].update(protected_qty=0, free_before_qty=10, external_consumed_qty=7,
                             external_remaining_qty=0, physical_after_qty=3, free_after_qty=3)
        service[0].update(consumed_qty=7, backlog_end_qty=0, available_after_qty=3)
    _, failures = evaluate(records)
    assert failures


def test_requested_amount_is_not_added_twice_for_split_physical_allocation():
    claims, allocations, services, work, issues = deepcopy(memory_case())
    claims[0]['protected_qty'] = 2
    claims.append(dict(claims[0], physical_item_id='OLD', protected_qty=4, allocation_kind='authorized_substitute'))
    allocations[0].update(available_before_qty=2, protected_qty=2, free_before_qty=0, external_consumed_qty=0,
                          external_remaining_qty=7, physical_after_qty=2, free_after_qty=0)
    services[0].update(available_before_qty=2, consumed_qty=0, backlog_end_qty=7, available_after_qty=2)
    allocations.append(dict(allocations[0], item_id='OLD', available_before_qty=4, protected_qty=4,
                            free_before_qty=0, external_required_qty=3, external_consumed_qty=0,
                            external_remaining_qty=3, physical_after_qty=4, free_after_qty=0))
    services.append(dict(services[0], item_id='OLD', available_before_qty=4, required_qty=3,
                         consumed_qty=0, backlog_end_qty=3, available_after_qty=4))
    values, failures = evaluate((claims, allocations, services, work, issues))
    assert not failures
    assert values == {(2, 'M', 'X'): 2.0, (2, 'M', 'OLD'): 4.0}


def test_zero_protection_still_requires_full_external_accounting():
    _, allocations, services, _, _ = memory_case()
    allocations[0].update(protected_qty=0, free_before_qty=10, external_consumed_qty=7,
                          external_remaining_qty=0, physical_after_qty=3, free_after_qty=3)
    services[0].update(consumed_qty=7, backlog_end_qty=0, available_after_qty=3)
    values, failures = evaluate(([], allocations, services, [], []))
    assert not failures
    assert values == {(2, 'M', 'X'): 0.0}
