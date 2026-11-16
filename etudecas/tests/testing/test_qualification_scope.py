"""Qualification scope counterexamples, wholly in memory without file fixtures."""
from copy import deepcopy

import pytest

from etudecas.testing.independent_review import (
    Evidence, audit_internal_transfer_availability, audit_scan3_closed_export,
    declared_scan3_requirements, declared_transfer_receipt_sources,
)


def failed(evidence):
    return {name for name, check in evidence.checks.items() if check['failed']}


def transfer(identity, pair, policy, *, horizon=10):
    quantity, physical, available = 10, 2, 4
    lot, parent, shipment = 'child-'+identity, 'parent-'+identity, 'shipment-'+identity
    order = dict(mrp_order_id=identity, order_type='lane_release', node_id=pair[0],
        item_id=pair[1], physical_delivery_day='2', available_day='4', arrival_day='4',
        planned_receipt_qty='10', source_file=policy, source_row='declared-row',
        actual_physical_receipt_day='2', actual_available_day='4' if horizon > 4 else '')
    common = dict(node_id=pair[0], item_id=pair[1], qty=quantity, uom='UN', lot_id=lot)
    events = [dict(common, event_type='lane_ship', day=0, lot_id=parent, shipment_id=shipment),
        dict(common, event_type='lane_receipt', day=physical, planned_order_id=identity,
            shipment_id=shipment),
        dict(common, event_type='stock_availability_hold', day=physical,
            source_type='internal_transfer_availability', source_id=identity)]
    if horizon > available:
        events.append(dict(common, event_type='stock_availability_release', day=available,
            source_type='internal_transfer_availability', source_id=identity))
    links = [dict(link_type='transport', child_lot_id=lot, parent_lot_id=parent,
        shipment_id=shipment, parent_qty=10, child_qty=10, allocation_share=1)]
    return order, events, links


def transfer_policy():
    return dict(internal_component_policy=dict(rows=[dict(node_id='plant', item_id='component', receipt_days=2)]),
        finished_goods_release_policy=dict(rows=[dict(node_id='factory', item_id='PF',
            depot_node_id='depot', receipt_days=2, location_basis='destination_after_transport')]))


@pytest.mark.parametrize('horizon', [3, 10])
def test_component_and_finished_goods_destinations_have_complete_same_scope(horizon):
    evidence = Evidence()
    sources = declared_transfer_receipt_sources(transfer_policy(), evidence)
    assert sources == {('plant', 'component'): 'graph.meta.internal_component_policy',
                       ('depot', 'PF'): 'graph.meta.finished_goods_release_policy'}
    a = transfer('A', ('plant', 'component'), sources['plant', 'component'], horizon=horizon)
    b = transfer('B', ('depot', 'PF'), sources['depot', 'PF'], horizon=horizon)
    before = deepcopy((a, b))
    assert audit_internal_transfer_availability([a[0], b[0]], a[1]+b[1], a[2]+b[2],
        horizon, set(sources), evidence, policy_sources=sources) == 2
    assert not failed(evidence)
    assert (a, b) == before


@pytest.mark.parametrize('fault,expected', [
    ('orphan', 'internal_transfer_no_orphan_availability'),
    ('undeclared_pair', 'internal_transfer_no_orphan_availability'),
    ('wrong_policy', 'internal_transfer_policy_provenance'),
    ('early_release', 'internal_transfer_availability_date'),
    ('duplicate_receipt', 'internal_transfer_single_physical'),
    ('wrong_parent', 'internal_transfer_transported_parents'),
])
def test_finished_goods_scope_does_not_hide_orphans_or_broken_physical_evidence(fault, expected):
    evidence = Evidence()
    sources = declared_transfer_receipt_sources(transfer_policy(), evidence)
    order, events, links = transfer('B', ('depot', 'PF'), sources['depot', 'PF'])
    if fault == 'orphan':
        events.append(dict(events[-1], source_id='unknown-order'))
    elif fault == 'undeclared_pair':
        sources.pop(('depot', 'PF'))
    elif fault == 'wrong_policy':
        order['source_file'] = 'graph.meta.internal_component_policy'
    elif fault == 'early_release':
        events[-1]['day'] = 3
    elif fault == 'duplicate_receipt':
        events.append(deepcopy(events[1]))
    elif fault == 'wrong_parent':
        links[0]['parent_lot_id'] = 'unknown-parent'
    audit_internal_transfer_availability([order], events, links, 10, set(sources), evidence,
        policy_sources=sources)
    assert expected in failed(evidence)


def test_an_availability_event_without_any_declared_policy_is_still_rejected():
    evidence = Evidence()
    order, events, links = transfer('B', ('depot', 'PF'), 'graph.meta.finished_goods_release_policy')
    audit_internal_transfer_availability([order], events, links, 10, set(), evidence, policy_sources={})
    assert 'internal_transfer_no_orphan_availability' in failed(evidence)


def budget(row, first, quantity):
    end = 5 if first == 0 else first+7
    partial = first == 0
    return dict(node_id='plant', item_id='component', source_row=row,
        budget_id=f'plant:component:R{row}', first_day=first, end_day_exclusive=end,
        closing_day=end-1, covered_days=end-first, covered_scan3_qty=quantity,
        full_week_scan3_qty=quantity, raw_signed_scan3_qty=-quantity, uom='UN',
        source_file='observations.xlsx', scan3_source_cell=f'Sheet!J{row}',
        source_week_marker='2024-12-29' if partial else '2025-01-05',
        partial_week=partial, include_in_main_source_balance=not partial,
        coverage_status='documented_withdrawals' if quantity else 'documented_zero')


