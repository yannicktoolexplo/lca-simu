"""Pure in-memory observed-use import contracts; no filesystem fixtures."""
from copy import deepcopy
import json
import pytest

from etudecas.simulation.experiments.shared_components import (
    build_observed_external_component_demands, declare_managed_inventory_pairs,
)
from etudecas.simulation.engine.mrp_planning import ExternalComponentDemandCalendar


def graph(uom='KG'):
    return {'nodes': [{'id': 'M-1810', 'inventory': {'states': [
        {'item_id': 'item:001848', 'uom': uom}, {'item_id': 'item:021081', 'uom': 'KG'},
        {'item_id': 'item:268091', 'uom': 'UN'}]}, 'processes': [{'inputs': [
            {'item_id': 'item:001848'}, {'item_id': 'item:021081'}],
            'outputs': [{'item_id': 'item:268091'}]}]}], 'edges': []}


def row(item='001848', week='2025-01-05', sorties=-7, uom='KG', rn=2):
    return dict(item=item, division='1810', article_type='MP', week=week, sorties=sorties, uom=uom, row=rn)


def build(g, rr):
    return build_observed_external_component_demands(g, rr, source_file='movements.xlsx', source_sha256='a'*64)


def calendar(payload, g):
    return ExternalComponentDemandCalendar(payload, pair_uoms={
        (n['id'],s['item_id']):s['uom'] for n in g['nodes'] for s in n['inventory']['states']},
        origin_date='2025-01-01', horizon_days=365)


def test_observed_other_use_is_physical_daily_only_and_never_forecast():
    g=graph(); before=deepcopy(g)
    p=build(g,[row()]); c=calendar(p,g)
    assert g==before
    assert [r['period_start_day'] for r in p['rows']]==list(range(5,12))
    assert [r['qty'] for r in p['rows']]==[1.]*7
    assert all(r['known_day']==r['period_start_day'] for r in p['rows'])
    assert c.requirements(decision_day=5, first_day=6, through_day=364)=={}
    assert sum(r.qty for r in c.due(5)['M-1810','item:001848'])==1
    assert json.loads(p['rows'][0]['estimation_basis'])['scan3_not_injected'] is True


def test_explicit_zero_is_coverage_but_missing_week_is_not_zero():
    g=graph();p=build(g,[row(item='021081',sorties=0)])
    assert len(p['rows'])==7 and sum(r['qty'] for r in p['rows'])==0
    assert p['coverage_rows']==[dict(node_id='M-1810',item_id='item:021081',first_day=5,end_day_exclusive=12,source_cells='Feuille1!I2')]
    assert not any(r['period_start_day']>=12 for r in p['rows'])
    assert calendar(p,g).due(5)=={}


def test_positive_I_excludes_entire_pair_and_local_outputs_are_not_uses():
    g=graph(); p=build(g,[row(),row(week='2025-01-12',sorties=1,rn=3),
        row(item='021081',sorties=0,rn=4),row(item='268091',uom='UN',rn=5)])
    assert {r['item_id'] for r in p['rows']}=={'item:021081'}
    reasons={r['item_id']:r.get('reason') for r in p['estimation_audit']}
    assert reasons['item:001848']=='positive_I_pair_has_ambiguous_net_flows'
    assert reasons['item:268091']=='local_manufactured_output_not_external_consumption'


def test_unit_conversion_and_partial_year_preserve_weekly_cumulative_UN():
    g=graph('G');p=build(g,[row(sorties=-1.4)])
    assert sum(r['qty'] for r in p['rows'])==1400
    assert all(r['uom']=='G' for r in p['rows'])
    g=graph('UN');p=build(g,[row(week='2024-12-29',sorties=-10,uom='ZUN')])
    # Full week floors [0,1,2,4,5,7,8,10]; first two days precede Jan1.
    assert [r['qty'] for r in p['rows']]==[2.,1.,2.,1.,2.]
    assert [r['period_start_day'] for r in p['rows']]==[0,1,2,3,4]
    assert sum(r['qty'] for r in p['rows'])==8
    assert calendar(p,g).due(0)['M-1810','item:001848'][0].qty==2
    p=build(g,[row(week='2025-12-28',sorties=-10,uom='ZUN')])
    assert [r['qty'] for r in p['rows']]==[1.,1.,2.]
    assert [r['period_start_day'] for r in p['rows']]==[362,363,364]


def test_invalid_observation_rejected_without_graph_change():
    g=graph('UN');before=deepcopy(g)
    with pytest.raises(ValueError,match='whole units'):
        build(g,[row(sorties=-1.5,uom='UN')])
    with pytest.raises(ValueError,match='Duplicate'):
        build(g,[row(uom='UN'),row(uom='UN')])
    with pytest.raises(ValueError,match='Sundays'):
        build(g,[row(week='2025-01-06',uom='UN')])
    assert g==before


def test_modeled_MP_without_BOM_eligible_but_internal_transfer_excluded():
    g=graph();g['nodes'][0]['processes'][0]['inputs']=[]
    p=build(g,[row()])
    assert len(p['rows'])==7
    assert p['estimation_audit'][0]['direct_BOM_component'] is False
    g['nodes'].append({'id':'M-1430','inventory':{'states':[{'item_id':'item:001848','uom':'KG'}]},'processes':[]})
    g['edges'].append({'from':'M-1810','to':'M-1430','items':['item:001848']})
    p=build(g,[row()])
    assert p['rows']==[]
    assert p['estimation_audit'][0]['reason']=='internal_transfer_departure_cannot_be_counted_twice'


def managed_graph():
    g=graph()
    g['nodes'].append({'id':'M-1430','inventory':{'states':[]},'processes':[]})
    g['meta']={'external_component_demands':{'untouched':'forecast-marker'}}
    return g


def managed_record(**changes):
    r=dict(node_id='M-1430',item_id='item:001848',initial_qty=31660430,uom='G',
           source_file='initial.xlsx',source_cells='Stocks!A3:G3',source_date='2025-01-01',
           initial_availability_status='backcast_first_MRP_status_separate_scenario',
           partial_scope=['known_open_orders_only','observed_other_use_execution','unmodelled_divers'])
    r.update(changes)
    return r


def test_managed_stock_activation_is_local_pure_and_idempotent_without_supply_rules():
    g=managed_graph();before=deepcopy(g)
    out=declare_managed_inventory_pairs(g,[managed_record()])
    assert g==before
    assert out['nodes'][0]==before['nodes'][0]
    assert out['edges']==before['edges'] and out['nodes'][1]['processes']==[]
    state=out['nodes'][1]['inventory']['states'][0]
    assert state['initial']==31660.43 and state['uom']=='KG'
    assert state['initial_source']=='initial.xlsx!Stocks!A3:G3'
    assert 'mrp_policy' not in state
    assert out['meta']['external_component_demands']==before['meta']['external_component_demands']
    declaration=out['meta']['managed_inventory_pairs']['rows'][0]
    assert declaration['supply_status']=='unconfigured' and declaration['role']=='stock_external_use'
    assert declare_managed_inventory_pairs(out,[managed_record()])==out
    assert declare_managed_inventory_pairs(g,[])==g


def test_managed_observed_execution_only_targets_declared_source_rows_not_existing_BOM():
    g=declare_managed_inventory_pairs(managed_graph(),[managed_record()])
    rr=[dict(row(sorties=-14),division='1430',article_type='AC',sorties_article_scan3=-999)]
    payload=build(g,rr)
    assert len(payload['rows'])==7 and sum(r['qty'] for r in payload['rows'])==14
    assert {(r['node_id'],r['item_id']) for r in payload['rows']}=={('M-1430','item:001848')}
    assert all(r['known_day']==r['period_start_day'] for r in payload['rows'])
    assert calendar(payload,g).requirements(decision_day=5,first_day=6,through_day=364)=={}
    assert g['meta']['external_component_demands']=={'untouched':'forecast-marker'}


@pytest.mark.parametrize('fault',['existing','duplicate','negative','nan','fractional_UN','future','provenance','route','BOM'])
def test_managed_stock_rejects_ambiguous_activation_without_mutating_input(fault):
    g=managed_graph();r=managed_record();rr=[r]
    if fault=='existing':g['nodes'][1]['inventory']['states']=[{'item_id':'item:001848','uom':'KG','initial':7}]
    elif fault=='duplicate':rr.append(deepcopy(r))
    elif fault=='negative':r['initial_qty']=-1
    elif fault=='nan':r['initial_qty']=float('nan')
    elif fault=='fractional_UN':
        g['nodes'][0]['inventory']['states'][0]['uom']='UN';r.update(initial_qty=1.5,uom='UN')
    elif fault=='future':r['source_date']='2025-01-06'
    elif fault=='provenance':r['source_cells']=''
    elif fault=='route':g['edges']=[{'from':'M-1810','to':'M-1430','items':['item:001848']}]
    elif fault=='BOM':g['nodes'][1]['processes']=[{'inputs':[{'item_id':'item:001848'}],'outputs':[]}]
    before=deepcopy(g)
    with pytest.raises(ValueError):declare_managed_inventory_pairs(g,rr)
    assert g==before


def test_managed_runtime_resolver_preserves_legacy_and_accepts_explicit_stock_only():
    from etudecas.simulation.engine.run_first_simulation import resolve_managed_inventory_pairs
    pair=('M-1430','item:001848')
    assert resolve_managed_inventory_pairs(None,stock_pairs=set(),production_pairs=set(),inbound_pairs=set())==set()
    payload=declare_managed_inventory_pairs(managed_graph(),[managed_record()])['meta']['managed_inventory_pairs']
    assert resolve_managed_inventory_pairs(payload,stock_pairs={pair},production_pairs=set(),inbound_pairs=set())=={pair}


