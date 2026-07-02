import unittest

from etudecas.visualization.maps.map_payload_builder import (
    attach_generic_payload_contract,
    build_generic_payload_contract,
    build_payload_layers_manifest,
    merge_hover_payload_maps,
    merge_payload_sections,
    payload_section,
)


class MapPayloadBuilderTest(unittest.TestCase):
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
            }
        )

        self.assertEqual(contract["nodes"], [{"id": "M-1"}])
        self.assertEqual(contract["edges"], [{"id": "E-1"}])
        self.assertEqual(contract["time_series"]["factory"], {"M-1": {"x": [0]}})
        self.assertEqual(contract["events"]["lot_events"], [{"event_id": "evt"}])
        self.assertEqual(contract["lots"]["lots"], {"L": {}})
        self.assertEqual(contract["diagnostics"]["simulation"], {"summary": "ok"})

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
