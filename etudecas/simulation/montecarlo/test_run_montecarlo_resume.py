import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etudecas.simulation.montecarlo.run_montecarlo_analysis import (
    checkpoint_fingerprint,
    checkpoint_path,
    load_run_checkpoint,
    parse_args,
    write_run_checkpoint,
)


class MonteCarloResumeCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = {
            "index": 7,
            "run_id": "run_0007",
            "row": {"run_id": "run_0007", "status": "ok"},
            "factors": {"demand_scale": 1.1},
            "demand_item_scale": {"item:1": 0.95},
        }
        self.config = {
            "input_sha256": "input-v1",
            "implementation_sha256": "engine-v1",
            "scenario_id": "scn:BASE",
            "days": 1825,
            "save_trajectories": True,
            "trajectory_max_points": 730,
        }

    def test_resume_is_enabled_by_default_and_can_be_disabled(self) -> None:
        with patch("sys.argv", ["run_montecarlo_analysis.py"]):
            self.assertTrue(parse_args().resume)
        with patch("sys.argv", ["run_montecarlo_analysis.py", "--no-resume"]):
            self.assertFalse(parse_args().resume)

    def test_fingerprint_is_stable_and_invalidated_by_spec_or_config(self) -> None:
        first = checkpoint_fingerprint(self.spec, self.config, phase="main")
        reordered = checkpoint_fingerprint(
            dict(reversed(list(self.spec.items()))),
            dict(reversed(list(self.config.items()))),
            phase="main",
        )
        changed_spec = checkpoint_fingerprint(
            {**self.spec, "factors": {"demand_scale": 1.2}},
            self.config,
            phase="main",
        )
        changed_config = checkpoint_fingerprint(
            self.spec,
            {**self.config, "days": 365},
            phase="main",
        )

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed_spec)
        self.assertNotEqual(first, changed_config)

    def test_successful_result_round_trips_as_atomic_gzip_checkpoint(self) -> None:
        trajectory = {
            "run_id": "run_0007",
            "series": {"backlog": [[0, 0.0], [1, 4.0]]},
        }
        result = {
            "index": 7,
            "row": {"run_id": "run_0007", "status": "ok", "kpi::total_cost": 42.0},
            "trajectory_run": trajectory,
        }
        fingerprint = checkpoint_fingerprint(self.spec, self.config, phase="main")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = checkpoint_path(root, self.spec, phase="main")
            written = write_run_checkpoint(
                path,
                fingerprint=fingerprint,
                phase="main",
                result=result,
                require_trajectory=True,
            )
            loaded = load_run_checkpoint(
                path,
                expected_fingerprint=fingerprint,
                phase="main",
                require_trajectory=True,
            )

            self.assertTrue(written)
            self.assertEqual(path.read_bytes()[:2], b"\x1f\x8b")
            self.assertEqual(loaded, result)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_mismatch_corruption_and_incomplete_results_are_not_reused(self) -> None:
        result = {
            "index": 7,
            "row": {"run_id": "run_0007", "status": "ok"},
            "trajectory_run": None,
        }
        fingerprint = checkpoint_fingerprint(self.spec, self.config, phase="paired")

        with tempfile.TemporaryDirectory() as tmp:
            path = checkpoint_path(Path(tmp), self.spec, phase="paired")
            self.assertFalse(
                write_run_checkpoint(
                    path,
                    fingerprint=fingerprint,
                    phase="paired",
                    result=result,
                    require_trajectory=True,
                )
            )
            self.assertFalse(path.exists())

            self.assertTrue(
                write_run_checkpoint(
                    path,
                    fingerprint=fingerprint,
                    phase="paired",
                    result=result,
                    require_trajectory=False,
                )
            )
            self.assertIsNone(
                load_run_checkpoint(
                    path,
                    expected_fingerprint="different",
                    phase="paired",
                    require_trajectory=False,
                )
            )
            self.assertIsNone(
                load_run_checkpoint(
                    path,
                    expected_fingerprint=fingerprint,
                    phase="main",
                    require_trajectory=False,
                )
            )

            path.write_bytes(b"incomplete")
            self.assertIsNone(
                load_run_checkpoint(
                    path,
                    expected_fingerprint=fingerprint,
                    phase="paired",
                    require_trajectory=False,
                )
            )


if __name__ == "__main__":
    unittest.main()
