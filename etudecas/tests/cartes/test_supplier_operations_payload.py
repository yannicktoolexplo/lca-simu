from __future__ import annotations

import unittest

from etudecas.visualization.maps.supplier_operations_payload import (
    build_unit_scoped_mrp_assets,
    consolidate_order_rows_weekly,
    effective_order_receipt_day,
    effective_procurement_lead_days,
    order_placed_day,
    planned_order_receipt_day,
    render_order_ledger_html,
    resolved_order_day,
)


class SupplierOperationsPayloadTest(unittest.TestCase):
    def test_effective_procurement_lead_uses_actual_receipt_when_available(self) -> None:
        row = {
            "order_date_imt": "10",
            "release_day": "12",
            "arrival_day": "18",
            "actual_receipt_day": "20",
        }

        self.assertEqual(effective_procurement_lead_days(row), 10.0)

    def test_consolidate_order_rows_weekly_groups_supplier_orders(self) -> None:
        rows = [
            {
                "dst_node_id": "M-1430",
                "src_node_id": "SDC-A",
                "item_id": "333362",
                "order_date_imt": "8",
                "release_day": "10",
                "arrival_day": "15",
                "planned_receipt_qty": "100",
                "release_qty": "80",
                "order_status_end_of_run": "received",
            },
            {
                "dst_node_id": "M-1430",
                "src_node_id": "SDC-A",
                "item_id": "333362",
                "order_date_imt": "9",
                "release_day": "11",
                "arrival_day": "16",
                "planned_receipt_qty": "50",
                "release_qty": "40",
                "order_status_end_of_run": "received",
            },
        ]

        grouped = consolidate_order_rows_weekly(rows)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["receipt_qty"], 150.0)
        self.assertEqual(grouped[0]["release_qty"], 120.0)
        self.assertEqual(grouped[0]["line_count"], 2)

    def test_render_order_ledger_empty_state_is_explicit(self) -> None:
        html = render_order_ledger_html("SDC-A", [], {}, empty_reason="hors horizon")

        self.assertIn("hors horizon", html)
        self.assertIn("Aucun ordre MRP", html)

    def test_explicit_milestones_keep_j0_decision_and_physical_receipt(self) -> None:
        row = dict(order_type="lane_release", day="4", order_decision_day="0",
                   order_date_imt="10", release_day="10", physical_delivery_day="18",
                   available_day="27", actual_physical_receipt_day="19", actual_available_day="28",
                   arrival_day="27", actual_receipt_day="28", lead_reference_days="56")
        self.assertEqual(order_placed_day(row), 0)
        self.assertEqual(resolved_order_day(row, "order_decision_day"), 0)
        self.assertEqual(planned_order_receipt_day(row), 18)
        self.assertEqual(effective_order_receipt_day(row), 19)
        self.assertEqual(effective_procurement_lead_days(row), 19)
        rendered = render_order_ledger_html("M", [row], {})
        self.assertIn("Décision MRP", rendered)
        self.assertIn("Réception physique simulée", rendered)
        self.assertIn("Disponibilité simulée", rendered)
        self.assertIn(">J19</td>", rendered)
        self.assertIn(">J28</td>", rendered)

    def test_opening_unknown_decision_is_not_loading_day_or_release(self) -> None:
        row = dict(order_type="opening_purchase_order", day="0", order_decision_day="",
                   order_date_imt="-10", release_day="-10", physical_delivery_day="0",
                   available_day="20", actual_physical_receipt_day="0", actual_available_day="20")
        self.assertIsNone(order_placed_day(row))
        self.assertIsNone(resolved_order_day(row, "order_decision_day"))
        self.assertIsNone(effective_procurement_lead_days(row))
        self.assertEqual(effective_order_receipt_day(row), 0)
        grouped = consolidate_order_rows_weekly([row])
        self.assertIsNone(grouped[0]["week_start"])
        self.assertIsNone(grouped[0]["order_min"])
        self.assertEqual(grouped[0]["release_min"], -10)

    def test_explicit_missing_physical_milestone_does_not_use_availability(self) -> None:
        row = dict(day="1", order_decision_day="1", release_day="3",
                   physical_delivery_day="", actual_physical_receipt_day="",
                   available_day="50", actual_available_day="50", arrival_day="50",
                   actual_receipt_day="50", lead_reference_days="7")
        self.assertIsNone(planned_order_receipt_day(row))
        self.assertIsNone(effective_order_receipt_day(row))
        self.assertIsNone(effective_procurement_lead_days(row))
        grouped = consolidate_order_rows_weekly([row])
        self.assertIsNone(grouped[0]["planned_arrival_min"])
        self.assertIsNone(grouped[0]["effective_arrival_min"])

    def test_chart_dates_known_decisions_without_inventing_opening_decision(self) -> None:
        raw = {"nodes": [{"id": "S", "inventory": {"states": [{"item_id": "RM", "uom": "UN"}]}}]}
        common = dict(item_id="RM", src_node_id="S", dst_node_id="M", day="0",
                      physical_delivery_day="14", available_day="21", actual_physical_receipt_day="14",
                      actual_available_day="21", release_day="10", order_date_imt="10")
        opening = dict(common, order_type="opening_purchase_order", order_decision_day="", release_qty="100", planned_receipt_qty="100")
        known = dict(common, order_type="lane_release", order_decision_day="0", release_qty="7", planned_receipt_qty="7")
        assets = build_unit_scoped_mrp_assets(raw, "S", trace_rows=[], order_rows=[opening, known],
            stock_rows=[], arrival_rows=[], shipment_rows=[], horizon_days=30)
        series = assets["supplier_order_send"]["figure"]["top"]["series"]
        decisions = next(row for row in series if row["label"] == "Décisions MRP connues")
        releases = next(row for row in series if row["label"] == "Expéditions prévues")
        self.assertEqual(sum(v or 0 for v in decisions["values"]), 7)
        self.assertEqual(sum(v or 0 for v in releases["values"]), 107)


if __name__ == "__main__":
    unittest.main()
