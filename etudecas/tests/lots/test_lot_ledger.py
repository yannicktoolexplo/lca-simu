"""Regression tests for lot ledger."""

from __future__ import annotations
import unittest
import csv
import json
import subprocess
import sys
import tempfile
from etudecas.simulation.engine.run_first_simulation import LotLedger
from pathlib import Path


# Test lot ledger


class OpeningPackPathAuditMemoryTest(unittest.TestCase):
    """Literal ledger oracles only; no temporary files, subprocess or fixture IO."""

    @staticmethod
    def _rows():
        events = [dict(event_type="opening_stock", lot_id="PACK", node_id="F-1", item_id="tube",
                       day=-1, qty=100, uom="UN", source_id="opening")]
        links = []
        # Two conditioning fragments share the same parent and day, not identity.
        for ordinal, pack, pf in [(1, 20, 100), (2, 30, 150)]:
            fragment = f"OF:1;pack_fragment={ordinal}"
            notes = json.dumps(dict(opening_pack_policy="pack_at_source_G_v1", non_pack_materials="initial_WIP_untraced"))
            events.extend([
                dict(event_type="production_consume", lot_id="PACK", node_id="F-1", item_id="tube",
                     day=0, qty=pack, uom="UN", source_id=fragment, production_campaign_id=""),
                dict(event_type="opening_production_order", lot_id=f"PF{ordinal}", node_id="F-1", item_id="PF",
                     day=0, qty=pf, uom="UN", source_id=fragment, production_campaign_id="", notes=notes),
            ])
            links.append(dict(link_type="production", day=0, parent_lot_id="PACK", parent_node_id="F-1",
                parent_item_id="tube", parent_qty=pack, child_lot_id=f"PF{ordinal}", child_node_id="F-1",
                child_item_id="PF", child_qty=pf, source_id=fragment, production_campaign_id="", notes=notes))
        return events, links

    @staticmethod
    def _audit(events, links):
        from etudecas.simulation.analysis.audit_lot_paths import audit_opening_pack_fragments
        return audit_opening_pack_fragments(events, links)

    def test_two_fragments_same_day_parent_reconcile_separately_in_memory(self):
        events, links = self._rows()
        result = self._audit(events, links)
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["fragment_ids"], {"OF:1;pack_fragment=1", "OF:1;pack_fragment=2"})
        self.assertEqual(result["link_indices"], {0, 1})

    def test_missing_debit_and_missing_link_are_rejected_in_memory(self):
        events, links = self._rows()
        without_debit = [row for row in events if not (row.get("event_type") == "production_consume"
                                                      and row.get("source_id") == "OF:1;pack_fragment=1")]
        self.assertIn("production_link_missing_consume_event", {i["kind"] for i in self._audit(without_debit, links)["issues"]})
        self.assertIn("opening_pack_consume_missing_genealogy", {i["kind"] for i in self._audit(events, links[1:])["issues"]})

    def test_missing_output_and_crossed_fragment_are_rejected_in_memory(self):
        events, links = self._rows()
        without_output = [r for r in events if r.get("lot_id") != "PF1"]
        self.assertIn("production_link_missing_output_event", {i["kind"] for i in self._audit(without_output, links)["issues"]})
        links[0]["source_id"] = "OF:1;pack_fragment=2"
        kinds = {i["kind"] for i in self._audit(events, links)["issues"]}
        self.assertIn("production_link_missing_output_event", kinds)
        self.assertIn("production_link_consume_qty_mismatch", kinds)

    def test_duplicated_parent_link_or_creation_is_rejected_in_memory(self):
        events, links = self._rows()
        result = self._audit(events, links + [dict(links[0])])
        self.assertIn("production_link_consume_qty_mismatch", {i["kind"] for i in result["issues"]})
        result = self._audit(events + [dict(events[2])], links)
        self.assertIn("opening_pack_duplicate_output", {i["kind"] for i in result["issues"]})

    def test_UN_quantities_are_exact_even_at_large_scale_in_memory(self):
        events, links = self._rows()
        events[2]["qty"] = 100_000_000
        links[0]["child_qty"] = 100_000_001
        self.assertIn("production_link_output_qty_mismatch", {i["kind"] for i in self._audit(events, links)["issues"]})
        links[0]["child_qty"] = events[2]["qty"]
        links[0]["parent_qty"] = "20.000001"
        self.assertIn("opening_pack_invalid_quantity", {i["kind"] for i in self._audit(events, links)["issues"]})

    def test_absent_output_and_links_cannot_hide_orphan_fragment_debit_in_memory(self):
        events, links = self._rows()
        events = [r for r in events if r.get("event_type") != "opening_production_order"]
        result = self._audit(events, [])
        self.assertEqual(sum(i["kind"] == "opening_pack_consume_missing_genealogy" for i in result["issues"]), 2)

    def test_legacy_campaign_is_not_reclassified_as_opening_pack_in_memory(self):
        events = [dict(event_type="production_consume", lot_id="PACK", day=1, qty=20,
                       node_id="F-1", item_id="tube", uom="UN", source_id="F-1|PF", production_campaign_id="CMP")]
        links = [dict(link_type="production", parent_lot_id="PACK", child_lot_id="PF",
                      source_id="F-1|PF", production_campaign_id="CMP", notes="semantics=campaign-batch-wip-release-v1")]
        result = self._audit(events, links)
        self.assertEqual(result, dict(issues=[], fragment_ids=set(), link_indices=set(), output_lots=set()))

    def test_untraced_initial_material_limit_is_required_in_memory(self):
        events, links = self._rows()
        events[2]["notes"] = json.dumps(dict(opening_pack_policy="pack_at_source_G_v1"))
        self.assertIn("opening_pack_missing_provenance", {i["kind"] for i in self._audit(events, links)["issues"]})

