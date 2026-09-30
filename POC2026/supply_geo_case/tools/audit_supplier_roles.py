"""Read source exports and publish documentary annotations, not a new simulation."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from POC2026.supply_geo_case.supplier_role_audit import build_supplier_role_audit

CASE = ROOT / 'POC2026/supply_geo_case'


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def main():
    data = CASE / 'outputs/data'
    config_path = CASE / 'config/supplier_role_review.yml'
    inputs = [config_path, CASE / 'supplier_role_audit.py', Path(__file__), *[
        data / f'{name}.csv' for name in ('primary_supply_sites', 'primary_supply_paths',
        'primary_supply_nodes', 'supplier_context_summary')]]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    audit = build_supplier_role_audit(read_rows(inputs[3]), read_rows(inputs[4]),
        read_rows(inputs[6]), config['decisions'], node_rows=read_rows(inputs[5]))
    audit.update(review_date=config['review_date'], scope=config['scope'], inputs=hashes,
        simulation_recalculated=False, commercial_relationships_verified=False)
    evidence = CASE / 'outputs/checks' / ('supplier_role_audit_' + uuid4().hex)
    evidence.mkdir(parents=True)
    text = json.dumps(audit, ensure_ascii=False, indent=2)
    (evidence / 'audit.json').write_text(text, encoding='utf-8')
    (CASE / 'outputs/summaries/supplier_role_audit.json').write_text(text, encoding='utf-8')
    columns = ['site_uid','name','roles_model','nature_label','status_label','primary_path_count',
        'families','documented_activity','proposed_role','rationale','confidence','source_scope',
        'source_urls','node_geometry_collision','node_geometry_groups','coordinates_uid_disagree']
    with (data / 'supplier_role_audit.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in audit['rows']:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), (list,dict)) else row.get(k) for k in columns})
    stable = all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(ROOT))] for p in inputs)
    manifest = {'status':'passed' if stable else 'failed','checks':['input_hashes_stable', 'one_dossier_per_site'],
        'inputs':hashes, 'summary':audit['summary'], 'simulation_recalculated':False}
    assert len(audit['rows']) == len(read_rows(inputs[3]))
    (evidence / 'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert stable
    print(json.dumps({'summary':audit['summary'],'manifest':str(evidence/'manifest.json')}))


if __name__ == '__main__':
    main()
