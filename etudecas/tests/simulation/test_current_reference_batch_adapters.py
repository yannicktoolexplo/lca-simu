"""Current-reference batch adapters and quantity oracles; no full simulation.

Manifests are normal new fixture files. All quantities and runtime collaborators
are in memory; no integrity mutation, timestamps, disappearance or source writes.
"""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from types import SimpleNamespace

from etudecas.simulation import current_reference
from etudecas.simulation.analysis_batch_common import apply_scales
from etudecas.simulation.engine import mrp_planning as planning
from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.montecarlo.run_montecarlo_analysis import extract_manifest_command
from etudecas.simulation.sensibility.run_supplier_parameter_sensitivity import resolve_baseline_context

ROOT=Path(__file__).resolve().parents[3]
PAIR=('C-DEMO','item:PF')

def manifest(tmp_path):
    value={'customer_demand_policy':current_reference.CUSTOMER_DEMAND_MODE,
           'scan3_reconciliation_mode':'legacy_residual','graph':'prepared/current.json',
           'output':'prepared/nominal','days':1825,'scenario_id':'scn:BASE',
           'engine_arguments':['--input','prepared/current.json','--output-dir','prepared/nominal',
               '--scenario-id','scn:BASE','--days','1825','--output-profile','full','--skip-map',
               '--seed','42','--lot-trace','--use-bom-demand-signal-for-mrp']}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(value),encoding='utf-8')
    return path

def graph():
    rows=[{'node_id':PAIR[0],'item_id':PAIR[1],'uom':'UN','period_start_day':start,
           'period_days':7,'qty':14,'source_row':'Sheet!A2:C2','source_file':'memory_customer.xlsx'}
          for start in range(-2,369,7)]
    return {'items':[{'id':PAIR[1],'uom':'UN'}],'nodes':[],
            'scenarios':[{'id':'scn:BASE','demand':[{'node_id':PAIR[0],'item_id':PAIR[1],
                          'profile':[{'type':'constant','value':2}]}]}],
            'meta':{'customer_demand_history':{'schema_version':1,'origin':'2025-01-01',
                      'calendar':'monday_start','rows':rows},
                    'mrp_forecasts':{'rows':[dict(rows[0],vintage_day=-9)]}}}

def test_montecarlo_current_manifest_keeps_runtime_graph_and_policy(tmp_path):
    result=extract_manifest_command(manifest(tmp_path))
    assert Path(result['run_script']).name=='current_reference_sensitivity_runner.py'
    assert Path(result['input_path'])==ROOT/'prepared/current.json'
    assert Path(result['nominal_output_dir'])==ROOT/'prepared/nominal'
    assert result['scenario_id']=='scn:BASE' and result['manifest_days']==1825
    args=result['simulator_extra_args']
    assert '--input' not in args and '--output-dir' not in args
    assert args[args.index('--output-profile')+1]=='compact'
    assert args[args.index('--current-reference-scan3-mode')+1]=='legacy_residual'
    assert args[args.index('--seed')+1]=='42' and '--lot-trace' in args

def test_supplier_sensitivity_current_manifest_cannot_fall_back_to_historical_graph(tmp_path):
    runner,prepared,output,args=resolve_baseline_context(
        manifest(tmp_path),Path('old_engine.py'),Path('historical.json'),Path('historical_output'))
    assert runner.name=='current_reference_sensitivity_runner.py'
    assert prepared==ROOT/'prepared/current.json' and output==ROOT/'prepared/nominal'
    assert '--current-reference-scan3-mode' in args and '--use-bom-demand-signal-for-mrp' in args

def test_legacy_montecarlo_manifest_contract_is_preserved(tmp_path):
    path=tmp_path/'legacy.json'
    path.write_text(json.dumps({'simulator_command':['python','run_first_simulation.py',
        '--input','old.json','--output-dir','old_out','--days','7','--scenario-id','scn:BASE',
        '--output-profile','full','--seed','17','--skip-map']}),encoding='utf-8')
    value=extract_manifest_command(path)
    assert value['input_path']=='old.json' and value['nominal_output_dir']=='old_out'
    assert value['run_script']=='run_first_simulation.py'
    assert value['manifest_days']==7 and value['simulator_extra_args']==['--seed','17']

