from __future__ import annotations

import unittest

from etudecas.simulation.lot_trace.procurement import (
    enrich_lot_trace_with_procurement,
    normalize_procurement_orders,
)
from etudecas.simulation.lot_trace.view_model import (
    build_lot_trace_view_model,
)


class LotTraceProcurementTest(unittest.TestCase):
    def test_matches_ship_receipt_and_transport_link_to_same_order(self) -> None:
        events = [
            {
                "event_id": "E-SHIP",
                "day": 3,
                "event_type": "lane_ship",
                "lot_id": "LOT-SOURCE",
                "node_id": "SDC-VD001",
                "item_id": "MP-1",
                "qty": 100.0,
                "source_id": "EDGE-1",
            },
            {
                "event_id": "E-RECEIPT",
                "day": 8,
                "event_type": "lane_receipt",
                "lot_id": "LOT-RECEIPT",
                "node_id": "M-1430",
                "item_id": "MP-1",
                "qty": 98.0,
                "source_id": "EDGE-1",
            },
        ]
        genealogy = [
            {
                "day": 8,
                "link_type": "transport",
                "parent_lot_id": "LOT-SOURCE",
                "parent_node_id": "SDC-VD001",
                "parent_item_id": "MP-1",
                "child_lot_id": "LOT-RECEIPT",
                "child_node_id": "M-1430",
                "child_item_id": "MP-1",
                "parent_qty": 100.0,
                "child_qty": 98.0,
                "source_id": "EDGE-1",
            }
        ]
        orders = [
            {
                "day": 1,
                "item_id": "MP-1",
                "src_node_id": "SDC-VD001",
                "dst_node_id": "M-1430",
                "edge_id": "EDGE-1",
                "order_date_imt": 1,
                "release_day": 3,
                "arrival_day": 8,
                "actual_receipt_day": 8,
                "lead_days": 5,
                "release_qty": 100,
                "planned_receipt_qty": 98,
                "order_status_end_of_run": "received",
            }
        ]

        result = enrich_lot_trace_with_procurement(events, genealogy, orders)

        order_id = result["orders"][0]["mrp_order_id"]
        self.assertTrue(order_id.startswith("MRPORD-"))
        self.assertEqual(events[0]["mrp_order_id"], order_id)
        self.assertEqual(events[1]["mrp_order_id"], order_id)
        self.assertEqual(genealogy[0]["mrp_order_id"], order_id)
        self.assertEqual(events[1]["supplier_node_id"], "SDC-VD001")
        self.assertEqual(events[1]["order_day"], 1)
        self.assertEqual(events[1]["mrp_decision_day"], 1)
        self.assertEqual(events[1]["requested_release_day"], 1)
        self.assertEqual(events[1]["actual_release_day"], 3)
        self.assertEqual(events[1]["planned_release_day"], 3)
        self.assertEqual(events[1]["actual_receipt_day"], 8)
        self.assertEqual(events[1]["procurement_lead_days"], 5)

    def test_matches_opening_receipt_without_lane_source(self) -> None:
        events = [
            {
                "event_id": "E-OPENING-RECEIPT",
                "day": 12,
                "event_type": "lane_receipt",
                "lot_id": "LOT-OPENING-RECEIPT",
                "node_id": "M-1430",
                "item_id": "038005",
                "qty": 10_000_000.0,
                "source_id": "",
            }
        ]
        orders = [
            {
                "day": 0,
                "item_id": "038005",
                "src_node_id": "SDC-VD0520132A",
                "dst_node_id": "M-1430",
                "edge_id": "EDGE-038005",
                "order_date_imt": -8,
                "release_day": -8,
                "arrival_day": 12,
                "actual_receipt_day": 12,
                "lead_days": 20,
                "release_qty": 10_000_000,
                "planned_receipt_qty": 10_000_000,
                "order_type": "opening_purchase_order",
            }
        ]

        enrich_lot_trace_with_procurement(events, [], orders)

        self.assertEqual(events[0]["supplier_node_id"], "SDC-VD0520132A")
        self.assertEqual(events[0]["order_day"], 0)
        self.assertEqual(events[0]["mrp_decision_day"], 0)
        self.assertEqual(events[0]["requested_release_day"], -8)
        self.assertEqual(events[0]["actual_release_day"], -8)
        self.assertEqual(events[0]["actual_receipt_day"], 12)
        self.assertEqual(
            events[0]["procurement_trace_status"],
            "mrp_order_matched",
        )

    def test_normalized_order_ids_are_stable_and_distinguish_duplicates(self) -> None:
        row = {
            "item_id": "MP-1",
            "src_node_id": "SUP",
            "dst_node_id": "FAC",
            "order_date_imt": 2,
            "release_day": 3,
            "arrival_day": 5,
            "release_qty": 10,
            "planned_receipt_qty": 10,
        }

        first = normalize_procurement_orders([row, row])
        second = normalize_procurement_orders([row, row])

        self.assertEqual(
            [order["mrp_order_id"] for order in first],
            [order["mrp_order_id"] for order in second],
        )
        self.assertNotEqual(
            first[0]["mrp_order_id"],
            first[1]["mrp_order_id"],
        )

    def test_infers_aggregate_supplier_timeline_from_lane_without_order(self) -> None:
        events = [
            {
                "event_id": "E-AGG",
                "day": 200,
                "event_type": "lane_receipt",
                "lot_id": "LOT-AGG",
                "node_id": "M-1430",
                "item_id": "item:038005",
                "qty": 2_694.8,
                "source_id": "edge:SUP_TO_M-1430_038005",
            }
        ]
        graph = {
            "edges": [
                {
                    "id": "edge:SUP_TO_M-1430_038005",
                    "from": "SDC-SUP",
                    "to": "M-1430",
                    "items": ["item:038005"],
                    "lead_time": {"mean": 20, "source": "supplier_data"},
                }
            ]
        }

        result = enrich_lot_trace_with_procurement(
            events,
            [],
            [],
            supply_graph=graph,
        )

        event = events[0]
        self.assertEqual(event["supplier_node_id"], "SDC-SUP")
        self.assertIsNone(event["planned_release_day"])
        self.assertEqual(event["estimated_release_day"], 180)
        self.assertIsNone(event["planned_arrival_day"])
        self.assertEqual(event["actual_receipt_day"], 200)
        self.assertIsNone(event["order_day"])
        self.assertEqual(
            event["procurement_trace_status"],
            "aggregate_replenishment_inferred_timeline",
        )
        self.assertEqual(
            result["summary"]["inferred_aggregate_receipt_count"],
            1,
        )

    def test_view_model_exposes_supplier_for_unparented_receipt(self) -> None:
        payload = {
            "lots": {
                "LOT-MP": {
                    "lot_id": "LOT-MP",
                    "node_id": "M-1430",
                    "item_id": "MP-1",
                    "qty": 100.0,
                    "uom": "KG",
                },
                "LOT-PF": {
                    "lot_id": "LOT-PF",
                    "node_id": "M-1430",
                    "item_id": "PF-1",
                    "qty": 10.0,
                    "uom": "UN",
                },
            },
            "events": [
                {
                    "event_id": "E-MP",
                    "day": 8,
                    "event_type": "lane_receipt",
                    "lot_id": "LOT-MP",
                    "node_id": "M-1430",
                    "item_id": "MP-1",
                    "qty": 100.0,
                    "uom": "KG",
                    "supplier_node_id": "SDC-VD001",
                    "mrp_order_id": "MRPORD-1",
                    "order_day": 1,
                    "planned_release_day": 3,
                    "planned_arrival_day": 8,
                    "actual_receipt_day": 8,
                    "procurement_lead_days": 5,
                    "procurement_status": "received",
                },
                {
                    "event_id": "E-PF",
                    "day": 9,
                    "event_type": "production_output",
                    "lot_id": "LOT-PF",
                    "node_id": "M-1430",
                    "item_id": "PF-1",
                    "qty": 10.0,
                    "uom": "UN",
                },
            ],
            "genealogy": [
                {
                    "day": 9,
                    "link_type": "production",
                    "parent_lot_id": "LOT-MP",
                    "parent_node_id": "M-1430",
                    "parent_item_id": "MP-1",
                    "child_lot_id": "LOT-PF",
                    "child_node_id": "M-1430",
                    "child_item_id": "PF-1",
                    "parent_qty": 100.0,
                    "child_qty": 10.0,
                }
            ],
        }

        view = build_lot_trace_view_model(payload, "LOT-PF", "upstream")

        self.assertEqual(len(view["transport_groups"]), 1)
        transport = view["transport_groups"][0]
        self.assertEqual(transport["group_type"], "untraced_receipt")
        self.assertEqual(transport["from_node_id"], "SDC-VD001")
        self.assertEqual(transport["to_node_id"], "M-1430")
        self.assertEqual(transport["mrp_order_id"], "MRPORD-1")
        self.assertEqual(transport["order_day"], 1)
        self.assertEqual(transport["actual_receipt_day"], 8)

    def test_order_quantity_cannot_be_allocated_more_than_once(self) -> None:
        events = [
            {
                "event_id": f"E-{index}",
                "day": 8,
                "event_type": "lane_receipt",
                "lot_id": f"LOT-{index}",
                "node_id": "M-1430",
                "item_id": "MP-1",
                "qty": 100.0,
                "source_id": "EDGE-1",
            }
            for index in range(3)
        ]
        base_order = {
            "day": 1,
            "item_id": "MP-1",
            "src_node_id": "SUP-1",
            "dst_node_id": "M-1430",
            "edge_id": "EDGE-1",
            "order_date_imt": 3,
            "release_day": 3,
            "arrival_day": 8,
            "actual_receipt_day": 8,
            "lead_days": 5,
            "release_qty": 100,
            "planned_receipt_qty": 100,
        }

        result = enrich_lot_trace_with_procurement(
            events,
            [],
            [base_order, base_order],
        )

        matched_ids = [
            event.get("mrp_order_id")
            for event in events
            if event.get("mrp_order_id")
        ]
        self.assertEqual(len(matched_ids), 2)
        self.assertEqual(len(set(matched_ids)), 2)
        self.assertEqual(
            events[2]["procurement_trace_status"],
            "receipt_without_matching_order",
        )
        self.assertEqual(result["summary"]["matched_lot_event_count"], 2)

    def test_incompatible_route_is_not_matched(self) -> None:
        event = {
            "event_id": "E-WRONG-ROUTE",
            "day": 8,
            "event_type": "lane_receipt",
            "lot_id": "LOT-WRONG-ROUTE",
            "node_id": "M-1430",
            "item_id": "MP-1",
            "qty": 100.0,
            "source_id": "EDGE-B",
        }
        order = {
            "day": 1,
            "item_id": "MP-1",
            "src_node_id": "SUP-A",
            "dst_node_id": "M-1430",
            "edge_id": "EDGE-A",
            "order_date_imt": 3,
            "release_day": 3,
            "arrival_day": 8,
            "actual_receipt_day": 8,
            "lead_days": 5,
            "release_qty": 100,
            "planned_receipt_qty": 100,
        }

        enrich_lot_trace_with_procurement([event], [], [order])

        self.assertNotIn("mrp_order_id", event)
        self.assertEqual(
            event["procurement_trace_status"],
            "receipt_without_matching_order",
        )

    def test_zero_quantity_transport_link_can_be_inspected_without_crashing(self) -> None:
        event = {
            "event_id": "E-ZERO",
            "day": 8,
            "event_type": "lane_receipt",
            "lot_id": "LOT-ZERO",
            "node_id": "M-1430",
            "item_id": "MP-1",
            "qty": 0.0,
            "source_id": "EDGE-1",
        }
        genealogy = [
            {
                "day": 8,
                "link_type": "transport",
                "parent_lot_id": "LOT-SOURCE",
                "parent_node_id": "SUP-1",
                "parent_item_id": "MP-1",
                "child_lot_id": "LOT-ZERO",
                "child_node_id": "M-1430",
                "child_item_id": "MP-1",
                "parent_qty": 0.0,
                "child_qty": 0.0,
                "source_id": "EDGE-1",
            }
        ]
        order = {
            "day": 1,
            "item_id": "MP-1",
            "src_node_id": "SUP-1",
            "dst_node_id": "M-1430",
            "edge_id": "EDGE-1",
            "release_day": 3,
            "arrival_day": 8,
            "actual_receipt_day": 8,
            "release_qty": 0.0,
            "planned_receipt_qty": 0.0,
        }

        result = enrich_lot_trace_with_procurement([event], genealogy, [order])

        self.assertEqual(result["summary"]["matched_transport_link_count"], 1)
        self.assertTrue(genealogy[0]["mrp_order_id"].startswith("MRPORD-"))


if __name__ == "__main__":
    unittest.main()
