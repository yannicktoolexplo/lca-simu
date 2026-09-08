import json
import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps.compress_html_payload import compress_embedded
from etudecas.visualization.maps.chunk_html_payload import chunk_embedded
from etudecas.visualization.maps.externalize_html_payload import externalize
from etudecas.visualization.maps.html_payload_tools import apply_html_payload_mode


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


if __name__ == "__main__":
    unittest.main()
