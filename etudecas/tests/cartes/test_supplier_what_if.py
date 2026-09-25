import csv
import tempfile
from pathlib import Path
import unittest

from etudecas.visualization.maps.inject_supplier_what_if import (
    build_supplier_what_if_payload,
    inject_supplier_what_if,
)


class SupplierWhatIfTest(unittest.TestCase):
    def test_builds_payload_and_injects_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics = Path(tmp) / "metrics.csv"
            fieldnames = [
                "case_id",
                "status",
                "parameter_group",
                "parameter_key",
                "parameter_label",
                "level",
                "kpi::fill_rate",
                "kpi::ending_backlog",
                "kpi::production_replanning_count",
                "kpi::raw_material_stockout_days",
                "kpi::total_cost",
                "kpi::total_produced",
                "kpi::product_availability",
                "kpi::total_external_procured_arrived_qty",
            ]
            with metrics.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "case_id": "baseline",
                        "status": "ok",
                        "parameter_group": "baseline",
                        "parameter_key": "baseline",
                        "level": "1.0",
                        "kpi::fill_rate": "1.0",
                        "kpi::total_cost": "100.0",
                    }
                )
                writer.writerow(
                    {
                        "case_id": "stock_supplier_0_5",
                        "status": "ok",
                        "parameter_group": "supplier_stock_node",
                        "parameter_key": "supplier_stock_node::SDC-1",
                        "parameter_label": "Stock fournisseur SDC-1",
                        "level": "0.5",
                        "kpi::fill_rate": "0.95",
                        "kpi::total_cost": "120.0",
                    }
                )

            payload = build_supplier_what_if_payload(
                metrics,
                simulation_input="graph.json",
                scenario_id="scn:BASE",
                days=90,
                output_profile="diagnostic",
            )

            self.assertEqual(payload["case_count"], 1)
            self.assertEqual(payload["suppliers"], ["SDC-1"])
            self.assertEqual(payload["baseline"]["fill_rate"], 1.0)
            self.assertEqual(payload["cases"][0]["supplier_id"], "SDC-1")
            self.assertEqual(payload["simulation_request_defaults"]["input_path"], "graph.json")
            self.assertEqual(payload["simulation_request_defaults"]["days"], 90)
            self.assertEqual(payload["cases"][0]["request_overrides"], {"supplier_node_scale": {"SDC-1": 0.5}})

            html = inject_supplier_what_if("<html><body>map</body></html>", payload)
            self.assertIn("What-if fournisseurs", html)
            self.assertIn("SUPPLIER_WHATIF", html)
            self.assertIn("Contrat simulation", html)
            self.assertIn("request_overrides", html)
            self.assertIn("</body>", html)


if __name__ == "__main__":
    unittest.main()