@pytest.mark.parametrize('fault',['unknown','duplicate','BOM','route'])
def test_managed_runtime_resolver_rejects_existing_planning_scope_overlap(fault):
    from etudecas.simulation.engine.run_first_simulation import resolve_managed_inventory_pairs
    pair=('M-1430','item:001848')
    payload=declare_managed_inventory_pairs(managed_graph(),[managed_record()])['meta']['managed_inventory_pairs']
    if fault=='duplicate':payload['rows'].append(deepcopy(payload['rows'][0]))
    with pytest.raises(ValueError):
        resolve_managed_inventory_pairs(payload,stock_pairs=set() if fault=='unknown' else {pair},
            production_pairs={pair} if fault=='BOM' else set(),inbound_pairs={pair} if fault=='route' else set())


def managed_supply_case():
    pair=('M-1430','item:001848')
    payload=declare_managed_inventory_pairs(managed_graph(),[managed_record()])['meta']['managed_inventory_pairs']
    payload['rows'][0].update(supply_status='configured_candidate',supply_policy={
        'policy_id':'test-local-policy','status':'candidate_not_inferred_ERP','lot_multiple_qty':7000,
        'protection_workdays':26,'buffer_qty':100,
        'source_refs':{'lot_multiple_qty':'MRP!H38; candidate','protection':'explicit test hypothesis'}})
    def week(start,qty):
        return dict(demand_id=f'w{start}',period_start_day=start,period_days=7,qty=qty,
                    source_file='MRP.xlsx',source_cells=f'I{start}',estimation_basis='local total I, no modeled BOM')
    forecast=dict(schema_version=3,origin='2025-01-01',scenario_id='local-test',
        semantics='incremental_non_modelled_component_use',repeat_period_days=None,rows=[],versioned_series=[
            dict(node_id=pair[0],item_id=pair[1],uom='KG',period_anchor_day=4,period_days=7,repeat_period_days=0,
                 current_bucket_policy='freeze_previous_exclude_current_vintage',missing_future_policy='unprovided_not_observed_zero',
                 versions=[dict(vintage_id='v4',known_day=4,rows=[week(11,700),week(18,1400)]),
                           dict(vintage_id='v11',known_day=11,rows=[week(25,2100)])])])
    lane=dict(src='SDC-F',dst=pair[0],lead_days=56,lead_days_mean=56,lead_time_source='case_data_fia',
              lead_time_is_default=False,standard_order_qty=6000,edge_id='F-Gien')
    kwargs=dict(managed_pairs={pair},lanes_by_dest_item={pair:[lane]},item_unit_map={pair[1]:'KG'},
                supplier_node_ids={'SDC-F'},forecast_payload=forecast,origin_date='2025-01-01',horizon_days=729)
    return pair,payload,kwargs


def test_managed_supply_uses_local_latest_forecast_without_BOM_or_future_physical_use():
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=managed_supply_case(); before=deepcopy((payload,kwargs))
    assert engine.resolve_managed_inventory_pairs(payload,stock_pairs={pair},production_pairs=set(),inbound_pairs={pair})=={pair}
    policies,forecast=engine.resolve_managed_supply_policies(payload,**kwargs)
    assert policies[pair]['supplier_id']=='SDC-F'
    assert policies[pair]['effective_protection_workdays']==26
    assert policies[pair]['effective_buffer_qty']==100
    assert forecast.requirements(decision_day=3,first_day=4,through_day=35)=={}
    first=forecast.requirements(decision_day=4,first_day=5,through_day=35)[pair]
    assert sum(r.qty for r in first)==2100
    revised=forecast.requirements(decision_day=11,first_day=12,through_day=35)[pair]
    # Current week remains 6 * 100; the old future 1400 does not survive v11.
    assert sum(r.qty for r in revised)==2700
    assert not any(18<=r.due_day<=24 for r in revised)
    g=declare_managed_inventory_pairs(managed_graph(),[managed_record()])
    physical=calendar(build(g,[dict(row(sorties=-14),division='1430')]),g)
    assert sum(r.qty for r in physical.due(5)[pair])==2
    assert physical.requirements(decision_day=5,first_day=6,through_day=364)=={}
    assert (payload,kwargs)==before


@pytest.mark.parametrize('fault',['no_route','internal_route','two_routes','no_FIA','unit','lot_zero',
    'lot_nan','days_fractional','no_protection','negative_buffer','no_provenance','no_forecast',
    'fixed_rows','wrong_pair','duplicate','unknown_policy_field','entirely_unknown_horizon','fractional_UN_lot'])
def test_managed_supply_rejects_implicit_or_inconsistent_rules_in_memory(fault):
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=managed_supply_case();policy=payload['rows'][0]['supply_policy']
    if fault=='no_route':kwargs['lanes_by_dest_item']={}
    elif fault=='internal_route':kwargs['supplier_node_ids']=set()
    elif fault=='two_routes':kwargs['lanes_by_dest_item'][pair]*=2
    elif fault=='no_FIA':kwargs['lanes_by_dest_item'][pair][0]['lead_time_is_default']=True
    elif fault=='unit':payload['rows'][0]['uom']='G'
    elif fault=='lot_zero':policy['lot_multiple_qty']=0
    elif fault=='lot_nan':policy['lot_multiple_qty']=float('nan')
    elif fault=='days_fractional':policy['protection_workdays']=1.5
    elif fault=='no_protection':policy.pop('protection_workdays');policy.pop('buffer_qty')
    elif fault=='negative_buffer':policy['buffer_qty']=-1
    elif fault=='no_provenance':policy['source_refs']['protection']=''
    elif fault=='no_forecast':kwargs['forecast_payload']=None
    elif fault=='fixed_rows':kwargs['forecast_payload']['rows']=[{}]
    elif fault=='wrong_pair':kwargs['forecast_payload']['versioned_series'][0]['node_id']='M-1810'
    elif fault=='duplicate':payload['rows'].append(deepcopy(payload['rows'][0]))
    elif fault=='unknown_policy_field':policy['source_safety_inferred']=20
    elif fault=='entirely_unknown_horizon':
        for version in kwargs['forecast_payload']['versioned_series'][0]['versions']:version['rows']=[]
    elif fault=='fractional_UN_lot':
        payload['rows'][0]['uom']='UN';kwargs['item_unit_map'][pair[1]]='UN';policy['lot_multiple_qty']=1.5
    with pytest.raises(ValueError):engine.resolve_managed_supply_policies(payload,**kwargs)


def test_managed_supply_legacy_and_explicit_single_protection_modes():
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=managed_supply_case()
    absent=dict(kwargs,forecast_payload=None,managed_pairs=set())
    assert engine.resolve_managed_supply_policies(None,**absent)==({},None)
    policy=payload['rows'][0]['supply_policy'];policy.pop('buffer_qty')
    p,_=engine.resolve_managed_supply_policies(payload,**kwargs)
    assert p[pair]['effective_buffer_qty']==0 and 'buffer_qty' not in p[pair]
    policy.pop('protection_workdays');policy['buffer_qty']=500
    p,_=engine.resolve_managed_supply_policies(payload,**kwargs)
    assert p[pair]['effective_protection_workdays']==0 and 'protection_workdays' not in p[pair]


def test_managed_purchase_projection_and_execution_share_7000_lot_and_source_dates():
    from etudecas.simulation.engine import run_first_simulation as engine
    from etudecas.simulation.engine.mrp_planning import Requirement, FirmReceipt, plan_dated_requirements
    pair,payload,kwargs=managed_supply_case()
    policies,_=engine.resolve_managed_supply_policies(payload,**kwargs)
    lot=engine.managed_supply_lot(policies[pair])
    assert lot.minimum==lot.multiple==7000 and lot.integer is False
    # 8000 - 100 available - 7000 already engaged = 900 -> one 7000 lot.
    plan=plan_dated_requirements(decision_day=0,available_qty=100,
        requirements=[Requirement('local',100,8000)],firm_receipts=[FirmReceipt('firm',90,7000)],
        lead_days=92,lot_sizing=lot)
    assert plan.proposed_qty==7000
    plans,requirements,_=engine.plan_component_network(decision_day=0,
        requirements_by_pair={pair:[Requirement('local',100,8000)]},available_by_pair={pair:100},
        firm_receipts_by_pair={pair:[FirmReceipt('firm',90,7000)]},transport_sources_by_pair={},bom_by_pair={},
        lead_days_by_pair={pair:92},lot_sizing_by_pair={pair:lot},reserve_targets_by_pair={pair:0},
        coverage_days_by_pair={},active_campaigns_by_pair={})
    assert set(plans)=={pair} and plans[pair].proposed_qty==7000
    assert sum(r.qty for r in requirements[pair])==8000
    assert engine.mrp_purchase_order_quantity(900,18640,lot.multiple,binding=True,uom='KG')==7000
    assert engine.mrp_purchase_order_quantity(7001,18640,lot.multiple,binding=True,uom='KG')==14000
    assert engine.mrp_purchase_order_quantity(7001,6999,lot.multiple,binding=True,uom='KG')==0
    lane=kwargs['lanes_by_dest_item'][pair][0]
    assert lane['standard_order_qty']==6000
    assert engine.supplier_delivery_lead_days(lane,None,mode='source',stochastic=False)==56
    # Jan1 + 56d = Feb26, plus26 working days = Apr3 (day92).
    assert engine.supplier_receipt_available_day(56,26,origin_date='2025-01-01')==92


