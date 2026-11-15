"""Memory-only independent balances for initial orders and new programmes."""
from copy import deepcopy
from decimal import Decimal

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, OrderProposal, Requirement, WeeklyProductionProgramme,
)
from etudecas.simulation.engine.programme_opening_coverage import (
    OPENING_COVERAGE_POLICY, reconcile_opening_programme, reserve_known_component_backlogs,
    reveal_current_component_requirements, reserve_current_component_requirements,
)

PAIR, A, B = ('F','PF'), ('F','A'), ('F','B')


def context(*, capacity=50, opening=(), current=None):
    return dict(capacity_qty=capacity,known_day=4,first_work_day=5,
        current_capacity_qty=capacity if current is None else current,
        closed_days=(),active_remaining_qty=0,opening_work=opening,intraday=True,
        supply_calendar=dict(physical_lead_days=0,receipt_days=0,origin_date='2025-01-01'))


def book(*, optin=True, budget=500):
    payload=dict(schema_version=1,mode='current_week_authorized_lot_multiday_v1',
        max_promotions_per_process=52,current_bucket_policy='latest_known_including_current',
        assumption='Synthetic arithmetic, not an industrial identified order',
        series=[dict(node_id='F',output_item_id='PF',versions=[dict(known_day=4,
            period_start_day=4,period_end_day_exclusive=11,component_budgets=[
                dict(item_id=c[1],qty=budget,uom='UN',source_file='synthetic',source_cells=c[1])
                for c in (A,B)])])])
    if optin:payload['opening_commitment_policy']=OPENING_COVERAGE_POLICY
    return WeeklyProductionProgramme(payload,bom_by_pair={PAIR:[(A,1),(B,1)]},
        pair_uoms={PAIR:'UN',A:'UN',B:'UN'})


def order(*, identity='initial', qty=100, physical=7, available=8, a=None):
    return (identity,PAIR,physical,available,qty,((A[0],A[1],qty if a is None else a),(B[0],B[1],qty)))


def selection(*, qty=100, initial=None, available=500, capacity=50, committed=None,
              consumed=None, optin=True, budget=500, future_receipts=(), initials=None):
    orders=tuple(initials) if initials is not None else (() if initial is None else (initial,))
    proposals=(OrderProposal('net',20,20,20,qty),)
    firms=tuple(FirmReceipt(r[0],r[3],r[4],'confirmed') for r in orders)
    coverage=reconcile_opening_programme(pair=PAIR,decision_day=5,orders=orders,
        firm_receipts=firms,proposals=proposals,component_firm_receipts=future_receipts)
    resource=context(capacity=capacity,opening=tuple((r[0],r[2],r[4]) for r in orders))
    placements=engine.programme_multiday_placements(proposals,decision_day=5,context=resource,
        allow_due=True,opening_commitment_policy=OPENING_COVERAGE_POLICY if optin else None)
    args=dict(pair=PAIR,decision_day=5,proposals=proposals,calendar=[(5,5)],consumed=consumed or {},
        committed=committed or {},available={A:available,B:available},capacity_qty=capacity,
        multiday_placements=placements,opening_pack_pending_qty=sum(r[4] for r in orders),
        opening_coverage=coverage,selection_audit=[])
    return book(optin=optin,budget=budget),args,resource


def test_net_need_is_250_less20stock_less100initial_not250():
    resource=context(capacity=500,opening=(('initial',7,100),))
    inputs=dict(decision_day=5,snapshot_day=4,requirements=[Requirement('need',20,250)],
        available_qty=20,firm_receipts=[FirmReceipt('initial',8,100,'confirmed')],
        lead_days=0,lot_sizing=LotSizing(integer=True),manufacturing_capacity=resource)
    _,plan=engine.dated_production_release(**inputs)
    assert sum(p.qty for p in plan.proposals)==130
    proof=reconcile_opening_programme(pair=PAIR,decision_day=5,orders=(order(),),
        firm_receipts=inputs['firm_receipts'],proposals=plan.proposals)
    args=dict(pair=PAIR,decision_day=5,proposals=plan.proposals,calendar=[(5,5)],
        consumed={},committed={},available={A:230,B:230},capacity_qty=500,opening_pack_pending_qty=100,
        opening_coverage=proof,multiday_placements=engine.programme_multiday_placements(plan.proposals,
            decision_day=5,context=resource,allow_due=True,opening_commitment_policy=OPENING_COVERAGE_POLICY))
    saved=deepcopy(inputs)
    candidate=book().select(**args)
    assert candidate['qty']==130
    checked=engine.programme_replacement_check(candidate,plan,**inputs)
    assert checked['before_proposed_qty']==checked['after_with_programme_qty']==130
    assert checked['remaining_proposals']==[] and inputs==saved


