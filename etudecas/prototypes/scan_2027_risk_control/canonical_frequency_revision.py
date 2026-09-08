#!/usr/bin/env python3
"""Build a traceable posthoc revision of a canonical frequency package.

The source package is treated as immutable.  This command copies its useful
tables into a sibling staging directory, changes only evidence semantics and
posthoc diagnostics, regenerates the report and figures, verifies hashes, and
then promotes the staging directory in one rename.  It never invokes the
simulator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_audit import (  # noqa: E402
    DEFAULT_GROWTH_TOLERANCE,
    DEFAULT_NO_RESPONSE_FLOOR,
    audit_comparisons,
    audit_stability,
)
from etudecas.prototypes.scan_2027_risk_control.canonical_frequency_study import (  # noqa: E402
    _annotate_delay_scope,
)


SCHEMA_VERSION = "scan.canonical_frequency_posthoc_revision.v1"

TABLE_FILES = {
    "native_spectra": "canonical_frequency_native_spectra.csv",
    "native_bands": "canonical_frequency_native_bands.csv",
    "response": "canonical_frequency_response.csv",
    "comparison": "canonical_frequency_closed_loop_comparison.csv",
    "resonances": "canonical_frequency_resonances.csv",
    "stability": "canonical_frequency_stability.csv",
    "delays": "canonical_frequency_delays.csv",
    "residual": "canonical_frequency_nonlinearity.csv",
    "regime_occupancy": "canonical_frequency_regime_occupancy.csv",
    "excitation_audit": "canonical_frequency_excitation_audit.csv",
    "trajectories": "canonical_frequency_trajectories.csv",
}

FIGURE_FILES = (
    "canonical_frequency_excitation_response.png",
    "canonical_frequency_bode_frf.png",
    "canonical_frequency_coherence.png",
    "canonical_frequency_resonances.png",
    "canonical_frequency_time_frequency.png",
    "canonical_frequency_stability.png",
)

SOURCE_METADATA_FILES = (
    "canonical_frequency_manifest.json",
    "canonical_frequency_protocol.json",
)

LEDGER_FILE = "canonical_frequency_revision_ledger.csv"
REVISION_FILE = "canonical_frequency_revision.json"
MANIFEST_FILE = "canonical_frequency_manifest.json"
PROTOCOL_FILE = "canonical_frequency_protocol.json"
REPORT_FILE = "canonical_frequency_report.md"

GROUP_KEYS = ("study_kind", "condition", "policy", "input_signal", "output_signal")
COMPARISON_KEYS = ("condition", "input_signal", "output_signal", "frequency_bin")

RESPONSE_NUMERIC_ESTIMATE_COLUMNS = (
    "frequency_bin",
    "frequency_cycles_per_day",
    "angular_frequency_rad_per_day",
    "period_days",
    "repetition_count",
    "input_line_rms",
    "output_line_rms",
    "frf_real",
    "frf_imag",
    "magnitude",
    "magnitude_db",
    "phase_deg",
    "coherence",
    "magnitude_period_resampling_q025",
    "magnitude_period_resampling_q975",
    "phase_period_resampling_q025_deg",
    "phase_period_resampling_q975_deg",
    "response_scale",
    "elasticity_magnitude",
    "elasticity_db",
)

_STABILITY_PATTERN = {
    "no_measurable_response": "no_measurable_response",
    "nonzero_repeatable": "nonzero_repeatable_response",
    "monotonic_growth": "monotonic_growth_detected",
    "interior_peak": "interior_period_peak_transient_or_delay",
    "other": "other_nonstationary_response",
}


class FrequencyRevisionError(RuntimeError):
    """Raised when an existing package cannot be revised without ambiguity."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            _json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _optional_bool_series(values: pd.Series) -> pd.Series:
    def parse(value: Any) -> Any:
        if value is None or pd.isna(value):
            return pd.NA
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
        return pd.NA

    return values.map(parse).astype("boolean")


def _csv_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "True" if bool(value) else "False"
    return str(value)