def test_opening_purchases_keep_per_row_source_file_and_text_identity_without_double_credit():
    from collections import defaultdict
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,_,kwargs=managed_supply_case()
    row=dict(dst_node_id=pair[0],src_node_id='SDC-F',item_id=pair[1],order_type='purchase_open_order',
             quantity=7000,uom='KG',physical_delivery_day=22,usable_day=42,receipt_release_days=20,source_row=38)
    payload=dict(source_file='Extract.xlsx',rows=[row,dict(row,source_file='MRP.xlsx',source_row='MRP_H38',
                                                         physical_delivery_day=32,usable_day=68)])
    before=deepcopy(payload); pipeline=defaultdict(list);transit=defaultdict(float);orders=[];inits=[];assumptions=[]
    total,seeded,_=engine.seed_open_orders_from_metadata(pipeline,transit,opening_open_orders_payload=payload,
        lanes_by_dest_item=kwargs['lanes_by_dest_item'],item_unit_map=kwargs['item_unit_map'],pair_mrp_safety_time_days={},
        total_timeline_days=365,warmup_days=0,opening_production_bom_issues_by_day=None,
        opening_production_order_bom_issue_mode='wip',mrp_order_rows=orders,supplier_shipment_rows=[],
        initialization_pipeline_rows=inits,assumptions_ledger_rows=assumptions,dated_purchase_availability=True)
    assert total==transit[pair]==14000 and payload==before
    book=engine.OpeningPurchaseAvailability(seeded,item_unit_map=kwargs['item_unit_map'])
    expected=[engine.OpeningPurchaseAvailability.marker_for('Extract.xlsx',38),
              engine.OpeningPurchaseAvailability.marker_for('MRP.xlsx','MRP_H38')]
    assert [pipeline[d][0][3] for d in (42,68)]==expected
    assert set(book.by_marker)==set(expected)
    assert [r['source_file'] for r in orders]==['Extract.xlsx','MRP.xlsx']
    assert [r['source_file'] for r in inits]==['Extract.xlsx','MRP.xlsx']
    assert [r['source'] for r in assumptions]==['Extract.xlsx','MRP.xlsx']


def planning_forecast_case():
    _,_,context=managed_supply_case()
    pair=('M-1810','item:338928')
    payload=deepcopy(context['forecast_payload']);payload['scenario_id']='planning-other-use'
    series=payload['versioned_series'][0]
    series.update(node_id=pair[0],item_id=pair[1],uom='UN')
    # Explicit future zero in v11, omitted v4 week25, current11 frozen fromv4.
    old=deepcopy(series['versions'][1]['rows'][0]);series['versions'][0]['rows'].append(old)
    zero=deepcopy(series['versions'][0]['rows'][1]);zero['qty']=0
    series['versions'][1]['rows']=[zero]
    kwargs=dict(production_input_pairs={pair},managed_pairs=set(),finished_good_item_ids={'item:268091'},
                item_unit_map={pair[1]:'UN'},origin_date='2025-01-01',horizon_days=729)
    return pair,payload,kwargs


def test_planning_only_new_component_without_legacy_is_causal_and_cannot_execute():
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=planning_forecast_case(); before=deepcopy(payload)
    new=engine.resolve_external_planning_forecasts(payload,**kwargs)
    assert engine.component_planning_requirements(None,new,decision_day=3,first_day=4,through_day=31)=={}
    future=engine.component_planning_requirements(None,new,decision_day=4,first_day=5,through_day=31)
    assert set(future)=={pair} and sum(r.qty for r in future[pair])==4200
    assert engine.component_planning_calendar_for_pair(pair,None,new) is new
    assert new.covered_days(pair,decision_day=4,first_day=5,through_day=31)==frozenset(range(11,32))
    with pytest.raises(ValueError,match='cannot execute'):new.due(11)
    assert payload==before


def test_planning_only_zero_or_absent_revision_replaces_old_needs_but_not_physical_due():
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=planning_forecast_case()
    oldpayload=deepcopy(payload);oldpayload['scenario_id']='old-physical'
    oldpayload['versioned_series'][0]['versions']=oldpayload['versioned_series'][0]['versions'][:1]
    legacy=ExternalComponentDemandCalendar(oldpayload,pair_uoms={pair:'UN'},origin_date='2025-01-01',horizon_days=729)
    new=engine.resolve_external_planning_forecasts(payload,**kwargs)
    before=legacy.due(18)
    replaced=engine.component_planning_requirements(legacy,new,decision_day=11,first_day=12,through_day=31)
    assert sum(r.qty for r in replaced[pair])==600  # Only6 current days fromv4.
    assert not any(r.due_day>=18 for r in replaced[pair])
    assert legacy.due(18)==before and sum(r.qty for r in before[pair])==200
    selected=engine.component_planning_calendar_for_pair(pair,legacy,new)
    assert selected is new
    assert selected.covered_days(pair,decision_day=11,first_day=12,through_day=31)==frozenset(range(12,25))
    # Explicit zero18..24 is covered. Missing25..31 is unknown, never old2100.
    assert engine.component_planning_requirements(legacy,new,decision_day=11,first_day=18,through_day=31)=={}


def test_planning_only_default_and_nonselected_pairs_preserve_legacy():
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=planning_forecast_case()
    new=engine.resolve_external_planning_forecasts(payload,**kwargs)
    other=('M-1810','item:338929');oldpayload=deepcopy(payload)
    oldpayload['versioned_series'][0].update(item_id=other[1]);oldpayload['scenario_id']='other'
    legacy=ExternalComponentDemandCalendar(oldpayload,pair_uoms={other:'UN'},origin_date='2025-01-01',horizon_days=729)
    query=dict(decision_day=4,first_day=5,through_day=31)
    assert engine.resolve_external_planning_forecasts(None,**kwargs) is None
    assert engine.component_planning_requirements(legacy,None,**query)==legacy.requirements(**query)
    result=engine.component_planning_requirements(legacy,new,**query)
    assert result[other]==legacy.requirements(**query)[other]
    assert sum(r.qty for r in result[pair])==4200
    assert engine.component_planning_calendar_for_pair(other,legacy,new) is legacy
    assert engine.component_planning_calendar_for_pair(('M-X','item:X'),legacy,new) is None


def test_planning_only_mass_forecast_keeps_fractional_source_quantity():
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=planning_forecast_case()
    kwargs['item_unit_map'][pair[1]]='KG';series=payload['versioned_series'][0];series['uom']='KG'
    series['versions'][0]['rows']=series['versions'][0]['rows'][:1]
    series['versions'][0]['rows'][0]['qty']=0.7
    new=engine.resolve_external_planning_forecasts(payload,**kwargs)
    needs=engine.component_planning_requirements(None,new,decision_day=4,first_day=11,through_day=17)[pair]
    assert len(needs)==7 and all(r.qty==0.1 for r in needs)
    assert sum(r.qty for r in needs)==pytest.approx(0.7,abs=1e-15)
    assert series['versions'][0]['rows'][0]['qty']==0.7


@pytest.mark.parametrize('fault',['version','repeat','series_repeat','fixed','unknown_pair','managed','PF','unit','fractional_UN','origin'])
def test_planning_only_forecast_rejects_wrong_scope_and_hidden_physical_rows(fault):
    from etudecas.simulation.engine import run_first_simulation as engine
    pair,payload,kwargs=planning_forecast_case()
    if fault=='version':payload['schema_version']=2
    elif fault=='repeat':payload['repeat_period_days']=365
    elif fault=='series_repeat':payload['versioned_series'][0]['repeat_period_days']=365
    elif fault=='fixed':payload['rows']=[{}]
    elif fault=='unknown_pair':kwargs['production_input_pairs']=set()
    elif fault=='managed':kwargs['managed_pairs']={pair}
    elif fault=='PF':kwargs['finished_good_item_ids']={pair[1]}
    elif fault=='unit':payload['versioned_series'][0]['uom']='KG'
    elif fault=='fractional_UN':payload['versioned_series'][0]['versions'][0]['rows'][0]['qty']=700.5
    elif fault=='origin':payload['origin']='2025-01-02'
    with pytest.raises(ValueError):engine.resolve_external_planning_forecasts(payload,**kwargs)


def promise_case():
    from collections import defaultdict
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import FirmReceipt,Requirement
    pair=('M-X','item:P'); identity='PO-1'
    availability=e.OpeningPurchaseAvailability([],item_unit_map={'item:P':'UN'})
    availability.add_order(dict(order_type='external_procurement_supplier_delivery',mrp_order_id=identity,
        node_id=pair[0],item_id=pair[1],src_node_id='S-X',receipt_qty=100,
        physical_delivery_day=20,arrival_day=20,source_file='source.xlsx',source_row='1'))
    pipeline=defaultdict(list,{20:[(*pair,100,'','',identity)]})
    order=dict(mrp_order_id=identity,order_type='external_procurement_supplier_delivery',
        release_status='order_placed_departure_unknown',shipment_id='',release_qty=100,
        planned_receipt_qty=100,day=0,source_file='source.xlsx',sourcing_purchase_cost=400)
    return dict(policy=dict(schema_version=1,mode='known_need_and_protection_v1',review_weekday=None,assumption='scenario'),
        decision_day=4,origin_date='2025-01-01',horizon_day=70,availability=availability,stock={pair:0},
        firm_snapshot={pair:[FirmReceipt(identity,20,100,'in_transit')]},
        requirements_by_pair={pair:[Requirement('need',50,100)]},plan_audits={pair:{}},
        external_pipeline=pipeline,commitments={pair:{identity:(20,100,'external_procurement_supplier_delivery')}},
        order_rows=[order],promise_book={identity:dict(receipt_days=0,original_physical_day=20,original_available_day=20)},
        audit_rows=[],total_days=365)


