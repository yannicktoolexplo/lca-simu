"""Customer/DC weekly comparisons: pure memory fixtures and manual balances."""
from copy import deepcopy

import pytest

from etudecas.visualization.maps.source_comparison import (
    CUSTOMER_RESPONSE_COLUMNS, _customer_response_payload, _customer_response_run,
    _factory_dispatch_observed, _factory_dispatch_run, build_factory_dispatch_comparison,
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


def _factory_registers():
    """A legacy-named edge really targets Muret; split lot departures total 30."""
    routes = [dict(id='edge:M-1810_TO_DC-1910_268091', type='transport',
                   **{'from': 'M-1810', 'to': 'DC-1920'}, items=['item:268091']),
              dict(id='factory_to_other_dc', type='transport',
                   **{'from': 'M-1810', 'to': 'DC-OTHER'}, items=['item:268091'])]
    stocks = [dict(day=day, node_id=node, item_id='item:268091', uom='UN', physical_qty=100)
              for day in range(12) for node in ('M-1810', 'DC-1920')]
    events = []

    def event(identity, day, kind, node, qty, shipment='F1', route=routes[0]['id']):
        events.append(dict(event_id=identity, day=day, event_type=kind, node_id=node,
            item_id='item:268091', qty=qty, uom='UN', shipment_id=shipment,
            source_id=route, departure_day=0, arrival_day=99))

    event('reserve', 4, 'shipment_reserve', 'M-1810', 300)
    event('part1', 5, 'lane_ship', 'M-1810', 20)
    event('part2', 5, 'lane_ship', 'M-1810', 10)
    event('receipt', 7, 'lane_receipt', 'DC-1920', 30)
    event('made', 5, 'production_output', 'M-1810', 500)
    event('release', 5, 'stock_availability_release', 'M-1810', 400)
    event('client', 5, 'lane_ship', 'DC-1920', 200, 'C1', 'dc_to_customer')
    event('other', 5, 'lane_ship', 'M-1810', 100, 'O1', 'factory_to_other_dc')
    return stocks, events, routes


def test_factory_dispatch_filter_and_split_shipment_manual_oracle():
    registers = _factory_registers()
    before = deepcopy(registers)
    actual = _factory_dispatch_run(*registers)['268091']
    assert actual['daily'][5] == {'day': 5, 'shipped_qty': 30}
    assert sum(r['shipped_qty'] for r in actual['daily'][:12]) == 30
    assert actual['daily'][4]['shipped_qty'] == 0
    assert actual['documented_days'] == list(range(12))
    assert actual['transport_delay_days'] == 2  # Actual days 7-5; ignore planned 99-0.
    match, = actual['transport_delay_evidence']['matched_shipments']
    assert match['departure_event_ids'] == ['part1', 'part2']
    assert match['receipt_event_ids'] == ['receipt']
    assert match['shipped_qty'] == match['received_qty'] == 30
    assert match['transport_delay_days'] == [2]
    assert registers == before


def test_factory_dispatch_missing_coverage_and_absent_ledger_remain_unknown():
    stocks, events, routes = _factory_registers()
    stocks = [r for r in stocks if not (r['day'] == 6 and r['node_id'] == 'M-1810')]
    result = _factory_dispatch_run(stocks, events, routes)
    assert result['268091']['daily'][6]['shipped_qty'] is None
    assert result['268091']['daily'][12]['shipped_qty'] is None
    assert result['268091']['daily'][11]['shipped_qty'] == 0
    assert 6 not in result['268091']['documented_days']
    assert all(r['shipped_qty'] is None for r in result['268967']['daily'])
    missing = _factory_dispatch_run(stocks, [], routes, has_event_ledger=False)['268091']
    assert all(r['shipped_qty'] is None for r in missing['daily'])
    assert missing['transport_delay_days'] is None


def test_factory_dispatch_source_balance_uses_g_only_and_preserves_negative():
    demand, pairs = _sources()
    before = deepcopy((demand, pairs))
    actual = build_factory_dispatch_comparison(demand, pairs, {})
    observed = actual['products']['268091']['observed']
    # First week: 110-100 +35 clients -2 Divers =43, NOT delta+35-(G+H+I+J).
    assert observed[0]['reconstructed_receipt_raw_qty'] == 43
    assert observed[0]['reconstructed_receipt_qty'] == 43
    assert observed[0]['other_net_qty'] == 2
    assert observed[0]['status'] == 'reconstructed'
    assert observed[0]['history_excel_row'] == 3
    assert observed[0]['opening_photo_excel_row'] == 11
    assert observed[0]['closing_photo_excel_row'] == 22
    assert observed[0]['movement_excel_row'] == 40
    assert observed[0]['arrival_start_date'] == '2025-01-06'
    assert observed[0]['closing_photo_date'] == '2025-01-13'
    assert len(observed) == 51 and observed[-1]['arrival_end_day'] == 361
    assert observed[1]['reconstructed_receipt_qty'] == 0
    assert (demand, pairs) == before
    pairs['268091/1920']['observed'][1][1] = 60
    negative = _factory_dispatch_observed(demand['products']['268091'], pairs['268091/1920'])[0]
    assert negative['reconstructed_receipt_raw_qty'] == -7  # 60-100+35-2
    assert negative['reconstructed_receipt_qty'] is None
    assert negative['status'] == 'negative_reconstruction'


def test_factory_dispatch_source_absence_is_not_zero_and_customer_arrays_unchanged():
    demand, pairs = _sources()
    response_before = _customer_response_payload(demand, pairs, {})
    build_factory_dispatch_comparison(demand, pairs, {})
    assert _customer_response_payload(demand, pairs, {}) == response_before
    del pairs['268091/1920']['source_movements']
    demand['products']['268091']['history'] = []
    result = build_factory_dispatch_comparison(demand, pairs, {})
    observed = result['products']['268091']['observed']
    assert observed[0]['history_outbound_assumption_qty'] is None
    assert observed[0]['other_net_qty'] is None
    assert observed[0]['stock_delta_qty'] == 10
    assert observed[0]['reconstructed_receipt_raw_qty'] is None
    assert observed[0]['status'] == 'missing_source'
    assert result['default_transport_lag_days'] is None
    assert build_factory_dispatch_comparison(None, pairs, {}) is None


def test_factory_dispatch_unreceived_tail_keeps_matched_transport_delay():
    stocks, events, routes = _factory_registers()
    tail = dict(events[1], event_id='tail', day=11, qty=7, shipment_id='F2')
    actual = _factory_dispatch_run(stocks, events + [tail], routes)['268091']
    assert actual['transport_delay_days'] == 2
    assert actual['daily'][11]['shipped_qty'] == 7
    incomplete, = actual['transport_delay_evidence']['incomplete_shipments']
    assert incomplete['shipment_id'] == 'F2' and incomplete['received_qty'] == 0


def test_factory_dispatch_variable_transport_delays_are_not_averaged():
    stocks, events, routes = _factory_registers()
    events.extend([dict(events[1], event_id='ship2', day=6, qty=7, shipment_id='F2'),
                   dict(events[3], event_id='receive2', day=9, qty=7, shipment_id='F2')])
    actual = _factory_dispatch_run(stocks, events, routes)['268091']
    assert actual['transport_delay_days'] is None
    assert actual['transport_delay_evidence']['observed_delays_days'] == [2, 3]


@pytest.mark.parametrize('kind', ['duplicate_event', 'fractional_UN', 'wrong_unit',
                                  'duplicate_stock', 'extra_receipt', 'receipt_before_ship',
                                  'wrong_route_endpoint'])
def test_factory_dispatch_rejects_invalid_physical_registers(kind):
    stocks, events, routes = _factory_registers()
    if kind == 'duplicate_event':
        events.append(dict(events[1]))
    elif kind == 'fractional_UN':
        events[1]['qty'] = 20.5
    elif kind == 'wrong_unit':
        events[1]['uom'] = 'KG'
    elif kind == 'duplicate_stock':
        stocks.append(dict(stocks[0]))
    elif kind == 'extra_receipt':
        events[3]['qty'] = 31
    elif kind == 'receipt_before_ship':
        events[3]['day'] = 4
    elif kind == 'wrong_route_endpoint':
        events[1]['node_id'] = 'DC-1920'
    with pytest.raises(ValueError):
        _factory_dispatch_run(stocks, events, routes)
