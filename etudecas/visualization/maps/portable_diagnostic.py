"""Embed a generated decision diagnostic and its downloads in a single map HTML.

This packaging step does not calculate or change the map's simulation payload.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path


ATTACHMENTS = (
    'decision-report.json', 'constraint-evidence.csv',
    'lot-causal-evidence.csv', 'delivery.json',
)
RUNTIME = r'''
<script data-portable-support="1">
(() => {
 const files = __FILES__;
 document.addEventListener('click', async (event) => {
   const link = event.target.closest('a[data-portable-file]');
   if (!link) return;
   event.preventDefault();
   const file = files[link.dataset.portableFile];
   if (!file) return;
   const target = file.mime === 'text/html' ? window.open('', '_blank') : null;
   try {
     const packed = Uint8Array.from(atob(file.gzip), c => c.charCodeAt(0));
     const bytes = await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
     const url = URL.createObjectURL(new Blob([bytes], {type: file.mime + ';charset=utf-8'}));
     if (file.mime === 'text/html') {
       if (target) target.location.href = url;
       else { URL.revokeObjectURL(url); alert('Autorisez l’ouverture du diagnostic dans un nouvel onglet.'); }
     } else {
       const download = document.createElement('a');
       download.href = url; download.download = file.name;
       download.click(); setTimeout(() => URL.revokeObjectURL(url), 60000);
     }
   } catch (error) {
     if (target) target.close();
     alert('Impossible d’ouvrir le document embarqué : ' + error.message);
   }
 });
})();
</script>
'''


def packed(data: bytes, name: str, mime: str) -> dict:
    return {
        'name': name, 'mime': mime, 'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'gzip': base64.b64encode(gzip.compress(data, mtime=0)).decode('ascii'),
    }


def attach(document: str, files: dict) -> str:
    if 'data-portable-support="1"' in document:
        raise ValueError('The input already contains a portable diagnostic')
    script = RUNTIME.replace('__FILES__', json.dumps(files, ensure_ascii=True).replace('<', '\\u003c'))
    # Maps contain HTML strings inside JavaScript: only the final closing tag
    # belongs to the outer document.
    head, marker, tail = document.rpartition('</html>')
    if not marker:
        raise ValueError('Missing final HTML closing tag')
    return head + script + marker + tail


def replace_link(document: str, previous: str, replacement: str) -> str:
    needle = f'href="{previous}"'
    if document.count(needle) != 1:
        raise ValueError(f'Expected exactly one link to {previous!r}')
    return document.replace(needle, replacement, 1)


def build_portable_map(map_path: Path, diagnostic_path: Path, output_path: Path) -> dict:
    map_path, diagnostic_path, output_path = (
        path.resolve() for path in (map_path, diagnostic_path, output_path)
    )
    if output_path.exists():
        raise ValueError(f'Output already exists: {output_path}')
    # Keep original line endings and payload bytes through the packaging step.
    original = map_path.read_bytes()
    document = original.decode('utf-8')
    diagnostic = diagnostic_path.read_bytes().decode('utf-8')
    attachments = {}
    for name in ATTACHMENTS:
        mime = 'application/json' if name.endswith('.json') else 'text/csv'
        attachments[name] = packed((diagnostic_path.parent / name).read_bytes(), name, mime)
        diagnostic = replace_link(diagnostic, name, f'href="#" data-portable-file="{name}"')
    return_path = Path(os.path.relpath(map_path, diagnostic_path.parent)).as_posix()
    diagnostic = replace_link(
        diagnostic, return_path,
        'href="#" onclick="if(window.opener){window.opener.focus();window.close();}return false;"',
    )
    diagnostic = attach(diagnostic, attachments)
    diagnostic_link = Path(os.path.relpath(diagnostic_path, map_path.parent)).as_posix()
    document = replace_link(document, diagnostic_link, 'href="#diagnostic" data-portable-file="diagnostic"')
    document = attach(document, {'diagnostic': packed(diagnostic.encode('utf-8'), 'diagnostic.html', 'text/html')})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(document.encode('utf-8'))
    return {
        'output': str(output_path), 'source_sha256': hashlib.sha256(original).hexdigest(),
        'output_sha256': hashlib.sha256(output_path.read_bytes()).hexdigest(),
        'attachments': {name: item['sha256'] for name, item in attachments.items()},
        'simulation_recomputed': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, required=True)
    parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_portable_map(args.map, args.diagnostic, args.output), indent=2))


if __name__ == '__main__':
    main()
