"""Memory-only independent arithmetic and timing examples for fixed requests."""
from copy import deepcopy
from decimal import Decimal

import pytest

from etudecas.simulation.current_reference import runtime_observed_type, validate_scan3_mode
from etudecas.simulation.engine.programme_opening_coverage import reveal_current_component_requirements
from etudecas.simulation.reference_mrp.historical_adapter import WeeklyTracker, tracker_for, f3_module
from etudecas.simulation.reference_mrp.fixed_residual_replay import (
    FixedResidualProfile, fixed_tracker_for, DEFERRED_REASON,
)


def _budget(identity='B', day=1, target=10, item='item:C', unit='UN', first=0):
    return dict(budget_id=identity,node_id='M',item_id=item,uom=unit,
        first_day=first,end_day_exclusive=day+1,closing_day=day,covered_scan3_qty=target,
        source_file='industrial.xlsx',scan3_source_cell='J1',source_week_marker='2025-01-05')


def _row(source, qty=6, **changes):
    row=dict(source,requirement_id=f"external:scn:BASE:zz-reconciled-F3:{source['budget_id']}:D{source['closing_day']}",
        residual_requested_qty=qty,residual_executed_qty=999,residual_backlog_final_qty=999,
        own_physical_qty=999)
    row.update(changes)
    return row


def _profile(budgets, rows, days=2):
    return FixedResidualProfile(rows,budgets,days=days,
        profile_path='scenario/fixed.csv',profile_sha256='0'*64)


def _tracker(qty=6, own=4, *, cumulative=False):
    source=_budget()
    profile=_profile([source],[_row(source,qty)])
    result=fixed_tracker_for(WeeklyTracker,[source],profile,[('M','item:C')] if cumulative else [])
    if own:
        result.own_withdrawal(day=1,node_id='M',item_id='item:C',qty=own,event_type='production_consume')
    return result


def test_requested_quantity_is_fixed_when_own_production_changes():
    first,second=_tracker(own=4),_tracker(own=9)
    a,b=first.close(1,{}),second.close(1,{})
    assert a[('M','item:C')][0].qty == b[('M','item:C')][0].qty == 6
    assert first.published['B']['scan3_minus_own_and_fixed_residual_qty']==0
    assert second.published['B']['scan3_minus_own_and_fixed_residual_qty']==-5


def test_executed_quantities_and_debts_from_profile_are_never_replayed():
    tracker=_tracker()
    tracker.close(1,{})
    row=tracker.published['B']
    assert row['own_physical_qty']==4 and row['residual_executed_qty']==0
    assert row['residual_backlog_initial_qty']==0 and row['residual_backlog_final_qty']==6
    tracker.served(1,row['requirement_id'],2)
    assert row['residual_executed_qty']==2 and row['residual_backlog_final_qty']==4
    assert tracker.allocations[0]['qty']==2


def test_fixed_zero_is_published_without_inventing_requirement_or_debt():
    tracker=_tracker(qty=0)
    assert tracker.close(1,{})=={}
    assert tracker.published['B']['residual_requested_qty']==0
    assert tracker.published['B']['residual_backlog_final_qty']==0
    assert tracker.published['B']['requirement_id'] in tracker.provenance


def test_missing_explicit_zero_budget_is_rejected():
    with pytest.raises(ValueError,match='explicit fixed request'):
        _profile([_budget()],[])


def test_duplicate_or_unknown_budget_is_rejected():
    source=_budget(); row=_row(source)
    with pytest.raises(ValueError,match='duplicate'):_profile([source],[row,row])
    with pytest.raises(ValueError,match='Unknown'):_profile([source],[dict(row,budget_id='OTHER')])


@pytest.mark.parametrize('mutation',[
    {'node_id':'M2'},{'item_id':'item:D'},{'uom':'KG'},
    {'first_day':1},{'end_day_exclusive':3},{'closing_day':0},
    {'requirement_id':'different'},{'covered_scan3_qty':11},
])
def test_profile_identity_unit_dates_and_source_target_must_match(mutation):
    source=_budget()
    with pytest.raises(ValueError):_profile([source],[_row(source,**mutation)])


@pytest.mark.parametrize('quantity',[1.5,-1,float('nan'),float('inf'),True])
def test_invalid_physical_unit_request_is_rejected(quantity):
    source=_budget()
    with pytest.raises(ValueError):_profile([source],[_row(source,quantity)])


def test_fractional_mass_is_retained_without_whole_unit_rounding():
    source=_budget(unit='KG',target=2.5)
    profile=_profile([source],[_row(source,1.25)])
    tracker=fixed_tracker_for(WeeklyTracker,[source],profile)
    tracker.own_withdrawal(day=1,node_id='M',item_id='item:C',qty=0.75,event_type='production_consume')
    assert tracker.close(1,{})[('M','item:C')][0].qty==1.25
    assert tracker.published['B']['scan3_minus_own_and_fixed_residual_qty']==0.5


def test_publication_occurs_only_on_closing_day_and_only_once():
    tracker=_tracker()
    assert tracker.close(0,{})=={} and tracker.published=={}
    assert tracker.close(1,{})[('M','item:C')][0].due_day==1
    with pytest.raises(ValueError,match='only once'):tracker.close(1,{})
    with pytest.raises(ValueError,match='horizon'):tracker.close(2,{})


class _Observed:
    def preview_due(self,day,estimated):return dict(estimated),()
    def merge_due(self,day,estimated):return dict(estimated)
    def provenance(self,identity,calendar):return {}


