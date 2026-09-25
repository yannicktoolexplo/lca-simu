"""Regression tests for production campaigns."""

from __future__ import annotations
import unittest
import csv
import json
import subprocess
import sys
from etudecas.simulation.lot_trace.campaigns import (
    build_production_campaign_rows,
    ProductionBatchWip,
    make_batch_id,
    physical_batch_target_qty,
    production_week_index,
)
from etudecas.simulation.analysis.factory_nervousness import (
    build_factory_nervousness_rows,
)
from pathlib import Path
from etudecas.simulation.engine.run_first_simulation import (
    campaign_lot_count,
    launch_campaign_qty,
    limit_campaign_qty_by_weekly_lots,
)


# Test production campaigns

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


# Test factory nervousness

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


# Test production batch engine integration

REPO_ROOT = Path(__file__).resolve().parents[3]


ENGINE = REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"


GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json"
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_multi_day_batch_crosses_day_zero_and_releases_once(tmp_path: Path) -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    factory = next(node for node in graph["nodes"] if node.get("id") == "M-1810")
    process = next(
        process
        for process in factory.get("processes", [])
        if any(output.get("item_id") == "item:268091" for output in process.get("outputs", []))
    )
    process["capacity"]["max_rate"] = 5_000.0
    fixture = tmp_path / "capacity_limited_graph.json"
    fixture.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "run"

    result = subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--input",
            str(fixture),
            "--output-dir",
            str(output_dir),
            "--scenario-id",
            "scn:BASE",
            "--days",
            "3",
            "--warmup-days",
            "1",
            "--seed",
            "9102",
            "--output-profile",
            "compact",
            "--skip-map",
            "--skip-plots",
            "--use-bom-demand-signal-for-mrp",
            "--mrp-demand-signal-smoothing-days",
            "7",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    plan_rows = _read_rows(output_dir / "data" / "production_plan_events.csv")
    carry_in_rows = [
        row
        for row in plan_rows
        if row["node_id"] == "M-1810"
        and row["output_item_id"] == "item:268091"
        and row["day"] == "0"
        and row["is_day_zero_carry_in"] == "1"
    ]
    assert len(carry_in_rows) == 1
    carry_in = carry_in_rows[0]
    assert float(carry_in["batch_target_qty"]) == 14_400.0
    assert float(carry_in["wip_start_qty"]) == 5_000.0
    assert float(carry_in["batch_executed_today_qty"]) == 5_000.0
    assert float(carry_in["released_qty"]) == 0.0
    assert float(carry_in["wip_end_qty"]) == 10_000.0
    assert float(carry_in["process_tau_days"]) == 3.0
    assert carry_in["release_gate_mode"] == "execution_complete_tau_planning_only"
    assert not carry_in["released_lot_id"]

    completion_rows = [
        row
        for row in plan_rows
        if row["campaign_id"] == carry_in["campaign_id"] and row["day"] == "1"
    ]
    assert len(completion_rows) == 1
    completion = completion_rows[0]
    assert completion["event_type"] == "run_campaign_complete"
    assert float(completion["batch_executed_today_qty"]) == 4_400.0
    assert float(completion["released_qty"]) == 14_400.0
    assert float(completion["wip_end_qty"]) == 0.0
    assert completion["released_lot_id"]

    campaign_id = carry_in["campaign_id"]
    lot_rows = _read_rows(output_dir / "data" / "production_lot_events.csv")
    output_rows = [
        row
        for row in lot_rows
        if row["event_type"] == "production_output"
        and row["production_campaign_id"] == campaign_id
    ]
    assert len(output_rows) == 1
    assert output_rows[0]["day"] == "1"
    assert float(output_rows[0]["qty"]) == 14_400.0

    output_daily = _read_rows(output_dir / "data" / "production_output_products_daily.csv")
    target_daily = [
        row
        for row in output_daily
        if row["node_id"] == "M-1810" and row["item_id"] == "item:268091"
    ]
    day_zero = next(row for row in target_daily if row["day"] == "0")
    day_one = next(row for row in target_daily if row["day"] == "1")
    assert float(day_zero["executed_qty"]) == 5_000.0
    assert float(day_zero["released_qty"]) == 0.0
    assert float(day_zero["wip_end_qty"]) == 10_000.0
    assert float(day_one["executed_qty"]) == 4_400.0
    assert float(day_one["released_qty"]) == 14_400.0

    campaign_rows = _read_rows(output_dir / "data" / "production_campaigns.csv")
    campaign = next(row for row in campaign_rows if row["campaign_id"] == campaign_id)
    assert campaign["campaign_started_day"] == "-1"
    assert campaign["completed_day"] == "1"
    assert campaign["last_release_day"] == "1"
    assert campaign["status"] == "completed_after_delay"

    audit_issues = _read_rows(output_dir / "data" / "lot_path_audit_issues.csv")
    assert not [row for row in audit_issues if row.get("severity") == "error"]


# Test production execution

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
