"""Oracles mémoire uniquement : aucun fichier, date, simulation ou sous-processus."""
from copy import deepcopy
from pathlib import Path

import pytest

from etudecas.simulation.analysis.production_daily_metrics import aggregate_production_days, daily_plan_metrics
from etudecas.simulation.analysis.factory_nervousness import build_factory_nervousness_rows


def row(day, planned, actual, *, programme=None, desired=0, **extra):
    result = dict(day=day,node_id='usine',output_item_id='article',
                  desired_qty=desired,planned_qty_after_lot_rule=planned,actual_qty=actual,
                  requested_lot_starts=0,actual_lot_starts=0)
    if programme is not None:
        result['programme_id']=programme
    result.update(extra)
    return result


def test_memory_multiple_passes_keep_one_remaining_programme():
    source=[row(0,p,600,programme='campagne') for p in [2400,1800,1200,600]]
    before=deepcopy(source)
    value,=aggregate_production_days(source)
    assert value['actual_qty']==2400
    assert value['planned_qty_after_lot_rule']==2400
    assert value['shortfall_vs_lot_plan_qty']==0
    assert daily_plan_metrics(source)['line_adherence']==1
    assert daily_plan_metrics(source)['line_nervousness'] is None
    assert source==before


def test_memory_independent_programmes_and_explicit_new_requirements():
    source=[row(0,200,200,programme='premier',desired=200,desired_signal_kind='new_requirement',desired_signal_id='besoin1'),
            row(0,300,100,programme='second',desired=300,desired_signal_kind='new_requirement',desired_signal_id='besoin2'),
            row(0,200,200,programme='second')]
    value,=aggregate_production_days(source)
    assert value['actual_qty']==500
    assert value['planned_qty_after_lot_rule']==500
    assert value['desired_qty']==500
    # Mixed observations do not certify that every signal is a new requirement.
    assert value['new_requirement_qty'] is None
    assert daily_plan_metrics(source)['line_adherence']==1


def test_memory_blocked_campaign_is_not_ten_new_orders():
    source=[row(day,600,0,programme='bloquee') for day in range(10)]
    values=aggregate_production_days(source)
    assert sum(v['planned_qty_after_lot_rule'] for v in values)==6000  # kg-jours de signal
    assert all(v['new_requirement_qty'] is None for v in values)
    assert daily_plan_metrics(source)['production_replanning_count'] is None
    actual=build_factory_nervousness_rows(source,[],horizon_days=10)[0]
    assert actual['actual_qty_total']==0
    assert actual['true_plan_revision_count'] is None


def test_memory_true_revision_requires_same_dated_proposal_target():
    first=row(0,100,20,proposal_id='proposition',proposal_version='version1',
              proposal_due_day=10,proposal_known_day=0,proposal_qty=100)
    second=row(1,80,30,proposal_id='proposition',proposal_version='version2',
               proposal_due_day=10,proposal_known_day=1,proposal_qty=120)
    daily=aggregate_production_days([first,second])
    assert daily[0]['plan_revision_count'] is None
    assert daily[1]['plan_revision_count']==1
    assert daily[1]['plan_revision_magnitude_pct']==pytest.approx(100*20/120)
    assert daily_plan_metrics([first,second])['line_nervousness']==1
    future=dict(second,proposal_known_day=2)
    with pytest.raises(ValueError,match='connue après'):
        aggregate_production_days([first,future])


def test_memory_unknown_origin_and_same_version_do_not_invent_revisions():
    source=[row(0,600,200),row(0,400,400),row(1,600,0)]
    values=aggregate_production_days(source)
    assert values[0]['planned_qty_after_lot_rule']==600
    assert values[0]['signal_status']=='origine_inconnue'
    assert all(v['plan_revision_count'] is None for v in values)
    source=[row(d,p,a,proposal_id='proposition',proposal_version='version1',
                proposal_due_day=10,proposal_known_day=0,proposal_qty=600)
            for d,p,a in [(0,600,200),(1,400,400)]]
    assert daily_plan_metrics(source)['production_replanning_count']==0
    assert aggregate_production_days(source)[1]['plan_revision_magnitude_pct']==0


def test_memory_new_requirement_identity_is_not_recounted_next_day():
    source=[row(d,100,0,desired=100,desired_signal_kind='new_requirement',desired_signal_id='evenement') for d in [0,1]]
    values=aggregate_production_days(source)
    assert [v['new_requirement_qty'] for v in values]==[100,0]
    assert [v['desired_qty'] for v in values]==[100,0]
    source[1]['desired_qty']=120
    with pytest.raises(ValueError,match='événement'):
        aggregate_production_days(source)


def test_memory_sensitivity_uses_daily_execution_and_preserves_unknown(monkeypatch):
    # Only replace a reader in memory; no file/fixture is created or altered.
    from etudecas.simulation.sensibility import run_supplier_parameter_sensitivity as sensitivity
    source=[row(0,p,600) for p in [2400,1800,1200,600]]
    monkeypatch.setattr(sensitivity,'read_csv_rows',lambda path: source if path.name=='production_constraint_daily.csv' else [])
    metrics=sensitivity.derived_case_kpis(Path('unused_memory_path'))
    assert metrics['line_adherence']==1
    assert metrics['line_nervousness'] is None
    assert metrics['production_replanning_count'] is None
    assert metrics['planning_semantics_status']=='revision_inconnue'


def test_memory_unknown_revision_prevents_a_certified_ranking():
    from etudecas.simulation.sensibility import run_supplier_parameter_sensitivity as sensitivity
    candidate={'level':1,'kpi::fill_rate':1,'kpi::ending_backlog':0,
               'kpi::line_nervousness':None,'kpi::production_replanning_count':None,
               'kpi::production_replanning_rate':None}
    assert not sensitivity.is_case_acceptable(candidate,candidate,0.95)
    spec=dict(parameter_key='capacity',parameter_group='capacity',parameter_label='capacité',safe_direction='lower_is_riskier')
    result=sensitivity.summarize_parameter(spec,[candidate],candidate,service_threshold=.95,cost_increase_pct=.1)
    assert result['assessment_status']=='donnees_insuffisantes'
    assert result['baseline_contiguous_safe_low'] is None
    assert result['line_nervousness_max'] is None
    assert result['first_unacceptable_level'] is None
    assert 'non évaluable' in sensitivity.safe_range_label(result)


def test_memory_global_adherence_is_invariant_to_units_of_another_article():
    first=row(0,100,100)
    second=dict(row(0,100,0),output_item_id='autre_article')
    assert daily_plan_metrics([first,second])['line_adherence']==0.5
    converted=dict(first,planned_qty_after_lot_rule=100000,actual_qty=100000)
    assert daily_plan_metrics([converted,second])['line_adherence']==0.5
