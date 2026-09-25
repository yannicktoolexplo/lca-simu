"""Reproduce contract gaps in temporary directories, without running a simulation.

Probes record actual rejection/acceptance. A failed expected rejection is a
finding; this tool does not modify production code to make findings disappear.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


def probes():
    from etudecas.knowledge_graph.schema import validate_graph_contract
    from etudecas.simulation.engine.api import SimulationRequest, simulate, request_from_dict
    from etudecas.simulation.engine.run_first_simulation import choose_scenario
    from etudecas import decision_actions
    from etudecas.visualization.maps.scenario_comparison_payload import compute_observed_impact
    from etudecas.simulation.analysis_batch_common import apply_scales
    from etudecas.simulation.montecarlo import run_montecarlo_analysis as mc

    results = []
    base_kpis = {'total_demand': 100, 'fill_rate': 1, 'total_cost': 100}
    scores = [compute_observed_impact({**base_kpis, 'total_unreliable_loss_qty': loss}, base_kpis)['observed_impact_score']
              for loss in [1, 1000]]
    results.append({'probe': 'score_material_unit_rescaling', 'expected': 'same physical loss in kg or g gives invariant score',
                    'rejected': scores[0] == scores[1], 'score_1_kg': scores[0], 'score_1000_g': scores[1],
                    'note': 'The KPI input discards material units; there is no normalization in this score.'})
    graph = {"items": [{"id": "item:X"}], "nodes": [{"id": "F", "type": "factory",
        "inventory": {"raw": [{"item_id": "item:X", "initial": 10}]},
        "processes": [{"inputs": [{"item_id": "item:X", "ratio_per_batch": 1}],
                       "outputs": [{"item_id": "item:X", "qty": 1}]}]}],
        "edges": [], "scenarios": [{"id": "scn:BASE", "demand": []}]}
    try:
        unchanged = apply_scales(graph, 'scn:BASE', {'misspelled_capacity_scale': 0.5}) == apply_scales(graph, 'scn:BASE', {})
        rejected = False
    except ValueError:
        unchanged, rejected = None, True
    results.append({'probe': 'unknown_sensitivity_factor', 'expected': 'reject',
                    'rejected': rejected, 'same_as_neutral_graph': unchanged})
    for name, mutate in [
        ("negative_opening_inventory", lambda g: g['nodes'][0]['inventory']['raw'][0].update(initial=-1)),
        ("unknown_inventory_item", lambda g: g['nodes'][0]['inventory']['raw'][0].update(item_id='item:ABSENT')),
        ("negative_bom_ratio", lambda g: g['nodes'][0]['processes'][0]['inputs'][0].update(ratio_per_batch=-1)),
        ("edge_without_endpoints", lambda g: g['edges'].append({'id':'E','items':['item:X']})),
    ]:
        altered = copy.deepcopy(graph)
        mutate(altered)
        issues = validate_graph_contract(altered)
        results.append({'probe': name, 'expected': 'reject', 'rejected': any(i['level']=='error' for i in issues), 'issues': issues})
    try:
        chosen = choose_scenario(graph, 'scn:ABSENT')
        rejected = False
    except ValueError:
        chosen, rejected = {}, True
    results.append({'probe': 'unknown_scenario', 'expected': 'reject', 'rejected': rejected,
                    'requested': 'scn:ABSENT', 'actual': chosen.get('id')})
    with tempfile.TemporaryDirectory(prefix='etudecas-contract-review-') as temp:
        root = Path(temp)
        calls = []
        def fake_executor(**kwargs):
            calls.append({'days': kwargs['days'], 'extra_args': kwargs['extra_args']})
            return {'kpis': {}}, ''
        try:
            simulate(SimulationRequest(input_graph=graph, days=-1, common_random_numbers='false',
                                       output_dir=root/'api'), run_executor=fake_executor)
            rejected = False
        except (ValueError, TypeError):
            rejected = True
        results.append({'probe': 'direct_python_request_validation', 'expected': 'reject',
                        'rejected': rejected and not calls, 'executor_calls': calls})
        try:
            request_from_dict({'input_graph': graph, 'days': -1})
            rejected = False
        except ValueError:
            rejected = True
        results.append({'probe': 'json_negative_horizon_control', 'expected': 'reject', 'rejected': rejected})

        # Cache reuse after deleting its audit schedule. The engine is mocked;
        # cache behavior itself executes unchanged, on a throwaway directory.
        engine = root/'etudecas/simulation/engine/run_first_simulation.py'
        engine.parent.mkdir(parents=True)
        engine.write_text('# fixture')
        dependency = root/'etudecas/simulation/lot_policy/models.py'
        dependency.parent.mkdir(parents=True)
        dependency.write_text('VALUE = 1')
        engine.write_text('from etudecas.simulation.lot_policy.models import VALUE')
        with patch.object(mc, '__file__', str(root/'etudecas/simulation/montecarlo/run_montecarlo_analysis.py')):
            before = mc._implementation_fingerprint(engine)
            dependency.write_text('VALUE = 2')
            after = mc._implementation_fingerprint(engine)
        results.append({'probe': 'montecarlo_imported_sibling_change', 'expected': 'fingerprint changes',
                        'rejected': before != after, 'fingerprint_changed': before != after})
        (root/'graph.json').write_text('{}')
        reference = root/'reference'
        reference.mkdir()
        command = ['python','etudecas/simulation/engine/run_first_simulation.py','--input','graph.json',
                   '--output-dir',str(reference),'--days','1']
        (reference/'run_manifest.json').write_text(json.dumps({'simulator_command':command}))
        def fake_run(cmd, **kwargs):
            target = Path(cmd[cmd.index('--output-dir')+1])/'summaries'
            target.mkdir(parents=True)
            (target/'first_simulation_summary.json').write_text('{}')
            data = target.parent/'data'
            data.mkdir()
            for name in ['first_simulation_daily', 'production_demand_service_daily', 'production_output_products_daily', 'production_lot_events', 'production_lot_genealogy']:
                (data/(name+'.csv')).write_text('day,qty\n0,1\n')
            return SimpleNamespace(returncode=0)
        with patch.object(decision_actions,'REPO',root), patch.object(decision_actions.subprocess,'run',fake_run):
            targets = [{'item_id':'X','supplier_id':'S','dst_node_id':'F'}]
            decision_actions.execute_action(reference,root/'actions','safety_150',targets)
            (root/'actions/safety_150.csv').unlink()
            try:
                returned = decision_actions.execute_action(reference,root/'actions','safety_150',targets)
                rejected = False
            except ValueError:
                returned, rejected = None, True
            results.append({'probe':'action_cache_missing_schedule', 'expected':'reject',
                            'rejected':rejected, 'returned':str(returned)})

    import pandas as pd
    from etudecas.toolbox.validation_contracts import ResultValidator
    from etudecas.toolbox.validation_contracts import DataValidator
    from etudecas.toolbox.validation_contracts import weighted_mean
    result = ResultValidator({'score_bounds':{'enabled':True,'columns':['score'],'min':0,'max':1}}).validate(pd.DataFrame({'other':[2]}))
    results.append({'probe':'pack_missing_required_score','expected':'reject','rejected':result.status=='reject','status':result.status})
    result = DataValidator({'columns':{'count':{'type':'integer','required':True}}}).validate(pd.DataFrame({'count':[1.5]}))
    results.append({'probe':'pack_fractional_integer','expected':'reject','rejected':result.status=='reject','status':result.status})
    try:
        value = weighted_mean(pd.DataFrame({'a':[1.0],'b':[0.0]}),{'a':2,'b':-1}).iloc[0]
        rejected = False
    except ValueError:
        value, rejected = None, True
    results.append({'probe':'pack_negative_weight','expected':'reject','rejected':rejected,'actual_score':value})
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    rows=probes()
    report={'ok':all(r['rejected'] for r in rows),'probes':rows,
            'scope':'Deliberately invalid inputs and cache evidence, not numerical calibration.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
