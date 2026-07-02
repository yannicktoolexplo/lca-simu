from __future__ import annotations

import unittest

from etudecas.simulation.analysis.factory_nervousness import build_factory_nervousness_rows


class FactoryNervousnessTest(unittest.TestCase):
    def test_lumpy_fixed_lot_is_high_even_with_few_delays(self) -> None:
        constraint_rows = [
            {
                "day": 0,
                "node_id": "M-1",
                "output_item_id": "item:PF",
                "desired_qty": 5000.0,
                "planned_qty_after_lot_rule": 100000.0,
                "actual_qty": 100000.0,
                "requested_lot_starts": 1,
                "actual_lot_starts": 1,
            },
            {
                "day": 10,
                "node_id": "M-1",
                "output_item_id": "item:PF",
                "desired_qty": 5000.0,
                "planned_qty_after_lot_rule": 100000.0,
                "actual_qty": 0.0,
                "requested_lot_starts": 1,
                "actual_lot_starts": 0,
            },
        ]
        campaign_rows = [
            {"node_id": "M-1", "output_item_id": "item:PF", "status": "completed_without_delay", "delay_day_count": 0},
            {"node_id": "M-1", "output_item_id": "item:PF", "status": "not_started_blocked", "delay_day_count": 1},
        ]

        rows = build_factory_nervousness_rows(constraint_rows, campaign_rows, horizon_days=30)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nervousness_level"], "high")
        self.assertGreater(rows[0]["lot_amplification_vs_avg_desired"], 5.0)
        self.assertEqual(rows[0]["blocked_campaigns"], 1)


if __name__ == "__main__":
    unittest.main()
