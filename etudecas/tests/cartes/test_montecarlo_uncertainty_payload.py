import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps.build_supplychain_worldmap import build_montecarlo_uncertainty_payload


class MonteCarloUncertaintyPayloadTest(unittest.TestCase):
    def test_builds_business_diagnostics_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected"
            selected.mkdir()
            summary = {
                "scenario_id": "scn:BASE",
                "seed": 42,
                "days_override": 30,
                "uncertainty_profile": "stress_probe",
                "runs_requested_excluding_baseline": 2,
                "successful_runs": 4,
                "successful_stochastic_runs": 3,
                "failed_runs": 0,
                "decision_metrics": {
                    "fill_rate_below_100pct": 0.5,
                    "fill_rate_below_99pct": 0.5,
                    "backlog_positive": 0.5,
                    "total_cost_above_baseline": 0.5,
                },
                "metric_statistics": {
                    "kpi::fill_rate": {"baseline": 1.0, "p05": 0.8, "p50": 0.9, "p95": 1.0, "max": 1.0},
                    "kpi::ending_backlog": {"baseline": 0, "p05": 0, "p50": 10, "p95": 100, "max": 120},
                    "kpi::total_cost": {"baseline": 1000, "p05": 1000, "p50": 1200, "p95": 1600, "max": 1700},
                    "kpi::total_supplier_capacity_binding_qty": {
                        "baseline": 0,
                        "p05": 0,
                        "p50": 0,
                        "p95": 1,
                        "max": 1,
                    },
                },
                "driver_rankings": {
                    "kpi::fill_rate": [
                        {
                            "factor": "supplier_reliability_node::SDC-A",
                            "correlation": 0.6,
                            "absolute_correlation": 0.6,
                        },
                    ],
                    "kpi::ending_backlog": [
                        {
                            "factor": "supplier_lead_node::SDC-B",
                            "correlation": 0.4,
                            "absolute_correlation": 0.4,
                        },
                    ],
                },
                "factor_kpi_correlations_pearson": {
                    "supplier_reliability_node::SDC-A": {
                        "kpi::fill_rate": 0.6,
                        "kpi::ending_backlog": -0.4,
                        "kpi::total_cost": -0.1,
                    },
                    "capacity_node::M-1": {
                        "kpi::fill_rate": 0.3,
                        "kpi::ending_backlog": -0.3,
                        "kpi::total_cost": 0.2,
                    },
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
                        "capacity_node::M-1",
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
                        "capacity_node::M-1": "1.0",
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
                        "capacity_node::M-1": "0.9",
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
                        "capacity_node::M-1": "0.7",
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
                        "capacity_node::M-1": "0.78",
                    }
                )
            (selected / "montecarlo_trajectories.json").write_text(
                json.dumps(
                    {
                        "days": [0, 1],
                        "run_count": 3,
                        "stochastic_run_count": 2,
                        "metrics": {
                            "service_rate": {
                                "label": "Service client cumule",
                                "y_label": "%",
                                "reference_value": 100,
                                "bands": {"p05": [80, 80], "p50": [90, 90], "p95": [100, 100]},
                                "series": [
                                    {"run_id": "run_0000", "label": "Nominal", "is_baseline": True, "values": [100, 100]},
                                    {"run_id": "run_0001", "label": "run_0001", "values": [98, 98]},
                                    {"run_id": "run_0002", "label": "run_0002", "values": [80, 80]},
                                ],
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

            payload = build_montecarlo_uncertainty_payload(selected / "montecarlo_summary.json")

        self.assertTrue(payload["available"])
        self.assertEqual(payload["diagnostics"]["meta"]["interpretation"], "stress_tres_severe")
        self.assertIn("Probabilites de seuils metier", payload["html"])
        self.assertIn("Propagation d'incertitude entree -> KPI", payload["html"])
        self.assertIn("Amplitude KPI estimee", payload["html"])
        self.assertIn("Sens si input +20%", payload["html"])
        self.assertIn("Qualite du signal", payload["html"])
        self.assertIn("des ecarts expliques", payload["html"])
        self.assertIn("Propagation", payload["html"])
        self.assertIn("20% entree -&gt;", payload["html"])
        self.assertIn("Prediction fournisseur - propagation relative lisible", payload["html"])
        self.assertIn("Cellule supply - priorites par agent metier", payload["html"])
        self.assertIn("Disponibilite produit", payload["html"])
        self.assertIn("Agent disponibilite produit", payload["html"])
        self.assertIn("Reports de production", payload["html"])
        self.assertIn("Agent planning production", payload["html"])
        self.assertIn("Top fournisseurs a traiter", payload["html"])
        self.assertIn("Details KPI, propagation et modele Monte Carlo", payload["html"])
        self.assertIn("Bandes d'incertitude fournisseur", payload["html"])
        self.assertIn("plage KPI finale relative au nominal", payload["html"])
        self.assertIn("si l'input fournisseur varie de -20% a +20%", payload["html"])
        self.assertIn("Impacts absolus sur KPI a nominal zero", payload["html"])
        self.assertIn("supplier-first", payload["html"])
        self.assertTrue(payload["diagnostics"]["uncertainty_propagation"]["available"])
        self.assertIn("Familles de parametres les plus explicatives", payload["html"])
        self.assertIn("Fournisseurs et noeuds a prioriser", payload["html"])
        self.assertIn("SDC-A", payload["nodes"])
        self.assertIn("M-1", payload["nodes"])


if __name__ == "__main__":
    unittest.main()
