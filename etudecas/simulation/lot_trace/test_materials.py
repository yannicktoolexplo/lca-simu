from copy import deepcopy
import unittest

from .materials import VERSION, build_material_traceability, build_incident_preview


def fixture():
    def event(id, lot, kind, qty, item="item:RM", shipment=""):
        return dict(event_id=id, lot_id=lot, event_type=kind, qty=qty, uom="UN", day=3,
                    node_id="PLANT", item_id=item, shipment_id=shipment, business_batch_id="SIM-" + lot)
    events = [event("E1", "R1", "lane_receipt", 60, shipment="S1"),
              event("E2", "R2", "lane_receipt", 40, shipment="S2"),
              event("E3", "R3", "lane_receipt", 50, shipment="S3"),
              event("E4", "P1", "production_output", 50, "item:PF"),
              event("E5", "P2", "production_output", 40, "item:PF"),
              event("E6", "P3", "production_output", 50, "item:PF")]
    links = [dict(link_type="production", parent_lot_id=parent, child_lot_id=child,
                  parent_node_id="SUP", parent_qty=qty, child_qty=qty)
             for parent, child, qty in [("R1", "P1", 50), ("R2", "P2", 40), ("R3", "P3", 50)]]
    metadata = dict(version=VERSION, origins=[dict(id="O1", manufacturer_id="MAKER", item_id="item:RM",
                    batch_number="B-2026", status="observed", source_reference="supplier_certificate:test")],
                    allocations=[dict(receipt_id="E1", origin_id="O1", quantity=60, uom="UN"),
                                 dict(receipt_id="E2", origin_id="O1", quantity=40, uom="UN")])
    return events, links, metadata


