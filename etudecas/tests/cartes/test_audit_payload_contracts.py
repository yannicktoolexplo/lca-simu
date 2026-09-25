from __future__ import annotations
import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps.simulation_payload import apply_physical_material_balances
from etudecas.visualization.maps.simulation_payload import economic_cost_view
from etudecas.visualization.maps.supplier_operations_payload import build_unit_scoped_mrp_assets
from etudecas.visualization.maps.scenario_comparison_payload import compute_observed_impact
from etudecas.visualization.maps.global_kpi_tree_payload import build_global_kpi_tree_payload
from etudecas.visualization.maps.build_supplychain_worldmap import build_simulation_diagnostics_payload, aggregate_daily_series, build_edge_metrics, summarize_inventory_rows
from etudecas.visualization.maps.simulation_payload import executed_shipment_day, observed_transport_lead
from etudecas.visualization.maps.supplier_risk_panels import build_simulated_risk_global_diagnostic_payload


def csv_file(path: Path, rows: list[dict]) -> Path:
    fields = sorted({key for row in rows for key in row}) or ["day"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


class ShipmentExecutionContractTests(unittest.TestCase):
    def test_inventory_table_distinguishes_rejected_known_and_missing_prices(self):
        states = [dict(item_id="RM", initial=10, uom="UN", initial_source="stock_source",
                       holding_cost=holding) for holding in (
            dict(unit_value_basis=3.895, value=0.02, source="global_value_median_fallback"),
            dict(unit_value_basis=12.5, value=0.03, source="article_price_UN"),
            {},
        )]
        rows = summarize_inventory_rows({"inventory": {"states": states}}, {})
        self.assertIn("repli historique rejete", rows[0][5])
        self.assertNotIn("3.895", rows[0][5])
        self.assertIn("rejete par le moteur", rows[0][6])
        self.assertEqual(float(rows[1][5]), 12.5)
        self.assertIn("article_price_UN", rows[1][6])
        self.assertIn("non documentee", rows[2][5])
        self.assertTrue(all("stock: stock_source" in row[6] for row in rows))
        self.assertEqual(states[0]["holding_cost"]["unit_value_basis"], 3.895)

    def test_departed_in_transit_is_not_received_or_an_observed_lead(self):
        row = dict(day="1824", arrival_day="1827", shipped_qty="3863", observation_day="1824",
                   departure_executed="1", arrival_executed="0", realized_departure_day="1824",
                   realized_arrival_day="", execution_status="in_transit", executed_shipped_qty="3863")
        self.assertEqual(aggregate_daily_series([row], value_field="shipped_qty"), [(1824, 3863)])
        self.assertEqual(aggregate_daily_series([row], value_field="shipped_qty", day_field="arrival_day"), [])
        self.assertIsNone(observed_transport_lead(row, horizon_days=1825))
        pending = dict(row, day="1826", departure_executed="0", execution_status="reserved_pending_departure")
        self.assertEqual(aggregate_daily_series([pending], value_field="shipped_qty"), [])

    def test_realized_dates_override_planned_and_legacy_future_is_excluded(self):
        row = dict(day="0", arrival_day="2", shipped_qty="7", observation_day="9",
                   departure_executed="1", arrival_executed="1", realized_departure_day="4",
                   realized_arrival_day="9", executed_shipped_qty="7", lead_days="2")
        self.assertEqual(executed_shipment_day(row), 4)
        self.assertEqual(aggregate_daily_series([row], value_field="shipped_qty", day_field="arrival_day"), [(9, 7)])
        self.assertEqual(observed_transport_lead(row), 5)
        self.assertIsNone(executed_shipment_day(dict(day="8", arrival_day="12"), arrival=True, horizon_days=10))
        self.assertIsNone(executed_shipment_day(dict(row, realized_arrival_day=""), arrival=True))

    def test_lane_stats_observe_only_completed_transports_and_do_not_invent_leads(self):
        raw = {"nodes": [], "edges": [dict(id="E", **{"from": "S", "to": "D"}, items=["I"], lead_time={"mean": 99})]}
        received = dict(src_node_id="S", dst_node_id="D", item_id="I", day=1, arrival_day=6,
                        shipped_qty=10, departure_executed=1, arrival_executed=1, lead_days=5)
        transit = dict(received, day=8, arrival_day=12, shipped_qty=20, arrival_executed=0, lead_days=4)
        pending = dict(received, day=9, arrival_day=10, shipped_qty=900, departure_executed=0, arrival_executed=0)
        with tempfile.TemporaryDirectory() as folder:
            path = csv_file(Path(folder) / "shipments.csv", [received, transit, pending])
            result = build_edge_metrics(raw, path, horizon_days=10)["E"]
            self.assertEqual(result["shipment_rows"], 2)
            self.assertEqual(result["avg_shipped_qty"], 15)
            self.assertEqual(result["observed_receipt_rows"], 1)
            self.assertEqual(result["avg_lead_days"], 5)
            path = csv_file(path, [transit, pending])
            result = build_edge_metrics(raw, path, horizon_days=10)["E"]
            self.assertIsNone(result["avg_lead_days"])
            self.assertEqual(result["planned_lead_days"], 99)


class PhysicalBalanceContractTests(unittest.TestCase):
    def material(self):
        return {"scope": "material", "node_id": "M", "item_id": "RM", "unit": "UN", "initial_qty": 100,
                "consumed_qty": 12.4, "planned_qty": 20,
                "yearly": {"1": {"consumed_qty": 12.4, "planned_qty": 20}}}

    def event(self, kind, qty, day=0, **extra):
        return dict(node_id="M", item_id="RM", event_type=kind, qty=qty, day=day, uom="UN", **extra)

    def test_rounding_opening_wip_and_future_receipt_are_not_inferred_from_bom(self):
        row = self.material()
        events = [self.event("opening_stock", 100), self.event("production_consume", 13),
                  self.event("lane_receipt", 20, 1), self.event("lane_receipt", 999, 2)]
        apply_physical_material_balances([row], events, [dict(node_id="M", item_id="RM", day=1, stock_end_of_day=107)], horizon_days=2, source_available=True)
        self.assertEqual(row["consumed_qty"], 13)
        self.assertEqual(row["theoretical_consumed_qty"], 12.4)
        self.assertEqual(row["delivered_qty"], 20)
        self.assertEqual(row["balance_gap_qty"], 0)
        self.assertEqual(row["balance_status"], "reconciled")

    def test_reservation_and_departure_are_not_debited_twice(self):
        row = self.material()
        events = [self.event("opening_stock", 100), self.event("shipment_reserve", 10), self.event("lane_ship", 10)]
        apply_physical_material_balances([row], events, [dict(node_id="M", item_id="RM", day=0, stock_end_of_day=90)], horizon_days=1, source_available=True)
        self.assertEqual(row["stock_outflow_qty"], 10)
        self.assertEqual(row["balance_status"], "reconciled")

    def test_previous_year_closing_stock_precedes_same_day_receipt(self):
        row = self.material()
        row["yearly"]["2"] = {"consumed_qty": 0}
        events = [self.event("opening_stock", 100), self.event("lane_receipt", 50, 365)]
        stocks = [dict(node_id="M", item_id="RM", day=364, stock_end_of_day=100), dict(node_id="M", item_id="RM", day=365, stock_end_of_day=150, stock_before_production=150)]
        apply_physical_material_balances([row], events, stocks, horizon_days=366, source_available=True)
        self.assertEqual(row["yearly"]["2"]["initial_qty"], 100)
        self.assertEqual(row["yearly"]["2"]["balance_gap_qty"], 0)

    def test_missing_source_unknown_event_or_wrong_unit_cannot_pass(self):
        for events, available in (([], False), ([self.event("unrecognized_stock_adjustment", 1)], True), ([dict(self.event("opening_stock", 100), uom="KG")], True)):
            with self.subTest(events=events):
                row = self.material()
                apply_physical_material_balances([row], events, [dict(node_id="M", item_id="RM", day=0, stock_end_of_day=100)], horizon_days=1, source_available=available)
                self.assertEqual(row["balance_status"], "unavailable")
                self.assertIsNone(row["consumed_qty"])

    def test_nonzero_ledger_gap_is_reported_even_below_old_two_percent_tolerance(self):
        row = self.material()
        events = [self.event("opening_stock", 100), self.event("production_consume", 13)]
        apply_physical_material_balances([row], events, [dict(node_id="M", item_id="RM", day=0, stock_end_of_day=88)], horizon_days=1, source_available=True)
        self.assertEqual(row["balance_gap_qty"], -1)
        self.assertEqual(row["balance_status"], "mismatch")


class SemanticGuardTests(unittest.TestCase):
    def test_unknown_or_incomplete_value_cannot_affect_cost_ranking_or_score(self):
        for valuation in ({}, {"economic_valuation": {"complete": False, "status": "incomplete"}}):
            view = economic_cost_view({**valuation, "kpis": {"total_cost": 100, "total_external_procurement_cost": 50}})
            self.assertEqual(view["economic_exposure"], 150)
            self.assertFalse(view["economic_ranking_eligible"])
            impact = compute_observed_impact({**view, "fill_rate": 1, "total_cost": 1000000}, {**view, "fill_rate": 1, "total_cost": 1})
            self.assertEqual(impact["observed_impact_score"], 0)
            self.assertIsNone(impact["cost_delta_pct"])
            self.assertIn("cost", impact["score_excluded_dimensions"])

    def test_two_units_and_unknown_articles_are_separate_axes(self):
        raw = {"nodes": [{"id": "M", "inventory": {"states": [{"item_id": "A", "uom": "UN"}, {"item_id": "B", "uom": "KG"}]}}]}
        traces = [dict(item_id=item, day=0, stock_proj_qty=value) for item, value in (("A", 100), ("B", 2), ("unknown1", 8), ("unknown2", 9))]
        assets = build_unit_scoped_mrp_assets(raw, "M", trace_rows=traces, order_rows=[], stock_rows=[], arrival_rows=[], shipment_rows=[], horizon_days=1)
        bundle = assets["incoming"]["bundle"]
        self.assertEqual(len(bundle), 4)
        values = {entry["label"]: next(series["values"] for series in entry["asset"]["figure"]["series"] if series["label"] == "Stock projeté") for entry in bundle}
        self.assertEqual(values["UN"], [100])
        self.assertEqual(values["KG"], [2])
        self.assertNotIn([102], values.values())

    def test_pending_departure_and_future_arrival_are_not_confirmed_movement(self):
        raw = {"nodes": [{"id": "S", "inventory": {"states": [{"item_id": "A", "uom": "UN"}]}}]}
        shipments = [dict(item_id="A", day=0, arrival_day=10, shipped_qty=5),
                     dict(item_id="A", day=1, arrival_day=1, shipped_qty=99, departure_executed=False, arrival_executed=False)]
        asset = build_unit_scoped_mrp_assets(raw, "S", trace_rows=[], order_rows=[], stock_rows=[], arrival_rows=[], shipment_rows=shipments, horizon_days=2)["supplier_order_send"]
        series = asset["figure"]["bottom"]["series"]
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["values"], [5])

    def test_planned_receipt_uses_raw_order_contract_not_nonexistent_column(self):
        raw = {"nodes": [{"id": "M", "inventory": {"states": [{"item_id": "A", "uom": "UN"}]}}]}
        order = dict(item_id="A", node_id="M", src_node_id="S", order_date_imt=0, day=0, release_day=0, arrival_day=12, lead_reference_days=12, release_qty=15, planned_receipt_qty=15)
        asset = build_unit_scoped_mrp_assets(raw, "M", trace_rows=[], order_rows=[order], stock_rows=[], arrival_rows=[], shipment_rows=[], horizon_days=20)
        receipts = next(series for series in asset["outgoing"]["figure"]["top"]["series"] if series["label"] == "Réceptions prévues")
        self.assertEqual(receipts["days"], [7])
        self.assertEqual(receipts["values"], [15])
        carnet = next(series for series in asset["fourth"]["figure"]["series"] if "réception prévue" in series["label"])
        self.assertEqual(carnet["values"], [15])

    def test_fractional_residuals_are_not_whole_unit_backlog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = csv_file(root / "empty.csv", [])
            demand = csv_file(root / "demand.csv", [dict(node_id="C", item_id="A", day=day, demand_qty=10, served_qty=10, backlog_end_qty=.75 if day < 20 else 1) for day in range(21)])
            raw = {"nodes": [{"id": "C", "type": "customer", "inventory": {"states": [{"item_id": "A", "uom": "UN"}]}}]}
            payload = build_simulation_diagnostics_payload(raw, demand_service_csv=demand, dc_stocks_csv=empty, sim_input_stocks_csv=empty, sim_output_products_csv=empty, production_constraint_csv=empty, production_plan_events_csv=empty, supplier_shipments_csv=empty, supplier_stocks_csv=empty, supplier_stock_flows_csv=empty, supplier_local_criticality_csv=empty, mrp_trace_csv=empty)
            diagnostic = payload["nodes"]["C"]
            self.assertEqual(diagnostic["backlog_days"], 21)
            self.assertEqual(diagnostic["actionable_backlog_days"], 1)
            self.assertEqual(diagnostic["forecast_residual_days"], 20)
            self.assertEqual(diagnostic["cls"], "businessOk")

    def test_dc_diagnostic_excludes_pending_future_departure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = csv_file(root / "empty.csv", [])
            stocks = csv_file(root / "stocks.csv", [dict(node_id="DC", item_id="A", day=day, stock_end_of_day=100) for day in range(2)])
            shipments = csv_file(root / "shipments.csv", [dict(src_node_id="S", dst_node_id="DC", item_id="A", day=10, arrival_day=12, shipped_qty=999, departure_executed=0, arrival_executed=0)])
            payload = build_simulation_diagnostics_payload({"nodes": [{"id": "DC", "type": "distribution_center"}]}, demand_service_csv=empty, dc_stocks_csv=stocks, sim_input_stocks_csv=empty, sim_output_products_csv=empty, production_constraint_csv=empty, production_plan_events_csv=empty, supplier_shipments_csv=shipments, supplier_stocks_csv=empty, supplier_stock_flows_csv=empty, supplier_local_criticality_csv=empty, mrp_trace_csv=empty)
            diagnostic = json.dumps(payload["nodes"]["DC"])
            self.assertNotIn("999", diagnostic)
            self.assertIn("receptions=0.0", diagnostic.lower())

    def test_obsolete_zero_stock_is_not_a_production_shortage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily = csv_file(root / "daily.csv", [dict(day=day, demand=1, served=1) for day in range(2)])
            demand = csv_file(root / "demand.csv", [dict(day=day, item_id="PF", demand_qty=1, served_qty=1) for day in range(2)])
            constraints = csv_file(root / "constraints.csv", [dict(day=0, node_id="M", output_item_id="PF", binding_cause="none", desired_qty=1, planned_qty_after_lot_rule=1, actual_qty=1, shortfall_vs_lot_plan_qty=0), dict(day=1, node_id="M", output_item_id="PF", binding_cause="input_shortage", desired_qty=1, planned_qty_after_lot_rule=1, actual_qty=0, shortfall_vs_lot_plan_qty=1)])
            csv_file(root / "production_input_stocks_daily.csv", [dict(day=day, node_id="M", item_id="OBSOLETE", stock_end_of_day=0) for day in range(2)])
            payload = build_global_kpi_tree_payload(daily, demand, constraints, write_derived_artifacts=False)
            production = next(group for group in payload["groups"] if group["id"] == "material_factory_nervousness")
            signal = next(series for series in production["secondary"] if series["label"] == "Jours de production bloques par intrants (30j)")
            self.assertEqual(signal["values"], [0, 1])

    def test_lot_plan_adherence_is_not_demand_concordance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily = csv_file(root / "daily.csv", [dict(day=0, demand=10, served=10)])
            demand = csv_file(root / "demand.csv", [dict(day=0, node_id="C", item_id="PF", demand_qty=10, served_qty=10)])
            constraints = csv_file(root / "constraints.csv", [dict(day=0, node_id="M", output_item_id="PF", binding_cause="none", desired_qty=20, planned_qty_after_lot_rule=20, actual_qty=20)])
            raw = {"nodes": [{"id": "M", "type": "factory"}, {"id": "C", "type": "customer"}], "edges": [{"from": "M", "to": "C", "items": ["PF"]}]}
            payload = build_global_kpi_tree_payload(daily, demand, constraints, raw=raw, write_derived_artifacts=False)
            production = next(group for group in payload["groups"] if group["id"] == "production")
            by_label = {row["label"]: row["values"] for row in production["secondary"]}
            self.assertEqual(by_label["Concordance production / besoin (30j) (%)"], [0])
            self.assertEqual(by_label["Adherence plan lotifie mensuelle (%)"], [100])

    def test_preexisting_client_backlog_is_not_attributed_to_unapplied_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "summaries").mkdir()
            (root / "summaries/first_simulation_summary.json").write_text(json.dumps({"production_tracking": {"supplier_risk_events": [{"event_id": "configured-only", "supplier_id": "S", "item_id": "RM", "start_day": 2, "end_day": 3, "risk_type": "stock", "multiplier": .5}]}}), encoding="utf-8")
            csv_file(root / "data/production_demand_service_daily.csv", [dict(day=day, node_id="C", item_id="PF", demand_qty=0, served_qty=0, backlog_end_qty=100) for day in (0, 2, 3)])
            raw = {"nodes": [{"id": "S", "type": "supplier_dc"}, {"id": "M", "type": "factory", "processes": [{"inputs": [{"item_id": "RM"}], "outputs": [{"item_id": "PF"}]}]}, {"id": "C", "type": "customer"}], "edges": [{"id": "SM", "from": "S", "to": "M", "items": ["RM"]}, {"id": "MC", "from": "M", "to": "C", "items": ["PF"]}]}
            payload = build_simulated_risk_global_diagnostic_payload(raw=raw, output_root=root, simulated_risk_metrics={})
            event = payload["events"][0]
            self.assertFalse(event["applied"])
            self.assertEqual(event["local_application_status"], "configured_only")
            self.assertEqual(event["causality_status"], "association_only")
            self.assertIsNone(event["attributed_customer_loss_qty"])
            self.assertIsNone(event["attributed_cost"])
            client_steps = [step for step in event["timeline_steps"] if step["step"] == "customer_backlog"]
            self.assertTrue(client_steps)
            self.assertEqual(client_steps[0]["status"], "association_only")


if __name__ == "__main__":
    unittest.main()
