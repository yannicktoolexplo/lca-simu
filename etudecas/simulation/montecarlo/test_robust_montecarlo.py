import csv
import random
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.montecarlo.run_robust_montecarlo import assess_profile, choose_profile
from etudecas.simulation.montecarlo.run_montecarlo_analysis import (
    PORTFOLIO_PROBE_FAMILIES,
    detect_portfolio_priority_targets,
    portfolio_family_for_run,
    portfolio_focus_sets,
)


def write_samples(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class RobustMonteCarloTests(unittest.TestCase):
    def test_portfolio_probe_cycles_business_families(self) -> None:
        observed = [portfolio_family_for_run(idx) for idx in range(len(PORTFOLIO_PROBE_FAMILIES) * 2)]

        self.assertEqual(observed[: len(PORTFOLIO_PROBE_FAMILIES)], PORTFOLIO_PROBE_FAMILIES)
        self.assertEqual(observed[len(PORTFOLIO_PROBE_FAMILIES) :], PORTFOLIO_PROBE_FAMILIES)

    def test_supplier_portfolio_family_selects_local_focus(self) -> None:
        focus_suppliers, focus_items, secondary_strength = portfolio_focus_sets(
            family="supplier_delay",
            rng=random.Random(7),
            demand_items=["item:1", "item:2"],
            supplier_nodes=["S1", "S2", "S3", "S4", "S5"],
            supplier_edge_sources=["S1", "S2", "S3", "S4", "S5"],
            critical_suppliers=["S3"],
            critical_demand_items=["item:1"],
        )

        self.assertGreaterEqual(len(focus_suppliers), 1)
        self.assertLessEqual(len(focus_suppliers), 4)
        self.assertEqual(focus_items, set())
        self.assertLess(secondary_strength, 0.5)

    def test_portfolio_priority_targets_follow_demand_bom_suppliers(self) -> None:
        data = {
            "nodes": [
                {
                    "id": "M1",
                    "type": "factory",
                    "processes": [
                        {
                            "outputs": [{"item_id": "item:PF"}],
                            "inputs": [{"item_id": "item:RM"}],
                        }
                    ],
                },
                {"id": "S1", "type": "supplier_dc"},
            ],
            "edges": [{"from": "S1", "to": "M1", "items": ["item:RM"]}],
            "scenarios": [{"id": "scn:BASE", "demand": [{"item_id": "item:PF"}]}],
        }

        targets = detect_portfolio_priority_targets(data, "scn:BASE")

        self.assertEqual(targets["critical_demand_items"], ["item:PF"])
        self.assertIn("item:RM", targets["critical_supply_items"])
        self.assertEqual(targets["critical_suppliers"], ["S1"])
        self.assertEqual(targets["high_priority_suppliers"], ["S1"])
        self.assertEqual(targets["single_source_supply_items"], ["item:RM"])

    def test_assess_profile_detects_weak_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.csv"
            rows = [
                {
                    "run_id": "run_0000",
                    "is_baseline": True,
                    "status": "ok",
                    "kpi::fill_rate": 1.0,
                    "kpi::ending_backlog": 0,
                    "kpi::total_cost": 1000,
                    "kpi::total_demand": 10000,
                    "kpi::total_supplier_capacity_binding_qty": 0,
                },
                {
                    "run_id": "run_0001",
                    "is_baseline": False,
                    "status": "ok",
                    "kpi::fill_rate": 0.9995,
                    "kpi::ending_backlog": 0,
                    "kpi::total_cost": 1005,
                    "kpi::total_demand": 10000,
                    "kpi::total_supplier_capacity_binding_qty": 0,
                },
                {
                    "run_id": "run_0002",
                    "is_baseline": False,
                    "status": "ok",
                    "kpi::fill_rate": 1.0,
                    "kpi::ending_backlog": 0,
                    "kpi::total_cost": 1008,
                    "kpi::total_demand": 10000,
                    "kpi::total_supplier_capacity_binding_qty": 0,
                },
            ]
            write_samples(path, rows)
            self.assertEqual(assess_profile(path, "workshop")["status"], "too_weak")

    def test_choose_profile_prefers_useful_near_target(self) -> None:
        selected = choose_profile(
            [
                {"profile": "workshop", "status": "too_weak", "variation_score": 0.02, "target_distance": 0.36},
                {"profile": "risk_probe", "status": "useful", "variation_score": 0.31, "target_distance": 0.07},
                {"profile": "stress_probe", "status": "useful", "variation_score": 0.62, "target_distance": 0.24},
            ],
            fallback="stress_probe",
        )
        self.assertEqual(selected, "risk_probe")

    def test_choose_profile_avoids_extreme_when_only_weak_and_extreme(self) -> None:
        selected = choose_profile(
            [
                {"profile": "workshop", "status": "too_weak", "variation_score": 0.03, "target_distance": 0.35},
                {"profile": "breakpoint_probe", "status": "too_extreme", "variation_score": 0.95, "target_distance": 0.57},
            ],
            fallback="stress_probe",
        )
        self.assertEqual(selected, "workshop")


if __name__ == "__main__":
    unittest.main()
