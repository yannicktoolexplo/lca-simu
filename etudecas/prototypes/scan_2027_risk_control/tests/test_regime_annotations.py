from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.calibration import (
    VALIDATED_REGIMES,
    calibrate_from_context,
    load_regime_annotations,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    build_input_context,
    load_config,
)
from etudecas.prototypes.scan_2027_risk_control.run_end_2026_validation import (
    REPO_ROOT,
    parse_args,
)


def weighted_vote_fixture() -> pd.DataFrame:
    """Return annotations covering a winner, a tie and an out-of-horizon day."""

    return pd.DataFrame({
        "day": [5, 5, 6, 6, 7, 7, 999],
        "site": ["S1", "S2", "S1", "S2", "S1", "S2", "S3"],
        "article": ["A1", "A2", "A1", "A2", "A1", "A2", "A3"],
        "validated_regime": [
            "crisis",
            "NOMINAL",
            "CRISIS",
            "NOMINAL",
            "RECOVERY",
            "RECOVERY",
            "NOMINAL",
        ],
        "expert_confidence": [0.9, 0.2, 0.5, 0.5, 0.7, 0.4, 0.8],
        "comment": [
            "major outage",
            "local view",
            "equal vote a",
            "equal vote b",
            "recovery a",
            "recovery b",
            "outside horizon",
        ],
    })


class RegimeAnnotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(None)
        cls.context = build_input_context(
            Path.cwd(), "auto", "auto", 28, 101, True
        )

    def test_absent_annotations_keep_explicit_pseudo_label_provenance(self) -> None:
        artifacts = calibrate_from_context(self.context, self.config)
        metadata = artifacts.metadata["regime_annotations"]

        self.assertEqual(metadata["status"], "not_provided")
        self.assertEqual(metadata["label_provenance"], "pseudo_labels_only")
        self.assertEqual(metadata["business_label_days"], 0)
        self.assertEqual(metadata["annotation_coverage_fraction"], 0.0)
        self.assertEqual(metadata["business_label_coverage_fraction"], 0.0)
        self.assertTrue(
            (artifacts.frame["regime_label_source"] == "pseudo_label").all()
        )
        pd.testing.assert_series_equal(
            artifacts.frame["calibrated_regime"],
            artifacts.frame["pseudo_regime"],
            check_names=False,
        )
        self.assertTrue(
            (artifacts.evidence["label_provenance"] == "pseudo_labels_only").all()
        )
        self.assertTrue(
            (artifacts.evidence["annotation_status"] == "not_provided").all()
        )

    def test_confidence_weighted_vote_exports_coverage_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "regime_annotations.csv"
            weighted_vote_fixture().to_csv(path, index=False)
            artifacts = calibrate_from_context(
                self.context,
                self.config,
                regime_annotations_path=path,
            )

        frame = artifacts.frame.set_index("day")
        self.assertEqual(frame.loc[5, "business_validated_regime"], "CRISIS")
        self.assertEqual(frame.loc[5, "calibrated_regime"], "CRISIS")
        self.assertEqual(frame.loc[5, "regime_label_source"], "business_annotation")
        self.assertAlmostEqual(float(frame.loc[5, "business_vote_weight"]), 0.9)
        self.assertAlmostEqual(float(frame.loc[5, "business_total_vote_weight"]), 1.1)
        self.assertEqual(int(frame.loc[5, "business_annotation_conflict"]), 1)
        self.assertEqual(
            frame.loc[5, "business_vote_weights_by_regime"],
            "CRISIS:0.9|NOMINAL:0.2",
        )
        self.assertEqual(
            frame.loc[5, "business_annotation_comments"],
            "major outage | local view",
        )

        self.assertTrue(pd.isna(frame.loc[6, "business_validated_regime"]))
        self.assertEqual(frame.loc[6, "calibrated_regime"], frame.loc[6, "pseudo_regime"])
        self.assertEqual(frame.loc[6, "regime_label_source"], "pseudo_label")
        self.assertEqual(int(frame.loc[6, "business_vote_tie"]), 1)

        self.assertEqual(frame.loc[7, "business_validated_regime"], "RECOVERY")
        self.assertEqual(frame.loc[7, "calibrated_regime"], "RECOVERY")
        self.assertEqual(frame.loc[7, "business_annotation_sites"], "S1|S2")

        metadata = artifacts.metadata["regime_annotations"]
        self.assertEqual(metadata["status"], "annotations_loaded")
        self.assertEqual(metadata["annotation_rows"], 7)
        self.assertEqual(metadata["annotated_days"], 4)
        self.assertEqual(metadata["matched_annotation_days"], 3)
        self.assertEqual(metadata["unmatched_annotation_days"], 1)
        self.assertEqual(metadata["business_label_days"], 2)
        self.assertEqual(metadata["pseudo_label_days"], 26)
        self.assertEqual(metadata["conflict_day_count"], 2)
        self.assertEqual(metadata["tie_day_count"], 1)
        self.assertAlmostEqual(metadata["annotation_coverage_fraction"], 3 / 28)
        self.assertAlmostEqual(metadata["business_label_coverage_fraction"], 2 / 28)
        self.assertEqual(
            metadata["label_provenance"],
            "business_annotations_with_pseudo_fallback",
        )
        self.assertTrue(
            (artifacts.evidence["annotation_conflict_day_count"] == 2).all()
        )
        self.assertTrue(
            (artifacts.evidence["business_label_days"] == 2).all()
        )
        self.assertEqual(
            artifacts.config["calibration"]["regime_annotations"]["annotation_rows"],
            7,
        )

    def test_period_dates_are_mapped_to_simulation_day_offsets(self) -> None:
        source = pd.DataFrame({
            "period": ["2026-10-01", "2026-10-03"],
            "site": ["S1", "S2"],
            "item": ["A1", "A2"],
            "validated_regime": ["NOMINAL", "SUPPLIER_STRESS"],
            "expert_confidence": [0.6, 0.9],
            "comment": ["baseline", "supplier alert"],
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dated_annotations.csv"
            source.to_csv(path, index=False)
            with self.assertRaisesRegex(
                ValueError, "require an explicit baseline calendar origin"
            ):
                load_regime_annotations(path)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dated_annotations_with_origin.csv"
            source.to_csv(path, index=False)
            with_origin = load_regime_annotations(
                path, period_origin="2026-09-28"
            )
        self.assertEqual(with_origin.rows["day"].tolist(), [3, 5])
        self.assertEqual(
            with_origin.metadata["time_mapping"],
            "calendar_day_offset_from_baseline_origin:2026-09-28",
        )

    def test_empty_annotation_file_does_not_claim_business_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty_annotations.csv"
            weighted_vote_fixture().iloc[0:0].to_csv(path, index=False)
            artifacts = calibrate_from_context(
                self.context,
                self.config,
                regime_annotations_path=path,
            )

        metadata = artifacts.metadata["regime_annotations"]
        self.assertEqual(metadata["status"], "provided_empty")
        self.assertEqual(metadata["schema_validation_status"], "passed")
        self.assertEqual(metadata["label_provenance"], "pseudo_labels_only")
        self.assertEqual(metadata["business_label_days"], 0)
        self.assertTrue(
            (artifacts.frame["regime_label_source"] == "pseudo_label").all()
        )

    def test_end_2026_cli_accepts_annotation_path(self) -> None:
        with patch(
            "sys.argv",
            ["run_end_2026_validation.py", "--regime-annotations-csv", "labels.csv"],
        ):
            args = parse_args()

        self.assertEqual(args.regime_annotations_csv, "labels.csv")
        self.assertEqual(Path(args.repo_root).resolve(), REPO_ROOT.resolve())

    def test_schema_regime_and_confidence_validation_is_strict(self) -> None:
        valid = pd.DataFrame({
            "day": [0],
            "site": ["S1"],
            "article": ["A1"],
            "validated_regime": [VALIDATED_REGIMES[0]],
            "expert_confidence": [0.5],
            "comment": ["reviewed"],
        })
        invalid_cases = {
            "unsupported regime": (
                valid.assign(validated_regime="UNKNOWN"),
                "must be one of",
            ),
            "confidence above one": (
                valid.assign(expert_confidence=1.01),
                r"within \[0, 1\]",
            ),
            "missing item": (
                valid.drop(columns="article"),
                "missing required item/article",
            ),
            "fractional day": (
                valid.assign(day=1.5),
                "must be integer simulation days",
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for index, (name, (source, expected)) in enumerate(invalid_cases.items()):
                with self.subTest(name=name):
                    path = Path(tmp) / f"invalid_{index}.csv"
                    source.to_csv(path, index=False)
                    with self.assertRaisesRegex(ValueError, expected):
                        load_regime_annotations(path)


if __name__ == "__main__":
    unittest.main()
