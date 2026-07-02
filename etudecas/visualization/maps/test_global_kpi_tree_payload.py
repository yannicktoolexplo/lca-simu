from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps import build_supplychain_worldmap as worldmap_builder
from etudecas.visualization.maps.global_kpi_tree_payload import build_global_kpi_tree_payload


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class GlobalKpiTreePayloadTest(unittest.TestCase):
    def test_builder_reexports_extracted_payload_builder(self) -> None:
        self.assertIs(worldmap_builder.build_global_kpi_tree_payload, build_global_kpi_tree_payload)

    def test_cost_supply_is_rebuilt_from_components_when_total_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily_csv = root / "first_simulation_daily.csv"
            demand_csv = root / "production_demand_service_daily.csv"
            constraint_csv = root / "production_constraint_daily.csv"

            write_csv(
                daily_csv,
                [
                    "day",
                    "demand",
                    "served",
                    "backlog_end",
                    "holding_cost_day",
                    "warehouse_operating_cost_day",
                    "inventory_risk_cost_day",
                    "operational_transport_cost_day",
                    "operational_purchase_cost_day",
                    "production_cost_day",
                ],
                [
                    {
                        "day": 0,
                        "demand": 100,
                        "served": 100,
                        "backlog_end": 0,
                        "holding_cost_day": 10,
                        "warehouse_operating_cost_day": 5,
                        "inventory_risk_cost_day": 1,
                        "operational_transport_cost_day": 4,
                        "operational_purchase_cost_day": 20,
                        "production_cost_day": 30,
                    },
                    {
                        "day": 1,
                        "demand": 100,
                        "served": 95,
                        "backlog_end": 5,
                        "holding_cost_day": 12,
                        "warehouse_operating_cost_day": 5,
                        "inventory_risk_cost_day": 1,
                        "operational_transport_cost_day": 6,
                        "operational_purchase_cost_day": 22,
                        "production_cost_day": 32,
                    },
                ],
            )
            write_csv(
                demand_csv,
                ["day", "item_id", "demand_qty", "required_with_backlog_qty", "served_qty", "backlog_end_qty"],
                [
                    {"day": 0, "item_id": "item:PF", "demand_qty": 100, "required_with_backlog_qty": 100, "served_qty": 100, "backlog_end_qty": 0},
                    {"day": 1, "item_id": "item:PF", "demand_qty": 100, "required_with_backlog_qty": 105, "served_qty": 95, "backlog_end_qty": 5},
                ],
            )
            write_csv(
                constraint_csv,
                [
                    "day",
                    "node_id",
                    "output_item_id",
                    "desired_qty",
                    "planned_qty_after_lot_rule",
                    "actual_qty",
                    "shortfall_vs_desired_qty",
                    "shortfall_vs_lot_plan_qty",
                    "binding_cause",
                ],
                [
                    {"day": 0, "node_id": "M-1", "output_item_id": "item:PF", "desired_qty": 100, "planned_qty_after_lot_rule": 100, "actual_qty": 100, "shortfall_vs_desired_qty": 0, "shortfall_vs_lot_plan_qty": 0, "binding_cause": ""},
                    {"day": 1, "node_id": "M-1", "output_item_id": "item:PF", "desired_qty": 100, "planned_qty_after_lot_rule": 100, "actual_qty": 95, "shortfall_vs_desired_qty": 5, "shortfall_vs_lot_plan_qty": 5, "binding_cause": "input_shortage"},
                ],
            )

            payload = build_global_kpi_tree_payload(daily_csv, demand_csv, constraint_csv)

        self.assertIsNotNone(payload)
        cost_group = next(group for group in payload["groups"] if group["id"] == "cost")
        total_series = next(series for series in cost_group["secondary"] if series["label"] == "Cout operationnel total")
        self.assertEqual(total_series["values"], [70.0, 78.0])
        self.assertEqual(cost_group["summary"][0]["label"], "Cout operationnel total")
        self.assertEqual(cost_group["summary"][0]["value"], "148.0")


if __name__ == "__main__":
    unittest.main()
