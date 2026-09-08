from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps import build_supplychain_worldmap as worldmap_builder
from etudecas.visualization.maps.build_supplychain_worldmap import (
    write_mrp_safety_arrival_reports,
)
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

    def test_read_only_safety_analysis_does_not_write_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = write_mrp_safety_arrival_reports(
                {"nodes": [], "edges": []},
                output_root=root,
                mrp_trace_rows=[],
                mrp_order_rows=[],
                input_rows=[],
                input_arrival_rows=[],
                write_outputs=False,
            )

            self.assertEqual(summary, {})
            self.assertFalse((root / "reports").exists())

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

    def test_cost_payload_splits_startup_established_and_opening_costs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily_csv = root / "first_simulation_daily.csv"
            demand_csv = root / "production_demand_service_daily.csv"
            constraint_csv = root / "production_constraint_daily.csv"

            daily_rows = []
            demand_rows = []
            constraint_rows = []
            for day in range(35):
                startup = day < 30
                daily_rows.append(
                    {
                        "day": day,
                        "demand": 100,
                        "served": 100,
                        "backlog_end": 0,
                        "holding_cost_day": 20 if startup else 5,
                        "warehouse_operating_cost_day": 10 if startup else 3,
                        "inventory_risk_cost_day": 5 if startup else 2,
                        "operational_transport_cost_day": 15 if startup else 0,
                        "opening_open_order_transport_cost_day": 50 if day == 0 else 0,
                        "operational_purchase_cost_day": 900 if startup else 70,
                        "opening_open_order_purchase_cost_day": 250 if day == 0 else 0,
                        "production_cost_day": 50 if startup else 20,
                    }
                )
                demand_rows.append(
                    {
                        "day": day,
                        "item_id": "item:PF",
                        "demand_qty": 100,
                        "required_with_backlog_qty": 100,
                        "served_qty": 100,
                        "backlog_end_qty": 0,
                    }
                )
                constraint_rows.append(
                    {
                        "day": day,
                        "node_id": "M-1",
                        "output_item_id": "item:PF",
                        "desired_qty": 100,
                        "planned_qty_after_lot_rule": 100,
                        "actual_qty": 100,
                        "shortfall_vs_desired_qty": 0,
                        "shortfall_vs_lot_plan_qty": 0,
                        "binding_cause": "",
                    }
                )

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
                    "opening_open_order_transport_cost_day",
                    "operational_purchase_cost_day",
                    "opening_open_order_purchase_cost_day",
                    "production_cost_day",
                ],
                daily_rows,
            )
            write_csv(
                demand_csv,
                ["day", "item_id", "demand_qty", "required_with_backlog_qty", "served_qty", "backlog_end_qty"],
                demand_rows,
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
                constraint_rows,
            )

            payload = build_global_kpi_tree_payload(daily_csv, demand_csv, constraint_csv)

        self.assertIsNotNone(payload)
        cost_main = next(series for series in payload["main"]["series"] if series["id"] == "cost")
        self.assertEqual(cost_main["values"][0], 1000.0)
        self.assertEqual(cost_main["values"][30], 100.0)

        cost_group = next(group for group in payload["groups"] if group["id"] == "cost")
        summary_by_label = {row["label"]: row["value"] for row in cost_group["summary"]}
        self.assertEqual(summary_by_label["Cout d'amorcage J0-J29"], "30 000.0")
        self.assertEqual(summary_by_label["Regime etabli J30+"], "500.0")
        self.assertEqual(summary_by_label["Moyenne regime etabli"], "100.0")
        self.assertEqual(summary_by_label["Base indice cout"], "regime etabli J30+")
        self.assertEqual(
            summary_by_label["Carnet initial deja engage"],
            "300.0 (achat 250.0, transport 50.0)",
        )

        series_by_label = {series["label"]: series for series in cost_group["secondary"]}
        self.assertEqual(series_by_label["Cout d'amorcage (J0-J29)"]["values"][29], 1000.0)
        self.assertEqual(series_by_label["Cout d'amorcage (J0-J29)"]["values"][30], 0.0)
        self.assertEqual(series_by_label["Regime etabli (J30+)"]["values"][29], 0.0)
        self.assertEqual(series_by_label["Regime etabli (J30+)"]["values"][30], 100.0)
        self.assertEqual(series_by_label["Moyenne regime etabli"]["values"][29], 0.0)
        self.assertEqual(series_by_label["Moyenne regime etabli"]["values"][30], 100.0)
        self.assertEqual(series_by_label["Carnet initial deja engage"]["values"][0], 300.0)
        self.assertEqual(sum(series_by_label["Carnet initial deja engage"]["values"]), 300.0)

    def test_cost_supply_is_reconstructed_from_summary_when_daily_cost_csv_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            summaries_dir = root / "summaries"
            daily_csv = data_dir / "physics_of_decision_kpi_daily.csv"
            demand_csv = data_dir / "production_demand_service_daily.csv"
            constraint_csv = data_dir / "production_constraint_daily.csv"

            write_csv(
                daily_csv,
                ["day", "inventory_cost__actual"],
                [{"day": 0, "inventory_cost__actual": 0}, {"day": 1, "inventory_cost__actual": 0}],
            )
            write_csv(
                demand_csv,
                ["day", "item_id", "demand_qty", "required_with_backlog_qty", "served_qty", "backlog_end_qty"],
                [
                    {"day": 0, "item_id": "item:PF", "demand_qty": 100, "required_with_backlog_qty": 100, "served_qty": 100, "backlog_end_qty": 0},
                    {"day": 1, "item_id": "item:PF", "demand_qty": 100, "required_with_backlog_qty": 100, "served_qty": 100, "backlog_end_qty": 0},
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
                    {"day": 0, "node_id": "M-1", "output_item_id": "item:PF", "desired_qty": 100, "planned_qty_after_lot_rule": 100, "actual_qty": 50, "shortfall_vs_desired_qty": 50, "shortfall_vs_lot_plan_qty": 50, "binding_cause": ""},
                    {"day": 1, "node_id": "M-1", "output_item_id": "item:PF", "desired_qty": 100, "planned_qty_after_lot_rule": 100, "actual_qty": 150, "shortfall_vs_desired_qty": 0, "shortfall_vs_lot_plan_qty": 0, "binding_cause": ""},
                ],
            )
            write_csv(
                data_dir / "production_output_products_daily.csv",
                ["day", "node_id", "item_id", "produced_qty", "stock_end_of_day"],
                [
                    {"day": 0, "node_id": "M-1", "item_id": "item:PF", "produced_qty": 50, "stock_end_of_day": 100},
                    {"day": 1, "node_id": "M-1", "item_id": "item:PF", "produced_qty": 150, "stock_end_of_day": 300},
                ],
            )
            write_csv(
                data_dir / "production_input_stocks_daily.csv",
                ["day", "node_id", "item_id", "stock_end_of_day"],
                [{"day": 0, "node_id": "M-1", "item_id": "item:RM", "stock_end_of_day": 100}],
            )
            write_csv(
                data_dir / "production_dc_stocks_daily.csv",
                ["day", "node_id", "item_id", "stock_end_of_day"],
                [{"day": 1, "node_id": "DC-1", "item_id": "item:PF", "stock_end_of_day": 100}],
            )
            write_csv(
                data_dir / "production_supplier_stocks_daily.csv",
                ["day", "node_id", "item_id", "stock_end_of_day"],
                [{"day": 0, "node_id": "S-1", "item_id": "item:RM", "stock_end_of_day": 200}],
            )
            write_csv(
                data_dir / "production_supplier_shipments_daily.csv",
                ["day", "src_node_id", "dst_node_id", "item_id", "shipped_qty", "transport_cost"],
                [
                    {"day": 0, "src_node_id": "S-1", "dst_node_id": "M-1", "item_id": "item:RM", "shipped_qty": 10, "transport_cost": 10},
                    {"day": 0, "src_node_id": "S-1", "dst_node_id": "M-1", "item_id": "item:RM2", "shipped_qty": 1_000_000, "transport_cost": 0},
                    {"day": 1, "src_node_id": "S-1", "dst_node_id": "M-1", "item_id": "item:RM", "shipped_qty": 30, "transport_cost": 30},
                ],
            )
            write_csv(
                data_dir / "mrp_orders_daily.csv",
                ["day", "release_day", "release_qty"],
                [{"day": 0, "release_day": 0, "release_qty": 25}, {"day": 1, "release_day": 1, "release_qty": 75}],
            )
            summaries_dir.mkdir(parents=True, exist_ok=True)
            (summaries_dir / "first_simulation_summary.json").write_text(
                json.dumps(
                    {
                        "kpis": {
                            "total_holding_cost": 10,
                            "total_warehouse_operating_cost": 20,
                            "total_inventory_risk_cost": 30,
                            "total_transport_cost": 40,
                            "total_purchase_cost": 100,
                            "total_production_cost": 200,
                            "total_cost": 400,
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = build_global_kpi_tree_payload(daily_csv, demand_csv, constraint_csv)

        self.assertIsNotNone(payload)
        cost_group = next(group for group in payload["groups"] if group["id"] == "cost")
        total_series = next(series for series in cost_group["secondary"] if series["label"] == "Cout operationnel total")
        transport_series = next(series for series in cost_group["secondary"] if series["label"] == "Cout de transport pilotable")
        self.assertAlmostEqual(sum(total_series["values"]), 400.0, places=4)
        self.assertEqual(transport_series["values"], [10.0, 30.0])
        self.assertIn("reconstruit", cost_group["summary"][-1]["value"])

    def test_component_immobilized_stock_group_is_added_when_artifact_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            daily_csv = data_dir / "first_simulation_daily.csv"
            demand_csv = data_dir / "production_demand_service_daily.csv"
            constraint_csv = data_dir / "production_constraint_daily.csv"

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
                        "holding_cost_day": 1,
                        "warehouse_operating_cost_day": 1,
                        "inventory_risk_cost_day": 1,
                        "operational_transport_cost_day": 1,
                        "operational_purchase_cost_day": 1,
                        "production_cost_day": 1,
                    },
                    {
                        "day": 1,
                        "demand": 100,
                        "served": 100,
                        "backlog_end": 0,
                        "holding_cost_day": 1,
                        "warehouse_operating_cost_day": 1,
                        "inventory_risk_cost_day": 1,
                        "operational_transport_cost_day": 1,
                        "operational_purchase_cost_day": 1,
                        "production_cost_day": 1,
                    },
                ],
            )
            write_csv(
                demand_csv,
                ["day", "item_id", "demand_qty", "required_with_backlog_qty", "served_qty", "backlog_end_qty"],
                [
                    {"day": 0, "item_id": "item:PF", "demand_qty": 100, "required_with_backlog_qty": 100, "served_qty": 100, "backlog_end_qty": 0},
                    {"day": 1, "item_id": "item:PF", "demand_qty": 100, "required_with_backlog_qty": 100, "served_qty": 100, "backlog_end_qty": 0},
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
                    {"day": 1, "node_id": "M-1", "output_item_id": "item:PF", "desired_qty": 100, "planned_qty_after_lot_rule": 100, "actual_qty": 100, "shortfall_vs_desired_qty": 0, "shortfall_vs_lot_plan_qty": 0, "binding_cause": ""},
                ],
            )
            write_csv(
                data_dir / "component_immobilized_stock_daily.csv",
                [
                    "day",
                    "node_id",
                    "product_item_id",
                    "product_code",
                    "threshold_mode",
                    "stock_value_eur",
                    "useful_stock_value_eur",
                    "immobilized_stock_value_eur",
                    "component_count",
                    "priced_component_count",
                ],
                [
                    {"day": 0, "node_id": "M-1", "product_item_id": "item:PF", "product_code": "PF", "threshold_mode": "target_stock", "stock_value_eur": 100, "useful_stock_value_eur": 20, "immobilized_stock_value_eur": 80, "component_count": 1, "priced_component_count": 1},
                    {"day": 1, "node_id": "M-1", "product_item_id": "item:PF", "product_code": "PF", "threshold_mode": "target_stock", "stock_value_eur": 200, "useful_stock_value_eur": 50, "immobilized_stock_value_eur": 150, "component_count": 1, "priced_component_count": 1},
                    {"day": 0, "node_id": "M-1", "product_item_id": "item:PF", "product_code": "PF", "threshold_mode": "demand_90d", "stock_value_eur": 100, "useful_stock_value_eur": 60, "immobilized_stock_value_eur": 40, "component_count": 1, "priced_component_count": 1},
                    {"day": 1, "node_id": "M-1", "product_item_id": "item:PF", "product_code": "PF", "threshold_mode": "demand_90d", "stock_value_eur": 200, "useful_stock_value_eur": 70, "immobilized_stock_value_eur": 130, "component_count": 1, "priced_component_count": 1},
                ],
            )

            payload = build_global_kpi_tree_payload(daily_csv, demand_csv, constraint_csv)

        self.assertIsNotNone(payload)
        group = next(group for group in payload["groups"] if group["id"] == "component_stock")
        self.assertEqual(group["secondary_y_label"], "EUR")
        summary_by_label = {row["label"]: row["value"] for row in group["summary"]}
        self.assertEqual(summary_by_label["Valeur stock composant moyen"], "150.0")
        self.assertEqual(summary_by_label["Excedent economique 90j moyen"], "85.0")
        series_by_label = {series["label"]: series for series in group["secondary"]}
        self.assertEqual(series_by_label["Excedent vs cible MRP"]["values"], [80.0, 150.0])

    def test_read_only_payload_does_not_write_physics_kpi_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            daily_csv = data_dir / "first_simulation_daily.csv"
            demand_csv = data_dir / "production_demand_service_daily.csv"
            constraint_csv = data_dir / "production_constraint_daily.csv"
            write_csv(
                daily_csv,
                ["day", "demand", "served", "backlog_end", "holding_cost_day"],
                [{"day": 0, "demand": 10, "served": 10, "backlog_end": 0, "holding_cost_day": 1}],
            )
            write_csv(
                demand_csv,
                ["day", "item_id", "demand_qty", "required_with_backlog_qty", "served_qty", "backlog_end_qty"],
                [{"day": 0, "item_id": "item:PF", "demand_qty": 10, "required_with_backlog_qty": 10, "served_qty": 10, "backlog_end_qty": 0}],
            )
            write_csv(
                constraint_csv,
                ["day", "node_id", "output_item_id", "desired_qty", "planned_qty_after_lot_rule", "actual_qty"],
                [{"day": 0, "node_id": "M-1", "output_item_id": "item:PF", "desired_qty": 10, "planned_qty_after_lot_rule": 10, "actual_qty": 10}],
            )

            payload = build_global_kpi_tree_payload(
                daily_csv,
                demand_csv,
                constraint_csv,
                write_derived_artifacts=False,
            )

            self.assertIsNotNone(payload)
            self.assertFalse((data_dir / "physics_of_decision_kpi_daily.csv").exists())


if __name__ == "__main__":
    unittest.main()
