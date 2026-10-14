"""Pure memory calendar/transfer oracles; no fixtures, files or timestamp writes."""
from copy import deepcopy
from datetime import date

import pytest

from etudecas.simulation.engine.mrp_planning import FirmReceipt, LotSizing, Requirement, plan_dated_requirements
from etudecas.simulation.engine.run_first_simulation import (
    apply_internal_component_lane_policies, calendarize_manufacturing_plan,
    dated_supply_release_calendar, resolve_site_receipt_calendars,
    supplier_receipt_available_day,
)


ORIGIN = date(2025, 1, 1)
HOLIDAYS = ('2025-01-01', '2025-04-21', '2025-05-01', '2025-05-08', '2025-05-29',
            '2025-06-09', '2025-07-14', '2025-08-15', '2025-11-01', '2025-11-11', '2025-12-25')
CLOSED = frozenset(date.fromisoformat(value) for value in
                   (*HOLIDAYS, *(f'2025-08-{day:02}' for day in range(4, 16))))


def offset(value):
    return (date.fromisoformat(value) - ORIGIN).days


def policy():
    return dict(schema_version=1, mode='explicit_site_nonworking_dates_v1', sites=[dict(
        node_id='Gaillac', calendar_id='explicit_test', nonworking_dates=sorted(d.isoformat() for d in CLOSED),
        source_refs={'dates': 'manual in-memory calendar oracle'}, status='candidate')])


def test_receipt_site_calendar_is_opt_in_absolute_and_preserves_zero_days():
    nodes = [{'id': 'Gaillac'}, {'id': 'Gien'}]
    assert resolve_site_receipt_calendars(None, execution_mode='dated', nodes=nodes) == {}
    resolved = resolve_site_receipt_calendars(policy(), execution_mode='dated', nodes=nodes)
    assert resolved == {'Gaillac': CLOSED} and 'Gien' not in resolved
    assert supplier_receipt_available_day(offset('2025-08-15'), 0,
        origin_date=ORIGIN.isoformat(), nonworking_dates=CLOSED) == offset('2025-08-15')
    # A2025 closure does not recur in2026. Jan1 is counted unless explicitly supplied.
    assert supplier_receipt_available_day(offset('2025-12-31'), 1,
        origin_date=ORIGIN.isoformat(), nonworking_dates=CLOSED) == offset('2026-01-01')
    assert supplier_receipt_available_day(offset('2025-12-31'), 1,
        origin_date=ORIGIN.isoformat(), nonworking_dates=CLOSED | {date(2026, 1, 1)}) == offset('2026-01-02')


def test_receipt_calendar_reproduces_source_75_day_example_and_manual_five_days():
    # Source Extract row23: Apr16 +75eligible days =Aug21, closure4..15Aug.
    assert supplier_receipt_available_day(offset('2025-04-16'), 75,
        origin_date=ORIGIN.isoformat(), nonworking_dates=CLOSED) == offset('2025-08-21')
    # Jul31, Aug1, Aug18, Aug19, Aug20. Arrival dayJul30 is not counted.
    assert supplier_receipt_available_day(offset('2025-07-30'), 5,
        origin_date=ORIGIN.isoformat(), nonworking_dates=CLOSED) == offset('2025-08-20')
    assert supplier_receipt_available_day(offset('2025-07-30'), 5,
        origin_date=ORIGIN.isoformat()) == offset('2025-08-06')


def test_exact_anticipation_advances_new_release_without_moving_existing_firm():
    day, need = offset('2025-07-28'), offset('2025-08-20')
    calendar = dated_supply_release_calendar(decision_day=day, through_day=need,
        physical_lead_days=0, receipt_days=5, receipt_nonworking_dates=CLOSED)
    firm = FirmReceipt('initial-source-I', offset('2025-08-05'), 40, 'held')
    plan = plan_dated_requirements(decision_day=day, available_qty=0,
        requirements=[Requirement('need', need, 100)], firm_receipts=[firm],
        lead_days=7, lot_sizing=LotSizing(integer=True), availability_by_release=calendar)
    assert [(p.release_day, p.available_day, p.qty) for p in plan.proposals] == [
        (offset('2025-07-30'), need, 60)]
    allocation = next(a for a in plan.commitment_allocations if a.supply_id == firm.receipt_id)
    assert (allocation.available_day, allocation.qty) == (offset('2025-08-05'), 40)
    assert sum(b.requirement_qty for b in plan.balances) == 100
    assert all(float(a.qty).is_integer() for a in plan.allocations)