class LotLedgerTest(unittest.TestCase):
    def test_closed_campaign_rejects_unlinked_consumption_in_memory(self) -> None:
        from etudecas.testing.independent_review import Evidence, audit_production_consumption
        evidence = Evidence()
        audit_production_consumption(
            {("pack", "closed"): 28801.0},
            {("pack", "closed"): 28879.0, ("missing", "closed"): 1.0},
            {"closed"}, evidence,
        )
        self.assertEqual(evidence.checks["closed_campaign_material_genealogy"]["failed"], 2)

    def test_open_campaign_keeps_wip_but_cannot_overlink_in_memory(self) -> None:
        from etudecas.testing.independent_review import Evidence, audit_production_consumption
        evidence = Evidence()
        audit_production_consumption(
            {("pack", "open"): 10.0}, {("pack", "open"): 15.0}, set(), evidence,
        )
        self.assertEqual(evidence.checks["genealogy_consumption_within_recorded"]["failed"], 0)
        audit_production_consumption(
            {("pack", "open"): 16.0}, {("pack", "open"): 15.0}, set(), evidence,
        )
        self.assertEqual(evidence.checks["genealogy_consumption_within_recorded"]["failed"], 1)

    def test_closed_campaign_accepts_conserved_material_in_memory(self) -> None:
        from etudecas.testing.independent_review import Evidence, audit_production_consumption
        evidence = Evidence()
        quantities = {("pack", "closed"): 28801.0, ("raw", "closed"): 12.375}
        audit_production_consumption(quantities, quantities, {"closed"}, evidence)
        self.assertEqual(evidence.checks["closed_campaign_material_genealogy"]["failed"], 0)

    def test_fifo_consumption_and_production_genealogy(self) -> None:
        ledger = LotLedger(enabled=True)
        ledger.create_lot(
            day=0,
            node_id="M-1",
            item_id="RM-1",
            qty=10.0,
            source_type="opening_stock",
            source_id="seed",
            uom="KG",
        )
        ledger.create_lot(
            day=1,
            node_id="M-1",
            item_id="RM-1",
            qty=5.0,
            source_type="lane_receipt",
            source_id="edge-1",
            uom="KG",
        )

        allocations = ledger.consume(
            day=2,
            node_id="M-1",
            item_id="RM-1",
            qty=12.0,
            event_type="production_consume",
            source_id="M-1|FG-1",
            production_campaign_id="CMP-1",
            uom="KG",
        )
        output_lot = ledger.create_child_lot(
            day=2,
            node_id="M-1",
            item_id="FG-1",
            qty=3.0,
            source_type="production_output",
            source_id="M-1|FG-1",
            parent_allocations=allocations,
            link_type="production",
            uom="UN",
            production_campaign_id="CMP-1",
        )

        self.assertEqual(len(allocations), 2)
        self.assertAlmostEqual(allocations[0]["qty"], 10.0)
        self.assertAlmostEqual(allocations[1]["qty"], 2.0)
        self.assertTrue(output_lot)
        self.assertEqual(len(ledger.genealogy_rows), 2)
        self.assertEqual({row["child_lot_id"] for row in ledger.genealogy_rows}, {output_lot})
        self.assertEqual({row["link_type"] for row in ledger.genealogy_rows}, {"production"})
        self.assertAlmostEqual(sum(row["parent_qty"] for row in ledger.genealogy_rows), 12.0)

    def test_mixed_batch_provenance_survives_two_transports(self) -> None:
        ledger = LotLedger(enabled=True)
        ledger.create_lot(
            day=0,
            node_id="S-1",
            item_id="RM-1",
            qty=4.0,
            source_type="opening_stock",
            source_id="seed-a",
            uom="UN",
            business_batch_id="BATCH-A",
        )
        ledger.create_lot(
            day=0,
            node_id="S-1",
            item_id="RM-1",
            qty=6.0,
            source_type="opening_stock",
            source_id="seed-b",
            uom="UN",
            business_batch_id="BATCH-B",
        )

        first_allocations = ledger.consume(
            day=1,
            node_id="S-1",
            item_id="RM-1",
            qty=10.0,
            event_type="lane_ship",
            source_id="S-1->M-1",
            uom="UN",
        )
        first_receipt = ledger.create_child_lot(
            day=2,
            node_id="M-1",
            item_id="RM-1",
            qty=10.0,
            source_type="lane_receipt",
            source_id="S-1->M-1",
            parent_allocations=first_allocations,
            link_type="transport",
            uom="UN",
            shipment_id="SHIP-1",
        )

        second_allocations = ledger.consume(
            day=3,
            node_id="M-1",
            item_id="RM-1",
            qty=10.0,
            event_type="lane_ship",
            source_id="M-1->DC-1",
            uom="UN",
        )
        second_receipt = ledger.create_child_lot(
            day=4,
            node_id="DC-1",
            item_id="RM-1",
            qty=10.0,
            source_type="lane_receipt",
            source_id="M-1->DC-1",
            parent_allocations=second_allocations,
            link_type="transport",
            uom="UN",
            shipment_id="SHIP-2",
        )

        for lot_id in (first_receipt, second_receipt):
            lot = ledger.lots[lot_id]
            self.assertEqual(lot["business_batch_id"], "")
            self.assertEqual(lot["provenance_batch_id"], "BATCH-A|BATCH-B")
            self.assertEqual(lot["trace_status"], "mixed_batch_occurrence")
            self.assertEqual(
                lot["trace_reason"],
                "consolidated_receipt_multiple_business_batches",
            )

        second_links = [
            row
            for row in ledger.genealogy_rows
            if row["child_lot_id"] == second_receipt
        ]
        self.assertEqual(len(second_links), 1)
        self.assertEqual(second_links[0]["provenance_batch_id"], "BATCH-A|BATCH-B")

    def test_untraced_lot_does_not_invent_business_batch(self) -> None:
        ledger = LotLedger(enabled=True)

        lot_id = ledger.create_lot(
            day=5,
            node_id="M-1",
            item_id="RM-1",
            qty=7.0,
            source_type="ledger_reconciliation",
            source_id="aggregate-stock",
            uom="KG",
            trace_status="untraced_origin",
            trace_reason="aggregate_stock_without_lot_detail",
        )

        lot = ledger.lots[lot_id]
        creation_event = next(
            row
            for row in ledger.event_rows
            if row["lot_id"] == lot_id
        )
        self.assertEqual(lot["business_batch_id"], "")
        self.assertEqual(creation_event["business_batch_id"], "")
        self.assertTrue(lot["lot_occurrence_id"].startswith("LOCC-"))
        self.assertEqual(lot["trace_status"], "untraced_origin")
        self.assertEqual(
            lot["trace_reason"],
            "aggregate_stock_without_lot_detail",
        )

    def test_produced_batch_keeps_its_identity_when_component_provenance_is_mixed(self) -> None:
        ledger = LotLedger(enabled=True)
        rm_a = ledger.create_lot(
            day=0,
            node_id="M-1",
            item_id="RM-1",
            qty=4.0,
            source_type="opening_stock",
            business_batch_id="RM-A",
            uom="KG",
        )
        rm_b = ledger.create_lot(
            day=0,
            node_id="M-1",
            item_id="RM-1",
            qty=6.0,
            source_type="opening_stock",
            business_batch_id="RM-B",
            uom="KG",
        )
        allocations = [
            {
                "lot_id": rm_a,
                "node_id": "M-1",
                "item_id": "RM-1",
                "qty": 4.0,
                "uom": "KG",
            },
            {
                "lot_id": rm_b,
                "node_id": "M-1",
                "item_id": "RM-1",
                "qty": 6.0,
                "uom": "KG",
            },
        ]
        produced = ledger.create_child_lot(
            day=1,
            node_id="M-1",
            item_id="PF-1",
            qty=100.0,
            source_type="production_output",
            source_id="CMP-1",
            parent_allocations=allocations,
            link_type="production",
            uom="UN",
        )
        produced_batch = ledger.lots[produced]["business_batch_id"]
        self.assertTrue(produced_batch)
        self.assertEqual(ledger.lots[produced]["provenance_batch_id"], "RM-A|RM-B")

        shipped = ledger.consume(
            day=2,
            node_id="M-1",
            item_id="PF-1",
            qty=100.0,
            event_type="lane_ship",
            uom="UN",
        )
        received = ledger.create_child_lot(
            day=3,
            node_id="DC-1",
            item_id="PF-1",
            qty=100.0,
            source_type="lane_receipt",
            source_id="M-1->DC-1",
            parent_allocations=shipped,
            link_type="transport",
            uom="UN",
            shipment_id="SHIP-PF",
        )

        self.assertEqual(ledger.lots[received]["business_batch_id"], produced_batch)
        self.assertEqual(ledger.lots[received]["provenance_batch_id"], produced_batch)
        self.assertEqual(ledger.lots[received]["trace_status"], "traced")

    def test_untraced_origin_stays_untraced_after_transport(self) -> None:
        ledger = LotLedger(enabled=True)
        ledger.create_lot(
            day=0,
            node_id="S-1",
            item_id="RM-1",
            qty=5.0,
            source_type="ledger_reconciliation",
            uom="KG",
            trace_status="untraced_origin",
            trace_reason="aggregate_source",
        )
        allocations = ledger.consume(
            day=1,
            node_id="S-1",
            item_id="RM-1",
            qty=5.0,
            event_type="lane_ship",
            uom="KG",
        )
        received = ledger.create_child_lot(
            day=2,
            node_id="M-1",
            item_id="RM-1",
            qty=5.0,
            source_type="lane_receipt",
            source_id="S-1->M-1",
            parent_allocations=allocations,
            link_type="transport",
            uom="KG",
            shipment_id="SHIP-UNKNOWN",
        )

        self.assertEqual(ledger.lots[received]["business_batch_id"], "")
        self.assertEqual(ledger.lots[received]["trace_status"], "untraced_origin")
        self.assertIn("inherited_untraced_parent_origin", ledger.lots[received]["trace_reason"])

    def test_component_share_normalizes_unites_and_un(self) -> None:
        ledger = LotLedger(enabled=True)
        lot_a = ledger.create_lot(
            day=0,
            node_id="M-1",
            item_id="COMP-1",
            qty=25.0,
            source_type="opening_stock",
            business_batch_id="COMP-A",
            uom="UNITES",
        )
        lot_b = ledger.create_lot(
            day=0,
            node_id="M-1",
            item_id="COMP-1",
            qty=75.0,
            source_type="opening_stock",
            business_batch_id="COMP-B",
            uom="UN",
        )
        child = ledger.create_child_lot(
            day=1,
            node_id="M-1",
            item_id="PF-1",
            qty=10.0,
            source_type="production_output",
            source_id="CMP-1",
            parent_allocations=[
                {
                    "lot_id": lot_a,
                    "node_id": "M-1",
                    "item_id": "COMP-1",
                    "qty": 25.0,
                    "uom": "UNITES",
                },
                {
                    "lot_id": lot_b,
                    "node_id": "M-1",
                    "item_id": "COMP-1",
                    "qty": 75.0,
                    "uom": "UN",
                },
            ],
            link_type="production",
            uom="UN",
        )
        shares = [
            row["component_allocation_share"]
            for row in ledger.genealogy_rows
            if row["child_lot_id"] == child
        ]
        self.assertEqual(shares, [0.25, 0.75])

    def test_opening_stock_is_an_untraced_occurrence_not_an_observed_batch(self) -> None:
        ledger = LotLedger(enabled=True)
        ledger.seed_opening_stock(
            day=0,
            stock={("M-1", "RM-1"): 12.0},
            item_unit_map={"RM-1": "KG"},
        )

        lot = next(iter(ledger.lots.values()))
        self.assertEqual(lot["business_batch_id"], "")
        self.assertEqual(lot["trace_status"], "untraced_before_horizon")
        self.assertEqual(
            lot["trace_reason"],
            "opening_stock_aggregated_without_source_batch_detail",
        )

    def test_known_batch_mixed_with_unknown_stock_is_only_partially_traced(self) -> None:
        ledger = LotLedger(enabled=True)
        ledger.create_lot(
            day=0,
            node_id="DC-1",
            item_id="PF-1",
            qty=4.0,
            source_type="opening_stock",
            business_batch_id="PF-KNOWN",
            uom="UN",
        )
        ledger.create_lot(
            day=0,
            node_id="DC-1",
            item_id="PF-1",
            qty=6.0,
            source_type="opening_stock",
            uom="UN",
            trace_status="untraced_before_horizon",
            trace_reason="opening_stock_aggregated_without_source_batch_detail",
        )
        allocations = ledger.consume(
            day=1,
            node_id="DC-1",
            item_id="PF-1",
            qty=10.0,
            event_type="lane_ship",
            uom="UN",
        )
        received = ledger.create_child_lot(
            day=2,
            node_id="C-1",
            item_id="PF-1",
            qty=10.0,
            source_type="lane_receipt",
            source_id="DC-1->C-1",
            parent_allocations=allocations,
            link_type="transport",
            uom="UN",
            shipment_id="SHIP-MIXED-TRACE",
        )

        lot = ledger.lots[received]
        self.assertEqual(lot["business_batch_id"], "")
        self.assertEqual(lot["provenance_batch_id"], "PF-KNOWN")
        self.assertEqual(lot["trace_status"], "partially_traced_mixed_occurrence")


# Test lot path audit

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
        repo_root = Path(__file__).resolve().parents[3]
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
