"""Customer/DC weekly comparisons: pure memory fixtures and manual balances."""
from copy import deepcopy

import pytest

from etudecas.visualization.maps.source_comparison import (
    CUSTOMER_RESPONSE_COLUMNS, _customer_response_payload, _customer_response_run,
)


def _registers():
    """100 DC units, 30 received and shipped; 10 still travelling on Sunday."""
    service, stocks = [], []
    events = []

    def event(identity, day, kind, node, qty, shipment='', source=''):
        events.append(dict(event_id=identity, day=day, event_type=kind, node_id=node,
                           item_id='item:268091', qty=qty, uom='UN',
                           shipment_id=shipment, source_id=source))

    event('ship1', 5, 'lane_ship', 'DC-1920', 20, 'S1', 'L_DC-1920_TO_C-1_268091')
    event('receiveDC', 6, 'lane_receipt', 'DC-1920', 30, 'FROM_FACTORY')
    event('receiveC1', 7, 'lane_receipt', 'C-1', 20, 'S1')
    event('service1', 7, 'demand_service', 'C-1', 20)
    event('ship2', 10, 'lane_ship', 'DC-1920', 10, 'S2', 'L_DC-1920_TO_C-1_268091')
    event('release', 10, 'stock_availability_release', 'DC-1920', 400)
    event('receiveC2', 12, 'lane_receipt', 'C-1', 10, 'S2')
    event('service2', 12, 'demand_service', 'C-1', 10)
    for day in range(19):
        demand = 35 if day == 5 else 0
        served = 20 if day == 7 else 10 if day == 12 else 0
        backlog = 0 if day < 5 else 35 if day < 7 else 15 if day < 12 else 5
        service.append(dict(day=day, node_id='C-1', item_id='item:268091', uom='UN',
                            demand_qty=demand, served_qty=served, backlog_end_qty=backlog))
        dc = 100 - (20 if day >= 5 else 0) + (30 if day >= 6 else 0) - (10 if day >= 10 else 0)
        for node, stock in [('DC-1920', dc), ('C-1', 0)]:
            stocks.append(dict(day=day, node_id=node, item_id='item:268091',
                               uom='UN', physical_qty=stock))
    return service, stocks, events


def _sources():
    return (
        {'products': {'268091': {'history': [[5, 35, -35, 3], [12, 0, 0, 4]]}}},
        {'268091/1920': {'observed': [[5, 100, 11], [12, 110, 22], [19, 110, 33]],
                         'source_movements': {'rows': [[4, 5, 11, 2, 0, 10, -5, 40],
                                                       [11, 12, 18, 0, 0, 0, 0, 41]]}}})


def test_customer_response_simulated_week_manual_balance_and_transit():
    registers = _registers()
    before = deepcopy(registers)
    result = _customer_response_run(*registers)
    # Monday J5–Sunday J11, with 10 units arriving only the following Monday.
    assert result['268091'][0] == [5, 11, 35, 30, 30, 20, 20, 10, 15, 100, 100, 0, 0, 0]
    assert result['268091'][1] == [12, 18, 0, 0, 0, 10, 10, 0, 5, 100, 100, 0, 0, 0]
    assert len(result['268091']) == 51
    assert result['268091'][-1][:2] == [355, 361]
    assert registers == before


def test_customer_response_observed_net_residual_dates_and_explicit_zero():
    source, pairs = _sources()
    result = _customer_response_payload(source, pairs, {'nominal': {'customer_response': {}}})
    product = result['products']['268091']
    # Net=2+0+10-5=7 ; photo variation=10 ; residual=variation-net=3.
    assert product['observed'][0] == [5, 11, 35, 100, 110, 10, 7, 3, 3, 11, 22, 40]
    assert product['observed'][1] == [12, 18, 0, 110, 110, 0, 0, 0, 4, 22, 33, 41]
    assert len(product['observed']) == 51
    assert result['columns'] == CUSTOMER_RESPONSE_COLUMNS
    assert 'receipts' not in result['columns']['observed']
    assert product['simulations']['nominal'] == []


def test_customer_response_source_absence_never_becomes_zero_or_imputed_receipt():
    source, pairs = _sources()
    del pairs['268091/1920']['source_movements']
    source['products']['268091']['history'] = []
    observed = _customer_response_payload(source, pairs, {})['products']['268091']['observed']
    assert observed[0][2] is None
    assert observed[0][3:6] == [100, 110, 10]
    assert observed[0][6:9] == [None, None, None]
    assert observed[2][3:8] == [110, None, None, None, None]
    assert _customer_response_payload(None, pairs, {}) is None


def test_customer_response_missing_service_and_stock_remain_unknown():
    service, stocks, events = _registers()
    service = [r for r in service if r['day'] != 6]
    stocks = [r for r in stocks if not (r['day'] == 4 and r['node_id'] == 'DC-1920')]
    result = _customer_response_run(service, stocks, events)
    first = result['268091'][0]
    assert first[2] is None and first[6] is None and first[8] is None
    assert first[9] is None and first[11] is None and first[13] is None
    assert result['268967'][0] == [5, 11, *([None] * 12)]


def test_customer_response_missing_departure_keeps_initial_pipeline_unknown():
    service, stocks, events = _registers()
    events = [r for r in events if r['event_id'] != 'ship1']
    first = _customer_response_run(service, stocks, events)['268091'][0]
    assert first[3] == 10
    assert first[5] is None and first[7] is None
    assert first[13] == -20  # Missing DC departure stays visible in its balance.


def test_customer_response_truncated_register_does_not_invent_future_zero_flows():
    service, stocks, events = _registers()
    # Complete first Monday–Sunday plus its preceding days; no following week.
    result = _customer_response_run(
        [r for r in service if r['day'] <= 11],
        [r for r in stocks if r['day'] <= 11],
        [r for r in events if r['day'] <= 11])['268091']
    assert result[0] == [5, 11, 35, 30, 30, 20, 20, 10, 15, 100, 100, 0, 0, 0]
    assert result[1] == [12, 18, None, None, None, None, None, None, None,
                         100, None, None, None, None]
    assert all(value is None for value in result[2][2:])


@pytest.mark.parametrize('kind', ['duplicate_event', 'fractional_UN', 'wrong_unit',
                                  'duplicate_service', 'duplicate_stock', 'extra_receipt',
                                  'wrong_service'])
def test_customer_response_rejects_ambiguous_or_invalid_registers(kind):
    service, stocks, events = _registers()
    if kind == 'duplicate_event':
        events.append(dict(events[0]))
    elif kind == 'fractional_UN':
        events[0]['qty'] = 20.5
    elif kind == 'wrong_unit':
        events[0]['uom'] = 'KG'
    elif kind == 'duplicate_service':
        service.append(dict(service[0]))
    elif kind == 'duplicate_stock':
        stocks.append(dict(stocks[0]))
    elif kind == 'extra_receipt':
        events[2]['qty'] = 21
    elif kind == 'wrong_service':
        service[7]['served_qty'] = 19
    with pytest.raises(ValueError):
        _customer_response_run(service, stocks, events)
