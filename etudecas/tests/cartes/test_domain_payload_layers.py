import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from etudecas.visualization.maps.risk_payload import build_risk_payload_manifest
from etudecas.visualization.maps.scenario_comparison_payload import build_sensitivity_payload_manifest
from etudecas.visualization.maps.simulation_payload import build_simulation_payload_manifest


class DomainPayloadLayersTest(unittest.TestCase):
    def test_material_delivery_default_refresh_keeps_arguments(self) -> None:
        from etudecas.visualization.maps import material_delivery

        argv = ["--data", "data", "--graph", "graph.json", "--output", "out.html",
                "--evidence", "proof", "--source", "source.html", "--metadata", "meta.json"]
        with patch.object(material_delivery, "refresh", return_value={"output": "out.html", "coverage": {}}) as refresh, \
                patch.object(material_delivery, "build_scenario_explorer") as scenario, \
                contextlib.redirect_stdout(io.StringIO()):
            material_delivery.main(argv)
        refresh.assert_called_once_with(Path("source.html"), Path("data"), Path("graph.json"),
                                        Path("out.html"), Path("proof"), Path("meta.json"))
        scenario.assert_not_called()

    def test_material_delivery_scenario_mode_uses_its_own_graph_and_data(self) -> None:
        from etudecas.visualization.maps import material_delivery

        argv = ["--mode", "scenario", "--data", "risk/data", "--graph", "risk/graph.json",
                "--output", "risk.html", "--evidence", "proof"]
        with patch.object(material_delivery, "refresh") as refresh, \
                patch.object(material_delivery, "build_scenario_explorer", return_value={"scenario": "risk"}) as scenario, \
                contextlib.redirect_stdout(io.StringIO()):
            material_delivery.main(argv)
        scenario.assert_called_once_with(Path("risk/data"), Path("risk/graph.json"), Path("risk.html"), Path("proof"))
        refresh.assert_not_called()

    def test_material_delivery_rejects_ambiguous_or_incomplete_modes(self) -> None:
        from etudecas.visualization.maps import material_delivery

        common = ["--data", "data", "--graph", "graph.json", "--output", "out.html", "--evidence", "proof"]
        for suffix in ([], ["--mode", "scenario", "--source", "old.html"],
                       ["--mode", "scenario", "--metadata", "meta.json"]):
            with self.subTest(suffix=suffix), patch.object(material_delivery, "refresh") as refresh, \
                    patch.object(material_delivery, "build_scenario_explorer") as scenario, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                material_delivery.main(common + suffix)
            self.assertEqual(raised.exception.code, 2)
            refresh.assert_not_called()
            scenario.assert_not_called()

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
