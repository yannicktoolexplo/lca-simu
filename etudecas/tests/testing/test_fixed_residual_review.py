"""Independent replay-contract examples in memory; no files or native runs."""
from copy import deepcopy
import csv
import hashlib
import io

import pytest

from etudecas.testing.fixed_residual_review import audit_fixed_residual_replay
from etudecas.testing.independent_review import (
    Evidence, audit_scan3_closed_export, declared_scan3_requirements,
    scan3_reconciliation_mode,
)


def _budget(row, first, target):
    end = 5 if first == 0 else first + 7
    return dict(budget_id=f'plant:component:R{row}', node_id='plant', item_id='component',
        uom='UN', source_row=row, source_file='observations.xlsx',
        scan3_source_cell=f'Sheet!J{row}', source_week_marker='2025-01-05',
        first_day=first, end_day_exclusive=end, closing_day=end-1, covered_days=end-first,
        partial_week=first == 0, include_in_main_source_balance=first != 0,
        covered_scan3_qty=target, full_week_scan3_qty=target, raw_signed_scan3_qty=-target,
        coverage_status='documented_withdrawals')


def _profile(case, rows):
    fields = ['budget_id','requirement_id','node_id','item_id','uom','first_day',
              'end_day_exclusive','closing_day','covered_scan3_qty','residual_requested_qty',
              'residual_executed_qty','own_physical_qty']
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    case['profile_bytes'] = text.getvalue().encode('utf-8')
    case['declaration'].update(rows=len(rows),
        profile_sha256=hashlib.sha256(case['profile_bytes']).hexdigest())
    for row in case['weekly_rows']:
        row['replay_profile_sha256'] = case['declaration']['profile_sha256']


def _case(requested=(7,3)):
    budgets = [_budget(1,0,10),_budget(2,5,8)]
    declarations = dict(schema_version=1, profile_path='study/fixed.csv', profile_sha256='',
        rows=2, days=12, quantity_field='residual_requested_qty',
        knowledge='closing_day_after_own_production', status='conditional_scenario_not_industrial_observation')
    own = [dict(day=2,node_id='plant',item_id='component',event_type='production_consume',qty=4,uom='UN'),
           dict(day=6,node_id='plant',item_id='component',event_type='production_consume',qty=2,uom='UN')]
    profile, weekly, allocations, issues = [], [], [], []
    for index,(source,quantity,used) in enumerate(zip(budgets,requested,(4,2))):
        rid=f"external:scn:BASE:zz-reconciled-F3:{source['budget_id']}:D{source['closing_day']}"
        # Deliberately unrelated historic service/own columns must never be replayed.
        profile.append(dict(source,requirement_id=rid,residual_requested_qty=quantity,
            residual_executed_qty=777,own_physical_qty=888))
        executions = ([(4,min(5,quantity)),(6,max(0,quantity-5))] if index==0 else [(11,quantity)])
        executions = [(day,qty) for day,qty in executions if qty]
        on_close = sum(qty for day,qty in executions if day==source['closing_day'])
        for day,qty in executions:
            issues.append(dict(day=day,node_id='plant',item_id='component',uom='UN',qty=qty,
                event_type='external_component_consume',source_id=rid))
            allocations.append(dict(day=day,node_id='plant',item_id='component',uom='UN',qty=qty,
                requirement_id=rid))
        target = source['covered_scan3_qty']
        weekly.append(dict(source, requirement_id=rid,own_physical_qty=used,
            residual_requested_qty=quantity,own_exceeds_scan3_qty=max(0,used-target),
            residual_executed_qty=quantity,residual_executed_on_closing_day_qty=on_close,
            residual_backlog_initial_qty=0,residual_backlog_final_qty=0,
            residual_backlog_at_closing_qty=quantity-on_close,
            first_execution_day=min((d for d,_ in executions),default=''),
            last_execution_day=max((d for d,_ in executions),default=''),
            scan3_reconciliation_mode='fixed_residual_replay',scan3_target_qty=target,
            scan3_minus_own_qty=target-used,fixed_residual_source_qty=quantity,
            scan3_minus_own_and_fixed_residual_qty=target-used-quantity,
            replay_profile_source='study/fixed.csv',replay_profile_sha256='',
            replay_known_phase='after_own_production'))
    total = requested[0]+requested[1]
    cumulative = [dict(node_id='plant',item_id='component',closing_day=4,source_cells='Sheet!J1',
        covered_source_cumulative_qty=10,covered_own_cumulative_qty=4,
        prior_requested_including_backlog_qty=0,new_residual_qty=requested[0],total_requested_qty=requested[0],
        cumulative_unreversed_excess_qty=max(0,4+requested[0]-10),
        scan3_minus_own_and_fixed_residual_qty=10-4-requested[0],scan3_reconciliation_mode='fixed_residual_replay'),
        dict(node_id='plant',item_id='component',closing_day=11,source_cells='Sheet!J2',
        covered_source_cumulative_qty=18,covered_own_cumulative_qty=6,
        prior_requested_including_backlog_qty=requested[0],new_residual_qty=requested[1],total_requested_qty=total,
        cumulative_unreversed_excess_qty=max(0,6+total-18),
        scan3_minus_own_and_fixed_residual_qty=18-6-total,scan3_reconciliation_mode='fixed_residual_replay')]
    case = dict(contract=dict(schema_version=1,mode='scan3_residual_v1',cumulative_pairs=[['plant','component']]),
        budgets=budgets,events=sorted(own+issues,key=lambda r:int(r['day'])),weekly_rows=weekly,
        allocation_rows=allocations,cumulative_rows=cumulative,horizon=12,scenario='scn:BASE',
        declaration=declarations)
    _profile(case,profile)
    return case,profile


