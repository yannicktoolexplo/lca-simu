"""In-memory arithmetic tests only; no generated files or filesystem fixtures."""
import pytest

from etudecas.simulation.experiments.empirical_delivery import reconcile_pair


def arguments():
    return dict(photos=[dict(day=35,qty=10.,row=2),dict(day=42,qty=100.,row=3)],
                plans={14:[[10,32,100.,7.,0.,0.],[11,39,0.,7.,0.,0.]]},
                item='039668',site='1810',unit='KG')


def test_interval_bounds_and_known_date_use_both_photo_and_week_width():
    accepted, rejected = reconcile_pair(**arguments())
    assert not rejected
    row = accepted[0]
    assert row['lower_days'] == -2  # earliest physical36 minus latest planned38
    assert row['upper_days'] == 10  # latest physical42 minus earliest planned32
    assert row['delta_days'] == 4
    assert row['known_day'] == 42
    assert row['plan_known_day'] == 14
    assert row['projected_I_in_photo_interval'] == 7
    assert row['quantity_residual'] == 3


def test_later_plan_and_future_J_do_not_supply_hindsight_receipts():
    kwargs = arguments()
    baseline = reconcile_pair(**kwargs)
    kwargs['plans'][28] = [[99,39,90.,0.,99999.,0.]]
    kwargs['plans'][14][0][4] = 500000.
    assert reconcile_pair(**kwargs) == baseline


def test_two_nearby_H_buckets_are_ambiguous_even_if_one_quantity_matches():
    kwargs = arguments()
    kwargs['plans'][14][1][2] = 200.
    accepted, rejected = reconcile_pair(**kwargs)
    assert not accepted
    assert rejected[0]['reason'] == 'no_isolated_projected_receipt'


def test_stock_rise_cannot_be_relabelled_as_larger_projected_receipt():
    kwargs = arguments()
    kwargs['photos'][1]['qty'] = 160.
    accepted, rejected = reconcile_pair(**kwargs)
    assert not accepted
    assert rejected[0]['reason'] == 'net_rise_incompatible_with_receipt_quantity'


def test_missing_I_bucket_is_unknown_instead_of_zero():
    kwargs = arguments()
    kwargs['plans'][14].pop()
    accepted, rejected = reconcile_pair(**kwargs)
    assert not accepted
    assert rejected[0]['reason'] == 'forecast_I_window_incomplete'


def test_one_projected_date_cannot_explain_two_stock_increases():
    kwargs = arguments()
    kwargs['photos'].append(dict(day=49,qty=190.,row=4))
    kwargs['plans'] = {21:[[10,32,0.,7.,0.,0.],[11,39,100.,7.,0.,0.],
                           [12,46,0.,7.,0.,0.]]}
    accepted, rejected = reconcile_pair(**kwargs)
    assert len(accepted) == 1
    assert accepted[0]['known_day'] == 42
    assert len(rejected) == 1
    assert rejected[0]['reason'] == 'already_matched_projected_date'
    kwargs['photos'].pop()
    assert reconcile_pair(**kwargs)[0] == accepted


def test_unexplained_net_consumption_is_not_an_accepted_delivery():
    kwargs = arguments()
    kwargs['photos'][1]['qty'] = 65.
    accepted, rejected = reconcile_pair(**kwargs)
    assert not accepted
    assert rejected[0]['reason'] == 'net_rise_plus_forecast_I_incompatible'


def test_duplicate_photos_raise_instead_of_inventing_a_receipt_interval():
    kwargs = arguments()
    kwargs['photos'].append(dict(kwargs['photos'][0]))
    with pytest.raises(ValueError, match='Duplicate stock photo'):
        reconcile_pair(**kwargs)
