from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import frequency_reporting
from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_revision import (
    FIGURE_FILES,
    _normalized_reporting_config,
    _read_source,
    recalculate_stability,
    requalify_response,
    revise_delays,
    run_revision,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_designed_only_package_may_omit_native_spectral_tables(
    tmp_path: Path,
) -> None:
    source = tmp_path / "designed_only"
    _write_package(source)
    (source / "canonical_frequency_native_spectra.csv").unlink()
    (source / "canonical_frequency_native_bands.csv").unlink()

    paths, frames = _read_source(source)

    assert "native_spectra" not in paths
    assert "native_bands" not in paths
    assert frames["native_spectra"].empty
    assert frames["native_bands"].empty


def _group(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "study_kind": "designed_closed_loop_disturbance_probe",
        "condition": "stress",
        "policy": "canonical_feedback",
        "input_signal": "lead_multiplier",
        "output_signal": "controller_command",
    }
    values.update(overrides)
    return values


def test_response_and_delay_are_requalified_without_changing_estimates() -> None:
    response = pd.DataFrame(
        [
            {
                **_group(),
                "frequency_bin": frequency_bin,
                "period_days": 32.0 / frequency_bin,
                "magnitude": 2.5 + frequency_bin,
                "phase_deg": -10.0 * frequency_bin,
                "coherence": 0.95,
                "valid_bin": True,
                "small_signal_local_claim": True,
                "regime_compatible_for_local_claim": False,
                "response_regime_scope": (
                    "hybrid_regime_switching_amplitude_conditioned"
                ),
            }
            for frequency_bin in (1, 2, 3)
        ]
    )
    delays = pd.DataFrame(
        [
            {
                **_group(),
                "status": "local_phase_slope_estimated_not_transport_delay_proof",
                "delay_days": 18.0,
                "point_count": 3,
                "weighted_r_squared": 0.9,
            }
        ]
    )

    revised_response = requalify_response(response)
    revised_delays = revise_delays(revised_response, delays)

    pd.testing.assert_series_equal(
        revised_response["magnitude"], response["magnitude"], check_names=True
    )
    pd.testing.assert_series_equal(
        revised_response["phase_deg"], response["phase_deg"], check_names=True
    )
    assert revised_response["source_small_signal_local_claim"].astype(bool).all()
    assert not revised_response["small_signal_local_claim"].astype(bool).any()
    assert not revised_response["active_set_invariance_verified"].astype(bool).any()
    assert revised_response["response_regime_scope"].eq(
        "tested_amplitude_hybrid_regime_switching_active_set_unverified"
    ).all()

    delay = revised_delays.iloc[0]
    assert pd.isna(delay["delay_days"])
    assert delay["descriptive_phase_slope_days"] == pytest.approx(18.0)
    assert delay["source_delay_days"] == pytest.approx(18.0)
    assert delay["status"] == "hybrid_regime_phase_slope_not_local_delay"
    assert not bool(delay["local_phase_slope_identified"])


def test_stability_revision_detects_period_constant_dc_drift() -> None:
    stability = pd.DataFrame(
        [
            {
                **_group(
                    policy="mrp_reference",
                    input_signal="demand_multiplier",
                    output_signal="stock",
                ),
                "status": "bounded_repeatable_response_observed",
                "period_count": 3,
                "period_rms_json": "[0.0, 0.0, 0.0]",
                "growth_tolerance": 1.10,
            }
        ]
    )
    trajectory_rows = []
    for period_index, level in enumerate((0.0, 1.0, 2.0, 3.0)):
        for day_in_period in range(4):
            trajectory_rows.append(
                {
                    "condition": "stress",
                    "policy": "mrp_reference",
                    "experiment_input_signal": "demand_multiplier",
                    "period_index": period_index,
                    "day": period_index * 4 + day_in_period,
                    "delta__stock": level,
                }
            )
    response = pd.DataFrame(
        [
            {
                **_group(
                    policy="mrp_reference",
                    input_signal="demand_multiplier",
                    output_signal="stock",
                ),
                "settling_periods_discarded": 1,
            }
        ]
    )

    revised = recalculate_stability(
        stability, pd.DataFrame(trajectory_rows), response
    ).iloc[0]

    assert json.loads(revised["period_total_rms_json"]) == pytest.approx(
        [1.0, 2.0, 3.0]
    )
    assert json.loads(revised["period_ac_rms_json"]) == pytest.approx(
        [0.0, 0.0, 0.0]
    )
    assert revised["response_pattern"] == "monotonic_growth_detected"
    assert not bool(revised["repeatable_periodic_response"])
    assert not bool(revised["global_stability_claimed"])


def test_reporting_period_uses_manifest_or_distinct_days_not_signal_rows() -> None:
    trajectories = pd.DataFrame(
        [
            {
                "period_index": period_index,
                "day": period_index * 8 + day_in_period,
                "output_signal": output_signal,
            }
            for period_index in range(4)
            for day_in_period in range(8)
            for output_signal in ("stock", "arrivals", "orders")
        ]
    )

    configured = _normalized_reporting_config(
        {
            "sampling": {
                "designed_period_days": 196,
                "measured_periods": 4,
                "warmup_days": 60,
            }
        },
        trajectories,
    )
    inferred = _normalized_reporting_config({}, trajectories)

    assert configured["period_days"] == 196
    assert configured["measured_periods"] == 4
    assert configured["warmup_days"] == 60
    assert inferred["period_days"] == 8
    assert inferred["measured_periods"] == 4


def _write_package(root: Path) -> None:
    root.mkdir()
    response_rows = []
    for frequency_bin in (1, 2, 3):
        response_rows.append(
            {
                **_group(),
                "frequency_bin": frequency_bin,
                "frequency_cycles_per_day": frequency_bin / 8.0,
                "period_days": 8.0 / frequency_bin,
                "magnitude": 2.0 + frequency_bin,
                "magnitude_db": 6.0,
                "phase_deg": -15.0 * frequency_bin,
                "coherence": 0.95,
                "coherence_threshold": 0.8,
                "elasticity_db": 6.0,
                "response_detected": True,
                "valid_bin": True,
                "designed_excitation": True,
                "small_signal_local_claim": True,
                "regime_compatible_for_local_claim": False,
                "response_regime_scope": (
                    "hybrid_regime_switching_amplitude_conditioned"
                ),
                "settling_periods_discarded": 1,
            }
        )
    for policy in ("mrp_reference", "canonical_feedback"):
        response_rows.append(
            {
                **_group(policy=policy, output_signal="arrivals"),
                "frequency_bin": 1,
                "frequency_cycles_per_day": 0.125,
                "period_days": 8.0,
                "magnitude": 2.0,
                "magnitude_db": 6.0,
                "phase_deg": 0.0,
                "coherence": 0.95,
                "coherence_threshold": 0.8,
                "elasticity_db": 6.0,
                "response_detected": True,
                "valid_bin": True,
                "designed_excitation": True,
                "small_signal_local_claim": True,
                "regime_compatible_for_local_claim": True,
                "response_regime_scope": "local_fixed_supervisory_regime_trace",
                "settling_periods_discarded": 1,
            }
        )
    response = pd.DataFrame(response_rows)
    response.to_csv(root / "canonical_frequency_response.csv", index=False)

    pd.DataFrame(
        [
            {
                **_group(),
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
                **_group(output_signal="stock"),
                "classical_margin_status": "not_applicable",
                "status": "bounded_repeatable_response_observed",
                "period_count": 3,
                "period_rms_json": "[0.0, 0.0, 0.0]",
                "growth_tolerance": 1.10,
            }
        ]
    ).to_csv(root / "canonical_frequency_stability.csv", index=False)

    pd.DataFrame(
        [
            {
                "condition": "stress",
                "input_signal": "lead_multiplier",
                "output_signal": "arrivals",
                "frequency_bin": 1,
                "v2_minus_mrp_attenuation_db": -0.2,
                "reliable_comparison": True,
                "attenuation_observed": True,
                "dynamic_feedback_modulation_identified": False,
            }
        ]
    ).to_csv(
        root / "canonical_frequency_closed_loop_comparison.csv", index=False
    )

    trajectory_rows = []
    for policy in ("mrp_reference", "canonical_feedback"):
        for period_index, level in enumerate((0.0, 1.0, 2.0, 3.0)):
            gain = 2.0 if policy == "mrp_reference" else 1.8
            for day_in_period in range(8):
                signal = math.sin(2.0 * math.pi * day_in_period / 8.0)
                trajectory_rows.append(
                    {
                        "condition": "stress",
                        "policy": policy,
                        "experiment_input_signal": "lead_multiplier",
                        "period_index": period_index,
                        "day": period_index * 8 + day_in_period,
                        "excitation_fraction__lead_multiplier": signal,
                        "delta__arrivals": gain * signal,
                        "delta__stock": level,
                        "delta__global_order_qty": signal,
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
                "output_signal": "global_order_qty",
                "period_days": 8.0,
                "output_psd_normalized": 1.0,
                "coherence": 0.5,
            }
        ]
    ).to_csv(root / "canonical_frequency_native_spectra.csv", index=False)
    pd.DataFrame(
        [
            {
                "source_run": "native",
                "input_signal": "demand",
                "output_signal": "global_order_qty",
                "band": "weekly_6_to_10_days",
                "period_min_days": 6.0,
                "period_max_days": 10.0,
                "power_amplification_db": 1.0,
            }
        ]
    ).to_csv(root / "canonical_frequency_native_bands.csv", index=False)
    pd.DataFrame(
        columns=[
            "source_run",
            "input_signal",
            "output_signal",
            "period_days",
            "peak_kind",
        ]
    ).to_csv(root / "canonical_frequency_resonances.csv", index=False)
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
    pd.DataFrame(
        [
            {
                "condition": "stress",
                "policy": "canonical_feedback",
                "input_signal": "lead_multiplier",
                "regime": "protect",
                "share": 1.0,
            }
        ]
    ).to_csv(root / "canonical_frequency_regime_occupancy.csv", index=False)
    pd.DataFrame(
        [{"condition": "stress", "experiment_input_signal": "lead_multiplier"}]
    ).to_csv(root / "canonical_frequency_excitation_audit.csv", index=False)

    manifest = {
        "schema_version": "source.v1",
        "coherence_threshold": 0.8,
        "sampling": {
            "designed_period_days": 8,
            "measured_periods": 4,
            "warmup_days": 8,
        },
        "claims": {"small_signal_local_subset_identified": True},
        "evidence_counts": {},
        "limitations": [],
    }
    for filename in (
        "canonical_frequency_manifest.json",
        "canonical_frequency_protocol.json",
    ):
        (root / filename).write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )


