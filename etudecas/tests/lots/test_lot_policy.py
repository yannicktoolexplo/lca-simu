"""Regression tests for lot policy."""

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
from etudecas.case_config import (
    DEFAULT_PRODUCTION_COST_LINE_PROFILES,
    DEFAULT_PRODUCTION_COST_LINE_SHARES,
    DEFAULT_PRODUCTION_COST_UNIT_RATES,
    DEFAULT_CASE_CONFIG_PATH,
    REFERENCE_TRANSITIONS,
    build_lot_trace_config,
    canonical_node_id,
    display_node_id,
    is_upstream_internal_site,
    load_case_config,
    standard_order_override,
)
from etudecas.simulation.lot_trace import LotTraceItemClassifier
from collections import defaultdict
from etudecas.simulation.engine.run_first_simulation import (
    LOT_TRACE_EPS,
    LotLedger,
    launch_campaign_qty,
    normalize_unit,
    process_lot_policy,
)
from etudecas.simulation.lot_trace.campaigns import build_production_campaign_rows
from etudecas.simulation.lot_trace.causal_links import build_lot_causal_link_rows


# Test lot policy

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


# Test lot trace config

class LotTraceConfigTest(unittest.TestCase):
    def test_default_config_can_be_overridden_from_graph(self) -> None:
        config = build_lot_trace_config(
            {
                "lot_trace_config": {
                    "node_aliases": {"OLD-DC": "NEW-DC"},
                    "node_display_labels": {"PFI-1": "PFI Site"},
                    "upstream_internal_site_ids": ["PFI-1"],
                    "item_reference_notes": {"item:X": "Item X label"},
                    "logistics_assumptions": {
                        "item:X": {
                            "unitsPerCase": 10,
                            "centralCasesPerPallet": 20,
                        }
                    },
                    "reference_transitions": [
                        {
                            "new_item_id": "X",
                            "old_item_id": "Y",
                            "scope": "packaging",
                        }
                    ],
                }
            }
        )

        self.assertEqual(config["node_aliases"]["OLD-DC"], "NEW-DC")
        self.assertEqual(config["node_display_labels"]["PFI-1"], "PFI Site")
        self.assertIn("PFI-1", config["upstream_internal_site_ids"])
        self.assertEqual(config["item_reference_notes"]["item:X"], "Item X label")
        self.assertEqual(config["logistics_assumptions"]["item:X"]["unitsPerCase"], 10)
        self.assertIn(
            {
                "new_item_id": "item:X",
                "old_item_id": "item:Y",
                "scope": "packaging",
            },
            config["reference_transitions"],
        )

    def test_common_case_helpers_are_centralized(self) -> None:
        self.assertTrue(DEFAULT_CASE_CONFIG_PATH.exists())
        self.assertEqual(load_case_config()["case_id"], "data_poc")
        self.assertEqual(canonical_node_id("DC-1910"), "DC-1920")
        self.assertEqual(display_node_id("SDC-1450"), "D-1450")
        self.assertTrue(is_upstream_internal_site("SDC-1450"))
        self.assertEqual(
            standard_order_override("SDC-VD0520115A", "M-1430", "item:708073")["qty"],
            5000.0,
        )
        self.assertIn(("M-1430", "item:268967"), DEFAULT_PRODUCTION_COST_LINE_SHARES)
        self.assertIn(("SDC-1450", "item:773474"), DEFAULT_PRODUCTION_COST_LINE_PROFILES)
        self.assertGreater(
            DEFAULT_PRODUCTION_COST_UNIT_RATES[("M-1430", "item:268967")],
            0.0,
        )
        transition_344135 = next(
            row for row in REFERENCE_TRANSITIONS if row.get("new_item_id") == "item:344135"
        )
        self.assertEqual(transition_344135["old_item_id"], "item:EX-344135")
        self.assertEqual(transition_344135["node_id"], "M-1430")
        self.assertEqual(transition_344135["initial_stock_qty"], 107800.0)
        self.assertEqual(transition_344135["consume_policy"], "use_old_until_new_stock_available")


# Test lot trace rules

class LotTraceRulesTest(unittest.TestCase):
    def test_item_classifier_extracts_families_and_scopes_from_raw_graph(self) -> None:
        raw = {
            "nodes": [
                {"id": "S-RAW", "type": "supplier_dc"},
                {
                    "id": "M-UP",
                    "type": "factory",
                    "processes": [
                        {
                            "inputs": [{"item_id": "item:RM"}],
                            "outputs": [{"item_id": "item:PFI"}],
                        }
                    ],
                },
                {
                    "id": "M-1",
                    "type": "factory",
                    "processes": [
                        {
                            "inputs": [{"item_id": "item:PFI"}],
                            "outputs": [{"item_id": "item:PF"}],
                        }
                    ],
                },
                {"id": "DC-1", "type": "distribution_center"},
                {"id": "C-1", "type": "customer"},
            ],
            "edges": [
                {"from": "S-RAW", "to": "M-UP", "items": ["item:RM"]},
                {"from": "M-UP", "to": "M-1", "items": ["item:PFI"]},
                {"from": "M-1", "to": "DC-1", "items": ["item:PF"]},
                {"from": "DC-1", "to": "C-1", "items": ["item:PF"]},
            ],
        }

        classifier = LotTraceItemClassifier.from_raw(raw)

        self.assertEqual(classifier.item_sets.final_good_item_ids, frozenset({"item:PF"}))
        self.assertEqual(classifier.item_sets.semi_finished_item_ids, frozenset({"item:PFI"}))
        self.assertEqual(classifier.item_family("item:PF", "M-1"), "finished_product")
        self.assertEqual(classifier.item_family("item:PFI", "M-1"), "semi_finished")
        self.assertEqual(classifier.item_family("item:RM", "S-RAW"), "raw_material")
        self.assertEqual(
            classifier.scope_for_creation(
                {"event_type": "production_output", "item_id": "item:PFI", "node_id": "M-UP"}
            ),
            ("semi_finished", "Semi-fini produit"),
        )
        self.assertEqual(
            classifier.scope_for_creation(
                {"event_type": "lane_receipt", "item_id": "item:PF", "node_id": "DC-1"}
            ),
            ("finished_product_receipt", "PF recu"),
        )
        self.assertEqual(
            classifier.scope_for_creation(
                {"event_type": "opening_stock", "item_id": "item:RM", "node_id": "S-RAW"}
            ),
            ("raw_material_opening", "MP stock initial"),
        )


# Test lotification acceptance contract

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
            qty=2,
            source_type="acceptance_fixture",
            uom="UN",
        )

        with self.assertRaisesRegex(ValueError, "integral"):
            ledger.create_lot(day=0, node_id="NODE", item_id="ITEM-UN", qty=2.5,
                              source_type="invalid_fraction", uom="UN")
        with self.assertRaisesRegex(ValueError, "integral"):
            ledger.consume(day=1, node_id="NODE", item_id="ITEM-UN", qty=0.5,
                           event_type="demand_service", uom="UN")

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
