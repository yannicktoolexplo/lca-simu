from __future__ import annotations

import unittest

from etudecas.simulation.initial_state_policy import merge_living_initial_state_args


class InitialStatePolicyTest(unittest.TestCase):
    def test_adds_living_supply_defaults_when_missing(self) -> None:
        args = merge_living_initial_state_args(["--skip-map"])

        self.assertIn("--initial-state-scale", args)
        self.assertIn("1", args)
        self.assertIn("--no-initial-seed-safety-time-on-hand", args)
        self.assertIn("--no-initial-seed-estimated-source-on-hand", args)
        self.assertIn("--no-initial-seed-in-transit", args)
        self.assertIn("--no-initial-seed-estimated-source-pipeline", args)
        self.assertIn("--mrp-base-stock-floor-factor", args)
        self.assertEqual(args[-1], "--skip-map")

    def test_keeps_explicit_initial_state_choice(self) -> None:
        args = merge_living_initial_state_args(["--initial-state-scale", "0.5", "--skip-map"])

        self.assertEqual(args, ["--initial-state-scale", "0.5", "--skip-map"])


if __name__ == "__main__":
    unittest.main()
