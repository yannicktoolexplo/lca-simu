import base64
import gzip
import hashlib
import io
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from etudecas.visualization.maps.html_payload_tools import (
    apply_html_payload_mode, chunk_embedded, compress_embedded, encode_json_chunk,
    externalize, extract_data_assignment, main,
)


class ExternalizeHtmlPayloadTest(unittest.TestCase):
    def sample_html(self) -> str:
        return """
        <script>
        const DATA = {"name": "abc", "nested": {"value": 3}};
        function init() { window.didInit = Boolean(DATA.nested); }
        window.addEventListener("load", init);
        </script>
        """

    def test_externalizes_data_and_defers_load_listener_init(self):
        html = self.sample_html()

        new_html, data_text = externalize(html, "map.data.json")

        self.assertEqual(json.loads(data_text)["nested"]["value"], 3)
        self.assertIn('const DATA_EXTERNAL_URL = "map.data.json"', new_html)
        self.assertIn("loadExternalMapData().then(() => {", new_html)
        self.assertIn("const DATA_EXTERNAL_URL", new_html)
        self.assertIn('document.readyState === "loading"', new_html)

    def test_externalizes_data_and_defers_direct_init_call(self):
        html = """
        <script>
        const DATA = {"label": "brace } inside string", "rows": [1, 2]};
        function init() {}
        init();
        </script>
        """

        new_html, data_text = externalize(html, "payload.json")

        self.assertEqual(json.loads(data_text)["rows"], [1, 2])
        self.assertIn("loadExternalMapData().then(() => {", new_html)
        self.assertIn('document.readyState === "loading"', new_html)

    def test_externalize_wraps_data_dependent_constants_after_loader(self):
        html = """
        <script>
        const DATA = {"nested": {"value": 9}};
        const VALUE = DATA.nested.value;
        function init() { window.didInit = VALUE; }
        window.addEventListener("load", init);
        </script>
        """

        new_html, _ = externalize(html, "payload.json")

        self.assertLess(new_html.index("loadExternalMapData().then(() => {"), new_html.index("const VALUE = DATA.nested.value"))

    def test_compress_embedded_keeps_single_html_and_defers_init(self):
        html = """
        <script>
        const DATA = {"rows": [1, 2, 3]};
        const ROWS = DATA.rows;
        function init() { window.rows = ROWS.length; }
        window.addEventListener("load", init);
        </script>
        """

        new_html, stats = compress_embedded(html, chunk_size=64)

        self.assertGreater(stats["raw_bytes"], 0)
        self.assertGreater(stats["compressed_bytes"], 0)
        self.assertIn("DATA_GZIP_BASE64_CHUNKS", new_html)
        self.assertIn("DecompressionStream", new_html)
        self.assertIn("loadEmbeddedCompressedMapData().then(() => {", new_html)
        self.assertLess(new_html.index("loadEmbeddedCompressedMapData().then(() => {"), new_html.index("const ROWS = DATA.rows"))

    def test_chunk_embedded_splits_top_level_keys_and_defers_init(self):
        html = """
        <script>
        const DATA = {"nodes": [{"id": "A"}], "lot_trace": {"lots": {"L1": {}}}, "model_panel": {"nodes": {}}, "montecarlo_uncertainty": {"available": true}, "scan_dashboard": {"available": true}};
        const NODES = DATA.nodes;
        function init() { window.nodeCount = NODES.length; }
        window.addEventListener("load", init);
        </script>
        """

        new_html, stats = chunk_embedded(html, chunk_size=64)

        self.assertEqual(stats["key_count"], 5)
        self.assertEqual(stats["manifest"]["nodes"]["group"], "core")
        self.assertEqual(stats["manifest"]["lot_trace"]["group"], "lot_trace")
        self.assertEqual(stats["manifest"]["montecarlo_uncertainty"]["group"], "uncertainty")
        self.assertEqual(stats["manifest"]["scan_dashboard"]["group"], "risk")
        self.assertIn("DATA_CHUNKED_GZIP_BASE64", new_html)
        self.assertIn("DATA_CHUNKED_MANIFEST", new_html)
        self.assertIn("loadEmbeddedChunkedMapData().then(() => {", new_html)
        self.assertIn("loadEmbeddedChunkedMapGroup", new_html)
        self.assertLess(new_html.index("loadEmbeddedChunkedMapData().then(() => {"), new_html.index("const NODES = DATA.nodes"))

    def test_apply_html_payload_mode_externalizes_and_writes_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_html = root / "nested" / "map.html"
            payload_json = root / "payloads" / "map.data.json"

            new_html = apply_html_payload_mode(
                self.sample_html(),
                output_html,
                externalize_payload=True,
                payload_json=payload_json,
                log=None,
            )

            self.assertEqual(json.loads(payload_json.read_text(encoding="utf-8"))["nested"]["value"], 3)
            self.assertIn('const DATA_EXTERNAL_URL = "../payloads/map.data.json"', new_html)

    def test_apply_html_payload_mode_rejects_multiple_modes(self):
        with self.assertRaisesRegex(ValueError, "Use only one payload mode"):
            apply_html_payload_mode(
                self.sample_html(),
                Path("map.html"),
                externalize_payload=True,
                compress_embedded_payload=True,
                log=None,
            )

    def test_apply_html_payload_mode_no_mode_keeps_html(self):
        html = self.sample_html()

        self.assertEqual(apply_html_payload_mode(html, Path("map.html"), log=None), html)

    def test_extract_preserves_json_text_and_exact_script_boundary(self):
        data_text = '{ "label": "accent é / brace } / quote \\\" / slash \\\\", "rows": [{"x": [1, null, false]}] }'
        prefix = '<html><script>\nconst DATA = '
        for suffix in (';\nconst NEXT = 1;', ' \t\r\n;\nconst NEXT = 1;', '\nconst NEXT = 1;'):
            with self.subTest(suffix=suffix):
                html = prefix + data_text + suffix
                marker, end, extracted = extract_data_assignment(html)
                self.assertEqual(marker, len('<html><script>\n'))
                self.assertEqual(extracted, data_text)
                self.assertEqual(json.loads(extracted)['rows'], [{'x': [1, None, False]}])
                self.assertEqual(html[end:].lstrip(), 'const NEXT = 1;')

    def test_extraction_and_chunking_reject_invalid_json(self):
        invalid = (
            '<script>const OTHER = {};</script>',
            '<script>const DATA = null;</script>',
            '<script>const DATA = {;</script>',
            '<script>const DATA = {"unfinished": "abc};</script>',
            '<script>const DATA = {"bad_escape": "\\q"};</script>',
            '<script>const DATA = {"bad_control": "a\nb"};</script>',
            '<script>const DATA = {"trailing": 1,};</script>',
            '<script>const DATA = {"nested": [1,2};</script>',
        )
        for html in invalid:
            for transform in (extract_data_assignment, chunk_embedded):
                with self.subTest(html=html, transform=transform.__name__):
                    with self.assertRaises(ValueError):
                        transform(html)

    def test_chunk_encoding_retains_exact_gzip_bytes_and_base64_boundaries(self):
        values = ({}, [], None, '', {'unicode': 'é 雪', 'qty': 14400.0},
                  [hashlib.sha256(str(i).encode()).hexdigest() for i in range(400)])
        for value in values:
            for width in (0, 64, 1024, 1025, 65536):
                with self.subTest(value_type=type(value).__name__, width=width):
                    chunks, raw_size, gzip_size = encode_json_chunk(value, chunk_size=width)
                    raw = json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
                    expected_gzip = gzip.compress(raw, compresslevel=9, mtime=0)
                    expected_base64 = base64.b64encode(expected_gzip).decode('ascii')
                    self.assertEqual(chunks, textwrap.wrap(expected_base64, max(1024, width)))
                    self.assertEqual(base64.b64decode(''.join(chunks)), expected_gzip)
                    self.assertEqual((raw_size, gzip_size), (len(raw), len(expected_gzip)))

    def test_chunking_decodes_assignment_only_once(self):
        calls = []
        original_decoder = json.JSONDecoder

        class CountingDecoder(original_decoder):
            def raw_decode(self, text, idx=0):
                calls.append((text, idx))
                return super().raw_decode(text, idx)

        with patch('etudecas.visualization.maps.html_payload_tools.json.JSONDecoder', CountingDecoder), \
             patch('etudecas.visualization.maps.html_payload_tools.json.loads', side_effect=AssertionError('extra parse')):
            html, stats = chunk_embedded(self.sample_html())
        self.assertEqual(len(calls), 1)
        self.assertEqual(stats['key_count'], 2)
        self.assertIn('const DATA_CHUNKED_GZIP_BASE64', html)

    def test_chunking_still_rejects_missing_script_close_or_init(self):
        for html in ('<script>const DATA = {}; init();', '<script>const DATA = {};</script>'):
            with self.subTest(html=html):
                with self.assertRaises(ValueError):
                    chunk_embedded(html)

    def test_unified_cli_dry_run_preserves_files_for_every_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.html"
            source.write_text(self.sample_html(), encoding="utf-8")
            original = source.read_bytes()
            for mode in ("external", "compressed", "chunked"):
                with self.subTest(mode=mode), redirect_stdout(io.StringIO()):
                    main(["--mode", mode, "--input", str(source)])
                    self.assertEqual(list(root.iterdir()), [source])
                    self.assertEqual(source.read_bytes(), original)

    def test_unified_cli_outputs_recover_the_input_payload(self):
        import re
        expected = {"name": "abc", "nested": {"value": 3}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.html"
            source.write_text(self.sample_html(), encoding="utf-8")
            for mode in ("external", "compressed", "chunked"):
                with self.subTest(mode=mode), redirect_stdout(io.StringIO()):
                    main(["--mode", mode, "--input", str(source), "--execute"])
                    document = source.with_suffix(f".{mode}.html").read_text(encoding="utf-8")
                    if mode == "external":
                        actual = json.loads(source.with_suffix(".external.data.json").read_text(encoding="utf-8"))
                        self.assertIn('const DATA_EXTERNAL_URL = "input.external.data.json"', document)
                    elif mode == "compressed":
                        chunks = json.loads(re.search(r"const DATA_GZIP_BASE64_CHUNKS = (.*?);", document).group(1))
                        actual = json.loads(gzip.decompress(base64.b64decode("".join(chunks))))
                    else:
                        chunks = json.loads(re.search(r"const DATA_CHUNKED_GZIP_BASE64 = (.*?);", document).group(1))
                        actual = {key: json.loads(gzip.decompress(base64.b64decode("".join(value))))
                                  for key, value in chunks.items()}
                    self.assertEqual(actual, expected)

    def test_unified_cli_refuses_inapplicable_external_destination(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["--mode", "chunked", "--input", "unused.html", "--data-output", "unused.json"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
