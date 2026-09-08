from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from etudecas.simulation.experiments.targeted_replay.comparison import (
    build_lot_delta_rows,
    build_supply_order_delta_rows,
)
from etudecas.simulation.lot_trace.campaigns import build_production_campaign_rows
from etudecas.simulation.lot_trace.causal_links import build_lot_causal_link_rows
from etudecas.simulation.lot_trace.causality import (
    causal_status,
    resolved_causal_status,
)
from etudecas.simulation.run_first_simulation import LotLedger


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class LotCausalityTest(unittest.TestCase):
    def test_co_cause_status_uses_independent_roots(self) -> None:
        self.assertEqual(
            causal_status("EVT-1|EVT-2", root_ids="ROOT-1"),
            "scenario_affected",
        )
        self.assertEqual(
            causal_status("EVT-1|EVT-2", root_ids="ROOT-1|ROOT-2"),
            "co_causes",
        )

    def test_nominal_status_cannot_override_explicit_causes(self) -> None:
        self.assertEqual(
            resolved_causal_status(
                "EVT-1",
                root_ids="ROOT-1",
                provided_status="nominal",
            ),
            "scenario_affected",
        )
        self.assertEqual(
            resolved_causal_status(
                "EVT-1|EVT-2",
                root_ids="ROOT-1|ROOT-2",
                provided_status="nominal",
            ),
            "co_causes",
        )
        self.assertEqual(
            resolved_causal_status(
                "EVT-1",
                root_ids="ROOT-1",
                provided_status="approved_transition",
            ),
            "approved_transition",
        )

    def test_two_risks_propagate_as_co_causes_to_customer_service(self) -> None:
        ledger = LotLedger(enabled=True, scenario_id="SCN-RISK")
        ledger.create_lot(
            day=0,
            node_id="SUP-1",
            item_id="RM-1",
            qty=100.0,
            source_type="lane_receipt",
            causal_event_ids="EVT-1|EVT-2",
            causal_root_ids="ROOT-1|ROOT-2",
            planned_order_id="MRPREQ-1",
            baseline_reference_id="MRPREQ-1",
        )
        component_allocations = ledger.consume(
            day=1,
            node_id="SUP-1",
            item_id="RM-1",
            qty=50.0,
            event_type="production_consume",
        )
        campaign_id = ledger.next_campaign_id(day=1, node_id="M-1", item_id="PF-1")
        production_order = ledger.planned_order_id(campaign_id)
        produced = ledger.create_child_lot(
            day=1,
            node_id="M-1",
            item_id="PF-1",
            qty=10.0,
            source_type="production_output",
            source_id=campaign_id,
            parent_allocations=component_allocations,
            link_type="production",
            production_campaign_id=campaign_id,
            planned_order_id=production_order,
            baseline_reference_id=production_order,
        )
        self.assertTrue(ledger.lots[produced]["business_batch_id"].startswith("PBATCH-"))

        shipped = ledger.consume(
            day=2,
            node_id="M-1",
            item_id="PF-1",
            qty=10.0,
            event_type="lane_ship",
            planned_order_id="MRPREQ-PF-1",
            shipment_id="SHP-1",
        )
        received = ledger.create_child_lot(
            day=3,
            node_id="DC-1",
            item_id="PF-1",
            qty=10.0,
            source_type="lane_receipt",
            source_id="M-1->DC-1",
            parent_allocations=shipped,
            link_type="transport",
            planned_order_id="MRPREQ-PF-1",
            shipment_id="SHP-1",
        )
        ledger.consume(
            day=4,
            node_id="DC-1",
            item_id="PF-1",
            qty=4.0,
            event_type="demand_service",
        )

        service = next(row for row in ledger.event_rows if row["event_type"] == "demand_service")
        contributions = json.loads(service["origin_production_contributions_json"])
        self.assertEqual(contributions, {production_order: 4.0})
        self.assertEqual(service["origin_allocation_basis"], "direct_production_order")
        self.assertEqual(service["causal_event_ids"], "EVT-1|EVT-2")
        self.assertEqual(service["causal_root_ids"], "ROOT-1|ROOT-2")
        self.assertEqual(service["causal_status"], "co_causes")
        self.assertEqual(ledger.lots[received]["origin_production_order_ids"], production_order)

    def test_reserved_shipment_records_physical_departure_without_double_consumption(self) -> None:
        ledger = LotLedger(enabled=True, scenario_id="SCN-1")
        lot_id = ledger.create_lot(
            day=0,
            node_id="SUP-1",
            item_id="RM-1",
            qty=20.0,
            source_type="opening_stock",
        )
        allocations = ledger.consume(
            day=1,
            node_id="SUP-1",
            item_id="RM-1",
            qty=8.0,
            event_type="shipment_reserve",
            shipment_id="SHP-1",
            departure_day=3,
            arrival_day=5,
        )
        ledger.record_allocation_event(
            day=3,
            event_type="lane_ship",
            parent_allocations=allocations,
            shipment_id="SHP-1",
            departure_day=3,
            arrival_day=5,
        )
        self.assertEqual(ledger.lots[lot_id]["qty_remaining"], 12.0)
        shipment_events = [
            row
            for row in ledger.event_rows
            if row["shipment_id"] == "SHP-1"
        ]
        self.assertEqual(
            [(row["day"], row["event_type"]) for row in shipment_events],
            [(1, "shipment_reserve"), (3, "lane_ship")],
        )

    def test_campaign_and_causal_index_keep_explicit_roots(self) -> None:
        plan_rows = [
            {
                "day": 2,
                "campaign_id": "CMP-1",
                "planned_order_id": "PORD-M-1-PF-1-000001",
                "baseline_reference_id": "PORD-M-1-PF-1-000001",
                "scenario_id": "SCN-1",
                "node_id": "M-1",
                "output_item_id": "PF-1",
                "event_type": "delay_input_shortage",
                "reason": "input_shortage",
                "planned_qty_after_lot_rule": 100.0,
                "actual_qty": 0.0,
                "shortfall_vs_lot_plan_qty": 100.0,
                "causal_event_ids": "EVT-A|EVT-B",
                "causal_root_ids": "ROOT-A|ROOT-B",
                "causal_status": "co_causes",
            },
            {
                "day": 5,
                "campaign_id": "CMP-1",
                "planned_order_id": "PORD-M-1-PF-1-000001",
                "baseline_reference_id": "PORD-M-1-PF-1-000001",
                "scenario_id": "SCN-1",
                "node_id": "M-1",
                "output_item_id": "PF-1",
                "event_type": "run_campaign_complete",
                "reason": "none",
                "planned_qty_after_lot_rule": 100.0,
                "actual_qty": 100.0,
            },
        ]
        lot_rows = [
            {
                "event_id": "LEVT-1",
                "day": 5,
                "event_type": "production_output",
                "lot_id": "LOT-1",
                "business_batch_id": "PBATCH-1",
                "lot_occurrence_id": "LOCC-1",
                "production_campaign_id": "CMP-1",
                "planned_order_id": "PORD-M-1-PF-1-000001",
                "scenario_id": "SCN-1",
                "node_id": "M-1",
                "item_id": "PF-1",
                "qty": 100.0,
                "causal_event_ids": "EVT-A|EVT-B",
                "causal_root_ids": "ROOT-A|ROOT-B",
                "causal_status": "co_causes",
            }
        ]
        campaigns = build_production_campaign_rows(plan_rows, lot_rows)
        self.assertEqual(campaigns[0]["status"], "completed_after_delay")
        self.assertEqual(campaigns[0]["causal_status"], "co_causes")
        causal_rows = build_lot_causal_link_rows(
            lot_event_rows=lot_rows,
            genealogy_rows=[],
            production_plan_rows=plan_rows,
            production_campaign_rows=campaigns,
            mrp_order_rows=[],
        )
        self.assertEqual(
            {
                row["causal_root_id"]
                for row in causal_rows
                if row["causal_root_id"]
            },
            {"ROOT-A", "ROOT-B"},
        )
        self.assertIn(
            "risk_affects_production_campaign",
            {row["relation_type"] for row in causal_rows},
        )
        self.assertIn(
            "risk_affects_business_lot",
            {row["relation_type"] for row in causal_rows},
        )

    def test_causal_index_exposes_shipment_and_customer_allocation(self) -> None:
        common = {
            "scenario_id": "SCN-1",
            "node_id": "DC-1",
            "item_id": "PF-1",
            "qty": 10.0,
            "uom": "UN",
            "shipment_id": "SHP-1",
            "business_batch_id": "PBATCH-1",
            "origin_production_order_ids": "PORD-1|PORD-2",
            "origin_production_contributions_json": json.dumps(
                {"PORD-1": 6.0, "PORD-2": 4.0}
            ),
            "causal_event_ids": "EVT-1",
            "causal_root_ids": "ROOT-1",
            "causal_status": "scenario_affected",
        }
        rows = build_lot_causal_link_rows(
            lot_event_rows=[
                {
                    **common,
                    "event_id": "LEVT-SHIP",
                    "day": 3,
                    "event_type": "lane_ship",
                },
                {
                    **common,
                    "event_id": "LEVT-SERVICE",
                    "day": 8,
                    "event_type": "demand_service",
                },
            ],
            genealogy_rows=[],
            production_plan_rows=[],
            production_campaign_rows=[],
            mrp_order_rows=[],
        )
        by_relation = {row["relation_type"]: row for row in rows}
        self.assertEqual(
            by_relation["risk_affects_shipment"]["entity_id"],
            "SHP-1",
        )
        self.assertEqual(
            by_relation["risk_affects_customer_stock_allocation"]["entity_id"],
            "LEVT-SERVICE",
        )
        allocation_links = [
            row
            for row in rows
            if row["relation_type"]
            == "production_order_contributes_to_customer_allocation"
        ]
        self.assertEqual(
            {row["parent_entity_id"] for row in allocation_links},
            {"PORD-1", "PORD-2"},
        )
        self.assertEqual(
            sum(float(row["qty"]) for row in allocation_links),
            10.0,
        )
        self.assertIn(
            "lot_allocated_to_shipment",
            {row["relation_type"] for row in rows},
        )

    def test_delta_report_uses_origin_production_contributions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "baseline"
            scenario = root / "scenario"
            campaign_base = {
                "campaign_id": "CMP-BASE",
                "planned_order_id": "PORD-1",
                "baseline_reference_id": "PORD-1",
                "node_id": "M-1",
                "output_item_id": "PF-1",
                "status": "completed_without_delay",
                "first_event_day": 2,
                "completed_day": 2,
                "delay_day_count": 0,
                "actual_qty": 100,
            }
            campaign_scenario = {
                **campaign_base,
                "campaign_id": "CMP-SCENARIO",
                "status": "completed_after_delay",
                "completed_day": 5,
                "delay_day_count": 3,
                "completed_lot_ids": "LOT-S1",
                "causal_event_ids": "EVT-1",
                "causal_root_ids": "ROOT-1",
                "causal_status": "scenario_affected",
            }
            _write_csv(
                baseline / "data" / "production_campaigns.csv",
                [campaign_base],
            )
            _write_csv(
                scenario / "data" / "production_campaigns.csv",
                [campaign_scenario],
            )
            _write_csv(
                scenario / "data" / "production_lot_events.csv",
                [
                    {
                        "event_id": "E-SERVICE",
                        "day": 12,
                        "event_type": "demand_service",
                        "qty": 40,
                        "origin_production_order_ids": "PORD-1",
                        "origin_production_contributions_json": json.dumps({"PORD-1": 40}),
                        "causal_event_ids": "EVT-1",
                        "causal_root_ids": "ROOT-1",
                    }
                ],
            )
            _write_csv(
                scenario / "data" / "production_lot_genealogy.csv",
                [],
            )
            rows = build_lot_delta_rows(
                baseline_run_dir=baseline,
                scenario_run_dir=scenario,
                scenario_id="SCN-1",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["production_shift_days"], 3)
            self.assertEqual(rows[0]["scenario_customer_service_qty"], 40.0)
            self.assertTrue(rows[0]["delayed"])
            self.assertTrue(rows[0]["rescheduled"])
            self.assertEqual(rows[0]["causal_root_ids"], "ROOT-1")

    def test_supply_order_delta_tracks_delayed_receipt_and_received_lot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "baseline"
            scenario = root / "scenario"
            common = {
                "mrp_order_id": "MRPREQ-1",
                "baseline_reference_id": "MRPREQ-1",
                "order_type": "lane_release",
                "src_node_id": "SUP-1",
                "dst_node_id": "M-1",
                "item_id": "RM-1",
                "release_day": 2,
                "planned_receipt_qty": 100,
                "shipment_id": "SHP-1",
            }
            _write_csv(
                baseline / "data" / "mrp_orders_daily.csv",
                [{**common, "arrival_day": 7, "actual_receipt_day": 7}],
            )
            _write_csv(
                scenario / "data" / "mrp_orders_daily.csv",
                [
                    {
                        **common,
                        "arrival_day": 11,
                        "actual_receipt_day": 11,
                        "causal_event_ids": "EVT-1",
                        "causal_root_ids": "ROOT-1",
                    }
                ],
            )
            _write_csv(
                scenario / "data" / "production_lot_events.csv",
                [
                    {
                        "event_id": "LEVT-1",
                        "event_type": "lane_receipt",
                        "lot_id": "LOT-RM-1",
                        "planned_order_id": "MRPREQ-1",
                        "baseline_reference_id": "MRPREQ-1",
                    }
                ],
            )
            rows = build_supply_order_delta_rows(
                baseline_run_dir=baseline,
                scenario_run_dir=scenario,
                scenario_id="SCN-1",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["arrival_shift_days"], 4)
            self.assertTrue(rows[0]["delayed"])
            self.assertEqual(rows[0]["scenario_received_lot_ids"], "LOT-RM-1")
            self.assertEqual(rows[0]["causal_root_ids"], "ROOT-1")
            self.assertEqual(
                rows[0]["matching_confidence"],
                "stable_generated_order_id",
            )

    def test_supply_order_delta_matches_split_orders_by_quantity_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "baseline"
            scenario = root / "scenario"
            common = {
                "order_type": "lane_release",
                "src_node_id": "SUP-1",
                "dst_node_id": "M-1",
                "item_id": "RM-1",
                "release_day": 2,
                "arrival_day": 7,
                "actual_receipt_day": 7,
            }
            _write_csv(
                baseline / "data" / "mrp_orders_daily.csv",
                [
                    {
                        **common,
                        "mrp_order_id": "MRPREQ-BASE",
                        "planned_receipt_qty": 100,
                    }
                ],
            )
            _write_csv(
                scenario / "data" / "mrp_orders_daily.csv",
                [
                    {
                        **common,
                        "mrp_order_id": "MRPREQ-SCENARIO-A",
                        "planned_receipt_qty": 40,
                    },
                    {
                        **common,
                        "mrp_order_id": "MRPREQ-SCENARIO-B",
                        "planned_receipt_qty": 60,
                    },
                ],
            )
            rows = build_supply_order_delta_rows(
                baseline_run_dir=baseline,
                scenario_run_dir=scenario,
                scenario_id="SCN-1",
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                sum(row["matched_qty"] for row in rows),
                100.0,
            )
            self.assertTrue(
                all(row["comparison_status"] == "matched" for row in rows)
            )
            self.assertTrue(
                all(
                    row["matching_confidence"]
                    == "quantity_overlap_reconstruction"
                    for row in rows
                )
            )
            self.assertTrue(all(row["order_shape_changed"] for row in rows))
            self.assertTrue(all(not row["quantity_changed"] for row in rows))


if __name__ == "__main__":
    unittest.main()
