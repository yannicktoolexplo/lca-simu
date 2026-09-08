from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from etudecas.prototypes.scan_2027_risk_control.core import (
    DEFAULT_ACTIONS,
    DEFAULT_CONFIG,
    ScenarioPath,
    SimulationState,
    build_input_context,
    deep_merge,
    initial_state,
)
from etudecas.prototypes.scan_2027_risk_control.decision import (
    adaptive_summary,
    run_adaptive_controller,
    simulate_fixed_policy_scenarios,
)
from etudecas.prototypes.scan_2027_risk_control.model import classify_regime, simulate_horizon


class Scan2027PocTests(unittest.TestCase):
    def small_config(self) -> dict:
        return deep_merge(DEFAULT_CONFIG, {
            "review_period_days": 7,
            "controller_horizon_days": 14,
            "controller_scenarios": 8,
            "policy_comparison_scenarios": 10,
        })

    def test_crisis_regime_is_detected(self) -> None:
        config = self.small_config()
        state = SimulationState(0.2, 0.0, 2.0, 0.5, 1.0, 1.1, 0.85, 1.5)
        metrics = {"demand": 1.0, "nervousness": 0.6, "production_utilization": 1.0}
        self.assertEqual(classify_regime(state, metrics, config), "CRISIS")

    def test_aggressive_action_creates_more_supplier_risk(self) -> None:
        config = self.small_config()
        horizon = 21
        demand = np.ones(horizon)
        base_risk = np.full(horizon, 0.18)
        scenario = ScenarioPath(np.ones(horizon), np.zeros(horizon), np.zeros(horizon), np.zeros(horizon), np.zeros(horizon))
        state = initial_state(config, 1.0, 0.18)
        actions = {action.name: action for action in DEFAULT_ACTIONS}
        reactive, _ = simulate_horizon(state, actions["reactive_buffer"], demand, base_risk, scenario, config)
        relief, _ = simulate_horizon(state, actions["supplier_relief"], demand, base_risk, scenario, config)
        self.assertGreater(float(reactive["supplier_risk"].mean()), float(relief["supplier_risk"].mean()))
        self.assertGreater(float(reactive["nervousness"].sum()), float(relief["nervousness"].sum()))

    def test_synthetic_smoke_run(self) -> None:
        config = self.small_config()
        with tempfile.TemporaryDirectory() as tmp:
            context = build_input_context(Path(tmp), "auto", "auto", 42, 17, True)
            adaptive, decisions, candidates = run_adaptive_controller(context, config, DEFAULT_ACTIONS, 17)
            comparison, trajectories = simulate_fixed_policy_scenarios(context, config, DEFAULT_ACTIONS, 17)
            self.assertEqual(len(adaptive), 42)
            self.assertFalse(decisions.empty)
            self.assertFalse(candidates.empty)
            self.assertFalse(comparison.empty)
            self.assertFalse(trajectories.empty)
            summary = adaptive_summary(adaptive)
            self.assertTrue(np.isfinite(list(summary.values())).all())
            self.assertIn("supplier_relief", set(comparison["policy"]))


if __name__ == "__main__":
    unittest.main()