def test_unit_demand_scale_preserves_history_forecast_and_input():
    original=graph();before=deepcopy(original)
    result=apply_scales(original,'scn:BASE',{'demand_scale':1})
    assert result['meta']==original['meta']==before['meta']
    assert original==before

def test_scaled_history_drives_native_integer_orders_once_and_marks_hypothesis():
    original=graph();before=deepcopy(original)
    scaled=apply_scales(original,'scn:BASE',{'demand_scale':1.5})
    payload=scaled['meta']['customer_demand_history']
    assert all(row['qty']==21 and type(row['qty']) is int for row in payload['rows'])
    assert scaled['meta']['mrp_forecasts']['rows'][0]['qty']==21
    history=engine.SourceCustomerHistory(payload,demand_pairs={PAIR},origin_date='2025-01-01',sim_days=7)
    observed=[history.quantity(PAIR,decision_day=day,target_day=day)[0] for day in range(7)]
    assert observed==[3]*7  # 14/week * 3/2 =21/week, not the profile scale applied twice.
    audit=history.quantity(PAIR,decision_day=0,target_day=0)[1]
    assert audit['source_file'].startswith('scenario_scaled_customer_demand:')
    assert payload['rows'][0]['quantity_before_scenario_scale']==14
    assert original==before

def test_item_scale_combines_once_with_global_scale_and_rounds_weekly_down():
    original=graph();original['meta']['customer_demand_history']['rows'][0]['qty']=15
    scaled=apply_scales(original,'scn:BASE',{'demand_scale':1.1},demand_item_scale={PAIR[1]:1.5})
    expected=int(Fraction(15)*Fraction(11,10)*Fraction(3,2))
    assert expected==24 and scaled['meta']['customer_demand_history']['rows'][0]['qty']==expected
    assert original['meta']['customer_demand_history']['rows'][0]['qty']==15

def test_scaled_template_reaches_current_reference_future_projection():
    scaled=apply_scales(graph(),'scn:BASE',{'demand_scale':1.5})
    payload=scaled['meta']['customer_demand_history']
    restorations=current_reference.install_projection(planning,engine,SimpleNamespace(units={}),1825,
                           forecast_mode='coherent_scenario',customer_payload=payload)
    try:
        history=engine.SourceCustomerHistory(payload,demand_pairs={PAIR},origin_date='2025-01-01',sim_days=1825)
        quantity,audit=history.quantity(PAIR,decision_day=365,target_day=365)
        # Independent rational weekly growth and cumulative integer allocation.
        weekly=int(Fraction(21)*Fraction(105,100))
        expected=weekly*4//7-weekly*3//7
        assert expected==3 and quantity==expected
        assert audit['status']=='synthetic_52_week_orders_5pct_growth'
    finally:
        for module,name,old in reversed(restorations):setattr(module,name,old)


def test_integer_weekly_scaling_composes_decimal_factors_before_floor():
    for quantity, global_factor, item_factor, expected in [
        (100, 0.7, 0.1, 7),
        (10000, 0.94, 0.95, 8930),
    ]:
        original=graph()
        for key in ('customer_demand_history','mrp_forecasts'):
            original['meta'][key]['rows'][0]['qty']=quantity
        before=deepcopy(original)
        scaled=apply_scales(original,'scn:BASE',{'demand_scale':global_factor},
                            demand_item_scale={PAIR[1]:item_factor})
        rational=Fraction(quantity)*Fraction(str(global_factor))*Fraction(str(item_factor))
        assert rational.numerator//rational.denominator==expected
        for key in ('customer_demand_history','mrp_forecasts'):
            assert scaled['meta'][key]['rows'][0]['qty']==expected
        json.dumps(scaled)
        assert original==before
