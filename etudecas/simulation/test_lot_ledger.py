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


if __name__ == "__main__":
    unittest.main()
