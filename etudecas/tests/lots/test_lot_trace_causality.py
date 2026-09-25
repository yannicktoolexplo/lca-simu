"""Regression tests for lot trace causality."""

from __future__ import annotations
import csv
import json
import tempfile
import unittest
from pathlib import Path
from etudecas.simulation.experiments.targeted_replay.comparison import (
    build_lot_delta_rows,
    build_supply_order_delta_rows,
)
from etudecas.simulation.lot_trace.campaigns import build_production_campaign_rows
from etudecas.simulation.lot_trace.causal_links import (
    build_lot_causal_link_rows,
    causal_status,
    resolved_causal_status,
)
from etudecas.simulation.engine.run_first_simulation import LotLedger
from etudecas.simulation.analysis.audit_lot_trace_semantics import (
    audit_acceptance_semantics,
)


# Test lot trace causality

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


# Test lot trace acceptance

class LotTraceAcceptanceTest(unittest.TestCase):
    def test_legacy_run_reports_migration_debt_without_fatal_error(self) -> None:
        events = [
            self._legacy_event("E1", 0, "opening_stock", "LOT-1", "M-1430", "item:RM", "KG"),
            self._legacy_event("E2", 1, "lane_receipt", "LOT-2", "M-1430", "item:RM", "KG"),
        ]

        issues = audit_acceptance_semantics(events, [])

        self.assertFalse(self._of_severity(issues, "error"), issues)
        self.assertTrue(self._of_kind(issues, "migration_debt_lot_identity"), issues)
        self.assertTrue(self._of_kind(issues, "migration_debt_untraced_origin_status"), issues)
        self.assertTrue(
            self._of_kind(issues, "migration_debt_lot_trace_contract_version"),
            issues,
        )

    def test_contract_version_mismatch_is_rejected(self) -> None:
        event = self._event(
            "E1", 0, "opening_stock", "LOT-A", "M-1430", "item:A", "KG", "BA", "OA"
        )
        event["lot_trace_contract_version"] = "1.0"

        issues = audit_acceptance_semantics([event], [])

        self.assertTrue(
            self._of_kind(issues, "lot_trace_contract_version_mismatch"),
            issues,
        )

    def test_production_shares_are_normalized_per_component_not_across_uoms(self) -> None:
        events = [
            self._event("E1", 0, "opening_stock", "LOT-A1", "M-1430", "item:A", "G", "BA1", "OA1"),
            self._event("E2", 0, "opening_stock", "LOT-A2", "M-1430", "item:A", "G", "BA2", "OA2"),
            self._event("E3", 0, "opening_stock", "LOT-B1", "M-1430", "item:B", "UN", "BB1", "OB1"),
            self._event(
                "E4", 1, "production_output", "LOT-PF", "M-1430", "item:268967", "UN", "BPF", "OPF"
            ),
        ]
        links = [
            self._production_link(events, "LOT-A1", "LOT-PF", "item:A", 25.0, 1000.0, 0.25),
            self._production_link(events, "LOT-A2", "LOT-PF", "item:A", 75.0, 1000.0, 0.75),
            self._production_link(events, "LOT-B1", "LOT-PF", "item:B", 5000.0, 1000.0, 1.0),
        ]

        issues = audit_acceptance_semantics(events, links)

        self.assertFalse(self._of_kind(issues, "production_component_share_sum_mismatch"), issues)
        self.assertFalse(self._of_kind(issues, "production_component_inter_uom_share"), issues)
        self.assertFalse(self._of_kind(issues, "production_component_share_qty_mismatch"), issues)

    def test_bad_component_share_and_inter_uom_are_rejected(self) -> None:
        events = [
            self._event("E1", 0, "opening_stock", "LOT-A1", "M-1430", "item:A", "G", "BA1", "OA1"),
            self._event("E2", 0, "opening_stock", "LOT-A2", "M-1430", "item:A", "KG", "BA2", "OA2"),
            self._event(
                "E3", 1, "production_output", "LOT-PF", "M-1430", "item:268967", "UN", "BPF", "OPF"
            ),
        ]
        links = [
            self._production_link(events, "LOT-A1", "LOT-PF", "item:A", 25.0, 1000.0, 0.2),
            self._production_link(events, "LOT-A2", "LOT-PF", "item:A", 75.0, 1000.0, 0.7),
        ]

        issues = audit_acceptance_semantics(events, links)

        self.assertTrue(self._of_kind(issues, "production_component_share_sum_mismatch"), issues)
        self.assertTrue(self._of_kind(issues, "production_component_inter_uom_share"), issues)

    def test_lot_and_genealogy_identity_must_match(self) -> None:
        events = [
            self._event("E1", 0, "opening_stock", "LOT-A", "M-1430", "item:A", "KG", "BA", "OA"),
            self._event("E2", 1, "production_output", "LOT-PF", "M-1430", "item:PF", "UN", "BPF", "OPF"),
        ]
        link = self._production_link(events, "LOT-A", "LOT-PF", "item:A", 10.0, 100.0, 1.0)
        link["parent_business_batch_id"] = "WRONG"

        issues = audit_acceptance_semantics(events, [link])

        self.assertTrue(self._of_kind(issues, "genealogy_identity_mismatch"), issues)

    def test_mixed_transport_occurrence_may_have_no_single_business_batch(self) -> None:
        event = self._event(
            "E1", 2, "lane_receipt", "LOT-MIX", "DC-1920", "item:PF", "UN", "", "OMIX"
        )
        event["trace_status"] = "mixed_batch_occurrence"
        event["trace_reason"] = "consolidated_receipt_multiple_business_batches"
        event["provenance_batch_id"] = "BATCH-A|BATCH-B"

        issues = audit_acceptance_semantics([event], [])

        self.assertFalse(self._of_kind(issues, "lot_identity_missing_value"), issues)

    def test_explicit_untraced_occurrence_may_have_no_business_batch(self) -> None:
        event = self._event(
            "E1", 0, "opening_stock", "LOT-OPEN", "M-1430", "item:RM", "KG", "", "OOPEN"
        )
        event["trace_status"] = "untraced_before_horizon"
        event["trace_reason"] = "opening_stock_aggregated_without_source_batch_detail"

        issues = audit_acceptance_semantics([event], [])

        self.assertFalse(self._of_kind(issues, "lot_identity_missing_value"), issues)

    def test_shipment_identity_and_dates_are_checked(self) -> None:
        events = [
            self._event("E1", 0, "opening_stock", "LOT-A", "S-1", "item:A", "KG", "BA", "OA"),
            self._event("E2", 3, "lane_receipt", "LOT-B", "M-1430", "item:A", "KG", "BA", "OB"),
        ]
        link = self._transport_link(events, "LOT-A", "LOT-B", shipment_id="SHP-1", departure_day=4, arrival_day=2)

        issues = audit_acceptance_semantics(events, [link])

        self.assertTrue(self._of_kind(issues, "transport_departure_after_arrival"), issues)
        self.assertTrue(self._of_kind(issues, "transport_arrival_differs_from_link_day"), issues)

    def test_untraced_receipt_requires_explicit_status_and_reason(self) -> None:
        event = self._event(
            "E1", 2, "lane_receipt", "LOT-A", "M-1430", "item:A", "KG", "BA", "OA"
        )
        event["trace_status"] = ""
        event["trace_reason"] = ""

        issues = audit_acceptance_semantics([event], [])

        self.assertTrue(self._of_kind(issues, "untraced_origin_not_explicit"), issues)

        event["trace_status"] = "untraced_origin"
        event["trace_reason"] = "aggregate opening pipeline has no parent lot detail"
        accepted = audit_acceptance_semantics([event], [])
        self.assertFalse(self._of_kind(accepted, "untraced_origin_not_explicit"), accepted)

    def test_consumed_finished_product_requires_factory_dc_customer_path(self) -> None:
        events = [
            self._event(
                "E1", 0, "production_output", "LOT-PF", "M-1430", "item:268967", "UN", "BPF", "OPF"
            ),
            self._event("E2", 2, "lane_receipt", "LOT-DC", "DC-1920", "item:268967", "UN", "BPF", "ODC"),
            self._event("E3", 3, "lane_receipt", "LOT-C", "C-1", "item:268967", "UN", "BPF", "OC"),
            self._event("E4", 4, "demand_service", "LOT-C", "C-1", "item:268967", "UN", "BPF", "OC"),
        ]
        links = [
            self._transport_link(events, "LOT-PF", "LOT-DC", "SHP-1", 1, 2),
            self._transport_link(events, "LOT-DC", "LOT-C", "SHP-2", 2, 3),
        ]
        node_types = {
            "M-1430": "factory",
            "DC-1920": "distribution_center",
            "C-1": "customer",
        }

        accepted = audit_acceptance_semantics(events, links, node_types=node_types)
        self.assertFalse(self._of_kind(accepted, "finished_product_path_missing_supply_stage"), accepted)

        direct_link = self._transport_link(events, "LOT-PF", "LOT-C", "SHP-3", 2, 3)
        rejected = audit_acceptance_semantics(events, [direct_link], node_types=node_types)
        self.assertTrue(self._of_kind(rejected, "finished_product_path_missing_supply_stage"), rejected)

    def test_pfi_773474_must_reach_m1430_before_production_use(self) -> None:
        events = [
            self._event(
                "E1", 0, "production_output", "LOT-PFI", "D-1450", "item:773474", "G", "BPFI", "OPFI"
            ),
            self._event("E2", 2, "lane_receipt", "LOT-PFI-M", "M-1430", "item:773474", "G", "BPFI", "OPFIM"),
            self._event(
                "E3", 3, "production_output", "LOT-PF", "M-1430", "item:268967", "UN", "BPF", "OPF"
            ),
        ]
        transport = self._transport_link(events, "LOT-PFI", "LOT-PFI-M", "SHP-1", 1, 2)
        production = self._production_link(
            events, "LOT-PFI-M", "LOT-PF", "item:773474", 100.0, 1000.0, 1.0
        )

        accepted = audit_acceptance_semantics(events, [transport, production])
        self.assertFalse(self._of_kind(accepted, "semifinished_path_missing_m1430_transport"), accepted)

        missing_transport = self._production_link(
            events, "LOT-PFI", "LOT-PF", "item:773474", 100.0, 1000.0, 1.0
        )
        missing_transport["parent_node_id"] = "M-1430"
        rejected = audit_acceptance_semantics(events, [missing_transport])
        self.assertTrue(self._of_kind(rejected, "semifinished_path_missing_m1430_transport"), rejected)

    @staticmethod
    def _legacy_event(
        event_id: str,
        day: int,
        event_type: str,
        lot_id: str,
        node_id: str,
        item_id: str,
        uom: str,
    ) -> dict[str, str]:
        return {
            "event_id": event_id,
            "day": str(day),
            "event_type": event_type,
            "lot_id": lot_id,
            "node_id": node_id,
            "item_id": item_id,
            "qty": "100",
            "qty_after": "100",
            "uom": uom,
            "source_type": event_type,
            "source_id": "source",
        }

    def _event(
        self,
        event_id: str,
        day: int,
        event_type: str,
        lot_id: str,
        node_id: str,
        item_id: str,
        uom: str,
        business_batch_id: str,
        lot_occurrence_id: str,
    ) -> dict[str, str]:
        return {
            **self._legacy_event(event_id, day, event_type, lot_id, node_id, item_id, uom),
            "business_batch_id": business_batch_id,
            "lot_occurrence_id": lot_occurrence_id,
            "shipment_id": "",
            "departure_day": "",
            "arrival_day": "",
            "trace_status": "traced",
            "trace_reason": "synthetic acceptance fixture",
            "lot_trace_contract_version": "2.0",
        }

    def _production_link(
        self,
        events: list[dict[str, str]],
        parent_lot: str,
        child_lot: str,
        parent_item: str,
        parent_qty: float,
        child_qty: float,
        component_share: float,
    ) -> dict[str, str]:
        parent = self._by_lot(events, parent_lot)
        child = self._by_lot(events, child_lot)
        return {
            "day": child["day"],
            "link_type": "production",
            "parent_lot_id": parent_lot,
            "parent_node_id": parent["node_id"],
            "parent_item_id": parent_item,
            "child_lot_id": child_lot,
            "child_node_id": child["node_id"],
            "child_item_id": child["item_id"],
            "parent_qty": str(parent_qty),
            "child_qty": str(child_qty),
            "allocation_share": str(component_share),
            "component_allocation_share": str(component_share),
            "parent_business_batch_id": parent["business_batch_id"],
            "parent_lot_occurrence_id": parent["lot_occurrence_id"],
            "child_business_batch_id": child["business_batch_id"],
            "child_lot_occurrence_id": child["lot_occurrence_id"],
            "shipment_id": "",
            "departure_day": "",
            "arrival_day": "",
            "lot_trace_contract_version": "2.0",
        }

    def _transport_link(
        self,
        events: list[dict[str, str]],
        parent_lot: str,
        child_lot: str,
        shipment_id: str,
        departure_day: int,
        arrival_day: int,
    ) -> dict[str, str]:
        parent = self._by_lot(events, parent_lot)
        child = self._by_lot(events, child_lot)
        if child["event_type"] == "lane_receipt":
            child["shipment_id"] = shipment_id
            child["departure_day"] = str(departure_day)
            child["arrival_day"] = str(arrival_day)
        return {
            "day": child["day"],
            "link_type": "transport",
            "parent_lot_id": parent_lot,
            "parent_node_id": parent["node_id"],
            "parent_item_id": parent["item_id"],
            "child_lot_id": child_lot,
            "child_node_id": child["node_id"],
            "child_item_id": child["item_id"],
            "parent_qty": "100",
            "child_qty": "100",
            "allocation_share": "1",
            "component_allocation_share": "",
            "parent_business_batch_id": parent["business_batch_id"],
            "parent_lot_occurrence_id": parent["lot_occurrence_id"],
            "child_business_batch_id": child["business_batch_id"],
            "child_lot_occurrence_id": child["lot_occurrence_id"],
            "shipment_id": shipment_id,
            "departure_day": str(departure_day),
            "arrival_day": str(arrival_day),
            "lot_trace_contract_version": "2.0",
        }

    @staticmethod
    def _by_lot(events: list[dict[str, str]], lot_id: str) -> dict[str, str]:
        return next(row for row in events if row["lot_id"] == lot_id)

    @staticmethod
    def _of_kind(issues: list[dict[str, str]], kind: str) -> list[dict[str, str]]:
        return [row for row in issues if row["kind"] == kind]

    @staticmethod
    def _of_severity(issues: list[dict[str, str]], severity: str) -> list[dict[str, str]]:
        return [row for row in issues if row["severity"] == severity]


if __name__ == "__main__":
    unittest.main()