def test_manufacturing_and_receipt_closures_are_distinct_and_firms_preserved():
    needs, firms = [Requirement('need', 233, 150)], [FirmReceipt('fixed-I', 232, 50, 'held')]
    plan = plan_dated_requirements(decision_day=200, available_qty=0, requirements=needs,
        firm_receipts=firms, lead_days=17)
    context = dict(requirements=needs, firm_receipts=firms, closed_days=frozenset(range(215, 227)),
                   process_days=3, receipt_days=10, origin_date=ORIGIN.isoformat())
    legacy = calendarize_manufacturing_plan(plan, **context)
    changed = calendarize_manufacturing_plan(plan, **context, receipt_nonworking_dates=CLOSED)
    assert legacy.proposals[0].release_day == changed.proposals[0].release_day == 211
    assert legacy.proposals[0].available_day == 226  # Aug15, receipt open under old convention.
    assert changed.proposals[0].available_day == offset('2025-08-29')
    assert changed.proposed_qty == legacy.proposed_qty == 100
    allocation = next(a for a in changed.commitment_allocations if a.supply_id == 'fixed-I')
    assert (allocation.available_day, allocation.qty) == (232, 50)


def test_free_transfer_does_not_change_manufacturing_lot_or_reference_transport():
    pair = ('Avene', '693055')
    lane = dict(standard_order_qty=600000., lead_time={'mean': 70}, physical_transport_days=7)
    manufacturing = LotSizing(minimum=600000, multiple=600000)
    original_manufacturing = deepcopy(manufacturing)
    apply_internal_component_lane_policies({pair: dict(transfer_multiple_qty=0, uom='G',
        source_refs={'transfer_multiple_qty': '1190kg observed transfer'}, status='candidate')},
        {pair: [lane]}, schema_version=2)
    assert lane['physical_dispatch_multiple'] == lane['standard_order_qty'] == 0
    assert lane['lead_time'] == {'mean': 70} and lane['physical_transport_days'] == 7
    assert manufacturing == original_manufacturing
    transferred = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('1190kg', 10, 1190000)], firm_receipts=[], lead_days=1,
        lot_sizing=LotSizing(multiple=lane['standard_order_qty']))
    fabricated = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('1190kg', 10, 1190000)], firm_receipts=[], lead_days=1,
        lot_sizing=manufacturing)
    assert transferred.proposed_qty == 1190000 and fabricated.proposed_qty == 1200000


@pytest.mark.parametrize('change', ['unknown_site', 'duplicate_site', 'duplicate_date', 'bad_date',
                                   'missing_provenance', 'unknown_key', 'boolean_schema', 'undated'])
def test_receipt_policy_rejects_ambiguous_or_unproven_contracts(change):
    payload, mode = policy(), 'dated'
    row = payload['sites'][0]
    if change == 'unknown_site': row['node_id'] = 'absent'
    if change == 'duplicate_site': payload['sites'].append(deepcopy(row))
    if change == 'duplicate_date': row['nonworking_dates'].append(row['nonworking_dates'][0])
    if change == 'bad_date': row['nonworking_dates'].append('2025-02-31')
    if change == 'missing_provenance': row['source_refs'] = {}
    if change == 'unknown_key': row['invented_scope'] = 'safety'
    if change == 'boolean_schema': payload['schema_version'] = True
    if change == 'undated': mode = 'legacy'
    with pytest.raises(ValueError):
        resolve_site_receipt_calendars(payload, execution_mode=mode, nodes=[{'id': 'Gaillac'}])
