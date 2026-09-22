"""Reassemble retained presentations using only their embedded resources.

No external research directory, network access or simulation is used. This
restores presentation data; it does not recreate the experiments that produced it.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re

from etudecas.visualization import standalone_html as standalone


def _replace_assignment(document: str, marker: str, value: object) -> str:
    # The existing validator enforces uniqueness and canonical, script-safe JSON.
    original = standalone.runtime_json_assignment(document, marker)
    start = document.index(marker) + len(marker)
    while document[start].isspace():
        start += 1
    end = start + len(standalone.script_json(original))
    return document[:start] + standalone.script_json(value) + document[end:]


def rebuild_demonstration(document: str) -> tuple[str, dict]:
    standalone.validate_single_html_document(document, label='source archive', opaque_depth=0)
    files = standalone.runtime_json_assignment(document, 'const files = ')
    hashes = {}
    for name, entry in files.items():
        data = standalone.decoded_entry(entry, label=name)
        hashes[name] = hashlib.sha256(data).hexdigest()
        entry['gzip_base64'] = standalone.gzip_base64(data)
    rebuilt = _replace_assignment(document, 'const files = ', files)
    plotly = standalone.runtime_json_assignment(document, 'const plotlyBundle = ')
    data = gzip.decompress(base64.b64decode(plotly['gzip_base64'], validate=True))
    if hashlib.sha256(data).hexdigest() != plotly['embedded_sha256']:
        raise ValueError('Plotly resource hash differs')
    plotly['gzip_base64'] = standalone.gzip_base64(data)
    rebuilt = _replace_assignment(rebuilt, 'const plotlyBundle = ', plotly)
    standalone.validate_single_html_document(rebuilt, label='rebuilt archive', opaque_depth=0)
    restored = standalone.runtime_json_assignment(rebuilt, 'const files = ')
    if any(hashlib.sha256(standalone.decoded_entry(restored[name], label=name)).hexdigest() != digest
           for name, digest in hashes.items()):
        raise ValueError('An embedded resource changed while reassembling')
    metadata = standalone.runtime_json_assignment(rebuilt, 'const metadata = ')
    return rebuilt, {'views': metadata['view_count'], 'embedded_resources': len(files),
                     'embedded_sha256': hashes, 'plotly_sha256': plotly['embedded_sha256']}


def rebuild_landscape(document: str) -> tuple[str, dict]:
    from etudecas.prototypes.scan_2027_risk_control import supplier_service_landscape_dashboard as landscape

    matches = re.findall(r'<script id="campaign-data" type="application/json">(.*?)</script>', document, re.S)
    if len(matches) != 1:
        raise ValueError('Expected exactly one embedded landscape campaign')
    payload = json.loads(matches[0])
    landscape.validate_supplier_service_campaign_for_dashboard(payload)
    rebuilt = landscape.render_supplier_service_landscape_dashboard(payload)
    return rebuilt, {'views': 3, 'rows': {name: len(table['rows']) for name, table in payload['tables'].items()}}


def rebuild(kind: str, source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(f'Choose a new output HTML: {output}')
    original = source.read_bytes()
    document = original.decode('utf-8')
    if kind == 'demonstration':
        rebuilt, detail = rebuild_demonstration(document)
    elif kind == 'supply_chains':
        rebuilt, detail = rebuild_landscape(document)
    elif kind == 'fournisseurs':
        from etudecas.visualization import supplier_configuration_comparison as suppliers

        payload = suppliers.extract_payload(source)
        rebuilt, detail = suppliers.render_html(payload), {'rows': len(payload['rows'])}
    else:
        raise ValueError(f'Unknown presentation: {kind}')
    encoded = rebuilt.encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(encoded)
    return {'kind': kind, 'source': str(source), 'output': str(output),
            'source_sha256': hashlib.sha256(original).hexdigest(),
            'output_sha256': hashlib.sha256(encoded).hexdigest(),
            'byte_identical': original == encoded, 'simulation_recomputed': False,
            'external_research_directory_used': False, 'detail': detail}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('demonstration', 'supply_chains', 'fournisseurs'), required=True)
    parser.add_argument('--source-html', type=Path, required=True)
    parser.add_argument('--output-html', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild(args.kind, args.source_html, args.output_html), indent=2))


if __name__ == '__main__':
    main()
