from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.analysis.component_immobilized_stock import (
    build_component_immobilized_stock_artifacts,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class ComponentImmobilizedStockTest(unittest.TestCase):
    def test_builds_useful_and_immobilized_stock_without_fallback_prices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            graph_path = root / "graph.json"
            _write_json(
                graph_path,
                {
                    "nodes": [
                        {
                            "id": "S",
                            "type": "supplier_dc",
                        },
                        {
                            "id": "M",
                            "type": "factory",
                            "inventory": {
                                "states": [
                                    {
                                        "item_id": "item:A",
                                        "uom": "UN",
                                        "holding_cost": {
                                            "unit_value_basis": 2.0,
                                            "source": "source_price",
                                        },
                                    },
                                    {
                                        "item_id": "item:B",
                                        "uom": "UN",
                                        "holding_cost": {
                                            "unit_value_basis": 100.0,
                                            "source": "simulation_prep_global_value_median_fallback",
                                        },
                                    },
                                ]
                            },
                            "processes": [
                                {
                                    "outputs": [{"item_id": "item:P"}],
                                    "inputs": [
                                        {"item_id": "item:A"},
                                        {"item_id": "item:B"},
                                        {"item_id": "item:C"},
                                    ],
                                }
                            ],
                        },
                    ],
                    "edges": [
                        {
                            "from": "S",
                            "to": "M",
                            "items": ["item:C"],
                            "order_terms": {
                                "sell_price": 30.0,
                                "price_base": 10.0,
                                "quantity_unit": "UN",
                            },
                        }
                    ],
                },
            )
            stock_rows = [
                {"day": 0, "node_id": "M", "item_id": "item:A", "stock_end_of_day": 10},
                {"day": 0, "node_id": "M", "item_id": "item:B", "stock_end_of_day": 10},
                {"day": 0, "node_id": "M", "item_id": "item:C", "stock_end_of_day": 5},
            ]
            mrp_rows = [
                {"day": 0, "node_id": "M", "item_id": "item:A", "target_stock_qty": 4},
                {"day": 0, "node_id": "M", "item_id": "item:B", "target_stock_qty": 4},
                {"day": 0, "node_id": "M", "item_id": "item:C", "target_stock_qty": 1},
            ]
            _write_csv(run_dir / "data" / "production_input_stocks_daily.csv", stock_rows)
            _write_csv(run_dir / "data" / "mrp_trace_daily.csv", mrp_rows)

            summary = build_component_immobilized_stock_artifacts(
                run_dir=run_dir,
                graph_path=graph_path,
                threshold_modes=("target_stock",),
            )

            self.assertEqual(summary["daily_rows"], 1)
            with (run_dir / "data" / "component_immobilized_stock_daily.csv").open(encoding="utf-8") as handle:
                daily = list(csv.DictReader(handle))
            self.assertEqual(len(daily), 1)
            self.assertEqual(daily[0]["component_count"], "3")
            self.assertEqual(daily[0]["priced_component_count"], "2")
            self.assertAlmostEqual(float(daily[0]["stock_value_eur"]), 35.0)
            self.assertAlmostEqual(float(daily[0]["useful_stock_value_eur"]), 11.0)
            self.assertAlmostEqual(float(daily[0]["immobilized_stock_value_eur"]), 24.0)

            with (run_dir / "data" / "component_immobilized_stock_components_daily.csv").open(
                encoding="utf-8"
            ) as handle:
                detail = list(csv.DictReader(handle))
            self.assertEqual({row["component_item_id"] for row in detail}, {"item:A", "item:C"})


if __name__ == "__main__":
    unittest.main()
