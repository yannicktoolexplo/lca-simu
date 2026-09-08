from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.end_2026_reporting import (
    write_end_2026_report,
)
from etudecas.prototypes.scan_2027_risk_control.reporting import (
    prediction_coverage_report_lines,
    write_report,
)
from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_prediction_interval_envelope,
)
from etudecas.prototypes.scan_2027_risk_control.run_scan_continuation import (
    write_handoff_report,
)


def _write_prediction(path: Path, *, include_probability: bool = True) -> None:
    payload: dict[str, list[object]] = {
        "snapshot_date": ["2026-06-01"],
        "supplier_id": ["SUP-A"],
        "factory_id": ["FAC-A"],
        "item_id": ["item:A"],
        "uncertainty_penalty": [0.0],
    }
    if include_probability:
        payload["predicted_incident_probability_30d"] = [0.25]
    pd.DataFrame(payload).to_csv(path, index=False)


def _write_calibration(path: Path, rows: int) -> None:
    pd.DataFrame({
        "predicted_incident_probability_30d": np.full(rows, 0.20),
        "incident_next_30d": np.zeros(rows),
    }).to_csv(path, index=False)


def _nonconformal_metadata() -> dict[str, object]:
    return {
        "interval_method": "assumption_envelope_with_uncertainty_penalty",
        "nominal_coverage": None,
        "requested_nominal_coverage": 0.90,
        "effective_finite_sample_level": None,
        "maximum_attainable_finite_sample_level": 8 / 9,
        "conformal_rank": 9,
        "conformal_calibration_status": (
            "not_estimable_requested_rank_exceeds_calibration_size"
        ),
        "coverage_guarantee_status": "nonconformal_assumption_envelope",
        "coverage_target": "none",
        "coverage_definition": "not_applicable_nonconformal_assumption_envelope",
        "interval_semantics": (
            "nonconformal_assumption_envelope_not_calibrated_probability_interval"
        ),
        "empirical_calibration_coverage": None,
        "calibration_coverage_rows": 8,
        "empirical_calibration_metric": "not_available",
        "coverage_limitations": (
            "Assumption envelope only: no conformal or frequentist coverage claim."
        ),
    }


@pytest.mark.parametrize("rows", range(1, 9))
def test_requested_90_percent_level_is_not_estimable_for_one_to_eight_rows(
    tmp_path: Path,
    rows: int,
) -> None:
    prediction_path = tmp_path / "predicted_supplier_item_risk.csv"
    _write_prediction(prediction_path)
    _write_calibration(tmp_path / "prediction_test_scored_rows.csv", rows)

    envelope, metadata = build_prediction_interval_envelope(
        prediction_path,
        3,
        fallback_uncertainty=np.full(3, 0.07),
        mapping_config={"conformal_alpha": 0.10},
    )

    requested_rank = math.ceil((rows + 1) * 0.90)
    assert requested_rank > rows
    assert metadata.residual_quantile is None
    assert metadata.nominal_coverage is None
    assert metadata.requested_nominal_coverage == pytest.approx(0.90)
    assert metadata.conformal_rank == requested_rank
    assert metadata.effective_finite_sample_level is None
    assert metadata.maximum_attainable_finite_sample_level == pytest.approx(
        rows / (rows + 1)
    )
    assert (
        metadata.conformal_calibration_status
        == "not_estimable_requested_rank_exceeds_calibration_size"
    )
    assert metadata.coverage_guarantee_status == "nonconformal_assumption_envelope"
    assert metadata.coverage_target == "none"
    assert metadata.interval_method.startswith("assumption_envelope")
    assert "nonconformal_assumption_envelope" in metadata.interval_semantics
    assert metadata.effective_interval_half_width == pytest.approx(0.07)
    assert envelope.loc[0, "risk_lower"] == pytest.approx(0.18)
    assert envelope.loc[0, "risk_upper"] == pytest.approx(0.32)


