from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


EVENT_FIELDS = [
    "event_id",
    "day",
    "event_type",
    "lot_id",
    "node_id",
    "item_id",
    "qty",
    "qty_after",
    "uom",
    "source_type",
    "source_id",
    "related_lot_id",
    "production_campaign_id",
    "notes",
]

GENEALOGY_FIELDS = [
    "day",
    "link_type",
    "parent_lot_id",
    "parent_node_id",
    "parent_item_id",
    "child_lot_id",
    "child_node_id",
    "child_item_id",
    "parent_qty",
    "child_qty",
    "allocation_share",
    "source_id",
    "production_campaign_id",
    "notes",
]


class LotPathAuditTest(unittest.TestCase):
    def test_lossy_transport_receipt_matches_child_quantity(self) -> None:
        source_id = "edge:S-1_TO_F-1_item:RM-1"
        events = [
            self._event("E1", 0, "opening_stock", "LOT-P", "S-1", "item:RM-1", 5000.0, 5000.0, "opening_stock", "seed"),
            self._event("E2", 1, "lane_ship", "LOT-P", "S-1", "item:RM-1", 5000.0, 0.0, "opening_stock", source_id),
            self._event("E3", 2, "lane_receipt", "LOT-C", "F-1", "item:RM-1", 4500.0, 4500.0, "lane_receipt", source_id),
        ]
        genealogy = [
            self._transport_link(
                day=2,
                parent_lot_id="LOT-P",
                child_lot_id="LOT-C",
                parent_qty=5000.0,
                child_qty=4500.0,
                allocation_share=1.0,
                source_id=source_id,
            )
        ]

        issues = self._run_audit(events, genealogy)

        self.assertFalse([row for row in issues if row["severity"] == "error"], issues)
        self.assertFalse([row for row in issues if row["kind"] == "transport_receipt_qty_mismatch"], issues)

    def test_transport_child_quantity_conflict_is_reported(self) -> None:
        source_id = "edge:S-1_TO_F-1_item:RM-1"
        events = [
            self._event("E1", 0, "opening_stock", "LOT-P1", "S-1", "item:RM-1", 3000.0, 3000.0, "opening_stock", "seed"),
            self._event("E2", 0, "opening_stock", "LOT-P2", "S-1", "item:RM-1", 2000.0, 2000.0, "opening_stock", "seed"),
            self._event("E3", 1, "lane_ship", "LOT-P1", "S-1", "item:RM-1", 3000.0, 0.0, "opening_stock", source_id),
            self._event("E4", 1, "lane_ship", "LOT-P2", "S-1", "item:RM-1", 2000.0, 0.0, "opening_stock", source_id),
            self._event("E5", 2, "lane_receipt", "LOT-C", "F-1", "item:RM-1", 4500.0, 4500.0, "lane_receipt", source_id),
        ]
        genealogy = [
            self._transport_link(
                day=2,
                parent_lot_id="LOT-P1",
                child_lot_id="LOT-C",
                parent_qty=3000.0,
                child_qty=4500.0,
                allocation_share=0.6,
                source_id=source_id,
            ),
            self._transport_link(
                day=2,
                parent_lot_id="LOT-P2",
                child_lot_id="LOT-C",
                parent_qty=2000.0,
                child_qty=4400.0,
                allocation_share=0.4,
                source_id=source_id,
            ),
        ]

        issues = self._run_audit(events, genealogy)

        self.assertTrue([row for row in issues if row["kind"] == "transport_receipt_child_qty_conflict"], issues)

    def test_unparented_lane_receipt_is_reported_as_trace_limit(self) -> None:
        source_id = "edge:S-1_TO_F-1_item:RM-1"
        events = [
            self._event("E1", 2, "lane_receipt", "LOT-C", "F-1", "item:RM-1", 4500.0, 4500.0, "lane_receipt", source_id),
        ]

        issues = self._run_audit(events, [])

        self.assertFalse([row for row in issues if row["severity"] == "error"], issues)
        self.assertTrue([row for row in issues if row["kind"] == "lane_receipts_without_trace_parent"], issues)

    def test_multi_day_wip_reconciles_consumption_at_campaign_level(self) -> None:
        events = [
            self._event("E0", -3, "opening_stock", "LOT-RM", "F-1", "item:RM-1", 100.0, 100.0, "opening_stock", "seed"),
            self._event("E1", -2, "production_consume", "LOT-RM", "F-1", "item:RM-1", 30.0, 70.0, "opening_stock", "F-1|item:PF"),
            self._event("E2", -1, "production_consume", "LOT-RM", "F-1", "item:RM-1", 30.0, 40.0, "opening_stock", "F-1|item:PF"),
            self._event("E3", 0, "production_consume", "LOT-RM", "F-1", "item:RM-1", 40.0, 0.0, "opening_stock", "F-1|item:PF"),
            self._event("E4", 0, "production_output", "LOT-PF", "F-1", "item:PF", 100.0, 100.0, "production_output", "F-1|item:PF"),
        ]
        for event in events[1:]:
            event["production_campaign_id"] = "CMP-PRE-J0"
        genealogy = [
            {
                "day": 0,
                "link_type": "production",
                "parent_lot_id": "LOT-RM",
                "parent_node_id": "F-1",
                "parent_item_id": "item:RM-1",
                "child_lot_id": "LOT-PF",
                "child_node_id": "F-1",
                "child_item_id": "item:PF",
                "parent_qty": 100.0,
                "child_qty": 100.0,
                "allocation_share": 1.0,
                "source_id": "F-1|item:PF",
                "production_campaign_id": "CMP-PRE-J0",
                "notes": "semantics=campaign-batch-wip-release-v1;batch_id=CMP-PRE-J0-B001",
            }
        ]

        issues = self._run_audit(events, genealogy)

        self.assertFalse([row for row in issues if row["severity"] == "error"], issues)

    def test_reference_transition_event_is_a_valid_production_consumption(self) -> None:
        campaign_id = "CMP-1"
        events = [
            {
                **self._event(
                    "E1",
                    0,
                    "opening_stock",
                    "LOT-P",
                    "F-1",
                    "item:EX-PACK",
                    100.0,
                    100.0,
                    "opening_stock",
                    "seed",
                ),
                "production_campaign_id": "",
            },
            {
                **self._event(
                    "E2",
                    1,
                    "production_consume_reference_transition",
                    "LOT-P",
                    "F-1",
                    "item:EX-PACK",
                    100.0,
                    0.0,
                    "opening_stock",
                    campaign_id,
                ),
                "production_campaign_id": campaign_id,
            },
            {
                **self._event(
                    "E3",
                    1,
                    "production_output",
                    "LOT-C",
                    "F-1",
                    "item:PF",
                    1000.0,
                    1000.0,
                    "production_output",
                    campaign_id,
                ),
                "production_campaign_id": campaign_id,
            },
        ]
        genealogy = [
            {
                "day": 1,
                "link_type": "production",
                "parent_lot_id": "LOT-P",
                "parent_node_id": "F-1",
                "parent_item_id": "item:EX-PACK",
                "child_lot_id": "LOT-C",
                "child_node_id": "F-1",
                "child_item_id": "item:PF",
                "parent_qty": 100.0,
                "child_qty": 1000.0,
                "allocation_share": 1.0,
                "source_id": campaign_id,
                "production_campaign_id": campaign_id,
                "notes": "",
            }
        ]

        issues = self._run_audit(events, genealogy)

        self.assertFalse([row for row in issues if row["severity"] == "error"], issues)

    def test_multi_day_wip_campaign_quantity_mismatch_is_reported(self) -> None:
        events = [
            self._event("E0", -1, "opening_stock", "LOT-RM", "F-1", "item:RM-1", 100.0, 100.0, "opening_stock", "seed"),
            self._event("E1", 0, "production_consume", "LOT-RM", "F-1", "item:RM-1", 90.0, 10.0, "opening_stock", "F-1|item:PF"),
            self._event("E2", 0, "production_output", "LOT-PF", "F-1", "item:PF", 100.0, 100.0, "production_output", "F-1|item:PF"),
        ]
        for event in events[1:]:
            event["production_campaign_id"] = "CMP-1"
        genealogy = [
            {
                "day": 0,
                "link_type": "production",
                "parent_lot_id": "LOT-RM",
                "parent_node_id": "F-1",
                "parent_item_id": "item:RM-1",
                "child_lot_id": "LOT-PF",
                "child_node_id": "F-1",
                "child_item_id": "item:PF",
                "parent_qty": 100.0,
                "child_qty": 100.0,
                "allocation_share": 1.0,
                "source_id": "F-1|item:PF",
                "production_campaign_id": "CMP-1",
                "notes": "semantics=campaign-batch-wip-release-v1;batch_id=CMP-1-B001",
            }
        ]

        issues = self._run_audit(events, genealogy)

        self.assertTrue(
            [row for row in issues if row["kind"] == "production_wip_link_campaign_consume_qty_mismatch"],
            issues,
        )

    def _run_audit(self, events: list[dict[str, object]], genealogy: list[dict[str, object]]) -> list[dict[str, str]]:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            data_dir = output_root / "data"
            data_dir.mkdir(parents=True)
            self._write_csv(data_dir / "production_lot_events.csv", EVENT_FIELDS, events)
            self._write_csv(data_dir / "production_lot_genealogy.csv", GENEALOGY_FIELDS, genealogy)
            input_path = output_root / "input.json"
            input_path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {"id": "S-1", "type": "supplier_dc"},
                            {"id": "F-1", "type": "factory"},
                            {"id": "C-1", "type": "customer"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            issues_path = output_root / "issues.csv"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "etudecas.simulation.analysis.audit_lot_paths",
                    "--output-root",
                    str(output_root),
                    "--input",
                    str(input_path),
                    "--issues-csv",
                    str(issues_path),
                ],
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with issues_path.open("r", encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))

    def _event(
        self,
        event_id: str,
        day: int,
        event_type: str,
        lot_id: str,
        node_id: str,
        item_id: str,
        qty: float,
        qty_after: float,
        source_type: str,
        source_id: str,
    ) -> dict[str, object]:
        return {
            "event_id": event_id,
            "day": day,
            "event_type": event_type,
            "lot_id": lot_id,
            "node_id": node_id,
            "item_id": item_id,
            "qty": qty,
            "qty_after": qty_after,
            "uom": "KG",
            "source_type": source_type,
            "source_id": source_id,
            "related_lot_id": "",
            "production_campaign_id": "",
            "notes": "",
        }

    def _transport_link(
        self,
        *,
        day: int,
        parent_lot_id: str,
        child_lot_id: str,
        parent_qty: float,
        child_qty: float,
        allocation_share: float,
        source_id: str,
    ) -> dict[str, object]:
        return {
            "day": day,
            "link_type": "transport",
            "parent_lot_id": parent_lot_id,
            "parent_node_id": "S-1",
            "parent_item_id": "item:RM-1",
            "child_lot_id": child_lot_id,
            "child_node_id": "F-1",
            "child_item_id": "item:RM-1",
            "parent_qty": parent_qty,
            "child_qty": child_qty,
            "allocation_share": allocation_share,
            "source_id": source_id,
            "production_campaign_id": "",
            "notes": "",
        }

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
