"""Contrôles mémoire : les inconnues ne deviennent ni zéro ni rang sûr.

Pas de fichier, fixture persistante, moteur, subprocess ou modification de date.
"""
from pathlib import Path
import json

import pytest

from etudecas.simulation.sensibility import run_supplier_risk_campaign as risk


def metrics(*, fill=1.0, identified=True):
    return dict(fill_rate=fill,ending_backlog=0,total_cost=100,total_holding_cost=10,
        total_shipped=1000,total_unreliable_loss_qty=0,derived_product_availability=1,
        derived_line_adherence=1,derived_production_replanning_count=0 if identified else None,
        derived_line_nervousness=0 if identified else None,derived_material_delay_days=0,
        derived_raw_material_stockout_days=0,derived_inventory_cost=10)


def make_case(supplier='fournisseur',family='capacity',*,identified=True,fill=.95):
    return risk.case_row(supplier_id=supplier,family_key=family,case_id='cas',event_row=None,
        metrics=metrics(fill=fill,identified=identified),baseline_metrics=metrics(identified=identified),
        case_dir=Path('unused_memory_path'))


def test_memory_extract_keeps_none_and_semantics_with_known_physical_metrics(monkeypatch):
    monkeypatch.setattr(risk,'derived_case_kpis',lambda _:dict(line_nervousness=None,
        production_replanning_count=None,line_adherence=.8,planning_semantics_status='revision_inconnue'))
    result=risk.extract_metrics(Path('unused_memory_path'),{'kpis':{'fill_rate':.95,'total_shipped':1000}})
    assert result['fill_rate']==.95 and result['total_shipped']==1000
    assert result['derived_line_nervousness'] is None
    assert result['derived_production_replanning_count'] is None
    assert result['derived_planning_semantics_status']=='revision_inconnue'
    assert result['total_cost'] is None


def test_memory_unknown_revisions_preserve_known_service_impact_without_global_score():
    result=risk.impact_reading_from_metrics(metrics(fill=.95,identified=False),metrics(identified=False))
    assert result['score_decisionnel_modele'] is None
    assert result['assessment_status']=='donnees_insuffisantes'
    assert result['components']['service']==pytest.approx(1)
    assert result['components']['nervousness'] is None
    assert result['components']['replanning'] is None
    assert result['impact_metier_score']==pytest.approx(1)
    assert result['impact_metier_kpi']=='Fill rate client'
    assert set(result['missing_components'])=={'replanning','nervousness'}


def test_memory_complete_score_keeps_original_weighted_formula():
    result=risk.impact_reading_from_metrics(metrics(fill=.95),metrics())
    assert result['assessment_status']=='evaluable'
    assert result['score_decisionnel_modele']==pytest.approx(.22)
    assert result['missing_components']==[]


def test_memory_case_and_csv_refresh_preserve_unknown_deltas():
    row=make_case(identified=False)
    assert row['line_nervousness_delta'] is None
    assert row['production_replanning_delta'] is None
    assert row['fill_rate_delta_pts']==-5
    assert row['impact_score'] is None and row['score_decisionnel_pct'] is None
    csv_row={k:'' if v is None else str(v) for k,v in row.items()}
    refreshed=risk.enrich_existing_case_row(csv_row)
    assert refreshed['score_decisionnel_modele'] is None
    assert refreshed['line_nervousness_delta'] is None
    assert refreshed['production_replanning_delta'] is None
    assert refreshed['assessment_status']=='donnees_insuffisantes'
    assert refreshed['impact_metier_score']==pytest.approx(1)
    json.dumps(row,allow_nan=False)
    json.dumps(refreshed,allow_nan=False)


def test_memory_missing_baseline_prevents_a_numeric_delta():
    row=risk.case_row(supplier_id='fournisseur',family_key='capacity',case_id='cas',event_row=None,
        metrics=metrics(),baseline_metrics=metrics(identified=False),case_dir=Path('unused_memory_path'))
    assert row['line_nervousness_delta'] is None
    assert row['production_replanning_delta'] is None
    assert row['assessment_status']=='donnees_insuffisantes'


def test_memory_partial_supplier_has_no_worst_family_or_safe_rank():
    result,=risk.summarize_by_supplier([make_case(family='capacity'),make_case(family='stock',identified=False)])
    assert result['worst_risk_family'] is None
    assert result['worst_score_decisionnel_modele'] is None
    assert result['rank'] is None
    assert result['worst_known_risk_family']=='capacity'
    assert result['capacity_impact_pct']==pytest.approx(22)
    assert result['stock_impact_pct'] is None
    assert result['lead_impact_pct'] is None  # une famille non testée n'est pas un risque nul
    assert result['known_impact_metier_score']==pytest.approx(1)
    json.dumps(result,allow_nan=False)


def test_memory_unknown_supplier_is_not_ranked_as_lowest_risk():
    values=risk.summarize_by_supplier([make_case(supplier='inconnu',identified=False),make_case(supplier='connu')])
    assert all(row['rank'] is None for row in values)
    unknown=next(row for row in values if row['supplier_id']=='inconnu')
    assert unknown['assessment_status']=='donnees_insuffisantes'
    assert unknown['worst_risk_family'] is None
    known,=risk.summarize_by_supplier([make_case(supplier='connu')])
    assert known['rank']==1 and known['worst_risk_family']=='capacity'
