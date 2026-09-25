import json
from types import SimpleNamespace

import pytest

from etudecas import decision_actions as actions


def test_action_replays_reference_in_isolated_directory_and_checks_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(actions,'REPO',tmp_path)
    engine=tmp_path/'etudecas/simulation/engine/run_first_simulation.py'
    engine.parent.mkdir(parents=True); engine.write_text('# test engine')
    (tmp_path/'graph.json').write_text('{}')
    reference=tmp_path/'reference';reference.mkdir()
    command=['python','etudecas/simulation/engine/run_first_simulation.py','--input','graph.json',
             '--output-dir',str(reference),'--days','2','--seed','42','--supplier-state-dependent-risks']
    (reference/'run_manifest.json').write_text(json.dumps({'simulator_command':command}))
    calls=[]
    def fake_run(cmd,**kwargs):
        calls.append(cmd)
        root=actions.Path(cmd[cmd.index('--output-dir')+1])
        (root/'summaries').mkdir(parents=True)
        (root/'summaries/first_simulation_summary.json').write_text('{}')
        data = root/'data'
        data.mkdir()
        for name in ['first_simulation_daily', 'production_demand_service_daily', 'production_output_products_daily', 'production_lot_events', 'production_lot_genealogy']:
            (data/(name+'.csv')).write_text('day,qty\n0,1\n')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(actions.subprocess,'run',fake_run)
    targets=[dict(item_id='X',supplier_id='S',dst_node_id='F')]
    root=actions.execute_action(reference,tmp_path/'out','safety_150',targets)
    assert root!=reference
    assert '--supplier-state-dependent-risks' in calls[0]
    assert calls[0][calls[0].index('--seed')+1]=='42'
    assert actions.execute_action(reference,tmp_path/'out','safety_150',targets)==root
    assert len(calls)==1
    (root/'summaries/first_simulation_summary.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='incomplete'):
        actions.execute_action(reference,tmp_path/'out','safety_150',targets)


def test_unknown_action_is_rejected_before_execution(tmp_path):
    with pytest.raises(ValueError,match='Unknown'):
        actions.execute_action(tmp_path,tmp_path/'out','unbounded',[])