class MaterialTraceabilityTest(unittest.TestCase):
    def test_unknown_is_not_the_simulated_batch_or_a_truck(self):
        events, links, _ = fixture()
        result = build_material_traceability(events, links)
        self.assertEqual(result["origins"], {})
        self.assertEqual(result["receipts"]["E1"]["unknown_origin_qty"], 60)
        self.assertEqual(result["receipts"]["E1"]["simulated_batch_id"], "SIM-R1")
        self.assertEqual(result["receipts"]["E1"]["handling_units"], [])

    def test_same_manufacturer_lot_can_have_two_receipts(self):
        events, links, metadata = fixture()
        result = build_material_traceability(events, links, metadata=metadata)
        incident = build_incident_preview(result, events, links, self.incident("supplier_lot", "O1"))
        self.assertEqual(incident["receipt_ids"], ["E1", "E2"])
        self.assertEqual(incident["potential_production_lot_ids"], ["P1", "P2"])
        self.assertNotIn("P3", incident["potential_lot_ids"])

    def test_receipt_scope_does_not_recall_another_delivery(self):
        events, links, metadata = fixture()
        result = build_material_traceability(events, links, metadata=metadata)
        incident = build_incident_preview(result, events, links, self.incident("receipt", "E1"))
        self.assertEqual(incident["potential_production_lot_ids"], ["P1"])
        self.assertEqual(incident["impact_status"], "exposure_only_no_resimulation")

    def test_partial_origin_keeps_unknown_remainder_and_conservative_scope(self):
        events, links, metadata = fixture()
        metadata["allocations"][0]["quantity"] = 20
        result = build_material_traceability(events, links, metadata=metadata)
        self.assertEqual(result["receipts"]["E1"]["unknown_origin_qty"], 40)
        incident = build_incident_preview(result, events, links, self.incident("supplier_lot", "O1"))
        self.assertIn("P1", incident["potential_production_lot_ids"])
        self.assertNotIn("defective_output_qty", incident)

    def test_containers_are_independent_and_not_invented_from_a_capacity(self):
        events, links, metadata = fixture()
        metadata["handling_units"] = [dict(id="PALLET-1", kind="palette", status="observed",
            source_reference="receiving_log:test", contents=[dict(receipt_id="E1", quantity=60, uom="UN")])]
        result = build_material_traceability(events, links, metadata=metadata)
        incident = build_incident_preview(result, events, links, self.incident("handling_unit", "PALLET-1"))
        self.assertEqual(incident["potential_production_lot_ids"], ["P1"])
        self.assertEqual(len(result["receipts"]["E1"]["handling_units"]), 1)

    def test_native_shipment_incident_does_not_expose_other_source_shipments(self):
        events, links, metadata = fixture()
        events.append(dict(event_id="SOURCE", lot_id="SUPPLIER-STOCK", item_id="item:RM", uom="UN",
                           day=0, qty=200, event_type="opening_stock", node_id="SUP"))
        events.append(dict(event_id="SEND", lot_id="SUPPLIER-STOCK", event_type="lane_ship",
                           qty=60, day=1, risk_decision_day=0, shipment_id="S1", risk_event_ids="RISK-1"))
        for child, qty in [("R1", 60), ("R2", 40), ("R3", 50)]:
            links.append(dict(link_type="transport", parent_lot_id="SUPPLIER-STOCK", child_lot_id=child,
                              parent_qty=qty, child_qty=qty))
        result = build_material_traceability(events, links, metadata=metadata)
        incident = result["incidents"][0]
        self.assertEqual(incident["seed_lot_ids"], ["R1"])
        self.assertEqual(incident["potential_production_lot_ids"], ["P1"])
        self.assertEqual(incident["status"], "engine_recorded")
        self.assertEqual(incident["day"], 0)

    def test_split_and_merge_paths_are_deduplicated(self):
        events, links, metadata = fixture()
        links.extend([dict(link_type="transport", parent_lot_id=p, child_lot_id="MIX", parent_qty=10,
                           child_qty=20) for p in ("P1", "P2")])
        result = build_material_traceability(events, links, metadata=metadata)
        incident = build_incident_preview(result, events, links, self.incident("supplier_lot", "O1"))
        self.assertEqual(incident["potential_lot_ids"].count("MIX"), 1)

    def test_transport_split_preserves_known_origin_without_a_new_manufacturer_lot(self):
        events, links, metadata = fixture()
        events.append(dict(event_id="E7", lot_id="R4", event_type="lane_receipt", qty=10, uom="UN",
                           day=5, item_id="item:RM", node_id="OTHER"))
        links.append(dict(link_type="transport", parent_lot_id="R1", child_lot_id="R4", parent_qty=10, child_qty=10))
        result = build_material_traceability(events, links, metadata=metadata)
        self.assertEqual(result["receipts"]["E7"]["origins"],
                         [dict(origin_id="O1", quantity=10, basis="transport_genealogy")])
        self.assertEqual(result["receipts"]["E7"]["unknown_origin_qty"], 0)

    def test_mixed_parent_split_does_not_invent_physical_origin_quantities(self):
        events, links, metadata = fixture()
        metadata["origins"].append({**metadata["origins"][0], "id": "O2", "batch_number": "OTHER"})
        metadata["allocations"][0]["quantity"] = 30
        metadata["allocations"].append(dict(receipt_id="E1", origin_id="O2", quantity=30, uom="UN"))
        events.append(dict(event_id="E7", lot_id="R4", event_type="lane_receipt", qty=10, uom="UN",
                           day=5, item_id="item:RM", node_id="OTHER"))
        links.append(dict(link_type="transport", parent_lot_id="R1", child_lot_id="R4", parent_qty=10, child_qty=10))
        result = build_material_traceability(events, links, metadata=metadata)
        self.assertEqual(result["receipts"]["E7"]["origins"], [])
        self.assertEqual(result["receipts"]["E7"]["possible_origin_ids"], ["O1", "O2"])
        self.assertEqual(result["receipts"]["E7"]["unknown_origin_qty"], 10)

    def test_invalid_metadata_is_rejected(self):
        events, links, baseline = fixture()
        for value in [61, -1, 0, 1.5, True, float("nan"), float("inf")]:
            with self.subTest(value=value):
                metadata = deepcopy(baseline)
                metadata["allocations"][0]["quantity"] = value
                with self.assertRaises(ValueError):
                    build_material_traceability(events, links, metadata=metadata)
        for field, value in [("uom", "KG"), ("origin_id", "absent"), ("receipt_id", "absent")]:
            with self.subTest(field=field):
                metadata = deepcopy(baseline)
                metadata["allocations"][0][field] = value
                with self.assertRaises(ValueError):
                    build_material_traceability(events, links, metadata=metadata)

    def test_overconsumption_is_rejected(self):
        events, links, _ = fixture()
        links[0]["parent_qty"] = 61
        with self.assertRaisesRegex(ValueError, "more than received"):
            build_material_traceability(events, links)

    def test_duplicate_origin_or_receipt_is_rejected(self):
        events, links, metadata = fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate event"):
            build_material_traceability(events + [events[0]], links)
        metadata["origins"].append({**metadata["origins"][0], "id": "O2"})
        with self.assertRaisesRegex(ValueError, "one origin identity"):
            build_material_traceability(events, links, metadata=metadata)

    def test_scope_requires_a_known_identity_and_valid_incident_kind(self):
        events, links, metadata = fixture()
        result = build_material_traceability(events, links, metadata=metadata)
        for target_type, target in [("supplier_lot", "unknown"), ("receipt", "unknown"),
                                    ("handling_unit", "unknown"), ("truck_proposal", "GROUP1")]:
            with self.subTest(target=target_type), self.assertRaises(ValueError):
                build_incident_preview(result, events, links, self.incident(target_type, target))
        delay = {**self.incident("receipt", "E1"), "kind": "transport_delay"}
        with self.assertRaisesRegex(ValueError, "target a shipment"):
            build_incident_preview(result, events, links, delay)

    def test_scenario_never_changes_the_source_ledgers(self):
        events, links, metadata = fixture()
        before = deepcopy((events, links, metadata))
        result = build_material_traceability(events, links, metadata=metadata)
        build_incident_preview(result, events, links, self.incident("receipt", "E1"))
        self.assertEqual((events, links, metadata), before)

    @staticmethod
    def incident(target_type, target_id):
        return dict(id="TEST-RECALL", label="Test only", status="scenario_preview", kind="quality_recall",
                    day=10, source_reference="test:fixture", target_type=target_type, target_id=target_id)
