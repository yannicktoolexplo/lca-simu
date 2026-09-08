from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.end_2026_reporting import (
    _executable_threshold_plot_frame,
    write_end_2026_report,
)
from etudecas.prototypes.scan_2027_risk_control.reporting import write_report
from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_granular_prediction_interval_envelope,
    build_prediction_interval_envelope,
)
from etudecas.prototypes.scan_2027_risk_control.run_end_2026_validation import (
    _build_run_provenance,
)


def _prediction_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "snapshot_date": ["2025-12-22", "2025-12-22"],
        "week_index": [104, 104],
        "supplier_id": ["SUP-A", "SUP-B"],
        "factory_id": ["FAC-A", "FAC-B"],
        "item_id": ["item:A", "item:B"],
        "predicted_incident_probability_30d": [0.25, 0.35],
        "uncertainty_penalty": [0.0, 0.0],
        "predicted_priority_score": [1.0, 0.9],
    })


def _calibration_rows() -> pd.DataFrame:
    operational_overlap = pd.DataFrame({
        "snapshot_date": ["2025-12-22", "2025-12-22"],
        "week_index": [104, 104],
        "supplier_id": ["SUP-A", "SUP-B"],
        "factory_id": ["FAC-A", "FAC-B"],
        "item_id": ["item:A", "item:B"],
        "predicted_incident_probability_30d": [0.0, 0.0],
        "incident_next_30d": [1, 1],
    })
    independent = pd.DataFrame({
        "snapshot_date": ["2025-09-15"] * 10,
        "week_index": [90] * 10,
        "supplier_id": [f"SUP-{index}" for index in range(10)],
        "factory_id": [f"FAC-{index}" for index in range(10)],
        "item_id": [f"item:{index}" for index in range(10)],
        "predicted_incident_probability_30d": [0.1] * 10,
        "incident_next_30d": [0] * 10,
    })
    return pd.concat([operational_overlap, independent], ignore_index=True)