@pytest.mark.parametrize('available_day',[8,30])
def test_initial_firm_even_late_covers_quantity_without_duplicate_new_lot(available_day):
    _,plan=engine.dated_production_release(decision_day=5,snapshot_day=4,
        requirements=[Requirement('covered',20,100)],available_qty=0,
        firm_receipts=[FirmReceipt('initial',available_day,100,'confirmed')],
        lead_days=0,lot_sizing=LotSizing(integer=True))
    assert not plan.proposals
    if available_day==30:assert plan.late_qty==100


def test_partial_initial_held40_plus_remaining60_credits100_once():
    initial=order(qty=60)
    firms=[FirmReceipt('initial',8,60,'confirmed'),FirmReceipt('initial;pack_fragment=1',7,40,'held')]
    _,plan=engine.dated_production_release(decision_day=5,snapshot_day=4,
        requirements=[Requirement('need',20,130)],available_qty=0,firm_receipts=firms,
        lead_days=0,lot_sizing=LotSizing(integer=True))
    assert sum(p.qty for p in plan.proposals)==30
    proof=reconcile_opening_programme(pair=PAIR,decision_day=5,orders=(initial,),firm_receipts=firms,proposals=plan.proposals)
    assert proof.valid and proof.pending_qty==60
    assert proof.component_reservations(8)=={A:60,B:60}


@pytest.mark.parametrize('fault',['missing','quantity','date','duplicate_firm','duplicate_initial'])
def test_unknown_or_duplicate_initial_credit_fails_closed(fault):
    orders=[order()];firms=[FirmReceipt('initial',8,100,'confirmed')]
    if fault=='missing':firms=[]
    elif fault=='quantity':firms=[FirmReceipt('initial',8,101,'confirmed')]
    elif fault=='date':firms=[FirmReceipt('initial',9,100,'confirmed')]
    elif fault=='duplicate_firm':firms*=2
    else:orders*=2
    result=reconcile_opening_programme(pair=PAIR,decision_day=5,orders=orders,firm_receipts=firms,proposals=[])
    assert not result.valid


def test_future_initial_covered_by_known_receipt_does_not_block_start():
    receipts=tuple(('known-'+c[1],c,14,100,'external_procurement',5) for c in (A,B))
    policy,args,resource=selection(initial=order(physical=15,available=16),available=100,capacity=100,
        future_receipts=receipts)
    candidate=policy.select(**args)
    assert candidate['qty']==100 and candidate['work_allocations']==((5,100),)
    assert all(r['initial_reserved_qty']==0 for r in candidate['material_availability_after_reservations'])
    assert resource['opening_work']==(('initial',15,100),)


def test_initial_work_subtracted_only_on_its_dated_machine_slots():
    resource=context(capacity=50,opening=(('initial',6,50),))
    reservation=[]
    rows=engine.programme_multiday_placements((OrderProposal('net',20,20,20,100),),
        decision_day=5,context=resource,opening_commitment_policy=OPENING_COVERAGE_POLICY,
        reservation_audit=reservation)
    assert rows['net']['allocations']==[(5,50),(7,50)]
    assert reservation[0]['work_allocations']==[(6,50)]
    assert rows['net']['physical_finish_day']==7


