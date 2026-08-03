from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import etudecas.prototypes.scan_2027_risk_control.run_scan_continuation as continuation

from etudecas.prototypes.scan_2027_risk_control.run_scan_continuation import (
    StepResult,
    build_next_actions,
    build_prototype_test_command,
    build_validation_command,
    fingerprint,
)


class ScanContinuationTests(unittest.TestCase):
    @staticmethod
    def _main_args(
        output_root: Path,
        *,
        stage: str,
        continue_on_error: bool = False,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            stage=stage,
            repo_root=str(Path(__file__).resolve().parents[4]),
            output_root=str(output_root),
            force=True,
            dry_run=False,
            continue_on_error=continue_on_error,
            skip_tests=False,
            skip_doctor=True,
            rebuild_baseline=False,
            with_montecarlo=False,
            montecarlo_runs=1,
            business_review_csv="",
            canonical_replay="run",
            days=56,
        )

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
        self.assertIn(
            (
                "Run the campaign on the canonical etudecas case-study "
                "simulation output"
            ),
            works,
        )
        self.assertIn("Execute paired canonical multi-item replays", works)
        self.assertIn("Complete the blinded RCI workshop with procurement and planning", works)

    def test_completed_review_requires_explicit_business_signoff(self) -> None:
        manifest = {
            "source": {"mode": "etudecas_baseline", "baseline_path": "baseline.csv"},
            "regime_calibration": {
                "high_confidence_thresholds": 8,
                "low_confidence_thresholds": 0,
                "regime_annotations": {
                    "business_label_days": 24,
                    "business_label_coverage_fraction": 0.40,
                },
            },
            "prediction_to_physics": {
                "interval_method": "finite_sample_residual_quantile",
                "rows_used": 1000,
            },
            "canonical_replay": {"status": "executed"},
            "rci_business_validation": {
                "status": "review_available",
                "completed_rows": 30,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "forecast_confusion_summary.csv").write_text("case,score\nTP,0\n", encoding="utf-8")
            actions = build_next_actions(manifest, Path(tmp))
        self.assertEqual(
            actions[0]["work"],
            "Review RCI metrics and record explicit business sign-off",
        )

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
            confusion_alert_response_policy="balanced_robust",
            confusion_alert_thresholds="0.40,0.70",
            confusion_interval_half_widths="0.05,0.18",
            confusion_sensitivity_durations="14,42",
            confusion_sensitivity_seed_count=1,
            controller_scenarios=24,
            policy_comparison_scenarios=48,
            controller_horizon_days=28,
            canonical_replay="overlay",
            canonical_graph="auto",
            canonical_engine_profile="engine_profile.json",
            canonical_days=365,
            canonical_seed_count=5,
            canonical_top_risk_pairs=5,
            mapping_sensitivity_factors="0.8,1.0,1.2",
            scenario_id="scn:BASE",
            synthetic=False,
            no_plots=False,
            config="scan_config.json",
            regime_annotations_csv="labels.csv",
            business_review_csv="",
        )
        command_a = build_validation_command(args, Path("/tmp/output"))
        command_b = build_validation_command(args, Path("/tmp/output"))
        self.assertEqual(fingerprint(command_a), fingerprint(command_b))
        self.assertIn("--paired-seed-count", command_a)
        self.assertIn("--canonical-replay", command_a)
        self.assertIn("--canonical-engine-profile", command_a)
        self.assertIn("--mapping-sensitivity-factors", command_a)
        self.assertIn("--confusion-alert-thresholds", command_a)
        self.assertIn("--confusion-alert-response-policy", command_a)
        self.assertIn("--regime-annotations-csv", command_a)
        self.assertIn("--config", command_a)
        self.assertEqual(
            command_a[command_a.index("--regime-annotations-csv") + 1],
            str(Path("labels.csv").resolve()),
        )
        self.assertEqual(
            command_a[command_a.index("--canonical-engine-profile") + 1],
            str(Path("engine_profile.json").resolve()),
        )

    def test_prototype_check_command_uses_pytest_for_the_complete_suite(self) -> None:
        test_dir = Path("/repo/scan/tests")
        self.assertEqual(
            build_prototype_test_command(test_dir),
            [sys.executable, "-m", "pytest", str(test_dir), "-q"],
        )

    def test_check_stage_executes_the_pytest_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self._main_args(Path(tmp), stage="check")

            def successful_step(**kwargs: object) -> StepResult:
                return StepResult(
                    name=str(kwargs["name"]),
                    status="ok",
                    started_at_utc="2026-01-01T00:00:00+00:00",
                    finished_at_utc="2026-01-01T00:00:01+00:00",
                    return_code=0,
                    command=list(kwargs["command"]),
                )

            with (
                patch.object(continuation, "parse_args", return_value=args),
                patch.object(
                    continuation,
                    "run_command",
                    side_effect=successful_step,
                ) as run_mock,
            ):
                return_code = continuation.main()

            self.assertEqual(return_code, 0)
            self.assertEqual(run_mock.call_count, 1)
            expected_test_dir = (
                Path(args.repo_root)
                / "etudecas"
                / "prototypes"
                / "scan_2027_risk_control"
                / "tests"
            )
            self.assertEqual(
                run_mock.call_args.kwargs["command"],
                build_prototype_test_command(expected_test_dir),
            )

    def test_continue_on_canonical_validation_error_keeps_handoff_but_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            args = self._main_args(
                output_root,
                stage="validate",
                continue_on_error=True,
            )
            failed_validation = StepResult(
                name="end_2026_validation",
                status="failed",
                started_at_utc="2026-01-01T00:00:00+00:00",
                finished_at_utc="2026-01-01T00:00:01+00:00",
                return_code=2,
                command=[sys.executable, "run_end_2026_validation.py"],
                message="Canonical replay failed its output contract.",
            )
            handoff_path = output_root / "SCAN_CONTINUATION_HANDOFF.md"

            with (
                patch.object(continuation, "parse_args", return_value=args),
                patch.object(
                    continuation,
                    "build_validation_command",
                    return_value=[sys.executable, "placeholder"],
                ),
                patch.object(
                    continuation,
                    "run_command",
                    return_value=failed_validation,
                ),
                patch.object(
                    continuation,
                    "write_handoff_report",
                    return_value=handoff_path,
                ) as handoff_mock,
            ):
                return_code = continuation.main()

            self.assertEqual(return_code, 1)
            handoff_mock.assert_called_once()
            summary = json.loads(
                (output_root / "last_run_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["overall_status"], "failed")
            self.assertEqual(summary["failed_steps"], ["end_2026_validation"])
            self.assertEqual(summary["results"][0]["return_code"], 2)


if __name__ == "__main__":
    unittest.main()