def test_exact_operational_snapshot_rows_are_excluded_from_conformal_scores(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "predicted_supplier_item_risk.csv"
    _prediction_rows().to_csv(prediction_path, index=False)
    _calibration_rows().to_csv(
        tmp_path / "prediction_test_scored_rows.csv", index=False
    )

    _, metadata = build_prediction_interval_envelope(
        prediction_path,
        3,
        mapping_config={"conformal_alpha": 0.10},
    )
    granular = build_granular_prediction_interval_envelope(
        prediction_path,
        1,
        mapping_config={"conformal_alpha": 0.10},
    )

    assert metadata.calibration_rows_before == 12
    assert metadata.calibration_rows_after == 10
    assert metadata.excluded_overlap_rows == 2
    assert metadata.rows_used == 10
    assert set(metadata.overlap_key_columns) == {
        "snapshot_date",
        "week_index",
        "supplier_id",
        "item_id",
        "dst_node_id",
    }
    assert metadata.residual_quantile == pytest.approx(0.1)
    assert metadata.operational_target_rows == 2
    assert metadata.operational_probability_unique_count == 2
    assert metadata.operational_snapshot_date.startswith("2025-12-22")
    assert metadata.operational_week_index == 104.0
    assert sorted(granular["risk_lower"].tolist()) == pytest.approx([0.15, 0.25])


def test_overlap_exclusion_requires_complete_temporal_lane_identity(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "predicted_supplier_item_risk.csv"
    _prediction_rows().to_csv(prediction_path, index=False)
    calibration = _calibration_rows().drop(columns=["factory_id"])
    calibration.to_csv(tmp_path / "prediction_test_scored_rows.csv", index=False)

    _, metadata = build_prediction_interval_envelope(
        prediction_path,
        2,
        mapping_config={"conformal_alpha": 0.10},
    )

    assert metadata.calibration_rows_before == 12
    assert metadata.calibration_rows_after == 12
    assert metadata.excluded_overlap_rows == 0
    assert metadata.overlap_key_columns == ()


def test_run_provenance_detects_synthetic_prediction_lineage_and_hashes(
    tmp_path: Path,
) -> None:
    package = (
        tmp_path / "etudecas" / "prototypes" / "scan_2027_risk_control"
    )
    package.mkdir(parents=True)
    (package / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    engine = tmp_path / "etudecas" / "simulation" / "engine"
    engine.mkdir(parents=True)
    engine_source = engine / "run_first_simulation.py"
    engine_source.write_text("ENGINE_VALUE = 1\n", encoding="utf-8")
    (tmp_path / "etudecas" / "run_etudecas_pipeline.py").write_text(
        "PIPELINE_VALUE = 1\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.csv"
    prediction = tmp_path / "predicted_supplier_item_risk.csv"
    calibration = tmp_path / "prediction_test_scored_rows.csv"
    baseline.write_bytes(b"day,demand\n0,1\n")
    prediction.write_bytes(b"probability\n0.2\n")
    calibration.write_bytes(b"probability,label\n0.2,0\n")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"data_history": "data/synthetic_supplier_history.csv"}),
        encoding="utf-8",
    )
    (tmp_path / "prediction_poc_report.md").write_text(
        "Les labels et une partie des variables temporelles sont synthetiques.\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(
        source_mode="etudecas_baseline",
        baseline_path=str(baseline),
        risk_path=str(prediction),
    )

    provenance = _build_run_provenance(
        tmp_path,
        context,
        {"calibration_path": str(calibration)},
    )

    assert provenance["baseline_origin"] == "etudecas_case_simulation_output"
    assert provenance["baseline"]["industrial_status"] == "non_industrial"
    assert provenance["baseline"]["source_sha256"] == hashlib.sha256(
        baseline.read_bytes()
    ).hexdigest()
    forecast = provenance["forecast"]
    assert forecast["origin"] == "synthetic_prediction_poc"
    assert forecast["history_origin"] == "synthetic"
    assert forecast["label_origin"] == "synthetic"
    assert forecast["temporal_feature_origin"] == "partly_synthetic"
    assert forecast["evaluation_status"] == (
        "retrospective_synthetic_non_deployment"
    )
    assert forecast["source_sha256"] == hashlib.sha256(
        prediction.read_bytes()
    ).hexdigest()
    assert forecast["calibration_sha256"] == hashlib.sha256(
        calibration.read_bytes()
    ).hexdigest()
    assert provenance["code_snapshot"]["sha256"]
    assert provenance["code_snapshot"]["file_count"] == 3
    assert provenance["code_snapshot"]["scope"] == (
        "scan_package_canonical_engine_and_execution_adapters"
    )
    initial_snapshot = provenance["code_snapshot"]["sha256"]
    engine_source.write_text("ENGINE_VALUE = 2\n", encoding="utf-8")
    changed = _build_run_provenance(
        tmp_path,
        context,
        {"calibration_path": str(calibration)},
    )
    assert changed["code_snapshot"]["sha256"] != initial_snapshot


def test_run_provenance_labels_generated_synthetic_risk_fallback(
    tmp_path: Path,
) -> None:
    context = SimpleNamespace(
        source_mode="synthetic_fallback",
        baseline_path=None,
        risk_path=None,
    )

    provenance = _build_run_provenance(
        tmp_path,
        context,
        {
            "fallback_used": True,
            "fallback_reason": "prediction_file_not_found",
        },
    )

    assert provenance["baseline_origin"] == "synthetic_fallback"
    assert provenance["baseline"]["industrial_status"] == "non_industrial"
    forecast = provenance["forecast"]
    assert forecast["origin"] == "synthetic_risk_series_fallback"
    assert forecast["industrial_status"] == "non_industrial"
    assert forecast["history_origin"] == "synthetic_generator"
    assert forecast["label_origin"] == "not_applicable_no_prediction_labels"
    assert forecast["temporal_feature_origin"] == "synthetic_generator"
    assert forecast["evaluation_status"] == (
        "synthetic_experiment_non_deployment"
    )
    assert forecast["detection"]["synthetic_fallback_context"] is True


def _report_manifest() -> dict[str, object]:
    return {
        "provenance": {
            "baseline": {
                "origin": "etudecas_case_simulation_output",
                "industrial_status": "non_industrial",
                "source_sha256": "baseline-hash",
            },
            "forecast": {
                "origin": "synthetic_prediction_poc",
                "industrial_status": "non_industrial",
                "history_origin": "synthetic",
                "label_origin": "synthetic",
                "temporal_feature_origin": "partly_synthetic",
                "evaluation_status": "retrospective_synthetic_non_deployment",
                "source_sha256": "risk-hash",
                "calibration_sha256": "calibration-hash",
            },
            "code_snapshot": {
                "sha256": "code-hash",
                "file_count": 3,
                "git": {
                    "head": "git-head",
                    "branch": "work",
                    "dirty": True,
                },
            },
        },
        "prediction_to_physics": {
            "coverage_guarantee_status": "nonconformal_assumption_envelope",
            "conformal_calibration_status": "not_estimable",
            "coverage_target": "none",
            "interval_semantics": "not_latent_probability_confidence_interval",
            "coverage_limitations": "No latent incident probability claim.",
            "coverage_definition": "not_applicable",
            "calibration_rows_before": 12,
            "calibration_rows_after": 10,
            "excluded_overlap_rows": 2,
            "operational_target_rows": 2,
            "operational_probability_unique_count": 1,
            "operational_snapshot_date": "2025-12-22T00:00:00",
            "operational_week_index": 104,
            "overlap_key_columns": ["snapshot_date", "supplier_id", "item_id", "dst_node_id"],
            "overlap_status": "detected_and_excluded_from_calibration",
            "calibration_use_status": "retrospective_synthetic_non_deployment",
            "forecast_origin": "synthetic_prediction_poc",
        },
        "regime_calibration": {
            "regime_annotations": {"business_label_days": 0},
            "source_mode": "etudecas_baseline",
        },
        "canonical_replay": {"status": "not_requested"},
        "rci_business_validation": {"status": "pending_business_review"},
    }


def _regime_evidence() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "regime": "NOMINAL",
            "classification_rule": "ordered fallthrough",
            "initial_thresholds": "{}",
            "calibrated_thresholds": "{}",
            "anchor_days": 30,
            "confidence": "high",
            "limitations": "legacy supplier_stress is diagnostic only",
        },
        {
            "regime": "SUPPLIER_STRESS",
            "classification_rule": "supplier_risk or supplier_stress",
            "initial_thresholds": '{"supplier_risk":0.4,"supplier_stress":0.7}',
            "calibrated_thresholds": '{"supplier_risk":0.5,"supplier_stress":0.8}',
            "anchor_days": 8,
            "confidence": "medium",
            "limitations": "pseudo-label evidence",
        },
    ])


