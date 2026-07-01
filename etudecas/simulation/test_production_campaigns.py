from __future__ import annotations

import unittest

from etudecas.simulation.lot_trace.campaigns import build_production_campaign_rows


class ProductionCampaignRowsTest(unittest.TestCase):
    def test_delayed_fixed_lot_counts_blocked_volume_once(self) -> None:
        plan_rows = [
            self._plan_row(3, "CMP-1", "delay_input_shortage", "input_shortage", 0.0, 107800.0, "item:RM", 6),
            self._plan_row(4, "CMP-1", "delay_input_shortage", "input_shortage", 0.0, 107800.0, "item:RM", 6),
            self._plan_row(5, "CMP-1", "delay_input_shortage", "input_shortage", 0.0, 107800.0, "item:RM", 6),
            self._plan_row(6, "CMP-1", "run_campaign_complete", "none", 107800.0, 0.0, "", ""),
        ]
        lot_rows = [
            {
                "day": 6,
                "event_type": "production_output",
                "lot_id": "LOT-PF",
                "qty": 107800.0,
                "production_campaign_id": "CMP-1",
            }
        ]

        rows = build_production_campaign_rows(plan_rows, lot_rows)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["status"], "completed_after_delay")
        self.assertEqual(row["delay_day_count"], 3)
        self.assertEqual(row["completed_lot_ids"], "LOT-PF")
        self.assertAlmostEqual(row["blocked_lot_qty"], 107800.0)
        self.assertAlmostEqual(row["repeated_daily_shortfall_qty"], 323400.0)
        self.assertEqual(row["binding_input_item_ids"], "item:RM")

    def test_blocked_order_without_campaign_id_gets_business_id(self) -> None:
        rows = build_production_campaign_rows(
            [
                self._plan_row(
                    12,
                    "",
                    "delay_weekly_lot_limit",
                    "weekly_lot_limit",
                    0.0,
                    0.0,
                    "",
                    "",
                    output_item_id="item:PFI",
                    campaign_requested_qty=6400000.0,
                    requested_lot_starts=1,
                )
            ],
            [],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_type"], "order_request")
        self.assertEqual(rows[0]["status"], "not_started_blocked")
        self.assertAlmostEqual(rows[0]["planned_qty"], 6400000.0)
        self.assertAlmostEqual(rows[0]["requested_qty"], 6400000.0)
        self.assertAlmostEqual(rows[0]["blocked_lot_qty"], 6400000.0)
        self.assertAlmostEqual(rows[0]["requested_lot_starts"], 1.0)
        self.assertTrue(str(rows[0]["campaign_id"]).startswith("ORDER-M-1-item-PFI-D12-"))

    def _plan_row(
        self,
        day: int,
        campaign_id: str,
        event_type: str,
        reason: str,
        actual_qty: float,
        shortfall: float,
        binding_item: str,
        next_receipt_day: int | str,
        *,
        output_item_id: str = "item:PF",
        campaign_requested_qty: float | None = None,
        requested_lot_starts: int = 0,
    ) -> dict[str, object]:
        planned = 107800.0
        requested_qty = planned if campaign_requested_qty is None else campaign_requested_qty
        return {
            "day": day,
            "campaign_id": campaign_id,
            "node_id": "M-1",
            "output_item_id": output_item_id,
            "event_type": event_type,
            "reason": reason,
            "desired_qty": planned,
            "planned_qty_after_lot_rule": planned,
            "actual_qty": actual_qty,
            "shortfall_vs_desired_qty": shortfall,
            "shortfall_vs_lot_plan_qty": shortfall,
            "binding_input_item_id": binding_item,
            "planned_qty_before": planned,
            "planned_qty_after": max(0.0, planned - actual_qty),
            "requested_lot_starts": requested_lot_starts,
            "actual_lot_starts": 1 if actual_qty > 0 else 0,
            "campaign_requested_qty": requested_qty,
            "campaign_started_qty": actual_qty,
            "campaign_remaining_start_qty": planned,
            "campaign_remaining_end_qty": max(0.0, planned - actual_qty),
            "next_expected_receipt_day": next_receipt_day,
            "notes": "",
        }


if __name__ == "__main__":
    unittest.main()
