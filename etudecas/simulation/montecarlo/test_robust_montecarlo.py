import csv
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.montecarlo.run_robust_montecarlo import assess_profile, choose_profile


def write_samples(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class RobustMonteCarloTests(unittest.TestCase):
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