def _write_frame_preserving_source_cells(
    source_path: Path,
    output_path: Path,
    frame: pd.DataFrame,
    *,
    changed_source_columns: Iterable[str],
) -> None:
    """Write an augmented CSV while retaining untouched source cell strings.

    Pandas' otherwise-correct shortest float formatting can move a handful of
    very small or very large estimates by one ULP after another CSV parse.  A
    semantic-only revision should not do that, so original cells are copied as
    strings and only declared semantic columns are replaced.
    """

    with source_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows:
        raise FrequencyRevisionError(f"Source CSV is empty: {source_path}")
    source_header = rows[0]
    source_rows = rows[1:]
    if len(source_rows) != len(frame):
        raise FrequencyRevisionError(
            f"CSV row count changed for {source_path.name}: "
            f"{len(source_rows)} != {len(frame)}"
        )
    if any(len(row) != len(source_header) for row in source_rows):
        raise FrequencyRevisionError(f"Source CSV has ragged rows: {source_path}")
    new_columns = [column for column in frame.columns if column not in source_header]
    output_header = [*source_header, *new_columns]
    changed = set(changed_source_columns)
    source_indexes = {field: index for index, field in enumerate(source_header)}
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(output_header)
        for row_index, source_row in enumerate(source_rows):
            revised_row = frame.iloc[row_index]
            output_row: list[str] = []
            for field in output_header:
                if field in source_indexes and field not in changed:
                    output_row.append(source_row[source_indexes[field]])
                else:
                    output_row.append(_csv_value(revised_row[field]))
            writer.writerow(output_row)


def _bool_series(frame: pd.DataFrame, field: str) -> pd.Series:
    if field not in frame:
        return pd.Series(False, index=frame.index, dtype=bool)
    return _optional_bool_series(frame[field]).fillna(False).astype(bool)


def _require_columns(frame: pd.DataFrame, fields: Iterable[str], label: str) -> None:
    missing = set(fields) - set(frame.columns)
    if missing:
        raise FrequencyRevisionError(
            f"{label} lacks required columns: {', '.join(sorted(missing))}"
        )


def requalify_response(response: pd.DataFrame) -> pd.DataFrame:
    """Downgrade finite-amplitude lines without changing numerical estimates."""

    _require_columns(response, (*GROUP_KEYS, "valid_bin"), "response CSV")
    source = response.copy(deep=True)
    revised = source.copy(deep=True)

    if "source_small_signal_local_claim" not in revised:
        revised["source_small_signal_local_claim"] = revised.get(
            "small_signal_local_claim", pd.Series(False, index=revised.index)
        )
    if "source_response_regime_scope" not in revised:
        revised["source_response_regime_scope"] = revised.get(
            "response_regime_scope", pd.Series(pd.NA, index=revised.index)
        )

    if "tested_amplitude_regime_trace_compatible" in revised:
        compatible = _optional_bool_series(
            revised["tested_amplitude_regime_trace_compatible"]
        )
    elif "regime_compatible_for_local_claim" in revised:
        compatible = _optional_bool_series(
            revised["regime_compatible_for_local_claim"]
        )
    else:
        scope = revised.get(
            "response_regime_scope", pd.Series("", index=revised.index)
        ).fillna("").astype(str)
        compatible = scope.map(
            lambda value: (
                False
                if "hybrid" in value
                else True
                if value
                in {
                    "local_fixed_supervisory_regime_trace",
                    "local_operating_condition_without_supervisory_regime",
                    "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified",
                    "tested_amplitude_no_supervisory_regime_active_set_unverified",
                }
                else pd.NA
            )
        ).astype("boolean")

    open_loop = revised["study_kind"].astype(str).eq(
        "designed_open_loop_actuator_probe"
    )
    compatible.loc[open_loop] = True
    revised["tested_amplitude_regime_trace_compatible"] = compatible
    revised["small_signal_local_claim"] = False
    revised["amplitude_sweep_verified"] = False
    revised["active_set_invariance_verified"] = False
    revised["zero_amplitude_derivative_identified"] = False
    revised["tested_amplitude_harmonic_response"] = _bool_series(
        revised, "valid_bin"
    )
    revised["locality_evidence_scope"] = (
        "finite_test_amplitude_only_active_set_unverified"
    )

    revised_scope = pd.Series(
        "tested_amplitude_regime_compatibility_unverified_active_set_unverified",
        index=revised.index,
        dtype=object,
    )
    revised_scope.loc[compatible.eq(True).fillna(False)] = (  # noqa: E712
        "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified"
    )
    revised_scope.loc[compatible.eq(False).fillna(False)] = (  # noqa: E712
        "tested_amplitude_hybrid_regime_switching_active_set_unverified"
    )
    revised_scope.loc[open_loop] = (
        "tested_amplitude_no_supervisory_regime_active_set_unverified"
    )
    revised["response_regime_scope"] = revised_scope

    checked_columns = [
        field for field in RESPONSE_NUMERIC_ESTIMATE_COLUMNS if field in source
    ]
    for field in checked_columns:
        if not source[field].equals(revised[field]):
            raise FrequencyRevisionError(
                f"Posthoc response revision changed numerical estimate {field}."
            )
    revised.attrs["verified_numeric_estimate_columns"] = checked_columns
    return revised


