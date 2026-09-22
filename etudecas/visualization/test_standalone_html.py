"""The shared publisher keeps legacy consumers working without prototype imports."""
from pathlib import Path
import subprocess
import sys

from etudecas.visualization import standalone_html


ROOT = Path(__file__).resolve().parents[2]


def test_legacy_module_and_mutable_limits_share_the_implementation(monkeypatch):
    from etudecas.prototypes.scan_2027_risk_control import standalone_single_html

    assert standalone_single_html is standalone_html
    monkeypatch.setattr(standalone_single_html, 'MAX_ENTRY_BYTES', 17)
    assert standalone_html.MAX_ENTRY_BYTES == 17
    assert standalone_html.decoded_entry is standalone_single_html._decoded_entry


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


def test_canonical_and_legacy_cli_keep_the_same_arguments():
    outputs = []
    for entry in [
        ['-m', 'etudecas.visualization.standalone_html'],
        ['-m', 'etudecas.prototypes.scan_2027_risk_control.standalone_single_html'],
        ['etudecas/prototypes/scan_2027_risk_control/standalone_single_html.py'],
    ]:
        result = subprocess.run([sys.executable, '-B', *entry, '--help'], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        outputs.append(result.stdout[result.stdout.index('options:'):])
    assert outputs[0] == outputs[1] == outputs[2]
