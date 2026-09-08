from __future__ import annotations

import unittest
from decimal import Decimal

from etudecas.simulation.lot_policy import (
    CandidateLotQuantity,
    Confidence,
    IncompatibleUomError,
    PolicyScope,
    Quantity,
    TransportRequest,
    UomPolicy,
    available_component_quantity,
    canonical_lot_policy_registry,
    consolidate_transport_requests,
    convert_quantity,
    normalize_physical_quantity,
    preflight_candidate,
    preflight_graph,
    required_component_quantity,
    resolve_canonical_lane_lot,
    resolve_internal_dispatch_multiple,
)


class CanonicalLotPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = canonical_lot_policy_registry()

    def test_708073_procurement_is_5000_kg(self) -> None:
        policy = self.registry.require("item:708073")
        rule = policy.procurement[0]

        self.assertEqual(rule.moq, Decimal("5000"))
        self.assertEqual(rule.order_multiple, Decimal("5000"))
        self.assertEqual(rule.uom, "KG")
        self.assertEqual(rule.source.confidence, Confidence.CONFIRMED)

    def test_mass_conversion_preserves_quantity(self) -> None:
        self.assertEqual(convert_quantity("5000", "KG", "G"), Decimal("5000000"))
        self.assertEqual(convert_quantity("5000000", "G", "KG"), Decimal("5000"))
        with self.assertRaises(IncompatibleUomError):
            convert_quantity("5000", "KG", "UN")

    def test_preflight_rejects_708073_5m_kg_but_accepts_5m_g(self) -> None:
        bad = CandidateLotQuantity(
            item_id="item:708073",
            scope=PolicyScope.PROCUREMENT,
            quantity="5000000",
            uom="KG",
            supplier_id="SDC-VD0520115A",
            destination_id="M-1430",
            source_ref="fixture",
            field_name="standard_order_qty",
        )
        correct_base_uom = CandidateLotQuantity(
            item_id="item:708073",
            scope=PolicyScope.PROCUREMENT,
            quantity="5000000",
            uom="G",
            supplier_id="SDC-VD0520115A",
            destination_id="M-1430",
            source_ref="fixture",
            field_name="standard_order_qty",
        )

        bad_codes = {issue.code for issue in preflight_candidate(bad, self.registry)}
        self.assertIn("likely_mass_conversion_applied_without_uom_change", bad_codes)
        self.assertEqual(preflight_candidate(correct_base_uom, self.registry), [])

    def test_773474_uses_production_lot_and_weekly_internal_transfer(self) -> None:
        policy = self.registry.require("item:773474")
        production = policy.production[0]
        transport = policy.transport[0]

        self.assertEqual(production.fixed_qty, Decimal("3200000"))
        self.assertEqual(production.uom, "G")
        self.assertEqual(transport.window_days, 7)
        self.assertEqual(transport.minimum_dispatch_qty, Decimal("3200000"))
        self.assertEqual(transport.dispatch_multiple, Decimal("3200000"))
        self.assertFalse(policy.procurement)

    def test_preflight_rejects_773474_one_gram_internal_dispatch(self) -> None:
        candidate = CandidateLotQuantity(
            item_id="item:773474",
            scope=PolicyScope.TRANSPORT,
            quantity="1",
            uom="G",
            origin_id="SDC-1450",
            destination_id="M-1430",
            source_ref="fixture",
            field_name="standard_order_qty",
        )

        codes = {issue.code for issue in preflight_candidate(candidate, self.registry)}
        self.assertEqual(
            codes,
            {"below_transport_dispatch_minimum", "not_transport_dispatch_multiple"},
        )

    def test_weekly_transport_consolidation_keeps_demand_and_dispatch_distinct(self) -> None:
        policy = self.registry.require("item:773474").transport[0]
        plans = consolidate_transport_requests(
            [
                TransportRequest(
                    request_id="REQ-1",
                    day=1,
                    item_id="item:773474",
                    origin_id="SDC-1450",
                    destination_id="M-1430",
                    quantity=Quantity("1000000", "G"),
                ),
                TransportRequest(
                    request_id="REQ-2",
                    day=5,
                    item_id="item:773474",
                    origin_id="SDC-1450",
                    destination_id="M-1430",
                    quantity=Quantity("500", "KG"),
                ),
                TransportRequest(
                    request_id="REQ-3",
                    day=8,
                    item_id="item:773474",
                    origin_id="SDC-1450",
                    destination_id="M-1430",
                    quantity=Quantity("3400000", "G"),
                ),
            ],
            policy,
        )

        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].demand_qty, Quantity("1500000", "G"))
        self.assertEqual(plans[0].dispatch_qty, Quantity("3200000", "G"))
        self.assertEqual(plans[0].planned_overage_qty, Quantity("1700000", "G"))
        self.assertEqual(plans[0].request_ids, ("REQ-1", "REQ-2"))
        self.assertEqual(plans[1].dispatch_qty, Quantity("6400000", "G"))

    def test_graph_preflight_detects_both_known_source_failures(self) -> None:
        graph = {
            "edges": [
                {
                    "id": "supplier-708073",
                    "from": "SDC-VD0520115A",
                    "to": "M-1430",
                    "items": ["item:708073"],
                    "attrs": {
                        "standard_order_qty": 5000000,
                        "standard_order_uom": "KG",
                    },
                },
                {
                    "id": "internal-773474",
                    "from": "SDC-1450",
                    "to": "M-1430",
                    "items": ["item:773474"],
                    "attrs": {
                        "standard_order_qty": 1,
                        "standard_order_uom": "G",
                    },
                },
            ]
        }

        issues = preflight_graph(graph, self.registry)
        by_item = {}
        for issue in issues:
            by_item.setdefault(issue.item_id, set()).add(issue.code)

        self.assertIn(
            "likely_mass_conversion_applied_without_uom_change",
            by_item["item:708073"],
        )
        self.assertIn(
            "below_transport_dispatch_minimum",
            by_item["item:773474"],
        )

    def test_uom_policy_rejects_cross_dimension_allowed_uoms(self) -> None:
        with self.assertRaises(ValueError):
            UomPolicy(base_uom="G", allowed_uoms=("G", "UN"))

    def test_finished_product_lot_does_not_override_mrp_lane_quantum(self) -> None:
        pharma = resolve_canonical_lane_lot(
            origin_id="M-1430",
            destination_id="DC-1920",
            item_id="268967",
            lane_uom="UN",
        )
        cosmetic = resolve_canonical_lane_lot(
            origin_id="M-1810",
            destination_id="DC-1920",
            item_id="268091",
            lane_uom="UN",
        )

        self.assertIsNone(pharma)
        self.assertIsNone(cosmetic)

    def test_finished_product_lot_only_consolidates_internal_dispatch(self) -> None:
        pharma = resolve_internal_dispatch_multiple(
            origin_id="M-1430",
            destination_id="DC-1920",
            item_id="268967",
            lane_uom="UN",
        )
        cosmetic = resolve_internal_dispatch_multiple(
            origin_id="M-1810",
            destination_id="DC-1920",
            item_id="268091",
            lane_uom="UN",
        )

        self.assertIsNotNone(pharma)
        self.assertEqual(pharma.quantity, 107800)
        self.assertEqual(pharma.scope, "internal_physical_dispatch")
        self.assertIsNotNone(cosmetic)
        self.assertEqual(cosmetic.quantity, 14400)

    def test_countable_component_requirement_is_rounded_up(self) -> None:
        self.assertEqual(required_component_quantity(107800, 8 / 1000, "UN"), 863)
        self.assertEqual(available_component_quantity(862.9, "UN"), 862)
        self.assertEqual(normalize_physical_quantity(2.5, "UN"), 3)
        self.assertAlmostEqual(
            required_component_quantity(107800, 0.009654718, "G"),
            1040.7786,
            places=6,
        )


if __name__ == "__main__":
    unittest.main()
