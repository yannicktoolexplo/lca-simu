from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.analysis.finished_goods_inventory_value import (
    build_finished_goods_inventory_value_artifacts,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class FinishedGoodsInventoryValueTest(unittest.TestCase):
    def test_builds_factory_dc_and_total_stock_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = root / "graph.json"
            run_dir = root / "run"
            _write_json(
                graph,
                {
                    "nodes": [
                        {
                            "id": "M",
                            "type": "factory",
                            "inventory": {
                                "states": [
                                    {
                                        "item_id": "item:P",
                                        "uom": "UN",
                                        "holding_cost": {"unit_value_basis": 2.0, "source": "standard_cost"},
                                    }
                                ]
                            },
                            "processes": [{"outputs": [{"item_id": "item:P"}], "inputs": [{"item_id": "item:A"}]}],
                        },
                        {
                            "id": "D",
                            "type": "distribution_center",
                            "inventory": {
                                "states": [
                                    {
                                        "item_id": "item:P",
                                        "uom": "UN",
                                        "holding_cost": {
                                            "unit_value_basis": 3.0,
                                            "source": "simulation_prep_global_value_median_fallback",
                                        },
                                    }
                                ]
                            },
                        },
                    ]
                },
            )
            _write_csv(
                run_dir / "data" / "production_output_products_daily.csv",
                [{"day": 0, "node_id": "M", "item_id": "item:P", "stock_end_of_day": 10}],
            )
            _write_csv(
                run_dir / "data" / "production_dc_stocks_daily.csv",
                [{"day": 0, "node_id": "D", "item_id": "item:P", "stock_end_of_day": 5}],
            )

            summary = build_finished_goods_inventory_value_artifacts(run_dir=run_dir, graph_path=graph)

            self.assertEqual(summary["daily_rows"], 3)
            with (run_dir / "data" / "finished_goods_stock_value_daily.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            total = next(row for row in rows if row["location_type"] == "total")
            self.assertEqual(total["product_code"], "P")
            self.assertAlmostEqual(float(total["stock_qty"]), 15.0)
            self.assertAlmostEqual(float(total["stock_value_eur"]), 35.0)
            dc = next(row for row in rows if row["node_id"] == "D")
            self.assertEqual(dc["is_fallback_unit_value"], "True")

    def test_prefers_bom_purchase_production_cost_over_pf_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = root / "graph.json"
            run_dir = root / "run"
            _write_json(
                graph,
                {
                    "nodes": [
                        {
                            "id": "M",
                            "type": "factory",
                            "inventory": {
                                "states": [
                                    {
                                        "item_id": "item:A",
                                        "uom": "KG",
                                        "holding_cost": {"unit_value_basis": 4.0, "source": "purchase_cost"},
                                    },
                                    {
                                        "item_id": "item:P",
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
                                    "batch_size": 10,
                                    "batch_size_unit": "UN",
                                    "outputs": [{"item_id": "item:P"}],
                                    "inputs": [{"item_id": "item:A", "ratio_per_batch": 5, "ratio_unit": "KG"}],
                                }
                            ],
                        },
                        {"id": "D", "type": "distribution_center"},
                    ]
                },
            )
            _write_csv(
                run_dir / "data" / "production_output_products_daily.csv",
                [{"day": 0, "node_id": "M", "item_id": "item:P", "stock_end_of_day": 10}],
            )
            _write_csv(
                run_dir / "data" / "production_dc_stocks_daily.csv",
                [{"day": 0, "node_id": "D", "item_id": "item:P", "stock_end_of_day": 5}],
            )

            build_finished_goods_inventory_value_artifacts(run_dir=run_dir, graph_path=graph)

            with (run_dir / "data" / "finished_goods_stock_value_daily.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            total = next(row for row in rows if row["location_type"] == "total")
            self.assertAlmostEqual(float(total["unit_value_eur"]), 2.0)
            self.assertAlmostEqual(float(total["stock_value_eur"]), 30.0)
            self.assertEqual(total["valuation_status"], "complete_production_cost")
            self.assertEqual(total["is_fallback_unit_value"], "False")


if __name__ == "__main__":
    unittest.main()
