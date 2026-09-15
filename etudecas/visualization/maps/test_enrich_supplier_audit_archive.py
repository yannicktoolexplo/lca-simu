import csv
import pytest
from etudecas.visualization.maps.enrich_supplier_audit_archive import matched_rankings, replace_assignment


@pytest.mark.parametrize('change', [None, 'score', 'rank', 'supplier', 'nan'])
def test_rankings_must_match_archived_results(tmp_path, change):
    row = dict(supplier_id='A', local_criticality_score=.2, system_criticality_score=.3,
        overall_criticality_score=.25, rank=1)
    data = dict(supplier_local_metrics={'A': dict(scores=dict(local=.2,system=.3,overall=.25),rank=1)})
    if change=='score': row['local_criticality_score']=.4
    if change=='rank': row['rank']=2
    if change=='supplier': row['supplier_id']='B'
    if change=='nan': row['local_criticality_score']='nan'
    path=tmp_path/'ranking.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    if change:
        with pytest.raises(ValueError): matched_rankings(data,path)
    else:
        assert matched_rankings(data,path)[0]['supplier_id']=='A'


def test_replacement_preserves_other_runtime_assets():
    document='before; const files = {"old":1}; const other = {"keep":2}; after'
    assert replace_assignment(document,'const files = ',{'new':3}) == (
        'before; const files = {"new":3}; const other = {"keep":2}; after')