def test_supplier_promise_report_and_return_preserve_identity_quantity_and_cost():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import Requirement
    k=promise_case(); pair=('M-X','item:P')
    assert e.apply_supplier_promise_postponement(**k)
    assert k['commitments'][pair]['PO-1'][:2]==(50,100)
    assert len(k['external_pipeline'][50])==1 and not k['external_pipeline'][20]
    k['decision_day']=5; k['requirements_by_pair'][pair]=[Requirement('need',25,100)]
    assert e.apply_supplier_promise_postponement(**k)
    assert k['commitments'][pair]['PO-1'][:2]==(25,100)
    assert len(k['external_pipeline'][25])==1 and not k['external_pipeline'][50]
    assert k['order_rows'][0]['sourcing_purchase_cost']==400
    assert k['order_rows'][0]['release_qty']==100 and k['order_rows'][0]['day']==0
    assert k['order_rows'][0]['shipment_id']==''
    assert k['availability'].rows[0]['quantity']==100 and not k['availability'].rows[0]['received']


@pytest.mark.parametrize('state',['disabled','shipment','received','released','unknown_status','expired','other_pair','documentary_initial'])
def test_supplier_promise_does_not_rewrite_unqualified_physical_states(state):
    from etudecas.simulation.engine import run_first_simulation as e
    k=promise_case()
    if state=='disabled':k['policy']=None
    elif state=='shipment':k['order_rows'][0]['shipment_id']='REAL-SHIPMENT'
    elif state=='received':k['availability'].rows[0]['received']=True
    elif state=='released':k['availability'].rows[0]['released']=True
    elif state=='unknown_status':k['order_rows'][0]['release_status']='unknown'
    elif state=='expired':k['decision_day']=20
    elif state=='other_pair':k['policy']['pairs']=[dict(node_id='M-Y',item_id='item:P')]
    elif state=='documentary_initial':k['promise_book']['PO-1']['initial_documentary_completion']=True
    assert not e.apply_supplier_promise_postponement(**k)
    assert k['commitments'][('M-X','item:P')]['PO-1'][:2]==(20,100)
    assert k['external_pipeline'][20]==[('M-X','item:P',100,'','','PO-1')]


def test_supplier_promise_sequential_shared_stock_has_no_duplicate_coverage():
    from etudecas.simulation.engine.mrp_planning import FirmReceipt,Requirement,ReceiptReplanningStatus,postpone_initial_receipts
    receipts=[FirmReceipt('a',20,100,'in_transit'),FirmReceipt('b',21,100,'in_transit')]
    result=postpone_initial_receipts(decision_day=4,available_qty=0,
        requirements=[Requirement('x',50,100),Requirement('y',60,100)],firm_receipts=receipts,
        coverage_days=range(5,71),horizon_day=70,statuses=[ReceiptReplanningStatus(r.receipt_id,True,False,False,4) for r in receipts],
        policy='known_need_and_protection_v1',earliest_available_by_id={'a':20,'b':21})
    assert [(r.receipt_id,r.available_day,r.qty) for r in result.firm_receipts]==[('a',60,100),('b',50,100)]


@pytest.mark.parametrize('fault',['version','mode','review','implicit','warmup','scope_duplicate','scope_empty'])
def test_supplier_promise_policy_rejects_implicit_or_ambiguous_permission(fault):
    from etudecas.simulation.engine import run_first_simulation as e
    policy=promise_case()['policy']; kwargs=dict(dated=True)
    if fault=='version':policy['schema_version']=True
    elif fault=='mode':policy['mode']='automatic'
    elif fault=='review':policy['review_weekday']=7
    elif fault=='implicit':policy['assumption']=''
    elif fault=='warmup':kwargs['warmup_days']=10
    elif fault=='scope_duplicate':policy['pairs']=[dict(node_id='M-X',item_id='item:P')]*2
    elif fault=='scope_empty':policy['pairs']=[]
    with pytest.raises(ValueError):e.resolve_supplier_promise_postponement(policy,**kwargs)
    assert e.resolve_supplier_promise_postponement(None,dated=False) is None


def test_supplier_promise_keeps_known_protection_without_creating_daily_demand():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import StockProtection,Requirement
    k=promise_case();pair=('M-X','item:P')
    k['stock'][pair]=100
    k['plan_audits'][pair]={'protection_points':[StockProtection('floor',5,80)]}
    k['requirements_by_pair'][pair]=[Requirement('need',30,30)]
    assert e.apply_supplier_promise_postponement(**k)
    assert k['commitments'][pair]['PO-1'][:2]==(30,100)
    assert k['stock'][pair]==100


def completion_case():
    pair=('M-X','item:P')
    row=dict(node_id=pair[0],item_id=pair[1],supplier_id='S-X',quantity=100,uom='UN',source_file='MRP.xlsx',
        source_row='H10',known_day=4,physical_delivery_day=15,available_day=23,receipt_workdays=6,
        source_vintage='2025-01-05',source_period_marker='2025-01-12',source_status='planned_weekly_H_not_proven_firm',
        deduplication=dict(source_H_qty=150,represented_opening_qty=50,matched_opening_orders=['original']),assumption='scenario')
    return dict(schema_version=1,mode='first_known_mrp_near_horizon_v1',boundary_policy='full_week_before_earliest_new_receipt',
        physical_week_convention='monday_after_sunday_marker',within_week_date='thursday',rows=[row]),dict(
        pair_uoms={pair:'UN'},lanes_by_dest_item={pair:[dict(src='S-X',edge_id='edge-X')]},
        receipt_policies={pair:dict(receipt_days=6)},origin_date='2025-01-01',dated=True)


def test_initial_book_completion_is_causal_net_and_does_not_mutate_source():
    from etudecas.simulation.engine import run_first_simulation as e
    payload,k=completion_case(); original=deepcopy(payload)
    result=e.resolve_initial_purchase_book_completion(payload,**k)
    assert set(result)=={4} and result[4][0]['quantity']==100
    assert result[4][0]['physical_delivery_day']==15 and result[4][0]['available_day']==23
    assert payload==original
    assert e.resolve_initial_purchase_book_completion(None,**k)=={}


@pytest.mark.parametrize('fault',['duplicate','future','past_receipt','fraction','unit','route','receipt','netting','warmup'])
def test_initial_book_completion_refuses_inconsistent_or_duplicated_evidence(fault):
    from etudecas.simulation.engine import run_first_simulation as e
    payload,k=completion_case();r=payload['rows'][0]
    if fault=='duplicate':payload['rows'].append(deepcopy(r))
    elif fault=='future':r['source_vintage']='2025-01-06'
    elif fault=='past_receipt':r['physical_delivery_day']=3
    elif fault=='fraction':r['quantity']=100.5
    elif fault=='unit':r['uom']='KG'
    elif fault=='route':r['supplier_id']='UNKNOWN'
    elif fault=='receipt':r['available_day']=22
    elif fault=='netting':r['deduplication']['represented_opening_qty']=0
    elif fault=='warmup':k['warmup_days']=3
    with pytest.raises(ValueError): e.resolve_initial_purchase_book_completion(payload,**k)


def weekly_purchase_case():
    pair=('M-X','item:P')
    policy=dict(schema_version=1,mode='weekly_calendar_v1',first_review_day=4,review_weekday=6,
        pairs=[dict(node_id=pair[0],item_id=pair[1])],assumption='scenario')
    return pair,policy


def test_weekly_purchases_anticipate_review_without_placing_at_j0_or_delaying_to_next_week():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import plan_dated_requirements,Requirement,LotSizing
    pair,policy=weekly_purchase_case()
    calendar=e.purchase_review_calendar(tuple((d,d+10) for d in range(36)),policy=policy,pair=pair,
        origin_date='2025-01-01',through_day=28)
    assert [r for r,a in calendar]==[4,11,18,25,32]
    plan=plan_dated_requirements(decision_day=0,available_qty=0,requirements=[Requirement('need',18,100)],
        firm_receipts=(),lead_days=10,lot_sizing=LotSizing(integer=True),availability_by_release=calendar)
    assert [(p.release_day,p.available_day,p.qty) for p in plan.proposals]==[(4,14,100)]
    assert not e.purchase_review_is_due(policy,pair,0,'2025-01-01')
    assert e.purchase_review_is_due(policy,pair,4,'2025-01-01')
    assert not e.purchase_review_is_due(policy,pair,8,'2025-01-01')


def test_weekly_purchases_keep_lateness_and_deduct_documentary_firm_once():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import plan_dated_requirements,Requirement,FirmReceipt,LotSizing
    pair,policy=weekly_purchase_case()
    calendar=e.purchase_review_calendar(tuple((d,d+10) for d in range(36)),policy=policy,pair=pair,
        origin_date='2025-01-01',through_day=28)
    args=dict(decision_day=0,available_qty=0,requirements=[Requirement('need',5,100)],
        lead_days=10,lot_sizing=LotSizing(integer=True),availability_by_release=calendar)
    late=plan_dated_requirements(firm_receipts=(),**args)
    assert late.proposals[0].release_day==4 and late.late_qty==100
    covered=plan_dated_requirements(firm_receipts=[FirmReceipt('initial',15,100,'confirmed')],**args)
    assert not covered.proposals and covered.late_qty==100