def source_case(*, budgets=None, events=None):
    sources = [budget(1, 0, 10), budget(2, 5, 20), budget(3, 12, 30)] if budgets is None else budgets
    own = [dict(day=2, node_id='plant', item_id='component', event_type='production_consume',
        qty=3, uom='UN')] if events is None else events
    evidence, closed = Evidence(), []
    result = declared_scan3_requirements(dict(schema_version=1, mode='scan3_residual_v1',
        cumulative_pairs=[['plant', 'component']]), sources, own, 10, 'scn:BASE', evidence,
        closed_rows=closed)
    return result, evidence, closed


def test_archival_future_and_incomplete_budgets_are_valid_but_create_no_requirement():
    result, evidence, closed = source_case()
    assert not failed(evidence)
    assert [r['qty'] for r in result.values()] == [7]  # 10 recorded, 3 physically used.
    assert [r['closing_day'] for r in closed] == [4]
    for cohort in ('closed', 'incomplete', 'future'):
        assert evidence.checks['scan3_budget_cohort_'+cohort]['checked'] == 1


@pytest.mark.parametrize('fault,expected', [
    ('bad_future_quantity', 'scan3_budget_contract'),
    ('duplicate_future', 'scan3_budget_unique'),
    ('fractional_future_UN', 'scan3_source_integer_UN'),
    ('future_own_event', 'scan3_own_execution_in_horizon'),
])
def test_archival_status_does_not_exempt_invalid_source_or_future_execution(fault, expected):
    sources = [budget(1, 0, 10), budget(2, 5, 20), budget(3, 12, 30)]
    events = []
    if fault == 'bad_future_quantity':
        sources[-1]['covered_scan3_qty'] = float('nan')
    elif fault == 'duplicate_future':
        sources.append(deepcopy(sources[-1]))
    elif fault == 'fractional_future_UN':
        sources[-1].update(covered_scan3_qty=30.5, full_week_scan3_qty=30.5, raw_signed_scan3_qty=-30.5)
    else:
        events.append(dict(day=12, node_id='plant', item_id='component',
            event_type='production_consume', qty=3, uom='UN'))
    _, evidence, _ = source_case(budgets=sources, events=events)
    assert expected in failed(evidence)


def closed_export_case():
    _, evidence, closed = source_case()
    row = dict(closed[0], residual_executed_qty=5,
        residual_executed_on_closing_day_qty=0, residual_backlog_initial_qty=0,
        residual_backlog_final_qty=2, residual_backlog_at_closing_qty=7,
        first_execution_day=6, last_execution_day=6)
    event = dict(day=6, source_id=row['requirement_id'], event_type='external_component_consume',
        node_id='plant', item_id='component', qty=5, uom='UN')
    allocation = dict(day=6, requirement_id=row['requirement_id'], node_id='plant',
        item_id='component', qty=5, uom='UN')
    return evidence, closed, [row], [event], [allocation]


def test_closed_export_covers_zero_and_positive_requests_with_exact_physical_allocations():
    evidence, closed, weekly, events, allocations = closed_export_case()
    audit_scan3_closed_export(closed, events, weekly, allocations, 10, evidence)
    assert not failed(evidence)
    # An observed zero remains an explicitly required closed export row.
    _, evidence, closed = source_case(budgets=[budget(1, 0, 0)], events=[])
    audit_scan3_closed_export(closed, [], [], [], 10, evidence)
    assert 'scan3_closed_weekly_coverage' in failed(evidence)


@pytest.mark.parametrize('fault,expected', [
    ('missing_closed_row', 'scan3_closed_weekly_coverage'),
    ('unclosed_row', 'scan3_closed_weekly_coverage'),
    ('future_residual_event', 'scan3_execution_has_closed_budget'),
    ('future_residual_allocation', 'scan3_allocation_has_closed_budget'),
    ('early_allocation', 'scan3_allocation_closed_and_in_horizon'),
    ('wrong_allocated_quantity', 'scan3_allocation_physical_quantity'),
    ('wrong_backlog', 'scan3_closed_weekly_residual_backlog_final_qty'),
    ('changed_source_quantity', 'scan3_closed_weekly_covered_scan3_qty'),
    ('changed_source_row', 'scan3_closed_weekly_source_identity'),
])
def test_closed_export_rejects_premature_publication_and_mismatched_service(fault, expected):
    evidence, closed, weekly, events, allocations = closed_export_case()
    if fault == 'missing_closed_row':
        weekly.clear()
    elif fault == 'unclosed_row':
        weekly.append(dict(weekly[0], budget_id='plant:component:R2'))
    elif fault == 'future_residual_event':
        events[0]['source_id'] = 'external:scn:BASE:zz-reconciled-F3:plant:component:R3:D18'
    elif fault == 'future_residual_allocation':
        allocations[0]['requirement_id'] = 'external:scn:BASE:zz-reconciled-F3:plant:component:R3:D18'
    elif fault == 'early_allocation':
        allocations[0]['day'] = 3
    elif fault == 'wrong_allocated_quantity':
        allocations[0]['qty'] = 4
    elif fault == 'wrong_backlog':
        weekly[0]['residual_backlog_final_qty'] = 0
    elif fault == 'changed_source_quantity':
        weekly[0]['covered_scan3_qty'] = 11
    elif fault == 'changed_source_row':
        weekly[0]['source_row'] = 99
    audit_scan3_closed_export(closed, events, weekly, allocations, 10, evidence)
    assert expected in failed(evidence)
