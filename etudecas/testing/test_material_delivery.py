import csv
import json
from pathlib import Path

import pytest

from etudecas.simulation.lot_trace.payload import build_lot_trace_payload
import etudecas.simulation.test_lot_trace_payload as payload_fixture
from etudecas.simulation.lot_trace.materials import VERSION
from etudecas.visualization.maps.material_delivery import refresh


def test_payload_loads_explicit_origins_without_promoting_simulated_batches(tmp_path):
    fixture = payload_fixture.LotTracePayloadTest()
    paths = [tmp_path / name for name in ('events.csv', 'genealogy.csv', 'plan.csv')]
    for path, fields, rows in zip(paths, [payload_fixture.EVENT_FIELDS, payload_fixture.GENEALOGY_FIELDS, payload_fixture.PLAN_FIELDS],
                                   [fixture._events(), fixture._genealogy(), []]):
        fixture._write_csv(path, fields, rows)
    metadata = dict(version=VERSION, origins=[dict(id='ORIGIN', manufacturer_id='MAKER',
        batch_number='SUP-1', item_id='item:RM', status='observed', source_reference='test:certificate')],
        allocations=[dict(receipt_id='E1', origin_id='ORIGIN', quantity=100, uom='UN')])
    (tmp_path / 'material_traceability.json').write_text(json.dumps(metadata), encoding='utf-8')
    payload = build_lot_trace_payload(*paths, raw=fixture._raw_graph())
    assert payload['material_traceability']['receipts']['E3']['origins'][0]['origin_id'] == 'ORIGIN'
    assert payload['material_traceability']['receipts']['E11']['origins'] == []
    with pytest.raises(FileNotFoundError):
        build_lot_trace_payload(*paths, raw=fixture._raw_graph(), material_traceability_json=tmp_path / 'absent.json')
    metadata['allocations'][0]['quantity'] = 101
    (tmp_path / 'material_traceability.json').write_text(json.dumps(metadata), encoding='utf-8')
    with pytest.raises(ValueError, match='exceed received'):
        build_lot_trace_payload(*paths, raw=fixture._raw_graph())


def test_refresh_refuses_to_attach_another_runs_csvs(tmp_path):
    event = dict(event_id='E1', lot_id='L1', event_type='opening_stock', item_id='item:RM',
                 node_id='SUP', qty=100, day=0, uom='UN')
    html = tmp_path / 'source.html'
    html.write_text('const DATA = ' + json.dumps({'lot_trace': {'events': [event], 'genealogy': []}}) + ';', encoding='utf-8')
    with (tmp_path / 'production_lot_events.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(event))
        writer.writeheader()
        writer.writerow({**event, 'qty': 101})
    destination = tmp_path / 'out.html'
    with pytest.raises(ValueError, match='Map/CSV mismatch'):
        refresh(html, tmp_path, Path('unused-graph'), destination, tmp_path / 'proof')
    assert not destination.exists()
    with pytest.raises(ValueError, match='historical map'):
        refresh(html, tmp_path, Path('unused-graph'), html, tmp_path / 'proof')