def revise_delays(response: pd.DataFrame, delays: pd.DataFrame) -> pd.DataFrame:
    """Move unsupported delays to descriptive phase slopes using the study gate."""

    source = delays.copy(deep=True)
    working = source.copy(deep=True)
    if "source_delay_days" not in working:
        working["source_delay_days"] = working.get(
            "delay_days", pd.Series(np.nan, index=working.index)
        )
    if "source_descriptive_phase_slope_days" not in working:
        working["source_descriptive_phase_slope_days"] = working.get(
            "descriptive_phase_slope_days", pd.Series(np.nan, index=working.index)
        )
    source_equivalent = pd.to_numeric(
        working.get("delay_days", pd.Series(np.nan, index=working.index)),
        errors="coerce",
    )
    if "descriptive_phase_slope_days" in working:
        source_equivalent = source_equivalent.combine_first(
            pd.to_numeric(
                working["descriptive_phase_slope_days"], errors="coerce"
            )
        )
    working["delay_days"] = source_equivalent
    revised = _annotate_delay_scope(response, working)
    revised["source_delay_days"] = working["source_delay_days"].to_numpy()
    revised["source_descriptive_phase_slope_days"] = working[
        "source_descriptive_phase_slope_days"
    ].to_numpy()
    return revised


def recalculate_stability(
    stability: pd.DataFrame,
    trajectories: pd.DataFrame,
    response: pd.DataFrame,
    *,
    no_response_floor: float = DEFAULT_NO_RESPONSE_FLOOR,
    growth_tolerance: float = DEFAULT_GROWTH_TOLERANCE,
) -> pd.DataFrame:
    """Recompute repeated-period diagnostics from total RMS, including DC."""

    audited = audit_stability(
        stability,
        trajectories=trajectories,
        response=response,
        no_response_floor=no_response_floor,
        growth_tolerance=growth_tolerance,
    )
    audited["response_pattern"] = audited["audit_classification"].map(
        _STABILITY_PATTERN
    )
    audited["status"] = audited["response_pattern"]
    audited["bounded_repeated_response"] = ~audited["growth_detected"].astype(bool)
    audited["local_stability_claimed"] = False
    audited["global_stability_claimed"] = False

    # Keep non-obsolete source metadata such as the classical-margin contract.
    stale = {
        "status",
        "period_count",
        "first_period_rms",
        "last_period_rms",
        "last_to_first_rms_ratio",
        "max_adjacent_rms_ratio",
        "max_to_first_rms_ratio",
        "max_to_min_rms_ratio",
        "max_to_min_rms_ratio_unbounded",
        "period_rms_json",
        "bounded_repeated_response",
        "repeatable_periodic_response",
        "local_stability_claimed",
        "global_stability_claimed",
    }
    metadata_columns = [
        column
        for column in stability.columns
        if column not in GROUP_KEYS
        and column not in stale
        and column not in audited.columns
    ]
    if metadata_columns:
        metadata = stability.loc[:, [*GROUP_KEYS, *metadata_columns]].copy()
        if metadata.duplicated(list(GROUP_KEYS)).any():
            raise FrequencyRevisionError("Stability source keys are not unique.")
        audited = audited.merge(
            metadata,
            on=list(GROUP_KEYS),
            how="left",
            validate="one_to_one",
            sort=False,
        )
    return audited


