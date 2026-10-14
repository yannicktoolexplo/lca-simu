"""In-memory order/dispatch oracles; no filesystem fixtures or writes."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import FirmReceipt, Requirement, plan_dated_requirements
from etudecas.simulation.engine.run_first_simulation import (
    apply_internal_component_lane_policies, internal_component_planning_lots,
    mrp_purchase_order_quantity, resolve_internal_component_policies,
    resolve_internal_transfer_planning_lots,
)

PAIR = ('factory', 'component')


def context(*, uom='G', transfer=0, order=None):
    row = dict(policy_id='explicit', node_id=PAIR[0], item_id=PAIR[1], source_node_id='upstream',
        uom=uom, receipt_days=7, receipt_calendar='monday_friday', delivery_reference_days=70,
        transfer_multiple_qty=transfer, status='candidate_not_inferred_ERP', source_refs={
            'receipt_days': 'source E', 'receipt_calendar': 'user Monday-Friday',
            'delivery_reference': 'source FIA', 'transfer_multiple_qty': 'observed1190kg'})
    if order is not None:
        row['order_multiple_qty'] = order
        row['source_refs']['order_multiple_qty'] = 'explicit grouping candidate, not FIA quantity'
    nodes = [dict(id='upstream', type='factory'), dict(id='factory', type='factory', processes=[dict(
        inputs=[dict(item_id='component', ratio_per_batch=1)], outputs=[dict(item_id='finished')])])]
    lanes = {PAIR: [dict(src='upstream', lead_days_mean=70, standard_order_qty=1)]}
    return dict(schema_version=2, rows=[row]), nodes, lanes, {'component': uom}


def resolve(payload, nodes, lanes, units):
    return resolve_internal_component_policies(payload, execution_mode='dated', nodes=nodes,
        lanes_by_dest_item=lanes, item_unit_map=units)


@pytest.mark.parametrize('multiple', [0, 600000])
def test_omitted_order_multiple_retains_legacy_coupling(multiple):
    payload, nodes, lanes, units = context(transfer=multiple)
    policies = resolve(payload, nodes, lanes, units)
    apply_internal_component_lane_policies(policies, lanes, schema_version=2)
    lots = internal_component_planning_lots(policies, units)
    assert lots[PAIR].multiple == multiple
    assert lanes[PAIR][0]['internal_transfer_multiple_qty'] == multiple
    assert lanes[PAIR][0]['standard_order_qty'] == multiple


def test_order_groups_dated_needs_but_allows_1190kg_physical_transfer():
    payload, nodes, lanes, units = context(order=600000)
    policies = resolve(payload, nodes, lanes, units)
    original = deepcopy(payload)
    apply_internal_component_lane_policies(policies, lanes, schema_version=2)
    lot = internal_component_planning_lots(policies, units)[PAIR]
    plan = plan_dated_requirements(decision_day=0, available_qty=0, firm_receipts=[], lead_days=1,
        requirements=[Requirement('first', 10, 300000), Requirement('second', 11, 300000)], lot_sizing=lot)
    assert len(plan.proposals) == 1 and plan.proposed_qty == 600000
    lane = lanes[PAIR][0]
    assert lane['standard_order_qty'] == lane['physical_dispatch_multiple'] == 0
    transferred = mrp_purchase_order_quantity(1200000, 1190000,
        lane['internal_transfer_multiple_qty'], binding=True, uom='G')
    assert transferred == 1190000  # Quantity carried is not a manufacturing batch.
    assert payload == original and lane['lead_days_mean'] == 70


def test_existing_transferred_and_committed_quantities_do_not_create_second_order():
    payload, nodes, lanes, units = context(order=600000)
    lot = internal_component_planning_lots(resolve(payload, nodes, lanes, units), units)[PAIR]
    # One1200kg order:1190in transit,10still promised. Do not order another600.
    firms = [FirmReceipt('in-transit', 10, 1190000), FirmReceipt('unshipped-balance', 11, 10000)]
    plan = plan_dated_requirements(decision_day=1, available_qty=0, lead_days=1,
        requirements=[Requirement('need', 11, 1200000)], firm_receipts=firms, lot_sizing=lot)
    assert plan.proposed_qty == 0 and not plan.proposals
    assert sum(a.qty for a in plan.commitment_allocations) == 1200000


def test_explicit_order_precedes_legacy_physical_alignment_and_preserves_units():
    payload, nodes, lanes, units = context(uom='UN', transfer=300, order=600)
    policies = resolve(payload, nodes, lanes, units)
    apply_internal_component_lane_policies(policies, lanes, schema_version=2)
    lots = internal_component_planning_lots(policies, units)
    aligned = resolve_internal_transfer_planning_lots('execution_dispatch_multiple_v1',
        execution_mode='dated', nodes=nodes, component_pairs={PAIR}, lanes_by_dest_item=lanes,
        item_unit_map=units, current_lots=lots, explicit_order_pairs={PAIR})
    assert aligned == {} and lots[PAIR].multiple == 600 and lots[PAIR].integer
    plan = plan_dated_requirements(decision_day=0, available_qty=0, lead_days=1,
        requirements=[Requirement('need', 10, 305)], firm_receipts=[], lot_sizing=lots[PAIR])
    assert plan.proposed_qty == 600
    assert mrp_purchase_order_quantity(600, 500, 300, binding=True, uom='UN') == 300


@pytest.mark.parametrize('error', ['negative', 'boolean', 'nan', 'fractional_UN', 'provenance', 'incompatible'])
def test_order_multiple_rejects_invalid_or_ambiguous_contract(error):
    payload, nodes, lanes, units = context(uom='UN', transfer=0, order=600)
    row = payload['rows'][0]
    if error == 'negative': row['order_multiple_qty'] = -1
    if error == 'boolean': row['order_multiple_qty'] = True
    if error == 'nan': row['order_multiple_qty'] = float('nan')
    if error == 'fractional_UN': row['order_multiple_qty'] = 1.5
    if error == 'provenance': del row['source_refs']['order_multiple_qty']
    if error == 'incompatible': row['transfer_multiple_qty'] = 400
    with pytest.raises(ValueError):
        resolve(payload, nodes, lanes, units)
