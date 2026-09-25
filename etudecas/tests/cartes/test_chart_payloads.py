from __future__ import annotations

import base64
import math
import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps.chart_payloads import (
    build_bar_chart_figure,
    build_dual_panel_figure,
    build_line_chart_figure,
    densify_daily_series,
    densify_event_spike_series,
    load_png_payload,
    png_payload_from_bytes,
    resolve_plot_payload,
)


class ChartPayloadsTest(unittest.TestCase):
    def test_png_payload_from_bytes_encodes_image_bytes(self) -> None:
        payload = png_payload_from_bytes(b"abc", "plot.png")

        self.assertEqual(payload["mime"], "image/png")
        self.assertEqual(payload["filename"], "plot.png")
        self.assertEqual(base64.b64decode(payload["data_b64"]), b"abc")

    def test_load_and_resolve_png_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "charts"
            nested.mkdir()
            (nested / "current.png").write_bytes(b"new")
            (root / "legacy.png").write_bytes(b"old")

            direct = load_png_payload(nested / "current.png")
            resolved = resolve_plot_payload(root, Path("charts") / "current.png", "legacy.png")

            self.assertIsNotNone(direct)
            self.assertEqual(base64.b64decode(direct["data_b64"]), b"new")
            self.assertIsNotNone(resolved)
            self.assertEqual(base64.b64decode(resolved["data_b64"]), b"new")

    def test_resolve_plot_payload_falls_back_to_legacy_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "legacy.png").write_bytes(b"old")

            resolved = resolve_plot_payload(root, Path("missing") / "current.png", "legacy.png")

            self.assertIsNotNone(resolved)
            self.assertEqual(base64.b64decode(resolved["data_b64"]), b"old")

    def test_densify_daily_series_fills_missing_days(self) -> None:
        self.assertEqual(densify_daily_series([(3, 2.0), (1, 4.0)]), [(1, 4.0), (2, 0.0), (3, 2.0)])

    def test_densify_event_spike_series_sums_duplicate_days(self) -> None:
        self.assertEqual(
            densify_event_spike_series([(2, 1.5), (1, 4.0), (2, 2.5)]),
            [(1, 0.0), (1, 4.0), (1, 0.0), (2, 0.0), (2, 4.0), (2, 0.0)],
        )

    def test_build_line_chart_figure_densifies_step_like_series(self) -> None:
        figure = build_line_chart_figure({"stock": [(1, 5.0), (3, 7.0)]}, title="Stock", y_label="Qty", step_like=True)

        self.assertIsNotNone(figure)
        self.assertEqual(figure["kind"], "line_multi")
        self.assertTrue(figure["step_like"])
        self.assertEqual(figure["series"][0]["days"], [1, 2, 3])
        self.assertEqual(figure["series"][0]["values"], [5.0, 0.0, 7.0])

    def test_build_bar_chart_figure_skips_missing_values(self) -> None:
        figure = build_bar_chart_figure({"A": 1.0, "B": None, "C": math.nan}, title="Bars", y_label="Qty")

        self.assertEqual(figure, {"kind": "bar", "title": "Bars", "y_label": "Qty", "labels": ["A"], "values": [1.0]})

    def test_build_dual_panel_figure_requires_at_least_one_panel(self) -> None:
        self.assertIsNone(
            build_dual_panel_figure(
                title="Empty",
                top_title="Top",
                top_x_label="x",
                top_y_label="y",
                top_kind="line",
                top_x=[],
                top_y=[],
                bottom_title="Bottom",
                bottom_x_label="x",
                bottom_y_label="y",
                bottom_kind="bar",
                bottom_x=[],
                bottom_y=[],
            )
        )


if __name__ == "__main__":
    unittest.main()
