from __future__ import annotations

import unittest

from etudecas.visualization.maps.map_render import (
    data_html_asset,
    fmt_qty,
    render_data_kv,
    render_data_table,
)


class MapRenderTest(unittest.TestCase):
    def test_data_html_asset_renders_escaped_panel(self) -> None:
        table_html = render_data_table(["Col & A"], [["x<y", None]])
        kv_html = render_data_kv([("Quantite", fmt_qty(1234.5, 1))])

        asset = data_html_asset(
            "Titre <carte>",
            "Sous & titre",
            [("Section <1>", table_html + kv_html)],
        )
        html = asset["html"]

        self.assertIn("factoryHtmlPanelContent dataSummaryPanelContent", html)
        self.assertIn("Titre &lt;carte&gt;", html)
        self.assertIn("Sous &amp; titre", html)
        self.assertIn("Section &lt;1&gt;", html)
        self.assertIn("<th>Col &amp; A</th>", html)
        self.assertIn("<td>x&lt;y</td>", html)
        self.assertIn("<td>n/a</td>", html)
        self.assertIn("1 234.5", html)


if __name__ == "__main__":
    unittest.main()
