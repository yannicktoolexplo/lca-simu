import unittest

from etudecas.visualization.maps.risk_payload import build_risk_payload_manifest
from etudecas.visualization.maps.sensitivity_payload import build_sensitivity_payload_manifest
from etudecas.visualization.maps.simulation_payload import build_simulation_payload_manifest


class DomainPayloadLayersTest(unittest.TestCase):
    def test_simulation_manifest_counts_lot_and_panel_sections(self) -> None:
        manifest = build_simulation_payload_manifest(
            {
                "factory_hover_series": {"M-1": {}},
                "supplier_hover_images": {"S-1": {}},
                "lot_trace": {"events": [{}, {}], "genealogy": [{}], "lot_options": [{}, {}, {}]},
            }
        )

        self.assertEqual(manifest["domain"], "simulation")
        self.assertIn("factory_hover_series", manifest["legacy_keys"])
        self.assertEqual(manifest["counts"]["factory_series"], 1)
        self.assertEqual(manifest["counts"]["lot_events"], 2)
        self.assertEqual(manifest["counts"]["lot_options"], 3)

    def test_risk_manifest_counts_scenarios_and_events(self) -> None:
        manifest = build_risk_payload_manifest(
            {
                "scenario_comparison": {"scenarios": [{}, {}], "figures": {"backlog": {}}},
                "simulated_risk_global_diagnostic": {"events": [{}, {}, {}]},
                "supplier_risk_metrics": {"S-1": {}},
            }
        )

        self.assertEqual(manifest["domain"], "risk")
        self.assertEqual(manifest["counts"]["scenario_count"], 2)
        self.assertEqual(manifest["counts"]["scenario_figures"], 1)
        self.assertEqual(manifest["counts"]["risk_events"], 3)

    def test_sensitivity_manifest_counts_domain_panels(self) -> None:
        manifest = build_sensitivity_payload_manifest(
            {
                "factory_sensitivity_hover_images": {"M-1": {}},
                "supplier_sensitivity_hover_images": {"S-1": {}, "S-2": {}},
                "supplier_parameter_sensitivity_nodes": {"S-1": {}},
            }
        )

        self.assertEqual(manifest["domain"], "sensitivity")
        self.assertEqual(manifest["counts"]["factory_panels"], 1)
        self.assertEqual(manifest["counts"]["supplier_panels"], 2)
        self.assertEqual(manifest["counts"]["supplier_parameter_nodes"], 1)


if __name__ == "__main__":
    unittest.main()
