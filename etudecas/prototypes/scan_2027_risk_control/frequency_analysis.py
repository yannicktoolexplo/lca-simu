"""Frequency-domain estimators for the RESILIENCE-SCAN case study.

The functions in this module deliberately separate two kinds of evidence:

* :func:`welch_native_spectra` describes spectra already present in a run.  A
  transfer estimate obtained from uncontrolled demand is observational and is
  never labelled causal.
* :func:`periodic_frf` estimates a finite-amplitude harmonic-line response from
  a designed, exactly periodic and paired perturbation.  It uses repeated
  periods as an ensemble and reports coherence so weakly identified lines stay
  visible.  A local small-signal derivative requires additional amplitude-sweep
  and active-set evidence outside this estimator.

Only NumPy and pandas are required.  SciPy and python-control are intentionally
not runtime dependencies of ``etudecas``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


FREQUENCY_SAMPLE_INTERVAL_DAYS = 1.0
DEFAULT_COHERENCE_THRESHOLD = 0.60


class FrequencyAnalysisError(ValueError):
    """Raised when a spectral estimate would violate its data contract."""


def _finite_vector(values: Sequence[float] | np.ndarray, *, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or vector.size < 2:
        raise FrequencyAnalysisError(f"{name} must be a one-dimensional vector with at least two samples.")
    if not np.isfinite(vector).all():
        raise FrequencyAnalysisError(f"{name} contains non-finite values.")
    return vector


def normalized_multisine(
    period_days: int,
    bins: Sequence[int],
    *,
    phase_seed: int,
) -> np.ndarray:
    """Return a zero-mean, unit-peak multisine on exact DFT lines.

    Exact integer bins make a rectangular-window FRF leakage-free when an
    integer number of periods is analysed.  Random phases reduce crest factor;
    the final peak normalization keeps the physical perturbation auditable.
    """

    if isinstance(period_days, bool) or int(period_days) < 8:
        raise FrequencyAnalysisError("period_days must be an integer >= 8.")
    n = int(period_days)
    parsed = tuple(int(value) for value in bins)
    if not parsed or len(set(parsed)) != len(parsed):
        raise FrequencyAnalysisError("bins must be a non-empty set of unique integers.")
    if any(value <= 0 or value >= n / 2 for value in parsed):
        raise FrequencyAnalysisError("Every multisine bin must be strictly between DC and Nyquist.")
    rng = np.random.default_rng(int(phase_seed))
    phases = rng.uniform(-math.pi, math.pi, size=len(parsed))
    day = np.arange(n, dtype=float)
    signal = np.zeros(n, dtype=float)
    for frequency_bin, phase in zip(parsed, phases, strict=True):
        signal += np.sin((2.0 * math.pi * frequency_bin * day / n) + phase)
    signal -= float(signal.mean())
    peak = float(np.max(np.abs(signal)))
    if peak <= 1e-12:
        raise FrequencyAnalysisError("The multisine has zero numerical amplitude.")
    return signal / peak


def validate_orthogonal_bins(channels: Mapping[str, Sequence[int]], period_days: int) -> None:
    """Validate that designed input channels occupy disjoint DFT lines."""

    owner: dict[int, str] = {}
    for channel, values in channels.items():
        for raw in values:
            value = int(raw)
            if value <= 0 or value >= int(period_days) / 2:
                raise FrequencyAnalysisError(
                    f"Input {channel!r} uses invalid DFT bin {value} for period {period_days}."
                )
            previous = owner.get(value)
            if previous is not None:
                raise FrequencyAnalysisError(
                    f"DFT bin {value} is shared by {previous!r} and {channel!r}."
                )
            owner[value] = str(channel)


def _bootstrap_complex_frf(
    u_fft: np.ndarray,
    y_fft: np.ndarray,
    *,
    samples: int,
    seed: int,
) -> tuple[float | None, float | None, float | None, float | None]:
    repetitions = len(u_fft)
    if repetitions < 2 or samples <= 0:
        return None, None, None, None
    rng = np.random.default_rng(int(seed))
    magnitudes: list[float] = []
    phases: list[float] = []
    reference = np.sum(y_fft * np.conjugate(u_fft)) / max(
        float(np.sum(np.abs(u_fft) ** 2)), 1e-30
    )
    reference_phase = float(np.angle(reference))
    for _ in range(int(samples)):
        indices = rng.integers(0, repetitions, size=repetitions)
        ub = u_fft[indices]
        yb = y_fft[indices]
        denominator = float(np.sum(np.abs(ub) ** 2))
        if denominator <= 1e-30:
            continue
        estimate = np.sum(yb * np.conjugate(ub)) / denominator
        magnitudes.append(float(abs(estimate)))
        phase_delta = float(np.angle(np.exp(1j * (np.angle(estimate) - reference_phase))))
        phases.append(math.degrees(reference_phase + phase_delta))
    if not magnitudes:
        return None, None, None, None
    return (
        float(np.quantile(magnitudes, 0.025)),
        float(np.quantile(magnitudes, 0.975)),
        float(np.quantile(phases, 0.025)),
        float(np.quantile(phases, 0.975)),
    )


def periodic_frf(
    input_signal: Sequence[float] | np.ndarray,
    output_delta: Sequence[float] | np.ndarray,
    *,
    period_days: int,
    bins: Sequence[int],
    discard_periods: int = 0,
    response_scale: float = 1.0,
    bootstrap_samples: int = 1000,
    bootstrap_seed: int = 0,
    coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
) -> pd.DataFrame:
    """Estimate an empirical H1 harmonic-line response from repeated periods.

    ``output_delta`` must be the excited trajectory minus its paired baseline.
    The input is a fractional perturbation (for example ``+0.03``).  Each
    repeated period is one ensemble member.  The estimate is therefore local to
    the operating condition and perturbation amplitude used by the caller.
    """

    u = _finite_vector(input_signal, name="input_signal")
    y = _finite_vector(output_delta, name="output_delta")
    if len(u) != len(y):
        raise FrequencyAnalysisError("input_signal and output_delta must have equal length.")
    n = int(period_days)
    if n <= 0 or len(u) % n:
        raise FrequencyAnalysisError("Signal length must contain an integer number of periods.")
    repetitions = len(u) // n
    if discard_periods < 0 or discard_periods >= repetitions:
        raise FrequencyAnalysisError("discard_periods must leave at least one analysed period.")
    parsed_bins = tuple(int(value) for value in bins)
    if any(value <= 0 or value >= n / 2 for value in parsed_bins):
        raise FrequencyAnalysisError("Requested FRF bins must lie between DC and Nyquist.")
    scale = float(response_scale)
    if not math.isfinite(scale) or scale <= 0:
        raise FrequencyAnalysisError("response_scale must be finite and strictly positive.")

    u_segments = u.reshape(repetitions, n)[discard_periods:]
    y_segments = y.reshape(repetitions, n)[discard_periods:]
    u_fft = np.fft.rfft(u_segments - u_segments.mean(axis=1, keepdims=True), axis=1) / n
    y_fft = np.fft.rfft(y_segments - y_segments.mean(axis=1, keepdims=True), axis=1) / n
    rows: list[dict[str, Any]] = []
    for frequency_bin in parsed_bins:
        uk = u_fft[:, frequency_bin]
        yk = y_fft[:, frequency_bin]
        suu = float(np.mean(np.abs(uk) ** 2))
        syy = float(np.mean(np.abs(yk) ** 2))
        syu = np.mean(yk * np.conjugate(uk))
        estimate = syu / suu if suu > 1e-30 else complex(math.nan, math.nan)
        response_detected = bool(syy > 1e-30)
        coherence = (
            float((abs(syu) ** 2) / (suu * syy))
            if suu > 1e-30 and syy > 1e-30
            else 0.0
        )
        coherence = min(1.0, max(0.0, coherence))
        magnitude = float(abs(estimate)) if np.isfinite(estimate.real) else math.nan
        phase_deg = (
            float(math.degrees(np.angle(estimate)))
            if np.isfinite(estimate.real) and response_detected
            else math.nan
        )
        ci_low, ci_high, phase_low, phase_high = _bootstrap_complex_frf(
            uk,
            yk,
            samples=int(bootstrap_samples),
            seed=int(bootstrap_seed) + frequency_bin * 104729,
        )
        if not response_detected:
            phase_low = None
            phase_high = None
        frequency = frequency_bin / float(n)
        rows.append(
            {
                "frequency_bin": frequency_bin,
                "frequency_cycles_per_day": frequency,
                "angular_frequency_rad_per_day": 2.0 * math.pi * frequency,
                "period_days": 1.0 / frequency,
                "repetition_count": int(len(uk)),
                "input_line_rms": float(math.sqrt(2.0 * suu)),
                "output_line_rms": float(math.sqrt(2.0 * syy)),
                "line_rms_definition": "temporal_rms_of_real_sinusoidal_dft_component",
                "frf_real": float(estimate.real) if np.isfinite(estimate.real) else None,
                "frf_imag": float(estimate.imag) if np.isfinite(estimate.imag) else None,
                "magnitude": magnitude if math.isfinite(magnitude) else None,
                "magnitude_db": 20.0 * math.log10(max(magnitude, 1e-30)) if math.isfinite(magnitude) else None,
                "phase_deg": phase_deg if math.isfinite(phase_deg) else None,
                "coherence": coherence,
                "coherence_threshold": float(coherence_threshold),
                "response_detected": response_detected,
                "valid_bin": bool(
                    suu > 1e-30
                    and response_detected
                    and coherence >= coherence_threshold
                ),
                "magnitude_period_resampling_q025": ci_low,
                "magnitude_period_resampling_q975": ci_high,
                "phase_period_resampling_q025_deg": phase_low,
                "phase_period_resampling_q975_deg": phase_high,
                "uncertainty_interval_kind": (
                    "period_resampling_percentile_interval_not_coverage_calibrated"
                ),
                "nominal_95_percent_coverage_claimed": False,
                "response_scale": scale,
                "elasticity_magnitude": magnitude / scale if math.isfinite(magnitude) else None,
                "elasticity_db": 20.0 * math.log10(max(magnitude / scale, 1e-30)) if math.isfinite(magnitude) else None,
            }
        )
    return pd.DataFrame(rows)


def periodic_residual_energy(
    input_signals: Mapping[str, Sequence[float] | np.ndarray],
    output_delta: Sequence[float] | np.ndarray,
    *,
    period_days: int,
    excited_bins: Mapping[str, Sequence[int]],
    discard_periods: int = 0,
) -> dict[str, Any]:
    """Quantify output energy away from all designed input lines.

    The residual combines nonlinear distortion, unmodelled exogenous effects
    and stochastic noise.  It is intentionally not presented as pure THD.
    """

    validate_orthogonal_bins(excited_bins, period_days)
    y = _finite_vector(output_delta, name="output_delta")
    n = int(period_days)
    if len(y) % n:
        raise FrequencyAnalysisError("output_delta must contain complete periods.")
    segments = y.reshape(-1, n)[int(discard_periods):]
    spectrum = np.fft.rfft(segments - segments.mean(axis=1, keepdims=True), axis=1) / n
    power = np.mean(np.abs(spectrum) ** 2, axis=0)
    designed = sorted({int(value) for values in excited_bins.values() for value in values})
    admissible = np.arange(1, n // 2, dtype=int)
    residual = np.array([value for value in admissible if value not in designed], dtype=int)
    designed_power = float(power[designed].sum()) if designed else 0.0
    residual_power = float(power[residual].sum()) if len(residual) else 0.0
    ratio = residual_power / max(designed_power, 1e-30)
    return {
        "analysed_period_count": int(len(segments)),
        "designed_line_count": len(designed),
        "residual_line_count": int(len(residual)),
        "designed_output_power": designed_power,
        "residual_output_power": residual_power,
        "residual_to_designed_energy_ratio": ratio,
        "interpretation": "nonlinear_distortion_plus_noise_not_pure_thd",
    }


def _linear_detrend(values: np.ndarray) -> np.ndarray:
    if len(values) < 2:
        return values - values.mean()
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)
    return values - (slope * x + intercept)


def welch_native_spectra(
    signals: Mapping[str, Sequence[float] | np.ndarray],
    *,
    input_signal: str,
    segment_days: int = 365,
    overlap_fraction: float = 0.5,
    sample_interval_days: float = FREQUENCY_SAMPLE_INTERVAL_DAYS,
) -> pd.DataFrame:
    """Return normalized PSD, observational H1 and coherence for native runs."""

    if input_signal not in signals:
        raise FrequencyAnalysisError(f"Unknown native input signal {input_signal!r}.")
    parsed = {name: _finite_vector(values, name=name) for name, values in signals.items()}
    lengths = {len(value) for value in parsed.values()}
    if len(lengths) != 1:
        raise FrequencyAnalysisError("All native signals must have equal length.")
    total = lengths.pop()
    n = min(int(segment_days), total)
    if n < 16:
        raise FrequencyAnalysisError("Native Welch segments must contain at least 16 days.")
    if not 0.0 <= float(overlap_fraction) < 1.0:
        raise FrequencyAnalysisError("overlap_fraction must be in [0, 1).")
    step = max(1, int(round(n * (1.0 - float(overlap_fraction)))))
    starts = list(range(0, total - n + 1, step))
    if not starts:
        starts = [0]
    window = np.hanning(n)
    window_power = float(np.sum(window**2))
    fs = 1.0 / float(sample_interval_days)
    frequency = np.fft.rfftfreq(n, d=float(sample_interval_days))
    transforms: dict[str, np.ndarray] = {}
    means: dict[str, float] = {}
    for name, vector in parsed.items():
        mean = float(np.mean(np.abs(vector)))
        means[name] = mean
        normalization = mean if mean > 1e-12 else 1.0
        transforms[name] = np.stack(
            [
                np.fft.rfft(_linear_detrend(vector[start : start + n] / normalization) * window)
                for start in starts
            ]
        )
    input_fft = transforms[input_signal]
    input_psd = np.mean(np.abs(input_fft) ** 2, axis=0) / (fs * window_power)
    one_sided = np.ones_like(frequency)
    if n % 2 == 0:
        one_sided[1:-1] = 2.0
    else:
        one_sided[1:] = 2.0
    input_psd *= one_sided

    rows: list[dict[str, Any]] = []
    for name, output_fft in transforms.items():
        output_psd = np.mean(np.abs(output_fft) ** 2, axis=0) / (fs * window_power)
        output_psd *= one_sided
        cross = np.mean(output_fft * np.conjugate(input_fft), axis=0) / (fs * window_power)
        cross *= one_sided
        frf = np.divide(cross, input_psd, out=np.zeros_like(cross), where=input_psd > 1e-30)
        coherence = np.divide(
            np.abs(cross) ** 2,
            input_psd * output_psd,
            out=np.zeros_like(input_psd),
            where=(input_psd * output_psd) > 1e-30,
        )
        coherence = np.clip(coherence, 0.0, 1.0)
        for index in range(1, len(frequency)):
            f = float(frequency[index])
            magnitude = float(abs(frf[index]))
            rows.append(
                {
                    "input_signal": input_signal,
                    "output_signal": name,
                    "frequency_bin": index,
                    "frequency_cycles_per_day": f,
                    "period_days": 1.0 / f,
                    "segment_days": n,
                    "segment_count": len(starts),
                    "window": "hann",
                    "detrend": "linear_per_segment",
                    "input_mean_abs": means[input_signal],
                    "output_mean_abs": means[name],
                    "input_psd_normalized": float(input_psd[index]),
                    "output_psd_normalized": float(output_psd[index]),
                    "cross_spectrum_real": float(cross[index].real),
                    "cross_spectrum_imag": float(cross[index].imag),
                    "observational_gain": magnitude,
                    "observational_gain_db": 20.0 * math.log10(max(magnitude, 1e-30)),
                    "observational_phase_deg": float(math.degrees(np.angle(frf[index]))),
                    "coherence": float(coherence[index]),
                    "causal_claimed": False,
                }
            )
    return pd.DataFrame(rows)


FREQUENCY_BANDS: tuple[tuple[str, float, float], ...] = (
    ("rapid_2_to_6_days", 2.0, 6.0),
    ("weekly_6_to_10_days", 6.0, 10.0),
    ("operational_10_to_35_days", 10.0, 35.0),
    ("planning_35_to_120_days", 35.0, 120.0),
    ("seasonal_120_to_400_days", 120.0, 400.0),
)


def native_band_amplification(spectra: pd.DataFrame) -> pd.DataFrame:
    """Integrate normalized output/input PSD ratios in business time bands."""

    required = {
        "output_signal",
        "period_days",
        "input_psd_normalized",
        "output_psd_normalized",
        "frequency_cycles_per_day",
    }
    missing = required - set(spectra.columns)
    if missing:
        raise FrequencyAnalysisError("Native spectra lack: " + ", ".join(sorted(missing)))
    rows: list[dict[str, Any]] = []
    for output_signal, group in spectra.groupby("output_signal", sort=True):
        for band, period_min, period_max in FREQUENCY_BANDS:
            selected = group.loc[
                group["period_days"].ge(period_min)
                & group["period_days"].lt(period_max)
            ].sort_values("frequency_cycles_per_day")
            if selected.empty:
                continue
            input_power = float(np.trapezoid(
                selected["input_psd_normalized"].to_numpy(dtype=float),
                selected["frequency_cycles_per_day"].to_numpy(dtype=float),
            ))
            output_power = float(np.trapezoid(
                selected["output_psd_normalized"].to_numpy(dtype=float),
                selected["frequency_cycles_per_day"].to_numpy(dtype=float),
            ))
            ratio = output_power / max(input_power, 1e-30)
            rows.append(
                {
                    "output_signal": output_signal,
                    "band": band,
                    "period_min_days": period_min,
                    "period_max_days": period_max,
                    "frequency_bin_count": int(len(selected)),
                    "normalized_input_power": input_power,
                    "normalized_output_power": output_power,
                    "power_amplification_ratio": ratio,
                    "power_amplification_db": 10.0 * math.log10(max(ratio, 1e-30)),
                    "bullwhip_amplification": bool(ratio > 1.0),
                    "causal_claimed": False,
                }
            )
    return pd.DataFrame(rows)


def estimate_group_delay(frf_rows: pd.DataFrame) -> dict[str, Any]:
    """Fit a coherence-weighted local phase slope as an approximate delay."""

    required = {"frequency_cycles_per_day", "phase_deg", "coherence", "valid_bin"}
    if not required.issubset(frf_rows.columns):
        return {"status": "not_identifiable_missing_columns", "delay_days": None, "point_count": 0}
    valid = frf_rows.loc[frf_rows["valid_bin"].astype(bool)].copy()
    valid = valid.dropna(subset=["frequency_cycles_per_day", "phase_deg", "coherence"])
    if len(valid) < 3:
        return {"status": "not_identifiable_insufficient_coherent_lines", "delay_days": None, "point_count": int(len(valid))}
    valid = valid.sort_values("frequency_cycles_per_day")
    frequency = valid["frequency_cycles_per_day"].to_numpy(dtype=float)
    phase = np.unwrap(np.deg2rad(valid["phase_deg"].to_numpy(dtype=float)))
    weight = np.clip(valid["coherence"].to_numpy(dtype=float), 1e-6, 1.0)
    design = np.column_stack([np.ones(len(frequency)), frequency])
    weighted_design = design * np.sqrt(weight)[:, None]
    weighted_phase = phase * np.sqrt(weight)
    coefficient, *_ = np.linalg.lstsq(weighted_design, weighted_phase, rcond=None)
    prediction = design @ coefficient
    residual = phase - prediction
    total = phase - np.average(phase, weights=weight)
    r_squared = 1.0 - float(np.sum(weight * residual**2)) / max(float(np.sum(weight * total**2)), 1e-30)
    delay = -float(coefficient[1]) / (2.0 * math.pi)
    return {
        "status": "local_phase_slope_estimated_not_transport_delay_proof",
        "delay_days": delay,
        "phase_intercept_deg": math.degrees(float(coefficient[0])),
        "weighted_r_squared": r_squared,
        "point_count": int(len(valid)),
    }


def paired_segment_growth(
    output_delta: Sequence[float] | np.ndarray,
    *,
    period_days: int,
    discard_periods: int = 0,
    tolerance: float = 1.10,
    numerical_response_floor: float = 1e-12,
) -> dict[str, Any]:
    """Classify repeated-period response shape; never a stability proof.

    A zero response is deliberately separated from a non-zero repeatable
    response.  The previous aggregate ``repeatable_periodic_response`` flag is
    retained for compatibility, but it must not be interpreted as evidence of
    an identified response when every retained RMS is below the numerical
    floor.
    """

    values = _finite_vector(output_delta, name="output_delta")
    n = int(period_days)
    if len(values) % n:
        raise FrequencyAnalysisError("output_delta must contain complete periods.")
    segments = values.reshape(-1, n)[int(discard_periods):]
    period_means = np.mean(segments, axis=1)
    ac_rms = np.sqrt(
        np.mean((segments - period_means[:, np.newaxis]) ** 2, axis=1)
    )
    # Total RMS intentionally retains the period mean.  Using only the
    # mean-centred AC component would classify a stock/backlog drifting from one
    # constant level to another as perfectly repeatable.
    rms = np.sqrt(np.mean(segments**2, axis=1))
    floor = float(numerical_response_floor)
    if not math.isfinite(floor) or floor < 0:
        raise FrequencyAnalysisError(
            "numerical_response_floor must be finite and non-negative."
        )
    first = float(rms[0])
    last = float(rms[-1])
    ratio = last / max(first, 1e-12)
    adjacent = [
        float(rms[index] / max(float(rms[index - 1]), 1e-12))
        for index in range(1, len(rms))
    ]
    max_adjacent_ratio = max(adjacent, default=0.0)
    max_to_first_ratio = float(np.max(rms)) / max(first, 1e-12)
    minimum = float(np.min(rms))
    maximum = float(np.max(rms))
    max_to_min_ratio_unbounded = False
    if maximum <= 1e-12:
        max_to_min_ratio: float | None = 1.0
    elif minimum <= 1e-12:
        max_to_min_ratio = None
        max_to_min_ratio_unbounded = True
    else:
        max_to_min_ratio = maximum / minimum
    growth_detected = bool(
        ratio > float(tolerance)
        or max_adjacent_ratio > float(tolerance)
        or max_to_first_ratio > float(tolerance)
    )
    repeatable = bool(
        max_to_min_ratio is not None
        and max_to_min_ratio <= float(tolerance)
    )
    measurable_response = bool(maximum > floor)
    nonzero_repeatable = bool(measurable_response and repeatable)
    monotonic_growth = bool(
        measurable_response
        and len(rms) >= 2
        and all(
            float(rms[index]) >= float(rms[index - 1]) - floor
            for index in range(1, len(rms))
        )
        and last > max(first, floor) * float(tolerance)
    )
    peak_period_index = int(np.argmax(rms)) if len(rms) else None
    interior_period_peak = bool(
        measurable_response
        and peak_period_index is not None
        and 0 < peak_period_index < len(rms) - 1
        and maximum
        > max(float(rms[0]), float(rms[-1]), floor) * float(tolerance)
    )
    response_pattern = (
        "no_measurable_response"
        if not measurable_response
        else "nonzero_repeatable_response"
        if nonzero_repeatable
        else "monotonic_growth_detected"
        if monotonic_growth
        else "interior_period_peak_transient_or_delay"
        if interior_period_peak
        else "other_nonstationary_response"
    )
    status = (
        "period_to_period_growth_detected"
        if growth_detected
        else "period_to_period_nonstationarity_detected"
        if not repeatable
        else "bounded_repeatable_response_observed"
    )
    return {
        "status": status,
        "period_count": int(len(segments)),
        "first_period_rms": first,
        "last_period_rms": last,
        "last_to_first_rms_ratio": ratio,
        "max_adjacent_rms_ratio": max_adjacent_ratio,
        "max_to_first_rms_ratio": max_to_first_ratio,
        "max_to_min_rms_ratio": max_to_min_ratio,
        "max_to_min_rms_ratio_unbounded": max_to_min_ratio_unbounded,
        "period_rms_json": json.dumps([float(value) for value in rms]),
        "period_total_rms_json": json.dumps([float(value) for value in rms]),
        "period_ac_rms_json": json.dumps([float(value) for value in ac_rms]),
        "period_mean_json": json.dumps([float(value) for value in period_means]),
        "first_period_mean": float(period_means[0]),
        "last_period_mean": float(period_means[-1]),
        "period_mean_drift": float(period_means[-1] - period_means[0]),
        "maximum_absolute_response": float(np.max(np.abs(segments))),
        "terminal_state_by_period_json": json.dumps(
            [float(value) for value in segments[:, -1]]
        ),
        "numerical_response_floor": floor,
        "measurable_response": measurable_response,
        "nonzero_repeatable_response": nonzero_repeatable,
        # The historical field name is retained for CSV compatibility.  The
        # criterion is non-decreasing (within the numerical floor) with a
        # material last/first increase, not mathematically strict monotonicity.
        "strictly_monotonic_growth": monotonic_growth,
        "monotonic_material_growth": monotonic_growth,
        "peak_period_index_after_discard": peak_period_index,
        "interior_period_peak": interior_period_peak,
        "response_pattern": response_pattern,
        "growth_tolerance": float(tolerance),
        "bounded_repeated_response": not growth_detected,
        "repeatable_periodic_response": repeatable,
        "local_stability_claimed": False,
        "global_stability_claimed": False,
    }


def _safe_read_csv(path: Path, required: Sequence[str]) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=list(required))
    frame = pd.read_csv(path)
    missing = set(required) - set(frame.columns)
    if missing:
        raise FrequencyAnalysisError(f"{path} lacks required columns: {', '.join(sorted(missing))}")
    return frame


def _daily_sum(frame: pd.DataFrame, value: str, days: pd.Index) -> pd.Series:
    if frame.empty:
        return pd.Series(0.0, index=days, dtype=float)
    values = pd.to_numeric(frame[value], errors="coerce").fillna(0.0)
    grouped = values.groupby(pd.to_numeric(frame["day"], errors="coerce").fillna(-1).astype(int)).sum()
    return grouped.reindex(days, fill_value=0.0).astype(float)


def extract_frequency_signals(
    result_dir: Path,
    *,
    target_finished_item_id: str,
    probe_supplier_id: str,
    probe_item_id: str,
    probe_dst_node_id: str,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Extract aligned global and targeted daily signals from one engine run."""

    data_root = Path(result_dir) / "data"
    daily = _safe_read_csv(
        data_root / "first_simulation_daily.csv",
        ("day", "demand", "served", "backlog_end", "inventory_total", "produced_qty", "total_supply_cost_day"),
    )
    if daily.empty:
        raise FrequencyAnalysisError(f"Missing non-empty first_simulation_daily.csv in {result_dir}.")
    daily = daily.sort_values("day").drop_duplicates("day", keep="last")
    days = pd.Index(pd.to_numeric(daily["day"], errors="raise").astype(int), name="day")
    if not days.equals(pd.Index(range(int(days.min()), int(days.max()) + 1), name="day")):
        raise FrequencyAnalysisError("Daily KPI days are not contiguous.")
    output = pd.DataFrame(index=days)
    output["global_demand_qty"] = pd.to_numeric(daily.set_index("day")["demand"], errors="coerce").reindex(days).to_numpy(dtype=float)
    output["global_served_qty"] = pd.to_numeric(daily.set_index("day")["served"], errors="coerce").reindex(days).to_numpy(dtype=float)
    output["global_backlog_qty"] = pd.to_numeric(daily.set_index("day")["backlog_end"], errors="coerce").reindex(days).to_numpy(dtype=float)
    output["global_inventory_qty"] = pd.to_numeric(daily.set_index("day")["inventory_total"], errors="coerce").reindex(days).to_numpy(dtype=float)
    output["global_production_qty"] = pd.to_numeric(daily.set_index("day")["produced_qty"], errors="coerce").reindex(days).to_numpy(dtype=float)
    output["global_total_supply_cost_per_day"] = pd.to_numeric(daily.set_index("day")["total_supply_cost_day"], errors="coerce").reindex(days).to_numpy(dtype=float)
    previous_backlog = output["global_backlog_qty"].shift(1, fill_value=0.0)
    required = output["global_demand_qty"] + previous_backlog
    output["global_service_level"] = np.divide(
        output["global_served_qty"], required, out=np.ones(len(output), dtype=float), where=required.to_numpy(dtype=float) > 1e-12
    )

    trace = _safe_read_csv(data_root / "mrp_trace_daily.csv", ("day", "planned_release_qty"))
    shipments = _safe_read_csv(
        data_root / "production_supplier_shipments_daily.csv",
        ("day", "src_node_id", "dst_node_id", "item_id", "shipped_qty"),
    )
    service = _safe_read_csv(
        data_root / "production_demand_service_daily.csv",
        ("day", "item_id", "demand_qty", "served_qty", "backlog_end_qty"),
    )
    products = _safe_read_csv(
        data_root / "production_output_products_daily.csv",
        ("day", "item_id", "produced_qty", "stock_end_of_day"),
    )
    supplier_stocks = _safe_read_csv(
        data_root / "production_supplier_stocks_daily.csv",
        ("day", "node_id", "item_id", "stock_end_of_day"),
    )
    supplier_capacity = _safe_read_csv(
        data_root / "production_supplier_capacity_daily.csv",
        ("day", "node_id", "item_id", "utilization"),
    )
    replenishment_arrivals = _safe_read_csv(
        data_root / "production_input_replenishment_arrivals_daily.csv",
        ("day", "node_id", "item_id", "arrived_qty"),
    )
    output["global_order_qty"] = _daily_sum(trace, "planned_release_qty", days).to_numpy()
    output["global_supplier_shipments_qty"] = _daily_sum(shipments, "shipped_qty", days).to_numpy()
    output["global_order_nervousness"] = output["global_order_qty"].diff().abs().fillna(0.0)
    output["global_production_nervousness"] = output["global_production_qty"].diff().abs().fillna(0.0)

    target_service = service.loc[service["item_id"].astype(str).eq(str(target_finished_item_id))]
    output["target_demand_qty"] = _daily_sum(target_service, "demand_qty", days).to_numpy()
    output["target_served_qty"] = _daily_sum(target_service, "served_qty", days).to_numpy()
    output["target_backlog_qty"] = _daily_sum(target_service, "backlog_end_qty", days).to_numpy()
    target_previous_backlog = output["target_backlog_qty"].shift(1, fill_value=0.0)
    target_required = output["target_demand_qty"] + target_previous_backlog
    output["target_service_level"] = np.divide(
        output["target_served_qty"], target_required, out=np.ones(len(output), dtype=float), where=target_required.to_numpy(dtype=float) > 1e-12
    )
    target_products = products.loc[products["item_id"].astype(str).eq(str(target_finished_item_id))]
    output["target_production_qty"] = _daily_sum(target_products, "produced_qty", days).to_numpy()
    output["target_finished_stock_qty"] = _daily_sum(target_products, "stock_end_of_day", days).to_numpy()

    probe_shipments = shipments.loc[
        shipments["src_node_id"].astype(str).eq(str(probe_supplier_id))
        & shipments["dst_node_id"].astype(str).eq(str(probe_dst_node_id))
        & shipments["item_id"].astype(str).eq(str(probe_item_id))
    ]
    output["probe_supplier_shipments_qty"] = _daily_sum(probe_shipments, "shipped_qty", days).to_numpy()
    probe_arrivals = replenishment_arrivals.loc[
        replenishment_arrivals["node_id"].astype(str).eq(str(probe_dst_node_id))
        & replenishment_arrivals["item_id"].astype(str).eq(str(probe_item_id))
    ]
    output["probe_destination_arrivals_qty"] = _daily_sum(
        probe_arrivals, "arrived_qty", days
    ).to_numpy()
    probe_stocks = supplier_stocks.loc[
        supplier_stocks["node_id"].astype(str).eq(str(probe_supplier_id))
        & supplier_stocks["item_id"].astype(str).eq(str(probe_item_id))
    ]
    output["probe_supplier_stock_qty"] = _daily_sum(probe_stocks, "stock_end_of_day", days).to_numpy()
    probe_capacity = supplier_capacity.loc[
        supplier_capacity["node_id"].astype(str).eq(str(probe_supplier_id))
        & supplier_capacity["item_id"].astype(str).eq(str(probe_item_id))
    ]
    if probe_capacity.empty:
        output["probe_supplier_utilization"] = 0.0
    else:
        utilization = pd.to_numeric(probe_capacity["utilization"], errors="coerce").fillna(0.0)
        output["probe_supplier_utilization"] = utilization.groupby(
            pd.to_numeric(probe_capacity["day"], errors="coerce").fillna(-1).astype(int)
        ).max().reindex(days, fill_value=0.0).to_numpy(dtype=float)

    output["control_order_multiplier"] = 1.0
    output["control_safety_stock_multiplier"] = 1.0
    output["control_production_target_multiplier"] = 1.0
    commands_path = data_root / "canonical_closed_loop_commands.csv"
    if commands_path.is_file():
        commands = pd.read_csv(commands_path)
        if {"effective_day", "effective_json"}.issubset(commands.columns):
            for _, row in commands.iterrows():
                try:
                    effective = json.loads(str(row.get("effective_json") or "{}"))
                except json.JSONDecodeError:
                    continue
                day = int(row["effective_day"])
                if day not in output.index or not isinstance(effective, Mapping):
                    continue
                for action in (
                    "order_multiplier",
                    "safety_stock_multiplier",
                    "production_target_multiplier",
                ):
                    if action in effective:
                        output.loc[day, f"control_{action}"] = float(effective[action])

    if not np.isfinite(output.to_numpy(dtype=float)).all():
        raise FrequencyAnalysisError(f"Extracted signals contain non-finite values: {result_dir}")
    units = {
        "global_demand_qty": "unit/day mixed portfolio",
        "global_served_qty": "unit/day mixed portfolio",
        "global_service_level": "fraction",
        "global_backlog_qty": "unit mixed portfolio",
        "global_inventory_qty": "unit mixed portfolio",
        "global_order_qty": "unit/day mixed portfolio",
        "global_production_qty": "unit/day mixed portfolio",
        "global_supplier_shipments_qty": "unit/day mixed portfolio",
        "global_total_supply_cost_per_day": "currency/day proxy",
        "global_order_nervousness": "absolute unit/day change",
        "global_production_nervousness": "absolute unit/day change",
        "target_demand_qty": "unit/day",
        "target_served_qty": "unit/day",
        "target_service_level": "fraction",
        "target_backlog_qty": "unit",
        "target_production_qty": "unit/day",
        "target_finished_stock_qty": "unit",
        "probe_supplier_shipments_qty": "item unit/day",
        "probe_destination_arrivals_qty": "item unit/day",
        "probe_supplier_stock_qty": "item unit",
        "probe_supplier_utilization": "fraction",
        "control_order_multiplier": "dimensionless",
        "control_safety_stock_multiplier": "dimensionless",
        "control_production_target_multiplier": "dimensionless",
    }
    return output.reset_index(), units


__all__ = [
    "DEFAULT_COHERENCE_THRESHOLD",
    "FREQUENCY_BANDS",
    "FrequencyAnalysisError",
    "estimate_group_delay",
    "extract_frequency_signals",
    "native_band_amplification",
    "normalized_multisine",
    "paired_segment_growth",
    "periodic_frf",
    "periodic_residual_energy",
    "validate_orthogonal_bins",
    "welch_native_spectra",
]