def test_initial_components_before_finish_and_other_campaign_are_not_stolen():
    policy,args,_=selection(qty=70,initial=order(qty=30,physical=6,available=7),
        available=100,capacity=50,committed={A:20,B:20})
    assert policy.select(**args) is None
    assert args['selection_audit'][0]['reason']=='material_reserved_or_missing'
    assert args['selection_audit'][0]['components'][0]['free_after_reservations_qty']==50


def test_cross_week_initial_material_reserved_through_campaign_finish():
    policy,args,_=selection(qty=100,initial=order(qty=30,physical=12,available=13),
        available=100,capacity=10)
    assert args['multiday_placements']['net']['physical_finish_day']>12
    assert policy.select(**args) is None
    assert args['selection_audit'][0]['components'][0]['initial_reserved_qty']==30


def test_source_budget_deducts_initial_current_week_once_but_not_all_future():
    policy,args,_=selection(qty=100,initial=order(qty=50,physical=8,available=9),
        available=150,capacity=100,budget=160,consumed={A:10,B:10})
    candidate=policy.select(**args)
    assert candidate['qty']==100
    assert all((r['consumed_qty'],r['committed_qty'],r['allocated_qty'],r['residual_qty'])==(10,50,100,0)
               for r in candidate['source_budgets'])
    args['consumed'][A]=11
    assert policy.select(**args) is None


def test_legacy_global_guard_still_applies_without_explicit_optin():
    policy,args,_=selection(initial=order(physical=15,available=16),optin=False)
    assert args['multiday_placements']=={} and policy.select(**args) is None


@pytest.mark.parametrize('fault',['missing_proof','wrong_pending','changed_proposal','changed_day','changed_proposal_dates'])
def test_selection_requires_exact_current_coverage_context(fault):
    policy,args,_=selection(initial=order(physical=15,available=16))
    if fault=='missing_proof':args['opening_coverage']=None
    elif fault=='wrong_pending':args['opening_pack_pending_qty']=99
    elif fault=='changed_proposal':args['proposals']=(OrderProposal('changed',20,20,20,100),)
    elif fault=='changed_day':args['decision_day']=6
    else:args['proposals']=(OrderProposal('net',21,21,21,100),)
    assert policy.select(**args) is None


def test_programme_remainders_use_only_unconsumed_components_and_unique_residual():
    initial=object.__new__(engine.OpeningPackOrders)
    initial.origin_date='2025-01-01';initial.closed_days_by_pair={}
    initial.components={PAIR:({'pair':A,'ratio':Decimal('1'),'uom':'UN'},)}
    initial.rows={'source83':dict(pair=PAIR,source_marker='source83',target_qty=100,completed_qty=40,
        physical_delivery_day=3,arrival_day=4,source_workdays=1,consumed={A:Decimal(40)})}
    rows=initial.programme_remainders(5)
    assert rows==(('source83',PAIR,6,7,60,(('F','A',60.0),)),)
    needs,firms=initial.planning(5)
    assert firms[PAIR][0].qty==60 and needs[A][0].qty==60


@pytest.mark.parametrize('receipt_day,accepted',[(None,False),(14,True),(15,True),(16,False),(5,False)])
def test_future_initial_prefix_protects_stock_until_usable_receipt(receipt_day,accepted):
    receipts=() if receipt_day is None else tuple(('R-'+c[1],c,receipt_day,100,'held',5) for c in (A,B))
    policy,args,_=selection(initial=order(physical=15,available=16),available=100,capacity=100,
        future_receipts=receipts)
    candidate=policy.select(**args)
    assert (candidate is not None)==accepted
    reserve,projection,excluded=args['opening_coverage'].future_material_protection()
    assert reserve=={A:0 if accepted else 100,B:0 if accepted else 100}
    if receipt_day==5:assert all(r['reason']=='already_due_not_a_second_future_credit' for r in excluded)


