"""Archive historical outputs, refresh mass use, and verify production is untouched."""
from __future__ import annotations

import csv
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / 'POC2026' / 'supply_geo_case'
OUTPUT = CASE / 'outputs'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def production_values(path):
    keys = ('scenario_id', 'month_index', 'seat_equivalent_volume',
            'production_static_kgco2e', 'production_dynamic_kgco2e',
            'sdd_inventory_delta_kgco2e')
    return [{k: row.get(k) for k in keys} for row in read_rows(path)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--production-source-root', type=Path)
    args = parser.parse_args()
    archive = OUTPUT / 'checks' / ('article_use_refresh_' + uuid.uuid4().hex)
    archive.mkdir(parents=True)
    caches = sorted((OUTPUT / 'data').glob('lightweight*exact_lcia.csv'))
    cache_before = {str(p.relative_to(OUTPUT)): digest(p) for p in caches}
    productions = [OUTPUT / 'data' / 'sdd_brightway_monthly.csv',
                   *sorted((OUTPUT / 'scenarios').glob('*/data/sdd_brightway_monthly.csv.gz'))]
    source_root = args.production_source_root or OUTPUT
    before = {str(p.relative_to(OUTPUT)): production_values(source_root / p.relative_to(OUTPUT)) for p in productions}
    paths = set()
    for pattern in ('lightweight*.csv', 'sdd_aircraft_use*.csv', 'lca_comparison*.csv',
                    'sdd_brightway_monthly.csv', 'sdd_brightway_cumulative.csv', 'brightway_usage_calibration.csv'):
        paths.update((OUTPUT / 'data').glob(pattern))
    paths.update((OUTPUT / 'summaries').glob('*.json'))
    paths.update((OUTPUT / 'run').glob('*.json'))
    paths.update((OUTPUT / 'scenarios').glob('*/scenario_manifest.json'))
    for pattern in ('*/data/sdd_aircraft_use*.csv.gz', '*/data/sdd_brightway_monthly.csv.gz',
                    '*/data/sdd_brightway_cumulative.csv.gz'):
        paths.update((OUTPUT / 'scenarios').glob(pattern))
    for source in sorted(paths):
        target = archive / 'previous' / source.relative_to(OUTPUT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest = {'status': 'running', 'archive': str(archive),
                'brightway_execution': 'not_rerun_historical_characterized_factors',
                'exact_cache_sha256_before': cache_before, 'commands': []}
    manifest_path = archive / 'manifest.json'
    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    save()
    commands = [
        ['refresh_lightweight_seat_outputs.py', '--cached-only', '--skip-map'],
        ['refresh_aircraft_use_outputs.py'],
        ['refresh_map_display.py', '--dashboard-json', str(OUTPUT / 'summaries' / 'general_kpis.json')],
    ]
    if args.production_source_root:
        commands[1].extend(['--production-source-root', str(args.production_source_root.resolve())])
        manifest['production_source_root'] = str(args.production_source_root.resolve())
    try:
        for index, command in enumerate(commands):
            process = subprocess.run([sys.executable, '-B', str(CASE / 'tools' / command[0]), *command[1:]],
                                     cwd=ROOT, capture_output=True, text=True)
            (archive / f'command_{index}.log').write_text(process.stdout + process.stderr, encoding='utf-8')
            manifest['commands'].append({'command': command, 'returncode': process.returncode})
            save()
            if process.returncode:
                raise RuntimeError(f'{command[0]} failed: {process.stderr[-2000:]}')
            print(process.stdout.strip(), flush=True)
        cache_after = {str(p.relative_to(OUTPUT)): digest(p) for p in caches}
        manifest['exact_cache_unchanged'] = cache_before == cache_after
        # CSV exporters may change formatting, but not the numerical production.
        def normalized(rows):
            return [{k: (float(v) if k != 'scenario_id' and v not in (None, '') else v)
                     for k, v in row.items()} for row in rows]
        manifest['production_and_sdd_unchanged'] = all(
            normalized(before[str(p.relative_to(OUTPUT))]) == normalized(production_values(p)) for p in productions)
        if not manifest['exact_cache_unchanged'] or not manifest['production_and_sdd_unchanged']:
            raise RuntimeError('Production or cached LCIA changed unexpectedly')
        result = json.loads((OUTPUT / 'summaries' / 'lightweight_seat_scenario.json').read_text(encoding='utf-8'))
        manifest['mission'] = result['mission']
        manifest['summary'] = result['summary']
        manifest['source_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in [
            CASE / 'aircraft_mission.py', CASE / 'aircraft_use_accounting.py', CASE / 'lightweight_seat.py',
            CASE / 'lca_comparison.py', CASE / 'adapter.py', CASE / 'config' / 'lightweight_seat_50.yml']}
        manifest['status'] = 'passed'
    except Exception as error:
        manifest.update(status='failed', error=str(error))
        raise
    finally:
        save()
        print(manifest_path, flush=True)


if __name__ == '__main__':
    main()
