from __future__ import annotations

from collections import defaultdict
import unittest

from etudecas.simulation.engine.run_first_simulation import (
    LOT_TRACE_EPS,
    LotLedger,
    launch_campaign_qty,
    normalize_unit,
    process_lot_policy,
)
from etudecas.simulation.lot_trace.campaigns import (
    build_production_campaign_rows,
)
from etudecas.simulation.lot_trace.causal_links import (
    build_lot_causal_link_rows,
)


class LotificationAcceptanceContractTest(unittest.TestCase):
    """Business acceptance contracts for generic lot-level simulation."""

    def test_fixed_lot_production_rounds_requirement_to_complete_lots(self) -> None:
        policy = process_lot_policy(
            {
                "lot_sizing": {
                    "fixed_lot_qty": 100,
                    "uom": "UN",
                    "source": "acceptance_fixture",
                }
            },
            out_item="PF",
            item_unit_map={"PF": "UN"},
        )

        self.assertTrue(policy["enabled"])
        self.assertEqual(policy["fixed_lot_qty"], 100)
        self.assertEqual(launch_campaign_qty(1, policy), 100)
        self.assertEqual(launch_campaign_qty(100, policy), 100)
        self.assertEqual(launch_campaign_qty(101, policy), 200)

    def test_un_quantities_are_whole_numbers_in_lot_movements(self) -> None:
        """Physical occurrences use integral units even when the signal is fractional."""

        ledger = LotLedger(enabled=True)
        lot_id = ledger.create_lot(
            day=0,
            node_id="NODE",
            item_id="ITEM-UN",
            qty=2.5,
            source_type="acceptance_fixture",
            uom="UN",
        )

        unit_quantities = [
            float(ledger.lots[lot_id]["initial_qty"]),
            *[
                float(row["qty"])
                for row in ledger.event_rows
                if normalize_unit(row.get("uom")) == "UN"
            ],
        ]
        self.assertTrue(
            all(qty.is_integer() for qty in unit_quantities),
            f"Fractional UN movements found: {unit_quantities}",
        )

    def test_sub_epsilon_quantities_create_no_dust_movement(self) -> None:
        ledger = LotLedger(enabled=True)
        dust_qty = LOT_TRACE_EPS / 2

        dust_lot = ledger.create_lot(
            day=0,
            node_id="NODE",
            item_id="ITEM",
            qty=dust_qty,
            source_type="acceptance_fixture",
            uom="KG",
        )
        self.assertEqual(dust_lot, "")
        self.assertEqual(ledger.lots, {})
        self.assertEqual(ledger.event_rows, [])

        stock_lot = ledger.create_lot(
            day=0,
            node_id="NODE",
            item_id="ITEM",
            qty=1.0,
            source_type="acceptance_fixture",
            uom="KG",
        )
        event_count = len(ledger.event_rows)
        allocations = ledger.consume(
            day=1,
            node_id="NODE",
            item_id="ITEM",
            qty=dust_qty,
            event_type="lane_ship",
            uom="KG",
        )

        self.assertEqual(allocations, [])
        self.assertEqual(len(ledger.event_rows), event_count)
        self.assertEqual(ledger.lots[stock_lot]["qty_remaining"], 1.0)

    def test_business_batch_identity_survives_transport_occurrences(self) -> None:
        chain = self._traced_finished_product_chain()
        ledger = chain["ledger"]
        produced = ledger.lots[chain["produced_lot_id"]]
        received = ledger.lots[chain["received_lot_id"]]

        self.assertTrue(produced["business_batch_id"].startswith("PBATCH-"))
        self.assertEqual(received["business_batch_id"], produced["business_batch_id"])
        self.assertNotEqual(received["lot_occurrence_id"], produced["lot_occurrence_id"])
        self.assertEqual(received["shipment_id"], chain["shipment_id"])
        self.assertNotEqual(received["shipment_id"], received["business_batch_id"])

        transport_links = [
            row
            for row in ledger.genealogy_rows
            if row["link_type"] == "transport"
            and row["child_lot_id"] == chain["received_lot_id"]
        ]
        self.assertEqual(len(transport_links), 1)
        self.assertEqual(
            transport_links[0]["parent_business_batch_id"],
            transport_links[0]["child_business_batch_id"],
        )

    def test_bom_contributions_balance_per_component_and_uom(self) -> None:
        ledger = LotLedger(enabled=True)
        component_specs = [
            ("COMP-A", 25.0, "UNITES", "A-1"),
            ("COMP-A", 75.0, "UN", "A-2"),
            ("COMP-B", 200.0, "G", "B-1"),
            ("COMP-B", 300.0, "G", "B-2"),
        ]
        for item_id, qty, uom, batch_id in component_specs:
            ledger.create_lot(
                day=0,
                node_id="FACTORY",
                item_id=item_id,
                qty=qty,
                source_type="acceptance_fixture",
                uom=uom,
                business_batch_id=batch_id,
            )

        allocations = [
            *ledger.consume(
                day=1,
                node_id="FACTORY",
                item_id="COMP-A",
                qty=100,
                event_type="production_consume",
                uom="UN",
            ),
            *ledger.consume(
                day=1,
                node_id="FACTORY",
                item_id="COMP-B",
                qty=500,
                event_type="production_consume",
                uom="G",
            ),
        ]
        campaign_id = ledger.next_campaign_id(
            day=1,
            node_id="FACTORY",
            item_id="PF",
        )
        planned_order_id = ledger.planned_order_id(campaign_id)
        child_lot_id = ledger.create_child_lot(
            day=1,
            node_id="FACTORY",
            item_id="PF",
            qty=100,
            source_type="production_output",
            source_id=campaign_id,
            parent_allocations=allocations,
            link_type="production",
            uom="UN",
            production_campaign_id=campaign_id,
            planned_order_id=planned_order_id,
            baseline_reference_id=planned_order_id,
        )

        grouped_shares: dict[tuple[str, str], float] = defaultdict(float)
        grouped_qty: dict[tuple[str, str], float] = defaultdict(float)
        for row in ledger.genealogy_rows:
            if row["child_lot_id"] != child_lot_id or row["link_type"] != "production":
                continue
            parent_lot = ledger.lots[row["parent_lot_id"]]
            key = (
                row["parent_item_id"],
                normalize_unit(parent_lot["uom"]),
            )
            grouped_shares[key] += float(row["component_allocation_share"])
            grouped_qty[key] += float(row["parent_qty"])

        self.assertEqual(set(grouped_shares), {("COMP-A", "UN"), ("COMP-B", "G")})
        for key, share in grouped_shares.items():
            self.assertAlmostEqual(share, 1.0, places=9, msg=f"Unbalanced {key}")
        self.assertEqual(grouped_qty[("COMP-A", "UN")], 100)
        self.assertEqual(grouped_qty[("COMP-B", "G")], 500)

    def test_selected_causal_root_exposes_events_and_structural_chain(self) -> None:
        chain = self._traced_finished_product_chain()
        ledger = chain["ledger"]
        plan_rows = [
            {
                "day": 1,
                "campaign_id": chain["campaign_id"],
                "planned_order_id": chain["planned_order_id"],
                "baseline_reference_id": chain["planned_order_id"],
                "scenario_id": "SCENARIO-RISK",
                "node_id": "FACTORY",
                "output_item_id": "PF",
                "event_type": "run_campaign_complete",
                "reason": "none",
                "planned_qty_after_lot_rule": 100,
                "campaign_requested_qty": 100,
                "campaign_started_qty": 100,
                "actual_qty": 100,
                "causal_event_ids": "EVENT-RISK",
                "causal_root_ids": "ROOT-RISK",
                "causal_status": "scenario_affected",
            }
        ]
        campaign_rows = build_production_campaign_rows(plan_rows, ledger.event_rows)
        causal_rows = build_lot_causal_link_rows(
            lot_event_rows=ledger.event_rows,
            genealogy_rows=ledger.genealogy_rows,
            production_plan_rows=plan_rows,
            production_campaign_rows=campaign_rows,
            mrp_order_rows=[
                {
                    "scenario_id": "SCENARIO-OTHER",
                    "mrp_order_id": "MRP-OTHER",
                    "node_id": "OTHER",
                    "item_id": "OTHER",
                    "planned_receipt_qty": 1,
                    "causal_event_ids": "EVENT-OTHER",
                    "causal_root_ids": "ROOT-OTHER",
                    "causal_status": "scenario_affected",
                }
            ],
        )

        selected_rows = [
            row for row in causal_rows if row["causal_root_id"] == "ROOT-RISK"
        ]
        self.assertTrue(selected_rows)
        self.assertNotIn("ROOT-OTHER", {row["causal_root_id"] for row in selected_rows})
        self.assertTrue(
            all("EVENT-RISK" in row["causal_event_ids"] for row in selected_rows)
        )
        self.assertTrue(
            {
                "risk_affects_production_plan",
                "risk_affects_production_campaign",
                "risk_affects_business_lot",
                "risk_affects_shipment",
                "risk_affects_customer_stock_allocation",
            }.issubset({row["relation_type"] for row in selected_rows})
        )

        structural_rows = [row for row in causal_rows if not row["causal_root_id"]]
        structural_edges = {
            (
                row["relation_type"],
                row["parent_entity_type"],
                row["entity_type"],
            )
            for row in structural_rows
        }
        self.assertTrue(
            {
                (
                    "production_order_has_campaign",
                    "production_order",
                    "production_campaign",
                ),
                (
                    "campaign_produces_business_lot",
                    "production_campaign",
                    "business_lot",
                ),
                ("lot_allocated_to_shipment", "business_lot", "shipment"),
                (
                    "shipment_creates_stock_occurrence",
                    "shipment",
                    "lot_occurrence",
                ),
                (
                    "production_order_contributes_to_customer_allocation",
                    "production_order",
                    "customer_stock_allocation",
                ),
            }.issubset(structural_edges)
        )

    @staticmethod
    def _traced_finished_product_chain() -> dict[str, object]:
        ledger = LotLedger(enabled=True, scenario_id="SCENARIO-RISK")
        ledger.create_lot(
            day=0,
            node_id="FACTORY",
            item_id="COMP",
            qty=10,
            source_type="lane_receipt",
            uom="KG",
            business_batch_id="COMP-BATCH",
            causal_event_ids="EVENT-RISK",
            causal_root_ids="ROOT-RISK",
        )
        component_allocations = ledger.consume(
            day=1,
            node_id="FACTORY",
            item_id="COMP",
            qty=10,
            event_type="production_consume",
            uom="KG",
        )
        campaign_id = ledger.next_campaign_id(
            day=1,
            node_id="FACTORY",
            item_id="PF",
        )
        planned_order_id = ledger.planned_order_id(campaign_id)
        produced_lot_id = ledger.create_child_lot(
            day=1,
            node_id="FACTORY",
            item_id="PF",
            qty=100,
            source_type="production_output",
            source_id=campaign_id,
            parent_allocations=component_allocations,
            link_type="production",
            uom="UN",
            production_campaign_id=campaign_id,
            planned_order_id=planned_order_id,
            baseline_reference_id=planned_order_id,
        )
        shipment_id = "SHIP-FACTORY-DC-1"
        shipment_allocations = ledger.consume(
            day=2,
            node_id="FACTORY",
            item_id="PF",
            qty=100,
            event_type="lane_ship",
            source_id="FACTORY->DC",
            uom="UN",
            shipment_id=shipment_id,
            departure_day=2,
            arrival_day=3,
        )
        received_lot_id = ledger.create_child_lot(
            day=3,
            node_id="DC",
            item_id="PF",
            qty=100,
            source_type="lane_receipt",
            source_id="FACTORY->DC",
            parent_allocations=shipment_allocations,
            link_type="transport",
            uom="UN",
            shipment_id=shipment_id,
            departure_day=2,
            arrival_day=3,
        )
        ledger.consume(
            day=4,
            node_id="DC",
            item_id="PF",
            qty=40,
            event_type="demand_service",
            source_id="CUSTOMER-DEMAND",
            uom="UN",
        )
        return {
            "ledger": ledger,
            "campaign_id": campaign_id,
            "planned_order_id": planned_order_id,
            "produced_lot_id": produced_lot_id,
            "received_lot_id": received_lot_id,
            "shipment_id": shipment_id,
        }


if __name__ == "__main__":
    unittest.main()
