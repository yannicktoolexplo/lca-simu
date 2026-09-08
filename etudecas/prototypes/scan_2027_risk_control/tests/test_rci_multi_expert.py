from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.rci_validation import (
    AUTHORITATIVE_MODEL_RCI_SOURCE,
    RCI_REVIEW_PACK_SCHEMA_VERSION,
    bind_completed_business_review,
    build_blinded_rci_review,
    build_rci_business_validation_pack,
    rci_review_variable_dictionary,
    summarize_completed_business_review,
)


def _long_review(
    ratings: dict[str, list[int]],
    rci_by_episode: dict[str, float],
) -> pd.DataFrame:
    reviewers = [f"expert-{index + 1}" for index in range(len(next(iter(ratings.values()))))]
    rows: list[dict[str, object]] = []
    ordered_episodes = list(ratings)
    for episode_index, episode_id in enumerate(ordered_episodes):
        for reviewer_id, rating in zip(reviewers, ratings[episode_id]):
            rows.append({
                "episode_id": episode_id,
                "reviewer_id": reviewer_id,
                "model_rci": rci_by_episode[episode_id],
                "expert_risk_created_0_1": rating,
                "expert_plausibility_1_5": 5 - episode_index,
                "supplier_pressure_risk_1_5": 5 - episode_index,
                "planning_nervousness_risk_1_5": 5 - episode_index,
                "operational_feasibility_1_5": 2 + episode_index,
                "procurement_acceptability_1_5": 2 + episode_index,
                "planning_acceptability_1_5": 2 + episode_index,
                "expected_service_impact_m2_p2": min(2, episode_index - 1),
                "expert_confidence_1_5": 4,
                "expert_comment": f"Assessment of {episode_id}",
                "is_selected": int(episode_id in {"E1", "E4"}),
                "is_rejected": int(episode_id not in {"E1", "E4"}),
                "is_aggressive": int(episode_id == "E2"),
            })
    return pd.DataFrame(rows)


def _sample_review_pack(model_shift: float = 0.0) -> pd.DataFrame:
    adaptive = pd.DataFrame({
        "base_risk": [0.1] * 8,
        "realized_base_risk": [0.12] * 8,
        "service": [0.98] * 8,
    })
    decisions = pd.DataFrame([{
        "day": 1,
        "selected_policy": "balanced_robust",
        "regime": "strained",
        "observability": 0.8,
        "controllability": 0.7,
    }])
    common = {
        "day": 1,
        "regime": "strained",
        "expected_score": 1.0,
        "mean_nervousness": 0.5,
        "mean_expedite": 0.2,
        "mean_service_loss": 0.1,
        "mean_backlog_area": 2.0,
        "mean_risk_area": 0.4,
        "mean_action_magnitude": 0.3,
        "p90_risk_creation": 0.2,
    }
    candidates = pd.DataFrame([
        {
            **common,
            "policy": "balanced_robust",
            "robust_score": 0.8,
            "mean_risk_creation": 0.02 + model_shift,
        },
        {
            **common,
            "policy": "reactive_buffer",
            "robust_score": 1.2,
            "mean_risk_creation": 0.18 + model_shift,
        },
        {
            **common,
            "policy": "supplier_relief",
            "robust_score": 1.0,
            "mean_risk_creation": -0.01 + model_shift,
        },
    ])
    return build_rci_business_validation_pack(
        adaptive,
        decisions,
        candidates,
        {"review_period_days": 7},
    )


def _completed_blind_review(pack: pd.DataFrame) -> pd.DataFrame:
    completed = build_blinded_rci_review(pack)
    completed["reviewer_id"] = "expert-1"
    completed["expert_risk_created_0_1"] = (
        completed["candidate_policy"].eq("reactive_buffer").astype(int)
    )
    completed["expert_plausibility_1_5"] = 4
    completed["supplier_pressure_risk_1_5"] = 4
    completed["planning_nervousness_risk_1_5"] = 4
    completed["operational_feasibility_1_5"] = 3
    completed["procurement_acceptability_1_5"] = 3
    completed["planning_acceptability_1_5"] = 3
    completed["expected_service_impact_m2_p2"] = 0
    completed["expert_confidence_1_5"] = 4
    completed["expert_comment"] = completed["episode_id"].map(
        lambda episode_id: f"Assessment of {episode_id}"
    )
    return completed