def test_weekly_purchase_calendar_legacy_and_nonscope_are_exact_and_tail_is_required():
    from etudecas.simulation.engine import run_first_simulation as e
    pair,policy=weekly_purchase_case(); calendar=tuple((d,d+10) for d in range(29))
    kwargs=dict(pair=pair,origin_date='2025-01-01',through_day=28)
    assert e.purchase_review_calendar(calendar,policy=None,**kwargs)==calendar
    assert e.purchase_review_calendar(calendar,policy=policy,**dict(kwargs,pair=('M-Y','item:P')))==calendar
    with pytest.raises(ValueError):e.purchase_review_calendar(calendar,policy=policy,**kwargs)


@pytest.mark.parametrize('fault',['first_day','weekday','scope','duplicate','assumption','mode'])
def test_weekly_purchase_policy_requires_explicit_consistent_scope_and_calendar(fault):
    from etudecas.simulation.engine import run_first_simulation as e
    pair,policy=weekly_purchase_case()
    if fault=='first_day':policy['first_review_day']=0
    elif fault=='weekday':policy['review_weekday']=7
    elif fault=='scope':policy['pairs'][0]['node_id']='unknown'
    elif fault=='duplicate':policy['pairs']*=2
    elif fault=='assumption':policy['assumption']=''
    elif fault=='mode':policy['mode']='daily'
    with pytest.raises(ValueError):e.resolve_purchase_calendar_or_source_policy(policy,
        mode='weekly_calendar_v1',eligible_pairs={pair},origin_date='2025-01-01')


@pytest.mark.parametrize('source,expected',[(100,100),(20,30),(0,30)])
def test_industrial_purchase_source_preserves_committed_floor_and_never_adds_total_twice(source,expected):
    from etudecas.simulation.engine.mrp_planning import Requirement,IndustrialPlanningWindow,reconcile_industrial_requirements
    original=[Requirement('opening-pack:OF1',12,30),Requirement('derived:provisional',13,80),
        Requirement('external:forecast',14,40),Requirement('reserve:floor',11,10)]
    window=IndustrialPlanningWindow(11,11,18,source,4,'MRP.xlsx','I10')
    result,audit=reconcile_industrial_requirements(original,[window],pair=('M-X','item:P'),decision_day=4,
        policy='source_weekly_with_committed_floor_v1')
    assert next(r for r in result if r.requirement_id=='opening-pack:OF1')==original[0]
    assert next(r for r in result if r.requirement_id=='reserve:floor')==original[3]
    assert sum(r.qty for r in result if not r.requirement_id.startswith('reserve:'))==pytest.approx(expected)
    assert not any(r.requirement_id in ('derived:provisional','external:forecast') for r in result)
    assert audit[0]['planning_qty']==expected and audit[0]['committed_qty']==30


def test_industrial_purchase_source_missing_window_and_current_committed_dates_are_not_zero():
    from etudecas.simulation.engine.mrp_planning import Requirement,IndustrialPlanningWindow,reconcile_industrial_requirements
    original=[Requirement('campaign:active',12,30),Requirement('opening_production:OF',15,20),
        Requirement('derived:uncovered',20,80),Requirement('backlog:current',4,40)]
    window=IndustrialPlanningWindow(11,11,18,100,4,'MRP.xlsx','I10')
    result,_=reconcile_industrial_requirements(original,[window],pair=('M-X','item:P'),decision_day=4,
        policy='source_weekly_with_committed_floor_v1')
    assert all(r in result for r in original)
    assert sum(r.qty for r in result)==pytest.approx(220)
    unchanged,_=reconcile_industrial_requirements(original,[],pair=('M-X','item:P'),decision_day=4,
        policy='source_weekly_with_committed_floor_v1')
    assert unchanged==original


def test_industrial_purchase_source_rejects_future_version_and_overlapping_window():
    from etudecas.simulation.engine.mrp_planning import Requirement,IndustrialPlanningWindow,reconcile_industrial_requirements
    kwargs=dict(pair=('M-X','item:P'),decision_day=4,policy='source_weekly_with_committed_floor_v1')
    future=IndustrialPlanningWindow(11,11,18,100,5,'MRP.xlsx','I10')
    with pytest.raises(ValueError):reconcile_industrial_requirements([Requirement('own',12,30)],[future],**kwargs)
    current=IndustrialPlanningWindow(11,11,18,100,4,'MRP.xlsx','I10')
    with pytest.raises(ValueError):reconcile_industrial_requirements([Requirement('own',12,30)],[current,current],**kwargs)


def test_industrial_purchase_current_week_only_uses_frozen_remaining_days():
    from etudecas.simulation.engine.mrp_planning import IndustrialComponentPlanningCalendar,reconcile_industrial_requirements
    pair=('M-X','item:P')
    source=lambda start,qty:dict(period_start_day=start,period_days=7,qty=qty,source_file='MRP.xlsx',source_cells='I10')
    payload=dict(schema_version=1,origin='2025-01-01',scenario_id='memory',
        semantics='industrial_total_gross_requirements_planning_only',versioned_series=[dict(
            node_id=pair[0],item_id=pair[1],uom='UN',repeat_period_days=0,period_days=7,period_anchor_day=4,
            current_bucket_policy='freeze_previous_exclude_current_vintage',missing_future_policy='unprovided_not_observed_zero',
            versions=[dict(known_day=4,rows=[source(11,70),source(25,210)]),dict(known_day=11,rows=[source(18,140)])])])
    calendar=IndustrialComponentPlanningCalendar(payload,pair_uoms={pair:'UN'},origin_date='2025-01-01')
    windows=calendar.windows(pair,decision_day=13,first_day=14,through_day=31)
    assert [(w.first_day,w.end_day_exclusive,w.qty,w.known_day) for w in windows]==[(14,18,40,4),(18,25,140,11)]
    result,_=reconcile_industrial_requirements([],windows,pair=pair,decision_day=13,
        policy='source_weekly_with_committed_floor_v1')
    assert sum(r.qty for r in result if r.due_day<18)==40
    assert not any(r.due_day<=13 or r.due_day>=25 for r in result)


def test_weekly_industrial_purchase_network_nets_firm_once_and_keeps_committed_BOM():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import Requirement,FirmReceipt,LotSizing,IndustrialPlanningWindow
    pair,policy=weekly_purchase_case()
    calendar=e.purchase_review_calendar(tuple((d,d+10) for d in range(4,40)),policy=policy,pair=pair,
        origin_date='2025-01-01',through_day=32)
    plans,requirements,audits=e.plan_component_network(decision_day=4,
        requirements_by_pair={pair:[Requirement('opening-pack:OF',12,10),Requirement('derived:future',15,100)]},
        available_by_pair={pair:0},firm_receipts_by_pair={pair:[FirmReceipt('initial-known',14,40,'confirmed')]},
        transport_sources_by_pair={},bom_by_pair={},lead_days_by_pair={pair:10},lot_sizing_by_pair={pair:LotSizing(integer=True)},
        reserve_targets_by_pair={pair:0},coverage_days_by_pair={pair:1},active_campaigns_by_pair={},
        industrial_windows_by_pair={pair:[IndustrialPlanningWindow(11,11,18,80,4,'MRP.xlsx','I10')]},
        industrial_target_context_by_pair={pair:dict(window_days=30,fixed_floor_qty=0,target_days=0,safety_floor_qty=0,safety_days=0,legacy_rate=0)},
        industrial_requirement_reconciliation_policy='separate_own_and_other_v1',industrial_purchase_source_pairs={pair},
        anticipated_need_by_pair={pair:dict(source_working_days=2,origin_weekday=2,fixed_floor_qty=0,fixed_floor_mode='additive')},
        availability_by_release_by_pair={pair:calendar})
    assert sum(r.qty for r in requirements[pair])==80
    assert any(r.requirement_id=='opening-pack:OF' and r.due_day==12 and r.qty==10 for r in requirements[pair])
    assert sum(p.qty for p in plans[pair].proposals)==40
    assert all(p.release_day==4 for p in plans[pair].proposals)
    assert audits[pair]['industrial_requirement_reconciliation_policy']=='source_weekly_with_committed_floor_v1'
    protected=audits[pair]['anticipated_requirements']
    assert sum(r.qty for r in protected)==pytest.approx(80)
    assert [(r.due_day,r.qty) for r in protected]==[(8,30),(9,10),(12,10),(13,10),(14,10),(15,10)]


def opening_review_case(*, model=False, allow_return=False):
    from collections import defaultdict
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import FirmReceipt,Requirement
    pair=('M-X','item:P')
    raw=dict(order_type='opening_purchase_order',node_id=pair[0],item_id=pair[1],src_node_id='S-X',
        receipt_qty=100,physical_delivery_day=20,arrival_day=20,source_file='Extract.xlsx',source_row=9)
    availability=e.OpeningPurchaseAvailability([raw],item_unit_map={'item:P':'UN'})
    identity=e.OpeningPurchaseAvailability.marker_for('Extract.xlsx',9)
    policy=dict(schema_version=1,mode='known_need_and_protection_v1',review_weekday=6,
        source_file='Extract.xlsx',assumption='explicit scenario',rows=[dict(source_row=9,replannable=True,
        transport_departed=False,receipt_executed=False,replannable_until_day=19)])
    if model:policy.update(coverage_basis='model_projection',allow_return_to_original=allow_return)
    permissions=e.resolve_opening_purchase_postponement(policy,availability=availability,origin_date='2025-01-01')
    return dict(permissions=permissions,decision_day=4,origin_date='2025-01-01',horizon_day=70,
        availability=availability,stock={pair:0},firm_snapshot={pair:[FirmReceipt(identity,20,100,'in_transit')]},
        requirements_by_pair={pair:[Requirement('need',50,100)]},plan_audits={pair:{}},industrial_windows={},
        pipeline=defaultdict(list,{20:[(*pair,100,identity)]}),pending_receipt_calendar=None,
        commitments={pair:{identity:(20,100,'opening_purchase_order')}},order_rows=[dict(mrp_order_id=identity)],
        shipment_rows=[dict(src_node_id='S-X',dst_node_id=pair[0],item_id=pair[1],shipped_qty=100,arrival_day=20,
            transport_cost_basis='opening_order_book',day=0)],audit_rows=[],total_days=365,safety_source_days_by_pair={}),policy


