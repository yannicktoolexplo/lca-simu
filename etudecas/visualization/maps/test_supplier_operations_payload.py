from __future__ import annotations

import unittest

from etudecas.visualization.maps.supplier_operations_payload import (
    consolidate_order_rows_weekly,
    effective_procurement_lead_days,
    render_order_ledger_html,
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


if __name__ == "__main__":
    unittest.main()
