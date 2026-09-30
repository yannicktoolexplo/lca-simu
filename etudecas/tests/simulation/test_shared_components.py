"""In-memory independent arithmetic oracles; no filesystem mutation fixtures."""
from etudecas.simulation.experiments.shared_components import estimate_first_plan


def network():
    return {'nodes': [
        {'id': 'M-1430', 'inventory': {'states': [{'item_id': 'item:100001', 'uom': 'UN'}]},
         'processes': [{'outputs': [{'item_id': 'item:900001'}], 'batch_size': 1,
                        'batch_size_unit': 'UN', 'inputs': [{'item_id': 'item:100001', 'ratio_per_batch': 1, 'ratio_unit': 'UN'}]}]},
        {'id': 'SDC-1450', 'inventory': {'states': [{'item_id': 'item:100002', 'uom': 'G'}]},
         'processes': [{'outputs': [{'item_id': 'item:100001'}], 'batch_size': 1,
                        'batch_size_unit': 'UN', 'inputs': [{'item_id': 'item:100002', 'ratio_per_batch': 10, 'ratio_unit': 'KG'}]}]},
    ]}


def records(a=(300, 300, 300), b=(6000, 6000, 6000), pf=(100, 100, 100)):
    result = []
    for item, division, kind, unit, values in [
        ('900001', '1920', 'PF', 'UN', pf), ('100001', '1430', 'MP', 'UN', a),
        ('100002', '1450', 'MP', 'KG', b)]:
        for index, qty in enumerate((0, *values)):
            result.append({'item': item, 'division': division, 'type': kind, 'unit': unit,
                           'qty': qty, 'day': 4 + 7 * index, 'row': len(result) + 2})
    return result


def test_upstream_residual_deducts_downstream_use_and_converts_units():
    rows, audit = estimate_first_plan(network(), 4, records())
    by_pair = {r['pair']: r for r in audit}
    assert by_pair['100001/1430']['scheduled_canonical_qty'] == 600
    # Own 300*10 plus external 600*10 are already represented upstream.
    assert by_pair['100002/1450']['own_bom_requirement'] == 3000
    assert by_pair['100002/1450']['already_induced_by_downstream'] == 6000
    assert by_pair['100002/1450']['scheduled_canonical_qty'] == 9000
    assert sum(r['qty'] for r in rows if r['item_id'] == 'item:100002') == 9_000_000
    assert all(r['uom'] == 'G' for r in rows if r['item_id'] == 'item:100002')


def test_timing_shift_alone_does_not_create_other_use():
    rows, audit = estimate_first_plan(network(), 4, records(a=(0, 0, 300), b=(0, 0, 3000)))
    assert rows == []
    assert all(r['status'] == 'not_selected' for r in audit)


def test_no_positive_upstream_residual_after_downstream_deduction():
    rows, audit = estimate_first_plan(network(), 4, records(b=(3000, 3000, 3000)))
    assert {r['item_id'] for r in rows} == {'item:100001'}
    assert next(r for r in audit if r['pair'] == '100002/1450')['source_to_represented_ratio'] == 1


def test_missing_pf_week_is_not_assumed_zero():
    source = [r for r in records() if not (r['type'] == 'PF' and r['day'] == 11)]
    rows, audit = estimate_first_plan(network(), 4, source)
    assert rows == []
    assert any(r['reason'] == 'finished_product_forecast_has_missing_weeks' for r in audit)


def test_estimated_physical_unit_quantities_are_integral_and_not_backdated():
    rows, _ = estimate_first_plan(network(), 4, records(a=(300.25, 300.25, 300.25)))
    assert all(r['qty'] == int(r['qty']) for r in rows if r['uom'] == 'UN')
    assert all(r['known_day'] == 4 and r['period_start_day'] >= 11 for r in rows)


def test_stock_values_and_safety_parameters_do_not_affect_residual_estimator():
    graph = network()
    expected = estimate_first_plan(graph, 4, records())
    for node in graph['nodes']:
        for state in node['inventory']['states']:
            state.update(initial=999999999, mrp_policy={'safety_stock_qty': 1234567, 'safety_time_days': 123})
    assert estimate_first_plan(graph, 4, records()) == expected
