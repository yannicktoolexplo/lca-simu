from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from etudecas.visualization.maps.scenario_comparison_payload import (
    build_scenario_comparison_payload,
)


class ScenarioComparisonPayloadTest(unittest.TestCase):
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

        self.assertEqual(payload, expected)

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


if __name__ == "__main__":
    unittest.main()