def _audit(case):
    evidence=Evidence()
    result=audit_fixed_residual_replay(**case,evidence=evidence,
        validate_declared=declared_scan3_requirements,audit_closed=audit_scan3_closed_export)
    return result,{name for name,row in evidence.checks.items() if row['failed']}


def test_fixed_requests_preserve_nonzero_signed_gap_and_ignore_old_service():
    case,_=_case(); before=deepcopy(case)
    result,failed=_audit(case)
    assert not failed and case==before
    assert [r['qty'] for r in result.values()]==[7,3]
    assert case['weekly_rows'][0]['scan3_minus_own_and_fixed_residual_qty']==-1
    assert case['cumulative_rows'][1]['scan3_minus_own_and_fixed_residual_qty']==2


def test_zero_request_is_an_explicit_required_closed_budget():
    case,_=_case(requested=(7,0))
    result,failed=_audit(case)
    assert not failed and len(result)==1
    assert len(case['weekly_rows'])==2


def test_absent_zero_request_cannot_be_inferred_from_missing_profile_row():
    case,profile=_case(requested=(7,0))
    _profile(case,profile[:1])
    _,failed=_audit(case)
    assert 'fixed_residual_exact_closed_budget_coverage' in failed


@pytest.mark.parametrize('mutation,expected',[
    ('duplicate','fixed_residual_profile_budget_identity'),
    ('identity','fixed_residual_profile_source_identity'),
    ('date','fixed_residual_profile_source_identity'),
    ('unit','fixed_residual_profile_source_identity'),
    ('fraction','fixed_residual_profile_integer_UN'),
    ('target','fixed_residual_profile_quantity'),
])
def test_profile_identity_dates_units_and_requests_are_not_self_justifying(mutation,expected):
    case,profile=_case()
    if mutation=='duplicate':profile.append(deepcopy(profile[0]))
    elif mutation=='identity':profile[0]['requirement_id']='unrelated'
    elif mutation=='date':profile[0]['closing_day']=3
    elif mutation=='unit':profile[0]['uom']='KG'
    elif mutation=='fraction':profile[0]['residual_requested_qty']=7.5
    else:profile[0]['covered_scan3_qty']=11
    _profile(case,profile)
    _,failed=_audit(case)
    assert expected in failed


@pytest.mark.parametrize('field,value',[
    ('quantity_field','residual_executed_qty'),('knowledge','known_from_initialisation'),
    ('status','observed'),('days',13),('schema_version',True),
])
def test_replay_declaration_rejects_changed_quantity_knowledge_or_status(field,value):
    case,_=_case();case['declaration'][field]=value
    _,failed=_audit(case)
    assert 'fixed_residual_profile_declaration' in failed