def test_revision_is_atomic_non_overwriting_and_hash_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "revised"
    _write_package(source)
    source_response_hash = _sha256(source / "canonical_frequency_response.csv")

    def fake_report(output_root: Path, **_: object) -> Path:
        path = Path(output_root) / "canonical_frequency_report.md"
        path.write_text("# revised report\n", encoding="utf-8")
        return path

    def fake_figures(output_root: Path, **_: object) -> list[Path]:
        paths = []
        for index, filename in enumerate(FIGURE_FILES):
            path = Path(output_root) / filename
            path.write_bytes(b"synthetic-png-" + str(index).encode("ascii"))
            paths.append(path)
        return paths

    monkeypatch.setattr(frequency_reporting, "write_frequency_report", fake_report)
    monkeypatch.setattr(frequency_reporting, "write_frequency_figures", fake_figures)

    result = run_revision(source, output)

    assert result["output_dir"] == output.resolve()
    assert _sha256(source / "canonical_frequency_response.csv") == source_response_hash
    source_response = pd.read_csv(source / "canonical_frequency_response.csv")
    revised_response = pd.read_csv(output / "canonical_frequency_response.csv")
    for field in (
        "frequency_bin",
        "frequency_cycles_per_day",
        "period_days",
        "magnitude",
        "magnitude_db",
        "phase_deg",
        "coherence",
        "elasticity_db",
    ):
        pd.testing.assert_series_equal(
            revised_response[field], source_response[field], check_names=True
        )
    revised = json.loads((output / "canonical_frequency_revision.json").read_text())
    assert not revised["simulation_rerun"]
    assert revised["response_numeric_estimates_unchanged"]
    assert revised["counts"]["local_delay_rows"] == 0

    ledger_path = output / "canonical_frequency_revision_ledger.csv"
    assert revised["ledger"]["sha256"] == _sha256(ledger_path)
    with ledger_path.open(encoding="utf-8", newline="") as stream:
        ledger = list(csv.DictReader(stream))
    assert ledger
    for entry in ledger:
        artifact = output / entry["relative_path"]
        assert artifact.stat().st_size == int(entry["size_bytes"])
        assert _sha256(artifact) == entry["sha256"]

    snapshot = output / "provenance" / "source_artifact" / (
        "canonical_frequency_response.csv"
    )
    assert _sha256(snapshot) == source_response_hash
    assert all((output / filename).is_file() for filename in FIGURE_FILES)

    revision_hash = _sha256(output / "canonical_frequency_revision.json")
    with pytest.raises(FileExistsError):
        run_revision(source, output)
    assert _sha256(output / "canonical_frequency_revision.json") == revision_hash
    assert not list(tmp_path.glob(".revised.staging-*"))
