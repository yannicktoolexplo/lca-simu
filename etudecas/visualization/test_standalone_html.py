"""The shared publisher and archive reconstruction work without prototype imports."""
from pathlib import Path
import subprocess
import sys

from etudecas.visualization import standalone_html


ROOT = Path(__file__).resolve().parents[2]


def test_archive_publisher_import_does_not_require_research_modules():
    code = '''
import importlib.abc
import sys
class RejectResearch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'etudecas.prototypes' or fullname.startswith('etudecas.prototypes.'):
            raise AssertionError('Unexpected research dependency: ' + fullname)
sys.meta_path.insert(0, RejectResearch())
from etudecas.visualization.maps import enrich_supplier_audit_archive
from etudecas.visualization import standalone_html
assert enrich_supplier_audit_archive.standalone is standalone_html
'''
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


def test_canonical_module_and_direct_cli_keep_the_same_arguments():
    outputs = []
    for entry in [
        ['-m', 'etudecas.visualization.standalone_html'],
        ['etudecas/visualization/standalone_html.py'],
    ]:
        result = subprocess.run([sys.executable, '-B', *entry, '--help'], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        outputs.append(result.stdout[result.stdout.index('options:'):])
    assert outputs[0] == outputs[1]


def test_reassembly_uses_embedded_resources_after_source_package_moves(tmp_path):
    from etudecas.visualization.rebuild_archives import rebuild

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'index.html').write_text(
        '<!doctype html><html><head><title>Archive</title></head><body>'
        '<a href="view.html">Vue</a><a href="evidence.csv">Source</a></body></html>', encoding='utf-8')
    (source / 'view.html').write_text(
        '<!doctype html><html><head><title>Vue</title></head><body>'
        '<p>Quantité : 17 UN</p></body></html>', encoding='utf-8')
    (source / 'evidence.csv').write_bytes(b'item,qty\n338929,17\n')
    archived = tmp_path / 'archived.html'
    standalone_html.build_single_html(source, archived)
    source.rename(tmp_path / 'source_no_longer_at_recorded_path')
    output = tmp_path / 'rebuilt.html'
    result = rebuild('demonstration', archived, output)
    assert output.read_bytes() == archived.read_bytes()
    assert result['detail']['views'] == 1
    assert result['simulation_recomputed'] is False
    assert result['external_research_directory_used'] is False


def test_archive_reassembly_refuses_corrupted_embedded_evidence(tmp_path):
    import pytest
    from etudecas.visualization.rebuild_archives import rebuild, _replace_assignment

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'index.html').write_text(
        '<!doctype html><html><head><title>Archive</title></head><body>'
        '<a href="evidence.csv">Source</a></body></html>', encoding='utf-8')
    (source / 'evidence.csv').write_bytes(b'qty\n17\n')
    archived = tmp_path / 'archived.html'
    standalone_html.build_single_html(source, archived)
    document = archived.read_text(encoding='utf-8')
    entries = standalone_html.runtime_json_assignment(document, 'const files = ')
    entries['evidence.csv']['gzip_base64'] = standalone_html.gzip_base64(b'qty\n18\n')
    archived.write_text(_replace_assignment(document, 'const files = ', entries), encoding='utf-8')
    output = tmp_path / 'must_not_exist.html'
    with pytest.raises(ValueError):
        rebuild('demonstration', archived, output)
    assert not output.exists()


def test_reassembly_never_overwrites_and_refuses_ambiguous_campaign(tmp_path):
    import pytest
    from etudecas.visualization.rebuild_archives import rebuild

    protected = tmp_path / 'protected.html'
    protected.write_bytes(b'keep me')
    with pytest.raises(FileExistsError):
        rebuild('demonstration', tmp_path / 'missing.html', protected)
    assert protected.read_bytes() == b'keep me'
    invalid = tmp_path / 'invalid.html'
    invalid.write_text('<script id="campaign-data" type="application/json">{}</script>' * 2)
    output = tmp_path / 'must_not_exist.html'
    with pytest.raises(ValueError, match='exactly one'):
        rebuild('supply_chains', invalid, output)
    assert not output.exists()
