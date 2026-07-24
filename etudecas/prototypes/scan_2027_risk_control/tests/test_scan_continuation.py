from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control.run_scan_continuation import (
    build_next_actions,
    build_validation_command,
    fingerprint,
)


class ScanContinuationTests(unittest.TestCase):
    def test_incomplete_manifest_generates_operational_gates(self) -> None:
        manifest = {
            "source": {"mode": "synthetic_fallback", "baseline_path": None},
            "regime_calibration": {
                "high_confidence_thresholds": 0,
                "low_confidence_thresholds": 3,
            },
            "prediction_to_physics": {
                "interval_method": "fallback_from_existing_risk_series",
                "rows_used": 0,
            },
            "canonical_replay": {"status": "overlays_prepared"},
            "rci_business_validation": {"status": "pending_business_review"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            actions = build_next_actions(manifest, Path(tmp))
        works = {action["work"] for action in actions}
        self.assertIn("Run the campaign on the real canonical etudecas baseline", works)
        self.assertIn("Execute paired canonical multi-item replays", works)
        self.assertIn("Complete the blinded RCI workshop with procurement and planning", works)

    def test_complete_manifest_opens_2027_control_phase(self) -> None:
        manifest = {
            "source": {"mode": "etudecas_baseline", "baseline_path": "baseline.csv"},
            "regime_calibration": {
                "high_confidence_thresholds": 8,
                "low_confidence_thresholds": 0,
            },
            "prediction_to_physics": {
                "interval_method": "finite_sample_residual_quantile",
                "rows_used": 1000,
            },
            "canonical_replay": {"status": "executed"},
            "rci_business_validation": {
                "status": "validated_business_review",
                "completed_rows": 30,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "forecast_confusion_summary.csv").write_text("case,score\nTP,0\n", encoding="utf-8")
            actions = build_next_actions(manifest, Path(tmp))
        self.assertEqual(actions[0]["work"], "Freeze the calibrated 2026 benchmark and start Scenario/Tube MPC")

    def test_validation_command_is_reproducible(self) -> None:
        args = argparse.Namespace(
            repo_root="/repo",
            baseline_csv="auto",
            risk_csv="auto",
            days=365,
            seed=20260,
            paired_seed_count=20,
            confusion_seed_count=10,
            confusion_duration_days=42,
            controller_scenarios=24,
            policy_comparison_scenarios=48,
            controller_horizon_days=28,
            canonical_replay="overlay",
            canonical_graph="auto",
            canonical_days=365,
            canonical_seed_count=5,
            canonical_top_risk_pairs=5,
            scenario_id="scn:BASE",
            synthetic=False,
            no_plots=False,
            business_review_csv="",
        )
        command_a = build_validation_command(args, Path("/tmp/output"))
        command_b = build_validation_command(args, Path("/tmp/output"))
        self.assertEqual(fingerprint(command_a), fingerprint(command_b))
        self.assertIn("--paired-seed-count", command_a)
        self.assertIn("--canonical-replay", command_a)


if __name__ == "__main__":
    unittest.main()
