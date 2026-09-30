import unittest

from etudecas.visualization.maps.map_payload_builder import (
    attach_generic_payload_contract,
    build_generic_payload_contract,
    build_payload_layers_manifest,
    compact_graph_payload,
    merge_hover_payload_maps,
    merge_payload_sections,
    payload_section,
)


class MapPayloadBuilderTest(unittest.TestCase):
    def test_gaillac_label_preserves_factory_and_real_inventory(self) -> None:
        raw = {"nodes": [
            {"id": "SDC-1450", "type": "factory", "name": "Gaillac", "attrs": {
                "physical_site_code": "1450", "site_functions": ["storage", "manufacturing"]},
             "inventory": {"states": [{"item_id": "item:021081"}]}},
            {"id": "DC-1450", "type": "distribution", "inventory": {"states": []}},
            {"id": "DC-other", "type": "distribution", "inventory": {"states": [
                {"item_id": "item:001893", "qty": 0}]}},
        ], "edges": []}
        nodes = {row['id']: row for row in compact_graph_payload(raw)['nodes']}
        self.assertEqual(nodes['SDC-1450']['type'], 'factory')
        self.assertEqual(nodes['SDC-1450']['name'], 'Gaillac — fabrication et stockage')
        self.assertNotIn('DC-1450', nodes)
        self.assertIn('DC-other', nodes)
        self.assertEqual(raw['nodes'][0]['name'], 'Gaillac')

    def test_site_flow_kinds_separate_supply_production_and_release(self) -> None:
        from etudecas.visualization.maps.source_comparison import site_flow_kind
        cases = [
            ({'event_type': 'external_procurement_receipt', 'source_type': 'source_boundary_receipt'}, 'simplified_supply'),
            ({'event_type': 'external_procurement_receipt', 'source_type': 'supplier'}, 'external_receipt'),
            ({'event_type': 'opening_purchase_order_receipt'}, 'external_receipt'),
            ({'event_type': 'opening_production_order'}, 'production_output'),
            ({'event_type': 'production_output'}, 'production_output'),
            ({'event_type': 'stock_availability_release'}, 'availability_release'),
            ({'event_type': 'stock_availability_hold'}, None),
            ({'event_type': 'production_consume_reference_transition'}, 'core_consumption'),
            ({'event_type': 'external_component_consume'}, 'other_consumption'),
            ({'event_type': 'shipment_reserve'}, None),
            ({'event_type': 'lane_ship'}, 'transport_shipment'),
            ({'event_type': 'lane_receipt'}, 'transport_receipt'),
        ]
        for row, expected in cases:
            with self.subTest(row=row):
                self.assertEqual(site_flow_kind(row), expected)

    def test_chain_equivalent_converts_bom_units_and_distinct_stock_positions(self) -> None:
        from etudecas.visualization.maps.source_comparison import chain_bom_factors, chain_stock_equivalence
        graph = {'nodes': [
            {'id': 'SDC-1450', 'processes': [{'outputs': [{'item_id': 'item:773474'}],
                'inputs': [{'item_id': 'item:021081', 'ratio_per_batch': 2, 'ratio_unit': 'KG'}],
                'batch_size': 1000, 'batch_size_unit': 'G'}]},
            {'id': 'M-1430', 'processes': [{'outputs': [{'item_id': 'item:268967'}],
                'inputs': [{'item_id': 'item:773474', 'ratio_per_batch': 500, 'ratio_unit': 'G'}],
                'batch_size': 1, 'batch_size_unit': 'UN'}]}]}
        factors = chain_bom_factors(graph)
        self.assertEqual(factors['raw_kg_per_intermediate_kg'], 2)
        self.assertEqual(factors['intermediate_kg_per_pf'], .5)
        quantities = {'021081/1450': 8, '773474/1450': 3, '773474/1430': 4, '268967/1920': 5}
        pairs = {key: {'observed': [[0, qty, 1], [1, qty, 2]],
            'simulations': {'nominal': {'stock': [[0, 0, 0, 0, 0, qty / 2]]}}}
            for key, qty in quantities.items()}
        rows = chain_stock_equivalence(pairs, {'nominal': {'chain_bom_268967': factors}})['rows']
        self.assertEqual(rows[0]['observed_pf_equivalent'], 27)
        self.assertIsNone(rows[0]['simulations']['nominal'])
        self.assertEqual(rows[1]['simulations']['nominal'], 13.5)
        pairs['773474/1430']['observed'] = []
        incomplete = chain_stock_equivalence(pairs, {'nominal': {'chain_bom_268967': factors}})['rows']
        self.assertTrue(all(row['observed_pf_equivalent'] is None for row in incomplete))

    def test_chain_equivalent_missing_bom_is_not_zero_stock(self) -> None:
        from etudecas.visualization.maps.source_comparison import chain_bom_factors, chain_stock_equivalence
        self.assertIsNone(chain_bom_factors({'nodes': []}))
        pairs = {'268967/1920': {'observed': [[5, 100, 2]], 'simulations': {}}}
        row = chain_stock_equivalence(pairs, {'nominal': {'chain_bom_268967': None}})['rows'][0]
        self.assertIsNone(row['observed_pf_equivalent'])
        self.assertIsNone(row['simulations']['nominal'])

    def test_merge_payload_sections_preserves_base_and_applies_sections(self) -> None:
        base = {"nodes": [{"id": "A"}], "edges": []}
        merged = merge_payload_sections(base, [payload_section("diagnostics", {"ok": True})])

        self.assertEqual(base, {"nodes": [{"id": "A"}], "edges": []})
        self.assertEqual(merged["nodes"], [{"id": "A"}])
        self.assertEqual(merged["diagnostics"], {"ok": True})

    def test_payload_section_rejects_empty_key(self) -> None:
        with self.assertRaises(ValueError):
            payload_section("", {})

    def test_generic_contract_maps_legacy_payload_to_generic_surface(self) -> None:
        contract = build_generic_payload_contract(
            {
                "nodes": [{"id": "M-1"}],
                "edges": [{"id": "E-1"}],
                "factory_hover_series": {"M-1": {"x": [0]}},
                "lot_trace": {"events": [{"event_id": "evt"}], "lots": {"L": {}}},
                "simulation_diagnostics": {"summary": "ok"},
                "run_contract": {"schema_version": "etudecas.simulation_run.v1"},
            }
        )

        self.assertEqual(contract["nodes"], [{"id": "M-1"}])
        self.assertEqual(contract["edges"], [{"id": "E-1"}])
        self.assertEqual(contract["schema_version"], "etudecas.map_viewer_payload.v1")
        self.assertEqual(contract["counts"]["lot_events"], 1)
        self.assertEqual(contract["counts"]["lot_nodes"], 1)
        self.assertEqual(contract["run_contract"]["schema_version"], "etudecas.simulation_run.v1")

    def test_payload_layers_manifest_indexes_domains(self) -> None:
        manifest = build_payload_layers_manifest(
            [
                {"domain": "simulation", "counts": {"lots": 2}},
                {"domain": "risk", "counts": {"events": 3}},
            ]
        )

        self.assertEqual(manifest["version"], 1)
        self.assertEqual(manifest["domains"]["simulation"]["counts"]["lots"], 2)
        self.assertEqual(manifest["domains"]["risk"]["counts"]["events"], 3)

    def test_merge_hover_payload_maps_preserves_specific_slots(self) -> None:
        merged = merge_hover_payload_maps(
            {"N1": {"incoming": "new-in"}, "N2": {"compare": "new-compare"}},
            {"N1": {"incoming": "old-in", "outgoing": "old-out"}, "N3": {"third": "old-third"}},
        )

        self.assertEqual(merged["N1"], {"incoming": "new-in", "outgoing": "old-out", "third": None, "fourth": None, "compare": None})
        self.assertEqual(merged["N2"]["compare"], "new-compare")
        self.assertEqual(merged["N3"]["third"], "old-third")

    def test_attach_generic_payload_contract_returns_copy(self) -> None:
        payload = {"nodes": [], "edges": []}
        enriched = attach_generic_payload_contract(payload)

        self.assertNotIn("generic", payload)
        self.assertIn("generic", enriched)


if __name__ == "__main__":
    unittest.main()