def test_opening_model_projection_is_explicit_and_default_unknown_coverage_does_not_move():
    from etudecas.simulation.engine import run_first_simulation as e
    import json
    k,_=opening_review_case()
    assert not e.apply_opening_purchase_postponement(**k)
    k,_=opening_review_case(model=True)
    assert e.apply_opening_purchase_postponement(**k)
    assert k['audit_rows'][-1]['new_available_day']==50
    snapshot=json.loads(k['audit_rows'][-1]['planning_snapshot_json'])
    assert snapshot['coverage_basis']=='model_projection' and snapshot['source_windows']==[]


def test_opening_model_return_keeps_original_bound_identity_and_expiry():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import Requirement
    k,_=opening_review_case(model=True,allow_return=True);pair=('M-X','item:P')
    assert e.apply_opening_purchase_postponement(**k)
    identity=next(iter(k['permissions']))
    k['decision_day']=11;k['requirements_by_pair'][pair]=[Requirement('earlier',25,100)]
    assert e.apply_opening_purchase_postponement(**k)
    assert k['commitments'][pair][identity][:2]==(25,100)
    assert k['pipeline'][25]==[(*pair,100,identity)] and not k['pipeline'][50]
    k['decision_day']=18;k['requirements_by_pair'][pair]=[Requirement('earliest',19,100)]
    assert e.apply_opening_purchase_postponement(**k)
    assert k['commitments'][pair][identity][:2]==(20,100)
    k,_=opening_review_case(model=True,allow_return=True)
    assert e.apply_opening_purchase_postponement(**k)
    k['decision_day']=25;k['requirements_by_pair'][pair]=[Requirement('later',60,100)]
    assert not e.apply_opening_purchase_postponement(**k)
    assert k['commitments'][pair][identity][:2]==(50,100)
    assert len(k['order_rows'])==1 and k['shipment_rows'][0]['shipped_qty']==100


def test_opening_model_return_requires_explicit_permission_and_valid_coverage():
    from etudecas.simulation.engine import run_first_simulation as e
    k,policy=opening_review_case()
    for extra in ({'coverage_basis':'invented'},{'allow_return_to_original':True},
                  {'coverage_basis':'model_projection','allow_return_to_original':1}):
        with pytest.raises(ValueError):
            e.resolve_opening_purchase_postponement(dict(policy,**extra),availability=k['availability'],origin_date='2025-01-01')


def test_weekly_supplier_offers_keep_own_calendar_price_and_legacy_validation():
    from dataclasses import replace
    from etudecas.simulation.engine.mrp_planning import SupplierOffer,LotSizing,Requirement,plan_sourced_requirements
    slow=SupplierOffer('cheap',1,'EUR','UN',14,LotSizing(integer=True),
        ((4,14),(11,21),(18,28),(25,35)),review_calendar=True)
    fast=SupplierOffer('fast',2,'EUR','UN',7,LotSizing(integer=True),
        ((4,7),(11,14),(18,21),(25,28)),review_calendar=True)
    args=dict(decision_day=0,available_qty=0,requirements=[Requirement('urgent',9,100)],firm_receipts=(),primary=slow,backups=(fast,))
    result=plan_sourced_requirements(**args)
    assert sum(p.qty for p in result.plan.proposals)==100
    assert [(p.supplier_id,p.proposal.release_day,p.proposal.available_day) for p in result.proposals]==[('fast',4,7)]
    with pytest.raises(ValueError):plan_sourced_requirements(**dict(args,primary=replace(slow,review_calendar=False)))


def exclusive_horizon_case():
    from etudecas.simulation.engine.mrp_planning import IndustrialComponentPlanningCalendar
    pair=('M-X','item:P')
    source=lambda start,qty:dict(period_start_day=start,period_days=7,qty=qty,source_file='MRP.xlsx',source_cells=f'I{start}')
    payload=dict(schema_version=1,origin='2025-01-01',scenario_id='memory',
        semantics='industrial_total_gross_requirements_planning_only',versioned_series=[dict(
            node_id=pair[0],item_id=pair[1],uom='UN',repeat_period_days=0,period_days=7,period_anchor_day=4,
            current_bucket_policy='freeze_previous_exclude_current_vintage',missing_future_policy='unprovided_not_observed_zero',
            versions=[dict(known_day=4,rows=[source(11,100),source(25,0)]),
                      dict(known_day=11,rows=[source(18,50)])])])
    calendar=IndustrialComponentPlanningCalendar(payload,pair_uoms={pair:'UN'},origin_date='2025-01-01')
    coverage=dict(schema_version=1,origin='2025-01-01',semantics='global_source_snapshot_week_bounds',rows=[
        dict(known_day=d,first_period_start_day=d,last_period_start_day=d+364,period_days=7,
             source_file='MRP.xlsx',source_cells=f'A{d}:A{d+1};G{d}:G{d+1}',
             present_pairs=[dict(node_id=pair[0],item_id=pair[1])]) for d in (4,11)])
    return pair,calendar,coverage


def test_exclusive_horizon_distinguishes_actual_zero_from_missing_and_keeps_horizon_bounds():
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage
    pair,calendar,payload=exclusive_horizon_case()
    policy=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01')
    actual,omitted=policy.select(pair,decision_day=4,first_day=5,through_day=400)
    assert [(w.period_start_day,w.qty,w.source_cells) for w in actual]==[(11,100,'I11'),(25,0,'I25')]
    assert 18 in {w.period_start_day for w in omitted} and 25 not in {w.period_start_day for w in omitted}
    assert min(w.first_day for w in omitted)==18
    assert max(w.end_day_exclusive for w in omitted)==375
    assert all(w.known_day==4 and not hasattr(w,'qty') for w in omitted)
    assert policy.select(pair,decision_day=0,first_day=1,through_day=30)==((),())


def test_exclusive_horizon_current_week_is_previous_known_and_only_remaining_days():
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage
    pair,calendar,payload=exclusive_horizon_case()
    policy=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01')
    actual,omitted=policy.select(pair,decision_day=13,first_day=14,through_day=31)
    assert [(w.first_day,w.end_day_exclusive,w.qty,w.known_day) for w in actual]==[(14,18,pytest.approx(400/7),4),(18,25,50,11)]
    assert [(w.first_day,w.end_day_exclusive,w.known_day) for w in omitted]==[(25,32,11)]
    assert not any(w.first_day<=13 for w in (*actual,*omitted))


def test_exclusive_horizon_entire_pair_absent_in_new_global_version_stays_unknown():
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage,Requirement,exclude_unreported_revocable_requirements
    pair,calendar,payload=exclusive_horizon_case()
    payload['rows'].append(dict(known_day=18,first_period_start_day=18,last_period_start_day=382,period_days=7,
        source_file='MRP.xlsx',source_cells='A18:A19;G18:G19',present_pairs=[]))
    policy=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01')
    actual,omitted=policy.select(pair,decision_day=18,first_day=19,through_day=40)
    assert [(w.first_day,w.end_day_exclusive,w.known_day) for w in actual]==[(19,25,11)]
    assert omitted==()
    original=[Requirement('derived:unknown',26,100)]
    retained,audit=exclude_unreported_revocable_requirements(original,omitted,decision_day=18)
    assert retained==original and audit==[]


def test_exclusive_horizon_removes_only_revocable_requirements_with_exact_audit():
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage,Requirement,exclude_unreported_revocable_requirements
    pair,calendar,payload=exclusive_horizon_case()
    _,omitted=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01').select(
        pair,decision_day=4,first_day=5,through_day=31)
    original=[Requirement('derived:shifted',20,100),Requirement('external:other',21,20),
        Requirement('campaign:firm',20,30),Requirement('opening-pack:OF',22,40),
        Requirement('opening_production:OF',23,50),Requirement('reserve:floor',19,10),
        Requirement('backlog:today',4,7),Requirement('derived:after',40,90),Requirement('derived:sourcezero',26,60)]
    retained,audit=exclude_unreported_revocable_requirements(original,omitted,decision_day=4)
    assert retained==original[2:]
    assert len(audit)==1
    a=audit[0]
    assert (a['before_qty'],a['removed_revocable_qty'],a['preserved_committed_qty'],a['preserved_reserve_qty'],a['after_qty'])==(250,120,120,10,130)
    assert a['removed_requirements']==[['derived:shifted',20,100],['external:other',21,20]]
    assert a['status']=='unreported_week_assumed_no_revocable_need_not_observed_zero'
    assert 'source_qty' not in a and 'source_cells' not in a


