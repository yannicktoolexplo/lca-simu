#!/usr/bin/env python3
"""Posthoc scientific audit for canonical frequency-study artifacts.

The audit is deliberately read-only with respect to the scientific package.  It
reclassifies existing evidence and writes a separate, deterministic audit
bundle.  It does not rerun the simulator and it does not alter source estimates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


SCHEMA_VERSION = "scan.canonical_frequency_posthoc_audit.v1"
DEFAULT_COHERENCE_THRESHOLD = 0.8
DEFAULT_NO_RESPONSE_FLOOR = 1e-12
DEFAULT_GROWTH_TOLERANCE = 1.10
DEFAULT_DISCARD_PERIODS = 1

SOURCE_FILES = {
    "stability": "canonical_frequency_stability.csv",
    "response": "canonical_frequency_response.csv",
    "delays": "canonical_frequency_delays.csv",
    "comparison": "canonical_frequency_closed_loop_comparison.csv",
    "trajectories": "canonical_frequency_trajectories.csv",
    "native_spectra": "canonical_frequency_native_spectra.csv",
    "native_bands": "canonical_frequency_native_bands.csv",
}

AUDIT_FILES = {
    "json": "canonical_frequency_audit.json",
    "markdown": "canonical_frequency_audit.md",
    "stability": "canonical_frequency_audit_stability.csv",
    "phase_slopes": "canonical_frequency_audit_phase_slopes.csv",
    "comparisons": "canonical_frequency_audit_comparisons.csv",
    "paired_periods": "canonical_frequency_audit_paired_periods.csv",
    "native_band_coherence": "canonical_frequency_audit_native_band_coherence.csv",
}

GROUP_KEYS = ("study_kind", "condition", "policy", "input_signal", "output_signal")
COMPARISON_KEYS = ("condition", "input_signal", "output_signal", "frequency_bin")


class FrequencyAuditError(RuntimeError):
    """Raised when source artifacts cannot support the requested audit."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _to_optional_bool(value: Any) -> bool | None:
    """Parse a CSV boolean while preserving missing or unrecognised evidence."""

    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [_json_safe(row) for row in frame.to_dict(orient="records")]


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = set(required) - set(frame.columns)
    if missing:
        raise FrequencyAuditError(f"{label} lacks required columns: {', '.join(sorted(missing))}")


def _parse_period_rms(value: Any) -> np.ndarray:
    try:
        parsed = json.loads(str(value))
        array = np.asarray(parsed, dtype=float)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise FrequencyAuditError(f"Invalid period_rms_json: {value!r}") from exc
    if array.ndim != 1 or array.size == 0 or not np.isfinite(array).all():
        raise FrequencyAuditError("period_rms_json must be a non-empty finite vector.")
    if (array < 0.0).any():
        raise FrequencyAuditError("period_rms_json cannot contain negative RMS values.")
    return array


