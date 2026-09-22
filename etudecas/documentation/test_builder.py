from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etudecas.documentation.builder import (
    DEFAULT_OUTPUT, DEFAULT_REGISTRY, DocumentationError, FINGERPRINT_METHOD,
    FORMAT_VERSION, REPO_ROOT, inspect_reference, load_registry, run, watch,
)


class DocumentationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "engine.py"
        self.source.write_text("raise RuntimeError('must not execute')\ndef flow(qty: float = 1.0):\n    return qty\n", encoding="utf-8")
        (self.root / "test_engine.py").write_text("def test_flow():\n    assert True\n", encoding="utf-8")
        (self.root / "business.md").write_text("Quantity is conserved.\n", encoding="utf-8")
        self.registry_path = self.root / "rules.json"
        self.output = self.root / "docs"
        self.registry = {
            "schema_version": FORMAT_VERSION, "fingerprint_method": FINGERPRINT_METHOD,
            "title": "Pilot",
            "business_source_fingerprints": {"business.md": hashlib.sha256(b"Quantity is conserved.\n").hexdigest()},
            "references": [
                {"id": "flow", "path": "engine.py", "symbol": "flow", "kind": "implementation", "reference_fingerprint": "0" * 64},
                {"id": "test", "path": "test_engine.py", "symbol": "test_flow", "kind": "test", "reference_fingerprint": "0" * 64},
            ],
            "rules": [{"id": "FLOW-001", "title": "Conservation", "statement": "Conserve quantity",
                       "units": "kg", "scope": "Transport", "limitations": "Not business validated",
                       "status": "documented", "references": ["flow", "test"], "sources": ["business.md"]}],
        }
        for ref in self.registry["references"]:
            ref["reference_fingerprint"] = inspect_reference(self.root, ref, {})["fingerprint"]
        self.save_registry()

    def save_registry(self) -> None:
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")

    def execute(self, command: str) -> int:
        with redirect_stdout(io.StringIO()):
            return run(command, root=self.root, registry_path=self.registry_path, output=self.output)

    def test_build_is_static_deterministic_and_check_detects_manual_damage(self) -> None:
        self.assertEqual(self.execute("build"), 0)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(self.execute("build"), 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        self.assertEqual(self.execute("check"), 0)
        (self.output / "index.md").write_text("outdated", encoding="utf-8")
        self.assertEqual(self.execute("check"), 1)

    def test_code_drift_requires_review_even_after_regeneration(self) -> None:
        baseline = self.registry_path.read_bytes()
        self.source.write_text("def flow(qty: float = 1.0):\n    return qty * 2\n", encoding="utf-8")
        self.assertEqual(self.execute("build"), 1)
        self.assertEqual(self.execute("check"), 1)
        self.assertEqual(self.registry_path.read_bytes(), baseline)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["rules"][0]["changed_references"], ["flow"])
        self.assertFalse(manifest["tests_executed"])

    def test_business_source_change_requires_review(self) -> None:
        (self.root / "business.md").write_text("Quantity may be lost.\n", encoding="utf-8")
        self.assertEqual(self.execute("build"), 1)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["rules"][0]["changed_business_sources"], ["business.md"])

    def test_crlf_and_formatting_do_not_change_symbol_fingerprint(self) -> None:
        ref = self.registry["references"][0]
        self.source.write_bytes(b"# comment\r\ndef flow( qty: float=1.0 ):\r\n    return qty\r\n")
        self.assertEqual(inspect_reference(self.root, ref, {})["fingerprint"], ref["reference_fingerprint"])

    def test_broken_symbol_is_not_silently_ignored(self) -> None:
        self.source.write_text("def renamed():\n    return 1\n", encoding="utf-8")
        with self.assertRaisesRegex(DocumentationError, "Symbol not found"):
            self.execute("build")

    def test_unknown_link_duplicate_id_missing_test_and_source_are_rejected(self) -> None:
        for mutation in ("unknown", "duplicate", "no_test", "missing_source"):
            with self.subTest(mutation=mutation):
                original = json.loads(json.dumps(self.registry))
                if mutation == "unknown":
                    self.registry["rules"][0]["references"].append("missing")
                elif mutation == "duplicate":
                    self.registry["rules"].append(self.registry["rules"][0].copy())
                elif mutation == "no_test":
                    self.registry["rules"][0]["references"] = ["flow"]
                else:
                    self.registry["rules"][0]["sources"] = ["missing.md"]
                self.save_registry()
                with self.assertRaises(DocumentationError):
                    load_registry(self.root, self.registry_path)
                self.registry = original

    def test_outside_repository_reference_is_rejected(self) -> None:
        self.registry["references"][0]["path"] = "../outside.py"
        self.save_registry()
        with self.assertRaisesRegex(DocumentationError, "outside repository"):
            load_registry(self.root, self.registry_path)

    def test_class_method_reference_has_real_signature(self) -> None:
        self.source.write_text("class Engine:\n    def flow(self, qty: int) -> int:\n        return qty\n", encoding="utf-8")
        ref = dict(self.registry["references"][0], symbol="Engine.flow")
        actual = inspect_reference(self.root, ref, {})
        self.assertEqual(actual["declaration"], "def flow(self, qty: int) -> int:")

    def test_watch_regenerates_changed_sources_without_accepting_them(self) -> None:
        calls = 0

        def edit_then_stop(_interval: float) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                self.source.write_text("def flow(qty: float = 1.0):\n    return qty + 10\n", encoding="utf-8")
            else:
                raise KeyboardInterrupt

        with patch("etudecas.documentation.builder.time.sleep", side_effect=edit_then_stop), redirect_stdout(io.StringIO()):
            self.assertEqual(watch(root=self.root, registry_path=self.registry_path, output=self.output, interval=0.1), 0)
        self.assertEqual(self.execute("check"), 1)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["rules"][0]["changed_references"], ["flow"])

    def test_repository_documentation_is_current(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run("check", root=REPO_ROOT, registry_path=REPO_ROOT / DEFAULT_REGISTRY,
                                 output=REPO_ROOT / DEFAULT_OUTPUT), 0,
                             "Run python -m etudecas.documentation check for details")

    def test_run_package_documentation_is_current(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run("check", root=REPO_ROOT,
                                 registry_path=REPO_ROOT / "etudecas/docs/rules/run_package.json",
                                 output=REPO_ROOT / "etudecas/docs/generated/run_package"), 0)

    def test_supplier_actions_documentation_is_current(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run("check", root=REPO_ROOT,
                                 registry_path=REPO_ROOT / "etudecas/docs/rules/supplier_actions.json",
                                 output=REPO_ROOT / "etudecas/docs/generated/supplier_actions"), 0)


if __name__ == "__main__":
    unittest.main()