def enrich_comparisons(
    comparison: pd.DataFrame,
    trajectories: pd.DataFrame,
    response: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach exact paired-period posthoc intervals to source comparisons."""

    audited, paired_periods = audit_comparisons(
        comparison, trajectories, response
    )
    audit_fields = [field for field in audited.columns if field not in COMPARISON_KEYS]
    base = comparison.drop(
        columns=[field for field in audit_fields if field in comparison.columns]
    )
    enriched = base.merge(
        audited,
        on=list(COMPARISON_KEYS),
        how="left",
        validate="one_to_one",
        sort=False,
    )
    enriched["dynamic_closed_loop_attenuation_proven"] = False
    return enriched, paired_periods


def _read_source(source_root: Path) -> tuple[dict[str, Path], dict[str, pd.DataFrame]]:
    candidates = {
        name: source_root / filename for name, filename in TABLE_FILES.items()
    }
    optional_for_designed_only = {"native_spectra", "native_bands"}
    missing = [
        str(path)
        for name, path in candidates.items()
        if name not in optional_for_designed_only and not path.is_file()
    ]
    manifest_path = source_root / MANIFEST_FILE
    if not manifest_path.is_file():
        missing.append(str(manifest_path))
    if missing:
        raise FileNotFoundError("Missing frequency revision inputs: " + ", ".join(missing))
    paths = {name: path for name, path in candidates.items() if path.is_file()}
    frames = {
        name: pd.read_csv(path) if path.is_file() else pd.DataFrame()
        for name, path in candidates.items()
    }
    return paths, frames


def _normalized_reporting_config(
    source_manifest: Mapping[str, Any], trajectories: pd.DataFrame
) -> dict[str, Any]:
    sampling = source_manifest.get("sampling", {})
    if not isinstance(sampling, Mapping):
        sampling = {}
    configured_period_days = sampling.get("designed_period_days")
    period_days = int(configured_period_days or 196)
    if (
        not configured_period_days
        and "period_index" in trajectories
        and "day" in trajectories
        and not trajectories.empty
    ):
        # A trajectory contains one row per signal/policy/condition/day.  Raw
        # group sizes therefore multiply the physical period by the number of
        # series.  Count distinct sampled days instead, and never override the
        # authoritative period registered in the source manifest.
        sampled_days = trajectories[["period_index", "day"]].dropna().drop_duplicates()
        counts = sampled_days.groupby("period_index", dropna=True)["day"].nunique()
        if not counts.empty:
            period_days = int(counts.mode().iloc[0])
    configured_measured_periods = sampling.get("measured_periods")
    measured_periods = int(configured_measured_periods or 4)
    if (
        not configured_measured_periods
        and "period_index" in trajectories
        and not trajectories.empty
    ):
        period_indexes = pd.to_numeric(
            trajectories["period_index"], errors="coerce"
        ).dropna()
        if not period_indexes.empty:
            measured_periods = int(period_indexes.nunique())
    return {
        "coherence_threshold": float(
            source_manifest.get("coherence_threshold")
            or source_manifest.get("designed_excitation", {}).get(
                "coherence_threshold", 0.8
            )
        ),
        "measured_periods": measured_periods,
        "period_days": period_days,
        "warmup_days": int(sampling.get("warmup_days") or 0),
    }


def _snapshot_sources(
    source_root: Path,
    stage: Path,
    source_paths: Mapping[str, Path],
) -> tuple[Path, list[dict[str, Any]]]:
    snapshot_root = stage / "provenance" / "source_artifact"
    snapshot_root.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    paths: list[tuple[str, Path]] = [
        (f"table:{name}", path) for name, path in source_paths.items()
    ]
    for filename in SOURCE_METADATA_FILES:
        path = source_root / filename
        if path.is_file():
            paths.append(("source_metadata", path))
    for role, path in paths:
        destination = snapshot_root / path.name
        shutil.copy2(path, destination)
        entries.append(
            {
                "role": role,
                "source_path": str(path),
                "snapshot_relative_path": destination.relative_to(stage).as_posix(),
                "size_bytes": int(destination.stat().st_size),
                "sha256": _sha256(destination),
            }
        )

    code_root = stage / "provenance" / "source_code"
    code_root.mkdir(parents=True, exist_ok=False)
    module_root = Path(__file__).resolve().parent
    for filename in (
        "canonical_frequency_revision.py",
        "canonical_frequency_audit.py",
        "canonical_frequency_study.py",
        "frequency_analysis.py",
        "frequency_reporting.py",
    ):
        path = module_root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing revision source code: {path}")
        destination = code_root / filename
        shutil.copy2(path, destination)
        entries.append(
            {
                "role": "executed_or_imported_source_code",
                "source_path": str(path),
                "snapshot_relative_path": destination.relative_to(stage).as_posix(),
                "size_bytes": int(destination.stat().st_size),
                "sha256": _sha256(destination),
            }
        )
    manifest_path = stage / "provenance" / "source_snapshot_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": f"{SCHEMA_VERSION}.source_snapshot.v1",
            "entry_count": len(entries),
            "entries": entries,
        },
    )
    return manifest_path, entries


def _count_values(frame: pd.DataFrame, field: str) -> dict[str, int]:
    if frame.empty or field not in frame:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[field]
        .fillna("missing")
        .value_counts()
        .sort_index()
        .items()
    }


def _build_manifest(
    source_manifest: Mapping[str, Any],
    *,
    generated_at: str,
    source_root: Path,
    source_manifest_sha256: str,
    response: pd.DataFrame,
    delays: pd.DataFrame,
    stability: pd.DataFrame,
    comparison: pd.DataFrame,
    snapshot_manifest: Path,
    stage: Path,
) -> dict[str, Any]:
    payload = deepcopy(dict(source_manifest))
    for stale_field in (
        "output_sha256",
        "artifact_ledger",
        "dashboard_artifact_ledger",
        "reporting_semantic_revision",
    ):
        payload.pop(stale_field, None)
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": generated_at,
            "status": "complete_posthoc_revision_without_simulation_rerun",
            "study_scope": (
                "native_observational_plus_finite_test_amplitude_designed_"
                "frequency_diagnostics"
            ),
            "scientific_claim": {
                "statement": (
                    "Designed harmonic responses are empirical at the tested finite "
                    "amplitude. Supervisory-regime compatibility is reported, while "
                    "zero-amplitude locality and active-set invariance remain unverified. "
                    "Native spectra are observational; no local/global stability or "
                    "dynamic closed-loop attenuation proof is claimed."
                ),
                "scope": "finite_test_amplitude_active_set_unverified",
                "small_signal_local_gate": "not_satisfied_no_amplitude_sweep_or_active_set_audit",
                "global_stability_claimed": False,
            },
        }
    )
    claims = dict(payload.get("claims", {}))
    claims.update(
        {
            "small_signal_local_subset_identified": False,
            "zero_amplitude_local_derivative_identified": False,
            "active_set_invariance_verified": False,
            "local_stability_proven": False,
            "global_stability_claimed": False,
            "dynamic_closed_loop_frequency_attenuation": False,
            "industrial_validation_claimed": False,
        }
    )
    payload["claims"] = claims
    evidence = dict(payload.get("evidence_counts", {}))
    valid = _bool_series(response, "valid_bin")
    compatible = _bool_series(response, "tested_amplitude_regime_trace_compatible")
    evidence.update(
        {
            "designed_line_response_rows": int(len(response)),
            "numerically_valid_designed_rows": int(valid.sum()),
            "tested_amplitude_regime_compatible_valid_rows": int(
                (valid & compatible).sum()
            ),
            "tested_amplitude_hybrid_or_unverified_valid_rows": int(
                (valid & ~compatible).sum()
            ),
            "verified_zero_amplitude_local_rows": 0,
            "identified_local_delay_rows": int(
                _bool_series(delays, "local_phase_slope_identified").sum()
            ),
            "descriptive_phase_slope_rows": int(
                pd.to_numeric(
                    delays.get("descriptive_phase_slope_days"), errors="coerce"
                ).notna().sum()
            ),
            "stability_diagnostic_rows": int(len(stability)),
            "stability_response_patterns": _count_values(
                stability, "response_pattern"
            ),
            "closed_loop_comparison_rows": int(len(comparison)),
            "paired_interval_available_rows": int(
                _bool_series(comparison, "paired_interval_available").sum()
            ),
        }
    )
    payload["evidence_counts"] = evidence
    limitations = list(payload.get("limitations", []))
    for statement in (
        "Single finite excitation amplitude: zero-amplitude locality is not identified.",
        "Plant/controller active-set invariance was not audited posthoc.",
        "Phase slopes outside a verified local scope are descriptive, not transport delays.",
        "DC-aware repeated-period diagnostics are not a local or global stability proof.",
    ):
        if statement not in limitations:
            limitations.append(statement)
    payload["limitations"] = limitations
    payload["posthoc_revision"] = {
        "source_artifact_dir": str(source_root),
        "source_manifest_sha256": source_manifest_sha256,
        "source_snapshot_manifest_relative_path": snapshot_manifest.relative_to(
            stage
        ).as_posix(),
        "source_snapshot_manifest_sha256": _sha256(snapshot_manifest),
        "simulation_rerun": False,
        "response_numeric_estimates_unchanged": True,
        "verified_response_numeric_columns": list(
            response.attrs.get("verified_numeric_estimate_columns", [])
        ),
        "semantic_requalification": (
            "finite_test_amplitude_supervisory_regime_trace_only_"
            "active_set_unverified"
        ),
    }
    payload["reporting"] = {
        "report_path": REPORT_FILE,
        "plot_status": "written",
        "plot_paths": list(FIGURE_FILES),
    }
    return payload


def _write_ledger(stage: Path) -> tuple[Path, list[dict[str, Any]]]:
    excluded = {LEDGER_FILE, REVISION_FILE}
    entries: list[dict[str, Any]] = []
    for path in sorted(
        (candidate for candidate in stage.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(stage).as_posix(),
    ):
        relative = path.relative_to(stage).as_posix()
        if relative in excluded:
            continue
        entries.append(
            {
                "relative_path": relative,
                "size_bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        )
    ledger = stage / LEDGER_FILE
    with ledger.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("relative_path", "size_bytes", "sha256"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(entries)
    return ledger, entries


def _verify_ledger(stage: Path, entries: Sequence[Mapping[str, Any]]) -> None:
    for entry in entries:
        path = stage / str(entry["relative_path"])
        if not path.is_file():
            raise FrequencyRevisionError(f"Ledger path is missing: {path}")
        if int(path.stat().st_size) != int(entry["size_bytes"]):
            raise FrequencyRevisionError(f"Ledger size mismatch: {path}")
        if _sha256(path) != str(entry["sha256"]):
            raise FrequencyRevisionError(f"Ledger SHA256 mismatch: {path}")


def run_revision(
    artifact_dir: str | Path,
    output_dir: str | Path,
    *,
    no_response_floor: float = DEFAULT_NO_RESPONSE_FLOOR,
    growth_tolerance: float = DEFAULT_GROWTH_TOLERANCE,
) -> dict[str, Any]:
    """Create and atomically promote a posthoc-only frequency revision."""

    source_root = Path(artifact_dir).resolve()
    destination = Path(output_dir).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Artifact directory does not exist: {source_root}")
    if destination.exists():
        raise FileExistsError(f"Output directory already exists: {destination}")
    if destination == source_root or source_root in destination.parents:
        raise FrequencyRevisionError(
            "output_dir must be outside the immutable source package."
        )
    source_paths, frames = _read_source(source_root)
    source_manifest_path = source_root / MANIFEST_FILE
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_hashes_before = {
        str(path): _sha256(path)
        for path in [*source_paths.values(), source_manifest_path]
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=str(destination.parent)
        )
    )
    promoted = False
    try:
        for path in source_paths.values():
            shutil.copy2(path, stage / path.name)
        snapshot_manifest, snapshot_entries = _snapshot_sources(
            source_root, stage, source_paths
        )

        response = requalify_response(frames["response"])
        delays = revise_delays(response, frames["delays"])
        stability = recalculate_stability(
            frames["stability"],
            frames["trajectories"],
            response,
            no_response_floor=no_response_floor,
            growth_tolerance=growth_tolerance,
        )
        comparison, paired_periods = enrich_comparisons(
            frames["comparison"], frames["trajectories"], response
        )
        _write_frame_preserving_source_cells(
            source_paths["response"],
            stage / TABLE_FILES["response"],
            response,
            changed_source_columns={
                "small_signal_local_claim",
                "response_regime_scope",
                "tested_amplitude_regime_trace_compatible",
                "amplitude_sweep_verified",
                "active_set_invariance_verified",
                "zero_amplitude_derivative_identified",
                "tested_amplitude_harmonic_response",
                "locality_evidence_scope",
            },
        )
        _write_frame_preserving_source_cells(
            source_paths["delays"],
            stage / TABLE_FILES["delays"],
            delays,
            changed_source_columns={
                "status",
                "delay_days",
                "supporting_valid_line_count",
                "supporting_local_line_count",
                "supporting_scope_verified_line_count",
                "phase_slope_scope",
                "local_phase_slope_identified",
                "zero_amplitude_local_delay_claimed",
                "active_set_invariance_verified",
                "amplitude_sweep_verified",
                "descriptive_phase_slope_days",
                "response_regime_scope",
            },
        )
        stability.to_csv(stage / TABLE_FILES["stability"], index=False)
        _write_frame_preserving_source_cells(
            source_paths["comparison"],
            stage / TABLE_FILES["comparison"],
            comparison,
            changed_source_columns={"dynamic_closed_loop_attenuation_proven"},
        )
        paired_period_path = stage / "canonical_frequency_revision_paired_periods.csv"
        paired_periods.to_csv(paired_period_path, index=False)

        from etudecas.prototypes.scan_2027_risk_control.frequency_reporting import (
            write_frequency_figures,
            write_frequency_report,
        )

        normalized_config = _normalized_reporting_config(
            source_manifest, frames["trajectories"]
        )
        controller_schema_version = str(
            source_manifest.get("controller", {}).get("schema_version") or ""
        ) or None
        report_path = write_frequency_report(
            stage,
            native_spectra=frames["native_spectra"],
            native_bands=frames["native_bands"],
            response=response,
            closed_loop_comparison=comparison,
            resonances=frames["resonances"],
            stability=stability,
            residual=frames["residual"],
            regime_occupancy=frames["regime_occupancy"],
            normalized_config=normalized_config,
            delays=delays,
            controller_schema_version=controller_schema_version,
        )
        figure_paths = write_frequency_figures(
            stage,
            native_spectra=frames["native_spectra"],
            native_bands=frames["native_bands"],
            response=response,
            closed_loop_comparison=comparison,
            resonances=frames["resonances"],
            stability=stability,
            trajectories=frames["trajectories"],
            controller_schema_version=controller_schema_version,
        )
        expected_figures = {stage / filename for filename in FIGURE_FILES}
        if set(map(Path, figure_paths)) != expected_figures:
            raise FrequencyRevisionError(
                "Reporting did not return the six expected frequency figures."
            )
        if Path(report_path) != stage / REPORT_FILE or not Path(report_path).is_file():
            raise FrequencyRevisionError("Reporting did not write the expected report.")
        missing_figures = [str(path) for path in expected_figures if not path.is_file()]
        if missing_figures:
            raise FrequencyRevisionError(
                "Reporting omitted figures: " + ", ".join(missing_figures)
            )

        generated_at = datetime.now(timezone.utc).isoformat()
        manifest = _build_manifest(
            source_manifest,
            generated_at=generated_at,
            source_root=source_root,
            source_manifest_sha256=_sha256(source_manifest_path),
            response=response,
            delays=delays,
            stability=stability,
            comparison=comparison,
            snapshot_manifest=snapshot_manifest,
            stage=stage,
        )
        _write_json(stage / MANIFEST_FILE, manifest)
        _write_json(stage / PROTOCOL_FILE, manifest)
        ledger, ledger_entries = _write_ledger(stage)
        _verify_ledger(stage, ledger_entries)

        source_hashes_after = {
            str(path): _sha256(path)
            for path in [*source_paths.values(), source_manifest_path]
        }
        if source_hashes_after != source_hashes_before:
            raise FrequencyRevisionError(
                "The immutable source package changed during posthoc revision."
            )
        revision = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
            "generated_at_utc": generated_at,
            "source_artifact_dir": str(source_root),
            "output_artifact_dir": str(destination),
            "simulation_rerun": False,
            "source_package_modified": False,
            "response_numeric_estimates_unchanged": True,
            "verified_response_numeric_columns": list(
                response.attrs.get("verified_numeric_estimate_columns", [])
            ),
            "semantic_changes": {
                "source_small_signal_claim_preserved": True,
                "small_signal_local_claim_forced_false": True,
                "finite_test_amplitude_scope_recorded": True,
                "active_set_invariance_verified": False,
                "delays_gated_with_annotate_delay_scope": True,
                "stability_recalculated_from_trajectory_total_rms": True,
                "comparison_enriched_with_exact_paired_period_audit": True,
            },
            "counts": {
                "response_rows": int(len(response)),
                "delay_rows": int(len(delays)),
                "local_delay_rows": int(
                    _bool_series(delays, "local_phase_slope_identified").sum()
                ),
                "stability_rows": int(len(stability)),
                "stability_response_patterns": _count_values(
                    stability, "response_pattern"
                ),
                "comparison_rows": int(len(comparison)),
                "paired_period_rows": int(len(paired_periods)),
            },
            "source_snapshot": {
                "manifest_relative_path": snapshot_manifest.relative_to(stage).as_posix(),
                "manifest_sha256": _sha256(snapshot_manifest),
                "entry_count": len(snapshot_entries),
            },
            "report": REPORT_FILE,
            "figures": list(FIGURE_FILES),
            "ledger": {
                "relative_path": LEDGER_FILE,
                "sha256": _sha256(ledger),
                "entry_count": len(ledger_entries),
                "excluded_self_referential_files": [LEDGER_FILE, REVISION_FILE],
            },
            "promotion": "single_same_filesystem_directory_rename",
        }
        _write_json(stage / REVISION_FILE, revision)

        if destination.exists():
            raise FileExistsError(
                f"Output directory appeared before promotion: {destination}"
            )
        os.rename(stage, destination)
        promoted = True
        return {
            "output_dir": destination,
            "manifest_path": destination / MANIFEST_FILE,
            "revision_path": destination / REVISION_FILE,
            "ledger_path": destination / LEDGER_FILE,
            "report_path": destination / REPORT_FILE,
            "figure_paths": [destination / filename for filename in FIGURE_FILES],
        }
    finally:
        if not promoted and stage.exists():
            shutil.rmtree(stage)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a new posthoc semantic/scientific revision of an existing "
            "canonical frequency package without rerunning the simulator."
        )
    )
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--no-response-floor", type=float, default=DEFAULT_NO_RESPONSE_FLOOR
    )
    parser.add_argument(
        "--growth-tolerance", type=float, default=DEFAULT_GROWTH_TOLERANCE
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_revision(
        args.artifact_dir,
        args.output_dir,
        no_response_floor=args.no_response_floor,
        growth_tolerance=args.growth_tolerance,
    )
    print(result["revision_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FIGURE_FILES",
    "FrequencyRevisionError",
    "enrich_comparisons",
    "recalculate_stability",
    "requalify_response",
    "revise_delays",
    "run_revision",
]