def test_profile_bytes_must_match_declared_sha_without_modifying_files():
    case,_=_case();case['profile_bytes']+=b'\n'
    _,failed=_audit(case)
    assert 'fixed_residual_profile_sha256' in failed


def test_published_request_cannot_be_recomputed_from_new_own_work():
    case,_=_case();case['weekly_rows'][0]['residual_requested_qty']=6
    _,failed=_audit(case)
    assert 'scan3_closed_weekly_residual_requested_qty' in failed


def test_signed_gap_must_not_be_forced_to_zero():
    case,_=_case();case['weekly_rows'][0]['scan3_minus_own_and_fixed_residual_qty']=0
    _,failed=_audit(case)
    assert 'fixed_residual_weekly_scan3_minus_own_and_fixed_residual_qty' in failed


def test_changed_own_work_is_reconstructed_instead_of_replayed():
    case,_=_case();case['events'][0]['qty']=5
    case['weekly_rows'][0].update(own_physical_qty=5,scan3_minus_own_qty=5,
        scan3_minus_own_and_fixed_residual_qty=-2)
    case['cumulative_rows'][0].update(covered_own_cumulative_qty=5,
        cumulative_unreversed_excess_qty=2,scan3_minus_own_and_fixed_residual_qty=-2)
    case['cumulative_rows'][1].update(covered_own_cumulative_qty=7,
        scan3_minus_own_and_fixed_residual_qty=1)
    result,failed=_audit(case)
    assert not failed and [r['qty'] for r in result.values()]==[7,3]


def test_residual_issue_cannot_precede_own_production_in_same_day():
    case,_=_case()
    own=case['events'].pop(0);own['day']=4
    case['events'].insert(1,own)
    _,failed=_audit(case)
    assert 'fixed_residual_physical_issue_after_own_production' in failed


def test_debt_and_allocations_are_actual_not_copied_from_profile():
    case,_=_case()
    case['allocation_rows'][0]['qty']+=1
    case['weekly_rows'][0]['residual_backlog_at_closing_qty']=0
    _,failed=_audit(case)
    assert 'scan3_allocation_physical_quantity' in failed
    assert 'scan3_closed_weekly_residual_backlog_at_closing_qty' in failed


def test_cumulative_prior_requests_and_signed_gap_are_preserved():
    case,_=_case()
    case['cumulative_rows'][1].update(prior_requested_including_backlog_qty=0,
        scan3_minus_own_and_fixed_residual_qty=0)
    _,failed=_audit(case)
    assert 'fixed_residual_cumulative_prior_requested_including_backlog_qty' in failed
    assert 'fixed_residual_cumulative_scan3_minus_own_and_fixed_residual_qty' in failed


def test_mode_is_explicit_and_cannot_mix_fixed_and_legacy_rows():
    case,_=_case();evidence=Evidence()
    manifest=dict(runtime=dict(scan3_reconciliation_mode='fixed_residual_replay'))
    assert scan3_reconciliation_mode(manifest,case['weekly_rows'],evidence,require_manifest=True)=='fixed_residual_replay'
    assert not any(row['failed'] for row in evidence.checks.values())
    case['weekly_rows'][0]['scan3_reconciliation_mode']='legacy_residual'
    assert scan3_reconciliation_mode(manifest,case['weekly_rows'],Evidence(),require_manifest=True) is None


@pytest.mark.parametrize('mode',['legacy_residual','audit_only',None])
def test_fixed_profile_cannot_masquerade_as_another_mode(mode):
    case,_=_case()
    runtime=dict(fixed_residual_replay=case['declaration'])
    if mode is not None:
        runtime['scan3_reconciliation_mode']=mode
    weekly=[] if mode is None else [dict(scan3_reconciliation_mode=mode)]
    evidence=Evidence()
    assert scan3_reconciliation_mode(dict(runtime=runtime),weekly,evidence) is None
    assert evidence.checks['scan3_execution_mode_declared_and_coherent']['failed']==1