def test_dated_prefix_reserves70_and_leaves30_not_the_final_net70_only():
    initial=(order(identity='early',qty=70,physical=8,available=9),
             order(identity='later',qty=60,physical=15,available=16))
    receipts=tuple(('R-'+c[1],c,10,60,'external_procurement_supplier_delivery',5) for c in (A,B))
    policy,args,_=selection(qty=30,initials=initial,available=100,capacity=100,future_receipts=receipts)
    candidate=policy.select(**args)
    assert candidate['qty']==30
    reserve,rows,_=args['opening_coverage'].future_material_protection()
    assert reserve=={A:70,B:70}
    assert [(r['day'],r['uncovered_prefix_qty']) for r in rows[0]['dates']]==[(8,70),(15,70)]
    assert all(r['free_after_reservations_qty']==30 for r in candidate['material_availability_after_reservations'])
    args['committed']={A:20,B:20}
    assert policy.select(**args) is None
    assert args['selection_audit'][-1]['components'][0]['free_after_reservations_qty']==10


def test_later_receipts_never_erase_an_earlier_initial_shortfall():
    initial=(order(identity='early',qty=70,physical=8,available=9),
             order(identity='later',qty=60,physical=15,available=16))
    receipts=tuple(('R-'+c[1],c,10,130,'held',5) for c in (A,B))
    policy,args,_=selection(qty=100,initials=initial,available=100,capacity=100,future_receipts=receipts)
    assert policy.select(**args) is None
    reserve,rows,_=args['opening_coverage'].future_material_protection()
    assert reserve=={A:70,B:70}
    assert [r['uncovered_prefix_qty'] for r in rows[0]['dates']]==[70,0]


@pytest.mark.parametrize('origin',['estimated','estimated_source','opening_execution_unknown','mrp_proposal','unidentified'])
def test_unproven_future_receipt_does_not_release_initial_stock(origin):
    receipts=tuple(('R-'+c[1],c,14,100,origin,5) for c in (A,B))
    policy,args,_=selection(initial=order(physical=15,available=16),available=100,capacity=100,
        future_receipts=receipts)
    assert policy.select(**args) is None
    reserve,rows,excluded=args['opening_coverage'].future_material_protection()
    assert reserve=={A:100,B:100} and len(excluded)==2
    assert all(r['reason']=='unproven_or_revocable_receipt_origin' for r in excluded)


@pytest.mark.parametrize('fault',['duplicate','future_known','negative'])
def test_invalid_future_component_receipt_invalidates_coverage(fault):
    receipt=('R',A,14,-1 if fault=='negative' else 100,'held',6 if fault=='future_known' else 5)
    receipts=(receipt,receipt) if fault=='duplicate' else (receipt,)
    policy,args,_=selection(initial=order(physical=15,available=16),future_receipts=receipts)
    assert not args['opening_coverage'].valid
    assert policy.select(**args) is None


def test_known_other_use_backlog_leaves28800_not150000_for_a_new_lot():
    debt={A:(Requirement('unserved',4,121200),)}
    saved=deepcopy(debt)
    reserved,audit=reserve_known_component_backlogs(debt,decision_day=5,components=(A,B))
    assert reserved=={A:121200} and audit[0]['requirements'][0]['due_day']==4
    large,args,_=selection(qty=129600,available=150000,capacity=150000,budget=500000,committed=reserved)
    assert large.select(**args) is None
    assert args['selection_audit'][0]['components'][0]['free_after_reservations_qty']==28800
    small,args,_=selection(qty=28800,available=150000,capacity=150000,budget=500000,committed=reserved)
    candidate=small.select(**args)
    assert candidate['qty']==28800
    budget=next(row for row in candidate['source_budgets'] if row['item_id']==A[1])
    assert budget['committed_qty']==121200 and budget['allocated_qty']==28800
    assert debt==saved


def test_known_other_use_backlog_and_initial_reserve_are_both_protected():
    reserved,_=reserve_known_component_backlogs({A:(Requirement('unserved',4,121200),)},
        decision_day=5,components=(A,B))
    policy,args,_=selection(qty=28800,initial=order(qty=10000,physical=15,available=16),
        available=150000,capacity=150000,budget=500000,committed=reserved)
    assert policy.select(**args) is None
    component=next(r for r in args['selection_audit'][0]['components'] if r['item_id']==A[1])
    assert component['initial_reserved_qty']==10000 and component['free_after_reservations_qty']==18800


