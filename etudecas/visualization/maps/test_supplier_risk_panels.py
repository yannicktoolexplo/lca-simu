from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from etudecas.visualization.maps.supplier_risk_panels import (
    build_simulated_risk_global_diagnostic_payload,
    build_simulated_supplier_risk_metrics,
    render_supplier_risk_catalog_html,
    supplier_risk_family_for_event,
)


class SupplierRiskPanelsTest(unittest.TestCase):
    def test_build_simulated_supplier_risk_metrics_counts_applied_state_event(self) -> None:
        metrics = build_simulated_supplier_risk_metrics(
            configured_by_node={
                "S-1": [
                    {
                        "event_id": "state_capacity_S-1",
                        "risk_type": "capacity",
                        "source": "state_dependent_supplier_risk",
                        "start_day": "3",
                        "end_day": "5",
                    }
                ]
            },
            applied_by_node={
                "S-1": [
                    {
                        "day": "4",
                        "event_ids": "state_capacity_S-1",
                        "capacity_multiplier": "0.50",
                    }
                ]
            },
        )

        node = metrics["nodes"]["S-1"]
        self.assertEqual(node["status"], "applied")
        self.assertEqual(node["driver_family"], "capacity")
        self.assertEqual(node["applied_source_counts"], {"state": 1})
        self.assertAlmostEqual(node["score"], 0.5)
        self.assertEqual(metrics["global"]["applied_event_count"], 1)

    def test_render_supplier_risk_catalog_html_marks_applied_and_configured_events(self) -> None:
        html = render_supplier_risk_catalog_html(
            "S-1",
            applied_rows=[
                {
                    "day": "2",
                    "event_ids": "stock_drop",
                    "stock_multiplier": "0.60",
                }
            ],
            configured_events=[
                {
                    "event_id": "stock_drop",
                    "risk_type": "stock",
                    "start_day": "1",
                    "end_day": "3",
                    "multiplier": "0.60",
                },
                {
                    "event_id": "cost_watch",
                    "risk_type": "purchase_cost",
                    "start_day": "4",
                    "end_day": "5",
                    "multiplier": "1.25",
                },
            ],
            economic_policy={
                "external_procurement_enabled": True,
                "external_procurement_lead_days": 7,
                "external_procurement_cost_multiplier": 1.2,
            },
        )

        self.assertIn("S-1 - risques simules fournisseur", html)
        self.assertIn("Stock fournisseur", html)
        self.assertIn("APPLIQUE", html)
        self.assertIn("Cout achat", html)
        self.assertIn("CONFIGURE", html)

    def test_supplier_risk_family_for_event_reads_state_event_id(self) -> None:
        family = supplier_risk_family_for_event({"event_id": "state_lead_S-1_001"})

        self.assertEqual(family, "lead")

    def test_global_diagnostic_classifies_state_event_as_production_cascade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            summaries = root / "summaries"
            data.mkdir()
            summaries.mkdir()
            (summaries / "first_simulation_summary.json").write_text(
                json.dumps(
                    {
                        "scenario_id": "scn:STATE",
                        "timeline_days": 20,
                        "kpis": {"fill_rate": 1.0, "ending_backlog": 0, "total_cost": 100},
                        "production_tracking": {"supplier_risk_events": []},
                    }
                ),
                encoding="utf-8",
            )

            def write_csv(name: str, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
                with (data / name).open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

            write_csv(
                "supplier_state_dependent_risk_events.csv",
                [
                    {
                        "event_id": "state_stock_S-1_item_A_d3",
                        "trigger_day": 3,
                        "start_day": 4,
                        "end_day": 6,
                        "supplier_id": "S-1",
                        "item_id": "item:A",
                        "risk_family": "stock",
                        "risk_type": "availability",
                        "multiplier": 0.8,
                        "trigger_metric": "stock_cover_below_3d",
                        "trigger_value": 2,
                        "threshold": 3,
                        "consecutive_days": 2,
                        "effect": "Disponibilite fournisseur x0.8",
                        "notes": "test",
                    }
                ],
                [
                    "event_id",
                    "trigger_day",
                    "start_day",
                    "end_day",
                    "supplier_id",
                    "item_id",
                    "risk_family",
                    "risk_type",
                    "multiplier",
                    "trigger_metric",
                    "trigger_value",
                    "threshold",
                    "consecutive_days",
                    "effect",
                    "notes",
                ],
            )
            write_csv(
                "supplier_risk_events_applied_daily.csv",
                [
                    {
                        "day": 4,
                        "supplier_id": "S-1",
                        "dst_node_id": "M-1",
                        "item_id": "item:A",
                        "edge_id": "E-1",
                        "event_ids": "state_stock_S-1_item_A_d3",
                        "availability_multiplier": 0.8,
                        "lead_time_extra_days": 2,
                    }
                ],
                [
                    "day",
                    "supplier_id",
                    "dst_node_id",
                    "item_id",
                    "edge_id",
                    "event_ids",
                    "availability_multiplier",
                    "lead_time_extra_days",
                ],
            )
            write_csv(
                "production_plan_events.csv",
                [
                    {
                        "day": 5,
                        "node_id": "M-1",
                        "output_item_id": "item:PF",
                        "event_type": "delay_input_shortage",
                        "reason": "input_shortage",
                        "shortfall_vs_lot_plan_qty": 120,
                        "binding_input_item_id": "item:A",
                        "next_expected_receipt_day": 8,
                    }
                ],
                [
                    "day",
                    "node_id",
                    "output_item_id",
                    "event_type",
                    "reason",
                    "shortfall_vs_lot_plan_qty",
                    "binding_input_item_id",
                    "next_expected_receipt_day",
                ],
            )
            write_csv(
                "production_constraint_daily.csv",
                [
                    {
                        "day": 5,
                        "node_id": "M-1",
                        "output_item_id": "item:PF",
                        "planned_qty_after_lot_rule": 120,
                        "actual_qty": 0,
                        "shortfall_vs_lot_plan_qty": 120,
                    }
                ],
                [
                    "day",
                    "node_id",
                    "output_item_id",
                    "planned_qty_after_lot_rule",
                    "actual_qty",
                    "shortfall_vs_lot_plan_qty",
                ],
            )
            write_csv(
                "production_demand_service_daily.csv",
                [
                    {
                        "day": 7,
                        "node_id": "C-1",
                        "item_id": "item:PF",
                        "demand_qty": 10,
                        "served_qty": 10,
                        "backlog_end_qty": 0,
                    }
                ],
                ["day", "node_id", "item_id", "demand_qty", "served_qty", "backlog_end_qty"],
            )
            write_csv(
                "first_simulation_daily.csv",
                [
                    {
                        "day": 4,
                        "external_procurement_transport_cost_day": 0,
                        "external_procurement_purchase_cost_day": 0,
                    }
                ],
                ["day", "external_procurement_transport_cost_day", "external_procurement_purchase_cost_day"],
            )

            payload = build_simulated_risk_global_diagnostic_payload(
                raw={
                    "nodes": [{"id": "S-1", "name": "Supplier"}, {"id": "M-1", "name": "Factory"}],
                    "edges": [{"id": "E-1", "from": "S-1", "to": "M-1", "items": ["item:A"]}],
                    "items": [{"id": "item:A", "code": "A"}, {"id": "item:PF", "code": "PF"}],
                },
                output_root=root,
                simulated_risk_metrics={"global": {}},
            )

        self.assertEqual(payload["summary"]["effective_cascade_count"], 1)
        self.assertEqual(payload["summary"]["cascade_stage_counts"]["production"], 1)
        self.assertEqual(payload["summary"]["origin_count"], 1)
        self.assertEqual(payload["summary"]["node_impact_count"], 2)
        self.assertEqual(payload["summary"]["edge_delay_impact_count"], 1)
        self.assertEqual(payload["summary"]["cascade_path_group_count"], 1)
        self.assertEqual(payload["summary"]["top_origin"]["supplier_id"], "S-1")
        self.assertEqual(payload["origin_impacts"][0]["primary_trigger"], "stock_cover_below_3d")
        self.assertEqual(payload["node_impacts"]["S-1"]["stage"], "production")
        self.assertEqual(payload["node_impacts"]["M-1"]["role"], "affected_factory")
        self.assertEqual(payload["edge_impacts"]["E-1"]["status"], "delay_impacted")
        self.assertEqual(payload["events"][0]["stage"], "production")
        self.assertEqual(payload["events"][0]["absorption_level"], "production_blocked")
        self.assertEqual(payload["events"][0]["highlight_edge_ids"], ["E-1"])
        self.assertIn("Stock fournisseur insuffisant", payload["events"][0]["root_cause_label"])
        self.assertGreaterEqual(len(payload["events"][0]["timeline_steps"]), 3)
        self.assertEqual(payload["cascade_roots"][0]["absorption_label"], "Absorbe partiellement: production reportee")
        self.assertEqual(payload["cascade_roots"][0]["action"]["label"], "Securiser l'intrant bloquant")
        self.assertIn("M-1", payload["cascade_roots"][0]["highlight_node_ids"])
        self.assertEqual(payload["cascade_path_groups"][0]["occurrence_count"], 1)
        self.assertEqual(payload["cascade_path_groups"][0]["route_edge_ids"], ["E-1"])
        self.assertIn("S-1 -> M-1", payload["cascade_path_groups"][0]["route_edge_labels"][0])
        self.assertEqual(payload["cascade_path_groups"][0]["action"]["label"], "Securiser l'intrant bloquant")
        self.assertIn("Origines principales des problemes", payload["html"])
        self.assertIn("Chemins metier consolides", payload["html"])
        self.assertIn("Cascades avec impact supply", payload["html"])


if __name__ == "__main__":
    unittest.main()
