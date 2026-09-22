"""Recreate retained reference calculations without historical result folders."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'etudecas/config/reproduction_20260920'


def _hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _capture_sources(output: Path, commands: list[list[str]]) -> dict:
    """Keep executable sources outside disposable simulation results."""
    from etudecas.reproduction_bundle import capture

    folder = CONFIG / 'sources'
    temporary = folder / f'.capture_{uuid.uuid4().hex}.zip'
    captured = capture(temporary, commands, root=ROOT)
    archive = folder / f"{captured['archive_sha256']}.zip"
    if archive.exists():
        if _hash(archive) != captured['archive_sha256']:
            raise ValueError(f'Existing source archive has an unexpected checksum: {archive}')
        temporary.unlink()
    else:
        temporary.rename(archive)
    result = {
        'archive': archive.relative_to(ROOT).as_posix(),
        'archive_sha256': captured['archive_sha256'], 'files': captured['files'],
        'compressed_bytes': captured['compressed_bytes'], 'capture_stage': 'before_simulation',
        'scope': 'Current sources, explicit inputs, commands and installed dependency versions.',
    }
    _write(output / 'source-bundle.json', result)
    return result


def _check_sources(bundle: dict) -> dict:
    from etudecas.reproduction_bundle import verify_current

    archive = ROOT / bundle['archive']
    if _hash(archive) != bundle['archive_sha256']:
        raise ValueError(f'Source archive changed during execution: {archive}')
    verify_current(archive, root=ROOT)
    return {**bundle, 'current_sources_verified_after_execution': True}


def _command(scenario: str, output: Path, days: int | None, with_map=False) -> list[str]:
    manifest = json.loads((CONFIG / f'{scenario}.json').read_text(encoding='utf-8'))
    command = manifest['simulator_command'][:]
    command[0] = sys.executable
    command[command.index('--output-dir') + 1] = str(output)
    if days is not None:
        command[command.index('--days') + 1] = str(days)
    if with_map:
        command = [value for value in command if value != '--skip-map']
    for flag in ('--input', '--control-schedule-csv'):
        if flag in command:
            path = Path(command[command.index(flag) + 1])
            if not (path if path.is_absolute() else ROOT / path).is_file():
                raise ValueError(f'Missing input for {flag}: {path}')
    if '-B' not in command[:2]:
        command.insert(1, '-B')
    return command


def _record_run(scenario: str, output: Path, command: list[str], *, companions=False,
                source_bundle: dict | None = None) -> None:
    """Record this execution, without copying historical status or code hashes."""
    source = CONFIG / f'{scenario}.json'
    inputs = {}
    for flag in ('--input', '--control-schedule-csv'):
        if flag in command:
            path = (ROOT / command[command.index(flag) + 1]).resolve()
            inputs[str(path)] = _hash(path)
    manifest = {
        'schema': 'etudecas.reproduced_run.v1',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'input_graph': str((ROOT / command[command.index('--input') + 1]).resolve()),
        'output_dir': str(output), 'scenario_id': command[command.index('--scenario-id') + 1],
        'days': int(command[command.index('--days') + 1]),
        'output_profile': command[command.index('--output-profile') + 1],
        'supplier_state_dependent_risks': '--supplier-state-dependent-risks' in command,
        'skip_map': '--skip-map' in command, 'skip_plots': '--skip-plots' in command,
        'simulator_command': command,
        'reproduction_source': {'path': str(source), 'sha256': _hash(source)},
        'input_hashes': inputs,
        'implementation_sha256': _hash(ROOT / 'etudecas/simulation/engine/run_first_simulation.py'),
        'qualification': 'New execution; historical acceptance is not transferred.',
    }
    if source_bundle is not None:
        manifest['source_bundle'] = source_bundle
    if companions:
        manifest['companion_runs'] = {
            'state_dependent_full': {
                'output_dir': 'scenario_runs/state_dependent_full',
                'scenario_id': 'scn:STATE_DEPENDENT_FULL',
                'label': 'Portefeuille state-dependent complet',
                'role': 'primary_simulated_risk',
            },
        }
    _write(output / 'run_manifest.json', manifest)


def _map_command(output: Path, graph: Path, map_path: Path) -> list[str]:
    missing = output / '__not_attached_optional_campaigns__'
    if missing.exists():
        raise ValueError(f'Optional-campaign sentinel must not exist: {missing}')
    command = [sys.executable, '-B', '-m', 'etudecas.visualization.maps.build_supplychain_worldmap',
               '--input', str(graph), '--run-package', str(output / 'run'),
               '--simulated-risk-output-dir', str(output / 'scenario_runs/state_dependent_full'),
               '--output', str(map_path), '--title', 'Simulation - lots et bilans corriges',
               '--read-only-source', '--chunked-embedded-payload',
               '--supplier-audit-xlsx', str(ROOT / 'etudecas/data/source')]
    # Attach only the retained four calculations. Repository defaults must never
    # silently supply an unrelated historical sensitivity or risk campaign.
    for flag in (
        '--sensitivity-cases-csv', '--structural-sensitivity-cases-csv',
        '--supplier-parameter-sensitivity-summary-json', '--supplier-parameter-summary-csv',
        '--supplier-parameter-cases-csv', '--supplier-risk-kpi-summary-json',
        '--supplier-risk-kpi-supplier-csv', '--supplier-risk-kpi-pair-csv',
        '--supplier-risk-kpi-panel-csv', '--supplier-risk-campaign-summary-json',
        '--supplier-risk-campaign-summary-csv', '--supplier-risk-campaign-cases-csv',
    ):
        command += [flag, str(missing)]
    for flag in (
        '--montecarlo-summary-json', '--scan-results-dir', '--closed-loop-results-dir',
        '--closed-loop-v2-results-dir', '--scan-frequency-results-dir',
        '--scan-control-system-results-dir', '--realistic-sensitivity-summary-json',
        '--realistic-local-elasticities-csv', '--realistic-stress-impacts-csv',
        '--threshold-sensitivity-summary-json', '--threshold-parameter-summary-csv',
        '--threshold-sweep-cases-csv',
    ):
        command += [flag, '']
    return command


def _assemble_diagnostic(output: Path, map_path: Path, validations: list[dict]) -> Path:
    """Read the four retained interventions; never select or execute new actions."""
    from etudecas import decision_support as ds
    from etudecas.visualization.maps.scenario_comparison_payload import build_scenario_comparison_payload

    risk = output / 'scenario_runs/state_dependent_full'
    diagnostic = output / 'decision_support'
    diagnostic.mkdir(parents=True, exist_ok=True)
    risk_manifest = ds.read_json(risk / 'run_manifest.json')
    payload = build_scenario_comparison_payload(output)
    scenario_ids = {row['id'] for row in payload.get('scenarios', [])}
    if scenario_ids != {output.name, risk.name}:
        raise ValueError(f'Expected only the retained nominal and risk comparison: {scenario_ids}')
    risk_kpis = next(row['kpis'] for row in payload['scenarios'] if row['id'] == risk.name)
    report = {
        'scope': 'Four explicit retained replays; descriptive results, no causal recommendation',
        'score': ds.score_breakdown(risk_kpis), 'delays': {}, 'actions': {}, 'source_hashes': {},
        'action_target_basis': 'Retained control schedules; targets have not been reselected.',
        'loss_audit': ds.audit_losses(risk, risk_manifest['days']),
        'bottlenecks': ds.bottlenecks(risk, ds.read_json(risk_manifest['input_graph']), diagnostic),
    }
    for label, source in [('nominal', output), ('risk', risk)]:
        days = ds.read_json(source / 'summaries/first_simulation_summary.json')['sim_days']
        report['delays'][label] = ds.fifo_delay(ds.csv_rows(source / 'data/production_demand_service_daily.csv'), days)
    sources = [('risk_reference', risk)] + [
        (name, diagnostic / 'actions' / name) for name in ('safety_150', 'expedite_50')]
    for label, source in sources:
        report['actions'][label] = ds.action_metrics(source)
    for value in report['actions'].values():
        value['cost_delta_vs_risk'] = value['total_cost'] - report['actions']['risk_reference']['total_cost']
    for source in [output] + [source for _, source in sources]:
        manifest = ds.read_json(source / 'run_manifest.json')
        for path in [source / 'run_manifest.json', Path(manifest['input_graph'])]:
            report['source_hashes'][str(path)] = _hash(path)
        for folder in ('data', 'summaries'):
            for path in sorted((source / folder).iterdir()):
                if path.is_file():
                    report['source_hashes'][str(path)] = _hash(path)
        report['source_hashes'].update(manifest['input_hashes'])
    for path in (Path(__file__).resolve(), Path(ds.__file__).resolve()):
        report['source_hashes'][str(path)] = _hash(path)
    if not report['loss_audit']['summary_matches']:
        raise ValueError('Risk losses do not reconcile with the simulation summary')
    _write(diagnostic / 'decision-report.json', report)
    ds.render_report(diagnostic, report, map_path)
    content = map_path.read_text(encoding='utf-8')
    head, marker, tail = content.rpartition('</body>')
    if not marker:
        raise ValueError('Missing map closing body tag')
    link = '<a id="decisionSupportLink" href="../decision_support/index.html" style="position:fixed;bottom:12px;left:12px;z-index:9999;background:white;padding:10px;border:1px solid #0369a1;border-radius:6px;color:#075985">Diagnostic métier et sensibilités</a>'
    map_path.write_text(head + link + marker + tail, encoding='utf-8')
    _write(diagnostic / 'delivery.json', {
        'ok': True, 'status': 'generated_with_csv_checks', 'runs': validations,
        'html_sha256': _hash(map_path), 'report_sha256': _hash(diagnostic / 'decision-report.json'),
        'browser_requested': False, 'browser_verified': False,
        'scope': 'New CSV invariants and run-package reconciliation. No historical acceptance reused.',
        'limitations': ['Browser interactions have not been verified by this command.',
                        'Industrial calibration and causal risk attribution are not certified.',
                        'Monte Carlo and SCAN were not computed or attached.'],
    })
    return diagnostic / 'index.html'


def _deliver(output: Path, commands: list[tuple[str, Path, list[str]]], map_command: list[str],
             map_path: Path, portable_path: Path) -> None:
    from etudecas.testing.qualification import require_run_invariants
    from etudecas.testing.map_delivery import reconcile_run
    from etudecas.visualization.maps.portable_diagnostic import build_portable_map

    bundle = _capture_sources(output, [command for _, _, command in commands])
    _write(output / 'reproduction-plan.json', {
        'schema': 'etudecas.reproduction_delivery.v1', 'delivery': 'lots',
        'commands': [command for _, _, command in commands], 'map_command': map_command,
        'source_bundle': bundle,
        'scope': 'Retained model inputs and controls; newly calculated results.',
    })
    validations = []
    for scenario, run, command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
        verified_sources = _check_sources(bundle)
        _record_run(scenario, run, command, companions=scenario == 'nominal',
                    source_bundle=verified_sources)
        invariant_result = require_run_invariants(run)
        _write(run / 'reproduction-invariants.json', invariant_result)
        reconciliation = reconcile_run(run)
        _write(run / 'reproduction-reconciliation.json', reconciliation)
        if not reconciliation['ok']:
            raise ValueError(f'Run reconciliation failed: {run}')
        validations.append({'run': str(run), 'ok': True,
                            'invariants_sha256': _hash(run / 'reproduction-invariants.json'),
                            'reconciliation_sha256': _hash(run / 'reproduction-reconciliation.json')})
    subprocess.run(map_command, cwd=ROOT, check=True)
    if not map_path.is_file():
        raise ValueError('Map builder completed without creating the expected HTML')
    diagnostic_path = _assemble_diagnostic(output, map_path, validations)
    packaging = build_portable_map(map_path, diagnostic_path, portable_path)
    _check_sources(bundle)
    _write(output / 'portable-delivery.json', packaging)
    print(json.dumps({'delivery': 'lots', 'html': str(portable_path),
                      'html_sha256': packaging['output_sha256'], 'runs': len(commands)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=('nominal', 'risques', 'securite_150', 'acceleration_50'), default='nominal')
    parser.add_argument('--days', type=int, help='Omit to keep the retained 1825-day horizon.')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--with-map', action='store_true', help='Build a basic map of this single run; use --delivery lots for the full portable comparison and diagnostic.')
    parser.add_argument('--delivery', choices=('lots',), help='Recreate all four retained runs, their comparison, and a portable map with its diagnostic.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.days is not None and args.days < 1:
        parser.error('--days must be positive')
    if args.delivery and (args.scenario != 'nominal' or args.with_map):
        parser.error('--delivery lots already includes all scenarios and the map; omit --scenario and --with-map')
    if args.delivery and args.days is not None and args.days < 300:
        parser.error('--delivery lots requires at least 300 days for the scenario comparison; use --scenario for shorter checks')
    label = 'lots' if args.delivery else args.scenario
    output = args.output_dir or Path('etudecas/simulation/result') / f'{label}_{datetime.now():%Y%m%d_%H%M%S}'
    output = output.resolve() if output.is_absolute() else (ROOT / output).resolve()
    if args.delivery and output.name == 'state_dependent_full':
        parser.error('Choose another output directory name: scenario comparisons use directory names as identifiers')
    if args.delivery and (output.parent / 'risk_amplitude_duration_sweep_5y').exists():
        parser.error('Choose an output directory in a parent without risk_amplitude_duration_sweep_5y; the legacy comparison reader also scans that neighbouring campaign')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error(f'Output must be new or empty: {output}')
    if args.delivery:
        runs = [('nominal', output), ('risques', output / 'scenario_runs/state_dependent_full'),
                ('securite_150', output / 'decision_support/actions/safety_150'),
                ('acceleration_50', output / 'decision_support/actions/expedite_50')]
        try:
            commands = [(name, run, _command(name, run, args.days)) for name, run in runs]
            graph = Path(commands[0][2][commands[0][2].index('--input') + 1])
            map_path = output / 'maps' / f'supply_graph_{output.name}.html'
            portable_path = output / 'maps/02_carte_lots_recente.html'
            map_command = _map_command(output, graph, map_path)
        except ValueError as exc:
            parser.error(str(exc))
        if args.dry_run:
            print(json.dumps({'delivery': 'lots', 'commands': [command for _, _, command in commands],
                              'map_command': map_command, 'assembly': '_assemble_diagnostic',
                              'portable_html': str(portable_path)}, ensure_ascii=False, indent=2))
            return
        _deliver(output, commands, map_command, map_path, portable_path)
        return
    try:
        command = _command(args.scenario, output, args.days, args.with_map)
    except ValueError as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps(command, ensure_ascii=False, indent=2))
        return
    bundle = _capture_sources(output, [command])
    _write(output / 'reproduction-plan.json', {
        'schema': 'etudecas.reproduction_run.v1', 'scenario': args.scenario, 'command': command,
        'source_bundle': bundle,
    })
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode == 0:
        verified_sources = _check_sources(bundle)
        _record_run(args.scenario, output, command, source_bundle=verified_sources)
        if args.with_map and not (output / 'maps' / f'supply_graph_{output.name}.html').is_file():
            raise SystemExit('Simulation completed, but the requested basic map was not generated.')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
