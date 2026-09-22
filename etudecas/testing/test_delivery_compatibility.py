"""Legacy delivery imports and commands delegate to canonical map publishers."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name,symbols', [
    ('journey_scenario_delivery', ['build_scenario_explorer', 'main']),
    ('material_delivery', ['_signature', 'refresh', 'main']),
])
def test_legacy_imports_are_canonical_functions(name, symbols):
    legacy = importlib.import_module('etudecas.testing.' + name)
    canonical = importlib.import_module('etudecas.visualization.maps.' + name)
    for symbol in symbols:
        assert getattr(legacy, symbol) is getattr(canonical, symbol)


@pytest.mark.parametrize('name', ['journey_scenario_delivery', 'material_delivery'])
@pytest.mark.parametrize('entry', ['legacy_module', 'legacy_script', 'canonical_module'])
def test_delivery_cli_help_remains_available(name, entry):
    if entry == 'legacy_script':
        arguments = [str(ROOT / 'etudecas/testing' / (name + '.py'))]
    else:
        package = 'etudecas.testing.' if entry == 'legacy_module' else 'etudecas.visualization.maps.'
        arguments = ['-m', package + name]
    result = subprocess.run([sys.executable, '-B', *arguments, '--help'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    for option in ('--data', '--graph', '--output', '--evidence'):
        assert option in result.stdout


def test_legacy_scenario_cli_publishes_with_canonical_source_paths(tmp_path):
    from .test_journey_scenario_delivery import scenario_files
    from etudecas.visualization.maps import journey_scenario_delivery as canonical

    data, graph = scenario_files(tmp_path)
    output = tmp_path / 'scenario.html'
    evidence = tmp_path / 'proof'
    result = subprocess.run([
        sys.executable, '-B', '-m', 'etudecas.testing.journey_scenario_delivery',
        '--data', str(data), '--graph', str(graph), '--output', str(output),
        '--evidence', str(evidence),
    ], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads((evidence / 'scenario-provenance.json').read_text(encoding='utf8'))
    assert report['scenario'] == 'scn:TEST'
    sources = {Path(path).resolve() for path in report['sources']}
    assert Path(canonical.__file__).resolve() in sources
    assert ROOT / 'etudecas/simulation/lot_trace/materials.py' in sources
    assert ROOT / 'etudecas/visualization/maps/lot_journey.js' in sources
    assert all(path.is_file() for path in sources)
    assert output.is_file()