def classify_stability_sequence(
    period_rms: Sequence[float],
    *,
    no_response_floor: float = DEFAULT_NO_RESPONSE_FLOOR,
    growth_tolerance: float = DEFAULT_GROWTH_TOLERANCE,
) -> tuple[str, str]:
    """Classify repeated-period RMS with ``paired_segment_growth`` semantics."""

    values = np.asarray(period_rms, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise FrequencyAuditError("period_rms must be a non-empty finite vector.")
    floor = float(no_response_floor)
    tolerance = float(growth_tolerance)
    if floor < 0.0 or tolerance <= 1.0:
        raise FrequencyAuditError("Invalid stability classification thresholds.")
    features = _stability_sequence_features(
        values,
        no_response_floor=floor,
        growth_tolerance=tolerance,
    )
    if not features["measurable_response"]:
        return "no_measurable_response", "all_period_rms_at_or_below_numerical_floor"
    if features["nonzero_repeatable_response"]:
        return "nonzero_repeatable", "nonzero_max_to_min_rms_within_tolerance"
    if features["monotonic_material_growth"]:
        return "monotonic_growth", "nondecreasing_rms_with_material_last_to_first_growth"
    if features["interior_period_peak"]:
        return "interior_peak", "largest_rms_is_a_material_interior_period_peak"
    return "other", "nonzero_sequence_not_repeatable_or_monotonic_and_without_material_interior_peak"


def _stability_sequence_features(
    period_rms: Sequence[float],
    *,
    no_response_floor: float,
    growth_tolerance: float,
) -> dict[str, Any]:
    """Mirror the thresholds and ordering used by ``paired_segment_growth``."""

    values = np.asarray(period_rms, dtype=float)
    floor = float(no_response_floor)
    tolerance = float(growth_tolerance)
    first = float(values[0])
    last = float(values[-1])
    ratio = last / max(first, 1e-12)
    adjacent = [
        float(values[index] / max(float(values[index - 1]), 1e-12))
        for index in range(1, len(values))
    ]
    max_adjacent_ratio = max(adjacent, default=0.0)
    maximum = float(np.max(values))
    minimum = float(np.min(values))
    max_to_first_ratio = maximum / max(first, 1e-12)
    if maximum <= 1e-12:
        max_to_min_ratio: float | None = 1.0
        max_to_min_unbounded = False
    elif minimum <= 1e-12:
        max_to_min_ratio = None
        max_to_min_unbounded = True
    else:
        max_to_min_ratio = maximum / minimum
        max_to_min_unbounded = False
    growth_detected = bool(
        ratio > tolerance
        or max_adjacent_ratio > tolerance
        or max_to_first_ratio > tolerance
    )
    repeatable = bool(
        max_to_min_ratio is not None and max_to_min_ratio <= tolerance
    )
    measurable = bool(maximum > floor)
    nonzero_repeatable = bool(measurable and repeatable)
    monotonic = bool(
        measurable
        and len(values) >= 2
        and all(
            float(values[index]) >= float(values[index - 1]) - floor
            for index in range(1, len(values))
        )
        and last > max(first, floor) * tolerance
    )
    peak_index = int(np.argmax(values))
    interior_peak = bool(
        measurable
        and 0 < peak_index < len(values) - 1
        and maximum > max(first, last, floor) * tolerance
    )
    return {
        "first_period_rms": first,
        "last_period_rms": last,
        "minimum_period_rms": minimum,
        "maximum_period_rms": maximum,
        "maximum_period_index": peak_index,
        "last_to_first_rms_ratio": ratio,
        "max_adjacent_rms_ratio": max_adjacent_ratio,
        "max_to_first_rms_ratio": max_to_first_ratio,
        "max_to_min_rms_ratio": max_to_min_ratio,
        "max_to_min_rms_ratio_unbounded": max_to_min_unbounded,
        "growth_detected": growth_detected,
        "repeatable_periodic_response": repeatable,
        "measurable_response": measurable,
        "nonzero_repeatable_response": nonzero_repeatable,
        "monotonic_material_growth": monotonic,
        "interior_period_peak": interior_peak,
    }


def _stability_discard_count(
    raw: Mapping[str, Any],
    response: pd.DataFrame | None,
    period_indexes: Sequence[int],
) -> tuple[int, str]:
    if response is not None and not response.empty:
        selected = response.copy()
        for key in GROUP_KEYS:
            if key in selected:
                selected = selected.loc[
                    selected[key].astype(str).eq(str(raw.get(key)))
                ]
        if "settling_periods_discarded" in selected and not selected.empty:
            documented = pd.to_numeric(
                selected["settling_periods_discarded"], errors="coerce"
            ).dropna()
            if not documented.empty:
                return max(0, int(documented.iloc[0])), "response_settling_periods_discarded"
    source_period_count = _to_float(raw.get("period_count"))
    if source_period_count is not None:
        inferred = max(0, len(period_indexes) - int(source_period_count))
        return inferred, "inferred_from_trajectory_minus_source_period_count"
    return DEFAULT_DISCARD_PERIODS, "default_discard_periods"


def _trajectory_stability_evidence(
    raw: Mapping[str, Any],
    trajectories: pd.DataFrame | None,
    response: pd.DataFrame | None,
) -> tuple[dict[str, Any] | None, str]:
    if trajectories is None or trajectories.empty:
        return None, "trajectory_table_missing_or_empty"
    required = {
        "condition",
        "policy",
        "experiment_input_signal",
        "period_index",
        "day",
    }
    if not required.issubset(trajectories.columns):
        return None, "trajectory_group_columns_missing"
    output_column = f"delta__{raw.get('output_signal')}"
    if output_column not in trajectories:
        return None, "trajectory_delta_output_column_missing"
    selected = trajectories.loc[
        trajectories["condition"].astype(str).eq(str(raw.get("condition")))
        & trajectories["policy"].astype(str).eq(str(raw.get("policy")))
        & trajectories["experiment_input_signal"].astype(str).eq(
            str(raw.get("input_signal"))
        )
    ].copy()
    if selected.empty:
        return None, "trajectory_group_not_found"
    selected["_period_index"] = pd.to_numeric(
        selected["period_index"], errors="coerce"
    )
    if selected["_period_index"].isna().any():
        return None, "trajectory_period_index_invalid"
    period_indexes = sorted(int(value) for value in selected["_period_index"].unique())
    discard_count, discard_source = _stability_discard_count(
        raw, response, period_indexes
    )
    retained_indexes = period_indexes[discard_count:]
    if not retained_indexes:
        return None, "trajectory_discard_removes_all_periods"
    total_rms: list[float] = []
    ac_rms: list[float] = []
    means: list[float] = []
    terminal: list[float] = []
    sample_counts: list[int] = []
    maximum_absolute = 0.0
    for period_index in retained_indexes:
        period = selected.loc[selected["_period_index"].eq(period_index)].sort_values(
            "day", kind="stable"
        )
        values = pd.to_numeric(period[output_column], errors="coerce").to_numpy(
            dtype=float
        )
        if values.size == 0 or not np.isfinite(values).all():
            return None, "trajectory_period_values_missing_or_nonfinite"
        mean = float(np.mean(values))
        means.append(mean)
        total_rms.append(float(np.sqrt(np.mean(values**2))))
        ac_rms.append(float(np.sqrt(np.mean((values - mean) ** 2))))
        terminal.append(float(values[-1]))
        sample_counts.append(int(len(values)))
        maximum_absolute = max(maximum_absolute, float(np.max(np.abs(values))))
    return {
        "period_total_rms": np.asarray(total_rms, dtype=float),
        "period_ac_rms": np.asarray(ac_rms, dtype=float),
        "period_means": np.asarray(means, dtype=float),
        "terminal_states": np.asarray(terminal, dtype=float),
        "period_indexes": retained_indexes,
        "period_sample_counts": sample_counts,
        "discarded_period_count": discard_count,
        "discard_count_source": discard_source,
        "trajectory_output_column": output_column,
        "maximum_absolute_response": maximum_absolute,
    }, "trajectory_delta_total_rms_dc_included"


def audit_stability(
    stability: pd.DataFrame,
    *,
    trajectories: pd.DataFrame | None = None,
    response: pd.DataFrame | None = None,
    no_response_floor: float = DEFAULT_NO_RESPONSE_FLOOR,
    growth_tolerance: float = DEFAULT_GROWTH_TOLERANCE,
) -> pd.DataFrame:
    _require_columns(stability, (*GROUP_KEYS, "period_rms_json"), "stability CSV")
    rows: list[dict[str, Any]] = []
    for raw in stability.to_dict(orient="records"):
        legacy_values = _parse_period_rms(raw["period_rms_json"])
        trajectory_evidence, evidence_source = _trajectory_stability_evidence(
            raw, trajectories, response
        )
        if trajectory_evidence is not None:
            values = trajectory_evidence["period_total_rms"]
            ac_rms = trajectory_evidence["period_ac_rms"]
            period_means = trajectory_evidence["period_means"]
            terminal_states = trajectory_evidence["terminal_states"]
            classification_rms_includes_dc: bool | None = True
            fallback_reason = None
        else:
            values = legacy_values
            ac_rms = None
            period_means = None
            terminal_states = None
            classification_rms_includes_dc = None
            fallback_reason = evidence_source
            evidence_source = "legacy_period_rms_json_fallback"
        row_tolerance = _to_float(raw.get("growth_tolerance")) or float(growth_tolerance)
        classification, reason = classify_stability_sequence(
            values,
            no_response_floor=no_response_floor,
            growth_tolerance=row_tolerance,
        )
        features = _stability_sequence_features(
            values,
            no_response_floor=no_response_floor,
            growth_tolerance=row_tolerance,
        )
        rows.append(
            {
                **{key: raw.get(key) for key in GROUP_KEYS},
                "source_status": raw.get("status"),
                "audit_classification": classification,
                "classification_reason": reason,
                "classification_metric_source": evidence_source,
                "classification_rms_includes_dc": classification_rms_includes_dc,
                "trajectory_recalculated": trajectory_evidence is not None,
                "trajectory_fallback_reason": fallback_reason,
                "trajectory_output_column": (
                    trajectory_evidence["trajectory_output_column"]
                    if trajectory_evidence is not None
                    else None
                ),
                "discarded_period_count": (
                    trajectory_evidence["discarded_period_count"]
                    if trajectory_evidence is not None
                    else None
                ),
                "discard_count_source": (
                    trajectory_evidence["discard_count_source"]
                    if trajectory_evidence is not None
                    else None
                ),
                "retained_period_indexes_json": (
                    json.dumps(trajectory_evidence["period_indexes"])
                    if trajectory_evidence is not None
                    else None
                ),
                "period_sample_counts_json": (
                    json.dumps(trajectory_evidence["period_sample_counts"])
                    if trajectory_evidence is not None
                    else None
                ),
                "period_count": int(len(values)),
                **features,
                "growth_tolerance": row_tolerance,
                "no_response_floor": float(no_response_floor),
                "period_rms_json": json.dumps([float(value) for value in values]),
                "period_total_rms_json": json.dumps(
                    [float(value) for value in values]
                ),
                "period_ac_rms_json": (
                    json.dumps([float(value) for value in ac_rms])
                    if ac_rms is not None
                    else None
                ),
                "period_mean_json": (
                    json.dumps([float(value) for value in period_means])
                    if period_means is not None
                    else None
                ),
                "first_period_mean": (
                    float(period_means[0]) if period_means is not None else None
                ),
                "last_period_mean": (
                    float(period_means[-1]) if period_means is not None else None
                ),
                "period_mean_drift": (
                    float(period_means[-1] - period_means[0])
                    if period_means is not None
                    else None
                ),
                "terminal_state_by_period_json": (
                    json.dumps([float(value) for value in terminal_states])
                    if terminal_states is not None
                    else None
                ),
                "maximum_absolute_response": (
                    trajectory_evidence["maximum_absolute_response"]
                    if trajectory_evidence is not None
                    else None
                ),
                "legacy_source_period_rms_json": json.dumps(
                    [float(value) for value in legacy_values]
                ),
                "local_stability_proven": False,
                "global_stability_proven": False,
            }
        )
    return pd.DataFrame(rows).sort_values(list(GROUP_KEYS), kind="stable").reset_index(drop=True)


def audit_phase_slopes(delays: pd.DataFrame, response: pd.DataFrame) -> pd.DataFrame:
    """Reclassify phase slopes using the response rows' posthoc regime scope."""

    _require_columns(delays, (*GROUP_KEYS, "delay_days", "status"), "delay CSV")
    _require_columns(response, (*GROUP_KEYS, "valid_bin"), "response CSV")
    tested_amplitude_field = "tested_amplitude_regime_trace_compatible"
    has_tested_amplitude_evidence = tested_amplitude_field in response.columns
    if not has_tested_amplitude_evidence:
        _require_columns(
            response,
            ("small_signal_local_claim", "response_regime_scope"),
            "legacy response CSV",
        )
    response_groups = {
        tuple(str(row[key]) for key in GROUP_KEYS): group.copy()
        for _, group in response.groupby(list(GROUP_KEYS), sort=False, dropna=False)
        for row in [group.iloc[0]]
    }
    rows: list[dict[str, Any]] = []
    for raw in delays.to_dict(orient="records"):
        key = tuple(str(raw.get(name)) for name in GROUP_KEYS)
        group = response_groups.get(key, pd.DataFrame())
        if group.empty:
            valid = group
        else:
            valid = group.loc[group["valid_bin"].map(_to_bool)].copy()
        valid_count = int(len(valid))
        small_count = (
            int(valid["small_signal_local_claim"].map(_to_bool).sum())
            if not valid.empty and "small_signal_local_claim" in valid.columns
            else 0
        )
        scopes = sorted(
            value
            for value in valid.get("response_regime_scope", pd.Series(dtype=str))
            .dropna()
            .astype(str)
            .unique()
            if value
        )
        source_delay_days = _to_float(raw.get("delay_days"))
        source_descriptive_days = _to_float(raw.get("descriptive_phase_slope_days"))
        if source_descriptive_days is not None:
            source_equivalent_days = source_descriptive_days
            source_equivalent_field = "descriptive_phase_slope_days"
        else:
            source_equivalent_days = source_delay_days
            source_equivalent_field = "delay_days" if source_delay_days is not None else None

        if has_tested_amplitude_evidence:
            compatible_values = (
                valid[tested_amplitude_field].map(_to_optional_bool)
                if not valid.empty
                else pd.Series(dtype=object)
            )
            compatible_count = int((compatible_values == True).sum())  # noqa: E712
            incompatible_count = int((compatible_values == False).sum())  # noqa: E712
            unknown_compatibility_count = valid_count - compatible_count - incompatible_count
            compatibility_source = tested_amplitude_field
            legacy_fallback = False
            hybrid_count = incompatible_count
        else:
            compatible_count = small_count
            hybrid_count = int(
                valid["response_regime_scope"]
                .astype(str)
                .eq("hybrid_regime_switching_amplitude_conditioned")
                .sum()
            ) if not valid.empty else 0
            incompatible_count = hybrid_count
            unknown_compatibility_count = max(
                0, valid_count - compatible_count - incompatible_count
            )
            compatibility_source = (
                "legacy_small_signal_local_claim_and_response_regime_scope"
            )
            legacy_fallback = True

        active_set_verified_count = (
            int(valid["active_set_invariance_verified"].map(_to_bool).sum())
            if not valid.empty and "active_set_invariance_verified" in valid.columns
            else 0
        )
        if source_equivalent_days is None:
            classification = "not_identified"
            interpretation = "no_finite_phase_slope_estimate"
        elif has_tested_amplitude_evidence:
            if valid_count > 0 and incompatible_count == valid_count:
                classification = "hybrid_regime_transition_phase_slope"
                interpretation = (
                    "tested_amplitude_phase_slope_across_regime_switching_"
                    "not_a_local_or_transport_delay"
                )
            elif compatible_count > 0 and incompatible_count > 0:
                classification = "mixed_scope_phase_slope"
                interpretation = (
                    "mixed_tested_amplitude_regime_compatibility_precludes_"
                    "a_local_delay_claim"
                )
            elif valid_count > 0 and compatible_count == valid_count:
                classification = (
                    "tested_amplitude_regime_compatible_active_set_unverified"
                )
                interpretation = (
                    "tested_amplitude_regime_trace_compatible_but_active_set_"
                    "and_zero_amplitude_locality_unverified"
                )
            else:
                classification = "scope_unsupported_phase_slope"
                interpretation = (
                    "finite_source_slope_lacks_complete_tested_amplitude_"
                    "regime_compatibility_evidence"
                )
        elif hybrid_count > 0 and small_count == 0:
            classification = "hybrid_regime_transition_phase_slope"
            interpretation = "phase_slope_across_regime_switching_not_a_local_or_transport_delay"
        elif hybrid_count > 0 and small_count > 0:
            classification = "mixed_scope_phase_slope"
            interpretation = "mixed_local_and_hybrid_lines_preclude_a_local_delay_claim"
        elif valid_count > 0 and small_count == valid_count:
            classification = "supervisory_regime_compatible_phase_slope"
            interpretation = "legacy_regime_compatible_phase_slope_not_a_transport_delay_proof"
        else:
            classification = "scope_unsupported_phase_slope"
            interpretation = "finite_source_slope_lacks_regime_compatible_support"
        rows.append(
            {
                **{name: raw.get(name) for name in GROUP_KEYS},
                "source_status": raw.get("status"),
                "source_delay_days": source_delay_days,
                "source_descriptive_phase_slope_days": source_descriptive_days,
                "phase_slope_equivalent_days": source_equivalent_days,
                "phase_slope_value_source_field": source_equivalent_field,
                "phase_slope_classification": classification,
                "audit_interpretation": interpretation,
                "source_point_count": int(_to_float(raw.get("point_count")) or 0),
                "valid_response_line_count": valid_count,
                "supervisory_regime_compatible_line_count": small_count,
                "tested_amplitude_regime_compatible_line_count": compatible_count,
                "tested_amplitude_regime_incompatible_line_count": incompatible_count,
                "tested_amplitude_regime_compatibility_unknown_line_count": (
                    unknown_compatibility_count
                ),
                "regime_compatibility_evidence_source": compatibility_source,
                "legacy_regime_compatibility_fallback": legacy_fallback,
                "active_set_invariance_verified_line_count": active_set_verified_count,
                "hybrid_regime_line_count": hybrid_count,
                "response_regime_scopes": "|".join(scopes),
                "weighted_r_squared": _to_float(raw.get("weighted_r_squared")),
                "local_delay_claimed": False,
                "transport_delay_claimed": False,
            }
        )
    return pd.DataFrame(rows).sort_values(list(GROUP_KEYS), kind="stable").reset_index(drop=True)


def _period_line_terms(
    frame: pd.DataFrame,
    *,
    input_column: str,
    output_column: str,
    frequency_bin: int,
    discard_periods: int,
) -> dict[int, dict[str, Any]]:
    _require_columns(frame, ("period_index", "day", input_column, output_column), "trajectory group")
    rows: dict[int, dict[str, Any]] = {}
    for raw_period, group in frame.groupby("period_index", sort=True):
        period_index = int(raw_period)
        if period_index < int(discard_periods):
            continue
        ordered = group.sort_values("day", kind="stable")
        u = pd.to_numeric(ordered[input_column], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(ordered[output_column], errors="coerce").to_numpy(dtype=float)
        if len(u) < 4 or not np.isfinite(u).all() or not np.isfinite(y).all():
            continue
        u_fft = np.fft.rfft(u - float(np.mean(u))) / len(u)
        y_fft = np.fft.rfft(y - float(np.mean(y))) / len(y)
        if frequency_bin <= 0 or frequency_bin >= len(u_fft):
            continue
        uk = complex(u_fft[frequency_bin])
        yk = complex(y_fft[frequency_bin])
        suu = float(abs(uk) ** 2)
        syu = yk * np.conjugate(uk)
        h = syu / suu if suu > 1e-30 else None
        rows[period_index] = {
            "suu": suu,
            "syu": syu,
            "h": h,
            "sample_count": int(len(u)),
        }
    return rows


def _weak_compositions(total: int, length: int) -> Iterable[tuple[int, ...]]:
    if length == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for tail in _weak_compositions(total - first, length - 1):
            yield (first, *tail)


def _weighted_empirical_quantile(values: Sequence[tuple[float, int]], quantile: float) -> float:
    ordered = sorted(values, key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    if total <= 0:
        raise FrequencyAuditError("Cannot take a quantile of an empty weighted distribution.")
    target = float(quantile) * total
    cumulative = 0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= target:
            return float(value)
    return float(ordered[-1][0])


def exact_paired_resampling_interval(
    mrp_terms: Sequence[Mapping[str, Any]],
    v2_terms: Sequence[Mapping[str, Any]],
    *,
    output_floor: float = 1e-30,
    max_compositions: int = 2_000_000,
) -> dict[str, Any]:
    """Enumerate the exact paired non-parametric bootstrap distribution.

    Weak compositions avoid expanding all ordered ``n**n`` resamples.  Each
    composition is weighted by its exact multinomial multiplicity.
    """

    if len(mrp_terms) != len(v2_terms) or not mrp_terms:
        return {
            "available": False,
            "reason": "no_equal_nonempty_paired_period_set",
            "paired_period_count": min(len(mrp_terms), len(v2_terms)),
        }
    n = len(mrp_terms)
    composition_count = math.comb((2 * n) - 1, n)
    if composition_count > int(max_compositions):
        return {
            "available": False,
            "reason": "exact_composition_limit_exceeded",
            "paired_period_count": n,
            "composition_count": composition_count,
        }
    factorial_n = math.factorial(n)
    weighted_values: list[tuple[float, int]] = []
    undefined_weight = 0
    for counts in _weak_compositions(n, n):
        multiplicity = factorial_n
        for count in counts:
            multiplicity //= math.factorial(count)
        mrp_suu = sum(count * float(term["suu"]) for count, term in zip(counts, mrp_terms, strict=True))
        v2_suu = sum(count * float(term["suu"]) for count, term in zip(counts, v2_terms, strict=True))
        if mrp_suu <= 1e-30 or v2_suu <= 1e-30:
            undefined_weight += multiplicity
            continue
        mrp_syu = sum(count * complex(term["syu"]) for count, term in zip(counts, mrp_terms, strict=True))
        v2_syu = sum(count * complex(term["syu"]) for count, term in zip(counts, v2_terms, strict=True))
        mrp_magnitude = abs(mrp_syu / mrp_suu)
        v2_magnitude = abs(v2_syu / v2_suu)
        if mrp_magnitude <= output_floor:
            undefined_weight += multiplicity
            continue
        db = 20.0 * math.log10(max(v2_magnitude / mrp_magnitude, 1e-300))
        weighted_values.append((db, multiplicity))
    total_weight = n**n
    defined_weight = sum(weight for _, weight in weighted_values)
    if not weighted_values:
        return {
            "available": False,
            "reason": "all_exact_resamples_have_zero_mrp_response",
            "paired_period_count": n,
            "composition_count": composition_count,
            "ordered_resample_count": total_weight,
            "undefined_resample_weight": undefined_weight,
        }
    return {
        "available": True,
        "method": "exact_paired_period_bootstrap_multinomial_enumeration_empirical_inverse_cdf",
        "paired_period_count": n,
        "composition_count": composition_count,
        "ordered_resample_count": total_weight,
        "defined_resample_weight": defined_weight,
        "undefined_resample_weight": undefined_weight,
        "defined_resample_mass_share": defined_weight / float(total_weight),
        "attenuation_db_min": min(value for value, _ in weighted_values),
        "attenuation_db_q025": _weighted_empirical_quantile(weighted_values, 0.025),
        "attenuation_db_median": _weighted_empirical_quantile(weighted_values, 0.5),
        "attenuation_db_q975": _weighted_empirical_quantile(weighted_values, 0.975),
        "attenuation_db_max": max(value for value, _ in weighted_values),
        "zero_db_in_percentile_interval": bool(
            _weighted_empirical_quantile(weighted_values, 0.025) <= 0.0
            <= _weighted_empirical_quantile(weighted_values, 0.975)
        ),
    }


def _discard_periods_for_comparison(response: pd.DataFrame, raw: Mapping[str, Any]) -> int:
    selected = response.copy()
    for key in ("condition", "input_signal", "output_signal"):
        if key in selected:
            selected = selected.loc[selected[key].astype(str).eq(str(raw.get(key)))]
    if "policy" in selected:
        selected = selected.loc[selected["policy"].astype(str).eq("mrp_reference")]
    if "settling_periods_discarded" in selected and not selected.empty:
        values = pd.to_numeric(selected["settling_periods_discarded"], errors="coerce").dropna()
        if not values.empty:
            return max(0, int(values.iloc[0]))
    return DEFAULT_DISCARD_PERIODS


def audit_comparisons(
    comparison: pd.DataFrame,
    trajectories: pd.DataFrame,
    response: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _require_columns(comparison, COMPARISON_KEYS, "closed-loop comparison CSV")
    _require_columns(
        trajectories,
        ("condition", "policy", "experiment_input_signal", "day", "period_index"),
        "trajectory CSV",
    )
    summary_rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    for raw in comparison.to_dict(orient="records"):
        condition = str(raw["condition"])
        input_signal = str(raw["input_signal"])
        output_signal = str(raw["output_signal"])
        frequency_bin = int(float(raw["frequency_bin"]))
        input_column = f"excitation_fraction__{input_signal}"
        if input_column not in trajectories.columns:
            input_column = input_signal
        output_column = f"delta__{output_signal}"
        if input_column not in trajectories.columns or output_column not in trajectories.columns:
            summary_rows.append(
                {
                    **{key: raw.get(key) for key in COMPARISON_KEYS},
                    "paired_interval_available": False,
                    "audit_reason": "trajectory_input_or_output_column_missing",
                }
            )
            continue
        selected = trajectories.loc[
            trajectories["condition"].astype(str).eq(condition)
            & trajectories["experiment_input_signal"].astype(str).eq(input_signal)
        ]
        discard = _discard_periods_for_comparison(response, raw)
        policy_terms: dict[str, dict[int, dict[str, Any]]] = {}
        for policy in ("mrp_reference", "canonical_feedback"):
            policy_frame = selected.loc[selected["policy"].astype(str).eq(policy)]
            policy_terms[policy] = _period_line_terms(
                policy_frame,
                input_column=input_column,
                output_column=output_column,
                frequency_bin=frequency_bin,
                discard_periods=discard,
            ) if not policy_frame.empty else {}
        periods = sorted(
            set(policy_terms["mrp_reference"]).intersection(policy_terms["canonical_feedback"])
        )
        mrp_list: list[dict[str, Any]] = []
        v2_list: list[dict[str, Any]] = []
        for period_index in periods:
            mrp = policy_terms["mrp_reference"][period_index]
            v2 = policy_terms["canonical_feedback"][period_index]
            mrp_list.append(mrp)
            v2_list.append(v2)
            mrp_h = mrp["h"]
            v2_h = v2["h"]
            ratio = (
                abs(v2_h) / abs(mrp_h)
                if mrp_h is not None and v2_h is not None and abs(mrp_h) > 1e-30
                else None
            )
            period_rows.append(
                {
                    **{key: raw.get(key) for key in COMPARISON_KEYS},
                    "period_index": period_index,
                    "mrp_frf_real": float(mrp_h.real) if mrp_h is not None else None,
                    "mrp_frf_imag": float(mrp_h.imag) if mrp_h is not None else None,
                    "mrp_frf_magnitude": float(abs(mrp_h)) if mrp_h is not None else None,
                    "v2_frf_real": float(v2_h.real) if v2_h is not None else None,
                    "v2_frf_imag": float(v2_h.imag) if v2_h is not None else None,
                    "v2_frf_magnitude": float(abs(v2_h)) if v2_h is not None else None,
                    "v2_over_mrp_magnitude_ratio": float(ratio) if ratio is not None else None,
                    "v2_minus_mrp_attenuation_db": (
                        20.0 * math.log10(max(float(ratio), 1e-300))
                        if ratio is not None
                        else None
                    ),
                    "paired_period_comparison_defined": ratio is not None,
                }
            )
        interval = exact_paired_resampling_interval(mrp_list, v2_list)
        defined_period_db = [
            row["v2_minus_mrp_attenuation_db"]
            for row in period_rows[-len(periods):]
            if row["v2_minus_mrp_attenuation_db"] is not None
        ] if periods else []
        summary_rows.append(
            {
                **{key: raw.get(key) for key in COMPARISON_KEYS},
                "source_reliable_comparison": _to_bool(raw.get("reliable_comparison")),
                "source_attenuation_db": _to_float(raw.get("v2_minus_mrp_attenuation_db")),
                "discarded_period_count": discard,
                "paired_period_count": len(periods),
                "defined_period_count": len(defined_period_db),
                "period_attenuation_db_min": min(defined_period_db) if defined_period_db else None,
                "period_attenuation_db_median": float(np.median(defined_period_db)) if defined_period_db else None,
                "period_attenuation_db_max": max(defined_period_db) if defined_period_db else None,
                "paired_interval_available": bool(interval.get("available")),
                "paired_interval_method": interval.get("method"),
                "paired_attenuation_db_q025": interval.get("attenuation_db_q025"),
                "paired_attenuation_db_median": interval.get("attenuation_db_median"),
                "paired_attenuation_db_q975": interval.get("attenuation_db_q975"),
                "zero_db_in_paired_interval": interval.get("zero_db_in_percentile_interval"),
                "defined_resample_mass_share": interval.get("defined_resample_mass_share"),
                "audit_reason": interval.get("reason", "exact_paired_interval_computed"),
                "dynamic_closed_loop_attenuation_proven": False,
            }
        )
    summaries = pd.DataFrame(summary_rows)
    periods_frame = pd.DataFrame(period_rows)
    if not summaries.empty:
        summaries = summaries.sort_values(list(COMPARISON_KEYS), kind="stable").reset_index(drop=True)
    if not periods_frame.empty:
        periods_frame = periods_frame.sort_values(
            [*COMPARISON_KEYS, "period_index"], kind="stable"
        ).reset_index(drop=True)
    return summaries, periods_frame


def audit_native_band_coherence(
    spectra: pd.DataFrame,
    bands: pd.DataFrame,
    *,
    coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
) -> pd.DataFrame:
    keys = ("source_run", "input_signal", "output_signal")
    _require_columns(
        spectra,
        (*keys, "period_days", "coherence"),
        "native spectra CSV",
    )
    _require_columns(
        bands,
        (*keys, "band", "period_min_days", "period_max_days"),
        "native bands CSV",
    )
    rows: list[dict[str, Any]] = []
    for raw in bands.to_dict(orient="records"):
        selected = spectra.copy()
        for key in keys:
            selected = selected.loc[selected[key].astype(str).eq(str(raw[key]))]
        lower = float(raw["period_min_days"])
        upper = float(raw["period_max_days"])
        selected = selected.loc[
            pd.to_numeric(selected["period_days"], errors="coerce").ge(lower)
            & pd.to_numeric(selected["period_days"], errors="coerce").lt(upper)
        ]
        coherence = pd.to_numeric(selected["coherence"], errors="coerce").dropna()
        rows.append(
            {
                **{key: raw[key] for key in keys},
                "band": raw["band"],
                "period_min_days": lower,
                "period_max_days": upper,
                "frequency_bin_count": int(len(coherence)),
                "median_coherence": float(coherence.median()) if not coherence.empty else None,
                "mean_coherence": float(coherence.mean()) if not coherence.empty else None,
                "maximum_coherence": float(coherence.max()) if not coherence.empty else None,
                "coherence_threshold": float(coherence_threshold),
                "coherence_threshold_pass_count": int(coherence.ge(coherence_threshold).sum()),
                "coherence_threshold_pass_share": (
                    float(coherence.ge(coherence_threshold).mean()) if not coherence.empty else None
                ),
                "power_amplification_db": _to_float(raw.get("power_amplification_db")),
                "causal_transfer_claimed": False,
                "interpretation": "observational_normalized_band_power_ratio_with_native_coherence",
            }
        )
    return pd.DataFrame(rows).sort_values([*keys, "period_min_days"], kind="stable").reset_index(drop=True)


def _count_records(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[column].fillna("missing").value_counts().sort_index().items()
    }


def _markdown_table(frame: pd.DataFrame, columns: Sequence[str], *, limit: int = 12) -> str:
    if frame.empty:
        return "_Aucune ligne._"
    selected = frame.loc[:, [column for column in columns if column in frame]].head(limit).copy()
    header = "| " + " | ".join(selected.columns) + " |"
    separator = "| " + " | ".join("---" for _ in selected.columns) + " |"
    lines = [header, separator]
    for row in selected.itertuples(index=False, name=None):
        lines.append(
            "| "
            + " | ".join(
                "" if pd.isna(value) else str(value).replace("|", "\\|") for value in row
            )
            + " |"
        )
    return "\n".join(lines)


def _build_markdown(
    source_root: Path,
    stability: pd.DataFrame,
    phase_slopes: pd.DataFrame,
    comparisons: pd.DataFrame,
    native_coherence: pd.DataFrame,
) -> str:
    stability_counts = _count_records(stability, "audit_classification")
    phase_counts = _count_records(phase_slopes, "phase_slope_classification")
    reliable = comparisons.loc[
        comparisons.get("source_reliable_comparison", pd.Series(False, index=comparisons.index)).map(_to_bool)
    ] if not comparisons.empty else comparisons
    return f"""# Audit posthoc de l'étude fréquentielle canonique

Paquet scientifique source (lecture seule) : `{source_root}`.

## Verdict

Cet audit ne recalcule pas la simulation. Il recalcule en priorité les RMS totales (composante
continue incluse), les moyennes de période et les états terminaux depuis les trajectoires. Le RMS
historique n'est utilisé qu'en fallback explicite. Il distingue absence de réponse, répétabilité
non nulle, transitoire avec pic intérieur et croissance monotone. Il requalifie les pentes issues de réponses
hybrides et isole aussi les pentes compatibles au seul niveau de l'amplitude testée lorsque
l'active-set reste non vérifié ; aucune de ces catégories n'est présentée comme délai local ou
délai de transport. Les intervalles
V2/MRP sont des percentiles descriptifs d'un bootstrap apparié exact des périodes disponibles ;
ils ne constituent pas une preuve industrielle ni une correction de multiplicité.

## Stabilité / répétabilité

{json.dumps(stability_counts, ensure_ascii=False, sort_keys=True)}

## Pentes de phase

{json.dumps(phase_counts, ensure_ascii=False, sort_keys=True)}

{_markdown_table(phase_slopes, ("condition", "policy", "input_signal", "output_signal", "phase_slope_equivalent_days", "phase_slope_classification"))}

## Comparaisons V2 / MRP marquées fiables dans la source

{_markdown_table(reliable, ("condition", "input_signal", "output_signal", "frequency_bin", "source_attenuation_db", "paired_attenuation_db_q025", "paired_attenuation_db_median", "paired_attenuation_db_q975", "zero_db_in_paired_interval"))}

## Cohérence native par bande

{_markdown_table(native_coherence.sort_values("median_coherence", ascending=False), ("source_run", "input_signal", "output_signal", "band", "median_coherence", "coherence_threshold_pass_share", "power_amplification_db"))}

## Limites de preuve

- Une trace identique du régime superviseur ne démontre pas à elle seule une dérivée petit-signal du plant lotifié.
- Une réponse nulle et répétable n'est pas une preuve de stabilité.
- Une pente de phase hybride peut refléter un calendrier de commutation plutôt qu'un transport.
- Les ratios spectraux natifs sont observationnels et doivent être accompagnés de leur cohérence.
- `dynamic_closed_loop_attenuation_proven` reste faux dans cet audit posthoc.
"""


def run_audit(
    artifact_dir: str | Path,
    output_dir: str | Path,
    *,
    coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
    no_response_floor: float = DEFAULT_NO_RESPONSE_FLOOR,
    growth_tolerance: float = DEFAULT_GROWTH_TOLERANCE,
) -> dict[str, Any]:
    """Read one artifact package and write a separate strict audit bundle."""

    source_root = Path(artifact_dir).resolve()
    destination = Path(output_dir).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Artifact directory does not exist: {source_root}")
    if destination == source_root or source_root in destination.parents:
        raise FrequencyAuditError("output_dir must be outside the source artifact package.")
    source_paths = {name: source_root / filename for name, filename in SOURCE_FILES.items()}
    missing = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing audit source files: " + ", ".join(missing))
    frames = {name: pd.read_csv(path) for name, path in source_paths.items()}

    stability = audit_stability(
        frames["stability"],
        trajectories=frames["trajectories"],
        response=frames["response"],
        no_response_floor=no_response_floor,
        growth_tolerance=growth_tolerance,
    )
    phase_slopes = audit_phase_slopes(frames["delays"], frames["response"])
    comparisons, paired_periods = audit_comparisons(
        frames["comparison"], frames["trajectories"], frames["response"]
    )
    native_coherence = audit_native_band_coherence(
        frames["native_spectra"],
        frames["native_bands"],
        coherence_threshold=coherence_threshold,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_artifact_dir": str(source_root),
        "source_files": {
            name: {
                "filename": path.name,
                "size_bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
            for name, path in source_paths.items()
        },
        "thresholds": {
            "native_coherence_threshold": float(coherence_threshold),
            "no_measurable_response_floor": float(no_response_floor),
            "growth_tolerance": float(growth_tolerance),
        },
        "evidence_counts": {
            "stability_rows": int(len(stability)),
            "stability_classifications": _count_records(stability, "audit_classification"),
            "stability_metric_sources": _count_records(
                stability, "classification_metric_source"
            ),
            "trajectory_recalculated_stability_rows": int(
                stability["trajectory_recalculated"].map(_to_bool).sum()
            ),
            "legacy_stability_fallback_rows": int(
                (~stability["trajectory_recalculated"].map(_to_bool)).sum()
            ),
            "phase_slope_rows": int(len(phase_slopes)),
            "phase_slope_classifications": _count_records(
                phase_slopes, "phase_slope_classification"
            ),
            "comparison_rows": int(len(comparisons)),
            "paired_period_rows": int(len(paired_periods)),
            "native_band_coherence_rows": int(len(native_coherence)),
        },
        "claims": {
            "source_package_modified": False,
            "local_delay_claimed": False,
            "transport_delay_claimed": False,
            "local_stability_proven": False,
            "global_stability_proven": False,
            "dynamic_closed_loop_attenuation_proven": False,
            "native_spectra_causal": False,
        },
        "stability_audit": _records(stability),
        "phase_slope_audit": _records(phase_slopes),
        "comparison_audit": _records(comparisons),
        "paired_period_audit": _records(paired_periods),
        "native_band_coherence_audit": _records(native_coherence),
    }
    payload = _json_safe(payload)
    destination.mkdir(parents=True, exist_ok=True)
    output_paths = {name: destination / filename for name, filename in AUDIT_FILES.items()}
    stability.to_csv(output_paths["stability"], index=False)
    phase_slopes.to_csv(output_paths["phase_slopes"], index=False)
    comparisons.to_csv(output_paths["comparisons"], index=False)
    paired_periods.to_csv(output_paths["paired_periods"], index=False)
    native_coherence.to_csv(output_paths["native_band_coherence"], index=False)
    output_paths["markdown"].write_text(
        _build_markdown(source_root, stability, phase_slopes, comparisons, native_coherence),
        encoding="utf-8",
    )
    output_paths["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": destination,
        "paths": output_paths,
        "payload": payload,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit an existing canonical frequency-study artifact package without modifying it."
    )
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--coherence-threshold", type=float, default=DEFAULT_COHERENCE_THRESHOLD
    )
    parser.add_argument(
        "--no-response-floor", type=float, default=DEFAULT_NO_RESPONSE_FLOOR
    )
    parser.add_argument(
        "--growth-tolerance", type=float, default=DEFAULT_GROWTH_TOLERANCE
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_audit(
        args.artifact_dir,
        args.output_dir,
        coherence_threshold=args.coherence_threshold,
        no_response_floor=args.no_response_floor,
        growth_tolerance=args.growth_tolerance,
    )
    print(result["paths"]["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
