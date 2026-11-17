"""Memory-only admission oracles; no native simulation or file mutation."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

import pytest

from etudecas.simulation.engine.dated_material_launch import assess_dated_material_launch


def _case(day, stock=2817066, receipt_day=128, **overrides):
    pair=("M","component")
    closed=tuple(d for d in range(day,day+366)
        if (date(2025,1,1)+timedelta(days=d)).weekday()>=5)
    values=dict(decision_day=day,batch_qty=107800,components=((pair,60.342),),
        available_by_pair={pair:stock},item_uoms={"component":"UN"},
        firm_receipts=[dict(identity="supplier-order",node_id="M",item_id="component",
            available_day=receipt_day,qty=30000000,known_day=89,origin="external_procurement")],
        other_requirements=[],capacity_context=dict(known_day=day,first_work_day=day,
            capacity_qty=7700,current_capacity_qty=7700,closed_days=closed,
            opening_work=(),frozen_work=(),active_remaining_qty=0))
    values.update(overrides)
    return values


@pytest.mark.parametrize("day,stock,receipt,known,allowed,finish,shortage",[
    (117,2817066,128,89,False,134,125),
    (120,2817066,128,89,True,139,None),
    (106,5604867,127,88,False,125,124),
    (111,5604867,127,88,True,128,None),
])
def test_continuous_projection_separates_existing_and_aligned_launches(day,stock,receipt,known,allowed,finish,shortage):
    args=_case(day,stock,receipt)
    args['firm_receipts'][0]['known_day']=known
    before=deepcopy(args)
    result=assess_dated_material_launch(**args)
    assert args==before
    assert result['applicable'] is True and result['allowed'] is allowed
    assert result['projected_finish_day']==finish
    if allowed:
        assert sum(row['qty'] for row in result['work_allocations'])==107800
        # Independent decimal total; no production helper used as the oracle.
        expected=int((Decimal('107800')*Decimal('60.342')).to_integral_value(rounding=ROUND_CEILING))
        assert expected==6504868
        assert sum(row['batch_issue_qty'] for row in result['component_projection'])==expected
    else:
        assert result['reason']=='dated_material_shortfall'
        assert result['first_shortage']['day']==shortage


def test_every_modeled_component_is_checked_not_only_bulk_material():
    args=_case(120)
    args['components']+=((('M','pack'),1),)
    args['available_by_pair']['M','pack']=107799
    args['item_uoms']['pack']='UN'
    result=assess_dated_material_launch(**args)
    assert result['reason']=='dated_material_shortfall'
    assert result['first_shortage']['item_id']=='pack'
    assert result['first_shortage']['day']==139


@pytest.mark.parametrize('start,finish',[(128,147),(127,146)])
def test_waiting_for_the_complete_kit_moves_completion_later(start,finish):
    # Receipt already usable at launch belongs in current stock, never twice.
    result=assess_dated_material_launch(**_case(start,stock=30000000,firm_receipts=[]))
    assert result['allowed'] is True and result['projected_finish_day']==finish


def test_current_stock_does_not_double_count_already_available_receipt():
    args=_case(120)
    args['firm_receipts'][0]['available_day']=120
    with pytest.raises(ValueError,match='Only future usable'):
        assess_dated_material_launch(**args)


@pytest.mark.parametrize('mutation',[{'known_day':121},{'origin':'estimated'}])
def test_unknown_future_or_revocable_receipt_cannot_fund_launch(mutation):
    args=_case(120)
    args['firm_receipts'][0].update(mutation)
    with pytest.raises(ValueError):assess_dated_material_launch(**args)


def test_known_external_debt_remains_due_and_can_refuse_admission():
    args=_case(120)
    args['other_requirements']=[dict(identity='prior-use',node_id='M',item_id='component',
        due_day=119,qty=3000000,known_day=120,basis='known_prior_backlog')]
    result=assess_dated_material_launch(**args)
    assert result['reason']=='dated_material_shortfall'
    assert result['first_shortage']['day']==120
    assert result['other_requirements']==args['other_requirements']


def test_own_frozen_reservation_is_excluded_once_but_other_order_stays_reserved():
    args=_case(120,own_order_id='self')
    args['capacity_context']['frozen_work']=(('self',120,107800),)
    assert assess_dated_material_launch(**args)['allowed'] is True
    args['capacity_context']['frozen_work']+=(('other',121,7700),)
    result=assess_dated_material_launch(**args)
    assert result['applicable'] is True and result['allowed'] is False
    assert result['reason']=='known_capacity_commitment_conflict'
    assert [row['order_id'] for row in result['capacity_reservations']]==['other']
    assert result['capacity_conflicts'][0]['day']==121


def test_duplicate_order_identity_is_rejected_even_for_own_order():
    args=_case(120,own_order_id='self')
    args['capacity_context']['frozen_work']=(('self',120,107800),('self',120,107800))
    with pytest.raises(ValueError,match='Duplicate'):assess_dated_material_launch(**args)


def test_unknown_capacity_is_an_audited_native_bypass_not_an_induced_shortage():
    result=assess_dated_material_launch(**_case(120,capacity_context=None))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['reason']=='unknown_finite_capacity'


def test_archived_transition_does_not_bypass_valid_projection():
    result=assess_dated_material_launch(**_case(120,nonprojectable_substitutions=[dict(start_day=1,end_day=119)]))
    assert result['applicable'] is True and result['allowed'] is True


def test_overlapping_unprojectable_transition_is_explicit_native_bypass():
    result=assess_dated_material_launch(**_case(120,nonprojectable_substitutions=[dict(start_day=128,end_day=140)]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['reason']=='dated_substitution_not_projectable'


def test_future_requirement_cannot_be_known_early():
    args=_case(120)
    args['other_requirements']=[dict(identity='future',node_id='M',item_id='component',
        due_day=125,qty=10,known_day=121,basis='unpublished')]
    with pytest.raises(ValueError,match='not known'):assess_dated_material_launch(**args)


@pytest.mark.parametrize('quantity',[1.5,-1,float('nan'),float('inf'),True])
def test_invalid_physical_stock_is_rejected(quantity):
    args=_case(120)
    args['available_by_pair']['M','component']=quantity
    with pytest.raises(ValueError):assess_dated_material_launch(**args)
