from __future__ import annotations

import unittest

from etudecas.simulation.lot_trace import LotTraceItemClassifier


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


if __name__ == "__main__":
    unittest.main()
