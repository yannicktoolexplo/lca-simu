import json
import tempfile
import unittest
import csv
from pathlib import Path

from etudecas.visualization.maps.montecarlo_trajectory_payload import build_montecarlo_trajectory_assets


class MonteCarloTrajectoryPayloadTest(unittest.TestCase):
    def test_builds_reusable_scenario_tube_figures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "driver_rankings": {
                            "kpi::fill_rate": [
                                {"factor": "supplier_reliability_node::SDC-A", "correlation": 0.8},
                            ],
                            "kpi::ending_backlog": [
                                {"factor": "supplier_reliability_node::SDC-A", "correlation": -0.7},
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
            with (root / "montecarlo_samples.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["run_id", "status", "is_baseline", "supplier_reliability_node::SDC-A"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "run_id": "run_0000",
                        "status": "ok",
                        "is_baseline": "True",
                        "supplier_reliability_node::SDC-A": "1.0",
                    }
                )
                for idx, value in enumerate([0.70, 0.75, 1.10, 1.15], start=1):
                    writer.writerow(
                        {
                            "run_id": f"run_{idx:04d}",
                            "status": "ok",
                            "is_baseline": "False",
                            "supplier_reliability_node::SDC-A": str(value),
                        }
                    )
            (root / "montecarlo_trajectories.json").write_text(
                json.dumps(
                    {
                        "schema_version": "etudecas.montecarlo_trajectories.v1",
                        "days": [0, 1],
                        "run_count": 5,
                        "stochastic_run_count": 4,
                        "metrics": {
                            "service_rate": {
                                "label": "Service",
                                "y_label": "%",
                                "reference_value": 100,
                                "reference_label": "service 100%",
                                "bands": {
                                    "p05": [98, 97],
                                    "p10": [98.2, 97.2],
                                    "p25": [98.5, 97.5],
                                    "p50": [99, 98],
                                    "p75": [99.5, 99],
                                    "p90": [99.8, 99.8],
                                    "p95": [100, 100],
                                },
                                "series_total_count": 2,
                                "series_display_count": 2,
                                "series": [
                                    {"run_id": "run_0000", "label": "Nominal", "is_baseline": True, "values": [100, 100]},
                                    {"run_id": "run_0001", "label": "run_0001", "is_baseline": False, "values": [99, 98]},
                                    {"run_id": "run_0002", "label": "run_0002", "is_baseline": False, "values": [98, 96]},
                                    {"run_id": "run_0003", "label": "run_0003", "is_baseline": False, "values": [100, 100]},
                                    {"run_id": "run_0004", "label": "run_0004", "is_baseline": False, "values": [100, 99]},
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            assets = build_montecarlo_trajectory_assets(summary)

        self.assertTrue(assets["available"])
        figure = assets["figures"]["service_rate"]
        self.assertEqual(figure["kind"], "line_multi")
        self.assertIn("Disponibilite produit", figure["title"])
        self.assertEqual(figure["reference_line_label"], "disponibilite 100%")
        self.assertTrue(figure["scenario_tube"])
        self.assertTrue(figure["fan_bands"])
        self.assertTrue(figure["preserve_sparse_days"])
        self.assertEqual(figure["fan_band_percentiles"][0], [0.05, 0.95])
        self.assertEqual(figure["fan_band_values"][0]["label"], "min-max (toutes courbes)")
        self.assertEqual(figure["fan_band_values"][0]["low"], [98.0, 96.0])
        self.assertEqual(figure["fan_band_values"][0]["high"], [100.0, 100.0])
        self.assertEqual(figure["fan_band_values"][1]["label"], "5-95%")
        self.assertEqual(figure["fan_median_values"], [99, 98])
        self.assertEqual(figure["fan_series_total_count"], 2)
        self.assertEqual(figure["reference_line_value"], 100.0)
        self.assertEqual(figure["series"][0]["label"], "Nominal")
        self.assertTrue(figure["series"][0]["is_nominal"])
        self.assertEqual(assets["metric_summaries"]["service_rate"]["p50_final"], 98.0)
        self.assertEqual(assets["metric_summaries"]["service_rate"]["p95_max"], 100.0)
        factor_figure = assets["factor_tube_figures"]["service_rate"]
        self.assertEqual(factor_figure["kind"], "factor_tubes")
        self.assertIn("Disponibilite produit", factor_figure["title"])
        self.assertEqual(factor_figure["bands"][0]["label"], "Fiabilite fournisseur SDC-A")
        self.assertEqual(factor_figure["bands"][0]["low_group_count"], 1)
        self.assertEqual(factor_figure["bands"][0]["high_group_count"], 1)
        self.assertEqual(factor_figure["nominal"]["values"], [100.0, 100.0])
        self.assertIsNotNone(assets["overview_bundle"])


if __name__ == "__main__":
    unittest.main()
