"""Scenario exports must identify their data and preserve the recorded graph."""
import csv
import json

import pytest

from etudecas.visualization.maps.journey_scenario_delivery import build_scenario_explorer
from .test_lot_journey import page  # noqa: F401


def scenario_files(tmp_path):
    data=tmp_path/'data';data.mkdir()
    row=dict(event_id='E0',lot_id='LOT-TEST',event_type='opening_stock',day=0,node_id='SUP',item_id='item:TEST',
        uom='UN',qty=100,qty_after=100,scenario_id='scn:TEST',shipment_id='',source_id='',source_type='opening_stock',
        trace_status='untraced_before_horizon',business_batch_id='',stock_lot_id='STOCK-TEST',lot_occurrence_id='LOCC-TEST')
    with (data/'production_lot_events.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    (data/'production_lot_genealogy.csv').write_text('parent_lot_id,child_lot_id,link_type,parent_qty,child_qty,day,shipment_id\n',encoding='utf-8')
    graph=tmp_path/'graph.json';graph.write_text(json.dumps({'nodes':[{'id':'SUP','type':'supplier_dc'}],'edges':[]}),encoding='utf-8')
    return data,graph


def test_scenario_export_opens_offline_with_unknown_origin_and_unchanged_inputs(tmp_path,page):
    data,graph=scenario_files(tmp_path)
    before={p:p.read_bytes() for p in [*data.iterdir(),graph]}
    output=tmp_path/'explorer.html'
    report=build_scenario_explorer(data,graph,output,tmp_path/'evidence')
    assert report['scenario']=='scn:TEST' and report['lots']==1
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(output.as_uri());page.wait_for_selector('#lotJourneyModal.visible')
    assert 'scn:TEST' in page.locator('#lotJourneyTitle').inner_text()
    page.locator('[data-journey-tab="identity"]').click()
    text=page.locator('.journeyIdentities').inner_text()
    assert 'Non documentée' in text and 'antérieur à J0' in text
    assert page.locator('[data-network-category="supplier"]').get_attribute('data-low')=='100'
    assert not errors
    assert all(p.read_bytes()==content for p,content in before.items())


def test_scenario_export_rejects_graph_different_from_run_manifest(tmp_path):
    data,graph=scenario_files(tmp_path)
    other=tmp_path/'other.json';other.write_text('{}',encoding='utf-8')
    (tmp_path/'run_manifest.json').write_text(json.dumps({'input_graph':str(other)}),encoding='utf-8')
    with pytest.raises(ValueError,match='Graph must match'):
        build_scenario_explorer(data,graph,tmp_path/'explorer.html',tmp_path/'evidence')
    assert not (tmp_path/'explorer.html').exists()


def test_scenario_export_rejects_missing_scenario_identity(tmp_path):
    data,graph=scenario_files(tmp_path)
    path=data/'production_lot_events.csv';path.write_text(path.read_text(encoding='utf-8').replace('scn:TEST',''),encoding='utf-8')
    with pytest.raises(ValueError,match='explicitly identified'):
        build_scenario_explorer(data,graph,tmp_path/'explorer.html',tmp_path/'evidence')
