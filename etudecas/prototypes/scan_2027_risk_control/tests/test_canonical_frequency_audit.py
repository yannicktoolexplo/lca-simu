from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_audit import (
    AUDIT_FILES,
    FrequencyAuditError,
    audit_phase_slopes,
    audit_stability,
    classify_stability_sequence,
    run_audit,
)


def test_phase_slope_uses_tested_amplitude_compatibility_without_local_claim() -> None:
    group = {
        "study_kind": "designed_closed_loop_disturbance_probe",
        "policy": "canonical_feedback",
        "input_signal": "lead_multiplier",
        "output_signal": "controller_command",
    }
    delays = pd.DataFrame(
        [
            {
                **group,
                "condition": condition,
                "status": "tested_amplitude_active_set_unverified_phase_slope_not_local_delay",
                "delay_days": np.nan,
                "descriptive_phase_slope_days": 18.0,
                "point_count": 3,
            }
            for condition in ("compatible", "hybrid")
        ]
    )
    response = pd.DataFrame(
        [
            {
                **group,
                "condition": condition,
                "frequency_bin": frequency_bin,
                "valid_bin": True,
                "small_signal_local_claim": False,
                "tested_amplitude_regime_trace_compatible": compatible,
                "active_set_invariance_verified": False,
                "response_regime_scope": (
                    "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified"
                    if compatible
                    else "tested_amplitude_hybrid_regime_switching_active_set_unverified"
                ),
            }
            for condition, compatible in (("compatible", True), ("hybrid", False))
            for frequency_bin in (1, 2, 3)
        ]
    )

    audited = audit_phase_slopes(delays, response).set_index("condition")

    compatible = audited.loc["compatible"]
    assert compatible["phase_slope_classification"] == (
        "tested_amplitude_regime_compatible_active_set_unverified"
    )
    assert compatible["phase_slope_equivalent_days"] == pytest.approx(18.0)
    assert compatible["phase_slope_value_source_field"] == "descriptive_phase_slope_days"
    assert compatible["regime_compatibility_evidence_source"] == (
        "tested_amplitude_regime_trace_compatible"
    )
    assert not bool(compatible["legacy_regime_compatibility_fallback"])
    assert compatible["tested_amplitude_regime_compatible_line_count"] == 3
    assert compatible["active_set_invariance_verified_line_count"] == 0
    assert not bool(compatible["local_delay_claimed"])
    assert not bool(compatible["transport_delay_claimed"])

    hybrid = audited.loc["hybrid"]
    assert hybrid["phase_slope_classification"] == "hybrid_regime_transition_phase_slope"
    assert hybrid["tested_amplitude_regime_incompatible_line_count"] == 3
    assert not bool(hybrid["local_delay_claimed"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(root: Path) -> None:
    group_base = {
        "study_kind": "designed_closed_loop_disturbance_probe",
        "condition": "stress",
        "policy": "canonical_feedback",
        "input_signal": "lead_multiplier",
    }
    stability_rows = []
    for output, values in (
        ("zero", [0.0, 0.0, 0.0]),
        ("repeatable", [1.0, 1.05, 1.0]),
        ("interior", [1.0, 2.0, 1.0]),
        ("growth", [1.0, 1.2, 1.4]),
        ("other", [2.0, 1.0, 1.5]),
    ):
        stability_rows.append(
            {
                **group_base,
                "output_signal": output,
                "status": "source_status",
                "period_rms_json": json.dumps(values),
                "growth_tolerance": 1.10,
            }
        )
    pd.DataFrame(stability_rows).to_csv(
        root / "canonical_frequency_stability.csv", index=False
    )

    response_rows = []
    for frequency_bin in (1, 2, 3):
        response_rows.append(
            {
                **group_base,
                "output_signal": "controller_command",
                "frequency_bin": frequency_bin,
                "valid_bin": True,
                "small_signal_local_claim": False,
                "response_regime_scope": "hybrid_regime_switching_amplitude_conditioned",
                "settling_periods_discarded": 1,
            }
        )
    for policy in ("mrp_reference", "canonical_feedback"):
        response_rows.append(
            {
                "study_kind": "designed_closed_loop_disturbance_probe",
                "condition": "stress",
                "policy": policy,
                "input_signal": "lead_multiplier",
                "output_signal": "arrivals",
                "frequency_bin": 1,
                "valid_bin": True,
                "small_signal_local_claim": True,
                "response_regime_scope": "local_fixed_supervisory_regime_trace",
                "settling_periods_discarded": 1,
            }
        )
    pd.DataFrame(response_rows).to_csv(
        root / "canonical_frequency_response.csv", index=False
    )

    pd.DataFrame(
        [
            {
                **group_base,
                "output_signal": "controller_command",
                "status": "local_phase_slope_estimated_not_transport_delay_proof",
                "delay_days": 18.0,
                "point_count": 3,
                "weighted_r_squared": 0.9,
            }
        ]
    ).to_csv(root / "canonical_frequency_delays.csv", index=False)

    pd.DataFrame(
        [
            {
                "condition": "stress",
                "input_signal": "lead_multiplier",
                "output_signal": "arrivals",
                "frequency_bin": 1,
                "v2_minus_mrp_attenuation_db": -0.3,
                "reliable_comparison": True,
            }
        ]
    ).to_csv(root / "canonical_frequency_closed_loop_comparison.csv", index=False)

    trajectory_rows = []
    period_days = 8
    for policy in ("mrp_reference", "canonical_feedback"):
        for period_index in range(4):
            if policy == "mrp_reference":
                gain = 2.0
            else:
                gain = 1.8 if period_index == 2 else 2.0
            for day_in_period in range(period_days):
                signal = math.sin(2.0 * math.pi * day_in_period / period_days)
                trajectory_rows.append(
                    {
                        "condition": "stress",
                        "policy": policy,
                        "experiment_input_signal": "lead_multiplier",
                        "day": period_index * period_days + day_in_period,
                        "period_index": period_index,
                        "excitation_fraction__lead_multiplier": signal,
                        "delta__arrivals": gain * signal,
                    }
                )
    pd.DataFrame(trajectory_rows).to_csv(
        root / "canonical_frequency_trajectories.csv", index=False
    )

    pd.DataFrame(
        [
            {
                "source_run": "native",
                "input_signal": "demand",
                "output_signal": "orders",
                "period_days": period,
                "coherence": coherence,
            }
            for period, coherence in ((2.5, 0.1), (3.0, 0.3), (4.0, 0.5))
        ]
    ).to_csv(root / "canonical_frequency_native_spectra.csv", index=False)
    pd.DataFrame(
        [
            {
                "source_run": "native",
                "input_signal": "demand",
                "output_signal": "orders",
                "band": "rapid",
                "period_min_days": 2.0,
                "period_max_days": 6.0,
                "power_amplification_db": 12.0,
            }
        ]
    ).to_csv(root / "canonical_frequency_native_bands.csv", index=False)

    pd.DataFrame(
        [
            {
                "condition": "stress",
                "experiment_input_signal": "lead_multiplier",
                "day": 0,
            }
        ]
    ).to_csv(root / "canonical_frequency_excitation_audit.csv", index=False)
    pd.DataFrame(
        [
            {
                "condition": "stress",
                "policy": "canonical_feedback",
                "input_signal": "lead_multiplier",
                "output_signal": "arrivals",
                "designed_output_power": 1.0,
            }
        ]
    ).to_csv(root / "canonical_frequency_nonlinearity.csv", index=False)


def test_stability_classifier_has_explicit_nonresponse_and_transient_classes() -> None:
    assert classify_stability_sequence([0.0, 0.0, 0.0])[0] == "no_measurable_response"
    assert classify_stability_sequence([1.0, 1.05, 1.0])[0] == "nonzero_repeatable"
    assert classify_stability_sequence([1.0, 2.0, 1.0])[0] == "interior_peak"
    assert classify_stability_sequence([1.0, 1.2, 1.4])[0] == "monotonic_growth"
    assert classify_stability_sequence([2.0, 1.0, 1.5])[0] == "other"


def test_stability_recalculation_includes_dc_drift_and_terminal_states() -> None:
    stability = pd.DataFrame(
        [
            {
                "study_kind": "designed_closed_loop_disturbance_probe",
                "condition": "stress",
                "policy": "mrp_reference",
                "input_signal": "demand_multiplier",
                "output_signal": "stock",
                "status": "bounded_repeatable_response_observed",
                "period_count": 3,
                # A centred RMS loses this period-constant state entirely.
                "period_rms_json": "[0.0, 0.0, 0.0]",
                "growth_tolerance": 1.10,
            }
        ]
    )
    rows = []
    for period_index, level in enumerate((0.0, 10.0, 10.5, 10.0)):
        for day_in_period in range(4):
            rows.append(
                {
                    "condition": "stress",
                    "policy": "mrp_reference",
                    "experiment_input_signal": "demand_multiplier",
                    "period_index": period_index,
                    "day": period_index * 4 + day_in_period,
                    "delta__stock": level,
                }
            )
    trajectories = pd.DataFrame(rows)
    response = pd.DataFrame(
        [
            {
                "study_kind": "designed_closed_loop_disturbance_probe",
                "condition": "stress",
                "policy": "mrp_reference",
                "input_signal": "demand_multiplier",
                "output_signal": "stock",
                "settling_periods_discarded": 1,
            }
        ]
    )

    audited = audit_stability(
        stability, trajectories=trajectories, response=response
    ).iloc[0]

    assert audited["audit_classification"] == "nonzero_repeatable"
    assert bool(audited["trajectory_recalculated"])
    assert bool(audited["classification_rms_includes_dc"])
    assert json.loads(audited["period_total_rms_json"]) == pytest.approx(
        [10.0, 10.5, 10.0]
    )
    assert json.loads(audited["period_ac_rms_json"]) == pytest.approx(
        [0.0, 0.0, 0.0]
    )
    assert json.loads(audited["period_mean_json"]) == pytest.approx(
        [10.0, 10.5, 10.0]
    )
    assert json.loads(audited["terminal_state_by_period_json"]) == pytest.approx(
        [10.0, 10.5, 10.0]
    )
    assert audited["legacy_source_period_rms_json"] == "[0.0, 0.0, 0.0]"


def test_stability_recalculation_has_explicit_legacy_fallback() -> None:
    stability = pd.DataFrame(
        [
            {
                "study_kind": "designed_closed_loop_disturbance_probe",
                "condition": "missing",
                "policy": "mrp_reference",
                "input_signal": "demand_multiplier",
                "output_signal": "stock",
                "status": "bounded_repeatable_response_observed",
                "period_rms_json": "[0.0, 0.0, 0.0]",
                "growth_tolerance": 1.10,
            }
        ]
    )

    audited = audit_stability(
        stability,
        trajectories=pd.DataFrame(
            columns=[
                "condition",
                "policy",
                "experiment_input_signal",
                "period_index",
                "day",
                "delta__stock",
            ]
        ),
    ).iloc[0]

    assert audited["audit_classification"] == "no_measurable_response"
    assert not bool(audited["trajectory_recalculated"])
    assert audited["classification_metric_source"] == (
        "legacy_period_rms_json_fallback"
    )
    assert audited["trajectory_fallback_reason"] == (
        "trajectory_table_missing_or_empty"
    )
    assert pd.isna(audited["classification_rms_includes_dc"])


def test_posthoc_audit_is_strict_separate_and_reclassifies_hybrid_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "audit"
    source.mkdir()
    _write_fixture(source)
    before = {path.name: _sha256(path) for path in source.iterdir() if path.is_file()}

    result = run_audit(source, output)

    after = {path.name: _sha256(path) for path in source.iterdir() if path.is_file()}
    assert after == before
    assert set(path.name for path in output.iterdir()) == set(AUDIT_FILES.values())
    payload_text = result["paths"]["json"].read_text(encoding="utf-8")
    assert "NaN" not in payload_text
    payload = json.loads(payload_text)
    assert payload["claims"]["source_package_modified"] is False
    assert payload["evidence_counts"]["stability_classifications"] == {
        "interior_peak": 1,
        "monotonic_growth": 1,
        "nonzero_repeatable": 1,
        "no_measurable_response": 1,
        "other": 1,
    }
    phase = pd.read_csv(result["paths"]["phase_slopes"])
    assert phase.loc[0, "phase_slope_classification"] == "hybrid_regime_transition_phase_slope"
    assert bool(phase.loc[0, "legacy_regime_compatibility_fallback"])
    assert phase.loc[0, "regime_compatibility_evidence_source"] == (
        "legacy_small_signal_local_claim_and_response_regime_scope"
    )
    assert not bool(phase.loc[0, "local_delay_claimed"])

    periods = pd.read_csv(result["paths"]["paired_periods"])
    assert len(periods) == 3
    assert periods["v2_minus_mrp_attenuation_db"].iloc[[0, 2]].to_numpy() == pytest.approx(
        [0.0, 0.0], abs=1e-12
    )
    assert periods["v2_minus_mrp_attenuation_db"].iloc[1] < 0.0
    comparisons = pd.read_csv(result["paths"]["comparisons"])
    assert bool(comparisons.loc[0, "paired_interval_available"])
    assert comparisons.loc[0, "paired_attenuation_db_q975"] == pytest.approx(0.0, abs=1e-12)
    assert bool(comparisons.loc[0, "zero_db_in_paired_interval"])

    coherence = pd.read_csv(result["paths"]["native_band_coherence"])
    assert coherence.loc[0, "median_coherence"] == pytest.approx(0.3)
    assert coherence.loc[0, "coherence_threshold_pass_count"] == 0
    assert "hybrides" in result["paths"]["markdown"].read_text(encoding="utf-8")


def test_audit_refuses_to_write_inside_source_package(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_fixture(source)
    with pytest.raises(FrequencyAuditError, match="outside"):
        run_audit(source, source / "audit")
