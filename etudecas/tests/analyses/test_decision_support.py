import copy
import json

import pytest

from etudecas.decision_support import fifo_delay, score_breakdown, audit_losses, bottlenecks


def demand_rows():
    return [dict(day=0,node_id='C',item_id='P',demand_qty=10,served_qty=5,backlog_end_qty=5,required_with_backlog_qty=10),
            dict(day=1,node_id='C',item_id='P',demand_qty=10,served_qty=10,backlog_end_qty=5,required_with_backlog_qty=15),
            dict(day=2,node_id='C',item_id='P',demand_qty=0,served_qty=3,backlog_end_qty=2,required_with_backlog_qty=5)]


def test_fifo_delay_distinguishes_served_and_censored_demand():
    result=fifo_delay(demand_rows(),3)[0]
    assert result['same_day_service_lower_pct']==50
    assert result['same_day_service_upper_pct']==75
    assert result['mean_delay_served_fifo_days']==pytest.approx(8/18)
    assert result['oldest_unserved_fifo_days']==1
    assert result['ending_backlog']==2
    assert result['backlog_quantity_days']==12


@pytest.mark.parametrize('damage',['duplicate','missing','negative','nan','opening','balance'])
def test_fifo_rejects_invalid_or_unaged_demand(damage):
    rows=demand_rows()
    if damage=='duplicate': rows.append(copy.deepcopy(rows[0]))
    elif damage=='missing': rows.pop(1)
    elif damage=='opening': rows[0]['required_with_backlog_qty']=12
    elif damage=='balance': rows[0]['served_qty']=9
    else: rows[0]['demand_qty']=-1 if damage=='negative' else float('nan')
    with pytest.raises(ValueError): fifo_delay(rows,3)


def test_score_components_exclude_incomparable_quantities():
    k=dict(service_loss_pp=1,backlog_pct=2,replan_volume_pct=3,cost_delta_pct=4,loss_qty_pct=100,
           observed_impact_score=12)
    result=score_breakdown(k)
    assert result['components']=={'service':5, 'backlog':6, 'extra_cost':1}
    assert 'material_loss' not in result['components']
    k['observed_impact_score']=0
    with pytest.raises(ValueError): score_breakdown(k)


def test_unknown_cost_is_excluded_and_not_rendered_as_zero_score():
    result = score_breakdown(dict(service_loss_pp=1, backlog_pct=2, cost_delta_pct=None,
                                  observed_impact_score=11))
    assert result['total'] == 11
    assert result['components']['extra_cost'] is None
    assert result['contribution_pct']['extra_cost'] is None


def test_loss_audit_excludes_departures_outside_horizon_and_preserves_units(tmp_path):
    (tmp_path/'data').mkdir();(tmp_path/'summaries').mkdir()
    (tmp_path/'data/production_supplier_shipments_daily.csv').write_text(
        'day,shipment_id,src_node_id,item_id,uom,pulled_qty,shipped_qty\n'
        '0,S1,A,X,KG,10,8\n1,S2,B,Y,UN,100,90\n2,S3,B,Y,UN,100,0\n')
    (tmp_path/'summaries/first_simulation_summary.json').write_text(json.dumps({'kpis':{'total_unreliable_loss_qty':12}}))
    result=audit_losses(tmp_path,2)
    assert result['summary_matches']
    assert result['outside_horizon_qty']==100
    assert {r['uom'] for r in result['by_item']}=={'KG','UN'}


def test_bottlenecks_use_binding_input_and_explicit_causal_context(tmp_path):
    (tmp_path/'data').mkdir()
    (tmp_path/'data/production_constraint_daily.csv').write_text(
        'day,node_id,output_item_id,binding_input_item_id,binding_cause,shortfall_vs_lot_plan_qty\n'
        '0,F,P,X,input_shortage,10\n1,F,P,X,input_shortage,10\n')
    (tmp_path/'data/lot_causal_links.csv').write_text(
        'item_id,causal_root_id,entity_id\nX,E1,L1\nY,E2,L2\n')
    result=bottlenecks(tmp_path,{'edges':[{'from':'S','to':'F','items':['X']}]},tmp_path/'evidence')
    assert result['ranked'][0]['blocked_days']==2
    assert result['ranked'][0]['repeated_shortfall_qty']==20
    assert result['ranked'][0]['suppliers']==['S']
    assert result['explicit_causal_rows']==1
    assert result['causal_examples'][0]['entity_id']=='L1'


def test_rebuild_refuses_existing_directory(tmp_path, monkeypatch):
    from etudecas import decision_support as module
    def forbidden(*args, **kwargs):
        raise AssertionError('Must not execute a pipeline in an existing directory')
    monkeypatch.setattr(module.subprocess, 'run', forbidden)
    with pytest.raises(SystemExit) as error:
        module.main(['--run', str(tmp_path), '--rebuild'])
    assert error.value.code == 2


def test_failed_delivery_does_not_keep_an_old_success(tmp_path, monkeypatch):
    from etudecas import decision_support as module
    folder=tmp_path/'decision_support'
    folder.mkdir()
    (folder/'delivery.json').write_text('{"ok": true}')
    def fail(*args):
        raise ValueError('injected validation failure')
    monkeypatch.setattr(module, 'deliver', fail)
    with pytest.raises(ValueError, match='injected'):
        module.main(['--run', str(tmp_path)])
    record=json.loads((folder/'delivery.json').read_text())
    assert record['ok'] is False
    assert record['status']=='failed'


def test_failed_delivery_preserves_the_actual_failed_checks(tmp_path, monkeypatch):
    from etudecas import decision_support as module
    def fail(*args):
        raise module.DeliveryValidationError({'ok': False, 'browser_errors': ['backlog day mismatch'],
                                              'runs': [{'ok': True}]})
    monkeypatch.setattr(module, 'deliver', fail)
    with pytest.raises(module.DeliveryValidationError):
        module.main(['--run', str(tmp_path)])
    record = json.loads((tmp_path/'decision_support/delivery.json').read_text())
    assert record['browser_errors'] == ['backlog day mismatch']
    assert record['runs'] == [{'ok': True}]
    assert record['status'] == 'failed'
