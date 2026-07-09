from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from typing import Any

from etudecas.simulation.lot_trace import (
    build_lot_trace_payload,
    build_lot_trace_view_model,
)


class LotTraceViewModelTest(unittest.TestCase):
    def test_view_model_splits_upstream_and_downstream(self) -> None:
        payload = self._payload()

        upstream = build_lot_trace_view_model(payload, "LOT-PF", direction="upstream")
        downstream = build_lot_trace_view_model(payload, "LOT-PF", direction="downstream")
        complete = build_lot_trace_view_model(payload, "LOT-PF")

        self.assertEqual(set(upstream["snapshot"]["lot_ids"]), {"LOT-RM-S", "LOT-RM-F", "LOT-PF"})
        self.assertNotIn("LOT-DC-A", upstream["snapshot"]["lot_ids"])
        self.assertEqual(set(downstream["snapshot"]["lot_ids"]), {"LOT-PF", "LOT-DC-A", "LOT-DC-B", "LOT-CUST"})
        self.assertNotIn("LOT-RM-S", downstream["snapshot"]["lot_ids"])
        self.assertEqual(complete["summary"]["upstream_lot_count"], 2)
        self.assertEqual(complete["summary"]["downstream_lot_count"], 3)
        self.assertEqual(complete["snapshot"]["days"], [0, 2, 3, 5, 7])

    def test_transport_groups_consolidate_technical_splits(self) -> None:
        payload = self._payload()
        view = build_lot_trace_view_model(payload, "LOT-PF")

        groups = {
            (row["from_node_id"], row["to_node_id"], row["item_id"], row["day"]): row
            for row in view["transport_groups"]
        }
        factory_to_dc = groups[("M-1", "DC-1", "item:PF", 5)]

        self.assertEqual(factory_to_dc["parent_lot_ids"], ["LOT-PF"])
        self.assertEqual(factory_to_dc["child_lot_ids"], ["LOT-DC-A", "LOT-DC-B"])
        self.assertEqual(factory_to_dc["parent_lot_count"], 1)
        self.assertEqual(factory_to_dc["child_lot_count"], 2)
        self.assertTrue(factory_to_dc["is_consolidated"])
        self.assertAlmostEqual(factory_to_dc["shipped_qty"], 10.0)
        self.assertAlmostEqual(factory_to_dc["received_qty"], 10.0)

    def test_mixed_customer_lot_reports_other_origin(self) -> None:
        payload = self._payload()
        view = build_lot_trace_view_model(payload, "LOT-PF")

        self.assertEqual(len(view["mixed_customer_lots"]), 1)
        mixed = view["mixed_customer_lots"][0]
        self.assertEqual(mixed["lot_id"], "LOT-CUST")
        self.assertEqual(mixed["visible_parent_lot_ids"], ["LOT-DC-A"])
        self.assertEqual(mixed["other_parent_lot_ids"], ["LOT-OTHER-DC"])
        self.assertAlmostEqual(mixed["visible_contribution_qty"], 6.0)
        self.assertAlmostEqual(mixed["other_contribution_qty"], 4.0)
        self.assertAlmostEqual(mixed["total_qty"], 10.0)
        self.assertAlmostEqual(mixed["visible_share"], 0.6)
        self.assertTrue(mixed["is_mixed_with_other_origin"])

    def test_mixed_customer_lot_propagates_partial_parent_share(self) -> None:
        payload = self._payload()
        for link in payload["genealogy"]:
            if link["parent_lot_id"] == "LOT-PF" and link["child_lot_id"] == "LOT-DC-A":
                link["parent_qty"] = 3.0
                break

        view = build_lot_trace_view_model(payload, "LOT-PF")

        mixed = view["mixed_customer_lots"][0]
        self.assertEqual(mixed["lot_id"], "LOT-CUST")
        self.assertAlmostEqual(mixed["visible_contribution_qty"], 3.0)
        self.assertAlmostEqual(mixed["other_contribution_qty"], 7.0)
        self.assertAlmostEqual(mixed["visible_share"], 0.3)

    @unittest.skipUnless(
        os.environ.get("ETUDECAS_RUN_SLOW_TESTS") == "1",
        "set ETUDECAS_RUN_SLOW_TESTS=1 to validate the 5-year lot view model",
    )
    def test_real_lot_00000095_view_model_invariants(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        output_root = repo_root / "etudecas" / "simulation" / "result" / "_codex_lot_trace_5y_risk_portfolio"
        summary_path = output_root / "summaries" / "first_simulation_summary.json"
        events_path = output_root / "data" / "production_lot_events.csv"
        genealogy_path = output_root / "data" / "production_lot_genealogy.csv"
        plan_path = output_root / "data" / "production_plan_events.csv"
        if not summary_path.exists() or not events_path.exists() or not genealogy_path.exists():
            self.skipTest("5-year lot trace fixture is not available locally")

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        graph_path = Path(summary.get("input_file") or "")
        if not graph_path.is_absolute():
            graph_path = repo_root / graph_path
        if not graph_path.exists():
            self.skipTest(f"simulation graph fixture is not available locally: {graph_path}")
        raw = json.loads(graph_path.read_text(encoding="utf-8"))

        payload = build_lot_trace_payload(events_path, genealogy_path, plan_path, raw=raw)
        view = build_lot_trace_view_model(payload, "LOT-00000095")
        factory_to_dc = [
            row
            for row in view["transport_groups"]
            if row["from_node_id"] == "M-1430"
            and row["to_node_id"] == "DC-1920"
            and row["item_id"] == "item:268967"
        ]
        component_items = {
            row["item_id"]
            for row in view["component_groups"]
            if row["child_lot_id"] == "LOT-00000095"
        }

        self.assertEqual(view["summary"]["upstream_lot_count"], 8)
        self.assertEqual(view["summary"]["downstream_lot_count"], 12)
        self.assertEqual(len(component_items), 8)
        self.assertEqual(len(factory_to_dc), 1)
        self.assertAlmostEqual(factory_to_dc[0]["shipped_qty"], 107800.0, places=4)
        self.assertAlmostEqual(factory_to_dc[0]["received_qty"], 107800.0, places=4)
        self.assertGreaterEqual(view["summary"]["mixed_customer_lot_count"], 1)

    def _payload(self) -> dict[str, Any]:
        lots = {
            "LOT-RM-S": self._lot("LOT-RM-S", 0, "S-RAW", "item:RM", 100.0, "raw_material_opening"),
            "LOT-RM-F": self._lot("LOT-RM-F", 2, "M-1", "item:RM", 100.0, "raw_material_factory_receipt"),
            "LOT-PF": self._lot("LOT-PF", 3, "M-1", "item:PF", 10.0, "finished_product"),
            "LOT-DC-A": self._lot("LOT-DC-A", 5, "DC-1", "item:PF", 6.0, "finished_product_receipt"),
            "LOT-DC-B": self._lot("LOT-DC-B", 5, "DC-1", "item:PF", 4.0, "finished_product_receipt"),
            "LOT-CUST": self._lot("LOT-CUST", 7, "C-1", "item:PF", 10.0, "customer_receipt"),
            "LOT-OTHER-DC": self._lot("LOT-OTHER-DC", 1, "DC-1", "item:PF", 4.0, "finished_product_receipt"),
        }
        events = [
            self._event("E-RM-S", "LOT-RM-S", 0, "S-RAW", "item:RM", 100.0),
            self._event("E-RM-F", "LOT-RM-F", 2, "M-1", "item:RM", 100.0),
            self._event("E-PF", "LOT-PF", 3, "M-1", "item:PF", 10.0),
            self._event("E-DC-A", "LOT-DC-A", 5, "DC-1", "item:PF", 6.0),
            self._event("E-DC-B", "LOT-DC-B", 5, "DC-1", "item:PF", 4.0),
            self._event("E-CUST", "LOT-CUST", 7, "C-1", "item:PF", 10.0),
            self._event("E-OTHER", "LOT-OTHER-DC", 1, "DC-1", "item:PF", 4.0),
        ]
        genealogy = [
            self._link(2, "transport", "LOT-RM-S", "S-RAW", "item:RM", "LOT-RM-F", "M-1", "item:RM", 100.0, 100.0),
            self._link(3, "production", "LOT-RM-F", "M-1", "item:RM", "LOT-PF", "M-1", "item:PF", 100.0, 10.0),
            self._link(5, "transport", "LOT-PF", "M-1", "item:PF", "LOT-DC-A", "DC-1", "item:PF", 6.0, 6.0),
            self._link(5, "transport", "LOT-PF", "M-1", "item:PF", "LOT-DC-B", "DC-1", "item:PF", 4.0, 4.0),
            self._link(7, "transport", "LOT-DC-A", "DC-1", "item:PF", "LOT-CUST", "C-1", "item:PF", 6.0, 10.0),
            self._link(7, "transport", "LOT-OTHER-DC", "DC-1", "item:PF", "LOT-CUST", "C-1", "item:PF", 4.0, 10.0),
        ]
        return {
            "available": True,
            "lots": lots,
            "events": events,
            "genealogy": genealogy,
            "plan_events": [],
            "lot_options": [lots["LOT-PF"], lots["LOT-RM-S"]],
            "deferred_orders": [],
            "stock_context": {},
            "summary": {"lot_count": len(lots)},
        }

    def _lot(
        self,
        lot_id: str,
        day: int,
        node_id: str,
        item_id: str,
        qty: float,
        scope: str,
    ) -> dict[str, Any]:
        return {
            "lot_id": lot_id,
            "label": lot_id,
            "trace_scope": scope,
            "trace_scope_label": scope,
            "created_day": day,
            "created_event_type": "creation",
            "node_id": node_id,
            "item_id": item_id,
            "qty": qty,
            "uom": "UN",
            "source_type": "creation",
            "source_id": "test",
            "production_campaign_id": "CMP-1" if lot_id == "LOT-PF" else "",
            "first_day": day,
            "last_day": day,
            "event_count": 1,
        }

    def _event(
        self,
        event_id: str,
        lot_id: str,
        day: int,
        node_id: str,
        item_id: str,
        qty: float,
    ) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "day": day,
            "event_type": "creation",
            "lot_id": lot_id,
            "node_id": node_id,
            "item_id": item_id,
            "qty": qty,
            "qty_after": qty,
            "uom": "UN",
            "source_type": "creation",
            "source_id": "test",
            "related_lot_id": "",
            "production_campaign_id": "CMP-1" if lot_id == "LOT-PF" else "",
            "notes": "",
        }

    def _link(
        self,
        day: int,
        link_type: str,
        parent_lot_id: str,
        parent_node_id: str,
        parent_item_id: str,
        child_lot_id: str,
        child_node_id: str,
        child_item_id: str,
        parent_qty: float,
        child_qty: float,
    ) -> dict[str, Any]:
        return {
            "day": day,
            "link_type": link_type,
            "parent_lot_id": parent_lot_id,
            "parent_node_id": parent_node_id,
            "parent_item_id": parent_item_id,
            "child_lot_id": child_lot_id,
            "child_node_id": child_node_id,
            "child_item_id": child_item_id,
            "parent_qty": parent_qty,
            "child_qty": child_qty,
            "allocation_share": parent_qty / child_qty if child_qty else 0.0,
            "source_id": f"{parent_node_id}->{child_node_id}",
            "production_campaign_id": "CMP-1" if link_type == "production" else "",
            "notes": "",
        }


if __name__ == "__main__":
    unittest.main()
