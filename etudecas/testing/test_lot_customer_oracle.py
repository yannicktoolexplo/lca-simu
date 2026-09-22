import csv
import json

import pytest

from etudecas.testing.lot_browser_review import business_batch_csv_oracle


def test_customer_oracle_uses_current_csv_split_and_excludes_future_receipts(tmp_path):
    (tmp_path / 'data').mkdir()
    (tmp_path / 'summaries').mkdir()
    (tmp_path / 'summaries/first_simulation_summary.json').write_text(json.dumps({'sim_days':5}))
    def write(name, rows):
        with (tmp_path / 'data' / name).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    write('production_demand_service_daily.csv', [{'node_id':'CLIENT'}])
    write('production_lot_events.csv', [dict(event_type='production_output', business_batch_id='BATCH', lot_id='ROOT', qty=20)])
    links = [dict(link_type='transport', parent_business_batch_id='BATCH', parent_lot_id='DEPOT', child_lot_id=f'C{i}', child_node_id='CLIENT', shipment_id=f'S{i}', parent_qty=qty, arrival_day=day)
             for i, (qty, day) in enumerate([(3, 2), (7, 3), (10, 8)])]
    write('production_lot_genealogy.csv', links)
    result = business_batch_csv_oracle(tmp_path, 'BATCH')
    assert sorted(result['contributions'].values()) == [3, 7]
    assert result['root_qty'] == 20
    assert result['remaining_not_received_qty'] == 10
    links[0]['parent_qty'] = 30
    write('production_lot_genealogy.csv', links)
    with pytest.raises(ValueError, match='exceed'):
        business_batch_csv_oracle(tmp_path, 'BATCH')
