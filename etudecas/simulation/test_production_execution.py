from __future__ import annotations

import unittest

from etudecas.simulation.lot_trace.execution import (
    ProductionBatchWip,
    make_batch_id,
    physical_batch_target_qty,
    production_week_index,
)
from etudecas.simulation.engine.run_first_simulation import (
    campaign_lot_count,
    launch_campaign_qty,
    limit_campaign_qty_by_weekly_lots,
)


class ProductionBatchExecutionTest(unittest.TestCase):
    def test_partial_daily_execution_stays_wip_until_full_batch(self) -> None:
        batch = ProductionBatchWip(
            campaign_id="CMP-1",
            batch_id="CMP-1-B001",
            node_id="M-1810",
            item_id="268091",
            campaign_started_day=-2,
            batch_started_day=-2,
            target_qty=14_400.0,
        )

        accepted_pre_day_zero = batch.add_execution(
            5_000.0,
            [{"lot_id": "RM-1", "qty": 1_000.0}],
        )
        accepted_day_zero = batch.add_execution(
            5_000.0,
            [{"lot_id": "RM-2", "qty": 1_000.0}],
        )

        self.assertEqual(accepted_pre_day_zero, 5_000.0)
        self.assertEqual(accepted_day_zero, 5_000.0)
        self.assertFalse(batch.is_complete)
        self.assertEqual(batch.executed_qty, 10_000.0)
        self.assertEqual(batch.remaining_qty, 4_400.0)
        self.assertEqual([row["lot_id"] for row in batch.parent_allocations], ["RM-1", "RM-2"])

        accepted_release_day = batch.add_execution(
            10_000.0,
            [{"lot_id": "RM-3", "qty": 880.0}],
        )

        self.assertEqual(accepted_release_day, 4_400.0)
        self.assertTrue(batch.is_complete)
        self.assertEqual(batch.executed_qty, 14_400.0)
        self.assertEqual(batch.remaining_qty, 0.0)

    def test_fixed_campaign_is_split_into_physical_batches(self) -> None:
        policy = {"fixed_lot_qty": 100.0}

        self.assertEqual(physical_batch_target_qty(300.0, policy), 100.0)
        self.assertEqual(physical_batch_target_qty(75.0, policy), 75.0)
        self.assertEqual(make_batch_id("CMP-9", 2), "CMP-9-B002")

    def test_min_max_campaign_is_one_release_batch(self) -> None:
        policy = {
            "fixed_lot_qty": 0.0,
            "min_lot_qty": 14_400.0,
            "max_lot_qty": 142_485.0,
            "lot_multiple_qty": 14_400.0,
        }

        self.assertEqual(physical_batch_target_qty(129_600.0, policy), 129_600.0)

    def test_zero_target_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductionBatchWip(
                campaign_id="CMP-1",
                batch_id="CMP-1-B001",
                node_id="M-1",
                item_id="PF",
                campaign_started_day=0,
                batch_started_day=0,
                target_qty=0.0,
            )

    def test_fixed_policy_rounds_to_complete_batches(self) -> None:
        policy = {
            "enabled": True,
            "fixed_lot_qty": 100.0,
            "min_lot_qty": 0.0,
            "max_lot_qty": 0.0,
            "lot_multiple_qty": 0.0,
        }

        launched = launch_campaign_qty(201.0, policy)

        self.assertEqual(launched, 300.0)
        self.assertEqual(campaign_lot_count(launched, policy), 3)
        self.assertEqual(limit_campaign_qty_by_weekly_lots(launched, policy, 2), 200.0)
        self.assertEqual(limit_campaign_qty_by_weekly_lots(launched, policy, 0), 0.0)

    def test_min_max_multiple_policy_returns_a_feasible_batch(self) -> None:
        policy = {
            "enabled": True,
            "fixed_lot_qty": 0.0,
            "min_lot_qty": 14_400.0,
            "max_lot_qty": 142_485.0,
            "lot_multiple_qty": 14_400.0,
        }

        self.assertEqual(launch_campaign_qty(10_000.0, policy), 14_400.0)
        self.assertEqual(launch_campaign_qty(130_000.0, policy), 129_600.0)
        self.assertEqual(launch_campaign_qty(500_000.0, policy), 129_600.0)

    def test_incompatible_min_max_multiple_policy_is_rejected(self) -> None:
        policy = {
            "enabled": True,
            "fixed_lot_qty": 0.0,
            "min_lot_qty": 10.0,
            "max_lot_qty": 10.0,
            "lot_multiple_qty": 6.0,
        }

        with self.assertRaisesRegex(ValueError, "no positive lot_multiple_qty"):
            launch_campaign_qty(8.0, policy)

    def test_weekly_limit_calendar_is_anchored_at_day_zero(self) -> None:
        self.assertEqual(production_week_index(-8), -2)
        self.assertEqual(production_week_index(-1), -1)
        self.assertEqual(production_week_index(0), 0)
        self.assertEqual(production_week_index(6), 0)
        self.assertEqual(production_week_index(7), 1)


if __name__ == "__main__":
    unittest.main()
