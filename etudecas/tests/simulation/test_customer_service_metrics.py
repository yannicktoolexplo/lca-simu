"""In-memory service oracles; no files, dates, subprocesses or native runs."""
from copy import deepcopy
from fractions import Fraction

import pytest

from etudecas.simulation.analysis.customer_service_metrics import customer_service_metrics, customer_service_scope


def row(day, new, required, served, backlog, item='PF'):
    return dict(day=day, node_id='C', item_id=item, demand_qty=new,
        required_with_backlog_qty=required, served_qty=served, backlog_end_qty=backlog)


def test_quantity_service_can_be_high_while_no_day_clears_the_backlog():
    rows = [row(0, 10, 10, 9, 1), row(1, 10, 11, 9, 2)]
    before = deepcopy(rows)
    result = customer_service_metrics(rows, expected_days=2)
    assert result['quantity_service_rate'] == float(Fraction(18, 20))
    assert result['product_availability'] == 0
    assert result['quantity_service_ending_backlog_qty'] == 2
    assert rows == before


def test_opening_backlog_is_counted_once_and_not_at_every_new_day():
    rows = [row(0, 5, 10, 5, 5), row(1, 5, 10, 5, 5)]
    result = customer_service_metrics(rows)
    assert result['quantity_service_opening_backlog_qty'] == 5
    assert result['quantity_service_rate'] == float(Fraction(10, 15))


def test_catch_up_counts_in_quantity_service_without_claiming_on_time_delivery():
    result = customer_service_metrics([row(0, 10, 10, 5, 5), row(1, 0, 5, 5, 0)])
    assert result['quantity_service_rate'] == 1
    assert result['product_availability'] == .5
    assert result['active_customer_item_days'] == 2


def test_empty_or_zero_demand_is_unknown_instead_of_one_hundred_percent():
    for rows in ([], [row(0, 0, 0, 0, 0)]):
        result = customer_service_metrics(rows)
        assert result['quantity_service_rate'] is None
        assert result['product_availability'] is None


def test_zero_actual_service_is_a_known_zero_when_demand_is_identified():
    result = customer_service_metrics([row(0, 10, 10, 0, 10)])
    assert result['quantity_service_rate'] == 0
    assert result['product_availability'] == 0


def test_missing_day_tail_or_field_never_produces_a_complete_rate():
    variants = [[row(0, 10, 10, 9, 1)],
        [row(0, 10, 10, 9, 1), row(2, 10, 11, 9, 2)],
        [dict(row(0, 10, 10, 9, 1), served_qty='')]]
    for rows in variants:
        assert customer_service_metrics(rows, expected_days=3)['quantity_service_rate'] is None


def test_duplicate_customer_item_day_is_refused():
    r = row(0, 10, 10, 9, 1)
    with pytest.raises(ValueError, match='Duplicate'):
        customer_service_metrics([r, deepcopy(r)])


@pytest.mark.parametrize('damage', ['nan', 'negative', 'balance', 'requirement', 'day'])
def test_contradictory_physical_rows_are_refused(damage):
    r = row(0, 10, 10, 9, 1)
    if damage == 'nan': r['served_qty'] = 'NaN'
    if damage == 'negative': r['served_qty'] = -1
    if damage == 'balance': r['backlog_end_qty'] = 2
    if damage == 'requirement': r['required_with_backlog_qty'] = 9
    if damage == 'day': r['day'] = .5
    with pytest.raises(ValueError):
        customer_service_metrics([r])


def test_unit_conversion_does_not_change_rates_and_mixed_units_are_refused():
    first = row(0, 10, 10, 9, 1)
    converted = dict(first, **{key: first[key] * 1000 for key in
        ('demand_qty', 'required_with_backlog_qty', 'served_qty', 'backlog_end_qty')})
    assert customer_service_metrics([first])['quantity_service_rate'] == customer_service_metrics([converted])['quantity_service_rate']
    with pytest.raises(ValueError, match='physical unit'):
        customer_service_metrics([dict(first, uom='KG'), dict(first, item_id='other', uom='UN')])


def test_absent_entire_customer_item_pair_stays_unknown():
    result = customer_service_metrics([row(0, 10, 10, 9, 1)],
        expected_pairs=[('C', 'PF'), ('C', 'other')])
    assert result['quantity_service_rate'] is None
    assert result['customer_service_semantics_status'] == 'incomplete_customer_service_pairs'


def graph():
    return {'scenarios': [{'id': 'BASE', 'demand': [{'node_id': 'C', 'item_id': 'PF'}]}],
        'nodes': [{'id': 'C', 'type': 'customer', 'inventory': {'states': [{'item_id': 'PF', 'uom': 'UN'}]}}]}


def test_expected_scope_is_sourced_from_scenario_and_customer_inventory_unit():
    scope = customer_service_scope(graph(), 'BASE')
    assert scope['expected_pairs'] == [('C', 'PF')]
    assert scope['uom'] == 'UN'
    result = customer_service_metrics([row(0, 10, 10, 9, 1)],
        expected_pairs=scope['expected_pairs'], expected_uom=scope['uom'])
    assert result['quantity_service_rate'] == .9


def test_unknown_or_conflicting_source_unit_does_not_certify_a_scope():
    source = graph()
    source['nodes'][0]['inventory']['states'][0].pop('uom')
    assert customer_service_scope(source, 'BASE')['expected_pairs'] is None
    source = graph()
    source['meta'] = {'customer_demand_history': {'rows': [{'node_id': 'C', 'item_id': 'PF', 'uom': 'KG'}]}}
    assert customer_service_scope(source, 'BASE')['expected_pairs'] is None


def test_scope_does_not_mix_products_with_different_physical_units():
    source = graph()
    source['scenarios'][0]['demand'].append({'node_id': 'C', 'item_id': 'bulk'})
    source['nodes'][0]['inventory']['states'].append({'item_id': 'bulk', 'uom': 'KG'})
    with pytest.raises(ValueError, match='different physical units'):
        customer_service_scope(source, 'BASE')
