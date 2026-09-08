from __future__ import annotations

import unittest

from etudecas.simulation.analysis.audit_lot_trace_semantics import (
    audit_acceptance_semantics,
)


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
