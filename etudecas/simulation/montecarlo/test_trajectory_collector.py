import csv
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.montecarlo.trajectory_collector import (
    build_montecarlo_trajectories_payload,
    extract_run_trajectories,
)


class MonteCarloTrajectoryCollectorTest(unittest.TestCase):
    def test_extract_run_trajectories_from_standard_data_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            with (data / "first_simulation_daily.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "day",
                        "demand",
                        "served",
                        "backlog_end",
                        "produced_qty",
                        "total_supply_cost_day",
                        "supplier_capacity_binding_qty",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "day": 0,
                        "demand": 100,
                        "served": 90,
                        "backlog_end": 10,
                        "produced_qty": 50,
                        "total_supply_cost_day": 12,
                        "supplier_capacity_binding_qty": 3,
                    }
                )
                writer.writerow(
                    {
                        "day": 1,
                        "demand": 100,
                        "served": 100,
                        "backlog_end": 10,
                        "produced_qty": 80,
                        "total_supply_cost_day": 14,
                        "supplier_capacity_binding_qty": 0,
                    }
                )
            with (data / "production_campaigns.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "campaign_id",
                        "status",
                        "first_delay_day",
                        "completed_day",
                        "blocked_lot_qty",
                        "delay_reasons",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "campaign_id": "CMP-1",
                        "status": "completed_after_delay",
                        "first_delay_day": 0,
                        "completed_day": 1,
                        "blocked_lot_qty": 25,
                        "delay_reasons": "input_shortage",
                    }
                )

            series = extract_run_trajectories(root)

        self.assertEqual(series["service_rate"], [(0, 90.0), (1, 95.0)])
        self.assertEqual(series["backlog"], [(0, 10.0), (1, 10.0)])
        self.assertEqual(series["total_supply_cost_cum"], [(0, 12.0), (1, 26.0)])
        self.assertEqual(series["production_reports"], [(0, 25.0), (1, 0.0)])
        self.assertEqual(series["production_delay_input_qty"], [(0, 25.0), (1, 0.0)])
        self.assertEqual(series["production_delay_active_orders"], [(0, 1.0), (1, 0.0)])
        self.assertEqual(series["production_delay_active_qty"], [(0, 25.0), (1, 0.0)])

    def test_build_payload_keeps_common_days_and_nominal_flag(self) -> None:
        payload = build_montecarlo_trajectories_payload(
            [
                {
                    "run_id": "run_0000",
                    "is_baseline": True,
                    "series": {"service_rate": [(0, 100), (1, 99)]},
                },
                {
                    "run_id": "run_0001",
                    "is_baseline": False,
                    "series": {"service_rate": [(0, 98), (1, 97)]},
                },
            ],
            scenario_id="scn",
            seed=42,
            profile="workshop",
            max_display_runs=1,
        )

        self.assertEqual(payload["days"], [0, 1])
        self.assertEqual(payload["metrics"]["service_rate"]["series"][0]["label"], "Nominal")
        self.assertTrue(payload["metrics"]["service_rate"]["series"][0]["is_baseline"])
        self.assertEqual(len(payload["metrics"]["service_rate"]["series"]), 1)
        self.assertEqual(payload["metrics"]["service_rate"]["series_total_count"], 2)
        self.assertEqual(payload["metrics"]["service_rate"]["bands"]["p50"], [99.0, 98.0])
        self.assertEqual(payload["stochastic_run_count"], 1)


if __name__ == "__main__":
    unittest.main()