@pytest.mark.parametrize('fault',['missing_proof','wrong_origin','short_horizon','duplicate','future_presence','unknown_pair','missing_global','legacy_fallback'])
def test_exclusive_horizon_rejects_unproven_or_inconsistent_coverage(fault):
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage
    pair,calendar,payload=exclusive_horizon_case()
    if fault=='missing_proof':payload['rows'][0]['source_cells']=''
    elif fault=='wrong_origin':payload['origin']='2025-01-02'
    elif fault=='short_horizon':payload['rows'][0]['last_period_start_day']=25
    elif fault=='duplicate':payload['rows'].append(payload['rows'][0])
    elif fault=='future_presence':payload['rows'].append(dict(payload['rows'][0],known_day=18,first_period_start_day=18,last_period_start_day=382))
    elif fault=='unknown_pair':payload['rows'][0]['present_pairs'][0]['node_id']='UNKNOWN'
    elif fault=='missing_global':payload['rows'].pop()
    elif fault=='legacy_fallback':calendar.missing_period_policy='last_known_period_v1'
    with pytest.raises(ValueError):IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01')


def test_exclusive_horizon_network_deducts_receipts_once_and_keeps_missing_policy_default():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage,Requirement,FirmReceipt,LotSizing
    pair,calendar,payload=exclusive_horizon_case()
    actual,omitted=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01').select(
        pair,decision_day=4,first_day=5,through_day=24)
    args=dict(decision_day=4,requirements_by_pair={pair:[Requirement('derived:shifted',20,100)]},
        available_by_pair={pair:10},firm_receipts_by_pair={pair:[FirmReceipt('initial',10,40,'confirmed')]},
        transport_sources_by_pair={},bom_by_pair={},lead_days_by_pair={pair:2},lot_sizing_by_pair={pair:LotSizing(integer=True)},
        reserve_targets_by_pair={pair:0},coverage_days_by_pair={pair:1},active_campaigns_by_pair={},
        industrial_windows_by_pair={pair:actual},industrial_purchase_source_pairs={pair},
        industrial_target_context_by_pair={pair:dict(window_days=30,fixed_floor_qty=0,target_days=0,safety_floor_qty=0,safety_days=0,legacy_rate=0)},
        industrial_requirement_reconciliation_policy='separate_own_and_other_v1')
    legacy=e.plan_component_network(**args)
    explicit_default=e.plan_component_network(**args,industrial_unreported_windows_by_pair=None)
    assert legacy==explicit_default
    assert sum(r.qty for r in legacy[1][pair])==pytest.approx(200)
    plans,needs,audits=e.plan_component_network(**args,industrial_unreported_windows_by_pair={pair:omitted})
    assert sum(r.qty for r in needs[pair])==pytest.approx(100)
    assert sum(p.qty for p in plans[pair].proposals)==50
    assert audits[pair]['industrial_unreported_windows'][0]['removed_revocable_qty']==100
    assert len(audits[pair]['industrial_windows'])==1 and audits[pair]['industrial_windows'][0]['source_qty']==100


def test_exclusive_horizon_policy_requires_explicit_interpretation_and_scope():
    from etudecas.simulation.engine import run_first_simulation as e
    pair,_=weekly_purchase_case()
    policy=dict(schema_version=1,mode='source_weekly_with_committed_floor_v1',pairs=[dict(node_id=pair[0],item_id=pair[1])],
        assumption='scenario',unreported_weeks_policy='no_revocable_need_within_declared_horizon_v1')
    assert e.resolve_purchase_calendar_or_source_policy(policy,mode=policy['mode'],eligible_pairs={pair},origin_date='2025-01-01')==policy
    with pytest.raises(ValueError):e.resolve_purchase_calendar_or_source_policy(dict(policy,unreported_weeks_policy='observed_zero'),
        mode=policy['mode'],eligible_pairs={pair},origin_date='2025-01-01')


@pytest.mark.parametrize('source,committed,length',[(100,0,7),(100,0.3333333333333333,7),(400/7,10,4),(0.7,0.1,7),(100000001,1,7)])
def test_industrial_source_daily_float_publication_conserves_exact_forecast_budget(source,committed,length):
    from fractions import Fraction
    from etudecas.simulation.engine.mrp_planning import Requirement,IndustrialPlanningWindow,reconcile_industrial_requirements
    original=[Requirement('opening-pack:committed',12,committed)] if committed else []
    window=IndustrialPlanningWindow(11,11,11+length,source,4,'MRP.xlsx','I10')
    result,_=reconcile_industrial_requirements(original,[window],pair=('M-X','item:P'),decision_day=4,
        policy='source_weekly_with_committed_floor_v1')
    assert sum((Fraction(str(r.qty)) for r in result),Fraction(0))==Fraction(str(source))
    assert all(11<=r.due_day<11+length and r.qty>0 for r in result)
    assert len({r.requirement_id for r in result})==len(result)
    assert all(r in result for r in original)


@pytest.mark.parametrize('committed,bom,source,expected,later',[
    (100,0,100,{20:100},100),
    (60,100,100,{10:40,20:60,30:60},60),
    (150,100,100,{20:150,30:100},100),
    (0,100,100,{10:100},0),
    (0,100,0,{30:100},0),
    (0,60,100,{10:100},0),
    (0,0,0,{},0),
])
def test_purchase_envelope_committed_fifo_and_cumulative_budget(committed,bom,source,expected,later):
    from collections import defaultdict
    from fractions import Fraction
    from etudecas.simulation.engine.mrp_planning import Requirement,IndustrialPlanningWindow,reconcile_industrial_purchase_envelope
    rows=([Requirement('opening-pack:OF',20,committed)] if committed else [])
    rows+=([Requirement('derived:BOM',30,bom)] if bom else [])
    windows=[IndustrialPlanningWindow(d,d,d+1,source if d==10 else 0,0,'memory.xlsx',f'I{d}') for d in range(1,31)]
    result,_,audit=reconcile_industrial_purchase_envelope(rows,windows,(),pair=('M-X','P'),decision_day=0)
    actual=defaultdict(Fraction)
    for row in result:actual[row.due_day]+=Fraction(str(row.qty))
    assert dict(actual)==expected
    assert Fraction(audit['retained_requirement_qty'])==max(committed+bom,source)
    assert Fraction(audit['source_assigned_later_committed_qty'])==later
    assert all(r in result for r in rows if r.requirement_id.startswith('opening-pack:'))
    assert all(planned<=due for _,due,planned,_ in audit['revocable_allocations'])
    for day,i,e,b,res,env,total,gap in audit['cumulative_points']:
        assert Fraction(env)==max(Fraction(b),Fraction(res))
        assert Fraction(total)==Fraction(e)+Fraction(env)
        assert Fraction(gap)==max(0,Fraction(i)-Fraction(total))
    if committed==100 and bom==0:
        assert Fraction(next(p for p in audit['cumulative_points'] if p[0]==10)[-1])==100


def test_purchase_envelope_preserves_reserves_uncovered_and_model_omitted_weeks():
    from fractions import Fraction
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage,Requirement,reconcile_industrial_purchase_envelope
    pair,calendar,payload=exclusive_horizon_case()
    actual,omitted=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01').select(
        pair,decision_day=4,first_day=5,through_day=31)
    rows=[Requirement('opening-pack:OF',20,60),Requirement('derived:BOM',23,100),
          Requirement('reserve:floor',15,1000),Requirement('derived:before',7,7),Requirement('external:outside',40,13)]
    result,_,audit=reconcile_industrial_purchase_envelope(rows,actual,omitted,pair=pair,decision_day=4)
    assert all(r in result for r in (rows[0],*rows[2:]))
    assert Fraction(audit['retained_requirement_qty'])==160
    assert sum((Fraction(str(r.qty)) for r in result),Fraction(0))==1180
    assert sum((Fraction(q) for _,_,_,q in audit['revocable_allocations']),Fraction(0))==100
    assert audit['omitted_windows'] and all(len(w)==8 for w in audit['omitted_windows'])
    assert all(not r.requirement_id.startswith('external:industrial-purchase-envelope-complement') for r in result)


def test_purchase_envelope_network_exact_budget_no_extra_unit_and_default_unchanged():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningHorizonCoverage,Requirement,FirmReceipt,LotSizing
    pair,calendar,payload=exclusive_horizon_case()
    actual,omitted=IndustrialPlanningHorizonCoverage(payload,calendar=calendar,eligible_pairs={pair},origin_date='2025-01-01').select(
        pair,decision_day=4,first_day=5,through_day=24)
    args=dict(decision_day=4,requirements_by_pair={pair:[Requirement('derived:BOM',20,100)]},
        available_by_pair={pair:10},firm_receipts_by_pair={pair:[FirmReceipt('initial',10,40,'confirmed')]},
        transport_sources_by_pair={},bom_by_pair={},lead_days_by_pair={pair:2},lot_sizing_by_pair={pair:LotSizing(integer=True)},
        reserve_targets_by_pair={pair:0},coverage_days_by_pair={pair:1},active_campaigns_by_pair={},
        industrial_windows_by_pair={pair:actual},industrial_purchase_source_pairs={pair},
        industrial_target_context_by_pair={pair:dict(window_days=30,fixed_floor_qty=0,target_days=0,safety_floor_qty=0,safety_days=0,legacy_rate=0)},
        industrial_requirement_reconciliation_policy='separate_own_and_other_v1')
    assert e.plan_component_network(**args)==e.plan_component_network(**args,industrial_purchase_envelope_pairs=None)
    plans,needs,audits=e.plan_component_network(**args,industrial_unreported_windows_by_pair={pair:omitted},
        industrial_purchase_envelope_pairs={pair})
    from fractions import Fraction
    assert sum((Fraction(str(r.qty)) for r in needs[pair]),Fraction(0))==100
    assert sum(p.qty for p in plans[pair].proposals)==50
    assert audits[pair]['industrial_purchase_envelope']['retained_requirement_qty']=='100'
    assert 'industrial_unreported_windows' not in audits[pair]
    assert audits[pair]['industrial_windows'][0]['own_planned_qty']==100
    with pytest.raises(ValueError):e.plan_component_network(**args,industrial_purchase_envelope_pairs={pair})