class RciMultiExpertValidationTests(unittest.TestCase):
    def test_pack_identity_survives_standard_and_round_trip_csv_parsers(
        self,
    ) -> None:
        # This shift yields decimal tokens for which pandas' standard parser
        # and round-trip parser choose adjacent binary64 values. Pack identity
        # must intentionally normalize that parser-only difference.
        pack = _sample_review_pack(model_shift=0.07584598159514884)
        blind = build_blinded_rci_review(pack)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            full_path = root / "rci_business_review_template.csv"
            blind_path = root / "rci_business_review_blind.csv"
            pack.to_csv(full_path, index=False)
            blind.to_csv(blind_path, index=False)

            identities: list[tuple[str, str]] = []
            for read_options in ({}, {"float_precision": "round_trip"}):
                authoritative = pd.read_csv(full_path, **read_options)
                completed = pd.read_csv(blind_path, **read_options)
                completed["reviewer_id"] = "expert-1"
                completed["expert_risk_created_0_1"] = (
                    completed["candidate_policy"]
                    .eq("reactive_buffer")
                    .astype(int)
                )
                completed["expert_plausibility_1_5"] = 4
                completed["supplier_pressure_risk_1_5"] = 4
                completed["planning_nervousness_risk_1_5"] = 4
                completed["operational_feasibility_1_5"] = 3
                completed["procurement_acceptability_1_5"] = 3
                completed["planning_acceptability_1_5"] = 3
                completed["expected_service_impact_m2_p2"] = 0
                completed["expert_confidence_1_5"] = 4
                completed["expert_comment"] = completed["episode_id"].map(
                    lambda episode_id: f"Assessment of {episode_id}"
                )

                # Rebuilding the blind view validates the round-tripped full
                # pack before the human-only file is bound to it.
                rebuilt_blind = build_blinded_rci_review(authoritative)
                self.assertEqual(
                    set(rebuilt_blind["review_pack_hash"]),
                    set(completed["review_pack_hash"]),
                )
                bound = bind_completed_business_review(
                    authoritative,
                    completed,
                )
                summary = summarize_completed_business_review(bound)
                self.assertEqual(summary["status"], "review_available")
                identities.append(
                    (
                        summary["review_pack_id"],
                        summary["review_pack_hash"],
                    )
                )

            self.assertEqual(identities[0], identities[1])

    def test_pack_contains_selected_rejected_and_aggressive_candidates(self) -> None:
        adaptive = pd.DataFrame({
            "base_risk": [0.1] * 8,
            "realized_base_risk": [0.12] * 8,
            "service": [0.98] * 8,
        })
        decisions = pd.DataFrame([{
            "day": 1,
            "selected_policy": "balanced_robust",
            "regime": "strained",
            "observability": 0.8,
            "controllability": 0.7,
        }])
        common = {
            "day": 1,
            "regime": "strained",
            "expected_score": 1.0,
            "mean_nervousness": 0.5,
            "mean_expedite": 0.2,
            "mean_service_loss": 0.1,
            "mean_backlog_area": 2.0,
            "mean_risk_area": 0.4,
            "mean_action_magnitude": 0.3,
            "p90_risk_creation": 0.2,
        }
        candidates = pd.DataFrame([
            {
                **common,
                "policy": "balanced_robust",
                "robust_score": 0.8,
                "mean_risk_creation": 0.02,
            },
            {
                **common,
                "policy": "reactive_buffer",
                "robust_score": 1.2,
                "mean_risk_creation": 0.18,
            },
            {
                **common,
                "policy": "supplier_relief",
                "robust_score": 1.0,
                "mean_risk_creation": -0.01,
            },
        ])

        pack = build_rci_business_validation_pack(
            adaptive,
            decisions,
            candidates,
            {"review_period_days": 7},
        )

        self.assertEqual(
            set(pack["candidate_policy"]),
            {"balanced_robust", "reactive_buffer", "supplier_relief"},
        )
        self.assertEqual(int(pack["is_selected"].sum()), 1)
        self.assertEqual(int(pack["is_rejected"].sum()), 2)
        aggressive = pack.loc[pack["candidate_policy"] == "reactive_buffer"].iloc[0]
        self.assertEqual(int(aggressive["is_aggressive"]), 1)
        self.assertEqual(aggressive["review_stratum"], "rejected_aggressive")
        self.assertIn("reviewer_id", pack)
        self.assertIn("expert_risk_created_0_1", pack)
        self.assertIn("expert_plausibility_1_5", pack)
        self.assertIn("operational_feasibility_1_5", pack)
        self.assertIn("procurement_acceptability_1_5", pack)
        self.assertIn("planning_acceptability_1_5", pack)
        self.assertIn("expected_service_impact_m2_p2", pack)
        self.assertIn("expert_confidence_1_5", pack)
        self.assertIn("expert_comment", pack)
        for column in (
            "review_pack_schema_version",
            "review_pack_id",
            "review_pack_hash",
        ):
            self.assertIn(column, pack)
            self.assertEqual(pack[column].nunique(), 1)
        self.assertEqual(
            set(pack["review_pack_schema_version"]),
            {RCI_REVIEW_PACK_SCHEMA_VERSION},
        )
        blind = build_blinded_rci_review(pack)
        self.assertEqual(
            blind[
                [
                    "review_pack_schema_version",
                    "review_pack_id",
                    "review_pack_hash",
                ]
            ].drop_duplicates().to_dict(orient="records"),
            pack[
                [
                    "review_pack_schema_version",
                    "review_pack_id",
                    "review_pack_hash",
                ]
            ].drop_duplicates().to_dict(orient="records"),
        )

    def test_completed_review_binds_authoritative_model_values(self) -> None:
        pack = _sample_review_pack()
        completed = _completed_blind_review(pack)
        # A legacy or malicious model column in the external file is ignored.
        completed["model_rci"] = 999.0

        bound = bind_completed_business_review(pack, completed)

        authoritative = pack.set_index("episode_id")["model_rci"]
        expected = bound["episode_id"].map(authoritative).to_numpy(dtype=float)
        pd.testing.assert_series_equal(
            bound["model_rci"].reset_index(drop=True),
            pd.Series(expected, name="model_rci"),
        )
        self.assertEqual(
            set(bound["model_rci_source"]),
            {AUTHORITATIVE_MODEL_RCI_SOURCE},
        )
        summary = summarize_completed_business_review(bound)
        self.assertEqual(summary["status"], "review_available")
        self.assertEqual(summary["review_pack_id"], pack["review_pack_id"].iloc[0])
        self.assertEqual(
            summary["model_rci_source"],
            AUTHORITATIVE_MODEL_RCI_SOURCE,
        )

    def test_review_binding_rejects_pack_identity_tampering(self) -> None:
        pack = _sample_review_pack()
        completed = _completed_blind_review(pack)
        completed["review_pack_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "incoherent"):
            bind_completed_business_review(pack, completed)

        tampered_pack = pack.copy()
        tampered_pack.loc[tampered_pack.index[0], "model_rci"] += 0.5
        with self.assertRaisesRegex(ValueError, "hash does not match"):
            bind_completed_business_review(
                tampered_pack,
                _completed_blind_review(pack),
            )

    def test_review_binding_rejects_stale_pack(self) -> None:
        original = _sample_review_pack()
        regenerated = _sample_review_pack(model_shift=0.01)
        completed = _completed_blind_review(original)

        with self.assertRaisesRegex(ValueError, "stale or different"):
            bind_completed_business_review(regenerated, completed)

    def test_review_binding_rejects_unknown_episode(self) -> None:
        pack = _sample_review_pack()
        completed = _completed_blind_review(pack)
        unknown = completed.iloc[[0]].copy()
        unknown["episode_id"] = "RCI-UNKNOWN"
        completed = pd.concat([completed, unknown], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "unknown episode_id"):
            bind_completed_business_review(pack, completed)

    def test_review_binding_rejects_duplicate_reviewer_episode(self) -> None:
        pack = _sample_review_pack()
        completed = _completed_blind_review(pack)
        completed = pd.concat(
            [completed, completed.iloc[[0]]],
            ignore_index=True,
        )

        with self.assertRaisesRegex(
            ValueError,
            "duplicate reviewer_id/episode_id",
        ):
            bind_completed_business_review(pack, completed)

    def test_review_binding_rejects_incomplete_episode_panel(self) -> None:
        pack = _sample_review_pack()
        completed = _completed_blind_review(pack).iloc[:-1].copy()

        with self.assertRaisesRegex(
            ValueError,
            "incomplete reviewer-panel coverage",
        ):
            bind_completed_business_review(pack, completed)

    def test_review_binding_requires_each_reviewer_to_cover_full_panel(
        self,
    ) -> None:
        pack = _sample_review_pack()
        first = _completed_blind_review(pack)
        second = _completed_blind_review(pack).iloc[:-1].copy()
        second["reviewer_id"] = "expert-2"
        completed = pd.concat([first, second], ignore_index=True)

        with self.assertRaisesRegex(
            ValueError,
            "incomplete reviewer-panel coverage",
        ):
            bind_completed_business_review(pack, completed)

    def test_review_stays_pending_without_complete_canonical_fields(self) -> None:
        empty = summarize_completed_business_review(pd.DataFrame())
        self.assertEqual(empty["status"], "pending_business_review")
        self.assertEqual(empty["reason"], "no_completed_review_file")

        missing = summarize_completed_business_review(pd.DataFrame([{
            "episode_id": "E1",
            "model_rci": 0.2,
        }]))
        self.assertEqual(missing["status"], "pending_business_review")
        self.assertEqual(missing["reason"], "missing_required_columns")
        self.assertIn("reviewer_id", missing["missing_columns"])

        incomplete = summarize_completed_business_review(pd.DataFrame([{
            "episode_id": "E1",
            "reviewer_id": "expert-1",
            "model_rci": 0.2,
            "expert_risk_created_0_1": "",
            "expert_plausibility_1_5": 4,
            "supplier_pressure_risk_1_5": 4,
            "planning_nervousness_risk_1_5": 4,
            "operational_feasibility_1_5": 3,
            "procurement_acceptability_1_5": 3,
            "planning_acceptability_1_5": 3,
            "expected_service_impact_m2_p2": 0,
            "expert_confidence_1_5": 4,
            "expert_comment": "Incomplete because the binary verdict is absent.",
        }]))
        self.assertEqual(incomplete["status"], "pending_business_review")
        self.assertEqual(incomplete["reason"], "incomplete_required_values")

        missing_comment = _long_review(
            {"E1": [1], "E2": [0]},
            {"E1": 0.8, "E2": 0.1},
        )
        missing_comment.loc[0, "expert_comment"] = " "
        summary = summarize_completed_business_review(missing_comment)
        self.assertEqual(summary["status"], "pending_business_review")
        self.assertEqual(summary["reason"], "incomplete_required_values")

    def test_two_reviewers_use_cohen_kappa_and_report_threshold_metrics(self) -> None:
        review = _long_review(
            {
                "E1": [1, 1],
                "E2": [1, 0],
                "E3": [0, 0],
                "E4": [0, 0],
            },
            {"E1": 0.9, "E2": 0.7, "E3": 0.2, "E4": 0.1},
        )

        summary = summarize_completed_business_review(review)

        self.assertEqual(summary["status"], "review_available")
        self.assertEqual(summary["agreement_method"], "cohen_kappa")
        self.assertEqual(summary["agreement_status"], "computed")
        self.assertAlmostEqual(float(summary["agreement_value"]), 0.5)
        self.assertAlmostEqual(float(summary["recommended_rci_threshold"]), 0.9)
        self.assertEqual(summary["unresolved_tied_episodes"], 1)
        self.assertEqual(summary["unresolved_tied_episode_ids"], ["E2"])
        self.assertEqual(summary["resolved_consensus_episodes"], 3)
        self.assertEqual(
            summary["performance_estimation_method"],
            "leave_one_episode_out",
        )
        self.assertEqual(summary["performance_evaluated_episodes"], 0)
        self.assertEqual(summary["performance_excluded_episodes"], 3)
        self.assertEqual(summary["performance_status"], "not_estimable")
        self.assertEqual(
            summary["performance_detail_status"],
            "not_estimable_insufficient_class_replication",
        )
        self.assertIsInstance(summary["fit_metrics"], dict)
        self.assertEqual(summary["fit_metrics_scope"], "in_sample_resolved_episodes")
        self.assertAlmostEqual(float(summary["spearman_rci_vs_plausibility"]), 1.0)
        self.assertIn("spearman_rci_vs_expert_risk_positive_rate", summary)
        self.assertIn("spearman_rci_vs_supplier_pressure_risk", summary)
        self.assertIn("spearman_rci_vs_planning_nervousness_risk", summary)
        self.assertIsNone(summary["confusion_matrix"])
        self.assertEqual(summary["review_scope"]["selected_episode_count"], 2)
        self.assertEqual(summary["review_scope"]["rejected_episode_count"], 2)
        self.assertEqual(summary["review_scope"]["aggressive_episode_count"], 1)

    def test_loo_performance_requires_and_uses_two_episodes_per_class(self) -> None:
        review = _long_review(
            {
                "E1": [1, 1],
                "E2": [1, 1],
                "E3": [0, 0],
                "E4": [0, 0],
            },
            {"E1": 0.9, "E2": 0.7, "E3": 0.2, "E4": 0.1},
        )

        summary = summarize_completed_business_review(review)

        self.assertEqual(summary["performance_detail_status"], "computed")
        self.assertEqual(summary["performance_status"], "exploratory_small_sample")
        self.assertEqual(summary["performance_evaluated_episodes"], 4)
        self.assertEqual(summary["performance_excluded_episodes"], 0)
        self.assertEqual(
            summary["false_positives"]
            + summary["false_negatives"]
            + summary["confusion_matrix"]["tp"]
            + summary["confusion_matrix"]["tn"],
            4,
        )

    def test_single_consensus_class_does_not_claim_discriminating_threshold(
        self,
    ) -> None:
        review = _long_review(
            {
                "E1": [1, 1],
                "E2": [1, 1],
                "E3": [1, 1],
            },
            {"E1": 0.9, "E2": 0.7, "E3": 0.2},
        )

        summary = summarize_completed_business_review(review)

        self.assertIsNone(summary["recommended_rci_threshold"])
        self.assertEqual(
            summary["threshold_estimation_status"],
            "not_estimable_single_consensus_class",
        )
        self.assertEqual(summary["resolved_consensus_class_counts"], {"1": 3})
        self.assertIsNone(summary["fit_metrics"])
        self.assertEqual(summary["performance_status"], "not_estimable")
        self.assertEqual(
            summary["performance_detail_status"],
            "not_estimable_single_consensus_class",
        )
        self.assertIsNone(summary["confusion_matrix"])

    def test_more_than_two_reviewers_use_fleiss_kappa(self) -> None:
        review = _long_review(
            {
                "E1": [1, 1, 1],
                "E2": [1, 1, 0],
                "E3": [0, 0, 0],
                "E4": [0, 0, 1],
            },
            {"E1": 0.9, "E2": 0.7, "E3": 0.2, "E4": 0.1},
        )

        summary = summarize_completed_business_review(review)

        self.assertEqual(summary["status"], "review_available")
        self.assertEqual(summary["agreement_method"], "fleiss_kappa")
        self.assertEqual(summary["agreement_status"], "computed")
        self.assertAlmostEqual(float(summary["agreement_value"]), 1.0 / 3.0)
        self.assertEqual(summary["inter_rater_agreement"]["reviewer_count"], 3)
        self.assertEqual(summary["inter_rater_agreement"]["episodes_used"], 4)

    def test_one_reviewer_reports_insufficient_agreement(self) -> None:
        review = _long_review(
            {"E1": [1], "E2": [0]},
            {"E1": 0.8, "E2": 0.1},
        )

        summary = summarize_completed_business_review(review)

        self.assertEqual(summary["status"], "review_available")
        self.assertIsNone(summary["agreement_method"])
        self.assertEqual(summary["agreement_status"], "insufficient_reviewers")
        self.assertIsNone(summary["agreement_value"])

    def test_variable_dictionary_covers_required_business_questions(self) -> None:
        dictionary = rci_review_variable_dictionary().set_index("variable")
        for field in (
            "supplier_pressure_risk_1_5",
            "planning_nervousness_risk_1_5",
            "operational_feasibility_1_5",
            "procurement_acceptability_1_5",
            "planning_acceptability_1_5",
            "expected_service_impact_m2_p2",
            "expert_confidence_1_5",
            "expert_comment",
        ):
            self.assertIn(field, dictionary.index)
            self.assertEqual(dictionary.loc[field, "role"], "required_expert_input")


if __name__ == "__main__":
    unittest.main()
