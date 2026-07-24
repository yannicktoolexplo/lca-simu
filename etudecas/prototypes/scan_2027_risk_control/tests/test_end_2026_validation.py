from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.calibration import calibrate_from_context
from etudecas.prototypes.scan_2027_risk_control.canonical_replay import apply_action_overlay_to_graph
from etudecas.prototypes.scan_2027_risk_control.core import (
    DEFAULT_ACTIONS,
    build_input_context,
    load_config,
    sample_scenarios,
)
from etudecas.prototypes.scan_2027_risk_control.decision import run_adaptive_controller
from etudecas.prototypes.scan_2027_risk_control.experiments import (
    build_confusion_context,
    build_truth_physical_envelope,
    paired_policy_experiment,
)
from etudecas.prototypes.scan_2027_risk_control.rci_validation import build_rci_business_validation_pack
from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_canonical_risk_events,
    map_prediction_interval_to_physical,
)


class End2026ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(None)
        self.config["controller_scenarios"] = 2
        self.config["policy_comparison_scenarios"] = 3
        self.config["controller_horizon_days"] = 7
        self.config["review_period_days"] = 7
        self.context = build_input_context(Path.cwd(), "auto", "auto", 28, 101, True)

    def test_prediction_interval_maps_monotonically_to_physics(self) -> None:
        envelope = pd.DataFrame({
            "day": [0, 1],
            "risk_lower": [0.10, 0.10],
            "risk_center": [0.50, 0.50],
            "risk_upper": [0.90, 0.90],
            "conditional_backlog_if_incident": [20.0, 20.0],
            "conditional_fill_loss_if_incident": [0.02, 0.02],
            "lead_mean_days": [10.0, 10.0],
            "priority_score": [1.0, 1.0],
            "source_pairs": [1, 1],
        })
        physical = map_prediction_interval_to_physical(envelope, self.config["physical_risk_mapping"])
        self.assertGreater(physical.loc[0, "availability_multiplier_lower"], physical.loc[0, "availability_multiplier_center"])
        self.assertGreater(physical.loc[0, "availability_multiplier_center"], physical.loc[0, "availability_multiplier_upper"])
        self.assertLess(physical.loc[0, "lead_time_extra_days_lower"], physical.loc[0, "lead_time_extra_days_center"])
        self.assertLess(physical.loc[0, "lead_time_extra_days_center"], physical.loc[0, "lead_time_extra_days_upper"])
        scenario = sample_scenarios(1, 2, self.config, 7, physical_risk=physical)[0]
        self.assertIsNotNone(scenario.realized_risk_probability)
        self.assertTrue(np.all(scenario.quality_yield_multiplier <= 1.0))

    def test_regime_calibration_returns_evidence_and_labels(self) -> None:
        artifacts = calibrate_from_context(self.context, self.config)
        self.assertEqual(len(artifacts.evidence), 8)
        self.assertIn("calibrated_regime", artifacts.frame)
        self.assertIn("material_cover_days", artifacts.frame)
        self.assertEqual(len(artifacts.frame), len(self.context.input_series))
        self.assertIn("regime_thresholds", artifacts.config)

    def test_realized_physical_truth_is_used_by_adaptive_controller(self) -> None:
        forecast_context = build_confusion_context(
            self.context,
            predicted_event=False,
            start_day=8,
            duration_days=12,
            low_probability=0.05,
            high_probability=0.85,
            mapping_config=self.config["physical_risk_mapping"],
        )
        low_truth = build_truth_physical_envelope(
            28, truth_event=False, start_day=8, duration_days=12,
            low_probability=0.05, high_probability=0.85,
            mapping_config=self.config["physical_risk_mapping"],
        )
        high_truth = build_truth_physical_envelope(
            28, truth_event=True, start_day=8, duration_days=12,
            low_probability=0.05, high_probability=0.85,
            mapping_config=self.config["physical_risk_mapping"],
        )
        low_scenario = sample_scenarios(1, 28, self.config, 44, physical_risk=low_truth)[0]
        high_scenario = sample_scenarios(1, 28, self.config, 44, physical_risk=high_truth)[0]
        low_trajectory, _, _ = run_adaptive_controller(
            forecast_context, self.config, DEFAULT_ACTIONS, 55, realized_scenario=low_scenario
        )
        high_trajectory, _, _ = run_adaptive_controller(
            forecast_context, self.config, DEFAULT_ACTIONS, 55, realized_scenario=high_scenario
        )
        self.assertGreater(high_trajectory["realized_base_risk"].mean(), low_trajectory["realized_base_risk"].mean())
        self.assertGreater(high_trajectory["supplier_risk"].mean(), low_trajectory["supplier_risk"].mean())

    def test_paired_comparison_has_exact_zero_reference_delta(self) -> None:
        runs, summary = paired_policy_experiment(self.context, self.config, DEFAULT_ACTIONS, [11, 12])
        self.assertFalse(runs.empty)
        reference = summary.loc[summary["policy"] == "mrp_reference"].iloc[0]
        self.assertAlmostEqual(float(reference["mean_delta_score"]), 0.0, places=10)
        self.assertEqual(int(reference["paired_seed_count"]), 2)

    def test_rci_pack_includes_counterfactual_candidates(self) -> None:
        trajectory, decisions, candidates = run_adaptive_controller(
            self.context, self.config, DEFAULT_ACTIONS, 21
        )
        review = build_rci_business_validation_pack(
            trajectory, decisions, candidates, self.config
        )
        self.assertFalse(review.empty)
        self.assertIn("candidate_policy", review)
        self.assertIn("is_selected", review)
        self.assertTrue((review["is_selected"] == 0).any())
        self.assertGreater(review["model_rci"].max(), review["model_rci"].min())

    def test_canonical_risk_events_and_overlay_are_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            prediction_path = temp / "prediction.csv"
            pd.DataFrame({
                "snapshot_date": ["2026-06-01", "2026-06-01"],
                "supplier_id": ["SUP-A", "SUP-B"],
                "factory_id": ["FACTORY", "FACTORY"],
                "item_id": ["item:A", "item:B"],
                "predicted_incident_probability_30d": [0.8, 0.3],
                "predicted_priority_score": [0.9, 0.2],
            }).to_csv(prediction_path, index=False)
            envelope = pd.DataFrame({
                "day": np.arange(30),
                "risk_lower": np.full(30, 0.55),
                "risk_center": np.full(30, 0.70),
                "risk_upper": np.full(30, 0.90),
                "conditional_backlog_if_incident": np.full(30, 20.0),
                "conditional_fill_loss_if_incident": np.full(30, 0.02),
                "lead_mean_days": np.full(30, 8.0),
                "priority_score": np.full(30, 0.8),
                "source_pairs": np.ones(30),
            })
            physical = map_prediction_interval_to_physical(envelope, self.config["physical_risk_mapping"])
            events, ledger = build_canonical_risk_events(
                prediction_path, physical, days=30, top_pairs=1
            )
            self.assertFalse(events.empty)
            self.assertEqual(set(events["supplier_id"]), {"SUP-A"})
            self.assertTrue((ledger["mapping_status"] == "research_mapping_requires_industrial_calibration").all())

            graph = {
                "nodes": [
                    {"id": "FACTORY", "type": "factory", "processes": [{"capacity": {"max_rate": 100.0}}],
                     "inventory": {"states": [{"item_id": "item:A", "initial": 10.0}]}}
                ],
                "edges": [{"from": "SUP-A", "to": "FACTORY", "lead_time": {"mean": 5.0, "min": 4.0, "max": 7.0}}],
                "scenarios": [{"id": "scn:BASE", "safety_stock_days": 7.0, "economic_policy": {}}],
            }
            patched, overlay = apply_action_overlay_to_graph(graph, DEFAULT_ACTIONS[4], scenario_id="scn:BASE")
            self.assertEqual(patched["metadata"]["scan_control_overlay"]["policy"], "balanced_robust")
            self.assertGreater(overlay["applied_counts"]["process_capacities"], 0)


if __name__ == "__main__":
    unittest.main()
