"""Memory-only independent examples for physical-launch priority v2."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.dated_material_launch import (
    DATED_MATERIAL_LAUNCH_POLICY, DATED_MATERIAL_PRIORITY_POLICY, assess_dated_material_launch,
)
from etudecas.simulation.engine.dated_launch_priority import frozen_material_requirement_links


def _order(identity, release=0, created=0, qty=8, item='PF'):
    return dict(order_id=identity,node_id='M',item_id=item,planned_release_day=release,
        created_day=created,known_day=created,qty=qty,state='frozen')


def _need(order, due, qty=None):
    identity='frozen_material:'+order['order_id']+':M|COMP'
    return dict(identity='other_frozen_order_components:'+identity,node_id='M',item_id='COMP',
        due_day=due,qty=order['qty'] if qty is None else qty,known_day=order['known_day'],
        basis='other_frozen_order_components',frozen_order_id=order['order_id'],
        frozen_output_node_id=order['node_id'],frozen_output_item_id=order['item_id'],
        frozen_component_requirement_id=identity,frozen_planned_release_day=order['planned_release_day'],
        frozen_created_day=order['created_day'])


def _case(orders=None, day=0, stock=12, rate=10, own='A', needs=None, **changes):
    orders=orders if orders is not None else [_order('A'),_order('B')]
    candidate=next(row for row in orders if row['order_id']==own)
    args=dict(decision_day=day,batch_qty=candidate['qty'],components=((('M','COMP'),1),),
        available_by_pair={('M','COMP'):stock},item_uoms={'COMP':'UN'},firm_receipts=[],
        other_requirements=needs if needs is not None else [_need(row,max(day,row['planned_release_day']))
            for row in orders if row['order_id']!=own],
        capacity_context=dict(known_day=day,first_work_day=day,capacity_qty=rate,
            current_capacity_qty=rate,closed_days=(),opening_work=(),active_remaining_qty=0,
            frozen_work=tuple((row['order_id'],max(day,row['planned_release_day']),row['qty'])
                for row in orders if row['item_id']=='PF')),
        own_order_id=own,output_pair=('M','PF'),frozen_orders=orders,policy=DATED_MATERIAL_PRIORITY_POLICY)
    args.update(changes)
    return args


def test_eight_plus_eight_at_capacity_ten_uses_two_launch_days_and_keeps_debt():
    args=_case();before=deepcopy(args)
    result=assess_dated_material_launch(**args)
    assert args==before
    assert result['allowed'] is True and result['projected_finish_day']==0
    successor=result['capacity_reservations'][0]
    assert successor['order_id']=='B' and successor['allocations']==[dict(day=1,qty=8)]
    assert successor['projected_launch_delay_days']==1
    assert result['priority_projection']['candidate_excluded_count']==1
    assert result['other_requirements'][0]['qty']==8
    assert result['other_requirements'][0]['due_day']==1
    debt=result['successor_material_obligations'][0]
    assert debt['qty']==8 and debt['usable_before_qty']==4 and debt['unfunded_qty']==4
    assert debt['projected_balance_after_qty']==-4


def test_v1_remains_blocked_on_the_same_eight_plus_eight_counterexample():
    args=_case(policy=DATED_MATERIAL_LAUNCH_POLICY)
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is False and result['reason']=='known_capacity_commitment_conflict'
    assert result['capacity_reservations'][0]['allocations']==[dict(day=0,qty=8)]
    assert 'priority_projection' not in result


def test_overdue_original_release_precedes_lexically_earlier_identifier():
    orders=[_order('Z',release=5),_order('A',release=10)]
    result=assess_dated_material_launch(**_case(orders,day=20,own='Z'))
    assert result['allowed'] is True
    assert result['priority_projection']['priority_orders'][0]['priority_key']==[5,0,'Z']
    assert result['capacity_reservations'][0]['order_id']=='A'
    assert result['capacity_reservations'][0]['planned_release_day']==10
    assert result['capacity_reservations'][0]['projected_start_day']==21


def test_original_creation_breaks_release_tie_before_identifier():
    orders=[_order('A',release=5,created=1),_order('Z',release=5,created=0)]
    result=assess_dated_material_launch(**_case(orders,day=20,own='Z'))
    assert result['allowed'] is True
    assert result['priority_projection']['priority_orders'][0]['priority_key']==[5,0,'Z']
    assert result['capacity_reservations'][0]['created_day']==1


def test_earlier_order_cannot_be_overtaken_even_if_capacity_has_room():
    orders=[_order('A',qty=2),_order('B',qty=8)]
    result=assess_dated_material_launch(**_case(orders,stock=20,own='B'))
    assert result['allowed'] is False
    assert result['priority_projection']['prior_launches_today']==['A']
    assert result['capacity_reservations'][0]['qty']==2
    assert result['other_requirements'][0]['due_day']==0


def test_future_initial_commitment_refuses_continuous_candidate_without_pause():
    args=_case(stock=100,rate=4)
    args['capacity_context']['opening_work']=(('observed-initial',1,4),)
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is False and result['reason']=='known_capacity_commitment_conflict'
    assert result['work_allocations']==[dict(day=0,qty=4),dict(day=1,qty=4)]
    assert result['capacity_reservations'][0]['order_id']=='observed-initial'
    assert result['capacity_reservations'][0]['qty']==4


def test_already_active_campaign_still_prevents_new_candidate():
    args=_case();args['capacity_context']['active_remaining_qty']=3
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is False and result['reason']=='existing_active_campaign'


def test_other_output_material_need_is_not_postponed_with_same_output_successor():
    orders=[_order('A'),_order('B'),_order('OTHER',qty=5,item='PF2')]
    result=assess_dated_material_launch(**_case(orders,stock=12))
    assert result['allowed'] is False and result['reason']=='dated_material_shortfall'
    other=next(row for row in result['other_requirements'] if row.get('frozen_order_id')=='OTHER')
    assert other['due_day']==0 and other['qty']==5 and 'retiming_basis' not in other


def test_external_backlog_keeps_identity_date_and_quantity():
    debt=dict(identity='external-debt',node_id='M',item_id='COMP',due_day=0,qty=5,
        known_day=0,basis='prior_external_backlog')
    args=_case(day=2,needs=[debt,_need(_order('B'),2)])
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is False and result['reason']=='dated_material_shortfall'
    assert result['other_requirements'][0]==debt


def test_initial_material_need_is_not_postponed():
    need=dict(identity='initial-components',node_id='M',item_id='COMP',due_day=0,qty=5,
        known_day=0,basis='initial_order_remaining_components')
    result=assess_dated_material_launch(**_case(needs=[need,_need(_order('B'),0)]))
    assert result['allowed'] is False and result['other_requirements'][0]==need


def test_colon_order_ids_and_prefixes_have_exact_structured_links():
    orders=[_order('A'),_order('A:B')]
    links=frozen_material_requirement_links(orders,{('M','PF'):((('M','COMP'),1),)})
    assert links[(('M','COMP'),'frozen_material:A:B:M|COMP')]['frozen_order_id']=='A:B'
    assert len(links)==2
    result=assess_dated_material_launch(**_case(orders))
    assert result['allowed'] is True
    assert result['other_requirements'][0]['frozen_order_id']=='A:B'
    assert result['other_requirements'][0]['qty']==8


def test_missing_candidate_metadata_is_an_explicit_refusal():
    args=_case();args['frozen_orders']=[_order('B')]
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is False and result['reason']=='missing_candidate_priority_metadata'
    assert result['other_requirements'][0]['qty']==8


def test_inconsistent_candidate_quantity_is_an_explicit_refusal():
    args=_case();args['frozen_orders'][0]['qty']=9
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is False and result['reason']=='inconsistent_candidate_priority_metadata'


def test_missing_other_reservation_is_rejected_not_silently_erased():
    args=_case();args['capacity_context']['frozen_work']=(('A',0,8),)
    with pytest.raises(ValueError,match='reconcile every'):
        assess_dated_material_launch(**args)


def test_duplicate_own_reservation_cannot_be_excluded_twice():
    args=_case();args['capacity_context']['frozen_work']+=(('A',0,8),)
    with pytest.raises(ValueError,match='Duplicate'):
        assess_dated_material_launch(**args)


def test_wrong_structured_material_link_is_rejected():
    args=_case();args['other_requirements'][0]['frozen_output_item_id']='PF2'
    with pytest.raises(ValueError,match='disagree'):
        assess_dated_material_launch(**args)


def test_own_component_requirement_is_not_double_counted():
    args=_case();args['other_requirements'].append(_need(_order('A'),0))
    with pytest.raises(ValueError,match='excluded exactly once'):
        assess_dated_material_launch(**args)


def test_j54_seven_orders_preserve_230400_units_and_use_seven_launch_days():
    # Exact capacities/quantities/identities from the independently extracted
    # J54 example; only component stock is a declared unconstrained witness.
    orders=[_order('FROZEN|M-1810|item:268091|'+str(i),release=54,qty=57600 if i==31 else 28800)
        for i in (26,31,35,41,42,44,54)]
    result=assess_dated_material_launch(**_case(orders,day=54,own=orders[0]['order_id'],
        stock=500000,rate=203550))
    assert result['allowed'] is True
    reservations=result['capacity_reservations']
    assert [row['projected_start_day'] for row in reservations]==list(range(55,61))
    assert sum(row['qty'] for row in reservations)==201600
    assert result['projected_completed_qty']+sum(row['qty'] for row in reservations)==230400
    assert all(row['planned_release_day']==54 for row in reservations)
    assert sum(row['qty'] for row in result['other_requirements'])==201600
    assert [row['due_day'] for row in result['other_requirements']]==list(range(55,61))


def test_calendar_and_no_same_day_residual_launch_are_both_respected():
    args=_case(stock=100);args['capacity_context']['closed_days']=(1,2)
    result=assess_dated_material_launch(**args)
    assert result['allowed'] is True
    assert result['capacity_reservations'][0]['allocations']==[dict(day=3,qty=8)]
    assert result['other_requirements'][0]['due_day']==3


def test_multiday_candidate_cannot_share_final_day_with_new_successor():
    orders=[_order('A',qty=15),_order('B',qty=8)]
    result=assess_dated_material_launch(**_case(orders,stock=100))
    assert result['allowed'] is True
    assert result['work_allocations']==[dict(day=0,qty=10),dict(day=1,qty=5)]
    assert result['capacity_reservations'][0]['allocations']==[dict(day=2,qty=8)]
    assert result['other_requirements'][0]['due_day']==2


def test_substitution_bypass_is_unchanged_and_does_not_invent_priority():
    args=_case(nonprojectable_substitutions=[dict(start_day=0,end_day=9)])
    result=assess_dated_material_launch(**args)
    assert result['applicable'] is False and result['allowed'] is None
    assert result['reason']=='dated_substitution_not_projectable'


def test_future_known_day_in_order_metadata_is_rejected():
    args=_case();args['frozen_orders'][1]['known_day']=1
    with pytest.raises(ValueError,match='future frozen'):
        assess_dated_material_launch(**args)
