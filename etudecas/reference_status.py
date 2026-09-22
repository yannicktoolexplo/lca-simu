"""Read-only verification of the fixed reference and documentary coverage. No simulation."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / 'etudecas/docs/reference/current.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_reference(root: Path, manifest: dict) -> dict:
    """Check pinned files without replacing expected hashes or executing the model."""
    root = root.resolve()
    if manifest.get('schema_version') != 'etudecas.fixed_reference.v1' or not manifest.get('files'):
        raise ValueError('Invalid or empty fixed reference')
    seen, results = set(), []
    for entry in manifest['files']:
        name, expected = entry['path'], entry['sha256']
        logical = PurePosixPath(name)
        path = (root/name).resolve()
        if (logical.is_absolute() or '..' in logical.parts or ':' in name or '\\' in name
                or name in seen or not path.is_relative_to(root)):
            raise ValueError(f'Unsafe or duplicate reference path: {name}')
        if not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError(f'Invalid reference hash: {name}')
        seen.add(name)
        actual = digest(path) if path.is_file() else None
        status = 'match' if actual == expected else 'missing' if actual is None else 'changed'
        results.append({'path': name, 'role': entry['role'], 'status': status,
                        'expected_sha256': expected, 'actual_sha256': actual})
    return {'reference_id': manifest['reference_id'], 'ok': all(r['status'] == 'match' for r in results),
            'counts': dict(Counter(r['status'] for r in results)), 'files': results,
            'scope': 'Pinned local files only; no transitive provenance or scientific validation.'}


def documentation_coverage(root):
    """Inventory registered rules and flag code/business changes using AST only."""
    from etudecas.documentation.builder import inspect_reference
    catalog = json.loads((root/'etudecas/docs/catalog.json').read_text(encoding='utf-8'))
    domains = []
    cache = {}
    for item in catalog['registries']:
        registry = json.loads((root/item['registry']).read_text(encoding='utf-8'))
        changes = [r['id'] for r in registry['references'] if inspect_reference(root, r, cache)['changed']]
        # Use the documentation builder's text normalization, not the byte-level
        # hash required for calculated artifacts (BOM and CRLF are immaterial here).
        business = [p for p, expected in registry['business_source_fingerprints'].items()
                    if hashlib.sha256((root/p).read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest() != expected]
        domains.append({'registry': item['registry'], 'title': registry['title'],
                        'rules': len(registry['rules']), 'references': len(registry['references']),
                        'rule_statuses': dict(Counter(r['status'] for r in registry['rules'])),
                        'changed_code_references': changes, 'changed_business_sources': business})
    return {'domains': domains, 'review_needed': any(d['changed_code_references'] or d['changed_business_sources'] for d in domains),
            'scope': 'Registered rules only, not exhaustive engine coverage; tests are not executed.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        reference = verify_reference(REPO, json.loads(args.manifest.read_text(encoding='utf-8')))
        coverage = documentation_coverage(REPO)
        report = {'ok': reference['ok'] and not coverage['review_needed'],
                  'reference': reference, 'documentation': coverage}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {'ok': False, 'error': str(exc)}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'ok': report['ok'], 'counts': report.get('reference', {}).get('counts'),
                      'review_needed': report.get('documentation', {}).get('review_needed'),
                      'error': report.get('error')}, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
