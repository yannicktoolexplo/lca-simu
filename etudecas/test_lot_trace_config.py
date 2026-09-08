from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
