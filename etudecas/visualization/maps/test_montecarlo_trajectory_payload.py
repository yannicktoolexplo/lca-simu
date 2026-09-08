import json
import tempfile
import unittest
import csv
from pathlib import Path

from etudecas.visualization.maps.montecarlo_trajectory_payload import build_montecarlo_trajectory_assets


class MonteCarloTrajectoryPayloadTest(unittest.TestCase):
    def test_loads_cost_perimeters_without_trajectories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(json.dumps({}), encoding="utf-8")
            (root / "montecarlo_cost_diagnostics.json").write_text(
                json.dumps(
                    {
                        "sample_count": 200,
                        "total_cost": {"baseline": 100.0, "median": 110.0},
                        "cost_without_production": {"baseline": 70.0, "median": 77.0},
                        "economic_exposure_including_exceptional_supply": {
                            "baseline": 140.0,
                            "median": 165.0,
                        },
                        "components": {"exceptional_supply": {"baseline": 40.0, "median": 55.0}},
                        "production_cost_coupling": {
                            "median_share_of_total": 0.3,
                            "mechanical_amplification_factor": 10.0 / 7.0,
                        },
                        "exceptional_supply_cost": {"included_in_total_cost": False},
                        "accounting_identity": {"valid_within_tolerance": True},
                    }
                ),
                encoding="utf-8",
            )

            assets = build_montecarlo_trajectory_assets(summary)

        costs = assets["cost_diagnostics"]
        self.assertTrue(costs["available"])
        self.assertEqual(costs["sample_count"], 200)
        self.assertEqual(costs["economic_exposure"]["median"], 165.0)
        self.assertAlmostEqual(costs["production_amplification"], 10.0 / 7.0)
        self.assertFalse(costs["exceptional_in_total"])

    def test_loads_optional_variance_decomposition_without_trajectories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(json.dumps({}), encoding="utf-8")
            (root / "variance_decomposition.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "method": {"name": "cross_validated_grouped_permutation_ridge", "is_sobol": False},
                        "source": {"stochastic_success_count": 200},
                        "kpis": {
                            "kpi::total_cost": {
                                "status": "ok",
                                "sample_count": 200,
                                "explained_percent": 80.0,
                                "residual_interactions_unexplained_percent": 20.0,
                                "families": [
                                    {
                                        "family": "holding_cost",
                                        "label": "Holding cost",
                                        "factor_count": 1,
                                        "explained_variance_percent": 65.0,
                                    },
                                    {
                                        "family": "transport_cost",
                                        "label": "Transport cost",
                                        "factor_count": 1,
                                        "explained_variance_percent": 15.0,
                                    },
                                ],
                            },
                            "kpi::ending_backlog": {
                                "status": "constant_kpi",
                                "sample_count": 200,
                                "explained_percent": 0.0,
                                "residual_interactions_unexplained_percent": 100.0,
                                "families": [],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            assets = build_montecarlo_trajectory_assets(summary)

        self.assertFalse(assets["available"])
        decomposition = assets["variance_decomposition"]
        self.assertTrue(decomposition["available"])
        self.assertEqual(decomposition["status"], "available")
        self.assertEqual(len(decomposition["kpis"]), 1)
        self.assertEqual(decomposition["kpis"][0]["label"], "Cout supply total")
        self.assertEqual(decomposition["kpis"][0]["explained_percent"], 80.0)
        self.assertEqual(decomposition["kpis"][0]["residual_percent"], 20.0)
        self.assertEqual(decomposition["figure"]["kind"], "stacked_bar_horizontal")
        self.assertEqual(
            [series["label"] for series in decomposition["figure"]["series"]],
            ["Cout de possession", "Cout transport", "Interactions / non-linearites / non expliquee"],
        )
        self.assertIn("pas une causalite terrain", decomposition["warning"])
        self.assertIn("ni une decomposition de Sobol", decomposition["warning"])

    def test_missing_variance_decomposition_is_non_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(json.dumps({}), encoding="utf-8")

            assets = build_montecarlo_trajectory_assets(summary)

        decomposition = assets["variance_decomposition"]
        self.assertFalse(decomposition["available"])
        self.assertEqual(decomposition["status"], "missing")
        self.assertEqual(decomposition["kpis"], [])
        self.assertIsNone(decomposition["figure"])

    def test_worldmap_template_renders_variance_decomposition_asset(self) -> None:
        template_source = (Path(__file__).with_name("worldmap_html_template.py")).read_text(encoding="utf-8")

        self.assertIn('figure.kind === "stacked_bar_horizontal"', template_source)
        self.assertIn("Decomposition de la dispersion Monte Carlo", template_source)
        self.assertIn("Interactions / non-linearites / non expliquee", template_source)
        self.assertIn("varianceDecomposition.warning", template_source)
        self.assertIn("Lecture economique des couts Monte Carlo", template_source)
        self.assertIn("Exposition economique combinee", template_source)

    def test_excludes_systemic_supplier_reliability_from_paired_operational_tubes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(json.dumps({}), encoding="utf-8")
            (root / "montecarlo_trajectories.json").write_text(
                json.dumps(
                    {
                        "days": [0, 1],
                        "metrics": {
                            "service_rate": {
                                "label": "Service",
                                "y_label": "%",
                                "series": [
                                    {
                                        "run_id": "run_0000",
                                        "is_baseline": True,
                                        "values": [100, 100],
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "montecarlo_paired_propagation.json").write_text(
                json.dumps(
                    {
                        "method": "paired_controlled_runs",
                        "input_relative_uncertainty": 0.20,
                        "days": [0, 1],
                        "metrics": {
                            "service_rate": {
                                "factors": [
                                    {
                                        "factor": "factor::supplier_reliability_scale",
                                        "center": [100, 100],
                                        "low": [80, 80],
                                        "high": [100, 100],
                                        "max_width": 20,
                                    },
                                    {
                                        "factor": "supplier_reliability_node::SDC-A",
                                        "family": "reliability",
                                        "node_id": "SDC-A",
                                        "center": [100, 100],
                                        "low": [98, 97],
                                        "high": [100, 100],
                                        "max_width": 3,
                                    },
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            assets = build_montecarlo_trajectory_assets(summary)

        bands = assets["factor_tube_figures"]["service_rate"]["bands"]
        self.assertEqual([band["factor"] for band in bands], ["supplier_reliability_node::SDC-A"])

    def test_prefers_controlled_paired_propagation_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(json.dumps({}), encoding="utf-8")
            (root / "montecarlo_trajectories.json").write_text(
                json.dumps(
                    {
                        "schema_version": "etudecas.montecarlo_trajectories.v1",
                        "days": [0, 1],
                        "run_count": 3,
                        "stochastic_run_count": 2,
                        "metrics": {
                            "service_rate": {
                                "label": "Service",
                                "y_label": "%",
                                "bands": {"p50": [100, 99]},
                                "series": [
                                    {
                                        "run_id": "run_0000",
                                        "label": "Nominal",
                                        "is_baseline": True,
                                        "values": [100, 100],
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "montecarlo_paired_propagation.json").write_text(
                json.dumps(
                    {
                        "schema_version": "etudecas.paired_uncertainty_propagation.v1",
                        "method": "paired_controlled_runs",
                        "input_relative_uncertainty": 0.20,
                        "background_count": 5,
                        "run_count": 15,
                        "days": [0, 1],
                        "metrics": {
                            "service_rate": {
                                "factors": [
                                    {
                                        "factor": "supplier_lead_node::SDC-A",
                                        "family": "lead",
                                        "node_id": "SDC-A",
                                        "background_count": 5,
                                        "input_low": 0.8,
                                        "input_high": 1.2,
                                        "center": [100, 99],
                                        "low": [98, 94],
                                        "high": [100, 100],
                                        "max_width": 6,
                                    }
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            assets = build_montecarlo_trajectory_assets(summary)

        figure = assets["factor_tube_figures"]["service_rate"]
        self.assertEqual(assets["factor_tube_source"], "paired_controlled_runs")
        self.assertTrue(figure["paired_controlled"])
        self.assertEqual(figure["method"], "paired_controlled_runs")
        self.assertEqual(figure["bands"][0]["low"], [98.0, 95.0])
        self.assertEqual(figure["bands"][0]["high"], [100.0, 100.0])
        self.assertEqual(figure["nominal"]["values"], [100.0, 100.0])

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
        self.assertIn("global_context", factor_figure)
        self.assertIn(
            "Monte Carlo global 5-95%",
            [band["label"] for band in factor_figure["global_context"]["bands"]],
        )
        self.assertEqual(factor_figure["global_context"]["median"], [99.0, 98.0])
        self.assertEqual(factor_figure["bands"][0]["low_group_median"], [99.0, 98.0])
        self.assertEqual(factor_figure["bands"][0]["high_group_median"], [100.0, 99.0])
        self.assertGreater(factor_figure["bands"][0]["explained_share"], 0)
        self.assertEqual(factor_figure["nominal"]["values"], [100.0, 100.0])
        self.assertIsNotNone(assets["overview_bundle"])

    def test_supplier_capacity_binding_uses_event_sensitive_grouping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "montecarlo_summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "driver_rankings": {
                            "kpi::total_supplier_capacity_binding_qty": [
                                {"factor": "supplier_capacity_node::SDC-A", "correlation": 0.8},
                            ],
                            "kpi::total_cost": [
                                {"factor": "capacity_node::M-1", "correlation": 0.9},
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
            fieldnames = [
                "run_id",
                "status",
                "is_baseline",
                "supplier_capacity_node::SDC-A",
                "capacity_node::M-1",
            ]
            with (root / "montecarlo_samples.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "run_id": "run_0000",
                        "status": "ok",
                        "is_baseline": "True",
                        "supplier_capacity_node::SDC-A": "1.0",
                        "capacity_node::M-1": "1.0",
                    }
                )
                for idx in range(1, 21):
                    writer.writerow(
                        {
                            "run_id": f"run_{idx:04d}",
                            "status": "ok",
                            "is_baseline": "False",
                            "supplier_capacity_node::SDC-A": f"{0.5 + idx * 0.05:.2f}",
                            "capacity_node::M-1": f"{1.5 - idx * 0.02:.2f}",
                        }
                    )
            series = [
                {"run_id": "run_0000", "label": "Nominal", "is_baseline": True, "values": [0, 0]},
            ]
            for idx in range(1, 21):
                late_value = 1000 if idx == 20 else 0
                series.append(
                    {
                        "run_id": f"run_{idx:04d}",
                        "label": f"run_{idx:04d}",
                        "is_baseline": False,
                        "values": [0, late_value],
                    }
                )
            (root / "montecarlo_trajectories.json").write_text(
                json.dumps(
                    {
                        "schema_version": "etudecas.montecarlo_trajectories.v1",
                        "days": [0, 1000],
                        "run_count": 21,
                        "stochastic_run_count": 20,
                        "metrics": {
                            "supplier_capacity_binding": {
                                "label": "Contrainte capacite fournisseur",
                                "y_label": "Quantite contrainte / jour",
                                "bands": {"p50": [0, 0], "p95": [0, 1000]},
                                "series": series,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            assets = build_montecarlo_trajectory_assets(summary)

        factor_figure = assets["factor_tube_figures"]["supplier_capacity_binding"]
        first_band = factor_figure["bands"][0]
        self.assertEqual(first_band["label"], "Capacite fournisseur SDC-A")
        self.assertEqual(first_band["aggregation"], "p90")
        self.assertEqual(first_band["aggregation_label"], "percentile 90 de groupe")
        self.assertGreater(first_band["high"][-1], 0)
        self.assertIn("global_context", factor_figure)
        self.assertGreater(factor_figure["global_context"]["max_spread"], 0)
        self.assertIn("evenements tardifs", factor_figure["note"])


if __name__ == "__main__":
    unittest.main()