def test_reports_disclose_hybrid_provenance_overlap_and_regime_rule_confidence(
    tmp_path: Path,
) -> None:
    manifest = _report_manifest()
    evidence = _regime_evidence()
    plot_frame = _executable_threshold_plot_frame(evidence)
    assert set(plot_frame["threshold"]) == {"supplier_risk", "supplier_stress"}
    assert "NOMINAL" not in set(plot_frame["regime"])

    write_report(
        tmp_path,
        SimpleNamespace(
            source_mode="etudecas_baseline",
            baseline_path="baseline.csv",
            risk_path="risk.csv",
        ),
        pd.DataFrame({
            "service": [1.0],
            "backlog": [0.0],
            "supplier_risk": [0.1],
            "observability": [0.5],
            "controllability": [0.5],
        }),
        pd.DataFrame(),
        pd.DataFrame({"policy": ["mrp_reference"], "robust_score": [0.0]}),
        pd.DataFrame({"active_constraint_count": [0]}),
        {},
        manifest,
    )
    confusion = pd.DataFrame({
        "case": ["TP"],
        "predicted_event": [1],
        "truth_event": [1],
        "mean_service_loss": [0.0],
        "mean_nervousness_area": [0.0],
        "mean_risk_creation_area": [0.0],
    })
    write_end_2026_report(
        tmp_path,
        manifest,
        evidence,
        pd.DataFrame(),
        confusion,
        {"status": "pending_business_review"},
        None,
    )

    poc_report = (tmp_path / "poc_report.md").read_text(encoding="utf-8")
    end_report = (tmp_path / "end_2026_validation_report.md").read_text(
        encoding="utf-8"
    )
    for report in (poc_report, end_report):
        assert "origin=`etudecas_case_simulation_output`" in report
        assert "origin=`synthetic_prediction_poc`" in report
        assert "retrospective_synthetic_non_deployment" in report
        assert "excluded overlap rows=2" in report
        assert "unique probability count=1" in report
        assert "not a latent-probability claim" in report
    assert "High / medium / low confidence regime rules: 1 / 1 / 0" in end_report
    assert "NOMINAL is an ordered fallthrough rule with confidence `high`" in end_report
    assert "SUPPLIER_STRESS is a distinct rule with confidence `medium`" in end_report
    assert "| Case | Predicted event | Simulated physical truth |" in end_report
    assert "Real event" not in end_report
    assert "missing a real event" not in end_report
