from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.lot_trace import (
    LOT_TRACE_CAMPAIGN_FIELDS,
    LOT_TRACE_EVENT_FIELDS,
    LOT_TRACE_GENEALOGY_FIELDS,
    LOT_TRACE_PLAN_EVENT_FIELDS,
    build_lot_trace_payload,
    build_lot_trace_view_model,
)
from etudecas.simulation.lot_trace.labels import (
    event_type_label,
    format_quantity,
    node_business_label,
)


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

PLAN_FIELDS = [
    "day",
    "campaign_id",
    "node_id",
    "output_item_id",
    "event_type",
    "reason",
    "desired_qty",
    "planned_qty_after_lot_rule",
    "actual_qty",
    "shortfall_vs_desired_qty",
    "shortfall_vs_lot_plan_qty",
    "binding_input_item_id",
    "planned_qty_before",
    "planned_qty_after",
    "campaign_remaining_start_qty",
    "campaign_remaining_end_qty",
    "next_expected_receipt_day",
    "notes",
]


class LotTracePayloadTest(unittest.TestCase):
    def test_payload_keeps_business_lots_and_excludes_transport_receipts(self) -> None:
        payload = self._build_payload()

        self.assertTrue(payload["available"])
        self.assertEqual(payload["default_lot"], "LOT-PF")
        self.assertEqual(payload["summary"]["selectable_filter"], "business_lots_pf_pfi_mp_no_transport_receipts")
        self.assertEqual(payload["summary"]["physical_lot_policy"], "select_business_lots_contextual_transport_receipts")
        self.assertIn("selectable_scope_counts", payload["summary"])
        self.assertGreater(payload["summary"]["selectable_scope_counts"].get("finished_product", 0), 0)
        self.assertIn("config", payload)

        option_ids = {row["lot_id"] for row in payload["lot_options"]}
        self.assertIn("LOT-PF", option_ids)
        self.assertIn("LOT-RM-S", option_ids)
        self.assertNotIn("LOT-RM-F", option_ids)
        self.assertNotIn("LOT-DC", option_ids)
        self.assertNotIn("LOT-CUST", option_ids)

        self.assertEqual(payload["lots"]["LOT-PF"]["trace_scope"], "finished_product")
        self.assertEqual(payload["lots"]["LOT-RM-S"]["trace_scope"], "raw_material_opening")
        self.assertGreater(payload["lots"]["LOT-PF"]["upstream_lot_count"], 0)
        self.assertGreater(payload["lots"]["LOT-RM-S"]["downstream_lot_count"], 0)
        self.assertNotIn("production_output", payload["lots"]["LOT-PF"]["label"])
        self.assertNotIn("amont", payload["lots"]["LOT-PF"]["label"])
        self.assertIn("Production terminée J3", payload["lots"]["LOT-PF"]["label"])
        self.assertIn("10 UN", payload["lots"]["LOT-PF"]["label"])
        self.assertEqual(
            payload["lots"]["LOT-PF"]["trace_counts"],
            {"upstream_lots": 2, "downstream_lots": 2},
        )
        self.assertEqual(payload["lots"]["LOT-PF"]["business_lot_id"], "LOT-PF")
        self.assertEqual(payload["lots"]["LOT-DC"]["business_lot_id"], "LOT-PF")
        self.assertEqual(payload["lots"]["LOT-DC"]["stock_occurrence_id"], "LOT-DC")
        self.assertEqual(payload["lots"]["LOT-DC"]["shipment_id"], "")
        self.assertEqual(payload["lots"]["LOT-DC"]["shipment_identity_status"], "not_available_legacy")
        self.assertEqual(payload["lots"]["LOT-ORPHAN"]["origin_trace_status"], "untraced_transport_origin")
        self.assertIn("Origine non tracée", payload["lots"]["LOT-ORPHAN"]["origin_trace_label"])
        self.assertEqual(payload["summary"]["untraced_transport_receipt_count"], 1)

    def test_payload_contract_keeps_js_consumed_keys_and_fields(self) -> None:
        payload = self._build_payload()

        for key in [
            "available",
            "default_lot",
            "config",
            "lots",
            "lot_options",
            "events",
            "genealogy",
            "plan_events",
            "campaigns",
            "deferred_orders",
            "stock_context",
            "nomenclature",
            "default_view_model",
            "summary",
        ]:
            self.assertIn(key, payload)

        self.assertEqual(list(payload["events"][0].keys()), LOT_TRACE_EVENT_FIELDS)
        self.assertEqual(list(payload["genealogy"][0].keys()), LOT_TRACE_GENEALOGY_FIELDS)
        self.assertEqual(payload["plan_events"], [])
        self.assertEqual(payload["campaigns"], [])
        self.assertIn("next_expected_receipt_day", LOT_TRACE_PLAN_EVENT_FIELDS)
        self.assertEqual(payload["default_view_model"]["version"], 1)
        self.assertEqual(payload["default_view_model"]["lot_id"], payload["default_lot"])
        self.assertEqual(payload["summary"]["default_view_model_lot"], payload["default_lot"])
        self.assertIn("deferred_order_completed_count", payload["summary"])
        self.assertIn("deferred_order_blocked_count", payload["summary"])
        self.assertEqual(
            payload["nomenclature"]["event_type_labels"]["lane_receipt"],
            "Réception logistique simulée",
        )

    def test_business_labels_are_french_and_keep_units_visible(self) -> None:
        self.assertEqual(event_type_label("production_output"), "Production terminée")
        self.assertEqual(event_type_label("unknown_internal_code"), "Événement métier non référencé")
        self.assertEqual(node_business_label("SDC-1450"), "Site PFI interne D1450")
        self.assertEqual(format_quantity(12.5, "KG"), "12,5 KG")
        self.assertIn("unité non renseignée", format_quantity(12.5, ""))

    def test_payload_accepts_explicit_identity_fields_from_newer_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "events.csv"
            genealogy_path = root / "genealogy.csv"
            plan_path = root / "plan.csv"
            events = self._events()
            for event in events:
                if event["lot_id"] == "LOT-DC" and event["event_type"] == "lane_receipt":
                    event["business_lot_id"] = "BATCH-PF-001"
                    event["stock_occurrence_id"] = "OCC-DC-001"
                    event["shipment_id"] = "SHIP-001"
            self._write_csv(
                events_path,
                [*EVENT_FIELDS, "business_lot_id", "stock_occurrence_id", "shipment_id"],
                events,
            )
            self._write_csv(genealogy_path, GENEALOGY_FIELDS, self._genealogy())
            self._write_csv(plan_path, PLAN_FIELDS, [])

            payload = build_lot_trace_payload(
                events_path,
                genealogy_path,
                plan_path,
                raw=self._raw_graph(),
            )

        dc_lot = payload["lots"]["LOT-DC"]
        self.assertEqual(dc_lot["business_lot_id"], "BATCH-PF-001")
        self.assertEqual(dc_lot["stock_occurrence_id"], "OCC-DC-001")
        self.assertEqual(dc_lot["shipment_id"], "SHIP-001")
        self.assertEqual(dc_lot["shipment_identity_status"], "identified")
        self.assertIn("Lot métier BATCH-PF-001", dc_lot["label"])
        self.assertNotIn("Lot métier LOT-DC", dc_lot["label"])

    def test_deferred_campaign_is_not_a_physical_lot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "events.csv"
            genealogy_path = root / "genealogy.csv"
            plan_path = root / "plan.csv"
            campaign_path = root / "campaigns.csv"
            self._write_csv(events_path, EVENT_FIELDS, [])
            self._write_csv(genealogy_path, GENEALOGY_FIELDS, [])
            self._write_csv(plan_path, PLAN_FIELDS, [])
            self._write_csv(
                campaign_path,
                LOT_TRACE_CAMPAIGN_FIELDS,
                [
                    {
                        "campaign_id": "CMP-1",
                        "record_type": "campaign",
                        "node_id": "M-1",
                        "output_item_id": "item:PF",
                        "status": "completed_after_delay",
                        "status_label": "Produit apres report",
                        "first_event_day": 3,
                        "first_delay_day": 3,
                        "last_delay_day": 5,
                        "completed_day": 6,
                        "delay_event_count": 3,
                        "delay_day_count": 3,
                        "delay_span_days": 3,
                        "event_count": 4,
                        "planned_qty": 107800.0,
                        "actual_qty": 107800.0,
                        "completed_lot_ids": "LOT-PF",
                        "completed_lot_qty": 107800.0,
                        "blocked_lot_qty": 107800.0,
                        "max_daily_shortfall_qty": 107800.0,
                        "repeated_daily_shortfall_qty": 323400.0,
                        "delay_reasons": "input_shortage",
                        "binding_input_item_ids": "item:RM",
                        "next_expected_receipt_days": "6",
                        "first_event_type": "delay_input_shortage",
                        "last_event_type": "run_campaign_complete",
                        "notes": "",
                    }
                ],
            )

            payload = build_lot_trace_payload(
                events_path,
                genealogy_path,
                plan_path,
                raw=self._raw_graph(),
                production_campaigns_csv=campaign_path,
            )

        self.assertFalse(payload["available"])
        self.assertEqual(payload["lots"], {})
        self.assertEqual(payload["lot_options"], [])
        self.assertEqual(len(payload["campaigns"]), 1)
        self.assertEqual(len(payload["deferred_orders"]), 1)
        order = payload["deferred_orders"][0]
        self.assertEqual(order["entity_type"], "deferred_production_order")
        self.assertEqual(order["selection_id"], "order:CMP-1")
        self.assertEqual(order["completed_lot_id"], "LOT-PF")
        self.assertEqual(order["blocking_input_item_ids"], ["item:RM"])
        self.assertAlmostEqual(order["blocked_lot_qty"], 107800.0)
        self.assertAlmostEqual(order["repeated_daily_shortfall_qty"], 323400.0)

    def test_finished_product_filter_is_explicit_option(self) -> None:
        payload = self._build_payload(visible_finished_product_items=["item:OTHER"])

        option_ids = {row["lot_id"] for row in payload["lot_options"]}
        self.assertNotIn("LOT-PF", option_ids)
        self.assertIn("LOT-RM-S", option_ids)
        self.assertEqual(payload["summary"]["selectable_finished_product_items"], ["item:OTHER"])

    def test_view_model_propagates_material_contribution_through_production(self) -> None:
        payload = self._build_payload()

        model = build_lot_trace_view_model(payload, "LOT-RM-S", direction="downstream")

        nodes_by_lot = {row["lot_id"]: row for row in model["nodes"]}
        links_by_child = {row["child_lot_id"]: row for row in model["links"]}

        self.assertAlmostEqual(nodes_by_lot["LOT-RM-S"]["contribution_qty"], 100.0)
        self.assertEqual(nodes_by_lot["LOT-RM-S"]["contribution_basis"], "selected_lot_total_qty")
        self.assertAlmostEqual(nodes_by_lot["LOT-PF"]["contribution_qty"], 10.0)
        self.assertEqual(
            nodes_by_lot["LOT-PF"]["contribution_basis"],
            "production_same_component_consumption_share",
        )
        self.assertAlmostEqual(nodes_by_lot["LOT-CUST"]["contribution_qty"], 10.0)
        self.assertEqual(
            nodes_by_lot["LOT-CUST"]["contribution_basis"],
            "transport_received_quantity_share",
        )
        self.assertEqual(
            links_by_child["LOT-PF"]["contribution_basis"],
            "production_same_component_consumption_share",
        )
        self.assertAlmostEqual(links_by_child["LOT-CUST"]["contribution_qty"], 10.0)

    @unittest.skipUnless(
        os.environ.get("ETUDECAS_RUN_SLOW_TESTS") == "1",
        "set ETUDECAS_RUN_SLOW_TESTS=1 to validate the 5-year lot payload",
    )
    def test_real_payload_lot_00000095_invariants(self) -> None:
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
        lot = payload["lots"]["LOT-00000095"]

        self.assertEqual(payload["default_lot"], "LOT-00000095")
        self.assertEqual(lot["trace_scope"], "finished_product")
        self.assertEqual(lot["created_day"], 0)
        self.assertEqual(lot["node_id"], "M-1430")
        self.assertEqual(lot["item_id"], "item:268967")
        self.assertAlmostEqual(lot["qty"], 107800.0)
        self.assertEqual(lot["upstream_lot_count"], 8)
        self.assertEqual(lot["downstream_lot_count"], 12)

        production_inputs = [
            row
            for row in payload["genealogy"]
            if row["link_type"] == "production" and row["child_lot_id"] == "LOT-00000095"
        ]
        self.assertEqual(len(production_inputs), 8)
        qty_by_item = {row["parent_item_id"]: row["parent_qty"] for row in production_inputs}
        self.assertAlmostEqual(qty_by_item["item:038005"], 1886.411173, places=5)
        self.assertAlmostEqual(qty_by_item["item:042342"], 6504867.6, places=3)
        self.assertAlmostEqual(qty_by_item["item:333362"], 107800.0)
        self.assertAlmostEqual(qty_by_item["item:773474"], 1040778.6004, places=3)

        factory_to_dc = [
            row
            for row in payload["genealogy"]
            if row["link_type"] == "transport"
            and row["parent_lot_id"] == "LOT-00000095"
            and row["child_node_id"] == "DC-1920"
        ]
        self.assertEqual(len(factory_to_dc), 2)
        self.assertAlmostEqual(sum(row["child_qty"] for row in factory_to_dc), 107800.0, places=4)

    def test_payload_can_keep_causal_registry_external_to_the_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "events.csv"
            genealogy_path = root / "genealogy.csv"
            plan_path = root / "plan.csv"
            causal_path = root / "lot_causal_links.csv"
            self._write_csv(events_path, EVENT_FIELDS, self._events())
            self._write_csv(genealogy_path, GENEALOGY_FIELDS, self._genealogy())
            self._write_csv(plan_path, PLAN_FIELDS, [])
            self._write_csv(
                causal_path,
                [
                    "causal_root_id",
                    "relation_type",
                    "entity_type",
                    "entity_id",
                    "basis",
                ],
                [
                    {
                        "causal_root_id": "RISK-1",
                        "relation_type": "risk_affects_business_lot",
                        "entity_type": "business_lot",
                        "entity_id": "LOT-PF",
                        "basis": "state-dependent",
                    }
                ],
            )

            payload = build_lot_trace_payload(
                events_path,
                genealogy_path,
                plan_path,
                raw=self._raw_graph(),
                lot_causal_links_csv=causal_path,
                include_causal_links=False,
            )

        self.assertEqual(payload["causal_links"], [])
        self.assertEqual(payload["summary"]["causal_link_count"], 1)
        self.assertEqual(payload["summary"]["causal_link_rows_embedded"], 0)

    def _build_payload(self, visible_finished_product_items: list[str] | None = None) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "events.csv"
            genealogy_path = root / "genealogy.csv"
            plan_path = root / "plan.csv"
            self._write_csv(events_path, EVENT_FIELDS, self._events())
            self._write_csv(genealogy_path, GENEALOGY_FIELDS, self._genealogy())
            self._write_csv(plan_path, PLAN_FIELDS, [])

            payload = build_lot_trace_payload(
                events_path,
                genealogy_path,
                plan_path,
                raw=self._raw_graph(),
                visible_finished_product_items=visible_finished_product_items,
            )
        return payload

    def _raw_graph(self) -> dict[str, object]:
        return {
            "nodes": [
                {"id": "S-RAW", "type": "supplier_dc"},
                {
                    "id": "M-1",
                    "type": "factory",
                    "processes": [
                        {
                            "inputs": [{"item_id": "item:RM"}],
                            "outputs": [{"item_id": "item:PF"}],
                        }
                    ],
                },
                {"id": "DC-1", "type": "distribution_center"},
                {"id": "C-1", "type": "customer"},
            ],
            "edges": [
                {"from": "S-RAW", "to": "M-1", "items": ["item:RM"]},
                {"from": "M-1", "to": "DC-1", "items": ["item:PF"]},
                {"from": "DC-1", "to": "C-1", "items": ["item:PF"]},
            ],
        }

    def _events(self) -> list[dict[str, object]]:
        return [
            self._event("E1", 0, "opening_stock", "LOT-RM-S", "S-RAW", "item:RM", 100.0, 100.0, "seed"),
            self._event("E2", 1, "lane_ship", "LOT-RM-S", "S-RAW", "item:RM", 100.0, 0.0, "edge:S-RAW_TO_M-1_RM"),
            self._event("E3", 2, "lane_receipt", "LOT-RM-F", "M-1", "item:RM", 100.0, 100.0, "edge:S-RAW_TO_M-1_RM"),
            self._event("E4", 3, "production_consume", "LOT-RM-F", "M-1", "item:RM", 100.0, 0.0, "M-1|item:PF"),
            self._event("E5", 3, "production_output", "LOT-PF", "M-1", "item:PF", 10.0, 10.0, "M-1|item:PF", "CMP-1"),
            self._event("E6", 4, "lane_ship", "LOT-PF", "M-1", "item:PF", 10.0, 0.0, "edge:M-1_TO_DC-1_PF"),
            self._event("E7", 5, "lane_receipt", "LOT-DC", "DC-1", "item:PF", 10.0, 10.0, "edge:M-1_TO_DC-1_PF"),
            self._event("E8", 6, "lane_ship", "LOT-DC", "DC-1", "item:PF", 10.0, 0.0, "edge:DC-1_TO_C-1_PF"),
            self._event("E9", 7, "lane_receipt", "LOT-CUST", "C-1", "item:PF", 10.0, 10.0, "edge:DC-1_TO_C-1_PF"),
            self._event("E10", 8, "demand_service", "LOT-CUST", "C-1", "item:PF", 10.0, 0.0, "customer_demand"),
            self._event("E11", 9, "lane_receipt", "LOT-ORPHAN", "M-1", "item:RM", 5.0, 5.0, "edge:UNKNOWN"),
        ]

    def _genealogy(self) -> list[dict[str, object]]:
        return [
            self._link(2, "transport", "LOT-RM-S", "S-RAW", "item:RM", "LOT-RM-F", "M-1", "item:RM", 100.0, 100.0, "edge:S-RAW_TO_M-1_RM"),
            self._link(3, "production", "LOT-RM-F", "M-1", "item:RM", "LOT-PF", "M-1", "item:PF", 100.0, 10.0, "M-1|item:PF", "CMP-1"),
            self._link(5, "transport", "LOT-PF", "M-1", "item:PF", "LOT-DC", "DC-1", "item:PF", 10.0, 10.0, "edge:M-1_TO_DC-1_PF"),
            self._link(7, "transport", "LOT-DC", "DC-1", "item:PF", "LOT-CUST", "C-1", "item:PF", 10.0, 10.0, "edge:DC-1_TO_C-1_PF"),
        ]

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
        source_id: str,
        campaign_id: str = "",
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
            "uom": "UN",
            "source_type": event_type,
            "source_id": source_id,
            "related_lot_id": "",
            "production_campaign_id": campaign_id,
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
        source_id: str,
        campaign_id: str = "",
    ) -> dict[str, object]:
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
            "allocation_share": 1.0,
            "source_id": source_id,
            "production_campaign_id": campaign_id,
            "notes": "",
        }

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
