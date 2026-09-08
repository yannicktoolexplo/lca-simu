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
        self.assertEqual(complete["summary"]["upstream_lot_count"], 1)
        self.assertEqual(complete["summary"]["downstream_lot_count"], 1)
        self.assertEqual(complete["summary"]["upstream_occurrence_count"], 2)
        self.assertEqual(complete["summary"]["downstream_occurrence_count"], 3)
        self.assertEqual(complete["summary"]["business_lot_count"], 2)
        self.assertEqual(complete["summary"]["stock_occurrence_count"], 6)
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
        self.assertEqual(factory_to_dc["child_lot_count"], 1)
        self.assertEqual(factory_to_dc["parent_occurrence_count"], 1)
        self.assertEqual(factory_to_dc["child_occurrence_count"], 2)
        self.assertEqual(factory_to_dc["business_lot_ids"], ["LOT-PF"])
        self.assertTrue(factory_to_dc["is_consolidated"])
        self.assertAlmostEqual(factory_to_dc["shipped_qty"], 10.0)
        self.assertAlmostEqual(factory_to_dc["received_qty"], 10.0)
        self.assertEqual(factory_to_dc["group_type"], "inferred_group")
        self.assertEqual(factory_to_dc["trace_status"], "inferred")
        self.assertFalse(factory_to_dc["is_physical_shipment"])

    def test_view_model_separates_business_entities_and_readable_counts(self) -> None:
        payload = self._payload()
        for lot_id in ("LOT-PF", "LOT-DC-A", "LOT-DC-B", "LOT-CUST"):
            payload["lots"][lot_id]["business_lot_id"] = "BATCH-PF-001"
            payload["lots"][lot_id]["stock_occurrence_id"] = f"OCC-{lot_id}"
        payload["lots"]["LOT-RM-S"]["business_lot_id"] = "BATCH-RM-001"
        payload["lots"]["LOT-RM-F"]["business_lot_id"] = "BATCH-RM-001"
        for link in payload["genealogy"]:
            if (
                link["link_type"] == "transport"
                and link["parent_lot_id"] == "LOT-PF"
            ):
                link["shipment_id"] = "SHIP-FACTORY-DC"

        view = build_lot_trace_view_model(payload, "LOT-PF")

        self.assertEqual(
            [row["business_lot_id"] for row in view["business_lots"]],
            ["BATCH-PF-001", "BATCH-RM-001"],
        )
        pf_business_lot = view["business_lots"][0]
        self.assertEqual(pf_business_lot["occurrence_count"], 4)
        self.assertEqual(view["summary"]["business_lot_count"], 2)
        self.assertEqual(view["summary"]["stock_occurrence_count"], 6)
        self.assertEqual(view["summary"]["shipment_count"], 1)
        self.assertEqual(view["summary"]["production_operation_count"], 1)
        self.assertEqual(len(view["shipments"]), 1)
        self.assertEqual(len(view["production_operations"]), 1)
        self.assertIn("2 lot(s) metier", view["summary"]["business_counter_label"])
        self.assertIn(
            "6 occurrence(s) de stock",
            view["summary"]["business_counter_label"],
        )

    def test_view_model_excludes_events_outside_selected_contribution(self) -> None:
        payload = self._payload()
        unrelated_writeoff = self._event(
            "E-WRITEOFF-LATE",
            "LOT-PF",
            30,
            "M-1",
            "item:PF",
            2.0,
        )
        unrelated_writeoff["event_type"] = "writeoff"
        unrelated_shipment = self._event(
            "E-SHIP-OTHER",
            "LOT-PF",
            4,
            "M-1",
            "item:PF",
            2.0,
        )
        unrelated_shipment.update(
            {
                "event_type": "lane_ship",
                "source_id": "M-1->DC-OTHER",
                "related_lot_id": "LOT-OTHER-RECEIPT",
            }
        )
        payload["events"].extend([unrelated_writeoff, unrelated_shipment])
        payload["lots"]["LOT-PF"]["event_count"] = 3

        view = build_lot_trace_view_model(payload, "LOT-PF")
        event_ids = {event["event_id"] for event in view["events"]}
        pf_node = next(
            node for node in view["nodes"] if node["lot_id"] == "LOT-PF"
        )

        self.assertNotIn("E-WRITEOFF-LATE", event_ids)
        self.assertNotIn("E-SHIP-OTHER", event_ids)
        self.assertEqual(view["summary"]["excluded_non_causal_event_count"], 2)
        self.assertEqual(pf_node["causal_event_count"], 1)
        self.assertEqual(pf_node["available_event_count"], 3)

    def test_untraced_receipt_is_occurrence_not_invented_business_lot(self) -> None:
        lot = self._lot(
            "LOT-UNTRACED",
            4,
            "M-1",
            "item:RM",
            12.0,
            "raw_material_factory_receipt",
        )
        event = self._event(
            "E-UNTRACED",
            "LOT-UNTRACED",
            4,
            "M-1",
            "item:RM",
            12.0,
        )
        event["event_type"] = "lane_receipt"
        payload = {
            "available": True,
            "lots": {"LOT-UNTRACED": lot},
            "events": [event],
            "genealogy": [],
            "plan_events": [],
            "lot_options": [],
            "deferred_orders": [],
            "stock_context": {},
            "summary": {"lot_count": 1},
        }

        view = build_lot_trace_view_model(payload, "LOT-UNTRACED")

        self.assertEqual(view["summary"]["business_lot_count"], 0)
        self.assertEqual(view["summary"]["stock_occurrence_count"], 1)
        self.assertEqual(view["summary"]["unidentified_occurrence_count"], 1)
        self.assertEqual(view["business_lots"], [])

    def test_transport_groups_use_shipment_id_and_expose_logistics_context(self) -> None:
        payload = self._payload()
        for link in payload["genealogy"]:
            if link["parent_lot_id"] == "LOT-PF" and link["child_node_id"] == "DC-1":
                link["shipment_id"] = "SHIP-001"
                link["departure_day"] = 3
                link["arrival_day"] = 5
                link["handling_unit"] = "HU-TRAILER-001"

        view = build_lot_trace_view_model(payload, "LOT-PF")
        shipments = [
            row
            for row in view["transport_groups"]
            if row["shipment_id"] == "SHIP-001"
        ]

        self.assertEqual(len(shipments), 1)
        shipment = shipments[0]
        self.assertEqual(shipment["group_type"], "shipment")
        self.assertEqual(shipment["trace_status"], "simulation_movement_identified")
        self.assertEqual(shipment["trace_reason"], "shipment_id_present")
        self.assertEqual(shipment["reason"], "shipment_id_present")
        self.assertEqual(shipment["departure_day"], 3)
        self.assertEqual(shipment["arrival_day"], 5)
        self.assertEqual(shipment["handling_unit"], "HU-TRAILER-001")
        self.assertFalse(shipment["is_physical_shipment"])
        self.assertTrue(shipment["is_simulated_shipment"])
        self.assertAlmostEqual(shipment["shipped_qty"], 10.0)
        self.assertAlmostEqual(shipment["received_qty"], 10.0)

    def test_handling_unit_does_not_leak_between_successive_shipments(self) -> None:
        payload = self._payload()
        for link in payload["genealogy"]:
            if link["link_type"] != "transport":
                continue
            if link["parent_node_id"] == "M-1":
                link["shipment_id"] = "SHIP-FACTORY-DC"
                link["handling_unit_id"] = "TRUCK-FACTORY-DC"
            elif link["parent_node_id"] == "DC-1":
                link["shipment_id"] = "SHIP-DC-CUSTOMER"
        pf_event = next(
            event for event in payload["events"] if event["lot_id"] == "LOT-PF"
        )
        pf_event.update(
            {
                "shipment_id": "SHIP-FACTORY-DC",
                "handling_unit_id": "TRUCK-FACTORY-DC",
            }
        )

        view = build_lot_trace_view_model(payload, "LOT-PF")
        by_shipment = {
            row["shipment_id"]: row
            for row in view["transport_groups"]
            if row.get("shipment_id")
        }

        self.assertEqual(
            by_shipment["SHIP-FACTORY-DC"]["handling_unit"],
            "TRUCK-FACTORY-DC",
        )
        self.assertEqual(
            by_shipment["SHIP-DC-CUSTOMER"]["handling_unit"],
            "",
        )

    def test_untraced_lane_receipt_is_explicit(self) -> None:
        lot = self._lot(
            "LOT-UNTRACED",
            4,
            "M-1",
            "item:RM",
            12.0,
            "raw_material_factory_receipt",
        )
        event = self._event(
            "E-UNTRACED",
            "LOT-UNTRACED",
            4,
            "M-1",
            "item:RM",
            12.0,
        )
        event["event_type"] = "lane_receipt"
        event["source_id"] = "S-RAW->M-1"
        payload = {
            "available": True,
            "lots": {"LOT-UNTRACED": lot},
            "events": [event],
            "genealogy": [],
            "plan_events": [],
            "lot_options": [lot],
            "deferred_orders": [],
            "stock_context": {},
            "summary": {"lot_count": 1},
        }

        view = build_lot_trace_view_model(payload, "LOT-UNTRACED")

        self.assertEqual(len(view["transport_groups"]), 1)
        receipt = view["transport_groups"][0]
        self.assertEqual(receipt["group_type"], "untraced_receipt")
        self.assertEqual(receipt["trace_status"], "untraced_origin")
        self.assertEqual(receipt["trace_reason"], "no_transport_parent_link")
        self.assertEqual(receipt["reason"], "no_transport_parent_link")
        self.assertEqual(receipt["parent_lot_ids"], [])
        self.assertEqual(receipt["child_lot_ids"], ["LOT-UNTRACED"])
        self.assertIsNone(receipt["departure_day"])
        self.assertEqual(receipt["arrival_day"], 4)
        self.assertAlmostEqual(receipt["received_qty"], 12.0)

    def test_untraced_lane_receipt_preserves_source_trace_reason(self) -> None:
        lot = self._lot(
            "LOT-UNTRACED",
            4,
            "M-1",
            "item:RM",
            12.0,
            "raw_material_factory_receipt",
        )
        event = self._event(
            "E-UNTRACED",
            "LOT-UNTRACED",
            4,
            "M-1",
            "item:RM",
            12.0,
        )
        event.update(
            {
                "event_type": "lane_receipt",
                "source_id": "aggregate-pipeline",
                "trace_status": "untraced_origin",
                "trace_reason": "aggregate_pipeline_without_scheduled_lot_detail",
            }
        )
        payload = {
            "available": True,
            "lots": {"LOT-UNTRACED": lot},
            "events": [event],
            "genealogy": [],
            "plan_events": [],
            "lot_options": [lot],
            "deferred_orders": [],
            "stock_context": {},
            "summary": {"lot_count": 1},
        }

        view = build_lot_trace_view_model(payload, "LOT-UNTRACED")

        receipt = view["transport_groups"][0]
        self.assertEqual(receipt["trace_status"], "untraced_origin")
        self.assertEqual(
            receipt["trace_reason"],
            "aggregate_pipeline_without_scheduled_lot_detail",
        )
        self.assertEqual(
            receipt["reason"],
            "aggregate_pipeline_without_scheduled_lot_detail",
        )

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
        payload["lots"]["LOT-OTHER-PF"] = self._lot(
            "LOT-OTHER-PF",
            3,
            "M-1",
            "item:PF",
            3.0,
            "finished_product",
        )
        payload["events"].append(
            self._event("E-OTHER-PF", "LOT-OTHER-PF", 3, "M-1", "item:PF", 3.0)
        )
        for link in payload["genealogy"]:
            if link["parent_lot_id"] == "LOT-PF" and link["child_lot_id"] == "LOT-DC-A":
                link["parent_qty"] = 3.0
                break
        payload["genealogy"].append(
            self._link(
                5,
                "transport",
                "LOT-OTHER-PF",
                "M-1",
                "item:PF",
                "LOT-DC-A",
                "DC-1",
                "item:PF",
                3.0,
                6.0,
            )
        )

        view = build_lot_trace_view_model(payload, "LOT-PF")

        mixed = view["mixed_customer_lots"][0]
        self.assertEqual(mixed["lot_id"], "LOT-CUST")
        self.assertAlmostEqual(mixed["visible_contribution_qty"], 3.0)
        self.assertAlmostEqual(mixed["other_contribution_qty"], 7.0)
        self.assertAlmostEqual(mixed["visible_share"], 0.3)

    def test_split_component_propagates_only_its_same_uom_consumption_share(self) -> None:
        payload = self._payload()
        payload["lots"]["LOT-RM-F"]["qty"] = 10.0
        payload["events"][1]["qty"] = 10.0
        payload["events"][1]["qty_after"] = 10.0
        payload["lots"]["LOT-RM-F-B"] = self._lot(
            "LOT-RM-F-B",
            2,
            "M-1",
            "item:RM",
            90.0,
            "raw_material_factory_receipt",
        )
        payload["lots"]["LOT-OTHER-UOM"] = self._lot(
            "LOT-OTHER-UOM",
            2,
            "M-1",
            "item:OTHER",
            1_000_000.0,
            "raw_material_factory_receipt",
        )
        payload["lots"]["LOT-OTHER-UOM"]["uom"] = "G"
        payload["events"].extend(
            [
                self._event("E-RM-F-B", "LOT-RM-F-B", 2, "M-1", "item:RM", 90.0),
                self._event("E-OTHER-UOM", "LOT-OTHER-UOM", 2, "M-1", "item:OTHER", 1_000_000.0),
            ]
        )
        payload["events"][-1]["uom"] = "G"
        for link in payload["genealogy"]:
            if link["link_type"] == "production" and link["parent_lot_id"] == "LOT-RM-F":
                link["parent_qty"] = 10.0
                break
        payload["genealogy"].extend(
            [
                self._link(
                    3,
                    "production",
                    "LOT-RM-F-B",
                    "M-1",
                    "item:RM",
                    "LOT-PF",
                    "M-1",
                    "item:PF",
                    90.0,
                    10.0,
                ),
                self._link(
                    3,
                    "production",
                    "LOT-OTHER-UOM",
                    "M-1",
                    "item:OTHER",
                    "LOT-PF",
                    "M-1",
                    "item:PF",
                    1_000_000.0,
                    10.0,
                ),
            ]
        )

        view = build_lot_trace_view_model(payload, "LOT-RM-F")
        nodes = {row["lot_id"]: row for row in view["nodes"]}
        production_link = next(
            row
            for row in view["links"]
            if row["link_type"] == "production"
            and row["parent_lot_id"] == "LOT-RM-F"
        )
        mixed = view["mixed_customer_lots"][0]

        self.assertAlmostEqual(nodes["LOT-PF"]["contribution_qty"], 1.0)
        self.assertAlmostEqual(production_link["contribution_qty"], 1.0)
        self.assertAlmostEqual(production_link["contribution_share_of_child"], 0.1)
        self.assertAlmostEqual(production_link["allocation_share"], 0.1)
        self.assertEqual(
            production_link["allocation_basis"],
            "same_child_same_component_same_uom",
        )
        self.assertAlmostEqual(nodes["LOT-DC-A"]["contribution_qty"], 0.6)
        self.assertAlmostEqual(nodes["LOT-CUST"]["contribution_qty"], 0.6)
        self.assertAlmostEqual(mixed["visible_contribution_qty"], 0.6)
        self.assertAlmostEqual(mixed["other_contribution_qty"], 9.4)
        self.assertAlmostEqual(mixed["visible_share"], 0.06)

    def test_component_allocation_normalizes_zun_and_un(self) -> None:
        lots = {
            "LOT-A": self._lot(
                "LOT-A",
                0,
                "M-1",
                "item:COMP",
                10.0,
                "raw_material_opening",
            ),
            "LOT-B": self._lot(
                "LOT-B",
                0,
                "M-1",
                "item:COMP",
                30.0,
                "raw_material_opening",
            ),
            "LOT-PF": self._lot(
                "LOT-PF",
                1,
                "M-1",
                "item:PF",
                100.0,
                "finished_product",
            ),
        }
        lots["LOT-A"]["uom"] = "ZUN"
        lots["LOT-B"]["uom"] = "UN"
        events = [
            self._event("E-A", "LOT-A", 0, "M-1", "item:COMP", 10.0),
            self._event("E-B", "LOT-B", 0, "M-1", "item:COMP", 30.0),
            self._event("E-PF", "LOT-PF", 1, "M-1", "item:PF", 100.0),
        ]
        events[0]["uom"] = "ZUN"
        events[1]["uom"] = "UN"
        genealogy = [
            self._link(
                1,
                "production",
                "LOT-A",
                "M-1",
                "item:COMP",
                "LOT-PF",
                "M-1",
                "item:PF",
                10.0,
                100.0,
            ),
            self._link(
                1,
                "production",
                "LOT-B",
                "M-1",
                "item:COMP",
                "LOT-PF",
                "M-1",
                "item:PF",
                30.0,
                100.0,
            ),
        ]
        payload = {
            "available": True,
            "lots": lots,
            "events": events,
            "genealogy": genealogy,
            "plan_events": [],
            "lot_options": [lots["LOT-A"]],
            "deferred_orders": [],
            "stock_context": {},
            "summary": {"lot_count": len(lots)},
        }

        view = build_lot_trace_view_model(payload, "LOT-A")
        production_link = next(
            row
            for row in view["links"]
            if row["link_type"] == "production"
        )
        nodes = {row["lot_id"]: row for row in view["nodes"]}

        self.assertEqual(production_link["allocation_basis"], "same_child_same_component_same_uom")
        self.assertAlmostEqual(production_link["allocation_share"], 0.25)
        self.assertAlmostEqual(production_link["contribution_qty"], 25.0)
        self.assertAlmostEqual(nodes["LOT-PF"]["contribution_qty"], 25.0)

    def test_partial_component_contribution_follows_transport_delivery_loss(self) -> None:
        lots = {
            "LOT-A": self._lot("LOT-A", 0, "M-1", "item:RM", 10.0, "raw_material_opening"),
            "LOT-B": self._lot("LOT-B", 0, "M-1", "item:RM", 90.0, "raw_material_opening"),
            "LOT-PF": self._lot("LOT-PF", 1, "M-1", "item:PF", 100.0, "finished_product"),
            "LOT-DC": self._lot("LOT-DC", 3, "DC-1", "item:PF", 90.0, "finished_product_receipt"),
        }
        events = [
            self._event(f"E-{lot_id}", lot_id, lot["created_day"], lot["node_id"], lot["item_id"], lot["qty"])
            for lot_id, lot in lots.items()
        ]
        genealogy = [
            self._link(1, "production", "LOT-A", "M-1", "item:RM", "LOT-PF", "M-1", "item:PF", 10.0, 100.0),
            self._link(1, "production", "LOT-B", "M-1", "item:RM", "LOT-PF", "M-1", "item:PF", 90.0, 100.0),
            self._link(3, "transport", "LOT-PF", "M-1", "item:PF", "LOT-DC", "DC-1", "item:PF", 100.0, 90.0),
        ]
        payload = {
            "available": True,
            "lots": lots,
            "events": events,
            "genealogy": genealogy,
            "plan_events": [],
            "lot_options": [lots["LOT-A"]],
            "deferred_orders": [],
            "stock_context": {},
            "summary": {"lot_count": len(lots)},
        }

        view = build_lot_trace_view_model(payload, "LOT-A")
        nodes = {row["lot_id"]: row for row in view["nodes"]}

        self.assertAlmostEqual(nodes["LOT-PF"]["contribution_qty"], 10.0)
        self.assertAlmostEqual(nodes["LOT-DC"]["contribution_qty"], 9.0)

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

        self.assertEqual(view["summary"]["upstream_occurrence_count"], 8)
        self.assertEqual(view["summary"]["downstream_occurrence_count"], 12)
        self.assertLessEqual(
            view["summary"]["upstream_lot_count"],
            view["summary"]["upstream_occurrence_count"],
        )
        self.assertLessEqual(
            view["summary"]["downstream_lot_count"],
            view["summary"]["downstream_occurrence_count"],
        )
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
