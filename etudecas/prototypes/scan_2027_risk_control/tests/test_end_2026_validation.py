from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
from etudecas.prototypes.scan_2027_risk_control.end_2026_reporting import (
    _portfolio_scope,
    derive_regime_recovery_episodes,
    save_regime_recovery_plot,
    save_rci_business_comparison_plot,
    summarize_regime_recovery,
)
from etudecas.prototypes.scan_2027_risk_control.experiments import (
    _paired_cohens_dz,
    build_confusion_context,
    build_truth_physical_envelope,
    forecast_confusion_experiment,
    forecast_confusion_sensitivity_experiment,
    paired_policy_experiment,
)
from etudecas.prototypes.scan_2027_risk_control.rci_validation import (
    REDUCED_RCI_CANONICAL_TRANSFERABILITY,
    REDUCED_RCI_DEFINITION_VERSION,
    REDUCED_RCI_SCOPE,
    build_blinded_rci_review,
    build_rci_business_validation_pack,
    summarize_completed_business_review,
)
from etudecas.prototypes.scan_2027_risk_control.run_end_2026_validation import (
    _canonical_execution_metadata,
    _parse_sensitivity_factors,
    _run_canonical_stage,
)
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

    def test_mapping_sensitivity_factors_require_positive_finite_values(
        self,
    ) -> None:
        self.assertEqual(
            _parse_sensitivity_factors("0.75,1,1.25"),
            (0.75, 1.0, 1.25),
        )
        for invalid in ("", "0,1", "-1,1", "nan,1", "inf,1"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _parse_sensitivity_factors(invalid)

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

    def test_reporting_selects_only_portfolio_rows_from_granular_exports(self) -> None:
        combined = pd.DataFrame({
            "day": [0, 0, 0, 1, 1],
            "scope": [
                "portfolio",
                "supplier_item_destination",
                "supplier_item_destination",
                " portfolio ",
                "supplier_item_destination",
            ],
            "risk_center": [0.25, 0.80, 0.50, 0.30, 0.65],
        })
        selected = _portfolio_scope(combined)
        self.assertEqual(selected["day"].tolist(), [0, 1])
        self.assertEqual(selected["risk_center"].tolist(), [0.25, 0.30])
        self.assertEqual(len(combined), 5)

    def test_regime_recovery_reports_stable_returns_and_censoring(self) -> None:
        trajectory = pd.DataFrame(
            {
                "day": np.arange(12),
                "regime": [
                    "NOMINAL",
                    "SUPPLIER_STRESS",
                    "SUPPLIER_STRESS",
                    "NOMINAL",
                    "MATERIAL_TENSION",
                    "NOMINAL",
                    "NOMINAL",
                    "NOMINAL",
                    "CRISIS",
                    "RECOVERY",
                    "NOMINAL",
                    "NOMINAL",
                ],
            }
        )
        episodes = derive_regime_recovery_episodes(
            trajectory,
            stable_nominal_days=3,
        )

        self.assertEqual(len(episodes), 2)
        recovered = episodes.iloc[0]
        self.assertEqual(recovered["entry_regime"], "SUPPLIER_STRESS")
        self.assertEqual(recovered["regime_path"], (
            "SUPPLIER_STRESS > NOMINAL > MATERIAL_TENSION"
        ))
        self.assertEqual(recovered["stable_nominal_start_day"], 5.0)
        self.assertEqual(recovered["recovery_time_days"], 4.0)
        self.assertFalse(bool(recovered["right_censored"]))

        censored = episodes.iloc[1]
        self.assertEqual(censored["entry_regime"], "CRISIS")
        self.assertTrue(bool(censored["right_censored"]))
        self.assertTrue(np.isnan(censored["recovery_time_days"]))
        self.assertEqual(censored["duration_or_lower_bound_days"], 4.0)
        self.assertEqual(censored["status"], "right_censored")

        summary = summarize_regime_recovery(
            episodes,
            stable_nominal_days=3,
        )
        self.assertEqual(summary["episode_count"], 2)
        self.assertEqual(summary["observed_recoveries"], 1)
        self.assertEqual(summary["right_censored_episodes"], 1)
        self.assertEqual(
            summary["attribution"],
            "entry_regime_descriptive_not_causal",
        )

        left_truncated = derive_regime_recovery_episodes(
            pd.DataFrame(
                {
                    "day": np.arange(4),
                    "regime": [
                        "CRISIS",
                        "NOMINAL",
                        "NOMINAL",
                        "NOMINAL",
                    ],
                }
            ),
            stable_nominal_days=3,
        )
        self.assertTrue(bool(left_truncated.loc[0, "left_truncated"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_regime_recovery_plot(Path(temp_dir), episodes)
            self.assertTrue(path.is_file())
            self.assertEqual(
                path.name,
                "regime_recovery_time_by_entry_regime.png",
            )

    def test_rci_business_plot_requires_completed_expert_evaluations(
        self,
    ) -> None:
        completed = pd.DataFrame(
            [
                {
                    "episode_id": episode_id,
                    "reviewer_id": reviewer_id,
                    "model_rci": model_rci,
                    "expert_risk_created_0_1": expert_risk,
                    "expert_plausibility_1_5": plausibility,
                    "supplier_pressure_risk_1_5": plausibility,
                    "planning_nervousness_risk_1_5": plausibility,
                    "operational_feasibility_1_5": 3,
                    "procurement_acceptability_1_5": 3,
                    "planning_acceptability_1_5": 3,
                    "expected_service_impact_m2_p2": 0,
                    "expert_confidence_1_5": 4,
                    "expert_comment": f"Review of {episode_id}",
                }
                for episode_id, model_rci, expert_risk, plausibility in (
                    ("E1", 0.8, 1, 5),
                    ("E2", 0.2, 0, 2),
                )
                for reviewer_id in ("procurement", "planning")
            ]
        )
        status = summarize_completed_business_review(completed)
        self.assertEqual(status["status"], "review_available")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            pending = save_rci_business_comparison_plot(
                output_dir,
                pd.DataFrame(),
                {"status": "pending_business_review"},
            )
            self.assertIsNone(pending)
            expected = (
                output_dir
                / "plots"
                / "end_2026"
                / "rci_model_vs_business_evaluations.png"
            )
            self.assertFalse(expected.exists())

            generated = save_rci_business_comparison_plot(
                output_dir,
                completed,
                status,
            )
            self.assertEqual(generated, expected)
            self.assertTrue(expected.is_file())

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

    def test_adaptive_decision_is_applied_and_labelled_on_next_day(self) -> None:
        forecast_paths: list[np.ndarray] = []

        def deterministic_selection(
            _state: object,
            _actions: object,
            demand_path: np.ndarray,
            _risk_path: np.ndarray,
            _scenarios: object,
            _config: object,
        ) -> pd.DataFrame:
            forecast_paths.append(demand_path.copy())
            return pd.DataFrame([{
                "policy": "supplier_relief",
                "robust_score": 0.0,
            }])

        with patch(
            "etudecas.prototypes.scan_2027_risk_control.decision.evaluate_actions",
            side_effect=deterministic_selection,
        ):
            trajectory, decisions, candidates = run_adaptive_controller(
                self.context, self.config, DEFAULT_ACTIONS, 55
            )

        self.assertEqual(trajectory.iloc[0]["selected_policy"], "mrp_reference")
        self.assertEqual(int(decisions.iloc[0]["decision_day"]), 0)
        self.assertEqual(int(decisions.iloc[0]["day"]), 1)
        self.assertEqual(int(candidates.iloc[0]["decision_day"]), 0)
        self.assertEqual(int(candidates.iloc[0]["day"]), 1)
        self.assertEqual(trajectory.iloc[1]["selected_policy"], "supplier_relief")
        for decision in decisions.itertuples():
            self.assertEqual(
                trajectory.iloc[int(decision.day)]["selected_policy"],
                decision.selected_policy,
            )
        expected_first_path = self.context.input_series["demand"].iloc[1:8].to_numpy(dtype=float)
        np.testing.assert_allclose(forecast_paths[0], expected_first_path)

    def test_paired_comparison_has_exact_zero_reference_delta(self) -> None:
        runs, summary = paired_policy_experiment(self.context, self.config, DEFAULT_ACTIONS, [11, 12])
        self.assertFalse(runs.empty)
        expected_policies = {action.name for action in DEFAULT_ACTIONS} | {"adaptive", "oracle"}
        self.assertEqual(set(runs["policy"]), expected_policies)
        self.assertEqual(set(summary["policy"]), expected_policies)
        self.assertIn("mrp_reference_score", runs)
        self.assertIn("delta_vs_mrp_score", runs)
        per_seed_reference = runs.loc[runs["policy"] == "mrp_reference"]
        self.assertTrue(
            (per_seed_reference["delta_vs_mrp_score"] == 0.0).all()
        )
        self.assertTrue(
            (
                runs["delta_vs_mrp_score"]
                - (runs["score"] - runs["mrp_reference_score"])
            )
            .abs()
            .lt(1e-12)
            .all()
        )
        for seed, group in runs.groupby("seed"):
            self.assertEqual(group["scenario_seed"].nunique(), 1)
            fixed = group.loc[group["run_type"] == "fixed"]
            oracle = group.loc[group["policy"] == "oracle"].iloc[0]
            self.assertAlmostEqual(float(oracle["score"]), float(fixed["score"].min()), places=12)
            self.assertIn(str(oracle["oracle_fixed_policy"]), set(fixed["policy"]))
        reference = summary.loc[summary["policy"] == "mrp_reference"].iloc[0]
        self.assertEqual(int(reference["paired_seed_count"]), 2)
        zero_columns = [
            column for column in summary.columns
            if column.startswith((
                "mean_delta_", "median_delta_", "ci95_low_delta_",
                "ci95_high_delta_", "p90_delta_", "standardized_effect_delta_",
                "cohen_dz_delta_",
            ))
        ]
        self.assertTrue(zero_columns)
        self.assertTrue((reference[zero_columns].astype(float) == 0.0).all())
        self.assertIn("median_delta_score", summary)
        self.assertIn("standardized_effect_delta_score", summary)
        self.assertIn("standardized_effect_status_delta_score", summary)
        self.assertIn("cohen_dz_delta_score", summary)
        self.assertIn("cohen_dz_status_delta_score", summary)
        self.assertIn("win_rate_vs_mrp_constraint_violation_count", summary)
        self.assertEqual(
            reference["standardized_effect_status_delta_score"],
            "exact_reference_zero",
        )
        for row in summary.itertuples(index=False):
            effect = float(row.standardized_effect_delta_score)
            cohen_alias = float(row.cohen_dz_delta_score)
            if str(row.standardized_effect_status_delta_score).startswith(
                "not_estimable"
            ):
                self.assertTrue(np.isnan(effect))
                self.assertTrue(np.isnan(cohen_alias))
            else:
                self.assertTrue(np.isfinite(effect))
                self.assertEqual(effect, cohen_alias)

    def test_paired_effect_is_conventional_cohens_dz(self) -> None:
        effect, status = _paired_cohens_dz(pd.Series([1.0, 2.0, 3.0]))
        self.assertEqual(status, "paired_cohens_dz")
        self.assertAlmostEqual(effect, 2.0)

        effect, status = _paired_cohens_dz(pd.Series([2.0, 2.0, 2.0]))
        self.assertEqual(status, "not_estimable_zero_paired_variance")
        self.assertTrue(np.isnan(effect))

        effect, status = _paired_cohens_dz(
            pd.Series([0.0, 0.0]),
            exact_reference=True,
        )
        self.assertEqual(status, "exact_reference_zero")
        self.assertEqual(effect, 0.0)

    def test_paired_experiment_rejects_duplicate_seeds(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            paired_policy_experiment(
                self.context,
                self.config,
                DEFAULT_ACTIONS,
                [11, 11],
            )

    def test_confusion_experiment_reports_regret_against_mrp(self) -> None:
        runs, summary, regret = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=12,
        )
        self.assertEqual(set(runs["case"]), {"TP", "FP", "FN", "TN"})
        self.assertEqual(set(summary["case"]), {"TP", "FP", "FN", "TN"})
        case_design = (
            runs.set_index("case")[
                [
                    "predicted_event",
                    "truth_event",
                    "alert_triggered",
                    "incident_occurred",
                    "action_taken",
                ]
            ]
            .astype(int)
            .to_dict(orient="index")
        )
        self.assertEqual(
            case_design,
            {
                "TP": {
                    "predicted_event": 1,
                    "truth_event": 1,
                    "alert_triggered": 1,
                    "incident_occurred": 1,
                    "action_taken": 1,
                },
                "FP": {
                    "predicted_event": 1,
                    "truth_event": 0,
                    "alert_triggered": 1,
                    "incident_occurred": 0,
                    "action_taken": 1,
                },
                "FN": {
                    "predicted_event": 0,
                    "truth_event": 1,
                    "alert_triggered": 0,
                    "incident_occurred": 1,
                    "action_taken": 0,
                },
                "TN": {
                    "predicted_event": 0,
                    "truth_event": 0,
                    "alert_triggered": 0,
                    "incident_occurred": 0,
                    "action_taken": 0,
                },
            },
        )
        expected_regret_columns = {
            "service_loss_regret_vs_mrp",
            "backlog_regret_vs_mrp",
            "nervousness_regret_vs_mrp",
            "risk_creation_regret_vs_mrp",
            "expedite_regret_vs_mrp",
            "unused_stock_regret_vs_mrp",
            "over_ordering_regret_vs_mrp",
            "total_cost_regret_vs_mrp",
            "supplier_stress_regret_vs_mrp",
        }
        self.assertTrue(expected_regret_columns.issubset(regret.columns))
        self.assertTrue(np.isfinite(regret[list(expected_regret_columns)].to_numpy(dtype=float)).all())
        by_case = runs.set_index("case")
        self.assertAlmostEqual(
            float(by_case.loc["TP", "mrp_service_loss"]),
            float(by_case.loc["FN", "mrp_service_loss"]),
            places=12,
        )
        self.assertAlmostEqual(
            float(by_case.loc["FP", "mrp_backlog_area"]),
            float(by_case.loc["TN", "mrp_backlog_area"]),
            places=12,
        )
        mrp_metric_columns = [
            column for column in runs.columns if column.startswith("mrp_")
        ]
        for left, right in (("TP", "FN"), ("FP", "TN")):
            np.testing.assert_allclose(
                by_case.loc[left, mrp_metric_columns].to_numpy(dtype=float),
                by_case.loc[right, mrp_metric_columns].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            )
        consequence_columns = [
            "order_area",
            "nervousness_area",
            "supplier_stress_area",
            "risk_creation_area",
            "total_cost_proxy",
        ]
        for alerted, not_alerted in (("TP", "FN"), ("FP", "TN")):
            self.assertTrue(
                (
                    by_case.loc[alerted, consequence_columns].astype(float)
                    - by_case.loc[
                        not_alerted, consequence_columns
                    ].astype(float)
                )
                .abs()
                .gt(1e-9)
                .any()
            )
        correct = regret.loc[regret["case"].isin(["TP", "TN"])]
        oracle_regret_columns = [
            column
            for column in regret.columns
            if column.endswith("_regret")
        ]
        self.assertTrue(oracle_regret_columns)
        self.assertTrue(
            (
                correct[oracle_regret_columns].to_numpy(dtype=float) == 0.0
            ).all()
        )
        self.assertEqual(
            set(regret["benchmark_definition"]),
            {"matched_truth_correct_forecast_gated_response"},
        )

    def test_confusion_design_rejects_semantically_ambiguous_cases(self) -> None:
        with self.assertRaisesRegex(ValueError, "separate"):
            forecast_confusion_experiment(
                self.context,
                self.config,
                DEFAULT_ACTIONS,
                [91],
                start_day=8,
                forecast_low_probability=0.08,
                forecast_high_probability=0.82,
                alert_threshold=0.90,
            )
        with self.assertRaisesRegex(ValueError, "pre-event"):
            forecast_confusion_experiment(
                self.context,
                self.config,
                DEFAULT_ACTIONS,
                [91],
                start_day=0,
            )

    def test_legacy_confusion_probability_aliases_remain_compatible(
        self,
    ) -> None:
        legacy_runs, _, _ = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=12,
            low_probability=0.10,
            high_probability=0.80,
        )
        explicit_runs, _, _ = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=12,
            forecast_low_probability=0.10,
            forecast_high_probability=0.80,
            truth_nominal_probability=0.10,
            truth_incident_probability=0.80,
        )
        pd.testing.assert_frame_equal(legacy_runs, explicit_runs)
        with self.assertRaisesRegex(ValueError, "Do not combine"):
            forecast_confusion_experiment(
                self.context,
                self.config,
                DEFAULT_ACTIONS,
                [91],
                start_day=8,
                low_probability=0.10,
                high_probability=0.80,
                truth_nominal_probability=0.08,
            )

    def test_alert_response_duration_keeps_physical_truth_fixed(self) -> None:
        short_runs, _, _ = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=7,
            incident_duration_days=12,
            forecast_signal_duration_days=12,
        )
        long_runs, _, _ = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=12,
            incident_duration_days=12,
            forecast_signal_duration_days=12,
        )
        short_by_case = short_runs.set_index("case")
        long_by_case = long_runs.set_index("case")
        for case in ("TP", "FP", "FN", "TN"):
            self.assertEqual(
                short_by_case.loc[case, "physical_scenario_fingerprint"],
                long_by_case.loc[case, "physical_scenario_fingerprint"],
            )
        mrp_columns = [
            column for column in short_runs if column.startswith("mrp_")
        ]
        for case in ("TP", "FP", "FN", "TN"):
            np.testing.assert_allclose(
                short_by_case.loc[case, mrp_columns].to_numpy(dtype=float),
                long_by_case.loc[case, mrp_columns].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            )
        consequence_columns = [
            "service_loss",
            "backlog_area",
            "order_area",
            "nervousness_area",
            "supplier_stress_area",
            "supplier_risk_area",
            "total_cost_proxy",
        ]
        for case in ("FN", "TN"):
            np.testing.assert_allclose(
                short_by_case.loc[
                    case, consequence_columns
                ].to_numpy(dtype=float),
                long_by_case.loc[
                    case, consequence_columns
                ].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            )
        self.assertEqual(
            int(short_by_case.loc["TP", "response_action_days"]),
            7,
        )
        self.assertEqual(
            int(long_by_case.loc["TP", "response_action_days"]),
            12,
        )

    def test_forecast_probabilities_do_not_change_physical_truth(self) -> None:
        conservative_runs, _, _ = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=12,
            incident_duration_days=12,
            forecast_signal_duration_days=12,
            forecast_low_probability=0.05,
            forecast_high_probability=0.75,
            truth_nominal_probability=0.08,
            truth_incident_probability=0.82,
            alert_threshold=0.50,
            interval_half_width=0.05,
        )
        severe_forecast_runs, _, _ = forecast_confusion_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            duration_days=12,
            incident_duration_days=12,
            forecast_signal_duration_days=12,
            forecast_low_probability=0.10,
            forecast_high_probability=0.90,
            truth_nominal_probability=0.08,
            truth_incident_probability=0.82,
            alert_threshold=0.50,
            interval_half_width=0.05,
        )
        conservative_by_case = conservative_runs.set_index("case")
        severe_by_case = severe_forecast_runs.set_index("case")
        mrp_columns = [
            column
            for column in conservative_runs
            if column.startswith("mrp_")
        ]
        for case in ("TP", "FP", "FN", "TN"):
            self.assertEqual(
                conservative_by_case.loc[
                    case, "physical_scenario_fingerprint"
                ],
                severe_by_case.loc[
                    case, "physical_scenario_fingerprint"
                ],
            )
            np.testing.assert_allclose(
                conservative_by_case.loc[
                    case, mrp_columns
                ].to_numpy(dtype=float),
                severe_by_case.loc[
                    case, mrp_columns
                ].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            )
        self.assertNotAlmostEqual(
            float(conservative_by_case.loc["TP", "response_intensity"]),
            float(severe_by_case.loc["TP", "response_intensity"]),
        )

    def test_confusion_sensitivity_grid_exports_richer_operational_metrics(self) -> None:
        sensitivity = forecast_confusion_sensitivity_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            alert_thresholds=[0.4, 0.7],
            interval_half_widths=[0.05, 0.18],
            alert_durations_days=[7, 12],
        )
        self.assertEqual(len(sensitivity), 2 * 2 * 2 * 4)
        self.assertEqual(set(sensitivity["case"]), {"TP", "FP", "FN", "TN"})
        self.assertEqual(set(sensitivity["alert_threshold"]), {0.4, 0.7})
        self.assertEqual(set(sensitivity["interval_half_width"]), {0.05, 0.18})
        self.assertEqual(set(sensitivity["alert_duration_days"]), {7, 12})
        self.assertEqual(
            sensitivity.groupby("alert_threshold")["low_probability"].nunique().max(),
            1,
        )
        self.assertEqual(
            sensitivity.groupby("alert_threshold")["high_probability"].nunique().max(),
            1,
        )
        probability_pairs = sensitivity[
            ["alert_threshold", "low_probability", "high_probability"]
        ].drop_duplicates()
        self.assertEqual(probability_pairs["low_probability"].nunique(), 1)
        self.assertEqual(probability_pairs["high_probability"].nunique(), 1)
        single_threshold = forecast_confusion_sensitivity_experiment(
            self.context,
            self.config,
            DEFAULT_ACTIONS,
            [91],
            start_day=8,
            alert_thresholds=[0.4],
            interval_half_widths=[0.05],
            alert_durations_days=[7],
        ).sort_values("case")
        matching_multi = sensitivity.loc[
            (sensitivity["alert_threshold"] == 0.4)
            & (sensitivity["interval_half_width"] == 0.05)
            & (sensitivity["alert_duration_days"] == 7)
        ].sort_values("case")
        for column in (
            "low_probability",
            "high_probability",
            "response_intensity",
            "mean_order_area",
            "mean_nervousness_area",
            "mean_supplier_risk_area",
        ):
            np.testing.assert_allclose(
                single_threshold[column].to_numpy(dtype=float),
                matching_multi[column].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            )
        tp_intensity = (
            sensitivity.loc[sensitivity["case"] == "TP"]
            .groupby(["alert_threshold", "interval_half_width"])[
                "response_intensity"
            ]
            .mean()
        )
        for threshold in (0.4, 0.7):
            self.assertGreater(
                float(tp_intensity.loc[(threshold, 0.18)]),
                float(tp_intensity.loc[(threshold, 0.05)]),
            )
        for column in (
            "mean_unused_stock_area",
            "mean_post_event_overstock_area",
            "mean_over_ordering_area",
            "mean_total_cost_proxy",
            "mean_supplier_stress_area",
            "service_loss_regret",
            "service_loss_regret_vs_mrp",
            "total_cost_regret",
            "total_cost_regret_vs_mrp",
        ):
            self.assertIn(column, sensitivity)
            self.assertTrue(np.isfinite(sensitivity[column]).all())

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
        self.assertTrue((review["is_aggressive"] == 1).any())
        self.assertIn("decision_eligible", review)
        self.assertIn("candidate_evaluation_scope", review)
        self.assertTrue(
            (
                review.loc[
                    review["is_aggressive"] == 1,
                    "candidate_policy",
                ]
                == "reactive_buffer"
            ).all()
        )
        self.assertGreater(review["model_rci"].max(), review["model_rci"].min())
        self.assertEqual(set(review["model_rci_scope"]), {REDUCED_RCI_SCOPE})
        self.assertEqual(
            set(review["model_rci_definition_version"]),
            {REDUCED_RCI_DEFINITION_VERSION},
        )
        self.assertEqual(
            set(review["model_rci_canonical_transferability"]),
            {REDUCED_RCI_CANONICAL_TRANSFERABILITY},
        )

        blinded = build_blinded_rci_review(review)
        self.assertEqual(set(blinded["episode_id"]), set(review["episode_id"]))
        forbidden = {
            "selected_policy",
            "is_selected",
            "is_rejected",
            "is_aggressive",
            "review_stratum",
            "robust_score",
            "expected_score",
            "review_priority",
            "decision_eligible",
            "candidate_evaluation_scope",
        }
        self.assertTrue(forbidden.isdisjoint(blinded.columns))
        self.assertFalse(
            any(column.startswith("model_rci") for column in blinded.columns)
        )
        self.assertFalse(
            any(
                column.startswith("selected_window_")
                for column in blinded.columns
            )
        )
        self.assertFalse(
            blinded["mechanism_to_review"]
            .astype(str)
            .str.contains(
                "modelled|high order-plan|sustained expediting",
                case=False,
                regex=True,
            )
            .any()
        )

    def test_canonical_status_counts_only_complete_physical_replays(self) -> None:
        runs = pd.DataFrame(
            [
                {
                    "policy": "mrp_reference",
                    "seed": 1,
                    "status": "ok",
                    "run_kind": "physical_replay",
                    "is_derived": 0,
                },
                {
                    "policy": "balanced_robust",
                    "seed": 1,
                    "status": "invalid_output",
                    "returncode": 0,
                    "error": "missing action ledger",
                    "run_kind": "physical_replay",
                    "is_derived": 0,
                },
                {
                    "policy": "oracle",
                    "seed": 1,
                    "status": "ok",
                    "run_kind": "derived_oracle",
                    "is_derived": 1,
                },
            ]
        )
        partial = _canonical_execution_metadata(runs, expected_runs=2)
        self.assertEqual(partial["status"], "partial_failure")
        self.assertEqual(partial["successful_runs"], 1)
        self.assertEqual(partial["failed_runs"], 1)
        self.assertEqual(partial["derived_oracle_rows"], 1)
        self.assertEqual(partial["errors"][0]["status"], "invalid_output")

        executed = _canonical_execution_metadata(
            runs.assign(status="ok"),
            expected_runs=2,
        )
        self.assertEqual(executed["status"], "executed")
        self.assertEqual(executed["successful_runs"], 2)

        missing = _canonical_execution_metadata(
            runs.iloc[[0, 2]],
            expected_runs=2,
        )
        self.assertEqual(missing["status"], "partial_failure")
        self.assertEqual(missing["missing_runs"], 1)
        self.assertTrue(
            any(error["status"] == "missing_replay_rows" for error in missing["errors"])
        )

        duplicate_and_missing = _canonical_execution_metadata(
            pd.DataFrame(
                [
                    {
                        "policy": "mrp_reference",
                        "seed": 1,
                        "status": "ok",
                        "run_kind": "physical_replay",
                        "is_derived": 0,
                    },
                    {
                        "policy": "mrp_reference",
                        "seed": 1,
                        "status": "ok",
                        "run_kind": "physical_replay",
                        "is_derived": 0,
                    },
                ]
            ),
            expected_runs=2,
            expected_policies=["mrp_reference", "balanced_robust"],
            expected_seeds=[1],
        )
        self.assertEqual(duplicate_and_missing["status"], "execution_failed")
        self.assertEqual(duplicate_and_missing["successful_runs"], 0)
        self.assertEqual(duplicate_and_missing["missing_runs"], 1)
        self.assertEqual(duplicate_and_missing["unexpected_runs"], 1)
        self.assertEqual(
            duplicate_and_missing["missing_identities"],
            [{"policy": "balanced_robust", "seed": 1}],
        )
        self.assertEqual(
            duplicate_and_missing["duplicate_identities"][0]["policy"],
            "mrp_reference",
        )

    @patch(
        "etudecas.prototypes.scan_2027_risk_control."
        "run_end_2026_validation.run_canonical_replays"
    )
    @patch(
        "etudecas.prototypes.scan_2027_risk_control."
        "run_end_2026_validation.prepare_canonical_overlay_package"
    )
    def test_canonical_modes_call_and_export_exclusively(
        self,
        prepare_overlay,
        run_replays,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graph_path = root / "graph.json"
            graph_path.write_text("{}", encoding="utf-8")
            output_root = root / "canonical"
            legacy_rows = pd.DataFrame(
                [
                    {
                        "policy": "adaptive_weighted_replay",
                        "integration_mode": (
                            "legacy_fixed_overlay_prepared"
                        ),
                    }
                ]
            )

            def prepare_side_effect(**kwargs):
                legacy_dir = (
                    Path(kwargs["output_root"])
                    / "adaptive_weighted_replay"
                )
                legacy_dir.mkdir(parents=True)
                return pd.DataFrame(), legacy_rows

            prepare_overlay.side_effect = prepare_side_effect
            (
                overlay_runs,
                overlay_summary,
                overlay_rows,
                overlay_metadata,
            ) = _run_canonical_stage(
                mode="overlay",
                repo_root=root,
                graph_path=graph_path,
                decisions=pd.DataFrame(),
                actions=DEFAULT_ACTIONS[:1],
                output_root=output_root,
                days=7,
                scenario_id="scn:BASE",
                seed=7,
                seed_count=1,
                prediction_path=None,
                physical_risk_envelope=pd.DataFrame(),
                risk_top_pairs=1,
                engine_extra_args=(),
                engine_profile={"enabled": False},
            )
            prepare_overlay.assert_called_once()
            run_replays.assert_not_called()
            self.assertEqual(
                overlay_metadata["status"],
                "overlays_prepared",
            )
            self.assertEqual(
                overlay_metadata["integration_mode"],
                "legacy_fixed_overlay_prepared",
            )
            self.assertEqual(
                overlay_rows["policy"].tolist(),
                ["adaptive_weighted_replay"],
            )
            self.assertTrue(overlay_runs.empty)
            self.assertTrue(overlay_summary.empty)
            self.assertIn("policy", overlay_runs)
            self.assertIn("recovery_status", overlay_runs)
            self.assertIn("policy", overlay_summary)
            self.assertIn(
                "ci95_status_delta_service_loss",
                overlay_summary,
            )
            overlay_runs.to_csv(
                root / "empty_canonical_runs.csv",
                index=False,
            )
            overlay_summary.to_csv(
                root / "empty_canonical_summary.csv",
                index=False,
            )
            self.assertTrue(
                pd.read_csv(root / "empty_canonical_runs.csv").empty
            )
            self.assertTrue(
                pd.read_csv(root / "empty_canonical_summary.csv").empty
            )
            exported_overlay = pd.read_csv(
                output_root / "canonical_control_overlays.csv"
            )
            self.assertEqual(
                exported_overlay["integration_mode"].tolist(),
                ["legacy_fixed_overlay_prepared"],
            )

            (output_root / "canonical_supplier_risk_events.csv").write_text(
                "supplier_id,item_id,dst_node_id\nstale,item:stale,stale\n",
                encoding="utf-8",
            )
            (
                output_root / "canonical_risk_mapping_ledger.csv"
            ).write_text("mapping_status\nstale\n", encoding="utf-8")
            replay_runs = pd.DataFrame(
                [
                    {
                        "policy": policy,
                        "seed": 90_007,
                        "status": "ok",
                        "returncode": 0,
                        "error": "",
                        "result_dir": str(root / policy),
                        "run_kind": "physical_replay",
                        "is_derived": 0,
                    }
                    for policy in ("mrp_reference", "adaptive_daily")
                ]
            )
            replay_summary = pd.DataFrame(
                [
                    {
                        "policy": "mrp_reference",
                        "paired_seed_count": 1,
                    }
                ]
            )
            daily_rows = pd.DataFrame(
                [
                    {
                        "policy": policy,
                        "integration_mode": "daily_open_loop_schedule",
                    }
                    for policy in ("mrp_reference", "adaptive_daily")
                ]
            )
            run_replays.return_value = (
                replay_runs,
                replay_summary,
                daily_rows,
            )

            _, _, replay_overlays, run_metadata = _run_canonical_stage(
                mode="run",
                repo_root=root,
                graph_path=graph_path,
                decisions=pd.DataFrame(),
                actions=DEFAULT_ACTIONS[:1],
                output_root=output_root,
                days=7,
                scenario_id="scn:BASE",
                seed=7,
                seed_count=1,
                prediction_path=None,
                physical_risk_envelope=pd.DataFrame(),
                risk_top_pairs=1,
                engine_extra_args=(),
                engine_profile={"enabled": False},
            )
            self.assertEqual(prepare_overlay.call_count, 1)
            run_replays.assert_called_once()
            self.assertEqual(run_metadata["status"], "executed")
            self.assertEqual(
                run_metadata["integration_mode"],
                "daily_open_loop_schedule",
            )
            self.assertFalse(
                replay_overlays["policy"]
                .astype(str)
                .eq("adaptive_weighted_replay")
                .any()
            )
            exported_run = pd.read_csv(
                output_root / "canonical_control_overlays.csv"
            )
            self.assertEqual(
                set(exported_run["integration_mode"]),
                {"daily_open_loop_schedule"},
            )
            self.assertNotIn(
                "adaptive_weighted_replay",
                set(exported_run["policy"]),
            )
            self.assertFalse(
                (output_root / "adaptive_weighted_replay").exists()
            )
            self.assertFalse(
                (
                    output_root
                    / "canonical_supplier_risk_events.csv"
                ).exists()
            )
            self.assertFalse(
                (
                    output_root
                    / "canonical_risk_mapping_ledger.csv"
                ).exists()
            )

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
            self.assertEqual(
                set(events["risk_type"]),
                {
                    "availability",
                    "capacity",
                    "lead_time_extra_days",
                    "quality_yield",
                    "purchase_cost",
                    "transport_cost",
                },
            )
            self.assertTrue((ledger["mapping_status"] == "research_mapping_requires_industrial_calibration").all())
            purchase = ledger.loc[
                ledger["risk_type"].eq("purchase_cost")
            ].iloc[0]
            pair_scale = 0.65 + 0.35 * 0.8
            self.assertAlmostEqual(
                float(purchase["applied_multiplier"]),
                1.0
                + pair_scale
                * (float(purchase["raw_physical_value"]) - 1.0),
            )

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