def test_sufficient_calibration_reports_binary_outcome_level_not_latent_p(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "predicted_supplier_item_risk.csv"
    _write_prediction(prediction_path)
    _write_calibration(tmp_path / "prediction_test_scored_rows.csv", 9)

    _, metadata = build_prediction_interval_envelope(
        prediction_path,
        3,
        mapping_config={"conformal_alpha": 0.10},
    )

    assert metadata.residual_quantile == pytest.approx(0.20)
    assert metadata.nominal_coverage == pytest.approx(0.90)
    assert metadata.requested_nominal_coverage == pytest.approx(0.90)
    assert metadata.conformal_rank == 9
    assert metadata.effective_finite_sample_level == pytest.approx(0.90)
    assert metadata.maximum_attainable_finite_sample_level == pytest.approx(0.90)
    assert (
        metadata.conformal_calibration_status
        == "estimable_binary_outcome_predictive_score"
    )
    assert metadata.coverage_target == "future_binary_incident_outcome"
    assert metadata.coverage_definition == (
        "future_binary_outcome_membership_abs_y_minus_p_hat_leq_q"
    )
    assert "not_latent_probability" in metadata.interval_semantics
    assert "latent incident probability" in metadata.coverage_limitations
    assert metadata.empirical_calibration_coverage == pytest.approx(1.0)
    assert metadata.empirical_calibration_metric == (
        "in_sample_calibration_score_inclusion_rate_not_predictive_coverage"
    )


def test_probability_free_fallback_is_explicitly_nonconformal(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "predicted_supplier_item_risk.csv"
    _write_prediction(prediction_path, include_probability=False)
    _write_calibration(tmp_path / "prediction_test_scored_rows.csv", 20)

    _, metadata = build_prediction_interval_envelope(
        prediction_path,
        3,
        fallback_uncertainty=np.full(3, 0.08),
        mapping_config={"conformal_alpha": 0.10},
    )

    assert metadata.interval_method == "assumption_envelope_probability_column_missing"
    assert metadata.fallback_used
    assert metadata.fallback_reason == "probability_column_missing"
    assert metadata.nominal_coverage is None
    assert metadata.coverage_guarantee_status == "nonconformal_assumption_envelope"
    assert metadata.coverage_definition == (
        "not_applicable_nonconformal_assumption_envelope"
    )
    assert metadata.coverage_target == "none"
    assert metadata.effective_interval_half_width == pytest.approx(0.08)
    assert "no conformal" in metadata.coverage_limitations


def test_fractional_targets_do_not_receive_binary_outcome_coverage_claim(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "predicted_supplier_item_risk.csv"
    _write_prediction(prediction_path)
    pd.DataFrame({
        "predicted_incident_probability_30d": np.full(20, 0.20),
        "incident_next_30d": np.full(20, 0.35),
    }).to_csv(tmp_path / "prediction_test_scored_rows.csv", index=False)

    _, metadata = build_prediction_interval_envelope(
        prediction_path,
        3,
        fallback_uncertainty=np.full(3, 0.06),
        mapping_config={"conformal_alpha": 0.10},
    )

    assert metadata.residual_quantile is None
    assert (
        metadata.conformal_calibration_status
        == "not_estimable_no_valid_binary_outcome_rows"
    )
    assert metadata.coverage_guarantee_status == "nonconformal_assumption_envelope"


def test_conformal_report_evidence_names_the_binary_target_and_effective_level() -> None:
    lines = prediction_coverage_report_lines({
        "requested_nominal_coverage": 0.90,
        "effective_finite_sample_level": 19 / 21,
        "maximum_attainable_finite_sample_level": 20 / 21,
        "conformal_rank": 19,
        "conformal_calibration_status": (
            "estimable_binary_outcome_predictive_score"
        ),
        "coverage_guarantee_status": (
            "finite_sample_binary_outcome_score_level_under_exchangeability"
        ),
        "coverage_target": "future_binary_incident_outcome",
        "coverage_definition": (
            "future_binary_outcome_membership_abs_y_minus_p_hat_leq_q"
        ),
        "interval_semantics": (
            "residual_calibrated_binary_outcome_operational_envelope_"
            "not_latent_probability_confidence_interval"
        ),
        "empirical_calibration_coverage": 0.95,
        "calibration_coverage_rows": 20,
        "empirical_calibration_metric": (
            "in_sample_calibration_score_inclusion_rate_not_predictive_coverage"
        ),
        "coverage_limitations": (
            "No coverage of the latent incident probability or mapped physics."
        ),
    })
    rendered = "\n".join(lines)

    assert "target=`future_binary_incident_outcome`" in rendered
    assert "requested level=90.00%" in rendered
    assert "effective finite-sample level=90.48%" in rendered
    assert "In-sample calibration-score inclusion rate: 95.00%" in rendered
    assert "not independent predictive coverage" in rendered
    assert "latent incident probability" in rendered


def test_all_reports_suppress_nominal_coverage_for_nonconformal_fallback(
    tmp_path: Path,
) -> None:
    metadata = _nonconformal_metadata()
    summary = {
        "prediction_to_physics": metadata,
        "canonical_replay": {"status": "not_requested"},
        "rci_business_validation": {"status": "pending_business_review"},
    }

    poc_dir = tmp_path / "poc"
    poc_dir.mkdir()
    write_report(
        poc_dir,
        SimpleNamespace(
            source_mode="synthetic_fallback",
            baseline_path=None,
            risk_path=None,
        ),
        pd.DataFrame({
            "service": [1.0],
            "backlog": [0.0],
            "supplier_risk": [0.1],
            "observability": [0.5],
            "controllability": [0.5],
        }),
        pd.DataFrame(),
        pd.DataFrame({"policy": ["mrp"], "robust_score": [0.0]}),
        pd.DataFrame({"active_constraint_count": [0]}),
        {},
        summary,
    )

    end_dir = tmp_path / "end"
    end_dir.mkdir()
    write_end_2026_report(
        end_dir,
        {"prediction_to_physics": metadata},
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        {"status": "pending_business_review"},
        None,
    )

    continuation_dir = tmp_path / "continuation"
    validation_dir = continuation_dir / "end_2026_validation"
    validation_dir.mkdir(parents=True)
    (validation_dir / "run_manifest.json").write_text(
        json.dumps({"prediction_to_physics": metadata}),
        encoding="utf-8",
    )
    handoff_path = write_handoff_report(
        output_root=continuation_dir,
        validation_dir=validation_dir,
        state_path=continuation_dir / "campaign_state.json",
        args=argparse.Namespace(days=3, canonical_replay="off"),
    )

    reports = [
        (poc_dir / "poc_report.md").read_text(encoding="utf-8"),
        (end_dir / "end_2026_validation_report.md").read_text(encoding="utf-8"),
        handoff_path.read_text(encoding="utf-8"),
    ]
    for report in reports:
        lowered = report.lower()
        assert "nominal coverage" not in lowered
        assert "prediction coverage: nominal" not in lowered
        assert "empirical calibration coverage" not in lowered
        assert "coverage claim: none" in lowered
        assert "not_estimable_requested_rank_exceeds_calibration_size" in report
        assert "maximum attainable finite-sample level=88.89%" in report
