from __future__ import annotations

import unittest

from etudecas.visualization.maps.supplier_risk_panels import (
    build_simulated_supplier_risk_metrics,
    render_supplier_risk_catalog_html,
    supplier_risk_family_for_event,
)


class SupplierRiskPanelsTest(unittest.TestCase):
    def test_build_simulated_supplier_risk_metrics_counts_applied_state_event(self) -> None:
        metrics = build_simulated_supplier_risk_metrics(
            configured_by_node={
                "S-1": [
                    {
                        "event_id": "state_capacity_S-1",
                        "risk_type": "capacity",
                        "source": "state_dependent_supplier_risk",
                        "start_day": "3",
                        "end_day": "5",
                    }
                ]
            },
            applied_by_node={
                "S-1": [
                    {
                        "day": "4",
                        "event_ids": "state_capacity_S-1",
                        "capacity_multiplier": "0.50",
                    }
                ]
            },
        )

        node = metrics["nodes"]["S-1"]
        self.assertEqual(node["status"], "applied")
        self.assertEqual(node["driver_family"], "capacity")
        self.assertEqual(node["applied_source_counts"], {"state": 1})
        self.assertAlmostEqual(node["score"], 0.5)
        self.assertEqual(metrics["global"]["applied_event_count"], 1)

    def test_render_supplier_risk_catalog_html_marks_applied_and_configured_events(self) -> None:
        html = render_supplier_risk_catalog_html(
            "S-1",
            applied_rows=[
                {
                    "day": "2",
                    "event_ids": "stock_drop",
                    "stock_multiplier": "0.60",
                }
            ],
            configured_events=[
                {
                    "event_id": "stock_drop",
                    "risk_type": "stock",
                    "start_day": "1",
                    "end_day": "3",
                    "multiplier": "0.60",
                },
                {
                    "event_id": "cost_watch",
                    "risk_type": "purchase_cost",
                    "start_day": "4",
                    "end_day": "5",
                    "multiplier": "1.25",
                },
            ],
            economic_policy={
                "external_procurement_enabled": True,
                "external_procurement_lead_days": 7,
                "external_procurement_cost_multiplier": 1.2,
            },
        )

        self.assertIn("S-1 - risques simules fournisseur", html)
        self.assertIn("Stock fournisseur", html)
        self.assertIn("APPLIQUE", html)
        self.assertIn("Cout achat", html)
        self.assertIn("CONFIGURE", html)

    def test_supplier_risk_family_for_event_reads_state_event_id(self) -> None:
        family = supplier_risk_family_for_event({"event_id": "state_lead_S-1_001"})

        self.assertEqual(family, "lead")


if __name__ == "__main__":
    unittest.main()
