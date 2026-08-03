from __future__ import annotations

import math

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.experiments import (
    _attach_reduced_mrp_reference_deltas,
    _paired_cohens_dz,
    _paired_reduced_summary,
    _reduced_recovery_contract,
)


def test_reduced_recovery_contract_distinguishes_observed_and_censored() -> None:
    observed = _reduced_recovery_contract(
        pd.DataFrame(
            {
                "backlog": [5.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "service": [0.80, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            }
        )
    )
    assert observed == {
        "recovery_time_days": 2.0,
        "recovery_time_lower_bound_days": 2.0,
        "recovery_followup_days": 8.0,
        "recovery_observed": 1.0,
        "recovery_status": "observed",
        "recovery_episode_detected": 1.0,
        "recovery_episode_basis": "backlog_peak",
    }

    censored = _reduced_recovery_contract(
        pd.DataFrame(
            {
                "backlog": [5.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "service": [0.80, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            }
        )
    )
    assert math.isnan(censored["recovery_time_days"])
    assert censored["recovery_time_lower_bound_days"] == 7.0
    assert censored["recovery_followup_days"] == 7.0
    assert censored["recovery_observed"] == 0.0
    assert censored["recovery_status"] == "right_censored"
    assert censored["recovery_episode_detected"] == 1.0
    assert censored["recovery_episode_basis"] == "backlog_peak"


def test_reduced_recovery_is_not_applicable_without_a_disruption() -> None:
    no_disruption = _reduced_recovery_contract(
        pd.DataFrame(
            {
                "backlog": [0.0] * 9,
                "service": [1.0] * 9,
            }
        )
    )
    for field in (
        "recovery_time_days",
        "recovery_time_lower_bound_days",
        "recovery_followup_days",
        "recovery_observed",
    ):
        assert math.isnan(no_disruption[field])
    assert no_disruption["recovery_status"] == "not_applicable_no_disruption"
    assert no_disruption["recovery_episode_detected"] == 0.0
    assert (
        no_disruption["recovery_episode_basis"]
        == "no_backlog_or_service_disruption"
    )

    service_only = _reduced_recovery_contract(
        pd.DataFrame(
            {
                "backlog": [0.0] * 10,
                "service": [1.0, 0.80, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            }
        )
    )
    assert service_only["recovery_time_days"] == 1.0
    assert service_only["recovery_time_lower_bound_days"] == 1.0
    assert service_only["recovery_followup_days"] == 8.0
    assert service_only["recovery_observed"] == 1.0
    assert service_only["recovery_status"] == "observed"
    assert service_only["recovery_episode_detected"] == 1.0
    assert service_only["recovery_episode_basis"] == "service_minimum"


def test_single_reduced_pair_has_no_fabricated_ci_and_exact_mrp_identity() -> None:
    runs = _attach_reduced_mrp_reference_deltas(
        pd.DataFrame(
            [
                {
                    "seed": 1,
                    "policy": "mrp_reference",
                    "score": 10.0,
                    "recovery_time_days": 5.0,
                    "recovery_time_lower_bound_days": 5.0,
                    "recovery_followup_days": 9.0,
                    "recovery_observed": 1.0,
                    "recovery_status": "observed",
                },
                {
                    "seed": 1,
                    "policy": "balanced_robust",
                    "score": 8.0,
                    "recovery_time_days": 3.0,
                    "recovery_time_lower_bound_days": 3.0,
                    "recovery_followup_days": 9.0,
                    "recovery_observed": 1.0,
                    "recovery_status": "observed",
                },
            ]
        )
    )
    summary = _paired_reduced_summary(runs).set_index("policy")

    reference = summary.loc["mrp_reference"]
    assert runs.loc[runs["policy"].eq("mrp_reference"), "delta_vs_mrp_score"].item() == 0.0
    assert reference["ci95_low_delta_score"] == 0.0
    assert reference["ci95_high_delta_score"] == 0.0
    assert reference["ci95_status_delta_score"] == "exact_reference_zero"

    controlled = summary.loc["balanced_robust"]
    assert controlled["mean_delta_score"] == -2.0
    assert math.isnan(controlled["ci95_low_delta_score"])
    assert math.isnan(controlled["ci95_high_delta_score"])
    assert controlled["ci95_status_delta_score"] == "not_estimable_single_pair"
    assert controlled["mean_delta_recovery_time_days"] == -2.0
    assert controlled["ci95_status_delta_recovery_time_days"] == "not_estimable_single_pair"
    zero_effect, zero_effect_status = _paired_cohens_dz(pd.Series([0.0]))
    assert math.isnan(zero_effect)
    assert zero_effect_status == "not_estimable_single_pair"


def test_recovery_delta_excludes_censored_and_non_comparable_pairs() -> None:
    rows = [
        # Policy recovery censored; reference recovery observed.
        {
            "seed": 1,
            "policy": "mrp_reference",
            "score": 10.0,
            "recovery_time_days": 5.0,
            "recovery_time_lower_bound_days": 5.0,
            "recovery_followup_days": 9.0,
            "recovery_observed": 1.0,
            "recovery_status": "observed",
        },
        {
            "seed": 1,
            "policy": "balanced_robust",
            "score": 9.0,
            "recovery_time_days": math.nan,
            "recovery_time_lower_bound_days": 9.0,
            "recovery_followup_days": 9.0,
            "recovery_observed": 0.0,
            "recovery_status": "right_censored",
        },
        # Reference recovery censored; policy recovery observed.
        {
            "seed": 2,
            "policy": "mrp_reference",
            "score": 11.0,
            "recovery_time_days": math.nan,
            "recovery_time_lower_bound_days": 9.0,
            "recovery_followup_days": 9.0,
            "recovery_observed": 0.0,
            "recovery_status": "right_censored",
        },
        {
            "seed": 2,
            "policy": "balanced_robust",
            "score": 10.0,
            "recovery_time_days": 3.0,
            "recovery_time_lower_bound_days": 3.0,
            "recovery_followup_days": 9.0,
            "recovery_observed": 1.0,
            "recovery_status": "observed",
        },
        # Only this seed is an observed, comparable duration pair.
        {
            "seed": 3,
            "policy": "mrp_reference",
            "score": 12.0,
            "recovery_time_days": 4.0,
            "recovery_time_lower_bound_days": 4.0,
            "recovery_followup_days": 9.0,
            "recovery_observed": 1.0,
            "recovery_status": "observed",
        },
        {
            "seed": 3,
            "policy": "balanced_robust",
            "score": 11.0,
            "recovery_time_days": 2.0,
            "recovery_time_lower_bound_days": 2.0,
            "recovery_followup_days": 9.0,
            "recovery_observed": 1.0,
            "recovery_status": "observed",
        },
    ]
    runs = _attach_reduced_mrp_reference_deltas(pd.DataFrame(rows))

    controlled = runs.loc[runs["policy"].eq("balanced_robust")].set_index("seed")
    assert math.isnan(controlled.loc[1, "delta_vs_mrp_recovery_time_days"])
    assert math.isnan(controlled.loc[2, "delta_vs_mrp_recovery_time_days"])
    assert math.isnan(controlled.loc[1, "delta_vs_mrp_recovery_followup_days"])
    assert math.isnan(controlled.loc[2, "delta_vs_mrp_recovery_observed"])
    assert controlled.loc[3, "delta_vs_mrp_recovery_time_days"] == -2.0
    assert controlled.loc[3, "delta_vs_mrp_recovery_followup_days"] == 0.0
    assert controlled.loc[3, "delta_vs_mrp_recovery_observed"] == 0.0
    assert controlled.loc[1, "delta_vs_mrp_recovery_time_status"] == "not_comparable_censored"
    assert controlled.loc[2, "delta_vs_mrp_recovery_time_status"] == "not_comparable_censored"
    assert controlled.loc[3, "delta_vs_mrp_recovery_time_status"] == "observed_pair"

    censored_reference = runs.loc[
        runs["policy"].eq("mrp_reference") & runs["seed"].eq(2)
    ].iloc[0]
    assert censored_reference["delta_vs_mrp_recovery_time_days"] == 0.0
    assert censored_reference["delta_vs_mrp_recovery_time_status"] == "reference_self_exact_zero"

    summary = _paired_reduced_summary(runs).set_index("policy")
    controlled_summary = summary.loc["balanced_robust"]
    assert controlled_summary["paired_seed_count"] == 3
    assert controlled_summary["paired_observed_count_recovery_time_days"] == 1
    assert controlled_summary["mean_delta_recovery_time_days"] == -2.0
    assert math.isnan(controlled_summary["ci95_low_delta_recovery_time_days"])
    assert controlled_summary["ci95_status_delta_recovery_time_days"] == "not_estimable_single_pair"
    assert (
        controlled_summary["pairing_status_delta_recovery_time_days"]
        == "partial_observed_pairs_excludes_censored"
    )


def test_no_disruption_recovery_delta_is_non_applicable_except_mrp_identity() -> None:
    runs = _attach_reduced_mrp_reference_deltas(
        pd.DataFrame(
            [
                {
                    "seed": 1,
                    "policy": "mrp_reference",
                    "score": 10.0,
                    "recovery_time_days": math.nan,
                    "recovery_time_lower_bound_days": math.nan,
                    "recovery_followup_days": math.nan,
                    "recovery_observed": math.nan,
                    "recovery_status": "not_applicable_no_disruption",
                },
                {
                    "seed": 1,
                    "policy": "balanced_robust",
                    "score": 9.0,
                    "recovery_time_days": math.nan,
                    "recovery_time_lower_bound_days": math.nan,
                    "recovery_followup_days": math.nan,
                    "recovery_observed": math.nan,
                    "recovery_status": "not_applicable_no_disruption",
                },
            ]
        )
    )
    reference = runs.loc[runs["policy"].eq("mrp_reference")].iloc[0]
    controlled = runs.loc[runs["policy"].eq("balanced_robust")].iloc[0]
    assert reference["delta_vs_mrp_recovery_time_days"] == 0.0
    assert (
        reference["delta_vs_mrp_recovery_time_status"]
        == "reference_self_exact_zero"
    )
    assert math.isnan(controlled["delta_vs_mrp_recovery_time_days"])
    assert math.isnan(controlled["delta_vs_mrp_recovery_followup_days"])
    assert math.isnan(controlled["delta_vs_mrp_recovery_observed"])
    assert (
        controlled["delta_vs_mrp_recovery_time_status"]
        == "not_comparable_no_disruption"
    )

    summary = _paired_reduced_summary(runs).set_index("policy")
    controlled_summary = summary.loc["balanced_robust"]
    assert controlled_summary["paired_observed_count_recovery_time_days"] == 0
    assert math.isnan(controlled_summary["mean_delta_recovery_time_days"])
    assert (
        controlled_summary["ci95_status_delta_recovery_time_days"]
        == "not_estimable_no_observed_pairs"
    )
    assert (
        controlled_summary["pairing_status_delta_recovery_time_days"]
        == "not_applicable_no_disruption_pairs"
    )