def test_served_other_use_is_not_reserved_again_from_historical_requirement():
    debt=(Requirement('unserved',4,121200),)
    service=engine.serve_external_component_requirements(decision_day=5,available_qty=121200,
        backlog=debt,due=(),uom='UN')
    assert service.consumed_qty==121200 and service.remaining==()
    reserved,audit=reserve_known_component_backlogs({A:service.remaining},decision_day=6,components=(A,))
    assert reserved=={} and audit==[]


@pytest.mark.parametrize('fault',['duplicate','today','future','negative'])
def test_component_backlog_rejects_duplicate_or_not_previously_due_rows(fault):
    day=5 if fault=='today' else 6 if fault=='future' else 4
    row=Requirement('debt',day,-1 if fault=='negative' else 10)
    debt=(row,row) if fault=='duplicate' else (row,)
    with pytest.raises(ValueError,match='unique prior-day'):
        reserve_known_component_backlogs({A:debt},decision_day=5,components=(A,))


def test_current_day_other_use_leaves46618_and_refuses57600_without_changing_lot():
    today={A:(Requirement('today',5,11818),)}
    reserved,audit=reserve_current_component_requirements(today,backlogs={},decision_day=5,components=(A,B))
    receipts=tuple(('R-'+c[1],c,6,50000,'held',5) for c in (A,B))
    for quantity,accepted in ((57600,False),(28800,True)):
        policy,args,_=selection(qty=quantity,initial=order(qty=120600,physical=6,available=7),
            available=129036,capacity=150000,budget=500000,committed=reserved,future_receipts=receipts)
        candidate=policy.select(**args)
        assert (candidate is not None)==accepted
        components=(candidate['material_availability_after_reservations'] if accepted else
                    args['selection_audit'][0]['components'])
        component=next(r for r in components if r['item_id']==A[1])
        assert component['initial_reserved_qty']==70600
        assert component['free_after_reservations_qty']==46618
    assert audit[0]['requirements']==[dict(requirement_id='today',due_day=5,remaining_qty=11818)]


def test_prior_backlog_and_current_need_are_disjoint_reserved_once_and_served_once():
    backlog={A:(Requirement('yesterday',4,20),)}
    today={A:(Requirement('today',5,30),)}
    prior,_=reserve_known_component_backlogs(backlog,decision_day=5,components=(A,))
    current,_=reserve_current_component_requirements(today,backlogs=backlog,decision_day=5,components=(A,))
    assert prior[A]+current[A]==50
    service=engine.serve_external_component_requirements(decision_day=5,available_qty=100,
        backlog=backlog[A],due=today[A],uom='UN')
    assert service.consumed_qty==50 and service.available_end_qty==50 and not service.remaining
    assert sum(row.qty for row in backlog[A])==20 and sum(row.qty for row in today[A])==30


@pytest.mark.parametrize('fault',['duplicate','backlog_overlap','past','future','negative'])
def test_current_component_demand_rejects_wrong_dates_or_double_count(fault):
    day=4 if fault=='past' else 6 if fault=='future' else 5
    row=Requirement('today',day,-1 if fault=='negative' else 10)
    rows=(row,row) if fault=='duplicate' else (row,)
    backlog={A:(Requirement('today',4,10),)} if fault=='backlog_overlap' else {}
    with pytest.raises(ValueError,match='unique current-day'):
        reserve_current_component_requirements({A:rows},backlogs=backlog,decision_day=5,components=(A,))


