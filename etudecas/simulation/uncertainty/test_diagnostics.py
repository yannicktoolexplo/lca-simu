import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.uncertainty import build_uncertainty_diagnostics


class UncertaintyDiagnosticsTest(unittest.TestCase):
    def test_builds_diagnostics_from_montecarlo_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected"
            selected.mkdir()
            summary = {
                "scenario_id": "scn:BASE",
                "seed": 123,
                "days_override": 30,
                "uncertainty_profile": "stress_probe",
                "runs_requested_excluding_baseline": 2,
                "successful_runs": 4,
                "successful_stochastic_runs": 3,
                "failed_runs": 0,
                "decision_metrics": {"fill_rate_below_99pct": 0.5},
                "metric_statistics": {
                    "kpi::fill_rate": {"baseline": 1.0, "p05": 0.8, "p50": 0.9, "p95": 1.0, "max": 1.0},
                    "kpi::ending_backlog": {"baseline": 0, "p05": 0, "p50": 10, "p95": 100, "max": 120},
                    "kpi::total_cost": {"baseline": 1000, "p05": 1000, "p50": 1200, "p95": 1600, "max": 1700},
                },
                "driver_rankings": {
                    "kpi::fill_rate": [
                        {
                            "factor": "supplier_reliability_node::SDC-A",
                            "correlation": 0.6,
                            "absolute_correlation": 0.6,
                        },
                        {
                            "factor": "factor::demand_scale",
                            "correlation": -0.2,
                            "absolute_correlation": 0.2,
                        },
                    ],
                    "kpi::total_cost": [
                        {
                            "factor": "supplier_capacity_node::SDC-A",
                            "correlation": -0.5,
                            "absolute_correlation": 0.5,
                        }
                    ],
                },
                "top_runs": {
                    "worst_fill_rate": [{"run_id": "run_0002", "kpi::fill_rate": 0.8}],
                },
            }
            (selected / "montecarlo_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            with (selected / "montecarlo_samples.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "run_id",
                        "status",
                        "is_baseline",
                        "kpi::fill_rate",
                        "kpi::ending_backlog",
                        "kpi::total_cost",
                        "kpi::total_supplier_capacity_binding_qty",
                        "supplier_reliability_node::SDC-A",
                        "factor::demand_scale",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "run_id": "run_0000",
                        "status": "ok",
                        "is_baseline": "True",
                        "kpi::fill_rate": "1",
                        "kpi::ending_backlog": "0",
                        "kpi::total_cost": "1000",
                        "kpi::total_supplier_capacity_binding_qty": "0",
                        "supplier_reliability_node::SDC-A": "1.0",
                        "factor::demand_scale": "1.0",
                    }
                )
                writer.writerow(
                    {
                        "run_id": "run_0001",
                        "status": "ok",
                        "is_baseline": "False",
                        "kpi::fill_rate": "0.98",
                        "kpi::ending_backlog": "0",
                        "kpi::total_cost": "1100",
                        "kpi::total_supplier_capacity_binding_qty": "0",
                        "supplier_reliability_node::SDC-A": "1.0",
                        "factor::demand_scale": "0.95",
                    }
                )
                writer.writerow(
                    {
                        "run_id": "run_0002",
                        "status": "ok",
                        "is_baseline": "False",
                        "kpi::fill_rate": "0.80",
                        "kpi::ending_backlog": "2000000",
                        "kpi::total_cost": "1800",
                        "kpi::total_supplier_capacity_binding_qty": "1",
                        "supplier_reliability_node::SDC-A": "0.7",
                        "factor::demand_scale": "1.2",
                    }
                )
                writer.writerow(
                    {
                        "run_id": "run_0003",
                        "status": "ok",
                        "is_baseline": "False",
                        "kpi::fill_rate": "0.90",
                        "kpi::ending_backlog": "1000000",
                        "kpi::total_cost": "1500",
                        "kpi::total_supplier_capacity_binding_qty": "1",
                        "supplier_reliability_node::SDC-A": "0.82",
                        "factor::demand_scale": "1.1",
                    }
                )
            (selected / "montecarlo_trajectories.json").write_text(
                json.dumps(
                    {
                        "run_count": 3,
                        "stochastic_run_count": 2,
                        "max_points": 30,
                        "max_display_runs": 0,
                        "days": [0, 1],
                        "metrics": {
                            "service_rate": {
                                "label": "Service",
                                "series_total_count": 3,
                                "series_display_count": 3,
                                "bands": {"p05": [80, 80], "p95": [100, 100]},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "montecarlo_suite_summary.json").write_text(
                json.dumps(
                    {
                        "selected_profile": "stress_probe",
                        "final_runs": 2,
                        "workers": 2,
                        "final_assessment": {"status": "too_extreme", "variation_score": 0.9},
                    }
                ),
                encoding="utf-8",
            )

            payload = build_uncertainty_diagnostics(selected / "montecarlo_summary.json")

        self.assertTrue(payload["available"])
        self.assertEqual(payload["meta"]["successful_stochastic_runs"], 3)
        self.assertEqual(payload["meta"]["interpretation"], "stress_tres_severe")
        self.assertEqual(payload["trajectory_summary"]["run_count"], 3)
        thresholds = {row["label"]: row["probability"] for row in payload["threshold_probabilities"]}
        self.assertEqual(thresholds["Fill rate < 99%"], 1.0)
        self.assertAlmostEqual(thresholds["Backlog > 1M"], 1 / 3, places=6)
        self.assertEqual(payload["drivers_by_kpi"]["kpi::fill_rate"][0]["subject"], "SDC-A")
        self.assertEqual(payload["supplier_impacts"][0]["supplier_id"], "SDC-A")
        self.assertEqual(payload["extreme_runs"]["worst_fill_rate"][0]["run_id"], "run_0002")
        self.assertTrue(payload["uncertainty_propagation"]["available"])
        self.assertAlmostEqual(payload["uncertainty_propagation"]["input_relative_uncertainty"], 0.20)
        self.assertEqual(payload["uncertainty_propagation"]["business_focus"], "supplier_prediction")
        self.assertIn("kpi::fill_rate", payload["uncertainty_propagation"]["by_kpi"])
        fill_rate_driver = payload["uncertainty_propagation"]["by_kpi"]["kpi::fill_rate"][0]
        self.assertEqual(fill_rate_driver["input_baseline"], 1.0)
        self.assertIn("kpi_delta_for_input_uncertainty", fill_rate_driver)
        self.assertIn("uncertainty_transfer_ratio", fill_rate_driver)
        supplier_relative = payload["uncertainty_propagation"]["top_supplier_relative_factors"]
        self.assertTrue(supplier_relative)
        self.assertTrue(all(row["business_scope"] == "supplier_prediction" for row in supplier_relative))
        self.assertEqual(
            fill_rate_driver["method"],
            "linear_regression_montecarlo",
        )

    def test_missing_summary_returns_unavailable(self) -> None:
        payload = build_uncertainty_diagnostics(Path("missing/montecarlo_summary.json"))

        self.assertFalse(payload["available"])
        self.assertEqual(payload["error"], "summary_json_missing_or_invalid")


if __name__ == "__main__":
    unittest.main()