class _Calendar:
    def __init__(self):self.days=[]
    def due(self,day):self.days.append(day);return {}


def test_preview_keeps_zero_marker_but_never_reads_fixed_quantities():
    tracker=_tracker(qty=0)
    class ForbiddenRead(dict):
        def __getitem__(self,key):raise AssertionError('Fixed quantity read before closing')
    tracker.profile.values=ForbiddenRead(tracker.profile.values)
    runtime=runtime_observed_type(_Observed,tracker,None,2)()
    calendar=_Calendar()
    snapshot=reveal_current_component_requirements(calendar,runtime,decision_day=1)
    assert snapshot.known_due=={} and tracker.published=={}
    assert len(snapshot.deferred_closures)==1 and calendar.days==[1]
    marker=snapshot.deferred_closures[0]
    assert marker['reason']==DEFERRED_REASON and marker['closing_day']==1
    assert not any('qty' in key or 'quantity' in key for key in marker)
    assert snapshot.unresolved_for([('M','item:C')])==(marker,)


def test_preview_does_not_expose_future_closing_and_merge_sees_today_work():
    tracker=_tracker(own=0)
    runtime=runtime_observed_type(_Observed,tracker,None,2)()
    assert runtime.preview_due(0,{})==({},())
    assert runtime.preview_due(1,{})[0]=={}
    tracker.own_withdrawal(day=1,node_id='M',item_id='item:C',qty=9,event_type='production_consume')
    assert runtime.merge_due(1,{})[('M','item:C')][0].qty==6
    assert tracker.published['B']['own_physical_qty']==9


def test_fixed_provenance_is_conditional_and_not_industrial_observation():
    tracker=_tracker()
    runtime=runtime_observed_type(_Observed,tracker,None,2)()
    runtime.merge_due(1,{})
    provenance=runtime.provenance(tracker.published['B']['requirement_id'],None)
    assert provenance['physical_demand_source']=='conditional_fixed_residual_from_retained_control'
    assert provenance['known_day']==1 and provenance['source_file']=='scenario/fixed.csv'
    assert provenance['source_cells']=='budget_id=B'
    assert 'conditional_scenario_not_industrial_observation' in provenance['estimation_basis']


def test_cumulative_target_is_audit_only_and_never_changes_fixed_requests():
    sources=[_budget('A',day=0,target=10),_budget('B',day=1,target=10,first=1)]
    profile=_profile(sources,[_row(sources[0],6),_row(sources[1],7)])
    tracker=fixed_tracker_for(WeeklyTracker,sources,profile,[('M','item:C')])
    tracker.own_withdrawal(day=0,node_id='M',item_id='item:C',qty=9,event_type='production_consume')
    assert tracker.close(0,{})[('M','item:C')][0].qty==6
    tracker.own_withdrawal(day=1,node_id='M',item_id='item:C',qty=8,event_type='production_consume')
    assert tracker.close(1,{})[('M','item:C')][0].qty==7
    audit=tracker.cumulative_audit[-1]
    assert audit['covered_source_cumulative_qty']==20 and audit['covered_own_cumulative_qty']==17
    assert audit['prior_requested_including_backlog_qty']==6 and audit['total_requested_qty']==13
    assert audit['scan3_minus_own_and_fixed_residual_qty']==-10
    assert audit['cumulative_unreversed_excess_qty']==10


def test_fixed_profile_does_not_modify_existing_known_requirements():
    from etudecas.simulation.engine.mrp_planning import Requirement
    tracker=_tracker()
    existing={('M','item:C'):(Requirement('direct',1,2),),('M','item:D'):(Requirement('other',1,5),)}
    before=deepcopy(existing)
    result=tracker.close(1,existing)
    assert existing==before and result[('M','item:C')][0]==before[('M','item:C')][0]
    assert result[('M','item:D')]==before[('M','item:D')]
    assert sum(r.qty for r in result[('M','item:C')])==8


def test_normal_and_cumulative_publication_order_matches_legacy():
    sources=[_budget('CUM',item='item:C'),_budget('NORMAL',item='item:N')]
    profile=_profile(sources,[_row(r) for r in sources])
    tracker=fixed_tracker_for(WeeklyTracker,sources,profile,[('M','item:C')])
    result=tracker.close(1,{})
    assert list(result)==[('M','item:N'),('M','item:C')]
    assert list(tracker.published)==['NORMAL','CUM']


def test_profile_requires_exact_horizon_including_no_extra_future_budget():
    sources=[_budget('NOW'),_budget('FUTURE',day=3,first=2)]
    profile=_profile(sources,[_row(sources[0])])
    assert set(profile.values)=={'NOW'}
    with pytest.raises(ValueError,match='Unknown'):_profile(sources,[_row(r) for r in sources])
    with pytest.raises(ValueError,match='362'):_profile(sources,[],days=363)
    with pytest.raises(ValueError,match='historical window'):validate_scan3_mode('fixed_residual_replay',363)


def test_legacy_and_audit_only_keep_their_existing_residual_contracts():
    source=_budget()
    legacy=tracker_for(f3_module(),[source],mode='legacy_residual')
    audit=tracker_for(f3_module(),[source],mode='audit_only')
    for tracker in (legacy,audit):
        tracker.own_withdrawal(day=1,node_id='M',item_id='item:C',qty=4,event_type='production_consume')
    assert legacy.close(1,{})[('M','item:C')][0].qty==6
    assert audit.close(1,{})=={} and audit.published['B']['residual_requested_qty']==0
    assert audit.published['B']['scan3_minus_own_qty']==6
