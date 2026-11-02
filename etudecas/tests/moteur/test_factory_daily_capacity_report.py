"""Memory-only regressions: executed passes are flows, plans are snapshots.

No files, subprocesses, simulation runs, fixtures or integrity probes are used.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.run_first_simulation import build_factory_nominal_capacity_rows


def node(site='plant', item='item:A', capacity=10, unit='KG'):
    return {'id': site, 'name': site, 'type': 'factory', 'processes': [
        {'id': 'process:'+site+item, 'outputs': [{'item_id': item, 'uom': unit}],
         'capacity': {'max_rate': capacity, 'source': 'memory_test'}}]}


def row(day, actual, *, site='plant', item='item:A', desired=0, planned=0, cause='none'):
    return dict(day=day, node_id=site, output_item_id=item, actual_qty=actual,
                desired_qty=desired, planned_qty_after_lot_rule=planned,
                binding_cause=cause, capacity_limit_mode='finite')


def report(rows, nodes=None):
    return build_factory_nominal_capacity_rows(nodes=nodes or [node()],
        production_constraint_rows=rows, item_unit_map={'item:A': 'KG', 'item:B': 'UN'})


def test_daily_capacity_report_sums_passes_and_counts_distinct_days():
    rows = [row(0, 3, desired=10, planned=10), row(0, 2, desired=8, planned=7),
            row(1, 0, cause='capacity'), row(1, 0, cause='capacity'),
            row(1, 0, cause='input_shortage'), row(2, 4)]
    before = deepcopy(rows)
    value, = report(rows)
    assert value['max_actual_qty_per_day'] == 5
    assert value['total_actual_qty'] == 9
    assert value['active_days'] == 2
    assert value['avg_actual_qty_per_active_day'] == 4.5
    assert value['constraint_rows'] == 6
    assert value['current_avg_utilization'] == 0.3  # 9 / (3 observed days * 10)
    assert value['current_max_utilization'] == 0.5
    assert value['capacity_binding_days'] == 1
    assert value['input_shortage_days'] == 1
    assert value['max_planned_qty_after_lot_rule'] == 10  # snapshots, not 10 + 7
    assert value['max_desired_qty_per_day'] == 10  # signal, not 10 + 8
    assert value['industrial_nominal_capacity_qty_per_day'] == pytest.approx(5 / 0.70)
    assert rows == before


def test_daily_capacity_report_is_invariant_to_splitting_and_row_order():
    whole = [row(0, 5, desired=10, planned=10), row(1, 0, cause='capacity'), row(2, 4)]
    split = [row('0', 3, desired=10, planned=10), row(0, 2, desired=8, planned=7),
             row(1, 0, cause='capacity'), row('1', 0, cause='capacity'), row(2, 4)]
    expected, = report(whole)
    for candidate in (split, list(reversed(split))):
        value, = report(candidate)
        assert value['constraint_rows'] == 5
        assert {k: v for k, v in value.items() if k != 'constraint_rows'} == {
            k: v for k, v in expected.items() if k != 'constraint_rows'}


def test_daily_capacity_report_keeps_sites_articles_and_units_separate():
    rows = [row(0, 3), row(0, 2), row(0, 100, item='item:B'),
            row(0, 7, site='other'), row(1, 1, site='other')]
    plant = node()
    plant['processes'].extend(node(item='item:B', unit='UN')['processes'])
    nodes = [plant, node(site='other')]
    values = {(v['node_id'], v['output_item_id']): v for v in report(rows, nodes)}
    assert values['plant', 'item:A']['max_actual_qty_per_day'] == 5
    assert values['plant', 'item:A']['total_actual_qty'] == 5
    assert values['plant', 'item:B']['max_actual_qty_per_day'] == 100
    assert values['plant', 'item:B']['uom'] == 'UN'
    assert values['other', 'item:A']['max_actual_qty_per_day'] == 7
    assert values['other', 'item:A']['total_actual_qty'] == 8
    assert values['other', 'item:A']['active_days'] == 2


def test_daily_capacity_report_zero_execution_does_not_infer_capacity():
    value, = report([row(0, 0), row(0, 0), row(1, 0)], [node(capacity=0)])
    assert value['max_actual_qty_per_day'] == 0
    assert value['total_actual_qty'] == 0
    assert value['active_days'] == 0
    assert value['avg_actual_qty_per_active_day'] == 0
    assert value['industrial_nominal_capacity_qty_per_day'] == 0
    assert value['current_avg_utilization'] == ''
    assert value['current_max_utilization'] == ''
    assert report([]) == []


@pytest.mark.parametrize('day', [None, 0.5, 'not-a-day'])
def test_daily_capacity_report_rejects_unknown_or_fractional_days(day):
    with pytest.raises(ValueError, match='integer day'):
        report([row(day, 3)])
