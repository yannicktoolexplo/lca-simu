from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from etudecas.visualization.maps.scenario_comparison_payload import (
    build_scenario_comparison_payload,
    compute_observed_impact,
)


class ScenarioComparisonPayloadTest(unittest.TestCase):
    def test_observed_score_and_signed_deltas(self) -> None:
        base = {"fill_rate": 1, "total_cost": 1000, "total_demand": 1000, "valuation_complete": True}
        risk = {"fill_rate": .9, "total_cost": 1200, "total_demand": 1000,
                "input_delay_volume": 40, "max_backlog": 20, "valuation_complete": True,
                "total_unreliable_loss_qty": 10, "risk_input_amplitude_points": 100}
        actual = compute_observed_impact(risk, base)
        self.assertAlmostEqual(actual["observed_impact_score"], 61)
        self.assertAlmostEqual(actual["fill_rate_delta_pp"], -10)
        self.assertEqual(actual["cost_delta"], 200)
        self.assertEqual(actual["input_delay_volume_delta"], 40)
        self.assertEqual(actual["loss_delta"], 10)
        self.assertIsNone(actual["loss_qty_pct"])
        self.assertIsNone(actual["replan_volume_pct"])
        risk["total_cost"] = 800
        actual = compute_observed_impact(risk, base)
        self.assertEqual(actual["cost_delta"], -200)
        self.assertEqual(actual["cost_delta_pct"], 0)  # Only excess cost enters the score.
        self.assertAlmostEqual(actual["observed_impact_score"], 56)

    def test_zero_service_is_total_service_loss(self) -> None:
        actual = compute_observed_impact(
            {"fill_rate": 0, "total_cost": 0, "total_demand": 100},
            {"fill_rate": 1, "total_cost": 10, "total_demand": 100})
        self.assertEqual(actual["fill_rate_delta_pp"], -100)
        self.assertEqual(actual["observed_impact_score"], 500)
        self.assertEqual(actual["cost_delta"], -10)

    def test_compact_payload_is_loaded_when_no_case_tree_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            current = Path(tmp) / "active_run"
            current.mkdir()
            sweep_root = Path(tmp) / "risk_amplitude_duration_sweep_5y"
            sweep_root.mkdir()
            expected = {
                "schema_version": "etudecas.scenario_comparison.v1",
                "scenarios": [{"id": "baseline"}],
                "charts": {},
            }
            (sweep_root / "scenario_comparison_payload_compact.json").write_text(
                json.dumps(expected),
                encoding="utf-8",
            )

            payload = build_scenario_comparison_payload(current)

        self.assertFalse(payload["available"])
        self.assertEqual(payload["valuation_status"], "unknown")
        self.assertEqual(payload["scenarios"], [])

    def test_current_run_with_companion_ignores_stale_compact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "active_run"
            companion = current / "scenario_runs" / "state_dependent_full"
            stale = root / "risk_amplitude_duration_sweep_5y"
            stale.mkdir()
            (stale / "scenario_comparison_payload_compact.json").write_text(
                json.dumps(
                    {
                        "schema_version": "etudecas.scenario_comparison.v1",
                        "scenarios": [{"id": "old_run"}],
                        "figures": {},
                    }
                ),
                encoding="utf-8",
            )

            for run_dir, scenario_id, state_count in [
                (current, "scn:BASE", 0),
                (companion, "scn:STATE_DEPENDENT_FULL", 3),
            ]:
                (run_dir / "summaries").mkdir(parents=True)
                (run_dir / "data").mkdir(parents=True)
                (run_dir / "summaries" / "first_simulation_summary.json").write_text(
                    json.dumps(
                        {
                            "scenario_id": scenario_id,
                            "timeline_days": 365,
                            "sim_days": 365,
                            "policy": {
                                "supplier_risk": {"event_count": 0},
                                "supplier_state_dependent_risk": {
                                    "enabled": bool(state_count),
                                    "generated_event_count": state_count,
                                },
                            },
                            "kpis": {
                                "fill_rate": 1.0,
                                "ending_backlog": 0,
                                "total_cost": 100.0 + state_count,
                                "total_demand": 1000.0,
                                "total_served": 1000.0,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                for csv_name in [
                    "production_demand_service_daily.csv",
                    "production_plan_events.csv",
                    "production_constraint_daily.csv",
                    "supplier_risk_events_applied_daily.csv",
                ]:
                    (run_dir / "data" / csv_name).write_text("day\n", encoding="utf-8")
                # Integer deliveries leave fractional forecast backlog. That
                # residual must never classify later shortages as startup.
                (run_dir / "data" / "production_demand_service_daily.csv").write_text(
                    "day,demand_qty,served_qty,backlog_end_qty\n"
                    "0,10.5,0,10.5\n1,10.5,0,21\n2,10.5,31,0.5\n"
                    "3,50,0,50.5\n", encoding="utf-8")
            (companion / "data" / "supplier_risk_events_applied_daily.csv").write_text(
                "\n".join(
                    [
                        "day,supplier_id,event_ids,capacity_multiplier,lead_time_extra_days,purchase_cost_multiplier",
                        "0,SUP-1,EV-1,0.5,3,1.2",
                    ]
                ),
                encoding="utf-8",
            )

            (current / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "companion_runs": {
                            "state_dependent_full": {
                                "output_dir": "scenario_runs/state_dependent_full",
                                "scenario_id": "scn:STATE_DEPENDENT_FULL",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = build_scenario_comparison_payload(current)

        ids = {row["id"] for row in payload["scenarios"]}
        self.assertIn("active_run", ids)
        self.assertIn("state_dependent_full", ids)
        state_row = next(row for row in payload["scenarios"] if row["id"] == "state_dependent_full")
        self.assertEqual(state_row["kpis"]["state_events_generated"], 3.0)
        self.assertGreater(state_row["kpis"]["risk_input_amplitude_points"], 0.0)
        self.assertIn("observed_impact_score", state_row["kpis"])
        self.assertEqual(state_row["kpis"]["startup_backlog_days"], 2)
        self.assertEqual(state_row["kpis"]["max_backlog"], 50.5)
        self.assertAlmostEqual(state_row["kpis"]["observed_impact_score"], 15.15)
        self.assertIn("cost", state_row["kpis"]["score_excluded_dimensions"])
        self.assertFalse(state_row["kpis"]["economic_ranking_eligible"])
        self.assertEqual(state_row["kpis"]["cost_delta"], 3)
        self.assertEqual(payload["reference_id"], "active_run")
        self.assertTrue(next(r for r in payload["scenarios"] if r["id"] == "active_run")["is_reference"])
        self.assertIn("pas un intervalle de confiance", payload["html"])
        self.assertIn("ne mesure pas les livraisons a l'heure", payload["html"])


if __name__ == "__main__":
    unittest.main()
