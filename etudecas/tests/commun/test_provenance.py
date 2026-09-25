from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from etudecas.provenance import diagnose_source_hash, main


class SourceProvenanceTest(unittest.TestCase):
    def test_diagnostic_distinguishes_exact_newlines_and_content_without_writing(self):
        baseline = b"def f():\n    return 1\n"
        expected = hashlib.sha256(baseline).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.py"
            for raw, status, exit_code in (
                (baseline, "exact_match", 0),
                (baseline.replace(b"\n", b"\r\n"), "line_endings_only", 1),
                (baseline.replace(b"1", b"2"), "content_mismatch", 1),
                (b"\xff\xfe", "content_mismatch", 1),
            ):
                with self.subTest(status=status, raw=raw):
                    source.write_bytes(raw)
                    self.assertEqual(diagnose_source_hash(source, expected)["status"], status)
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(main(["--path", str(source), "--expected-sha256", expected]), exit_code)
                    self.assertEqual(source.read_bytes(), raw)

    def test_invalid_inputs_report_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            for expected in ("invalid", "0" * 64):
                with self.subTest(expected=expected), redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--path", str(Path(tmp) / "missing.py"),
                                           "--expected-sha256", expected]), 2)
