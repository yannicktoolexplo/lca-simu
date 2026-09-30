import pytest

from POC2026.supply_geo_case.lca_comparison import build_lca_comparison
from POC2026.supply_geo_case.lightweight_seat import INDICATOR_METHODS


def model():
    return {'lightweight_seat': {'indicator_results': [
        {'indicator_id': key, 'baseline_production_raw': 20, 'baseline_use_raw': 100,
         'lightweight_production_raw': 10, 'lightweight_use_central_raw': 60,
         'normalization_factor_per_person_year': 10, 'ef30_weight_fraction': 1/16,
         'raw_unit': 'test'} for key in INDICATOR_METHODS]}}


def test_excel_score_uses_sixteen_weights_not_cabin_size():
    result = build_lca_comparison(model())
    totals = {(r['scenario_id'], r['phase']): r for r in result['totals']}
    assert totals['reference', 'production_use']['weighted_score_excel'] == pytest.approx(192)
    assert totals['lightweight', 'production_use']['weighted_score_excel'] == pytest.approx(112)
    assert totals['lightweight', 'use']['weighted_score_excel'] == pytest.approx(96)


@pytest.mark.parametrize('failure', ['missing_value', 'missing_category', 'duplicate', 'weights'])
def test_incomplete_score_not_zero(failure):
    data = model()
    rows = data['lightweight_seat']['indicator_results']
    if failure == 'missing_value':
        rows[0]['lightweight_use_central_raw'] = None
    elif failure == 'missing_category':
        rows.pop()
    elif failure == 'duplicate':
        rows.append(dict(rows[0]))
    else:
        rows[0]['ef30_weight_fraction'] = .9
    result = build_lca_comparison(data)
    total = next(r for r in result['totals'] if r['scenario_id']=='lightweight' and r['phase']=='production_use')
    assert total['weighted_score_excel'] is None
    assert not total['complete']
