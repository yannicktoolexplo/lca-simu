import csv
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.uncertainty.temporal_propagation import (
    build_temporal_propagation,
)


class TemporalPropagationTests(unittest.TestCase):
    def test_builds_supplier_factory_customer_timing_and_nominal_lot_exposure(self) -> None:
        factor = "supplier_lead_pair::SDC-S1|M-1|item:A"
        days = [0, 1, 2, 3, 4, 5]

        def factor_row(center, low, high):
            return {
                "factor": factor,
                "family": "lead",
                "scope": {
                    "supplier_id": "SDC-S1",
                    "destination_id": "M-1",
                    "item_id": "item:A",
                },
                "center": center,
                "low": low,
                "high": high,
            }

        paired = {
            "schema_version": "paired",
            "scenario_id": "scn:BASE",
            "days": days,
            "factors": [factor],
            "metrics": {
                "supplier_capacity_binding": {
                    "factors": [factor_row([0] * 6, [0] * 6, [0, 2, 3, 0, 0, 0])]
                },
                "production_delay_input_qty": {
                    "factors": [factor_row([0] * 6, [0] * 6, [0, 0, 4, 5, 0, 0])]
                },
                "backlog": {
                    "factors": [factor_row([0] * 6, [0] * 6, [0, 0, 0, 7, 8, 0])]
                },
            },
        }
        graph = {
            "nodes": [
                {"id": "SDC-S1", "type": "supplier_dc"},
                {
                    "id": "M-1",
                    "type": "factory",
                    "processes": [
                        {
                            "inputs": [{"item_id": "item:A"}],
                            "outputs": [{"item_id": "item:PF"}],
                        }
                    ],
                },
                {"id": "DC-1", "type": "distribution_center"},
                {"id": "C-1", "type": "customer"},
            ],
            "edges": [
                {"id": "e1", "from": "SDC-S1", "to": "M-1"},
                {"id": "e2", "from": "M-1", "to": "DC-1"},
                {"id": "e3", "from": "DC-1", "to": "C-1"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            lot_path = Path(tmp) / "lots.csv"
            with lot_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "day", "event_type", "lot_id", "node_id", "item_id",
                        "qty", "uom", "production_campaign_id",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "day": 2,
                    "event_type": "production_consume",
                    "lot_id": "LOT-MP",
                    "node_id": "M-1",
                    "item_id": "item:A",
                    "qty": 2,
                    "uom": "KG",
                    "production_campaign_id": "CMP-1",
                })
                writer.writerow({
                    "day": 3,
                    "event_type": "production_output",
                    "lot_id": "LOT-PF",
                    "node_id": "M-1",
                    "item_id": "item:PF",
                    "qty": 10,
                    "uom": "UN",
                    "production_campaign_id": "CMP-1",
                })
            payload = build_temporal_propagation(
                paired,
                graph,
                lot_events_csv=lot_path,
            )

        result = payload["factors"][0]
        self.assertEqual(result["stage_first_effect_days"]["supplier"], 1)
        self.assertEqual(result["stage_first_effect_days"]["factory"], 2)
        self.assertEqual(result["stage_first_effect_days"]["customer"], 3)
        self.assertEqual(result["outcome"], "client_impacted")
        self.assertEqual(result["network_path"]["node_ids"], ["SDC-S1", "M-1", "DC-1", "C-1"])
        self.assertEqual(
            {row["lot_id"] for row in result["nominally_exposed_lots"]},
            {"LOT-MP", "LOT-PF"},
        )
        self.assertEqual(result["lot_attribution_basis"], "nominal_time_window_overlap_not_causal")


if __name__ == "__main__":
    unittest.main()