def test_purchase_envelope_policy_requires_explicit_interpretation_exclusive_mode():
    from etudecas.simulation.engine import run_first_simulation as e
    pair,_=weekly_purchase_case()
    policy=dict(schema_version=1,mode='source_weekly_with_committed_floor_v1',pairs=[dict(node_id=pair[0],item_id=pair[1])],
        assumption='FIFO volume matching is a scenario',forecast_envelope_policy='declared_horizon_cumulative_max_v1')
    kw=dict(mode=policy['mode'],eligible_pairs={pair},origin_date='2025-01-01')
    assert e.resolve_purchase_calendar_or_source_policy(policy,**kw)==policy
    for bad in (dict(policy,forecast_envelope_policy='wrong'),
                dict(policy,unreported_weeks_policy='no_revocable_need_within_declared_horizon_v1')):
        with pytest.raises(ValueError):e.resolve_purchase_calendar_or_source_policy(bad,**kw)


def weekly_programme_case():
    from etudecas.simulation.engine.mrp_planning import WeeklyProductionProgramme,OrderProposal
    pair=('M-X','item:PF');a=('M-X','item:A');b=('M-X','item:B')
    payload=dict(schema_version=1,mode='current_week_existing_lot_v1',max_promotions_per_process=1,
        current_bucket_policy='latest_known_including_current',assumption='compatible budgets, no industrial OF identity',
        series=[dict(node_id=pair[0],output_item_id=pair[1],versions=[dict(known_day=4,period_start_day=4,
            period_end_day_exclusive=11,component_budgets=[
                dict(item_id=a[1],qty=110,uom='UN',source_file='MRP.xlsx',source_cells='I10'),
                dict(item_id=b[1],qty=22,uom='M',source_file='MRP.xlsx',source_cells='I11')])])])
    bom={pair:[(a,1),(b,.2)]};units={pair:'UN',a:'UN',b:'M'}
    book=WeeklyProductionProgramme(payload,bom_by_pair=bom,pair_uoms=units)
    args=dict(pair=pair,decision_day=5,proposals=[OrderProposal('future',20,23,23,100)],
        calendar=[(5,8),(6,9)],consumed={},committed={},available={a:100,b:20},capacity_qty=100)
    return book,args,payload,bom,units


def test_weekly_programme_advances_existing_whole_lot_with_explicit_residual():
    book,args,_,_,_=weekly_programme_case()
    row=book.select(**args)
    assert (row['qty'],row['release_day'],row['available_day'])==(100,5,8)
    assert row['original_proposal_id']=='future' and row['original_release_day']==20
    assert [(b['allocated_qty'],b['residual_qty']) for b in row['source_budgets']]==[(100,10),(20,2)]
    assert row['source_known_day']==4 and row['state']=='proposed'
    book.accept(row)
    assert book.select(**args) is None
    assert book.rows[args['pair']]['qty']==100


@pytest.mark.parametrize('fault',['future_known','material','capacity','engaged_plus_consumed','no_proposal','Sunday','pending_initial_Pack'])
def test_weekly_programme_cannot_promote_without_current_budget_and_full_feasibility(fault):
    book,args,_,_,_=weekly_programme_case();a=('M-X','item:A')
    if fault=='future_known':args['decision_day']=3
    elif fault=='material':args['available'][a]=99
    elif fault=='capacity':args['capacity_qty']=99
    elif fault=='engaged_plus_consumed':args.update(consumed={a:40},committed={a:60})
    elif fault=='no_proposal':args['proposals']=[]
    elif fault=='Sunday':args.update(decision_day=4,calendar=[(4,7)])
    elif fault=='pending_initial_Pack':args['opening_pack_pending_qty']=141780
    assert book.select(**args) is None and book.rows=={}


def test_weekly_programme_atomic_handoff_partial_execution_and_no_resurrection():
    book,args,_,_,_=weekly_programme_case();pair=args['pair']
    book.accept(book.select(**args));book.engage(pair,5,'CMP-existing')
    assert book.rows[pair]['state']=='engaged'
    book.execute(pair,5,'CMP-existing',40)
    assert book.rows[pair]['executed_qty']==40 and book.rows[pair]['state']=='engaged'
    book.execute(pair,6,'CMP-existing',60)
    assert book.rows[pair]['state']=='executed' and book.select(**args) is None
    assert sum(e.get('executed_today_qty',0) for e in book.events)==100
    with pytest.raises(ValueError):book.engage(pair,7,'cannot_reengage_executed')


def test_weekly_programme_network_replaces_credit_and_explodes_components_once():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import Requirement,LotSizing,FirmReceipt
    book,selection,_,bom,_=weekly_programme_case();pair=selection['pair'];a,b=(p for p,_ in bom[pair])
    inputs=dict(decision_day=5,snapshot_day=4,requirements=[Requirement('customer',30,100)],available_qty=0,
        firm_receipts=[],lead_days=3,lot_sizing=LotSizing(integer=True))
    _,old=e.dated_production_release(**inputs)
    row=book.select(**dict(selection,proposals=old.proposals))
    proof=e.programme_replacement_check(row,old,**inputs)
    assert proof['status']=='advanced_existing_lot'
    assert proof['before_proposed_qty']==proof['after_with_programme_qty']==100
    assert proof['remaining_proposals']==[] and inputs['firm_receipts']==[]
    # Normal campaign accounting, no parallel programme promise.
    network=dict(decision_day=5,requirements_by_pair={pair:inputs['requirements']},
        available_by_pair={pair:0,a:960,b:992},firm_receipts_by_pair={},transport_sources_by_pair={},bom_by_pair=bom,
        lead_days_by_pair={pair:3,a:1,b:1},lot_sizing_by_pair={pair:LotSizing(integer=True)},
        reserve_targets_by_pair={},coverage_days_by_pair={},
        active_campaigns_by_pair={pair:('real_campaign',60,40,7)})
    new=e.plan_component_network(**network)
    assert sum(p.qty for p in new[0][pair].proposals)==0
    assert sum(r.qty for r in new[1][a])==60
    assert sum(r.qty for r in new[1][b])==12
    assert sum(f.qty for f in new[2][pair]['firm_receipts'])==100
    # After completion, real held stock replaces the campaign: no remaining BOM.
    network.update(active_campaigns_by_pair={},firm_receipts_by_pair={pair:[FirmReceipt('held',8,100,'held')]})
    completed=e.plan_component_network(**network)
    assert not completed[0][pair].proposals and sum(r.qty for r in completed[1].get(a,()))==0


def test_weekly_programme_local_source_budget_keeps_raw_audit_and_nets_committed_once():
    from etudecas.simulation.engine import run_first_simulation as e
    from etudecas.simulation.engine.mrp_planning import IndustrialPlanningWindow,Requirement,reconcile_industrial_requirements
    book,args,_,_,_=weekly_programme_case();pair=args['pair'];a=('M-X','item:A')
    row=book.select(**args);book.accept(row)
    original={a:(IndustrialPlanningWindow(4,6,11,60,0,'MRP.xlsx','Iold'),)}
    assert e.programme_current_source_windows(original,book.rows.values(),decision_day=5,
        weekly_consumed={(4,a):40},source_purchase_pairs={a})==(original,[])
    book.engage(pair,5,'actual_campaign')
    windows,audit=e.programme_current_source_windows(original,book.rows.values(),decision_day=5,
        weekly_consumed={(4,a):40},source_purchase_pairs={a})
    assert original[a][0].qty==60
    assert windows[a][0].qty==70 and windows[a][0].known_day==4
    assert audit[0]['source_full_week_qty']==110 and audit[0]['model_week_consumed_qty']==40
    assert audit[0]['remaining_forecast_qty']==70 and audit[0]['previous_windows'][0][2]==60
    retained,_=reconcile_industrial_requirements([Requirement('campaign:remaining',6,60)],windows[a],
        pair=a,decision_day=5,policy='source_weekly_with_committed_floor_v1')
    assert sum(r.qty for r in retained)==pytest.approx(70)  # 60 engaged +10, never100+60 or70+60.
    assert e.programme_current_source_windows(original,book.rows.values(),decision_day=11,
        weekly_consumed={},source_purchase_pairs={a})==(original,[])


def test_weekly_programme_rejects_unknown_scope_units_and_unbounded_policy():
    import copy
    from etudecas.simulation.engine.mrp_planning import WeeklyProductionProgramme
    _,_,payload,bom,units=weekly_programme_case()
    for fault in ('scope','unit','unbounded','unknown_field'):
        bad=copy.deepcopy(payload)
        if fault=='scope':bad['series'][0]['output_item_id']='item:UNKNOWN'
        elif fault=='unit':bad['series'][0]['versions'][0]['component_budgets'][0]['uom']='KG'
        elif fault=='unbounded':bad['max_promotions_per_process']=2
        else:bad['invented']=1
        with pytest.raises(ValueError):WeeklyProductionProgramme(bad,bom_by_pair=bom,pair_uoms=units)
