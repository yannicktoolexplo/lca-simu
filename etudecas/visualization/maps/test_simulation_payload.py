from __future__ import annotations

import csv
import tempfile
from pathlib import Path
import unittest

from etudecas.visualization.maps.simulation_payload import (
    build_material_balance_table_rows,
    convert_unit_quantity,
    normalize_unit_label,
    render_material_balance_table_html,
)


class SimulationPayloadTest(unittest.TestCase):
    def test_unit_normalization_and_conversion(self) -> None:
        self.assertEqual(normalize_unit_label("units"), "UN")
        self.assertEqual(convert_unit_quantity(1500.0, "G", "KG"), 1.5)
        self.assertEqual(convert_unit_quantity(2.0, "KG", "G"), 2000.0)
        self.assertEqual(convert_unit_quantity(3.0, "L", "KG"), 3.0)

    def test_material_balance_rows_convert_bom_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            demand_csv = root / "demand.csv"
            input_csv = root / "inputs.csv"
            output_csv = root / "outputs.csv"
            shipments_csv = root / "shipments.csv"
            _write_csv(
                demand_csv,
                ["node_id", "item_id", "day", "demand_qty", "served_qty"],
                [{"node_id": "C-1", "item_id": "item:PF", "day": "0", "demand_qty": "2", "served_qty": "1"}],
            )
            _write_csv(
                input_csv,
                ["node_id", "item_id", "day", "stock_before_production", "stock_end_of_day"],
                [
                    {
                        "node_id": "M-1",
                        "item_id": "item:RM",
                        "day": "0",
                        "stock_before_production": "1",
                        "stock_end_of_day": "0.5",
                    }
                ],
            )
            _write_csv(
                output_csv,
                ["node_id", "item_id", "day", "produced_qty", "stock_end_of_day"],
                [
                    {
                        "node_id": "M-1",
                        "item_id": "item:PF",
                        "day": "0",
                        "produced_qty": "1",
                        "stock_end_of_day": "0",
                    }
                ],
            )
            _write_csv(
                shipments_csv,
                ["src_node_id", "dst_node_id", "item_id", "day", "shipped_qty"],
                [
                    {
                        "src_node_id": "S-1",
                        "dst_node_id": "M-1",
                        "item_id": "item:RM",
                        "day": "0",
                        "shipped_qty": "0.25",
                    }
                ],
            )
            raw = {
                "items": [
                    {"id": "item:PF", "code": "PF-01"},
                    {"id": "item:RM", "code": "RM-01"},
                ],
                "nodes": [
                    {
                        "id": "C-1",
                        "type": "customer",
                        "inventory": {"states": [{"item_id": "item:PF", "initial": 0, "uom": "UN"}]},
                    },
                    {
                        "id": "M-1",
                        "type": "factory",
                        "inventory": {"states": [{"item_id": "item:RM", "initial": 1, "uom": "KG"}]},
                        "processes": [
                            {
                                "batch_size": 1,
                                "outputs": [{"item_id": "item:PF"}],
                                "inputs": [
                                    {
                                        "item_id": "item:RM",
                                        "ratio_per_batch": 500,
                                        "ratio_unit": "G",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }

            rows = build_material_balance_table_rows(
                raw,
                demand_service_csv=demand_csv,
                sim_input_stocks_csv=input_csv,
                sim_output_products_csv=output_csv,
                supplier_shipments_csv=shipments_csv,
            )

        pf_row = next(row for row in rows if row["scope"] == "pf")
        material_row = next(row for row in rows if row["scope"] == "material")
        self.assertEqual(pf_row["planned_qty"], 2.0)
        self.assertEqual(pf_row["delivered_qty"], 1.0)
        self.assertEqual(material_row["unit"], "KG")
        self.assertEqual(material_row["planned_qty"], 1.0)
        self.assertEqual(material_row["consumed_qty"], 0.5)
        self.assertEqual(material_row["delivered_qty"], 0.25)
        self.assertEqual(material_row["yearly"]["1"]["planned_qty"], 1.0)
        self.assertEqual(material_row["yearly"]["1"]["consumed_qty"], 0.5)

    def test_render_material_balance_empty_state(self) -> None:
        self.assertEqual(
            render_material_balance_table_html([]),
            "<tr><td colspan='13'>Aucune ligne de bilan disponible.</td></tr>",
        )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
