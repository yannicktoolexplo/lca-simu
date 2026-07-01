from __future__ import annotations

import unittest

from etudecas.case_config import (
    DEFAULT_PRODUCTION_COST_LINE_PROFILES,
    DEFAULT_PRODUCTION_COST_LINE_SHARES,
    DEFAULT_CASE_CONFIG_PATH,
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
                }
            }
        )

        self.assertEqual(config["node_aliases"]["OLD-DC"], "NEW-DC")
        self.assertEqual(config["node_display_labels"]["PFI-1"], "PFI Site")
        self.assertIn("PFI-1", config["upstream_internal_site_ids"])
        self.assertEqual(config["item_reference_notes"]["item:X"], "Item X label")
        self.assertEqual(config["logistics_assumptions"]["item:X"]["unitsPerCase"], 10)

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


if __name__ == "__main__":
    unittest.main()
