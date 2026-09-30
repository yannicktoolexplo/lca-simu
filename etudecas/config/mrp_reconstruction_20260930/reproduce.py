"""Reproduce the frozen MRP analysis in a new directory; never replace a reference."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDY = Path('etudecas/artifacts/testing/mrp_reconstruction_20260930')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(script, directory, *args):
    result = subprocess.run([sys.executable, '-B', str(script), *map(str, args)],
                            cwd=directory, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=300)
    log = script.with_suffix('.execution.txt')
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'Execution failed ({result.returncode}): {log}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-map', action='store_true',
                        help='Also rebuild the complete map from the two local reference HTMLs.')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    archive = HERE / manifest['archive']
    if sha(archive) != manifest['archive_sha256']:
        raise ValueError('Archive differs from the checkpoint.')
    if args.with_map:
        for ref in manifest['local_map_references']:
            if not (ROOT / ref['path']).is_file() or sha(ROOT / ref['path']) != ref['sha256']:
                raise ValueError(f"Required local reference missing or changed: {ref['path']}")
    destination = ROOT / 'etudecas/artifacts/testing' / ('mrp_reproduction_' + uuid.uuid4().hex)
    destination.mkdir(parents=True, exist_ok=False)
    qualified_name = (STUDY / 'engine/reconstruction.json').as_posix()
    # Extract only necessary inputs and executable sources; historical proofs stay in the ZIP.
    required = {
        'etudecas/data/source/Flow_Data_MRP_results.xlsx',
        'etudecas/data/source/Flow_Data_Inventory_and_Replenishment_rules.xlsx',
        'etudecas/data/source/268091.xlsx', 'etudecas/data/source/Extract_En_cours.xlsx',
        'etudecas/artifacts/testing/mrp_common_rules_20260930/grouping/analysis.json',
        'etudecas/artifacts/testing/mrp_source_driven_20260928/source_supply/autonomous_projection.json',
        'etudecas/visualization/maps/portable_diagnostic.py',
        *(str(STUDY / p).replace('\\', '/') for p in (
            'engine/reconstruct.py', 'validation/verify_reconstruction.py',
            'map/build.py', 'map/view.html')),
    }
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != set(manifest['members']):
            raise ValueError('Archive member list differs from the checkpoint.')
        for name, entry in manifest['members'].items():
            data = bundle.read(name)
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError(f'Archive member differs: {name}')
            if name in required:
                target = (destination / name).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError('Archive path escapes the new directory.')
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(data)
        qualified_bytes = bundle.read(qualified_name)
    study = destination / STUDY
    run(study / 'engine/reconstruct.py', destination)
    actual = json.loads((study / 'engine/reconstruction.json').read_text(encoding='utf-8'))
    qualified = json.loads(qualified_bytes)
    # Fresh execution has no prior unqualified output to replace. All other fields must match.
    actual.pop('replaces_unqualified_reconstruction_sha256')
    qualified.pop('replaces_unqualified_reconstruction_sha256')
    if actual != qualified:
        raise ValueError('Reconstructed values or provenance differ from the qualified baseline.')
    run(study / 'validation/verify_reconstruction.py', destination)
    oracle = json.loads((study / 'validation/reconstruction_check_final.json').read_text(encoding='utf-8'))
    if not oracle['ok']:
        raise ValueError('Independent numerical review failed.')
    # Render the frozen, now reproduced payload to preserve the exact reviewed UI data.
    payload = json.loads(qualified_bytes)
    template = (study / 'map/view.html').read_text(encoding='utf-8')
    template = template.replace(
        'Les autres onglets et les deux suivis de lots restent ceux de la carte historique.',
        'La carte historique complète et ses deux suivis de lots sont conservés séparément.')
    marker = '__MRP_RECONSTRUCTION_PAYLOAD__'
    if template.count(marker) != 1:
        raise ValueError('Unexpected HTML template.')
    text = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    standalone = destination / 'comparaison_mrp.html'
    standalone.write_text(template.replace(marker, text), encoding='utf-8', newline='\n')
    complete = None
    if args.with_map:
        for ref in manifest['local_map_references']:
            target = destination / ref['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / ref['path'], target)
            if sha(target) != ref['sha256']:
                raise ValueError('Copied map differs from its reference.')
        qualified_input = study / 'engine/qualified_reconstruction.json'
        qualified_input.write_bytes(qualified_bytes)
        run(study / 'map/build.py', destination, '--input', qualified_input)
        complete = destination / manifest['delivered_map']
        if sha(complete) != manifest['delivered_map_sha256']:
            raise ValueError('Complete rebuilt HTML differs from the reviewed map.')
    report = dict(ok=True, numerical_checks=oracle['checks'],
                  archive_sha256=sha(archive), all_reconstructed_values_equal=True,
                  ignored_metadata_field='replaces_unqualified_reconstruction_sha256',
                  standalone_html=str(standalone), complete_html=str(complete) if complete else None,
                  complete_html_sha256=sha(complete) if complete else None,
                  scope='Normal reconstruction and independent source review; no physical simulation or browser rerun.')
    (destination / 'reproduction.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
