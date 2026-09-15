"""Add existing supplier audit panels to an archived standalone demonstration.

No simulation or criticality score is recomputed. The original archive is kept.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control import standalone_single_html as standalone
from etudecas.risk.supplier_audit import (
    DEFAULT_SUPPLIER_AUDIT_SOURCE, DEFAULT_SUPPLIER_CONTEXT_PROXIES,
    DEFAULT_SUPPLIER_PUBLIC_EVIDENCE, load_supplier_audits,
    expand_supplier_audit_coverage, estimate_supplier_audit_profiles,
    supplier_audit_coverage_summary, attach_supplier_audit_panels,
)
from etudecas.visualization.maps.compress_html_payload import compress_embedded
from etudecas.visualization.maps.simulation_payload import render_material_balance_table_html
from etudecas.visualization.maps.worldmap_html_template import html_template
from etudecas.visualization.maps.worldmap_html_template import plotly_script_tag

VIEW = 'views/carte_reseau_lots.html'


def decode_payload(document):
    for marker, mode in [('const DATA_GZIP_BASE64_CHUNKS =', 'gzip'),
                         ('const DATA_CHUNKED_GZIP_BASE64 =', 'chunks'), ('const DATA =', 'raw')]:
        if marker not in document:
            continue
        value, _ = json.JSONDecoder().raw_decode(document.split(marker, 1)[1].lstrip())
        def inflate(chunks):
            return json.loads(gzip.decompress(base64.b64decode(''.join(chunks))))
        if mode == 'gzip':
            return inflate(value)
        if mode == 'chunks':
            return {key: inflate(chunks) for key, chunks in value.items()}
        return value
    raise ValueError('Map DATA not found')


def matched_rankings(data, csv_path):
    import csv
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    by_id = {row['supplier_id']: row for row in rows}
    metrics = data['supplier_local_metrics']
    if len(by_id) != len(rows) or set(by_id) != set(metrics):
        raise ValueError('Ranking supplier coverage differs from archived map')
    for node, value in metrics.items():
        row = by_id[node]
        for metric, field in [('local', 'local_criticality_score'),
                              ('system', 'system_criticality_score'),
                              ('overall', 'overall_criticality_score')]:
            score = float(row[field])
            if not math.isfinite(score) or abs(score - value['scores'][metric]) > 1e-6:
                raise ValueError(f'Ranking differs from archive: {node}/{metric}')
        if int(row['rank']) != value['rank']:
            raise ValueError(f'Ranking differs from archive: {node}/rank')
    return rows


def replace_assignment(document, marker, value):
    start = document.index(marker) + len(marker)
    while document[start].isspace():
        start += 1
    _, count = json.JSONDecoder().raw_decode(document[start:])
    return document[:start] + standalone._script_json(value) + document[start + count:]


def enrich_archive(source: Path, ranking: Path, output: Path):
    if output.exists() or output.resolve() == source.resolve():
        raise ValueError('Choose a new output file; original archive must be preserved')
    standalone.validate_single_html(source)
    document = source.read_text(encoding='utf8')
    original_hash = standalone.sha256_file(source)
    entries = standalone._runtime_json_assignment(document, 'const files = ')
    metadata = standalone._runtime_json_assignment(document, 'const metadata = ')
    original_entries = deepcopy(entries)
    data = decode_payload(standalone._decoded_entry(entries[VIEW], label=VIEW).decode('utf8'))
    original_data = deepcopy(data)
    rows = matched_rankings(data, ranking)
    audit_nodes = list(data['nodes'])
    node_ids = {node['id'] for node in audit_nodes}
    # Some ranked suppliers have no map node/coordinates in the archive. Keep
    # their audit accessible in the existing selector without inventing a site.
    audit_nodes.extend(dict(id=row['supplier_id'], type='supplier_dc', name=row.get('supplier_name', ''))
        for row in rows if row['supplier_id'] not in node_ids)
    audits = expand_supplier_audit_coverage(audit_nodes, load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_SOURCE))
    if not audits or any(len(a['criteria']) != 28 for a in audits.values()):
        raise ValueError('Expected complete existing 28-criterion audit template')
    estimate_supplier_audit_profiles(audits, rows)
    data['supplier_audits'] = audits
    data['supplier_audit_coverage'] = supplier_audit_coverage_summary(audits)
    data['supplier_risk_hover_images'] = attach_supplier_audit_panels(data['supplier_risk_hover_images'], audits)
    for key, value in original_data.items():
        if key != 'supplier_risk_hover_images' and data[key] != value:
            raise AssertionError(f'Existing results changed: {key}')
    sources = {
        'sources/supplier_public_evidence.csv': DEFAULT_SUPPLIER_PUBLIC_EVIDENCE,
        'sources/supplier_context_proxies.csv': DEFAULT_SUPPLIER_CONTEXT_PROXIES,
        'sources/supplier_criticality_reference.csv': ranking,
        'sources/trame_audit_fournisseur.xlsx': DEFAULT_SUPPLIER_AUDIT_SOURCE/'Trame_Audit_Fournisseur.xlsx',
    }
    completed = next(iter(load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_SOURCE).values()))
    sources['sources/audit_fournisseur_renseigne.xlsx'] = Path(completed['source_file'])
    for name, path in sources.items():
        content = path.read_bytes()
        entries[name] = standalone._entry(name, content, content, kind='file')
    rendered = html_template('Carte historique - contexte et audits fournisseurs',
        json.dumps(data, ensure_ascii=False),
        render_material_balance_table_html(data.get('material_balance_rows', [])),
        len(data.get('material_balance_rows', [])),
        'Resultats historiques conserves ; estimations issues des criteres existants, non auditees.')
    links = ''.join(f'<a href="../{name}">{Path(name).name}</a> &nbsp; ' for name in sources)
    notice = ('<details style="position:fixed;bottom:8px;left:8px;z-index:10000;background:white;'
        'padding:8px;max-width:480px;border:1px solid #aaa"><summary>Sources contexte et audit</summary>'
        '<p>Informations publiques deja collectees, sans nouvelle recherche Internet. '
        'Les estimations ne constituent pas des reponses confirmees du fournisseur. '
        'Les scores et simulations historiques restent inchanges.</p>' + links + '</details>')
    rendered = rendered.replace('</body>', notice + '</body>')
    # The archive already owns Plotly and the world topology. Reuse those exact
    # assets rather than embedding the current viewer's duplicate network shim.
    plotly_tag = plotly_script_tag()
    if rendered.count(plotly_tag) != 1:
        raise ValueError('Expected one controlled Plotly asset')
    topology = standalone._decoded_entry(entries['views/world_110m.json'], label='world topology')
    offline = ('<script src="plotly-2.32.0.min.js"></script><script>'
        "if(location.protocol==='file:'){"
        'window.PlotlyGeoAssets=window.PlotlyGeoAssets||{};'
        'window.PlotlyGeoAssets.topojson=window.PlotlyGeoAssets.topojson||{};'
        'window.PlotlyGeoAssets.topojson.world_110m='
        + standalone._script_json(json.loads(topology)) + ';}</script>')
    rendered = rendered.replace(plotly_tag, offline, 1)
    rendered, _ = compress_embedded(rendered)
    assert decode_payload(rendered) == data
    transformed, needs_plotly, _ = standalone.transform_view(
        rendered, VIEW, output.parent, set(entries) | {standalone.PLOTLY_PATH})
    entries[VIEW] = standalone._entry(VIEW, rendered.encode('utf8'), transformed.encode('utf8'),
        kind='html', title='Carte historique - contexte et audits fournisseurs', needs_plotly=needs_plotly)
    inventory = standalone.inventory_document(entries, metadata['source_package'],
        hardened=bool(metadata.get('security_profile'))).encode('utf8')
    entries[standalone.INVENTORY_PATH] = standalone._entry(
        standalone.INVENTORY_PATH, inventory, inventory, kind='html', title='Contenu embarque')
    metadata['embedded_entry_count'] = len(entries)
    metadata['generated_at_utc'] = datetime.now(timezone.utc).isoformat()
    result = replace_assignment(document, 'const files = ', entries)
    result = replace_assignment(result, 'const metadata = ', metadata)
    standalone._validate_single_html_document(result, label=str(output), opaque_depth=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding='utf8')
    assert standalone.sha256_file(source) == original_hash
    untouched = set(original_entries) - {VIEW, standalone.INVENTORY_PATH}
    assert all(entries[k] == original_entries[k] for k in untouched)
    report = dict(original_sha256=original_hash, output=str(output),
        supplier_count=len(audits), coverage=data['supplier_audit_coverage'],
        preserved_entries=len(untouched), historical_results_unchanged=True,
        ranking_source=str(ranking), source_hashes={k: standalone.sha256_file(p) for k,p in sources.items()})
    output.with_suffix('.audit_addition.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--ranking', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(enrich_archive(args.source, args.ranking, args.output), ensure_ascii=True))
