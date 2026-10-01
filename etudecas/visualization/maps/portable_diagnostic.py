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
COMPARISON_START = '<!-- ETUDECAS_SOURCE_COMPARISON_BEGIN -->'
COMPARISON_END = '<!-- ETUDECAS_SOURCE_COMPARISON_END -->'
COMPARISON_RUNTIME = r'''
<style>
#sourceComparisonOpenBtn{background:#075985;color:white;border:1px solid #075985;border-radius:6px;padding:7px 11px;cursor:pointer;font:inherit}
#sourceComparisonModal{width:calc(100vw - 24px);max-width:1700px;height:calc(100vh - 24px);max-height:none;padding:0;border:1px solid #94a3b8;border-radius:10px;background:#f6f8fb;color:#142b3f;box-sizing:border-box}
#sourceComparisonModal::backdrop{background:#10233799}
#sourceComparisonModal[open]{display:flex;flex-direction:column}
#sourceComparisonModal header{display:flex;align-items:center;justify-content:space-between;padding:9px 16px;border-bottom:1px solid #d5dee7;background:white;gap:12px}
#sourceComparisonModal h2{font:600 17px system-ui;margin:0}
#sourceComparisonCloseBtn{border:1px solid #b7c6d4;background:white;border-radius:6px;padding:7px 12px;cursor:pointer;font:14px system-ui}
#sourceComparisonFrame{width:100%;flex:1;border:0;min-height:0}
#sourceComparisonStatus{padding:18px;font:15px system-ui}
</style>
<dialog id="sourceComparisonModal" aria-labelledby="sourceComparisonTitle">
 <header><h2 id="sourceComparisonTitle">Comparaisons 2025 — données et simulations</h2><button id="sourceComparisonCloseBtn" type="button">Retour à la carte</button></header>
 <div id="sourceComparisonStatus" role="status">Chargement des courbes…</div>
 <iframe id="sourceComparisonFrame" title="Comparaisons interactives des stocks et du MRP en 2025" sandbox="allow-scripts allow-downloads" hidden></iframe>
</dialog>
<script data-source-comparison="1">
(() => {
 const entry = __ENTRY__;
 const panel = document.getElementById('sourceComparisonModal');
 const frame = document.getElementById('sourceComparisonFrame');
 const status = document.getElementById('sourceComparisonStatus');
 const close = document.getElementById('sourceComparisonCloseBtn');
 const button = document.createElement('button');
 button.id='sourceComparisonOpenBtn';button.type='button';button.textContent='Comparaisons 2025';
 button.title='Stocks observés, simulations, plans MRP, flux et service';
 const toolbar = document.querySelector('.modeTabs') || document.querySelector('.toolbar');
 if(toolbar)toolbar.append(button);else {button.style.cssText='position:fixed;top:12px;right:12px;z-index:99999';document.body.append(button);}
 let ready = false, pending = false;
 const finish = () => {panel.close();button.focus();};
 close.onclick=finish;
 panel.addEventListener('close',()=>button.focus());
 window.addEventListener('message',event=>{if(event.source===frame.contentWindow && event.data?.type==='source-comparison-close')finish();});
 button.onclick=async()=>{
   if(!panel.open)panel.showModal();
   if(ready||pending)return;
   pending=true;status.hidden=false;status.textContent='Chargement des courbes…';
   try {
     const bytes=Uint8Array.from(atob(entry.gzip),c=>c.charCodeAt(0));
     const content=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
     frame.onload=()=>{status.hidden=true;frame.hidden=false;};
     // A Blob avoids copying large comparisons into a UTF-16 srcdoc attribute.
     frame.src=URL.createObjectURL(new Blob([content],{type:'text/html;charset=utf-8'}));ready=true;
   } catch(error){status.textContent='Impossible de charger les comparaisons : '+error.message;}
   finally{pending=false;}
 };
})();
</script>
'''
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


def comparison_document(payload: dict) -> str:
    """Render the local offline view. Data is inert JSON, never executable text."""
    template = Path(__file__).with_name('source_comparison_view.html').read_text(encoding='utf-8')
    marker = '__SOURCE_COMPARISON_PAYLOAD__'
    if template.count(marker) != 1:
        raise ValueError('Expected one comparison JSON placeholder')
    data = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    return template.replace(marker, data)


def strip_comparison(document: str) -> str:
    """Remove only our marked addition; preserve all original map bytes/text."""
    if COMPARISON_START not in document and COMPARISON_END not in document:
        return document
    if document.count(COMPARISON_START) != 1 or document.count(COMPARISON_END) != 1:
        raise ValueError('Ambiguous comparison markers')
    start = document.index(COMPARISON_START)
    end = document.index(COMPARISON_END)
    if end < start:
        raise ValueError('Reversed comparison markers')
    return document[:start] + document[end + len(COMPARISON_END):]


def build_comparison_map(map_path: Path, payload: dict, output_path: Path) -> dict:
    """Add/refresh a comparison panel without recalculating existing map views."""
    if output_path.exists():
        raise ValueError(f'Output already exists: {output_path}')
    original = map_path.read_bytes()
    document = strip_comparison(original.decode('utf-8'))
    comparison = comparison_document(payload)
    entry = packed(comparison.encode('utf-8'), 'comparaisons_2025.html', 'text/html')
    block = COMPARISON_START + COMPARISON_RUNTIME.replace('__ENTRY__', json.dumps(entry)) + COMPARISON_END
    head, marker, tail = document.rpartition('</html>')
    if not marker:
        raise ValueError('Missing final HTML closing tag')
    result = head + block + marker + tail
    assert strip_comparison(result) == document
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result.encode('utf-8'))
    return {'output': str(output_path), 'source_sha256': hashlib.sha256(original).hexdigest(),
            'original_map_sha256': hashlib.sha256(document.encode('utf-8')).hexdigest(),
            'output_sha256': hashlib.sha256(output_path.read_bytes()).hexdigest(),
            'comparison_html_sha256': entry['sha256'],
            'comparison_json_sha256': hashlib.sha256(json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True).encode()).hexdigest(),
            'existing_map_content_unchanged': True,
            'scope': 'A separate dated comparison panel; original scenarios and both lot views preserved.'}


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
