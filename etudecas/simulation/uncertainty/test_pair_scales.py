import unittest

from etudecas.simulation.analysis_batch_common import apply_scales


class PairScaleTests(unittest.TestCase):
    def test_applies_scales_only_to_selected_supplier_item_lane(self) -> None:
        graph = {
            "scenarios": [{"id": "scn:BASE", "demand": []}],
            "nodes": [
                {
                    "id": "SDC-S1",
                    "type": "supplier_dc",
                    "inventory": {
                        "states": [
                            {"item_id": "item:A", "initial": 100.0},
                            {"item_id": "item:B", "initial": 100.0},
                        ]
                    },
                    "simulation_constraints": {},
                },
                {"id": "M-1", "type": "factory", "inventory": {"states": []}},
            ],
            "edges": [
                {
                    "id": "A",
                    "type": "transport",
                    "from": "SDC-S1",
                    "to": "M-1",
                    "items": ["item:A"],
                    "lead_time": {"mean": 10.0},
                    "service_level": {"otif": 0.9},
                },
                {
                    "id": "B",
                    "type": "transport",
                    "from": "SDC-S1",
                    "to": "M-1",
                    "items": ["item:B"],
                    "lead_time": {"mean": 10.0},
                    "service_level": {"otif": 0.9},
                },
            ],
        }

        result = apply_scales(
            graph,
            "scn:BASE",
            {},
            supplier_stock_pair_scale={"SDC-S1|M-1|item:A": 0.5},
            supplier_capacity_pair_scale={"SDC-S1|M-1|item:A": 0.8},
            edge_pair_lead_time_scale={"SDC-S1|M-1|item:A": 1.5},
            edge_pair_reliability_scale={"SDC-S1|M-1|item:A": 0.8},
        )

        supplier = result["nodes"][0]
        states = {
            row["item_id"]: row["initial"]
            for row in supplier["inventory"]["states"]
        }
        self.assertEqual(states["item:A"], 50.0)
        self.assertEqual(states["item:B"], 100.0)
        self.assertEqual(
            supplier["simulation_constraints"]["supplier_item_capacity_scale"]["item:A"],
            0.8,
        )
        self.assertEqual(result["edges"][0]["lead_time"]["mean"], 15.0)
        self.assertEqual(result["edges"][1]["lead_time"]["mean"], 10.0)
        self.assertAlmostEqual(result["edges"][0]["service_level"]["otif"], 0.72)
        self.assertAlmostEqual(result["edges"][1]["service_level"]["otif"], 0.9)
