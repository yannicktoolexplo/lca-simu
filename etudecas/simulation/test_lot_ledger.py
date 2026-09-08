from __future__ import annotations

import unittest

from etudecas.simulation.run_first_simulation import LotLedger


class LotLedgerTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
