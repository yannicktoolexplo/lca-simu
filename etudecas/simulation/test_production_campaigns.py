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
        self.assertEqual(row["completed_day"], 6)
        self.assertEqual(row["last_release_day"], 6)
        self.assertEqual(row["completion_basis"], "last_released_physical_lot")
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

    def test_campaign_crossing_day_zero_completes_on_real_release_day(self) -> None:
        carry_in = self._plan_row(
            0,
            "CMP-PRE-J0",
            "carry_in_wip",
            "none",
            4_400.0,
            0.0,
            "",
            "",
        )
        carry_in.update(
            {
                "semantics_version": "campaign-batch-wip-release-v1",
                "campaign_started_day": -2,
                "batch_id": "CMP-PRE-J0-B001",
                "batch_target_qty": 14_400.0,
                "wip_start_qty": 5_000.0,
                "wip_end_qty": 9_400.0,
                "released_qty": 0.0,
                "campaign_remaining_end_qty": 5_000.0,
            }
        )
        complete = self._plan_row(
            1,
            "CMP-PRE-J0",
            "run_campaign_complete",
            "none",
            5_000.0,
            0.0,
            "",
            "",
        )
        complete.update(
            {
                "semantics_version": "campaign-batch-wip-release-v1",
                "campaign_started_day": -2,
                "batch_id": "CMP-PRE-J0-B001",
                "batch_target_qty": 14_400.0,
                "wip_start_qty": 9_400.0,
                "wip_end_qty": 0.0,
                "released_qty": 14_400.0,
                "campaign_remaining_end_qty": 0.0,
            }
        )
        lot_rows = [
            {
                "day": 1,
                "event_type": "production_output",
                "lot_id": "LOT-RELEASED",
                "qty": 14_400.0,
                "production_campaign_id": "CMP-PRE-J0",
            }
        ]

        row = build_production_campaign_rows([carry_in, complete], lot_rows)[0]

        self.assertEqual(row["campaign_started_day"], -2)
        self.assertEqual(row["first_event_day"], 0)
        self.assertEqual(row["completed_day"], 1)
        self.assertEqual(row["completed_lot_qty"], 14_400.0)
        self.assertEqual(row["wip_qty"], 0.0)

    def test_early_batch_release_does_not_mark_unfinished_campaign_complete(self) -> None:
        row_day_zero = self._plan_row(
            0,
            "CMP-MULTI",
            "start_campaign",
            "none",
            100.0,
            0.0,
            "",
            "",
        )
        row_day_zero.update(
            {
                "campaign_remaining_end_qty": 100.0,
                "released_qty": 100.0,
                "wip_end_qty": 0.0,
            }
        )
        delayed = self._plan_row(
            1,
            "CMP-MULTI",
            "delay_input_shortage",
            "input_shortage",
            0.0,
            100.0,
            "RM",
            3,
        )
        delayed.update({"campaign_remaining_start_qty": 100.0, "campaign_remaining_end_qty": 100.0})
        lot_rows = [
            {
                "day": 0,
                "event_type": "production_output",
                "lot_id": "LOT-FIRST-BATCH",
                "qty": 100.0,
                "production_campaign_id": "CMP-MULTI",
            }
        ]

        row = build_production_campaign_rows([row_day_zero, delayed], lot_rows)[0]

        self.assertEqual(row["status"], "partially_released_blocked")
        self.assertEqual(row["completed_day"], "")
        self.assertEqual(row["last_release_day"], 0)
        self.assertEqual(row["remaining_qty"], 100.0)

    def test_same_day_start_and_release_is_completed(self) -> None:
        start = self._plan_row(
            4,
            "CMP-SAME-DAY",
            "start_campaign",
            "none",
            14_400.0,
            0.0,
            "",
            "",
        )
        start.update(
            {
                "campaign_remaining_end_qty": 0.0,
                "released_qty": 14_400.0,
                "wip_end_qty": 0.0,
            }
        )

        row = build_production_campaign_rows(
            [start],
            [
                {
                    "day": 4,
                    "event_type": "production_output",
                    "lot_id": "LOT-SAME-DAY",
                    "qty": 14_400.0,
                    "production_campaign_id": "CMP-SAME-DAY",
                }
            ],
        )[0]

        self.assertEqual(row["status"], "completed_without_delay")
        self.assertEqual(row["completed_day"], 4)

    def test_multi_batch_campaign_completion_uses_last_release_day(self) -> None:
        first = self._plan_row(0, "CMP-TWO", "start_campaign", "none", 100.0, 0.0, "", "")
        first.update({"campaign_remaining_end_qty": 100.0, "released_qty": 100.0})
        second = self._plan_row(2, "CMP-TWO", "run_campaign_complete", "none", 100.0, 0.0, "", "")
        second.update(
            {
                "campaign_remaining_start_qty": 100.0,
                "campaign_remaining_end_qty": 0.0,
                "released_qty": 100.0,
            }
        )

        row = build_production_campaign_rows(
            [first, second],
            [
                {
                    "day": 0,
                    "event_type": "production_output",
                    "lot_id": "LOT-B1",
                    "qty": 100.0,
                    "production_campaign_id": "CMP-TWO",
                },
                {
                    "day": 2,
                    "event_type": "production_output",
                    "lot_id": "LOT-B2",
                    "qty": 100.0,
                    "production_campaign_id": "CMP-TWO",
                },
            ],
        )[0]

        self.assertEqual(row["completed_day"], 2)
        self.assertEqual(row["last_release_day"], 2)
        self.assertEqual(row["released_batch_count"], 2)
        self.assertEqual(row["completed_lot_qty"], 200.0)

    def test_compact_fractional_execution_uses_physical_batch_release(self) -> None:
        first = self._plan_row(0, "CMP-COMPACT", "partial_run_capacity", "capacity", 40.0, 60.0, "", "")
        first.update(
            {
                "batch_id": "CMP-COMPACT-B001",
                "batch_target_qty": 100.0,
                "batch_executed_end_qty": 40.0,
                "campaign_remaining_end_qty": 60.0,
                "wip_end_qty": 40.0,
                "released_qty": 0.0,
            }
        )
        second = self._plan_row(1, "CMP-COMPACT", "partial_run_capacity", "capacity", 35.0, 25.0, "", "")
        second.update(
            {
                "batch_id": "CMP-COMPACT-B001",
                "batch_target_qty": 100.0,
                "batch_executed_start_qty": 40.0,
                "batch_executed_end_qty": 75.0,
                "campaign_remaining_end_qty": 25.0,
                "wip_end_qty": 75.0,
                "released_qty": 0.0,
            }
        )
        complete = self._plan_row(2, "CMP-COMPACT", "run_campaign_complete", "none", 25.0, 0.0, "", "")
        complete.update(
            {
                "batch_id": "CMP-COMPACT-B001",
                "batch_target_qty": 100.0,
                "batch_executed_start_qty": 75.0,
                "batch_executed_end_qty": 100.0,
                "campaign_remaining_end_qty": 0.0,
                "wip_end_qty": 0.0,
                "released_qty": 100.0,
            }
        )

        row = build_production_campaign_rows([first, second, complete], [])[0]

        self.assertEqual(row["status"], "completed_after_delay")
        self.assertEqual(row["completed_day"], 2)
        self.assertEqual(row["last_release_day"], 2)
        self.assertEqual(row["completion_basis"], "last_released_physical_batch_from_plan_event")
        self.assertEqual(row["completed_lot_ids"], "")
        self.assertEqual(row["completed_lot_qty"], 100.0)
        self.assertEqual(row["released_batch_count"], 1)
        self.assertEqual(row["wip_qty"], 0.0)
        self.assertIn("compact evidence has no physical lot identifier or genealogy", row["notes"])

    def test_compact_incomplete_wip_is_not_reported_as_released(self) -> None:
        partial = self._plan_row(0, "CMP-WIP", "partial_run_input_shortage", "input_shortage", 40.0, 60.0, "RM", 3)
        partial.update(
            {
                "batch_id": "CMP-WIP-B001",
                "batch_target_qty": 100.0,
                "batch_executed_end_qty": 40.0,
                "campaign_remaining_end_qty": 60.0,
                "wip_end_qty": 40.0,
                "released_qty": 0.0,
            }
        )

        row = build_production_campaign_rows([partial], [])[0]

        self.assertEqual(row["status"], "in_progress_delayed")
        self.assertEqual(row["completed_day"], "")
        self.assertEqual(row["last_release_day"], "")
        self.assertEqual(row["completed_lot_qty"], 0.0)
        self.assertEqual(row["released_batch_count"], 0)
        self.assertEqual(row["wip_qty"], 40.0)

    def test_compact_partial_multi_batch_campaign_stays_open(self) -> None:
        released = self._plan_row(0, "CMP-PARTIAL", "start_campaign", "none", 100.0, 0.0, "", "")
        released.update(
            {
                "batch_id": "CMP-PARTIAL-B001",
                "batch_target_qty": 100.0,
                "campaign_remaining_end_qty": 100.0,
                "wip_end_qty": 0.0,
                "released_qty": 100.0,
            }
        )
        wip = self._plan_row(1, "CMP-PARTIAL", "run_campaign_partial", "none", 25.0, 0.0, "", "")
        wip.update(
            {
                "batch_id": "CMP-PARTIAL-B002",
                "batch_target_qty": 100.0,
                "batch_executed_end_qty": 25.0,
                "campaign_remaining_end_qty": 75.0,
                "wip_end_qty": 25.0,
                "released_qty": 0.0,
            }
        )

        row = build_production_campaign_rows([released, wip], [])[0]

        self.assertEqual(row["status"], "partially_released_in_progress")
        self.assertEqual(row["completed_day"], "")
        self.assertEqual(row["last_release_day"], 0)
        self.assertEqual(row["completed_lot_qty"], 100.0)
        self.assertEqual(row["released_batch_count"], 1)
        self.assertEqual(row["remaining_qty"], 75.0)
        self.assertEqual(row["wip_qty"], 25.0)

    def test_lot_trace_evidence_has_priority_without_double_counting(self) -> None:
        complete = self._plan_row(4, "CMP-FULL", "run_campaign_complete", "none", 100.0, 0.0, "", "")
        complete.update(
            {
                "batch_id": "CMP-FULL-B001",
                "campaign_remaining_end_qty": 0.0,
                "released_qty": 100.0,
            }
        )

        row = build_production_campaign_rows(
            [complete],
            [
                {
                    "day": 4,
                    "event_type": "production_output",
                    "lot_id": "LOT-FULL",
                    "qty": 100.0,
                    "production_campaign_id": "CMP-FULL",
                }
            ],
        )[0]

        self.assertEqual(row["completed_lot_qty"], 100.0)
        self.assertEqual(row["released_batch_count"], 1)
        self.assertEqual(row["completed_lot_ids"], "LOT-FULL")
        self.assertEqual(row["completion_basis"], "last_released_physical_lot")
        self.assertIn("release_evidence=lot_trace_production_output", row["notes"])
        self.assertNotIn("compact evidence", row["notes"])

    def test_compact_release_without_batch_identity_fails_closed(self) -> None:
        complete = self._plan_row(4, "CMP-ANON", "run_campaign_complete", "none", 100.0, 0.0, "", "")
        complete.update(
            {
                "campaign_remaining_end_qty": 0.0,
                "released_qty": 100.0,
            }
        )

        with self.assertRaisesRegex(ValueError, "lacks batch_id"):
            build_production_campaign_rows([complete], [])

    def test_compact_repeated_batch_release_fails_before_double_counting(self) -> None:
        first = self._plan_row(0, "CMP-DUP", "start_campaign", "none", 100.0, 0.0, "", "")
        first.update(
            {
                "batch_id": "CMP-DUP-B001",
                "campaign_remaining_end_qty": 100.0,
                "released_qty": 100.0,
            }
        )
        duplicate = self._plan_row(1, "CMP-DUP", "run_campaign_complete", "none", 100.0, 0.0, "", "")
        duplicate.update(
            {
                "batch_id": "CMP-DUP-B001",
                "campaign_remaining_end_qty": 0.0,
                "released_qty": 100.0,
            }
        )

        with self.assertRaisesRegex(ValueError, "repeats batch_id"):
            build_production_campaign_rows([first, duplicate], [])

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