def test_current_day_revelation_reads_estimates_once_and_defers_merge_until_service():
    calls=[]
    estimate_rows=[Requirement('estimate',5,99)]
    actual_rows=[Requirement('today',5,30)]
    class Estimated:
        def due(self,day):
            calls.append(('estimate',day))
            return {A:estimate_rows}
    class Observed:
        def preview_due(self,day,due):
            calls.append(('preview',day))
            assert due[A]==tuple(estimate_rows)
            return {A:actual_rows},()
        def merge_due(self,day,due):
            calls.append(('observed',day))
            assert due[A]==tuple(estimate_rows)
            return {A:(Requirement('today',5,30),)}
    observed=Observed()
    snapshot=reveal_current_component_requirements(Estimated(),observed,decision_day=5)
    actual_rows.append(Requirement('later mutation',5,900))
    for _ in range(2):
        reserved,_=reserve_current_component_requirements(snapshot.known_due,backlogs={},decision_day=5,components=(A,))
        assert reserved[A]==30
    assert calls==[('estimate',5),('preview',5)]
    final_due=observed.merge_due(5,snapshot.estimated_due)
    service=engine.serve_external_component_requirements(decision_day=5,available_qty=100,
        backlog=(),due=final_due[A],uom='UN')
    assert service.consumed_qty==30 and calls==[('estimate',5),('preview',5),('observed',5)]


def test_current_revelation_rejects_a_calendar_returning_future_observation():
    class InvalidCalendar:
        def due(self,day):
            return {A:(Requirement('future',day+1,30),)}
    with pytest.raises(ValueError,match='unique current-day'):
        reveal_current_component_requirements(InvalidCalendar(),None,decision_day=5)


@pytest.mark.parametrize('cumulative',[False,True])
def test_real_runtime_preview_never_closes_before_own_production(cumulative):
    from etudecas.simulation.current_reference import runtime_observed_type
    from etudecas.simulation.reference_mrp import historical_adapter as adapter
    from etudecas.simulation.engine.mrp_planning import ObservedExternalComponentExecution
    budget=dict(budget_id='weekly',node_id=A[0],item_id=A[1],uom='UN',closing_day=5,
        first_day=0,end_day_exclusive=6,covered_scan3_qty=100,source_file='synthetic',
        scan3_source_cell='J1',source_week_marker='synthetic week')
    tracker=adapter.tracker_for(adapter.f3_module(),[budget],(A,) if cumulative else ())
    calls=[]
    original_close=tracker.close
    def counted_close(day,due):
        calls.append(day)
        return original_close(day,due)
    tracker.close=counted_close
    runtime_type=runtime_observed_type(ObservedExternalComponentExecution,tracker,None,10)
    observed=object.__new__(runtime_type)
    class Calendar:
        def due(self,day):return {}
    observed.calendar=Calendar();observed.pairs=();observed._rows={}
    tracker.own_withdrawal(day=4,node_id=A[0],item_id=A[1],qty=40,event_type='production_consume')
    before=deepcopy((dict(tracker.own),tracker.published,tracker.provenance,dict(tracker.cumulative)))
    snapshot=reveal_current_component_requirements(Calendar(),observed,decision_day=5)
    assert snapshot.known_due=={} and snapshot.unresolved_for((A,))
    assert not snapshot.unresolved_for((B,))
    assert snapshot.deferred_closures[0]['closing_day']==5
    assert (dict(tracker.own),tracker.published,tracker.provenance,dict(tracker.cumulative))==before
    assert calls==[]
    tracker.own_withdrawal(day=5,node_id=A[0],item_id=A[1],qty=30,event_type='production_consume')
    due=observed.merge_due(5,snapshot.estimated_due)
    assert calls==[5] and sum(r.qty for r in due[A])==30
    assert tracker.published['weekly']['own_physical_qty']==70
    assert tracker.published['weekly']['residual_requested_qty']==30


def test_current_revelation_refuses_stateful_adapter_without_pure_preview_contract():
    class Calendar:
        def due(self,day):return {}
    class Stateful:
        def merge_due(self,day,due):raise AssertionError('must not close in preview')
    with pytest.raises(ValueError,match='pure preview_due API'):
        reveal_current_component_requirements(Calendar(),Stateful(),decision_day=5)


def test_current_revelation_rejects_future_deferred_closing():
    class Calendar:
        def due(self,day):return {}
    class Preview:
        def preview_due(self,day,due):
            return {},(dict(node_id=A[0],item_id=A[1],budget_id='week',closing_day=day+1,
                reason='quantity_depends_on_current_day_production'),)
    with pytest.raises(ValueError,match='unique current-day identity'):
        reveal_current_component_requirements(Calendar(),Preview(),decision_day=5)
