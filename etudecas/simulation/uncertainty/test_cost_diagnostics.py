import csv
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.uncertainty.cost_diagnostics import build_cost_diagnostics


class CostDiagnosticsTests(unittest.TestCase):
    def test_cost_identity_and_separate_exceptional_supply(self) -> None:
        columns = [
            "run_id", "status", "is_baseline", "factor::holding_cost_scale",
            "kpi::total_purchase_cost", "kpi::total_transport_cost", "kpi::total_holding_cost",
            "kpi::total_warehouse_operating_cost", "kpi::total_inventory_risk_cost",
            "kpi::total_production_cost", "kpi::total_external_procurement_cost",
            "kpi::operational_risk_cost", "kpi::total_cost",
        ]
        rows = []
        for index, scale in enumerate((1.0, 0.8, 1.2, 1.4)):
            base = 70.0 * scale
            production = base * 3.0 / 7.0
            rows.append({
                "run_id": f"run_{index}", "status": "ok", "is_baseline": index == 0,
                "factor::holding_cost_scale": scale,
                "kpi::total_purchase_cost": base * 0.1,
                "kpi::total_transport_cost": base * 0.1,
                "kpi::total_holding_cost": base * 0.3,
                "kpi::total_warehouse_operating_cost": base * 0.3,
                "kpi::total_inventory_risk_cost": base * 0.2,
                "kpi::total_production_cost": production,
                "kpi::total_external_procurement_cost": 50.0,
                "kpi::operational_risk_cost": 60.0,
                "kpi::total_cost": base + production,
            })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            payload = build_cost_diagnostics(path)

        self.assertTrue(payload["accounting_identity"]["valid_within_tolerance"])
        self.assertTrue(payload["production_cost_coupling"]["fixed_share_detected"])
        self.assertAlmostEqual(payload["production_cost_coupling"]["median_share_of_total"], 0.3)
        self.assertAlmostEqual(payload["production_cost_coupling"]["mechanical_amplification_factor"], 10.0 / 7.0)
        self.assertFalse(payload["exceptional_supply_cost"]["included_in_total_cost"])
        self.assertAlmostEqual(payload["cost_without_production"]["median"], 84.0)
        self.assertAlmostEqual(payload["cost_without_production"]["baseline"], 70.0)
        self.assertAlmostEqual(payload["economic_exposure_including_exceptional_supply"]["median"], 170.0)
        self.assertAlmostEqual(payload["economic_exposure_including_exceptional_supply"]["baseline"], 150.0)
        self.assertEqual(payload["sample_count"], 3)


if __name__ == "__main__":
    unittest.main()
