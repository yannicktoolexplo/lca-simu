#!/usr/bin/env python3
"""Run the additive frequency study for the canonical ``etudecas`` supply chain.

The study never modifies the historical cold-start or Closed-Loop V2 runners.
It creates graph/risk/schedule variants below its own output directory and uses
the public canonical engine interfaces:

* five-year native spectra for seasonality and descriptive bullwhip;
* paired periodic multisine experiments for a configured non-empty subset of
  demand, supplier availability and supplier lead time under MRP and the gated
  V2 controller (all three remain the backward-compatible default);
* a backward-compatible open-loop actuator probe through
  ``--control-schedule-csv``;
* an opt-in additive actuator probe around the V2/V3 feedback command through
  ``--control-probe-schedule-csv``.

The V2 policy is a hybrid supervisory controller.  Classical gain/phase margins
are therefore reported as non-identifiable unless a continuous local loop is
actually present.  Empirical attenuation and repeated-period boundedness are
reported instead, without a global stability claim.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    canonical_closed_loop as canonical,
)
from etudecas.prototypes.scan_2027_risk_control.frequency_analysis import (  # noqa: E402
    DEFAULT_COHERENCE_THRESHOLD,
    FrequencyAnalysisError,
    estimate_group_delay,
    extract_frequency_signals,
    native_band_amplification,
    normalized_multisine,
    paired_segment_growth,
    periodic_frf,
    periodic_residual_energy,
    validate_orthogonal_bins,
    welch_native_spectra,
)
from etudecas.simulation.engine.control_schedule import (  # noqa: E402
    ACTION_FIELDS,
    CONTROL_SCHEDULE_COLUMNS,
)
from etudecas.simulation.engine.demand_perturbation import (  # noqa: E402
    DEMAND_PERTURBATION_COLUMNS,
)


DEFAULT_CONFIG_PATH = HERE.parent / "config" / "canonical_frequency_study_config.json"
DEFAULT_OUTPUT_ROOT = HERE.parent / "outputs" / "canonical_frequency_study"
PROTOCOL_SCHEMA_VERSION = "scan.canonical_frequency_protocol.v1"
CONFIG_SCHEMA_VERSION = "scan.canonical_frequency_study.v1"
V2_CONTROL_POLICY_SCHEMA_VERSION = "scan.canonical_state_feedback.v2"
V3_CONTROL_POLICY_SCHEMA_VERSION = "scan.canonical_state_feedback.v3"
V2_CONTROL_FLAG = "--control-policy-v2-json"
V3_CONTROL_FLAG = "--control-policy-v3-json"
_CONTROL_POLICY_INTERFACES = {
    V2_CONTROL_POLICY_SCHEMA_VERSION: (
        V2_CONTROL_FLAG,
        "hybrid_supervisory_state_feedback_v2",
    ),
    V3_CONTROL_POLICY_SCHEMA_VERSION: (
        V3_CONTROL_FLAG,
        "hybrid_supervisory_continuous_state_feedback_v3",
    ),
}
TESTED_AMPLITUDE_LOCALITY_SCOPE = (
    "tested_amplitude_only_active_set_unverified"
)
DESIGNED_RESPONSE_SCOPE = (
    "tested_amplitude_operating_condition_dependent_active_set_unverified"
)
ACTUATOR_RESPONSE_SCOPE = (
    "tested_amplitude_command_to_output_active_set_unverified"
)
ACTUATOR_OPEN_LOOP_SCHEDULE = "open_loop_schedule"
ACTUATOR_POST_FEEDBACK_ADDITIVE = "post_feedback_additive"
ACTUATOR_APPLICATION_MODES = (
    ACTUATOR_OPEN_LOOP_SCHEDULE,
    ACTUATOR_POST_FEEDBACK_ADDITIVE,
)
LEGACY_REGIME_COMPATIBILITY_SEMANTICS = (
    "supervisory_regime_trace_compatibility_only_not_local_derivative_evidence"
)
DESIGNED_INPUT_SIGNALS = (
    "demand_multiplier",
    "supplier_availability_multiplier",
    "supplier_lead_time_multiplier",
)


class CanonicalFrequencyStudyError(RuntimeError):
    """Base error raised by the frequency study."""


class CanonicalFrequencyContractError(CanonicalFrequencyStudyError):
    """Configuration or generated evidence violates the study contract."""


@dataclass(frozen=True)
class CanonicalFrequencyArtifacts:
    """Paths and manifest returned by a completed frequency study."""

    output_root: Path
    protocol_path: Path
    protocol: Mapping[str, Any]
    response_path: Path | None
    native_spectra_path: Path | None


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
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalFrequencyContractError(f"{label} is not valid UTF-8 JSON: {resolved}") from exc
    if not isinstance(payload, dict):
        raise CanonicalFrequencyContractError(f"{label} must contain a JSON object: {resolved}")
    return payload


def _resolve_path(value: str | Path, *, repo_root: Path, relative_to: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (repo_root / path).resolve()
    local_candidate = (relative_to / path).resolve()
    return repo_candidate if repo_candidate.exists() else local_candidate


def _control_policy_interface(policy_path: Path) -> tuple[str, str, str]:
    """Return the explicit schema, engine flag and protocol kind for a policy."""

    payload = _read_json_object(policy_path, "control-policy JSON")
    schema_version = str(payload.get("schema_version") or "")
    interface = _CONTROL_POLICY_INTERFACES.get(schema_version)
    if interface is None:
        supported = ", ".join(sorted(_CONTROL_POLICY_INTERFACES))
        raise CanonicalFrequencyContractError(
            "control-policy JSON schema_version must select a supported "
            f"versioned interface ({supported}); got {schema_version!r}."
        )
    engine_flag, protocol_kind = interface
    return schema_version, engine_flag, protocol_kind


def _strict_positive_int(value: Any, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CanonicalFrequencyContractError(f"{label} must be an integer >= {minimum}.")
    return int(value)


def _strict_fraction(value: Any, label: str, *, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CanonicalFrequencyContractError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number) or not lower <= number <= upper:
        raise CanonicalFrequencyContractError(f"{label} must be finite in [{lower}, {upper}].")
    return number


def validate_frequency_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the immutable study protocol."""

    if str(payload.get("schema_version") or "") != CONFIG_SCHEMA_VERSION:
        raise CanonicalFrequencyContractError(
            f"schema_version must be {CONFIG_SCHEMA_VERSION!r}."
        )
    identification = payload.get("identification")
    if not isinstance(identification, Mapping):
        raise CanonicalFrequencyContractError("identification must be a JSON object.")
    period_days = _strict_positive_int(
        identification.get("period_days"), "identification.period_days", minimum=16
    )
    if period_days % 14:
        raise CanonicalFrequencyContractError(
            "identification.period_days must be a multiple of 14 so repeated periods align with weekly plant reviews and the V2 dwell calendar."
        )
    measured_periods = _strict_positive_int(
        identification.get("measured_periods"), "identification.measured_periods", minimum=3
    )
    warmup_periods = _strict_positive_int(
        identification.get("warmup_periods"), "identification.warmup_periods", minimum=1
    )
    warmup_days = _strict_positive_int(
        identification.get("warmup_days", period_days * warmup_periods),
        "identification.warmup_days",
        minimum=1,
    )
    raw_bins = identification.get("input_bins")
    if not isinstance(raw_bins, Mapping) or not raw_bins:
        raise CanonicalFrequencyContractError("identification.input_bins must be a non-empty object.")
    input_bins: dict[str, tuple[int, ...]] = {}
    for name, values in raw_bins.items():
        if not isinstance(values, list) or not values:
            raise CanonicalFrequencyContractError(f"identification.input_bins.{name} must be a non-empty list.")
        parsed: list[int] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int):
                raise CanonicalFrequencyContractError(f"identification.input_bins.{name} must contain integers.")
            parsed.append(int(value))
        input_bins[str(name)] = tuple(parsed)
    required_inputs = set(DESIGNED_INPUT_SIGNALS)
    if set(input_bins) != required_inputs:
        raise CanonicalFrequencyContractError(
            "identification.input_bins must contain exactly: " + ", ".join(sorted(required_inputs))
        )
    enabled_inputs_declared = "enabled_input_signals" in identification
    raw_enabled_inputs = identification.get("enabled_input_signals")
    if not enabled_inputs_declared:
        # Preserve the historical campaign exactly: all definitions execute in
        # the order in which input_bins declares them.
        enabled_input_signals = tuple(input_bins)
    else:
        if not isinstance(raw_enabled_inputs, list) or not raw_enabled_inputs:
            raise CanonicalFrequencyContractError(
                "identification.enabled_input_signals must be a non-empty list."
            )
        if not all(isinstance(name, str) and name for name in raw_enabled_inputs):
            raise CanonicalFrequencyContractError(
                "identification.enabled_input_signals must contain non-empty strings."
            )
        if len(set(raw_enabled_inputs)) != len(raw_enabled_inputs):
            raise CanonicalFrequencyContractError(
                "identification.enabled_input_signals must not contain duplicates."
            )
        unknown_inputs = sorted(set(raw_enabled_inputs) - required_inputs)
        if unknown_inputs:
            raise CanonicalFrequencyContractError(
                "identification.enabled_input_signals contains unsupported inputs: "
                + ", ".join(unknown_inputs)
            )
        enabled_input_signals = tuple(raw_enabled_inputs)
    if identification.get("experiment_design") != "separate_siso_campaigns":
        raise CanonicalFrequencyContractError(
            "identification.experiment_design must be separate_siso_campaigns."
        )
    try:
        for name, values in input_bins.items():
            validate_orthogonal_bins({name: values}, period_days)
    except FrequencyAnalysisError as exc:
        raise CanonicalFrequencyContractError(str(exc)) from exc
    if any(value % 2 == 0 for values in input_bins.values() for value in values):
        raise CanonicalFrequencyContractError(
            "identification.input_bins must use odd DFT lines so quadratic intermodulation remains on unexcited even lines."
        )
    peak = identification.get("peak_fraction")
    if not isinstance(peak, Mapping):
        raise CanonicalFrequencyContractError("identification.peak_fraction must be an object.")
    peak_fraction = {
        name: _strict_fraction(peak.get(name), f"identification.peak_fraction.{name}", lower=0.0, upper=0.20)
        for name in required_inputs
    }
    phase_seed = _strict_positive_int(
        identification.get("phase_seed", 1), "identification.phase_seed", minimum=0
    )
    coherence_threshold = _strict_fraction(
        identification.get("coherence_threshold", DEFAULT_COHERENCE_THRESHOLD),
        "identification.coherence_threshold",
        lower=0.0,
        upper=1.0,
    )

    conditions = payload.get("operating_conditions")
    if not isinstance(conditions, list) or not conditions:
        raise CanonicalFrequencyContractError(
            "operating_conditions must contain at least one condition."
        )
    parsed_conditions: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, raw in enumerate(conditions):
        if not isinstance(raw, Mapping):
            raise CanonicalFrequencyContractError(f"operating_conditions[{index}] must be an object.")
        name = str(raw.get("name") or "").strip()
        if not name or name in names:
            raise CanonicalFrequencyContractError("Operating-condition names must be unique and non-empty.")
        names.add(name)
        raw_demand_scales = raw.get("demand_scale_by_item", {})
        if not isinstance(raw_demand_scales, Mapping):
            raise CanonicalFrequencyContractError(
                f"operating_conditions[{index}].demand_scale_by_item must be an object."
            )
        demand_scales = {
            str(item_id): _strict_fraction(
                value,
                f"operating_conditions[{index}].demand_scale_by_item.{item_id}",
                lower=0.0,
                upper=2.0,
            )
            for item_id, value in raw_demand_scales.items()
        }
        parsed_conditions.append(
            {
                "name": name,
                "supplier_availability_baseline": _strict_fraction(
                    raw.get("supplier_availability_baseline"),
                    f"operating_conditions[{index}].supplier_availability_baseline",
                    lower=0.10,
                    upper=2.0,
                ),
                "supplier_lead_time_baseline": _strict_fraction(
                    raw.get("supplier_lead_time_baseline"),
                    f"operating_conditions[{index}].supplier_lead_time_baseline",
                    lower=0.10,
                    upper=5.0,
                ),
                "demand_scale_by_item": demand_scales,
                "intended_regime": str(raw.get("intended_regime") or "not_prespecified"),
            }
        )

    probe = payload.get("supplier_probe")
    if not isinstance(probe, Mapping):
        raise CanonicalFrequencyContractError("supplier_probe must be a JSON object.")
    required_probe = ("supplier_id", "item_id", "dst_node_id", "target_finished_item_id")
    parsed_probe = {name: str(probe.get(name) or "").strip() for name in required_probe}
    if any(not value for value in parsed_probe.values()):
        raise CanonicalFrequencyContractError("supplier_probe identifiers must all be non-empty.")
    parsed_probe["nominal_lead_time_days"] = _strict_fraction(
        probe.get("nominal_lead_time_days"),
        "supplier_probe.nominal_lead_time_days",
        lower=0.0,
        upper=365.0,
    )
    parsed_probe["selection_basis"] = str(probe.get("selection_basis") or "")
    require_unaliased_supplier_delay = identification.get(
        "require_unaliased_supplier_delay", True
    )
    if not isinstance(require_unaliased_supplier_delay, bool):
        raise CanonicalFrequencyContractError(
            "identification.require_unaliased_supplier_delay must be boolean."
        )
    lead_bins = sorted(input_bins["supplier_lead_time_multiplier"])
    # Phase must remain unwrap-safe across every adjacent sampled interval;
    # the largest DFT-bin gap is therefore the limiting spacing.
    lead_bin_spacing = max(
        (right - left for left, right in zip(lead_bins, lead_bins[1:])),
        default=0,
    )
    supplier_delay_alias_bound_days = (
        float(period_days) / (2.0 * lead_bin_spacing)
        if lead_bin_spacing > 0
        else None
    )
    maximum_structural_lead_days = max(
        float(parsed_probe["nominal_lead_time_days"])
        * float(condition["supplier_lead_time_baseline"])
        for condition in parsed_conditions
    )
    if (
        require_unaliased_supplier_delay
        and "supplier_lead_time_multiplier" in enabled_input_signals
        and (
            supplier_delay_alias_bound_days is None
            or maximum_structural_lead_days >= supplier_delay_alias_bound_days
        )
    ):
        raise CanonicalFrequencyContractError(
            "The supplier probe lead time exceeds the phase-unwrapping bound; "
            "increase period_days/change lead bins or select a shorter active lane."
        )

    campaign = payload.get("campaign")
    if not isinstance(campaign, Mapping):
        raise CanonicalFrequencyContractError("campaign must be a JSON object.")
    seed = _strict_positive_int(campaign.get("seed"), "campaign.seed", minimum=0)
    engine_args = campaign.get("engine_args", [])
    if not isinstance(engine_args, list) or not all(isinstance(item, str) and item for item in engine_args):
        raise CanonicalFrequencyContractError("campaign.engine_args must be a list of non-empty strings.")
    managed_engine_flags = {
        "--demand-perturbation-csv",
        "--control-schedule-csv",
        "--control-probe-schedule-csv",
        "--control-policy-json",
        V2_CONTROL_FLAG,
        V3_CONTROL_FLAG,
        "--supplier-risk-events-csv",
        "--warmup-days",
        "--warmup-profile-mode",
    }
    conflicting_flags = sorted(
        {
            argument.split("=", 1)[0]
            for argument in engine_args
            if argument.split("=", 1)[0] in managed_engine_flags
        }
    )
    if conflicting_flags:
        raise CanonicalFrequencyContractError(
            "campaign.engine_args cannot override frequency-study managed flags: "
            + ", ".join(conflicting_flags)
        )
    if campaign.get("state_dependent_risks") is not False:
        raise CanonicalFrequencyContractError(
            "campaign.state_dependent_risks must be false so designed exogenous lines remain identifiable."
        )
    claims = payload.get("claims")
    if not isinstance(claims, Mapping):
        raise CanonicalFrequencyContractError("claims must be a JSON object.")
    if claims.get("designed_response_scope") != DESIGNED_RESPONSE_SCOPE:
        raise CanonicalFrequencyContractError(
            "claims.designed_response_scope must explicitly describe a "
            "tested-amplitude response with unverified active-set invariance."
        )
    for claim_name in (
        "small_signal_local_derivative_claimed",
        "amplitude_sweep_verified",
        "active_set_invariance_verified",
        "global_stability_claimed",
        "industrial_validation_claimed",
    ):
        if claims.get(claim_name) is not False:
            raise CanonicalFrequencyContractError(
                f"claims.{claim_name} must be false."
            )

    actuator = payload.get("actuator_probe", {})
    if not isinstance(actuator, Mapping):
        raise CanonicalFrequencyContractError("actuator_probe must be a JSON object.")
    actuator_enabled = actuator.get("enabled", True)
    if not isinstance(actuator_enabled, bool):
        raise CanonicalFrequencyContractError("actuator_probe.enabled must be boolean.")
    actuator_application_mode = str(
        actuator.get("application_mode") or ACTUATOR_OPEN_LOOP_SCHEDULE
    )
    if actuator_application_mode not in ACTUATOR_APPLICATION_MODES:
        raise CanonicalFrequencyContractError(
            "actuator_probe.application_mode must be one of: "
            + ", ".join(ACTUATOR_APPLICATION_MODES)
            + "."
        )
    actuator_condition_name = str(
        actuator.get("baseline_condition") or parsed_conditions[0]["name"]
    ).strip()
    condition_names = {str(item["name"]) for item in parsed_conditions}
    if actuator_condition_name not in condition_names:
        raise CanonicalFrequencyContractError(
            "actuator_probe.baseline_condition must name one of the configured "
            "operating_conditions."
        )
    actuator_bins: dict[str, tuple[int, ...]] = {}
    if actuator_enabled:
        if actuator.get("response_scope") != ACTUATOR_RESPONSE_SCOPE:
            raise CanonicalFrequencyContractError(
                "actuator_probe.response_scope must explicitly describe a "
                "tested-amplitude command-to-output response with unverified "
                "active-set invariance."
            )
        for claim_name in (
            "small_signal_local_derivative_claimed",
            "active_set_invariance_verified",
        ):
            if actuator.get(claim_name) is not False:
                raise CanonicalFrequencyContractError(
                    f"actuator_probe.{claim_name} must be false."
                )
        raw_actuator_bins = actuator.get("input_bins")
        if not isinstance(raw_actuator_bins, Mapping):
            raise CanonicalFrequencyContractError("actuator_probe.input_bins must be an object.")
        for name in (
            "order_multiplier",
            "safety_stock_multiplier",
            "production_target_multiplier",
        ):
            values = raw_actuator_bins.get(name)
            if not isinstance(values, list) or not values:
                raise CanonicalFrequencyContractError(f"actuator_probe.input_bins.{name} must be non-empty.")
            actuator_bins[name] = tuple(int(value) for value in values)
        try:
            for name, values in actuator_bins.items():
                validate_orthogonal_bins({name: values}, period_days)
        except FrequencyAnalysisError as exc:
            raise CanonicalFrequencyContractError(str(exc)) from exc
        if any(value % 2 == 0 for values in actuator_bins.values() for value in values):
            raise CanonicalFrequencyContractError(
                "actuator_probe.input_bins must use odd DFT lines for quadratic nonlinearity separation."
            )
        if (
            actuator_application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE
            and max(value for values in actuator_bins.values() for value in values) > 13
        ):
            raise CanonicalFrequencyContractError(
                "post_feedback_additive actuator probes must use DFT bins <= 13 "
                "so the pilot remains below the weekly-review frequency range."
            )
    return {
        "period_days": period_days,
        "experiment_design": "separate_siso_campaigns",
        "measured_periods": measured_periods,
        "warmup_periods": warmup_periods,
        "days": period_days * measured_periods,
        "warmup_days": warmup_days,
        "warmup_periods_equivalent": warmup_days / float(period_days),
        "input_bins": input_bins,
        "enabled_input_signals": enabled_input_signals,
        "peak_fraction": peak_fraction,
        "phase_seed": phase_seed,
        "coherence_threshold": coherence_threshold,
        "bootstrap_samples": _strict_positive_int(
            identification.get("bootstrap_samples", 1000),
            "identification.bootstrap_samples",
            minimum=0,
        ),
        "conditions": parsed_conditions,
        "probe": parsed_probe,
        "require_unaliased_supplier_delay": require_unaliased_supplier_delay,
        "supplier_delay_phase_unwrap_bound_days": supplier_delay_alias_bound_days,
        "campaign": dict(campaign),
        "seed": seed,
        "engine_args": tuple(engine_args),
        "actuator_enabled": actuator_enabled,
        "actuator_application_mode": actuator_application_mode,
        "actuator_condition_name": actuator_condition_name,
        "actuator_bins": actuator_bins,
        "actuator_peak_fraction": _strict_fraction(
            actuator.get("peak_fraction", 0.03),
            "actuator_probe.peak_fraction",
            lower=0.0,
            upper=0.20,
        ),
        "designed_response_scope": DESIGNED_RESPONSE_SCOPE,
        "actuator_response_scope": ACTUATOR_RESPONSE_SCOPE,
    }


def _profile_mean(profile: Sequence[Mapping[str, Any]]) -> float:
    values: list[float] = []
    for day in range(365):
        candidates: list[tuple[int, float]] = []
        for raw in profile:
            repeat = int(float(raw.get("repeat_period_days") or 0))
            eval_day = day % repeat if repeat > 0 else day
            kind = str(raw.get("type") or "constant")
            if kind == "constant":
                candidates.append((0, float(raw.get("value") or 0.0)))
            elif kind == "piecewise":
                for point in raw.get("points") or []:
                    if not isinstance(point, Mapping):
                        continue
                    t = int(float(point.get("t") or 0))
                    if eval_day >= t:
                        candidates.append((t, float(point.get("value") or 0.0)))
        values.append(sorted(candidates)[-1][1] if candidates else 0.0)
    positive_mean = float(np.mean(values))
    if not math.isfinite(positive_mean) or positive_mean <= 0:
        raise CanonicalFrequencyContractError("A demand profile has no positive finite annual mean.")
    return positive_mean


def _write_graph_variant(
    source_graph: Path,
    destination: Path,
    *,
    period_days: int,
    demand_fraction: np.ndarray,
    excited: bool,
    demand_scale_by_item: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    payload = _read_json_object(source_graph, "canonical graph")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise CanonicalFrequencyContractError("Canonical graph has no scenario.")
    demand_rows = scenarios[0].get("demand")
    if not isinstance(demand_rows, list) or not demand_rows:
        raise CanonicalFrequencyContractError("Canonical scenario has no demand profiles.")
    baselines: dict[str, float] = {}
    original_baselines: dict[str, float] = {}
    demand_scales = dict(demand_scale_by_item or {})
    for row in demand_rows:
        if not isinstance(row, dict):
            continue
        source_profile = row.get("profile")
        if not isinstance(source_profile, list):
            raise CanonicalFrequencyContractError("Demand row profile is not a list.")
        original_baseline = _profile_mean(source_profile)
        item_id = str(row.get("item_id") or "")
        scale = float(demand_scales.get(item_id, 1.0))
        baseline = original_baseline * scale
        pair = f"{row.get('node_id')}|{row.get('item_id')}"
        baselines[pair] = baseline
        original_baselines[pair] = original_baseline
        multiplier = 1.0 + demand_fraction if excited else np.ones(period_days, dtype=float)
        row["profile"] = [
            {
                "type": "piecewise",
                "points": [
                    {"t": day, "value": round(float(baseline * multiplier[day]), 9)}
                    for day in range(period_days)
                ],
                "repeat_mode": "frequency_study_periodic",
                "repeat_period_days": int(period_days),
                "daily_distribution": "designed_daily_multisine" if excited else "constant_operating_point",
                "uom": "unit/day",
                "source": "scan_frequency_tested_amplitude_experiment",
                "is_default": False,
            }
        ]
        source_truth = row.get("source_truth")
        source_truth = dict(source_truth) if isinstance(source_truth, Mapping) else {}
        source_truth.update(
            {
                "frequency_study_variant": "excited" if excited else "paired_baseline",
                "original_case_profile_preserved_in_source_graph": True,
                "designed_local_identification": True,
                "industrial_observation": False,
                "operating_point_demand_scale": scale,
            }
        )
        row["source_truth"] = source_truth
    meta = payload.get("meta")
    meta = dict(meta) if isinstance(meta, Mapping) else {}
    meta["scan_frequency_study"] = {
        "source_graph": str(source_graph),
        "source_graph_sha256": _sha256(source_graph),
        "variant": "excited" if excited else "paired_baseline",
        "period_days": int(period_days),
        "demand_peak_fraction_realized": float(np.max(np.abs(demand_fraction))) if excited else 0.0,
        "synthetic_designed_excitation": True,
        "demand_scale_by_item": demand_scales,
        "focused_operating_point": bool(demand_scales),
    }
    payload["meta"] = meta
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(destination),
        "sha256": _sha256(destination),
        "demand_baselines": baselines,
        "original_demand_baselines": original_baselines,
        "demand_scale_by_item": demand_scales,
    }


def _write_demand_perturbation(
    destination: Path,
    *,
    graph_path: Path,
    measured_days: int,
    period_days: int,
    demand_fraction: np.ndarray,
    target_item_id: str | None = None,
) -> dict[str, Any]:
    """Write an exact-scope, measured-day-only demand excitation schedule."""

    payload = _read_json_object(graph_path, "frequency operating-point graph")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise CanonicalFrequencyContractError("Frequency graph has no scenario.")
    demand_rows = scenarios[0].get("demand")
    if not isinstance(demand_rows, list) or not demand_rows:
        raise CanonicalFrequencyContractError("Frequency graph has no demand pairs.")
    pairs = sorted(
        {
            (str(row.get("node_id") or ""), str(row.get("item_id") or ""))
            for row in demand_rows
            if isinstance(row, Mapping)
            and (
                target_item_id is None
                or str(row.get("item_id") or "") == str(target_item_id)
            )
        }
    )
    if not pairs or any(not node_id or not item_id for node_id, item_id in pairs):
        raise CanonicalFrequencyContractError("Frequency graph contains an invalid demand pair.")
    rows = [
        {
            "day": day,
            "node_id": node_id,
            "item_id": item_id,
            "demand_multiplier": round(
                1.0 + float(demand_fraction[day % int(period_days)]), 9
            ),
        }
        for day in range(int(measured_days))
        for node_id, item_id in pairs
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=DEMAND_PERTURBATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "path": str(destination),
        "sha256": _sha256(destination),
        "row_count": len(rows),
        "demand_pair_count": len(pairs),
        "target_item_id": str(target_item_id or "all_graph_demand_items"),
        "day_basis": "zero_based_measured_days_only_never_warmup",
        "peak_fraction_realized": float(np.max(np.abs(demand_fraction))),
    }


def _write_risk_events(
    destination: Path,
    *,
    condition: Mapping[str, Any],
    probe: Mapping[str, str],
    warmup_days: int,
    measured_days: int,
    period_days: int,
    availability_fraction: np.ndarray,
    lead_time_fraction: np.ndarray,
    excited: bool,
) -> dict[str, Any]:
    fields = (
        "event_id",
        "risk_type",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "start_day",
        "end_day",
        "multiplier",
        "notes",
    )
    availability_baseline = float(condition["supplier_availability_baseline"])
    lead_baseline = float(condition["supplier_lead_time_baseline"])
    rows: list[dict[str, Any]] = []
    if excited:
        for day in range(-int(warmup_days), int(measured_days)):
            phase_day = day % int(period_days)
            measured = day >= 0
            availability_multiplier = availability_baseline * (
                1.0 + availability_fraction[phase_day] if measured else 1.0
            )
            lead_multiplier = lead_baseline * (
                1.0 + lead_time_fraction[phase_day] if measured else 1.0
            )
            rows.extend(
                [
                    {
                        "event_id": f"frequency_availability_d{day}",
                        "risk_type": "availability",
                        "supplier_id": probe["supplier_id"],
                        "item_id": probe["item_id"],
                        "dst_node_id": probe["dst_node_id"],
                        "start_day": day,
                        "end_day": day,
                        "multiplier": round(availability_multiplier, 9),
                        "notes": (
                            "designed bounded periodic supplier-availability excitation"
                            if measured
                            else "paired constant warmup before measured excitation"
                        ),
                    },
                    {
                        "event_id": f"frequency_lead_time_d{day}",
                        "risk_type": "lead_time",
                        "supplier_id": probe["supplier_id"],
                        "item_id": probe["item_id"],
                        "dst_node_id": probe["dst_node_id"],
                        "start_day": day,
                        "end_day": day,
                        "multiplier": round(lead_multiplier, 9),
                        "notes": (
                            "designed bounded periodic supplier-lead-time excitation"
                            if measured
                            else "paired constant warmup before measured excitation"
                        ),
                    },
                ]
            )
    else:
        rows.extend(
            [
                {
                    "event_id": "frequency_availability_paired_baseline",
                    "risk_type": "availability",
                    "supplier_id": probe["supplier_id"],
                    "item_id": probe["item_id"],
                    "dst_node_id": probe["dst_node_id"],
                    "start_day": -int(warmup_days),
                    "end_day": int(measured_days) - 1,
                    "multiplier": availability_baseline,
                    "notes": "paired operating-condition baseline for frequency study",
                },
                {
                    "event_id": "frequency_lead_time_paired_baseline",
                    "risk_type": "lead_time",
                    "supplier_id": probe["supplier_id"],
                    "item_id": probe["item_id"],
                    "dst_node_id": probe["dst_node_id"],
                    "start_day": -int(warmup_days),
                    "end_day": int(measured_days) - 1,
                    "multiplier": lead_baseline,
                    "notes": "paired operating-condition baseline for frequency study",
                },
            ]
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return {"path": str(destination), "sha256": _sha256(destination), "row_count": len(rows)}


def _write_excitation_audit(
    path: Path,
    *,
    normalized: Mapping[str, Any],
    channel_signals: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    period = int(normalized["period_days"])
    days = int(normalized["days"])
    for condition in normalized["conditions"]:
        availability_baseline = float(condition["supplier_availability_baseline"])
        lead_baseline = float(condition["supplier_lead_time_baseline"])
        for experiment_input in normalized["enabled_input_signals"]:
            for day in range(days):
                phase_day = day % period
                demand_fraction = (
                    float(channel_signals["demand_multiplier"][phase_day])
                    if experiment_input == "demand_multiplier"
                    else 0.0
                )
                availability_fraction = (
                    float(channel_signals["supplier_availability_multiplier"][phase_day])
                    if experiment_input == "supplier_availability_multiplier"
                    else 0.0
                )
                lead_fraction = (
                    float(channel_signals["supplier_lead_time_multiplier"][phase_day])
                    if experiment_input == "supplier_lead_time_multiplier"
                    else 0.0
                )
                rows.append(
                    {
                        "condition": condition["name"],
                        "experiment_input_signal": experiment_input,
                        "day": day,
                        "period_index": day // period,
                        "day_in_period": phase_day,
                        "demand_fractional_excitation": demand_fraction,
                        "supplier_availability_fractional_excitation": availability_fraction,
                        "supplier_lead_time_fractional_excitation": lead_fraction,
                        "demand_multiplier": 1.0 + demand_fraction,
                        "supplier_availability_multiplier": availability_baseline * (1.0 + availability_fraction),
                        "supplier_availability_baseline": availability_baseline,
                        "supplier_lead_time_multiplier": lead_baseline * (1.0 + lead_fraction),
                        "supplier_lead_time_baseline": lead_baseline,
                        "synthetic_designed_excitation": True,
                        "separate_siso_campaign": True,
                    }
                )
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False)
    return frame


def _response_scale(output_signal: str, baseline: pd.DataFrame) -> tuple[float, str]:
    if output_signal.endswith("service_level") or output_signal.endswith("utilization"):
        return 1.0, "fraction"
    if output_signal.startswith("control_"):
        return 1.0, "dimensionless"
    values = baseline[output_signal].to_numpy(dtype=float)
    scale = max(abs(float(np.mean(values))), float(np.mean(np.abs(values))), 1.0)
    if output_signal.endswith("backlog_qty"):
        demand_name = "target_demand_qty" if output_signal.startswith("target_") else "global_demand_qty"
        scale = max(scale, abs(float(baseline[demand_name].mean())), 1.0)
        return scale, "backlog normalized by mean daily demand"
    return scale, "mean absolute paired-baseline response"


def _delay_diagnostic(
    estimate: pd.DataFrame,
    *,
    input_signal: str,
    bins: Sequence[int],
    period_days: int,
    structural_lead_days: float | None = None,
) -> dict[str, Any]:
    result = estimate_group_delay(estimate)
    parsed = sorted(int(value) for value in bins)
    # Use the largest retained gap: a smaller gap would overstate the
    # unambiguous-delay range on a non-uniform frequency grid.
    spacing = max(
        (right - left for left, right in zip(parsed, parsed[1:])),
        default=0,
    )
    alias_bound = (
        float(period_days) / (2.0 * spacing) if spacing > 0 else None
    )
    result["phase_unwrap_abs_delay_bound_days"] = alias_bound
    result["structural_probe_lead_days"] = structural_lead_days
    if (
        input_signal == "supplier_lead_time_multiplier"
        and structural_lead_days is not None
        and alias_bound is not None
        and structural_lead_days >= alias_bound
    ):
        result["aliased_phase_slope_days"] = result.get("delay_days")
        result["delay_days"] = None
        result["status"] = (
            "not_identifiable_phase_alias_structural_lead_exceeds_unwrap_bound"
        )
    return result


def _regime_occupancy(result_dir: Path) -> dict[str, int]:
    trace = _regime_trace(result_dir)
    return {
        str(name): int(count)
        for name, count in pd.Series(
            tuple(regime for _, regime in trace), dtype=str
        ).value_counts().items()
    }


def _regime_trace(result_dir: Path) -> tuple[tuple[int, str], ...]:
    path = result_dir / "data" / "canonical_closed_loop_observations.csv"
    if not path.is_file():
        return ()
    frame = pd.read_csv(path, usecols=["day", "confirmed_regime"]).sort_values(
        "day", kind="stable"
    )
    return tuple(
        (int(row.day), str(row.confirmed_regime))
        for row in frame.itertuples(index=False)
    )


def _regime_pair_metadata(
    policy: str,
    baseline_trace: Sequence[tuple[int, str]],
    excited_trace: Sequence[tuple[int, str]],
) -> dict[str, Any]:
    if policy == canonical.REFERENCE_POLICY:
        return {
            "baseline_dominant_regime": "not_applicable_mrp_reference",
            "baseline_dominant_regime_share": None,
            "excited_dominant_regime": "not_applicable_mrp_reference",
            "excited_dominant_regime_share": None,
            "regime_trace_mismatch_days": 0,
            "baseline_regime_day_grid_valid": None,
            "excited_regime_day_grid_valid": None,
            "regime_compatible_for_local_claim": True,
            "regime_compatible_for_local_claim_semantics": (
                LEGACY_REGIME_COMPATIBILITY_SEMANTICS
            ),
            "tested_amplitude_regime_trace_compatible": True,
            "amplitude_sweep_verified": False,
            "active_set_invariance_verified": False,
            "zero_amplitude_local_derivative_claimed": False,
            "locality_evidence_scope": TESTED_AMPLITUDE_LOCALITY_SCOPE,
            "response_regime_scope": (
                "tested_amplitude_no_supervisory_regime_active_set_unverified"
            ),
        }

    def dominant(
        trace: Sequence[tuple[int, str]],
    ) -> tuple[str | None, float | None]:
        if not trace:
            return None, None
        counts = pd.Series(
            tuple(regime for _, regime in trace), dtype=str
        ).value_counts()
        maximum = int(counts.max())
        name = sorted(str(value) for value in counts[counts.eq(maximum)].index)[0]
        return name, maximum / float(len(trace))

    baseline_dominant, baseline_share = dominant(baseline_trace)
    excited_dominant, excited_share = dominant(excited_trace)
    baseline_day_grid_valid = tuple(day for day, _ in baseline_trace) == tuple(
        range(len(baseline_trace))
    )
    excited_day_grid_valid = tuple(day for day, _ in excited_trace) == tuple(
        range(len(excited_trace))
    )
    comparable_length = (
        len(baseline_trace) == len(excited_trace)
        and bool(baseline_trace)
        and baseline_day_grid_valid
        and excited_day_grid_valid
    )
    mismatch_days = (
        sum(left != right for left, right in zip(baseline_trace, excited_trace))
        if comparable_length
        else max(len(baseline_trace), len(excited_trace))
    )
    compatible = bool(comparable_length and mismatch_days == 0)
    return {
        "baseline_dominant_regime": baseline_dominant,
        "baseline_dominant_regime_share": baseline_share,
        "excited_dominant_regime": excited_dominant,
        "excited_dominant_regime_share": excited_share,
        "regime_trace_mismatch_days": int(mismatch_days),
        "baseline_regime_day_grid_valid": baseline_day_grid_valid,
        "excited_regime_day_grid_valid": excited_day_grid_valid,
        "regime_compatible_for_local_claim": compatible,
        "regime_compatible_for_local_claim_semantics": (
            LEGACY_REGIME_COMPATIBILITY_SEMANTICS
        ),
        "tested_amplitude_regime_trace_compatible": compatible,
        "amplitude_sweep_verified": False,
        "active_set_invariance_verified": False,
        "zero_amplitude_local_derivative_claimed": False,
        "locality_evidence_scope": TESTED_AMPLITUDE_LOCALITY_SCOPE,
        "response_regime_scope": (
            "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified"
            if compatible
            else "tested_amplitude_hybrid_regime_switching_active_set_unverified"
        ),
    }


def _annotate_response_regime_scope(
    response: pd.DataFrame,
    *,
    condition_runs: Mapping[str, Mapping[str, Any]],
    seed: int,
) -> pd.DataFrame:
    if response.empty:
        return response.copy()
    annotated = response.copy()
    designed = annotated["study_kind"].eq(
        "designed_closed_loop_disturbance_probe"
    )
    metadata_fields = (
        "baseline_dominant_regime",
        "baseline_dominant_regime_share",
        "excited_dominant_regime",
        "excited_dominant_regime_share",
        "regime_trace_mismatch_days",
        "baseline_regime_day_grid_valid",
        "excited_regime_day_grid_valid",
        "regime_compatible_for_local_claim",
        "regime_compatible_for_local_claim_semantics",
        "tested_amplitude_regime_trace_compatible",
        "amplitude_sweep_verified",
        "active_set_invariance_verified",
        "zero_amplitude_local_derivative_claimed",
        "locality_evidence_scope",
        "response_regime_scope",
    )
    for field in metadata_fields:
        annotated[field] = None
    for keys, indexes in annotated.loc[designed].groupby(
        ["condition", "policy", "input_signal"], sort=True
    ).groups.items():
        condition_name, policy, input_name = (str(value) for value in keys)
        roots = condition_runs[condition_name]
        baseline_dir = (
            Path(roots["baseline_root"]) / policy / f"seed_{int(seed)}"
        )
        excited_dir = (
            Path(roots["excited_roots"][input_name])
            / policy
            / f"seed_{int(seed)}"
        )
        metadata = _regime_pair_metadata(
            policy,
            _regime_trace(baseline_dir),
            _regime_trace(excited_dir),
        )
        for field, value in metadata.items():
            annotated.loc[indexes, field] = value
        annotated.loc[indexes, "response_kind"] = (
            "hybrid_regime_switching_harmonic_line_response"
            if not bool(metadata["tested_amplitude_regime_trace_compatible"])
            else "empirical_diagonal_harmonic_line_response"
        )
    annotated.loc[designed, "tested_amplitude_harmonic_response"] = (
        annotated.loc[designed, "valid_bin"].astype(bool)
    )
    # Historical consumers expect this column to exist.  An unchanged
    # supervisory trace is necessary but not sufficient for a zero-amplitude
    # derivative: the campaign has one finite amplitude and does not audit the
    # plant/controller active set.  Therefore no current row may assert a true
    # small-signal-local claim.
    annotated.loc[designed, "small_signal_local_claim"] = False
    return annotated


def _annotate_delay_scope(
    response: pd.DataFrame,
    delays: pd.DataFrame,
) -> pd.DataFrame:
    """Gate phase slopes on the final response-scope classification.

    Delay diagnostics are initially computed from the numerical harmonic-line
    estimates.  A local group-delay claim additionally requires a verified
    local scope: fixed supervisory trace, an amplitude-sweep basis and
    invariant active sets.  Hybrid or single-tested-amplitude phase trends may
    remain descriptive, but must not remain in ``delay_days``.
    """

    if delays.empty:
        return delays.copy()
    annotated = delays.copy()
    annotated["supporting_valid_line_count"] = 0
    annotated["supporting_local_line_count"] = 0
    annotated["supporting_scope_verified_line_count"] = 0
    annotated["phase_slope_scope"] = "not_identified"
    annotated["local_phase_slope_identified"] = False
    annotated["zero_amplitude_local_delay_claimed"] = False
    annotated["active_set_invariance_verified"] = False
    annotated["amplitude_sweep_verified"] = False
    annotated["descriptive_phase_slope_days"] = None
    keys = ("study_kind", "condition", "policy", "input_signal", "output_signal")
    for index, row in annotated.iterrows():
        mask = pd.Series(True, index=response.index, dtype=bool)
        for key in keys:
            if key not in response.columns:
                mask &= False
                continue
            mask &= response[key].astype(str).eq(str(row.get(key, "")))
        supporting = response.loc[mask].copy()
        valid = supporting.loc[
            supporting.get("valid_bin", pd.Series(False, index=supporting.index))
            .fillna(False)
            .astype(bool)
        ]
        legacy_local = valid.loc[
            valid.get(
                "small_signal_local_claim", pd.Series(False, index=valid.index)
            )
            .fillna(False)
            .astype(bool)
        ]
        scope_verified = valid.loc[
            valid.get(
                "small_signal_local_claim", pd.Series(False, index=valid.index)
            )
            .fillna(False)
            .astype(bool)
            & valid.get(
                "amplitude_sweep_verified", pd.Series(False, index=valid.index)
            )
            .fillna(False)
            .astype(bool)
            & valid.get(
                "active_set_invariance_verified",
                pd.Series(False, index=valid.index),
            )
            .fillna(False)
            .astype(bool)
        ]
        annotated.at[index, "supporting_valid_line_count"] = int(len(valid))
        annotated.at[index, "supporting_local_line_count"] = int(
            len(legacy_local)
        )
        annotated.at[index, "supporting_scope_verified_line_count"] = int(
            len(scope_verified)
        )
        raw_delay = pd.to_numeric(
            pd.Series([row.get("delay_days")]), errors="coerce"
        ).iloc[0]
        if pd.isna(raw_delay):
            continue
        annotated.at[index, "descriptive_phase_slope_days"] = float(raw_delay)
        all_support_is_local = bool(
            len(valid) >= 3 and len(scope_verified) == len(valid)
        )
        if all_support_is_local:
            annotated.at[index, "phase_slope_scope"] = (
                "verified_local_mode_phase_slope"
            )
            annotated.at[index, "local_phase_slope_identified"] = True
            annotated.at[index, "zero_amplitude_local_delay_claimed"] = True
            annotated.at[index, "active_set_invariance_verified"] = True
            annotated.at[index, "amplitude_sweep_verified"] = True
            continue
        scopes = sorted(
            {
                str(value)
                for value in valid.get(
                    "response_regime_scope", pd.Series(dtype=str)
                ).dropna()
                if str(value)
            }
        )
        annotated.at[index, "delay_days"] = None
        annotated.at[index, "phase_slope_scope"] = (
            "tested_amplitude_or_hybrid_descriptive_phase_trend"
        )
        annotated.at[index, "status"] = (
            "hybrid_regime_phase_slope_not_local_delay"
            if any("hybrid" in scope for scope in scopes)
            else "tested_amplitude_active_set_unverified_phase_slope_not_local_delay"
        )
        if scopes:
            annotated.at[index, "response_regime_scope"] = "|".join(scopes)
    return annotated


def _analyse_designed_pairs(
    *,
    normalized: Mapping[str, Any],
    condition_runs: Mapping[str, Mapping[str, Any]],
    channel_signals: Mapping[str, np.ndarray],
    output_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    response_rows: list[pd.DataFrame] = []
    trajectory_rows: list[pd.DataFrame] = []
    residual_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    delay_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    period = int(normalized["period_days"])
    measured_periods = int(normalized["measured_periods"])
    input_series = {
        name: np.tile(signal, measured_periods)
        for name, signal in channel_signals.items()
    }
    probe = normalized["probe"]
    output_names = (
        "global_service_level",
        "global_backlog_qty",
        "global_inventory_qty",
        "global_order_qty",
        "global_production_qty",
        "global_supplier_shipments_qty",
        "global_total_supply_cost_per_day",
        "global_order_nervousness",
        "global_production_nervousness",
        "target_service_level",
        "target_backlog_qty",
        "target_production_qty",
        "target_finished_stock_qty",
        "probe_supplier_shipments_qty",
        "probe_destination_arrivals_qty",
        "probe_supplier_stock_qty",
        "probe_supplier_utilization",
        "control_order_multiplier",
        "control_safety_stock_multiplier",
        "control_production_target_multiplier",
    )
    for condition in normalized["conditions"]:
        condition_name = str(condition["name"])
        roots = condition_runs[condition_name]
        reference_scale_dir = (
            Path(roots["baseline_root"])
            / canonical.REFERENCE_POLICY
            / f"seed_{normalized['seed']}"
        )
        reference_scale_baseline, _ = extract_frequency_signals(
            reference_scale_dir,
            target_finished_item_id=probe["target_finished_item_id"],
            probe_supplier_id=probe["supplier_id"],
            probe_item_id=probe["item_id"],
            probe_dst_node_id=probe["dst_node_id"],
        )
        for policy in (canonical.REFERENCE_POLICY, canonical.FEEDBACK_POLICY):
            baseline_dir = Path(roots["baseline_root"]) / policy / f"seed_{normalized['seed']}"
            baseline, units = extract_frequency_signals(
                baseline_dir,
                target_finished_item_id=probe["target_finished_item_id"],
                probe_supplier_id=probe["supplier_id"],
                probe_item_id=probe["item_id"],
                probe_dst_node_id=probe["dst_node_id"],
            )
            if len(baseline) != int(normalized["days"]):
                raise CanonicalFrequencyContractError(
                    f"{condition_name}/{policy}: baseline signals do not match the measured horizon."
                )
            baseline_occupancy = _regime_occupancy(baseline_dir)
            for regime, count in baseline_occupancy.items():
                regime_rows.append(
                    {
                        "condition": condition_name,
                        "policy": policy,
                        "arm": "shared_baseline",
                        "experiment_input_signal": "none",
                        "confirmed_regime": regime,
                        "day_count": count,
                        "day_share": count / float(normalized["days"]),
                    }
                )

            for input_name in normalized["enabled_input_signals"]:
                bins = normalized["input_bins"][input_name]
                excited_dir = (
                    Path(roots["excited_roots"][input_name])
                    / policy
                    / f"seed_{normalized['seed']}"
                )
                excited, _ = extract_frequency_signals(
                    excited_dir,
                    target_finished_item_id=probe["target_finished_item_id"],
                    probe_supplier_id=probe["supplier_id"],
                    probe_item_id=probe["item_id"],
                    probe_dst_node_id=probe["dst_node_id"],
                )
                if len(excited) != len(baseline):
                    raise CanonicalFrequencyContractError(
                        f"{condition_name}/{policy}/{input_name}: paired signals do not match."
                    )
                delta = excited.set_index("day") - baseline.set_index("day")
                trajectory = pd.DataFrame(
                    {
                        "condition": condition_name,
                        "policy": policy,
                        "experiment_input_signal": input_name,
                        "day": baseline["day"].astype(int),
                        "period_index": baseline["day"].astype(int) // period,
                    }
                )
                for candidate_name, candidate_values in input_series.items():
                    values = (
                        candidate_values
                        if candidate_name == input_name
                        else np.zeros_like(candidate_values)
                    )
                    trajectory[candidate_name] = values
                    trajectory[f"excitation_fraction__{candidate_name}"] = values
                for output_signal in output_names:
                    trajectory[f"baseline__{output_signal}"] = baseline[
                        output_signal
                    ].to_numpy(dtype=float)
                    trajectory[f"excited__{output_signal}"] = excited[
                        output_signal
                    ].to_numpy(dtype=float)
                    trajectory[f"delta__{output_signal}"] = delta[
                        output_signal
                    ].to_numpy(dtype=float)
                trajectory_rows.append(trajectory)

                occupancy = _regime_occupancy(excited_dir)
                for regime, count in occupancy.items():
                    regime_rows.append(
                        {
                            "condition": condition_name,
                            "policy": policy,
                            "arm": "excited",
                            "experiment_input_signal": input_name,
                            "confirmed_regime": regime,
                            "day_count": count,
                            "day_share": count / float(normalized["days"]),
                        }
                    )

                active_input_series = {input_name: input_series[input_name]}
                active_bins = {input_name: bins}
                for output_signal in output_names:
                    scale, scale_basis = _response_scale(
                        output_signal, reference_scale_baseline
                    )
                    scale_basis = "common_mrp_reference__" + scale_basis
                    output_delta = delta[output_signal].to_numpy(dtype=float)
                    residual = periodic_residual_energy(
                        active_input_series,
                        output_delta,
                        period_days=period,
                        excited_bins=active_bins,
                        discard_periods=1,
                    )
                    residual_rows.append(
                        {
                            "study_kind": "designed_closed_loop_disturbance_probe",
                            "condition": condition_name,
                            "policy": policy,
                            "input_signal": input_name,
                            "output_signal": output_signal,
                            "output_unit": units.get(output_signal, "unknown"),
                            **residual,
                        }
                    )
                    growth = paired_segment_growth(
                        output_delta,
                        period_days=period,
                        discard_periods=1,
                    )
                    stability_rows.append(
                        {
                            "study_kind": "designed_closed_loop_disturbance_probe",
                            "condition": condition_name,
                            "policy": policy,
                            "input_signal": input_name,
                            "output_signal": output_signal,
                            "classical_margin_status": (
                                "not_identifiable_hybrid_supervisory_controller"
                                if policy == canonical.FEEDBACK_POLICY
                                else "not_applicable_mrp_reference_has_no_feedback_compensator"
                            ),
                            **growth,
                        }
                    )
                    estimate = periodic_frf(
                        input_series[input_name],
                        output_delta,
                        period_days=period,
                        bins=bins,
                        discard_periods=1,
                        response_scale=scale,
                        bootstrap_samples=int(normalized["bootstrap_samples"]),
                        bootstrap_seed=int(normalized["phase_seed"]) + len(response_rows) * 8191,
                        coherence_threshold=float(normalized["coherence_threshold"]),
                    )
                    estimate.insert(0, "study_kind", "designed_closed_loop_disturbance_probe")
                    estimate.insert(1, "condition", condition_name)
                    estimate.insert(2, "policy", policy)
                    estimate.insert(3, "input_signal", input_name)
                    estimate.insert(4, "output_signal", output_signal)
                    estimate.insert(5, "output_unit", units.get(output_signal, "unknown"))
                    estimate.insert(6, "response_scale_basis", scale_basis)
                    estimate["designed_excitation"] = True
                    estimate["experiment_design"] = "separate_siso_campaign"
                    estimate["response_kind"] = (
                        "empirical_diagonal_harmonic_line_response"
                    )
                    estimate["isolated_lti_frf_claimed"] = False
                    estimate["settling_periods_discarded"] = 1
                    bounded = bool(growth["bounded_repeated_response"])
                    repeatable = bool(growth["repeatable_periodic_response"])
                    estimate["bounded_repeated_response"] = bounded
                    estimate["repeatable_periodic_response"] = repeatable
                    estimate["valid_bin"] = (
                        estimate["valid_bin"].astype(bool) & bounded & repeatable
                    )
                    estimate["small_signal_local_claim"] = False
                    estimate["global_stability_claimed"] = False
                    response_rows.append(estimate)
                    delay_rows.append(
                        {
                            "study_kind": "designed_closed_loop_disturbance_probe",
                            "condition": condition_name,
                            "policy": policy,
                            "input_signal": input_name,
                            "output_signal": output_signal,
                            **_delay_diagnostic(
                                estimate,
                                input_signal=input_name,
                                bins=bins,
                                period_days=period,
                                structural_lead_days=(
                                    float(probe["nominal_lead_time_days"])
                                    * float(condition["supplier_lead_time_baseline"])
                                    if input_name == "supplier_lead_time_multiplier"
                                    else None
                                ),
                            ),
                        }
                    )
    response = pd.concat(response_rows, ignore_index=True) if response_rows else pd.DataFrame()
    response = _annotate_response_regime_scope(
        response,
        condition_runs=condition_runs,
        seed=int(normalized["seed"]),
    )
    trajectories = pd.concat(trajectory_rows, ignore_index=True) if trajectory_rows else pd.DataFrame()
    delays = _annotate_delay_scope(response, pd.DataFrame(delay_rows))
    return (
        response,
        trajectories,
        pd.DataFrame(residual_rows),
        pd.DataFrame(stability_rows),
        delays,
        pd.DataFrame(regime_rows),
    )


def _closed_loop_comparison(
    response: pd.DataFrame,
    condition_runs: Mapping[str, Mapping[str, Any]],
) -> pd.DataFrame:
    designed = response.loc[
        response["study_kind"].eq("designed_closed_loop_disturbance_probe")
    ].copy()
    keys = ["condition", "input_signal", "output_signal", "frequency_bin"]
    mrp = designed.loc[designed["policy"].eq(canonical.REFERENCE_POLICY)].set_index(keys)
    feedback = designed.loc[designed["policy"].eq(canonical.FEEDBACK_POLICY)].set_index(keys)
    dynamic_modulation_keys = {
        (
            str(row["condition"]),
            str(row["input_signal"]),
            int(row["frequency_bin"]),
        )
        for _, row in designed.loc[
            designed["policy"].eq(canonical.FEEDBACK_POLICY)
            & designed["output_signal"].astype(str).str.startswith("control_")
            & designed["valid_bin"].astype(bool)
        ].iterrows()
    }
    shared = mrp.index.intersection(feedback.index)
    rows: list[dict[str, Any]] = []
    for key in shared:
        left = mrp.loc[key]
        right = feedback.loc[key]
        condition_name = str(key[0])
        input_name = str(key[1])
        activation = condition_runs.get(condition_name, {}).get(
            "feedback_activation", {}
        )
        input_activation = activation.get("by_input", {}).get(input_name, {})
        activation_arms = input_activation.get("arms", {})
        baseline_feedback_active = bool(
            activation_arms.get("baseline", {}).get("physical_action_applied")
        )
        excited_feedback_active = bool(
            activation_arms.get("excited", {}).get("physical_action_applied")
        )
        all_arms_feedback_active = bool(
            input_activation.get("all_arms_physically_active")
            and baseline_feedback_active
            and excited_feedback_active
        )
        dynamic_feedback_modulation = (
            condition_name,
            input_name,
            int(key[3]),
        ) in dynamic_modulation_keys
        mrp_magnitude = float(left["elasticity_magnitude"] or 0.0)
        feedback_magnitude = float(right["elasticity_magnitude"] or 0.0)
        denominator_nonzero = mrp_magnitude > 1e-20
        ratio = (
            feedback_magnitude / mrp_magnitude if denominator_nonzero else None
        )
        attenuation_db = (
            20.0 * math.log10(max(float(ratio), 1e-30))
            if ratio is not None
            else None
        )
        small_signal_regime_compatible = bool(
            left.get("small_signal_local_claim", False)
            and right.get("small_signal_local_claim", False)
        )
        tested_amplitude_regime_compatible = bool(
            left.get("tested_amplitude_regime_trace_compatible", False)
            and right.get("tested_amplitude_regime_trace_compatible", False)
        )
        reliable = bool(
            all_arms_feedback_active
            and left["valid_bin"]
            and right["valid_bin"]
            and tested_amplitude_regime_compatible
            and denominator_nonzero
        )
        rows.append(
            {
                **dict(zip(keys, key, strict=True)),
                "frequency_cycles_per_day": float(left["frequency_cycles_per_day"]),
                "period_days": float(left["period_days"]),
                "mrp_elasticity_magnitude": mrp_magnitude,
                "v2_elasticity_magnitude": feedback_magnitude,
                "feedback_elasticity_magnitude": feedback_magnitude,
                "mrp_denominator_nonzero": denominator_nonzero,
                "v2_over_mrp_magnitude_ratio": ratio,
                "feedback_over_mrp_magnitude_ratio": ratio,
                "v2_minus_mrp_attenuation_db": attenuation_db,
                "feedback_minus_mrp_attenuation_db": attenuation_db,
                "mrp_phase_deg": left["phase_deg"],
                "v2_phase_deg": right["phase_deg"],
                "feedback_phase_deg": right["phase_deg"],
                "phase_difference_deg": (
                    (
                        float(right["phase_deg"])
                        - float(left["phase_deg"])
                        + 180.0
                    )
                    % 360.0
                    - 180.0
                    if pd.notna(right["phase_deg"]) and pd.notna(left["phase_deg"])
                    else None
                ),
                "mrp_coherence": float(left["coherence"]),
                "v2_coherence": float(right["coherence"]),
                "feedback_coherence": float(right["coherence"]),
                "baseline_feedback_physically_active": baseline_feedback_active,
                "excited_feedback_physically_active": excited_feedback_active,
                "all_arms_feedback_physically_active": all_arms_feedback_active,
                "feedback_physically_active": all_arms_feedback_active,
                "feedback_physically_active_semantics": (
                    "all_arms_feedback_physically_active"
                ),
                "small_signal_regime_compatible": small_signal_regime_compatible,
                "tested_amplitude_regime_compatible": (
                    tested_amplitude_regime_compatible
                ),
                "comparison_scope": TESTED_AMPLITUDE_LOCALITY_SCOPE,
                "small_signal_local_derivative_claimed": False,
                "active_set_invariance_verified": False,
                "amplitude_sweep_verified": False,
                "dynamic_feedback_modulation_identified": dynamic_feedback_modulation,
                "comparison_interpretation": (
                    "not_comparable_feedback_inactive_in_one_or_both_arms"
                    if not all_arms_feedback_active
                    else "hybrid_regime_switching_tested_amplitude"
                    if not tested_amplitude_regime_compatible
                    else "dynamic_feedback_modulation"
                    if dynamic_feedback_modulation
                    else "active_static_policy_conditioning"
                ),
                "reliable_comparison": reliable,
                "attenuation_observed": bool(
                    reliable and ratio is not None and ratio < 1.0
                ),
                "global_stability_claimed": False,
            }
        )
    return pd.DataFrame(rows)


def _resonance_table(response: pd.DataFrame, native_spectra: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not response.empty:
        for keys, group in response.groupby(
            ["study_kind", "condition", "policy", "input_signal", "output_signal"],
            sort=True,
        ):
            valid = group.loc[group["valid_bin"].astype(bool) & group["elasticity_magnitude"].notna()]
            if valid.empty:
                continue
            peak = valid.loc[valid["elasticity_magnitude"].astype(float).idxmax()]
            median = float(valid["elasticity_magnitude"].astype(float).median())
            rows.append(
                {
                    "study_kind": keys[0],
                    "condition": keys[1],
                    "policy": keys[2],
                    "input_signal": keys[3],
                    "output_signal": keys[4],
                    "peak_frequency_cycles_per_day": float(peak["frequency_cycles_per_day"]),
                    "peak_period_days": float(peak["period_days"]),
                    "peak_elasticity_magnitude": float(peak["elasticity_magnitude"]),
                    "peak_elasticity_db": float(peak["elasticity_db"]),
                    "peak_phase_deg": float(peak["phase_deg"]),
                    "peak_coherence": float(peak["coherence"]),
                    "peak_to_median_gain_ratio": float(peak["elasticity_magnitude"]) / max(median, 1e-30),
                    "causal_claimed": True,
                    "boundary_peak": False,
                    "peak_classification": (
                        "designed_local_line_peak"
                        if bool(peak.get("small_signal_local_claim", False))
                        else "designed_tested_amplitude_active_set_unverified_line_peak"
                        if bool(
                            peak.get(
                                "tested_amplitude_regime_trace_compatible",
                                False,
                            )
                        )
                        else "designed_hybrid_line_peak"
                    ),
                    "response_kind": str(peak.get("response_kind")),
                    "small_signal_local_claim": bool(
                        peak.get("small_signal_local_claim", False)
                    ),
                    "isolated_lti_frf_claimed": False,
                }
            )
    if not native_spectra.empty:
        for keys, group in native_spectra.groupby(["source_run", "output_signal"], sort=True):
            selected = group.loc[group["period_days"].between(2.0, 400.0, inclusive="both")]
            if selected.empty:
                continue
            peak = selected.loc[selected["output_psd_normalized"].astype(float).idxmax()]
            minimum_frequency = float(
                selected["frequency_cycles_per_day"].astype(float).min()
            )
            boundary_peak = bool(
                math.isclose(
                    float(peak["frequency_cycles_per_day"]),
                    minimum_frequency,
                    rel_tol=1e-9,
                    abs_tol=1e-12,
                )
            )
            rows.append(
                {
                    "study_kind": "native_observational_spectrum",
                    "condition": keys[0],
                    "policy": "mrp_native",
                    "input_signal": str(peak["input_signal"]),
                    "output_signal": keys[1],
                    "peak_frequency_cycles_per_day": float(peak["frequency_cycles_per_day"]),
                    "peak_period_days": float(peak["period_days"]),
                    "peak_elasticity_magnitude": float(peak["observational_gain"]),
                    "peak_elasticity_db": float(peak["observational_gain_db"]),
                    "peak_phase_deg": float(peak["observational_phase_deg"]),
                    "peak_coherence": float(peak["coherence"]),
                    "peak_to_median_gain_ratio": float(peak["output_psd_normalized"]) / max(
                        float(selected["output_psd_normalized"].median()), 1e-30
                    ),
                    "causal_claimed": False,
                    "boundary_peak": boundary_peak,
                    "peak_classification": (
                        "native_low_frequency_boundary_dominance"
                        if boundary_peak
                        else "native_internal_spectral_peak_candidate"
                    ),
                    "response_kind": "native_observational_spectrum",
                    "small_signal_local_claim": False,
                    "isolated_lti_frf_claimed": False,
                }
            )
    return pd.DataFrame(rows)


def _native_analysis(
    payload: Mapping[str, Any],
    *,
    repo_root: Path,
    config_dir: Path,
    output_root: Path,
    probe: Mapping[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    native = payload.get("native_spectra")
    if not isinstance(native, Mapping):
        raise CanonicalFrequencyContractError("native_spectra must be a JSON object.")
    runs = native.get("runs")
    if not isinstance(runs, list) or not runs:
        raise CanonicalFrequencyContractError("native_spectra.runs must be a non-empty list.")
    segment_days = _strict_positive_int(native.get("segment_days", 365), "native_spectra.segment_days", minimum=16)
    overlap = _strict_fraction(native.get("overlap_fraction", 0.5), "native_spectra.overlap_fraction", lower=0.0, upper=0.95)
    spectra_rows: list[pd.DataFrame] = []
    band_rows: list[pd.DataFrame] = []
    sources: list[dict[str, Any]] = []
    native_signal_groups = {
        "global_demand_qty": (
            "global_demand_qty",
            "global_order_qty",
            "global_production_qty",
            "global_supplier_shipments_qty",
            "global_inventory_qty",
            "global_backlog_qty",
            "global_service_level",
            "global_order_nervousness",
            "global_production_nervousness",
        ),
        "target_demand_qty": (
            "target_demand_qty",
            "target_production_qty",
            "target_finished_stock_qty",
            "target_backlog_qty",
            "target_service_level",
            "probe_supplier_shipments_qty",
            "probe_destination_arrivals_qty",
            "probe_supplier_stock_qty",
            "probe_supplier_utilization",
        ),
    }
    for index, raw in enumerate(runs):
        if not isinstance(raw, Mapping):
            raise CanonicalFrequencyContractError(f"native_spectra.runs[{index}] must be an object.")
        name = str(raw.get("name") or f"native_{index}")
        result_dir = _resolve_path(str(raw.get("result_dir") or ""), repo_root=repo_root, relative_to=config_dir)
        signals, _ = extract_frequency_signals(
            result_dir,
            target_finished_item_id=probe["target_finished_item_id"],
            probe_supplier_id=probe["supplier_id"],
            probe_item_id=probe["item_id"],
            probe_dst_node_id=probe["dst_node_id"],
        )
        for input_signal, signal_names in native_signal_groups.items():
            mapping = {
                signal: signals[signal].to_numpy(dtype=float)
                for signal in signal_names
            }
            estimate = welch_native_spectra(
                mapping,
                input_signal=input_signal,
                segment_days=segment_days,
                overlap_fraction=overlap,
            )
            estimate.insert(0, "source_run", name)
            estimate.insert(1, "source_result_dir", str(result_dir))
            spectra_rows.append(estimate)
            bands = native_band_amplification(estimate)
            bands.insert(0, "source_run", name)
            bands.insert(1, "input_signal", input_signal)
            band_rows.append(bands)
        daily_path = result_dir / "data" / "first_simulation_daily.csv"
        signal_source_names = (
            "first_simulation_daily.csv",
            "mrp_trace_daily.csv",
            "production_supplier_shipments_daily.csv",
            "production_demand_service_daily.csv",
            "production_output_products_daily.csv",
            "production_supplier_stocks_daily.csv",
            "production_supplier_capacity_daily.csv",
            "production_input_replenishment_arrivals_daily.csv",
            "canonical_closed_loop_commands.csv",
        )
        missing_required_sources = [
            filename
            for filename in signal_source_names[:8]
            if not (result_dir / "data" / filename).is_file()
        ]
        if missing_required_sources:
            raise CanonicalFrequencyContractError(
                f"Native source {name} is missing frequency signal inputs: "
                + ", ".join(missing_required_sources)
            )
        signal_source_files = []
        for filename in signal_source_names:
            source_path = result_dir / "data" / filename
            if source_path.is_file():
                signal_source_files.append(
                    {
                        "filename": filename,
                        "path": str(source_path),
                        "size_bytes": int(source_path.stat().st_size),
                        "sha256": _sha256(source_path),
                    }
                )
        sources.append(
            {
                "name": name,
                "result_dir": str(result_dir),
                "daily_kpi_sha256": _sha256(daily_path),
                "signal_source_file_count": int(len(signal_source_files)),
                "signal_source_files": signal_source_files,
                "day_count": int(len(signals)),
                "source_kind": str(raw.get("source_kind") or "etudecas_case_simulation_output"),
                "industrial_observation": False,
            }
        )
    spectra = pd.concat(spectra_rows, ignore_index=True)
    bands = pd.concat(band_rows, ignore_index=True)
    spectra.to_csv(output_root / "canonical_frequency_native_spectra.csv", index=False)
    bands.to_csv(output_root / "canonical_frequency_native_bands.csv", index=False)
    return spectra, bands, sources


def _write_actuator_schedule(
    path: Path,
    *,
    normalized: Mapping[str, Any],
    input_name: str,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    period = int(normalized["period_days"])
    periods = int(normalized["measured_periods"])
    peak = float(normalized["actuator_peak_fraction"])
    if input_name not in normalized["actuator_bins"]:
        raise CanonicalFrequencyContractError(f"Unknown actuator input {input_name!r}.")
    input_index = list(normalized["actuator_bins"]).index(input_name)
    signals = {
        input_name: peak
        * normalized_multisine(
            period,
            normalized["actuator_bins"][input_name],
            phase_seed=int(normalized["phase_seed"]) + (input_index + 1) * 1009,
        )
    }
    rows: list[dict[str, Any]] = []
    closed_loop_probe = (
        normalized.get("actuator_application_mode")
        == ACTUATOR_POST_FEEDBACK_ADDITIVE
    )
    for day in range(period * periods):
        phase_day = day % period
        row: dict[str, Any] = {name: "" for name in CONTROL_SCHEDULE_COLUMNS}
        row.update({"day": day, "policy": "frequency_actuator_probe"})
        for action in ACTION_FIELDS:
            if closed_loop_probe:
                # Blank action cells are absent actions.  This keeps the
                # closed-loop probe truly SISO in the engine audit, whereas
                # the historical open-loop schedule retains its exact full
                # neutral overlay below.
                neutral = ""
            elif action == "lead_time_adjustment_days":
                neutral = 0
            elif action == "expedite_level":
                neutral = 0.0
            else:
                neutral = 1.0
            row[action] = neutral
        for action, signal in signals.items():
            row[action] = 1.0 + float(signal[phase_day])
        rows.append(row)
    frame = pd.DataFrame(rows, columns=CONTROL_SCHEDULE_COLUMNS)
    frame.to_csv(path, index=False)
    return frame, signals


def _actuator_realization_evidence(
    ledger_path: Path,
    *,
    input_name: str,
    measured_days: int,
) -> dict[str, Any]:
    """Separate requested/effective commands from realized physical volume."""

    required = (
        "day",
        "action",
        "requested",
        "effective",
        "executed_control_volume_qty",
    )
    ledger = pd.read_csv(ledger_path, usecols=list(required))
    selected = ledger.loc[ledger["action"].astype(str).eq(str(input_name))].copy()
    selected["day"] = pd.to_numeric(selected["day"], errors="raise").astype(int)
    selected = selected.loc[selected["day"].between(0, int(measured_days) - 1)]
    if selected.empty:
        raise CanonicalFrequencyContractError(
            f"{input_name}: no matching rows in the physical action ledger."
        )
    for field in ("requested", "effective", "executed_control_volume_qty"):
        selected[field] = pd.to_numeric(selected[field], errors="coerce")
    requested_days = selected.groupby("day")["requested"].apply(
        lambda values: bool((values.sub(1.0).abs() > 1e-12).any())
    )
    effective_days = selected.groupby("day")["effective"].apply(
        lambda values: bool((values.sub(1.0).abs() > 1e-12).any())
    )
    realized_by_day = selected.groupby("day")["executed_control_volume_qty"].sum(
        min_count=1
    )
    realized_positive = realized_by_day.fillna(0.0).gt(1e-12)
    return {
        "action": str(input_name),
        "ledger_path": str(ledger_path),
        "ledger_sha256": _sha256(ledger_path),
        "ledger_action_row_count": int(len(selected)),
        "ledger_action_day_count": int(selected["day"].nunique()),
        "requested_non_neutral_day_count": int(requested_days.sum()),
        "effective_non_neutral_day_count": int(effective_days.sum()),
        "realized_positive_volume_day_count": int(realized_positive.sum()),
        "realized_positive_volume_day_share": float(
            realized_positive.sum() / max(int(measured_days), 1)
        ),
        "realized_control_volume_qty": float(realized_by_day.fillna(0.0).sum()),
        "realized_volume_semantics": (
            "physical_volume_executed_on_objects_matched_by_the_command_not_"
            "incremental_causal_volume"
        ),
    }


def _closed_loop_probe_realization_evidence(
    result_dir: Path,
    *,
    input_name: str,
    measured_days: int,
) -> dict[str, Any]:
    """Audit the independent probe separately from the feedback command.

    The ordinary action ledger contains the composed command in this mode, so
    non-neutral ledger rows cannot distinguish controller action from probe
    action.  The dedicated composition sidecar is therefore the source of
    truth for the injected instrumental signal.
    """

    composition_path = (
        result_dir / "data" / "canonical_control_probe_composition.csv"
    )
    required = (
        "day",
        "action",
        "feedback_effective",
        "probe_effective",
        "probe_delta",
        "composed_effective",
        "composition_clipped",
    )
    composition = pd.read_csv(composition_path, usecols=list(required))
    selected = composition.loc[
        composition["action"].astype(str).eq(str(input_name))
    ].copy()
    selected["day"] = pd.to_numeric(selected["day"], errors="raise").astype(int)
    selected = selected.loc[selected["day"].between(0, int(measured_days) - 1)]
    if selected.empty:
        raise CanonicalFrequencyContractError(
            f"{input_name}: no matching rows in the control-probe composition audit."
        )
    for field in (
        "feedback_effective",
        "probe_effective",
        "probe_delta",
        "composed_effective",
        "composition_clipped",
    ):
        selected[field] = pd.to_numeric(selected[field], errors="raise")
    probe_days = selected.groupby("day")["probe_delta"].apply(
        lambda values: bool(values.abs().gt(1e-12).any())
    )
    clipped_days = selected.groupby("day")["composition_clipped"].apply(
        lambda values: bool(values.astype(bool).any())
    )
    physical_ledger = _actuator_realization_evidence(
        result_dir / "data" / "canonical_action_ledger.csv",
        input_name=input_name,
        measured_days=measured_days,
    )
    return {
        "action": str(input_name),
        "composition_mode": ACTUATOR_POST_FEEDBACK_ADDITIVE,
        "composition_audit_path": str(composition_path),
        "composition_audit_sha256": _sha256(composition_path),
        "composition_row_count": int(len(selected)),
        "composition_day_count": int(selected["day"].nunique()),
        "probe_non_neutral_day_count": int(probe_days.sum()),
        "probe_non_neutral_day_share": float(
            probe_days.sum() / max(int(measured_days), 1)
        ),
        "composition_clipped_row_count": int(
            selected["composition_clipped"].astype(bool).sum()
        ),
        "composition_clipped_day_count": int(clipped_days.sum()),
        "probe_delta_min": float(selected["probe_delta"].min()),
        "probe_delta_max": float(selected["probe_delta"].max()),
        "feedback_and_probe_separated": True,
        "physical_action_ledger": physical_ledger,
    }


def _run_actuator_probe(
    *,
    normalized: Mapping[str, Any],
    root: Path,
    engine_path: Path,
    graph_path: Path,
    risk_path: Path,
    engine_args: Sequence[str],
    output_root: Path,
    input_name: str,
    application_mode: str = ACTUATOR_OPEN_LOOP_SCHEDULE,
    control_policy_path: Path | None = None,
    control_policy_flag: str | None = None,
) -> tuple[Path, Path, dict[str, np.ndarray], dict[str, Any]]:
    if application_mode not in ACTUATOR_APPLICATION_MODES:
        raise CanonicalFrequencyContractError(
            f"Unknown actuator application mode {application_mode!r}."
        )
    if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE:
        if control_policy_path is None or control_policy_flag not in {
            V2_CONTROL_FLAG,
            V3_CONTROL_FLAG,
        }:
            raise CanonicalFrequencyContractError(
                "post_feedback_additive requires an explicit V2/V3 control policy."
            )
    schedule_path = (
        output_root / "inputs" / f"canonical_frequency_actuator_schedule__{input_name}.csv"
    )
    schedule, signals = _write_actuator_schedule(
        schedule_path,
        normalized=normalized,
        input_name=input_name,
    )
    result_policy = (
        canonical.FEEDBACK_POLICY
        if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE
        else canonical.REFERENCE_POLICY
    )
    result_dir = (
        output_root
        / "actuator_probe"
        / "excited"
        / input_name
        / result_policy
        / f"seed_{normalized['seed']}"
    )
    if result_dir.exists() and any(result_dir.iterdir()):
        raise FileExistsError(f"Refusing to mix actuator artifacts with existing output: {result_dir}")
    command = [
        sys.executable,
        str(engine_path),
        "--input",
        str(graph_path),
        "--output-dir",
        str(result_dir),
        "--scenario-id",
        str(normalized["campaign"].get("scenario_id") or "scn:BASE"),
        "--days",
        str(normalized["days"]),
        "--seed",
        str(normalized["seed"]),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        *engine_args,
        "--common-random-numbers",
        "--no-supplier-state-dependent-risks",
        "--supplier-risk-events-csv",
        str(risk_path),
    ]
    if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE:
        command.extend(
            [
                str(control_policy_flag),
                str(control_policy_path),
                "--controller-prime-during-warmup",
                "--control-probe-schedule-csv",
                str(schedule_path),
            ]
        )
    else:
        command.extend(["--control-schedule-csv", str(schedule_path)])
    canonical._run_engine(command, cwd=root, result_dir=result_dir)
    summary_path = result_dir / "summaries" / "first_simulation_summary.json"
    summary = _read_json_object(summary_path, "actuator-probe engine summary")
    policy = summary.get("policy") if isinstance(summary.get("policy"), Mapping) else {}
    summary_key = (
        "control_probe"
        if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE
        else "control_schedule"
    )
    schedule_summary = policy.get(summary_key) if isinstance(policy, Mapping) else {}
    if not isinstance(schedule_summary, Mapping) or schedule_summary.get("enabled") is not True:
        raise CanonicalFrequencyContractError(
            f"The engine did not confirm the actuator {summary_key}."
        )
    if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE:
        ordinary_schedule = policy.get("control_schedule") if isinstance(policy, Mapping) else {}
        if isinstance(ordinary_schedule, Mapping) and ordinary_schedule.get("enabled") is True:
            raise CanonicalFrequencyContractError(
                "A post-feedback probe must not enable the ordinary control schedule."
            )
        if schedule_summary.get("composition_mode") != ACTUATOR_POST_FEEDBACK_ADDITIVE:
            raise CanonicalFrequencyContractError(
                "The engine did not confirm post-feedback additive composition."
            )
    resolved_actions = int(schedule_summary.get("resolved_actions", 0))
    if resolved_actions <= 0:
        raise CanonicalFrequencyContractError(
            "The actuator probe schedule produced no resolved physical action."
        )
    if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE:
        realization = _closed_loop_probe_realization_evidence(
            result_dir,
            input_name=input_name,
            measured_days=int(normalized["days"]),
        )
    else:
        realization = _actuator_realization_evidence(
            result_dir / "data" / "canonical_action_ledger.csv",
            input_name=input_name,
            measured_days=int(normalized["days"]),
        )
    metadata = {
        "command": command,
        "schedule_rows": int(len(schedule)),
        "schedule_sha256": _sha256(schedule_path),
        "engine_summary_sha256": _sha256(summary_path),
        "application_mode": application_mode,
        "command_injection_point": application_mode,
        "control_schedule_enabled": application_mode == ACTUATOR_OPEN_LOOP_SCHEDULE,
        "control_probe_enabled": application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE,
        "input_signal": input_name,
        "experiment_design": "separate_siso_campaign",
        "scheduled_actions": int(schedule_summary.get("scheduled_actions", 0)),
        "resolved_actions": resolved_actions,
        "unresolved_actions": int(schedule_summary.get("unresolved_actions", 0)),
        "requested_vs_realized": realization,
    }
    if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE:
        metadata.update(
            {
                "feedback_policy_enabled": True,
                "composition_mode": str(schedule_summary.get("composition_mode")),
                "composition_rows": int(schedule_summary.get("composition_rows", 0)),
                "clipped_action_count": int(
                    schedule_summary.get("clipped_action_count", 0)
                ),
                "feedback_command_export_modified": bool(
                    schedule_summary.get("feedback_command_export_modified", True)
                ),
            }
        )
    else:
        metadata["action_ledger_rows"] = int(
            schedule_summary.get("action_ledger_rows", 0)
        )
    return result_dir, schedule_path, signals, metadata


def _annotate_actuator_response_scope(
    estimate: pd.DataFrame,
    *,
    application_mode: str = ACTUATOR_OPEN_LOOP_SCHEDULE,
) -> pd.DataFrame:
    """Attach the finite-amplitude actuator scope without claiming locality."""

    if "valid_bin" not in estimate.columns:
        raise CanonicalFrequencyContractError(
            "Actuator response rows require a valid_bin column."
        )
    annotated = estimate.copy()
    annotated["regime_compatible_for_local_claim"] = True
    annotated["regime_compatible_for_local_claim_semantics"] = (
        LEGACY_REGIME_COMPATIBILITY_SEMANTICS
    )
    annotated["tested_amplitude_regime_trace_compatible"] = True
    annotated["amplitude_sweep_verified"] = False
    annotated["active_set_invariance_verified"] = False
    annotated["zero_amplitude_local_derivative_claimed"] = False
    annotated["locality_evidence_scope"] = TESTED_AMPLITUDE_LOCALITY_SCOPE
    if application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE:
        annotated["response_regime_scope"] = (
            "tested_amplitude_post_feedback_additive_closed_loop_"
            "active_set_unverified"
        )
    elif application_mode == ACTUATOR_OPEN_LOOP_SCHEDULE:
        annotated["response_regime_scope"] = (
            "tested_amplitude_open_loop_schedule_no_supervisory_regime_"
            "active_set_unverified"
        )
    else:
        raise CanonicalFrequencyContractError(
            f"Unknown actuator application mode {application_mode!r}."
        )
    annotated["tested_amplitude_harmonic_response"] = annotated[
        "valid_bin"
    ].astype(bool)
    # A valid command-to-output line at one amplitude is not a zero-amplitude
    # plant derivative.  Lot sizing, review calendars, capacity saturation and
    # other active sets are not audited here.
    annotated["small_signal_local_claim"] = False
    return annotated


def _analyse_actuator_probe(
    *,
    normalized: Mapping[str, Any],
    baseline_dir: Path,
    excited_dir: Path,
    actuator_signals: Mapping[str, np.ndarray],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    probe = normalized["probe"]
    application_mode = str(
        normalized.get("actuator_application_mode")
        or ACTUATOR_OPEN_LOOP_SCHEDULE
    )
    closed_loop_probe = application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE
    study_kind = (
        "designed_closed_loop_actuator_probe"
        if closed_loop_probe
        else "designed_open_loop_actuator_probe"
    )
    condition_name = str(
        normalized.get("actuator_condition_name") or "nominal_capacity"
    )
    policy_label = (
        "canonical_feedback_post_feedback_additive_probe"
        if closed_loop_probe
        else "mrp_reference_schedule_probe"
    )
    margin_status = (
        "closed_loop_probe_response_only_plant_margin_not_computed"
        if closed_loop_probe
        else "plant_frf_only_controller_margin_not_computed"
    )
    response_kind = (
        "empirical_closed_loop_probe_to_output_harmonic_line_response"
        if closed_loop_probe
        else "empirical_diagonal_actuator_harmonic_line_response"
    )
    baseline, units = extract_frequency_signals(
        baseline_dir,
        target_finished_item_id=probe["target_finished_item_id"],
        probe_supplier_id=probe["supplier_id"],
        probe_item_id=probe["item_id"],
        probe_dst_node_id=probe["dst_node_id"],
    )
    excited, _ = extract_frequency_signals(
        excited_dir,
        target_finished_item_id=probe["target_finished_item_id"],
        probe_supplier_id=probe["supplier_id"],
        probe_item_id=probe["item_id"],
        probe_dst_node_id=probe["dst_node_id"],
    )
    delta = excited.set_index("day") - baseline.set_index("day")
    periods = int(normalized["measured_periods"])
    period = int(normalized["period_days"])
    input_series = {name: np.tile(values, periods) for name, values in actuator_signals.items()}
    active_input_name = next(iter(input_series))
    output_names = (
        "global_service_level",
        "global_backlog_qty",
        "global_inventory_qty",
        "global_order_qty",
        "global_production_qty",
        "global_supplier_shipments_qty",
        "global_order_nervousness",
        "global_production_nervousness",
        "target_service_level",
        "target_backlog_qty",
        "target_production_qty",
        "probe_destination_arrivals_qty",
    )
    response_rows: list[pd.DataFrame] = []
    stability_rows: list[dict[str, Any]] = []
    delay_rows: list[dict[str, Any]] = []
    for output_signal in output_names:
        scale, basis = _response_scale(output_signal, baseline)
        output_delta = delta[output_signal].to_numpy(dtype=float)
        stability_rows.append(
            {
                "study_kind": study_kind,
                "condition": condition_name,
                "policy": policy_label,
                "input_signal": active_input_name,
                "output_signal": output_signal,
                "classical_margin_status": margin_status,
                **paired_segment_growth(output_delta, period_days=period, discard_periods=1),
            }
        )
        for input_name in input_series:
            bins = normalized["actuator_bins"][input_name]
            estimate = periodic_frf(
                input_series[input_name],
                output_delta,
                period_days=period,
                bins=bins,
                discard_periods=1,
                response_scale=scale,
                bootstrap_samples=int(normalized["bootstrap_samples"]),
                bootstrap_seed=int(normalized["phase_seed"]) + len(response_rows) * 65537,
                coherence_threshold=float(normalized["coherence_threshold"]),
            )
            estimate.insert(0, "study_kind", study_kind)
            estimate.insert(1, "condition", condition_name)
            estimate.insert(2, "policy", policy_label)
            estimate.insert(3, "input_signal", input_name)
            estimate.insert(4, "output_signal", output_signal)
            estimate.insert(5, "output_unit", units.get(output_signal, "unknown"))
            estimate.insert(6, "response_scale_basis", basis)
            estimate["designed_excitation"] = True
            estimate["experiment_design"] = "separate_siso_campaign"
            estimate["response_kind"] = response_kind
            estimate["isolated_lti_frf_claimed"] = False
            estimate["settling_periods_discarded"] = 1
            bounded = bool(stability_rows[-1]["bounded_repeated_response"])
            repeatable = bool(stability_rows[-1]["repeatable_periodic_response"])
            estimate["bounded_repeated_response"] = bounded
            estimate["repeatable_periodic_response"] = repeatable
            estimate["valid_bin"] = (
                estimate["valid_bin"].astype(bool) & bounded & repeatable
            )
            estimate = _annotate_actuator_response_scope(
                estimate,
                application_mode=application_mode,
            )
            estimate["global_stability_claimed"] = False
            response_rows.append(estimate)
            delay_rows.append(
                {
                    "study_kind": study_kind,
                    "condition": condition_name,
                    "policy": policy_label,
                    "input_signal": input_name,
                    "output_signal": output_signal,
                    **estimate_group_delay(estimate),
                }
            )
    trajectory = pd.DataFrame(
        {
            "condition": condition_name,
            "policy": policy_label,
            "experiment_input_signal": active_input_name,
            "day": baseline["day"].astype(int),
            "period_index": baseline["day"].astype(int) // period,
        }
    )
    for input_name, values in input_series.items():
        trajectory[input_name] = values
        trajectory[f"excitation_fraction__{input_name}"] = values
    for output_signal in output_names:
        trajectory[f"baseline__{output_signal}"] = baseline[output_signal]
        trajectory[f"excited__{output_signal}"] = excited[output_signal]
        trajectory[f"delta__{output_signal}"] = delta[output_signal].to_numpy(dtype=float)
    response = pd.concat(response_rows, ignore_index=True)
    delays = _annotate_delay_scope(response, pd.DataFrame(delay_rows))
    return (
        response,
        trajectory,
        pd.DataFrame(stability_rows),
        delays,
    )


def _result_dir(campaign_root: Path, policy: str, seed: int) -> Path:
    return campaign_root / policy / f"seed_{seed}"


def _warmup_boundary_evidence(
    run_dirs: Mapping[str, Path],
) -> dict[str, Any]:
    """Require byte-stable physical state at the measured J0 boundary."""

    hashes: dict[str, str] = {}
    component_hashes: dict[str, Mapping[str, Any]] = {}
    summaries: dict[str, str] = {}
    for label, run_dir in run_dirs.items():
        summary_path = run_dir / "summaries" / "first_simulation_summary.json"
        summary = _read_json_object(summary_path, f"warmup boundary summary for {label}")
        policy = summary.get("policy")
        boundary = policy.get("warmup_boundary_audit") if isinstance(policy, Mapping) else None
        if not isinstance(boundary, Mapping):
            raise CanonicalFrequencyContractError(
                f"Run {label} did not emit policy.warmup_boundary_audit."
            )
        core_hash = str(boundary.get("core_state_sha256") or "")
        components = boundary.get("component_sha256")
        if not core_hash or not isinstance(components, Mapping) or not components:
            raise CanonicalFrequencyContractError(
                f"Run {label} emitted an incomplete warmup boundary audit."
            )
        hashes[label] = core_hash
        component_hashes[label] = dict(components)
        summaries[label] = str(summary_path)
    core_match = len(set(hashes.values())) == 1
    component_match = len(
        {json.dumps(value, sort_keys=True) for value in component_hashes.values()}
    ) == 1
    if not core_match or not component_match:
        raise CanonicalFrequencyContractError(
            "Paired frequency runs do not share the exact physical warmup state at J0."
        )
    return {
        "status": "exact_match",
        "scope": "core_dynamic_engine_state_at_measured_j0",
        "all_core_state_hashes_match": core_match,
        "all_component_hashes_match": component_match,
        "core_state_sha256": next(iter(hashes.values())),
        "run_core_state_sha256": hashes,
        "summary_paths": summaries,
    }


def _demand_perturbation_evidence(
    *,
    baseline_root: Path,
    excited_root: Path,
    seed: int,
    schedule_metadata: Mapping[str, Any],
    measured_days: int,
) -> dict[str, Any]:
    """Validate that demand excitation is absent in baseline and measured-only in pairs."""

    expected_rows = int(schedule_metadata["row_count"])
    expected_hash = str(schedule_metadata["sha256"])
    expected_pairs = int(schedule_metadata["demand_pair_count"])
    if expected_rows != int(measured_days) * expected_pairs:
        raise CanonicalFrequencyContractError(
            "Demand excitation schedule does not cover every measured day/pair exactly once."
        )
    audit: dict[str, Any] = {}
    for policy_name in (canonical.REFERENCE_POLICY, canonical.FEEDBACK_POLICY):
        baseline_dir = _result_dir(baseline_root, policy_name, seed)
        excited_dir = _result_dir(excited_root, policy_name, seed)
        baseline_summary = _read_json_object(
            baseline_dir / "summaries" / "first_simulation_summary.json",
            f"baseline demand summary for {policy_name}",
        )
        baseline_policy = baseline_summary.get("policy")
        baseline_policy = baseline_policy if isinstance(baseline_policy, Mapping) else {}
        baseline_audit = baseline_dir / "data" / "canonical_demand_perturbations.csv"
        if "demand_perturbation" in baseline_policy or baseline_audit.exists():
            raise CanonicalFrequencyContractError(
                f"Baseline run {policy_name} unexpectedly contains a demand perturbation."
            )

        excited_summary_path = excited_dir / "summaries" / "first_simulation_summary.json"
        excited_summary = _read_json_object(
            excited_summary_path, f"excited demand summary for {policy_name}"
        )
        excited_policy = excited_summary.get("policy")
        excited_policy = excited_policy if isinstance(excited_policy, Mapping) else {}
        manifest = excited_policy.get("demand_perturbation")
        if not isinstance(manifest, Mapping) or manifest.get("enabled") is not True:
            raise CanonicalFrequencyContractError(
                f"Excited run {policy_name} did not confirm demand perturbation."
            )
        excited_audit = excited_dir / "data" / "canonical_demand_perturbations.csv"
        if not excited_audit.is_file():
            raise CanonicalFrequencyContractError(
                f"Excited run {policy_name} did not emit the demand perturbation audit."
            )
        rows = pd.read_csv(excited_audit)
        required = {"day", "node_id", "item_id", "status"}
        if rows.empty or not required.issubset(rows.columns):
            raise CanonicalFrequencyContractError(
                f"Excited run {policy_name} emitted an incomplete demand perturbation audit."
            )
        days = pd.to_numeric(rows["day"], errors="raise").astype(int)
        unique_keys = rows[["day", "node_id", "item_id"]].drop_duplicates()
        all_applied = rows["status"].astype(str).eq("applied").all()
        valid = (
            len(rows) == expected_rows
            and len(unique_keys) == expected_rows
            and int(days.min()) == 0
            and int(days.max()) == int(measured_days) - 1
            and all_applied
            and str(manifest.get("sha256") or "") == expected_hash
            and int(manifest.get("row_count", -1)) == expected_rows
            and int(manifest.get("applied_count", -1)) == expected_rows
            and int(manifest.get("warmup_application_count", -1)) == 0
        )
        if not valid:
            raise CanonicalFrequencyContractError(
                f"Excited run {policy_name} failed measured-only demand excitation validation."
            )
        audit[policy_name] = {
            "status": "complete_measured_only",
            "audit_csv": str(excited_audit),
            "audit_sha256": _sha256(excited_audit),
            "row_count": int(len(rows)),
            "unique_key_count": int(len(unique_keys)),
            "day_min": int(days.min()),
            "day_max": int(days.max()),
            "all_rows_applied": bool(all_applied),
            "warmup_application_count": 0,
            "summary_path": str(excited_summary_path),
        }
    return {
        "status": "validated",
        "baseline_has_no_perturbation": True,
        "schedule": dict(schedule_metadata),
        "policies": audit,
    }


def _feedback_activation_evidence(
    *,
    baseline_root: Path,
    excited_root: Path,
    seed: int,
) -> dict[str, Any]:
    """Require the V2 arms to contain causal, physically applied feedback."""

    arms: dict[str, Any] = {}
    for arm, campaign_root in (
        ("baseline", baseline_root),
        ("excited", excited_root),
    ):
        result_dir = _result_dir(campaign_root, canonical.FEEDBACK_POLICY, seed)
        summary_path = result_dir / "summaries" / "first_simulation_summary.json"
        summary = _read_json_object(summary_path, f"V2 activation summary for {arm}")
        policy = summary.get("policy")
        provider = policy.get("control_provider") if isinstance(policy, Mapping) else None
        if not isinstance(provider, Mapping):
            raise CanonicalFrequencyContractError(
                f"V2 {arm} run did not emit policy.control_provider evidence."
            )
        physical_count = int(provider.get("physically_applied_action_count", 0))
        scheduled_count = int(provider.get("scheduled_active_actions", 0))
        active = bool(
            provider.get("closed_loop_claimed") is True
            and provider.get("physical_action_applied") is True
            and physical_count > 0
            and scheduled_count > 0
        )
        arms[arm] = {
            "closed_loop_claimed": provider.get("closed_loop_claimed") is True,
            "causal_contract_satisfied": provider.get("causal_contract_satisfied") is True,
            "physical_action_applied": provider.get("physical_action_applied") is True,
            "physically_applied_action_count": physical_count,
            "scheduled_active_actions": scheduled_count,
            "active_command_row_count": int(provider.get("active_command_row_count", 0)),
            "final_regime": str(provider.get("final_regime") or ""),
            "final_policy": str(provider.get("final_policy") or ""),
            "summary_path": str(summary_path),
            "validated": active,
        }
    all_arms_active = all(bool(row["validated"]) for row in arms.values())
    return {
        "status": (
            "causal_physical_feedback_active_in_both_arms"
            if all_arms_active
            else "inactive_or_neutral_feedback_condition_not_closed_loop_comparable"
        ),
        "all_arms_physically_active": all_arms_active,
        "arms": arms,
    }


def _supplier_perturbation_application_evidence(
    *,
    excited_roots: Mapping[str, Path],
    excited_risks: Mapping[str, Mapping[str, Any]],
    seed: int,
    probe: Mapping[str, str],
    measured_days: int,
    period_days: int,
    discard_periods: int = 1,
) -> dict[str, Any]:
    """Match requested multipliers on every physically affected supplier event."""

    experiment_fields = {
        "supplier_availability_multiplier": {
            "risk_type": "availability",
            "audit_field": "availability_multiplier",
        },
        "supplier_lead_time_multiplier": {
            "risk_type": "lead_time",
            "audit_field": "lead_time_multiplier",
        },
    }
    selected_inputs = set(excited_roots)
    if selected_inputs != set(excited_risks):
        raise CanonicalFrequencyContractError(
            "Supplier perturbation roots and risk schedules must name the same inputs."
        )
    unsupported_inputs = sorted(selected_inputs - set(experiment_fields))
    if unsupported_inputs:
        raise CanonicalFrequencyContractError(
            "Supplier perturbation evidence received unsupported inputs: "
            + ", ".join(unsupported_inputs)
        )
    if not selected_inputs:
        return {
            "status": "not_requested_inputs_disabled",
            "enabled_supplier_input_signals": [],
            "applicable": False,
            "validation_performed": False,
            "serialization_absolute_tolerance": 5e-7,
            "experiments": {},
        }
    experiments: dict[str, Any] = {}
    for input_name, field_meta in experiment_fields.items():
        if input_name not in selected_inputs:
            continue
        schedule_path = Path(str(excited_risks[input_name]["path"]))
        schedule = pd.read_csv(schedule_path)
        expected = schedule.loc[
            schedule["risk_type"].astype(str).eq(str(field_meta["risk_type"]))
            & pd.to_numeric(schedule["start_day"], errors="raise").between(
                0, int(measured_days) - 1
            )
        ].copy()
        expected["day"] = pd.to_numeric(
            expected["start_day"], errors="raise"
        ).astype(int)
        expected["expected_multiplier"] = pd.to_numeric(
            expected["multiplier"], errors="raise"
        )
        if (
            len(expected) != int(measured_days)
            or expected["day"].nunique() != int(measured_days)
        ):
            raise CanonicalFrequencyContractError(
                f"{input_name}: requested supplier perturbation is not daily and complete."
            )
        expected = expected.set_index("day")["expected_multiplier"].sort_index()
        policies: dict[str, Any] = {}
        for policy in (canonical.REFERENCE_POLICY, canonical.FEEDBACK_POLICY):
            result_dir = _result_dir(Path(excited_roots[input_name]), policy, seed)
            audit_path = result_dir / "data" / "supplier_risk_events_applied_daily.csv"
            audit = pd.read_csv(audit_path)
            selected = audit.loc[
                audit["supplier_id"].astype(str).eq(str(probe["supplier_id"]))
                & audit["dst_node_id"].astype(str).eq(str(probe["dst_node_id"]))
                & audit["item_id"].astype(str).eq(str(probe["item_id"]))
            ].copy()
            selected["day"] = pd.to_numeric(
                selected["day"], errors="raise"
            ).astype(int)
            selected = selected.loc[
                selected["day"].between(0, int(measured_days) - 1)
            ]
            if selected.empty or selected["day"].duplicated().any():
                raise CanonicalFrequencyContractError(
                    f"{input_name}/{policy}: engine supplier-risk application audit is empty or duplicated."
                )
            actual = pd.to_numeric(
                selected.set_index("day")[str(field_meta["audit_field"])],
                errors="raise",
            ).sort_index()
            expected_on_applied_days = expected.reindex(actual.index)
            if expected_on_applied_days.isna().any():
                raise CanonicalFrequencyContractError(
                    f"{input_name}/{policy}: applied supplier-risk day lies outside the requested schedule."
                )
            maximum_error = float(
                np.max(
                    np.abs(
                        actual.to_numpy()
                        - expected_on_applied_days.to_numpy()
                    )
                )
            )
            exact_with_serialization_tolerance = bool(
                np.allclose(
                    actual.to_numpy(),
                    expected_on_applied_days.to_numpy(),
                    rtol=1e-9,
                    atol=5e-7,
                )
            )
            if not exact_with_serialization_tolerance:
                raise CanonicalFrequencyContractError(
                    f"{input_name}/{policy}: applied multipliers differ from the requested schedule."
                )
            period_count = int(measured_days) // int(period_days)
            applied_days_by_period = {
                str(index): int(
                    pd.Index(actual.index)[
                        (pd.Index(actual.index) // int(period_days)) == index
                    ].nunique()
                )
                for index in range(period_count)
            }
            analysed_periods = list(range(int(discard_periods), period_count))
            if not all(
                applied_days_by_period[str(index)] >= 1
                for index in analysed_periods
            ):
                raise CanonicalFrequencyContractError(
                    f"{input_name}/{policy}: no physical multiplier application in at least one analysed period."
                )
            policies[policy] = {
                "status": "requested_multiplier_matched_on_every_physical_application",
                "scheduled_day_count": int(len(expected)),
                "physically_applied_day_count": int(len(actual)),
                "day_min": int(actual.index.min()),
                "day_max": int(actual.index.max()),
                "physically_applied_days_by_period": applied_days_by_period,
                "analysed_period_indices": analysed_periods,
                "requested_unique_value_count": int(expected.nunique()),
                "applied_unique_value_count": int(actual.nunique()),
                "maximum_absolute_serialization_error": maximum_error,
                "audit_path": str(audit_path),
                "audit_sha256": _sha256(audit_path),
            }
        experiments[input_name] = {
            "requested_schedule_path": str(schedule_path),
            "requested_schedule_sha256": _sha256(schedule_path),
            "risk_type": str(field_meta["risk_type"]),
            "audit_field": str(field_meta["audit_field"]),
            "policies": policies,
        }
    return {
        "status": (
            "supplier_multisines_scheduled_daily_and_matched_on_all_physical_applications"
        ),
        "enabled_supplier_input_signals": [
            name for name in experiment_fields if name in selected_inputs
        ],
        "serialization_absolute_tolerance": 5e-7,
        "experiments": experiments,
    }


def _supplier_probe_reachability_evidence(
    *,
    baseline_root: Path,
    excited_roots: Mapping[str, Path] | None = None,
    seed: int,
    probe: Mapping[str, str],
    measured_days: int,
    period_days: int,
    discard_periods: int = 1,
) -> dict[str, Any]:
    """Require measured lane flow in every period retained for identification."""

    if int(measured_days) % int(period_days):
        raise CanonicalFrequencyContractError(
            "Supplier reachability requires a whole number of measured periods."
        )
    period_count = int(measured_days) // int(period_days)
    analysed_periods = list(range(int(discard_periods), period_count))
    if not analysed_periods:
        raise CanonicalFrequencyContractError(
            "Supplier reachability requires at least one analysed period."
        )
    minimum_days_per_period = 1
    run_dirs: dict[str, Path] = {
        f"baseline__{policy}": _result_dir(baseline_root, policy, seed)
        for policy in (canonical.REFERENCE_POLICY, canonical.FEEDBACK_POLICY)
    }
    for input_name, campaign_root in (excited_roots or {}).items():
        for policy in (canonical.REFERENCE_POLICY, canonical.FEEDBACK_POLICY):
            run_dirs[f"excited__{input_name}__{policy}"] = _result_dir(
                Path(campaign_root), policy, seed
            )

    runs: dict[str, Any] = {}
    failed: list[str] = []
    for label, result_dir in run_dirs.items():
        data_root = result_dir / "data"
        shipments_path = data_root / "production_supplier_shipments_daily.csv"
        arrivals_path = data_root / "production_input_replenishment_arrivals_daily.csv"
        shipments = pd.read_csv(shipments_path)
        arrivals = pd.read_csv(arrivals_path)
        shipment_rows = shipments.loc[
            shipments["src_node_id"].astype(str).eq(str(probe["supplier_id"]))
            & shipments["dst_node_id"].astype(str).eq(str(probe["dst_node_id"]))
            & shipments["item_id"].astype(str).eq(str(probe["item_id"]))
        ].copy()
        arrival_rows = arrivals.loc[
            arrivals["node_id"].astype(str).eq(str(probe["dst_node_id"]))
            & arrivals["item_id"].astype(str).eq(str(probe["item_id"]))
        ].copy()
        shipment_rows["day"] = pd.to_numeric(
            shipment_rows["day"], errors="raise"
        ).astype(int)
        arrival_rows["day"] = pd.to_numeric(
            arrival_rows["day"], errors="raise"
        ).astype(int)
        shipment_rows["quantity"] = pd.to_numeric(
            shipment_rows["shipped_qty"], errors="raise"
        )
        arrival_rows["quantity"] = pd.to_numeric(
            arrival_rows["arrived_qty"], errors="raise"
        )
        shipment_rows = shipment_rows.loc[
            shipment_rows["day"].between(0, int(measured_days) - 1)
        ].copy()
        arrival_rows = arrival_rows.loc[
            arrival_rows["day"].between(0, int(measured_days) - 1)
        ].copy()
        shipment_nonzero = shipment_rows.loc[shipment_rows["quantity"].gt(1e-12)]
        arrival_nonzero = arrival_rows.loc[arrival_rows["quantity"].gt(1e-12)]
        shipment_days_by_period = {
            str(index): int(
                shipment_nonzero.loc[
                    (shipment_nonzero["day"] // int(period_days)).eq(index), "day"
                ].nunique()
            )
            for index in range(period_count)
        }
        arrival_days_by_period = {
            str(index): int(
                arrival_nonzero.loc[
                    (arrival_nonzero["day"] // int(period_days)).eq(index), "day"
                ].nunique()
            )
            for index in range(period_count)
        }
        reachable = bool(
            all(
                shipment_days_by_period[str(index)] >= minimum_days_per_period
                and arrival_days_by_period[str(index)] >= minimum_days_per_period
                for index in analysed_periods
            )
        )
        if not reachable:
            failed.append(label)
        runs[label] = {
            "result_dir": str(result_dir),
            "shipment_total_qty_measured": float(shipment_rows["quantity"].sum()),
            "arrival_total_qty_measured": float(arrival_rows["quantity"].sum()),
            "nonzero_shipment_days_measured": int(shipment_nonzero["day"].nunique()),
            "nonzero_arrival_days_measured": int(arrival_nonzero["day"].nunique()),
            "nonzero_shipment_days_by_period": shipment_days_by_period,
            "nonzero_arrival_days_by_period": arrival_days_by_period,
            "all_analysed_periods_reachable": reachable,
            "shipments_sha256": _sha256(shipments_path),
            "arrivals_sha256": _sha256(arrivals_path),
        }
    if failed:
        raise CanonicalFrequencyContractError(
            "Selected supplier probe is inactive in at least one analysed period: "
            + ", ".join(failed)
        )
    reference = runs[f"baseline__{canonical.REFERENCE_POLICY}"]
    return {
        "status": "active_reachable_lane_in_every_analysed_period",
        "measurement_window": [0, int(measured_days) - 1],
        "analysed_period_indices": analysed_periods,
        "settling_periods_excluded": int(discard_periods),
        "minimum_nonzero_days_per_analysed_period": minimum_days_per_period,
        "shipment_total_qty": reference["shipment_total_qty_measured"],
        "arrival_total_qty": reference["arrival_total_qty_measured"],
        "nonzero_shipment_days": reference["nonzero_shipment_days_measured"],
        "nonzero_arrival_days": reference["nonzero_arrival_days_measured"],
        "measured_days": int(measured_days),
        "all_runs_reachable": True,
        "runs": runs,
    }


def _regime_persistence_evidence(
    *,
    baseline_root: Path,
    excited_root: Path,
    seed: int,
    intended_regime: str,
    period_days: int,
    measured_days: int,
) -> dict[str, Any]:
    """Audit whether a prescribed hybrid operating regime persists by period."""

    intended = str(intended_regime or "measured_not_forced").upper()
    gate_required = intended not in {"", "MEASURED_NOT_FORCED", "NOT_PRESPECIFIED"}
    arms: dict[str, Any] = {}
    for arm, campaign_root in (("baseline", baseline_root), ("excited", excited_root)):
        result_dir = _result_dir(campaign_root, canonical.FEEDBACK_POLICY, seed)
        path = result_dir / "data" / "canonical_closed_loop_observations.csv"
        frame = pd.read_csv(path, usecols=["day", "confirmed_regime"])
        if len(frame) != int(measured_days):
            raise CanonicalFrequencyContractError(
                f"V2 {arm} regime audit does not match the measured horizon."
            )
        regimes = frame["confirmed_regime"].astype(str).str.upper()
        shares = regimes.value_counts(normalize=True).to_dict()
        period_index = pd.to_numeric(frame["day"], errors="raise").astype(int) // int(period_days)
        intended_period_shares = [
            float(regimes.loc[period_index.eq(index)].eq(intended).mean())
            for index in sorted(period_index.unique())
        ]
        arms[arm] = {
            "dominant_regime": str(regimes.value_counts().index[0]),
            "regime_shares": {str(name): float(value) for name, value in shares.items()},
            "intended_regime_share": float(regimes.eq(intended).mean()) if gate_required else None,
            "intended_regime_share_by_period": intended_period_shares if gate_required else [],
            "observation_csv": str(path),
            "observation_sha256": _sha256(path),
        }
    persistent = bool(
        not gate_required
        or all(
            row["intended_regime_share"] >= 0.80
            and min(row["intended_regime_share_by_period"], default=0.0) >= 0.75
            for row in arms.values()
        )
    )
    if gate_required and not persistent:
        raise CanonicalFrequencyContractError(
            f"Intended regime {intended} is not persistent across repeated periods."
        )
    return {
        "status": (
            "persistent_intended_regime"
            if gate_required
            else "descriptive_regime_occupancy_no_prescribed_gate"
        ),
        "intended_regime": intended,
        "gate_required": gate_required,
        "persistent": persistent,
        "minimum_total_share": 0.80 if gate_required else None,
        "minimum_each_period_share": 0.75 if gate_required else None,
        "arms": arms,
    }


def _artifact_hashes(output_root: Path) -> dict[str, str]:
    names = (
        "canonical_frequency_native_spectra.csv",
        "canonical_frequency_native_bands.csv",
        "canonical_frequency_response.csv",
        "canonical_frequency_closed_loop_comparison.csv",
        "canonical_frequency_resonances.csv",
        "canonical_frequency_stability.csv",
        "canonical_frequency_delays.csv",
        "canonical_frequency_nonlinearity.csv",
        "canonical_frequency_regime_occupancy.csv",
        "canonical_frequency_excitation_audit.csv",
        "canonical_frequency_trajectories.csv",
        "canonical_frequency_report.md",
        "canonical_frequency_excitation_response.png",
        "canonical_frequency_bode_frf.png",
        "canonical_frequency_coherence.png",
        "canonical_frequency_resonances.png",
        "canonical_frequency_time_frequency.png",
        "canonical_frequency_stability.png",
        "canonical_frequency_artifact_ledger.csv",
        "provenance/source_snapshot_manifest.json",
    )
    return {name: _sha256(output_root / name) for name in names if (output_root / name).is_file()}


def _write_artifact_ledger(output_root: Path) -> dict[str, Any]:
    """Hash the complete package except the recursive protocol/ledger files."""

    ledger_path = output_root / "canonical_frequency_artifact_ledger.csv"
    excluded = {
        ledger_path.resolve(),
        (output_root / "canonical_frequency_protocol.json").resolve(),
        (output_root / "canonical_frequency_manifest.json").resolve(),
    }
    rows: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in output_root.rglob("*") if candidate.is_file()):
        if path.resolve() in excluded:
            continue
        rows.append(
            {
                "relative_path": path.relative_to(output_root).as_posix(),
                "size_bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        )
    with ledger_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("relative_path", "size_bytes", "sha256")
        )
        writer.writeheader()
        writer.writerows(rows)
    return {
        "path": str(ledger_path),
        "relative_path": ledger_path.relative_to(output_root).as_posix(),
        "sha256": _sha256(ledger_path),
        "row_count": int(len(rows)),
        "scope": (
            "all_package_files_except_protocol_manifest_and_recursive_ledger"
        ),
    }


def _write_provenance_snapshot(
    output_root: Path,
    *,
    repo_root: Path,
    sources: Mapping[str, Path],
) -> dict[str, Any]:
    """Copy exact study inputs/sources below the output and hash every copy."""

    provenance_root = output_root / "provenance"
    snapshot_root = provenance_root / "source_snapshot"
    snapshot_root.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    for label, raw_path in sources.items():
        source = Path(raw_path).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Provenance source does not exist: {source}")
        try:
            relative = source.relative_to(repo_root)
        except ValueError:
            relative = Path("external") / f"{label}__{source.name}"
        snapshot = snapshot_root / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, snapshot)
        source_hash = _sha256(source)
        snapshot_hash = _sha256(snapshot)
        if source_hash != snapshot_hash:
            raise CanonicalFrequencyContractError(
                f"Provenance snapshot hash mismatch for {source}."
            )
        entries.append(
            {
                "label": str(label),
                "source_path": str(source),
                "snapshot_path": str(snapshot),
                "snapshot_relative_path": snapshot.relative_to(
                    output_root
                ).as_posix(),
                "sha256": source_hash,
                "size_bytes": int(source.stat().st_size),
            }
        )
    manifest_path = provenance_root / "source_snapshot_manifest.json"
    metadata: dict[str, Any] = {
        "schema_version": "scan.frequency_source_snapshot.v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_root": str(snapshot_root),
        "source_hashes_verified_at_completion": False,
        "entry_count": int(len(entries)),
        "entries": entries,
        "git_at_capture": canonical._git_provenance(repo_root),
        "manifest_path": str(manifest_path),
        "manifest_relative_path": manifest_path.relative_to(
            output_root
        ).as_posix(),
    }
    manifest_path.write_text(
        json.dumps(_json_safe(metadata), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return metadata


def _finalize_provenance_snapshot(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Refuse publication if any snapshotted source drifted during execution."""

    result = dict(metadata)
    entries = [dict(row) for row in result.get("entries", [])]
    drifted: list[str] = []
    for row in entries:
        source = Path(str(row["source_path"]))
        snapshot = Path(str(row["snapshot_path"]))
        expected = str(row["sha256"])
        if (
            not source.is_file()
            or not snapshot.is_file()
            or _sha256(source) != expected
            or _sha256(snapshot) != expected
        ):
            drifted.append(str(row["label"]))
    if drifted:
        raise CanonicalFrequencyContractError(
            "Study sources changed during execution: " + ", ".join(drifted)
        )
    result["entries"] = entries
    result["source_hashes_verified_at_completion"] = True
    result["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest_path = Path(str(result["manifest_path"]))
    manifest_path.write_text(
        json.dumps(_json_safe(result), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    result["manifest_sha256"] = _sha256(manifest_path)
    return result


def run_frequency_study(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path | None = None,
    stage: str = "all",
    make_plots: bool | None = None,
) -> CanonicalFrequencyArtifacts:
    """Execute native/designed stages and write a self-contained protocol."""

    if stage not in {"native", "designed", "all"}:
        raise ValueError("stage must be native, designed or all")
    root = repo_root.resolve()
    config = config_path.resolve()
    payload = _read_json_object(config, "frequency-study config")
    normalized = validate_frequency_config(payload)
    campaign = normalized["campaign"]
    output = (
        output_root.resolve()
        if output_root is not None
        else _resolve_path(
            str(campaign.get("output_dir") or DEFAULT_OUTPUT_ROOT),
            repo_root=root,
            relative_to=config.parent,
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "inputs").mkdir(exist_ok=True)
    (output / "runs").mkdir(exist_ok=True)

    graph_value = str(campaign.get("graph") or "auto")
    if graph_value == "auto":
        graph_path = canonical.discover_canonical_graph(root, "auto")
        if graph_path is None:
            raise FileNotFoundError("No canonical graph candidate was discovered.")
    else:
        graph_path = _resolve_path(graph_value, repo_root=root, relative_to=config.parent)
    policy_path = _resolve_path(
        str(campaign.get("control_policy_json") or ""), repo_root=root, relative_to=config.parent
    )
    (
        control_policy_schema,
        control_policy_flag,
        control_policy_kind,
    ) = _control_policy_interface(policy_path)
    engine_path = _resolve_path(
        str(campaign.get("engine_script") or root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"),
        repo_root=root,
        relative_to=config.parent,
    )
    profile_args: tuple[str, ...] = ()
    profile_metadata: dict[str, Any] = {}
    profile_path: Path | None = None
    if campaign.get("engine_profile"):
        profile_path = _resolve_path(
            str(campaign["engine_profile"]), repo_root=root, relative_to=config.parent
        )
        profile_args, profile_metadata = canonical.load_canonical_engine_profile(root, str(profile_path))
    provenance_sources: dict[str, Path] = {
        "study_config": config,
        "study_runner": HERE,
        "frequency_analysis": HERE.parent / "frequency_analysis.py",
        "frequency_reporting": HERE.parent / "frequency_reporting.py",
        "canonical_closed_loop_runner": HERE.parent / "canonical_closed_loop.py",
        "canonical_graph": graph_path,
        "control_policy": policy_path,
        "engine_entrypoint": engine_path,
    }
    if profile_path is not None:
        provenance_sources["engine_profile"] = profile_path
    for source_path in sorted(HERE.parent.glob("*.py")):
        provenance_sources[f"scan_source__{source_path.stem}"] = source_path
    for source_path in sorted(
        (root / "etudecas" / "simulation" / "engine").glob("*.py")
    ):
        provenance_sources[f"engine_source__{source_path.stem}"] = source_path
    analysis_common_path = root / "etudecas" / "simulation" / "analysis_batch_common.py"
    if analysis_common_path.is_file():
        provenance_sources["simulation_analysis_batch_common"] = analysis_common_path
    provenance_snapshot = _write_provenance_snapshot(
        output,
        repo_root=root,
        sources=provenance_sources,
    )
    snapshot_paths = {
        str(row["label"]): str(row["snapshot_path"])
        for row in provenance_snapshot["entries"]
    }
    snapshot_relative_paths = {
        str(row["label"]): str(row["snapshot_relative_path"])
        for row in provenance_snapshot["entries"]
    }
    frequency_engine_args = (
        *profile_args,
        *normalized["engine_args"],
        "--mrp-demand-signal-smoothing-days",
        "1",
        "--warmup-days",
        str(normalized["warmup_days"]),
        "--warmup-profile-mode",
        "preperiod",
        "--no-restore-opening-stock-after-warmup",
        "--warmup-boundary-audit",
    )

    native_spectra = pd.DataFrame()
    native_bands = pd.DataFrame()
    native_sources: list[dict[str, Any]] = []
    if stage in {"native", "all"}:
        native_spectra, native_bands, native_sources = _native_analysis(
            payload,
            repo_root=root,
            config_dir=config.parent,
            output_root=output,
            probe=normalized["probe"],
        )

    response = pd.DataFrame()
    trajectories = pd.DataFrame()
    residual = pd.DataFrame()
    stability = pd.DataFrame()
    delays = pd.DataFrame()
    regime_occupancy = pd.DataFrame()
    condition_runs: dict[str, dict[str, Any]] = {}
    actuator_metadata: dict[str, Any] = {
        "enabled": False,
        "response_scope": ACTUATOR_RESPONSE_SCOPE,
        "small_signal_local_derivative_claimed": False,
        "amplitude_sweep_verified": False,
        "active_set_invariance_verified": False,
    }
    channel_signals = {
        name: float(normalized["peak_fraction"][name])
        * normalized_multisine(
            int(normalized["period_days"]),
            bins,
            phase_seed=int(normalized["phase_seed"]) + index * 10007,
        )
        for index, (name, bins) in enumerate(normalized["input_bins"].items())
    }
    excitation_path = output / "canonical_frequency_excitation_audit.csv"
    if stage in {"designed", "all"}:
        _write_excitation_audit(
            excitation_path, normalized=normalized, channel_signals=channel_signals
        )
        for condition in normalized["conditions"]:
            condition_name = str(condition["name"])
            input_root = output / "inputs" / condition_name
            baseline_graph = input_root / "canonical_frequency_graph_baseline.json"
            baseline_graph_meta = _write_graph_variant(
                graph_path,
                baseline_graph,
                period_days=int(normalized["period_days"]),
                demand_fraction=channel_signals["demand_multiplier"],
                excited=False,
                demand_scale_by_item=condition.get("demand_scale_by_item", {}),
            )
            excited_graph_meta = {
                **baseline_graph_meta,
                "variant": "same_operating_point_graph_as_paired_baseline",
                "exact_graph_hash_match": True,
            }
            demand_schedule = input_root / "canonical_frequency_demand_excited.csv"
            demand_schedule_meta = _write_demand_perturbation(
                demand_schedule,
                graph_path=baseline_graph,
                measured_days=int(normalized["days"]),
                period_days=int(normalized["period_days"]),
                demand_fraction=channel_signals["demand_multiplier"],
                target_item_id=normalized["probe"]["target_finished_item_id"],
            )
            baseline_risk = input_root / "canonical_frequency_risk_baseline.csv"
            baseline_risk_meta = _write_risk_events(
                baseline_risk,
                condition=condition,
                probe=normalized["probe"],
                warmup_days=int(normalized["warmup_days"]),
                measured_days=int(normalized["days"]),
                period_days=int(normalized["period_days"]),
                availability_fraction=channel_signals["supplier_availability_multiplier"],
                lead_time_fraction=channel_signals["supplier_lead_time_multiplier"],
                excited=False,
            )
            condition_root = output / "runs" / condition_name
            baseline_root = condition_root / "baseline"
            baseline_artifacts = canonical.run_canonical_closed_loop(
                repo_root=root,
                graph_path=baseline_graph,
                control_policy_path=policy_path,
                seeds=(normalized["seed"],),
                output_root=baseline_root,
                days=int(normalized["days"]),
                scenario_id=str(campaign.get("scenario_id") or "scn:BASE"),
                engine_script=engine_path,
                supplier_risk_events_path=baseline_risk,
                enable_state_dependent_risks=False,
                engine_extra_args=frequency_engine_args,
                feedback_engine_extra_args=("--controller-prime-during-warmup",),
                control_policy_flag=control_policy_flag,
                engine_profile_metadata=profile_metadata,
                make_plot=False,
            )
            baseline_probe_preflight = _supplier_probe_reachability_evidence(
                baseline_root=baseline_root,
                seed=int(normalized["seed"]),
                probe=normalized["probe"],
                measured_days=int(normalized["days"]),
                period_days=int(normalized["period_days"]),
                discard_periods=1,
            )
            excited_roots: dict[str, str] = {}
            excited_manifests: dict[str, str] = {}
            excited_risks: dict[str, dict[str, Any]] = {}
            feedback_by_input: dict[str, dict[str, Any]] = {}
            regime_by_input: dict[str, dict[str, Any]] = {}
            run_dirs = {
                f"baseline__{policy_name}": _result_dir(
                    baseline_root, policy_name, int(normalized["seed"])
                )
                for policy_name in (canonical.REFERENCE_POLICY, canonical.FEEDBACK_POLICY)
            }
            zero_signal = np.zeros(int(normalized["period_days"]), dtype=float)
            for input_name in normalized["enabled_input_signals"]:
                excited_root = condition_root / "excited" / input_name
                risk_path = input_root / f"canonical_frequency_risk_excited__{input_name}.csv"
                risk_meta = _write_risk_events(
                    risk_path,
                    condition=condition,
                    probe=normalized["probe"],
                    warmup_days=int(normalized["warmup_days"]),
                    measured_days=int(normalized["days"]),
                    period_days=int(normalized["period_days"]),
                    availability_fraction=(
                        channel_signals["supplier_availability_multiplier"]
                        if input_name == "supplier_availability_multiplier"
                        else zero_signal
                    ),
                    lead_time_fraction=(
                        channel_signals["supplier_lead_time_multiplier"]
                        if input_name == "supplier_lead_time_multiplier"
                        else zero_signal
                    ),
                    excited=input_name != "demand_multiplier",
                )
                extra_args: tuple[str, ...] = frequency_engine_args
                if input_name == "demand_multiplier":
                    extra_args = (
                        *frequency_engine_args,
                        "--demand-perturbation-csv",
                        str(demand_schedule),
                    )
                    risk_path = baseline_risk
                    risk_meta = baseline_risk_meta
                excited_artifacts = canonical.run_canonical_closed_loop(
                    repo_root=root,
                    graph_path=baseline_graph,
                    control_policy_path=policy_path,
                    seeds=(normalized["seed"],),
                    output_root=excited_root,
                    days=int(normalized["days"]),
                    scenario_id=str(campaign.get("scenario_id") or "scn:BASE"),
                    engine_script=engine_path,
                    supplier_risk_events_path=risk_path,
                    enable_state_dependent_risks=False,
                    engine_extra_args=extra_args,
                    feedback_engine_extra_args=("--controller-prime-during-warmup",),
                    control_policy_flag=control_policy_flag,
                    engine_profile_metadata=profile_metadata,
                    make_plot=False,
                )
                excited_roots[input_name] = str(excited_root)
                excited_manifests[input_name] = str(excited_artifacts.manifest_path)
                excited_risks[input_name] = risk_meta
                feedback_by_input[input_name] = _feedback_activation_evidence(
                    baseline_root=baseline_root,
                    excited_root=excited_root,
                    seed=int(normalized["seed"]),
                )
                regime_by_input[input_name] = _regime_persistence_evidence(
                    baseline_root=baseline_root,
                    excited_root=excited_root,
                    seed=int(normalized["seed"]),
                    intended_regime=str(condition.get("intended_regime") or ""),
                    period_days=int(normalized["period_days"]),
                    measured_days=int(normalized["days"]),
                )
                run_dirs.update(
                    {
                        f"excited__{input_name}__{policy_name}": _result_dir(
                            excited_root, policy_name, int(normalized["seed"])
                        )
                        for policy_name in (
                            canonical.REFERENCE_POLICY,
                            canonical.FEEDBACK_POLICY,
                        )
                    }
                )
            boundary_evidence = _warmup_boundary_evidence(run_dirs)
            if "demand_multiplier" in normalized["enabled_input_signals"]:
                demand_evidence = _demand_perturbation_evidence(
                    baseline_root=baseline_root,
                    excited_root=Path(excited_roots["demand_multiplier"]),
                    seed=int(normalized["seed"]),
                    schedule_metadata=demand_schedule_meta,
                    measured_days=int(normalized["days"]),
                )
            else:
                demand_evidence = {
                    "status": "not_requested_input_disabled",
                    "input_signal": "demand_multiplier",
                    "applicable": False,
                    "validation_performed": False,
                }
            probe_reachability = _supplier_probe_reachability_evidence(
                baseline_root=baseline_root,
                excited_roots={
                    name: Path(path) for name, path in excited_roots.items()
                },
                seed=int(normalized["seed"]),
                probe=normalized["probe"],
                measured_days=int(normalized["days"]),
                period_days=int(normalized["period_days"]),
                discard_periods=1,
            )
            supplier_inputs = tuple(
                name
                for name in normalized["enabled_input_signals"]
                if name
                in {
                    "supplier_availability_multiplier",
                    "supplier_lead_time_multiplier",
                }
            )
            if supplier_inputs:
                supplier_perturbation_application = (
                    _supplier_perturbation_application_evidence(
                        excited_roots={
                            name: Path(excited_roots[name])
                            for name in supplier_inputs
                        },
                        excited_risks={
                            name: excited_risks[name] for name in supplier_inputs
                        },
                        seed=int(normalized["seed"]),
                        probe=normalized["probe"],
                        measured_days=int(normalized["days"]),
                        period_days=int(normalized["period_days"]),
                        discard_periods=1,
                    )
                )
            else:
                supplier_perturbation_application = {
                    "status": "not_requested_inputs_disabled",
                    "enabled_supplier_input_signals": [],
                    "experiments": {},
                    "applicable": False,
                    "validation_performed": False,
                }
            any_active_input = any(
                bool(value["all_arms_physically_active"])
                for value in feedback_by_input.values()
            )
            condition_runs[condition_name] = {
                "baseline_root": str(baseline_root),
                "excited_roots": excited_roots,
                "baseline_manifest": str(baseline_artifacts.manifest_path),
                "excited_manifests": excited_manifests,
                "baseline_graph": baseline_graph_meta,
                "excited_graph": excited_graph_meta,
                "exact_graph_hash_match": (
                    baseline_graph_meta["sha256"] == excited_graph_meta["sha256"]
                ),
                "baseline_risk": baseline_risk_meta,
                "excited_risks": excited_risks,
                "demand_perturbation": demand_evidence,
                "warmup_boundary": boundary_evidence,
                "feedback_activation": {
                    "experiment_design": "separate_siso_campaigns",
                    "enabled_input_signals": list(
                        normalized["enabled_input_signals"]
                    ),
                    "any_input_with_both_arms_physically_active": any_active_input,
                    "by_input": feedback_by_input,
                },
                "supplier_probe_reachability": probe_reachability,
                "supplier_probe_baseline_preflight": baseline_probe_preflight,
                "supplier_perturbation_application": supplier_perturbation_application,
                "regime_persistence": regime_by_input,
            }

        if not any(
            bool(metadata["feedback_activation"]["any_input_with_both_arms_physically_active"])
            for metadata in condition_runs.values()
        ):
            raise CanonicalFrequencyContractError(
                "Every V2 operating condition was neutral/no-op; refusing to publish a closed-loop frequency campaign."
            )

        (
            response,
            trajectories,
            residual,
            stability,
            delays,
            regime_occupancy,
        ) = _analyse_designed_pairs(
            normalized=normalized,
            condition_runs=condition_runs,
            channel_signals=channel_signals,
            output_root=output,
        )
        if normalized["actuator_enabled"]:
            actuator_condition_name = str(normalized["actuator_condition_name"])
            actuator_condition_meta = condition_runs[actuator_condition_name]
            actuator_baseline_root = Path(actuator_condition_meta["baseline_root"])
            actuator_application_mode = str(
                normalized["actuator_application_mode"]
            )
            actuator_baseline_policy = (
                canonical.FEEDBACK_POLICY
                if actuator_application_mode == ACTUATOR_POST_FEEDBACK_ADDITIVE
                else canonical.REFERENCE_POLICY
            )
            baseline_dir = (
                actuator_baseline_root
                / actuator_baseline_policy
                / f"seed_{normalized['seed']}"
            )
            actuator_response_frames: list[pd.DataFrame] = []
            actuator_trajectory_frames: list[pd.DataFrame] = []
            actuator_stability_frames: list[pd.DataFrame] = []
            actuator_delay_frames: list[pd.DataFrame] = []
            actuator_experiments: dict[str, Any] = {}
            for actuator_input in normalized["actuator_bins"]:
                (
                    actuator_dir,
                    schedule_path,
                    actuator_signals,
                    experiment_metadata,
                ) = _run_actuator_probe(
                    normalized=normalized,
                    root=root,
                    engine_path=engine_path,
                    graph_path=Path(
                        actuator_condition_meta["baseline_graph"]["path"]
                    ),
                    risk_path=Path(
                        actuator_condition_meta["baseline_risk"]["path"]
                    ),
                    engine_args=frequency_engine_args,
                    output_root=output,
                    input_name=actuator_input,
                    application_mode=actuator_application_mode,
                    control_policy_path=policy_path,
                    control_policy_flag=control_policy_flag,
                )
                (
                    actuator_response,
                    actuator_trajectory,
                    actuator_stability,
                    actuator_delays,
                ) = _analyse_actuator_probe(
                    normalized=normalized,
                    baseline_dir=baseline_dir,
                    excited_dir=actuator_dir,
                    actuator_signals=actuator_signals,
                )
                experiment_metadata.update(
                    {
                        "result_dir": str(actuator_dir),
                        "schedule_path": str(schedule_path),
                        "warmup_boundary": _warmup_boundary_evidence(
                            {
                                (
                                    f"{actuator_condition_name}_baseline__"
                                    f"{actuator_baseline_policy}"
                                ): baseline_dir,
                                f"actuator_probe__{actuator_input}": actuator_dir,
                            }
                        ),
                        "detected_response_rows": int(
                            actuator_response["response_detected"].sum()
                        ),
                        "coherent_bounded_line_rows": int(
                            actuator_response["valid_bin"].sum()
                        ),
                        "coherent_repeatable_line_rows": int(
                            actuator_response["valid_bin"].sum()
                        ),
                        "growth_diagnostic_rows": int(
                            actuator_stability["status"]
                            .eq("period_to_period_growth_detected")
                            .sum()
                        ),
                        "nonstationary_diagnostic_rows": int(
                            actuator_stability["status"]
                            .eq("period_to_period_nonstationarity_detected")
                            .sum()
                        ),
                    }
                )
                actuator_experiments[actuator_input] = experiment_metadata
                actuator_response_frames.append(actuator_response)
                actuator_trajectory_frames.append(actuator_trajectory)
                actuator_stability_frames.append(actuator_stability)
                actuator_delay_frames.append(actuator_delays)
            actuator_response_all = pd.concat(
                actuator_response_frames, ignore_index=True
            )
            actuator_trajectory_all = pd.concat(
                actuator_trajectory_frames, ignore_index=True
            )
            actuator_stability_all = pd.concat(
                actuator_stability_frames, ignore_index=True
            )
            actuator_delays_all = pd.concat(actuator_delay_frames, ignore_index=True)
            actuator_detected = int(actuator_response_all["response_detected"].sum())
            actuator_coherent = int(actuator_response_all["valid_bin"].sum())
            actuator_growth = int(
                actuator_stability_all["status"]
                .eq("period_to_period_growth_detected")
                .sum()
            )
            actuator_nonstationary = int(
                actuator_stability_all["status"]
                .eq("period_to_period_nonstationarity_detected")
                .sum()
            )
            response = pd.concat([response, actuator_response_all], ignore_index=True)
            trajectories = pd.concat(
                [trajectories, actuator_trajectory_all], ignore_index=True
            )
            stability = pd.concat([stability, actuator_stability_all], ignore_index=True)
            delays = pd.concat([delays, actuator_delays_all], ignore_index=True)
            actuator_metadata = {
                "enabled": True,
                "experiment_design": "separate_siso_campaigns",
                "application_mode": actuator_application_mode,
                "baseline_condition": actuator_condition_name,
                "baseline_policy": actuator_baseline_policy,
                "response_scope": ACTUATOR_RESPONSE_SCOPE,
                "small_signal_local_derivative_claimed": False,
                "amplitude_sweep_verified": False,
                "active_set_invariance_verified": False,
                "boundary_reference_run": str(baseline_dir),
                "experiments": actuator_experiments,
                "detected_response_rows": actuator_detected,
                "tested_amplitude_valid_line_rows": actuator_coherent,
                "small_signal_local_derivative_rows": 0,
                "coherent_bounded_line_rows": actuator_coherent,
                "coherent_repeatable_line_rows": actuator_coherent,
                "growth_diagnostic_rows": actuator_growth,
                "nonstationary_diagnostic_rows": actuator_nonstationary,
                "identification_status": (
                    "coherent_repeatable_empirical_actuator_line_response_identified"
                    if actuator_coherent > 0
                    else "no_coherent_repeatable_actuator_line_response_identified"
                ),
            }

        response.to_csv(output / "canonical_frequency_response.csv", index=False)
        trajectories.to_csv(output / "canonical_frequency_trajectories.csv", index=False)
        residual.to_csv(output / "canonical_frequency_nonlinearity.csv", index=False)
        stability.to_csv(output / "canonical_frequency_stability.csv", index=False)
        delays.to_csv(output / "canonical_frequency_delays.csv", index=False)
        regime_occupancy.to_csv(output / "canonical_frequency_regime_occupancy.csv", index=False)

    closed_loop_comparison = (
        _closed_loop_comparison(response, condition_runs)
        if not response.empty
        else pd.DataFrame()
    )
    resonances = _resonance_table(response, native_spectra)
    if not closed_loop_comparison.empty:
        closed_loop_comparison.to_csv(
            output / "canonical_frequency_closed_loop_comparison.csv", index=False
        )
    if not resonances.empty:
        resonances.to_csv(output / "canonical_frequency_resonances.csv", index=False)

    plot_status = "disabled"
    plot_paths: list[Path] = []
    report_path: Path | None = None
    selected_plots = bool(payload.get("reporting", {}).get("plots", True)) if make_plots is None else bool(make_plots)
    try:
        from etudecas.prototypes.scan_2027_risk_control.frequency_reporting import (
            write_frequency_report,
            write_frequency_figures,
        )

        report_path = write_frequency_report(
            output,
            native_spectra=native_spectra,
            native_bands=native_bands,
            response=response,
            closed_loop_comparison=closed_loop_comparison,
            resonances=resonances,
            stability=stability,
            residual=residual,
            regime_occupancy=regime_occupancy,
            normalized_config=normalized,
            delays=delays,
            controller_schema_version=control_policy_schema,
        )
        if selected_plots:
            plot_paths = write_frequency_figures(
                output,
                native_spectra=native_spectra,
                native_bands=native_bands,
                response=response,
                closed_loop_comparison=closed_loop_comparison,
                resonances=resonances,
                stability=stability,
                trajectories=trajectories,
                controller_schema_version=control_policy_schema,
            )
            plot_status = "written"
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("matplotlib"):
            plot_status = "matplotlib_unavailable"
        else:
            raise

    provenance_snapshot = _finalize_provenance_snapshot(provenance_snapshot)
    artifact_ledger = _write_artifact_ledger(output)

    feedback_input_flags = [
        bool(input_metadata.get("all_arms_physically_active"))
        for metadata in condition_runs.values()
        for input_metadata in metadata.get("feedback_activation", {})
        .get("by_input", {})
        .values()
    ]
    all_feedback_conditions_active = bool(feedback_input_flags) and all(
        feedback_input_flags
    )
    any_feedback_condition_active = any(feedback_input_flags)
    reliable_comparison_count = (
        int(closed_loop_comparison["reliable_comparison"].sum())
        if not closed_loop_comparison.empty
        else 0
    )
    attenuated_comparison_count = (
        int(
            closed_loop_comparison.loc[
                closed_loop_comparison["reliable_comparison"].astype(bool),
                "attenuation_observed",
            ].sum()
        )
        if not closed_loop_comparison.empty
        else 0
    )
    dynamic_reliable_count = (
        int(
            (
                closed_loop_comparison["reliable_comparison"].astype(bool)
                & closed_loop_comparison[
                    "dynamic_feedback_modulation_identified"
                ].astype(bool)
            ).sum()
        )
        if not closed_loop_comparison.empty
        else 0
    )
    dynamic_attenuated_count = (
        int(
            (
                closed_loop_comparison["reliable_comparison"].astype(bool)
                & closed_loop_comparison[
                    "dynamic_feedback_modulation_identified"
                ].astype(bool)
                & closed_loop_comparison["attenuation_observed"].astype(bool)
            ).sum()
        )
        if not closed_loop_comparison.empty
        else 0
    )
    legacy_v2_publication = (
        control_policy_schema == V2_CONTROL_POLICY_SCHEMA_VERSION
    )
    feedback_comparison_label = (
        "V2/MRP" if legacy_v2_publication else "feedback/MRP"
    )
    feedback_policy_comparison_claim = bool(
        any_feedback_condition_active and reliable_comparison_count > 0
    )
    dynamic_feedback_attenuation_claim = bool(
        any_feedback_condition_active and dynamic_attenuated_count > 0
    )
    controller_limitation = (
        "The V2 controller is hybrid and switched; a single global Bode, pole set or "
        "classical phase margin is not defined."
        if legacy_v2_publication
        else "The adaptive feedback controller combines hybrid supervisory switching "
        "with continuous state-dependent modulation; a single global Bode, pole set "
        "or classical phase margin is not defined."
    )

    protocol: dict[str, Any] = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": f"complete_{stage}",
        "sample_period_days": 1,
        "measured_days": int(normalized["days"]),
        "coherence_threshold": float(normalized["coherence_threshold"]),
        "enabled_designed_input_signals": list(
            normalized["enabled_input_signals"]
        ),
        "study_scope": "native_descriptive_plus_local_designed_frequency_identification",
        "scientific_claim": (
            "Designed paired empirical diagonal harmonic-line responses and "
            f"{feedback_comparison_label} attenuation "
            "are local to the tested operating conditions; native spectra are observational. "
            "No isolated LTI FRF, global stability, or industrial causal claim is made."
        ),
        "config": {
            "path": str(config),
            "snapshot_path": snapshot_paths["study_config"],
            "snapshot_relative_path": snapshot_relative_paths["study_config"],
            "sha256": _sha256(config),
            "schema_version": CONFIG_SCHEMA_VERSION,
        },
        "runner": {
            "path": str(HERE),
            "snapshot_path": snapshot_paths["study_runner"],
            "snapshot_relative_path": snapshot_relative_paths["study_runner"],
            "sha256": _sha256(HERE),
        },
        "analysis_source": {
            "path": str(HERE.parent / "frequency_analysis.py"),
            "snapshot_path": snapshot_paths["frequency_analysis"],
            "snapshot_relative_path": snapshot_relative_paths[
                "frequency_analysis"
            ],
            "sha256": _sha256(HERE.parent / "frequency_analysis.py"),
        },
        "graph_source": {
            "path": str(graph_path),
            "snapshot_path": snapshot_paths["canonical_graph"],
            "snapshot_relative_path": snapshot_relative_paths["canonical_graph"],
            "sha256": _sha256(graph_path),
        },
        "engine": {
            "path": str(engine_path),
            "snapshot_path": snapshot_paths["engine_entrypoint"],
            "snapshot_relative_path": snapshot_relative_paths["engine_entrypoint"],
            "sha256": _sha256(engine_path),
        },
        "controller": {
            "path": str(policy_path),
            "snapshot_path": snapshot_paths["control_policy"],
            "snapshot_relative_path": snapshot_relative_paths["control_policy"],
            "sha256": _sha256(policy_path),
            "schema_version": control_policy_schema,
            "engine_flag": control_policy_flag,
            "kind": control_policy_kind,
        },
        "provenance_snapshot": provenance_snapshot,
        "artifact_ledger": artifact_ledger,
        "sampling": {
            "sample_interval_days": 1,
            "nyquist_frequency_cycles_per_day": 0.5,
            "nyquist_period_days": 2.0,
            "designed_period_days": int(normalized["period_days"]),
            "measured_periods": int(normalized["measured_periods"]),
            "warmup_periods_config_value": int(normalized["warmup_periods"]),
            "warmup_periods_equivalent": float(
                normalized["warmup_periods_equivalent"]
            ),
            "measured_days": int(normalized["days"]),
            "warmup_days": int(normalized["warmup_days"]),
            "frequency_resolution_cycles_per_day": 1.0 / int(normalized["period_days"]),
            "supplier_delay_phase_unwrap_bound_days": normalized[
                "supplier_delay_phase_unwrap_bound_days"
            ],
            "supplier_delay_required_unaliased": bool(
                normalized["require_unaliased_supplier_delay"]
            ),
            "supplier_delay_phase_bound_check_applied": bool(
                normalized["require_unaliased_supplier_delay"]
                and "supplier_lead_time_multiplier"
                in normalized["enabled_input_signals"]
            ),
        },
        "designed_excitation": {
            "type": "separate_siso_random_phase_periodic_multisine_campaigns",
            "simultaneous_disturbance_inputs": False,
            "settling_periods_discarded": 1,
            "input_bins": {name: list(values) for name, values in normalized["input_bins"].items()},
            "available_input_signals": list(normalized["input_bins"]),
            "enabled_input_signals": list(normalized["enabled_input_signals"]),
            "disabled_input_signals": [
                name
                for name in normalized["input_bins"]
                if name not in normalized["enabled_input_signals"]
            ],
            "executed_input_bins": {
                name: list(normalized["input_bins"][name])
                for name in normalized["enabled_input_signals"]
            },
            "peak_fraction": normalized["peak_fraction"],
            "phase_seed": int(normalized["phase_seed"]),
            "coherence_threshold": float(normalized["coherence_threshold"]),
            "bootstrap_samples": int(normalized["bootstrap_samples"]),
            "uncertainty_interval_kind": (
                "period_resampling_percentile_interval_not_coverage_calibrated"
            ),
            "nominal_95_percent_coverage_claimed": False,
            "synthetic_designed_excitation": True,
            "paired_baseline_subtraction": True,
            "state_dependent_risks_disabled_during_identification": True,
            "odd_dft_lines_only": True,
            "quadratic_intermodulation_on_excited_lines": False,
            "quadratic_nonlinearity_detection_lines": "unexcited_even_dft_lines",
            "trajectory_input_column_semantics": (
                "columns named *_multiplier are fractional deviations around zero; "
                "the exact physical multipliers are in canonical_frequency_excitation_audit.csv"
            ),
        },
        "supplier_probe": dict(normalized["probe"]),
        "operating_conditions": normalized["conditions"],
        "condition_runs": condition_runs,
        "feedback_activation": {
            "required_for_closed_loop_label": True,
            "any_condition_with_both_arms_physically_active": any_feedback_condition_active,
            "all_conditions_and_arms_physically_active": all_feedback_conditions_active,
        },
        "actuator_probe": actuator_metadata,
        "native_sources": native_sources,
        "evidence_counts": {
            "native_spectral_rows": int(len(native_spectra)),
            "native_band_rows": int(len(native_bands)),
            "designed_line_response_rows": int(len(response)),
            "designed_frf_rows": int(len(response)),
            "detected_response_rows": (
                int(response["response_detected"].sum()) if not response.empty else 0
            ),
            "coherence_threshold_pass_rows": (
                int(
                    pd.to_numeric(response["coherence"], errors="coerce")
                    .ge(float(normalized["coherence_threshold"]))
                    .sum()
                )
                if not response.empty
                else 0
            ),
            "valid_designed_rows": (
                int(response["valid_bin"].sum()) if not response.empty else 0
            ),
            "tested_amplitude_valid_rows": (
                int(
                    response.get(
                        "tested_amplitude_harmonic_response",
                        pd.Series(False, index=response.index),
                    )
                    .fillna(False)
                    .astype(bool)
                    .sum()
                )
                if not response.empty
                else 0
            ),
            "tested_amplitude_regime_trace_compatible_rows": (
                int(
                    response.get(
                        "tested_amplitude_regime_trace_compatible",
                        pd.Series(False, index=response.index),
                    )
                    .fillna(False)
                    .astype(bool)
                    .sum()
                )
                if not response.empty
                else 0
            ),
            "regime_compatible_small_signal_rows": (
                int(response["small_signal_local_claim"].sum())
                if not response.empty
                else 0
            ),
            "small_signal_local_derivative_rows": (
                int(response["small_signal_local_claim"].sum())
                if not response.empty
                else 0
            ),
            "closed_loop_comparison_rows": int(len(closed_loop_comparison)),
            "reliable_closed_loop_comparison_rows": reliable_comparison_count,
            "attenuated_closed_loop_comparison_rows": attenuated_comparison_count,
            "dynamic_feedback_reliable_rows": dynamic_reliable_count,
            "dynamic_feedback_attenuated_rows": dynamic_attenuated_count,
            "resonance_rows": int(len(resonances)),
            "stability_diagnostic_rows": int(len(stability)),
        },
        "margin_contract": {
            "controller_kind": (
                "hybrid_supervisory_threshold_controller"
                if legacy_v2_publication
                else control_policy_kind
            ),
            "classical_gain_margin": "not_identifiable_without_continuous_local_loop_transfer",
            "classical_phase_margin": "not_identifiable_without_continuous_local_loop_transfer",
            "replacement_diagnostics": [
                "paired_empirical_closed_loop_attenuation",
                "coherence",
                "repeated_period_rms_growth",
                "residual_spectral_energy",
            ],
        },
        "claims": {
            "native_spectral_description": bool(not native_spectra.empty),
            "designed_empirical_diagonal_line_response": bool(not response.empty),
            "designed_response_scope": DESIGNED_RESPONSE_SCOPE,
            "tested_amplitude_response_measured": bool(not response.empty),
            "small_signal_local_derivative_claimed": False,
            "amplitude_sweep_verified": False,
            "active_set_invariance_verified": False,
            "isolated_lti_frf_claimed": False,
            "physical_closed_loop_v2_active": any_feedback_condition_active,
            "feedback_physical_closed_loop_active": any_feedback_condition_active,
            "v2_policy_conditioned_frequency_comparison": (
                feedback_policy_comparison_claim
            ),
            "feedback_policy_conditioned_frequency_comparison": (
                feedback_policy_comparison_claim
            ),
            "closed_loop_frequency_attenuation": dynamic_feedback_attenuation_claim,
            "feedback_closed_loop_frequency_attenuation": (
                dynamic_feedback_attenuation_claim
            ),
            "dynamic_closed_loop_frequency_attenuation": (
                dynamic_feedback_attenuation_claim
            ),
            "feedback_dynamic_closed_loop_frequency_attenuation": (
                dynamic_feedback_attenuation_claim
            ),
            "active_static_policy_attenuation_observed": bool(
                attenuated_comparison_count > dynamic_attenuated_count
            ),
            "actuator_empirical_line_response_identified": bool(
                actuator_metadata.get("coherent_repeatable_line_rows", 0) > 0
            ),
            "local_stability_proven": False,
            "global_stability_claimed": False,
            "industrial_validation_claimed": False,
        },
        "reporting": {
            "report_path": str(report_path or ""),
            "plot_status": plot_status,
            "plot_paths": [str(path) for path in plot_paths],
        },
        "engine_profile": profile_metadata,
        "engine_args": list(frequency_engine_args),
        "git": canonical._git_provenance(root),
        "limitations": [
            "Native spectra use simulated etudecas case trajectories and are observational, not causal FRFs.",
            "Designed estimates are causal empirical diagonal line responses around synthetic periodic operating conditions, not isolated LTI FRFs.",
            "One-day sampling cannot identify dynamics above the 0.5 cycles/day Nyquist frequency.",
            controller_limitation,
            "Separate SISO campaigns prevent cross-input attribution, but weekly/lotified harmonic transfer can still mix lines of the same multisine.",
            "Full MIMO singular directions require additional independent phase realizations and a harmonic-transfer formulation.",
            "Odd excitation lines keep quadratic intermodulation off the excited lines, but higher-order nonlinear products can still contaminate them.",
            "Transport-delay estimates remain local phase-slope diagnostics and can be ambiguous modulo the designed period.",
            "The designed first pass disables stochastic lead times; a separate multi-seed stochastic robustness campaign remains required.",
            "Repeated-period boundedness and attenuation do not prove nonlinear global stability.",
            "The study is non-industrial and does not validate transfer to plant operations.",
        ],
    }
    protocol_path = output / "canonical_frequency_protocol.json"
    protocol_path.write_text(
        json.dumps(_json_safe(protocol), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    # Alias kept deliberately small for dashboard consumers that use a generic
    # manifest filename; both files carry the same auditable payload.
    (output / "canonical_frequency_manifest.json").write_text(
        protocol_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    protocol["output_sha256"] = _artifact_hashes(output)
    protocol_path.write_text(
        json.dumps(_json_safe(protocol), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output / "canonical_frequency_manifest.json").write_text(
        protocol_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return CanonicalFrequencyArtifacts(
        output_root=output,
        protocol_path=protocol_path,
        protocol=protocol,
        response_path=(output / "canonical_frequency_response.csv") if (output / "canonical_frequency_response.csv").is_file() else None,
        native_spectra_path=(output / "canonical_frequency_native_spectra.csv") if (output / "canonical_frequency_native_spectra.csv").is_file() else None,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run native and designed frequency analysis on the canonical etudecas supply chain."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--stage", choices=["native", "designed", "all"], default="all")
    parser.add_argument("--plot", action=argparse.BooleanOptionalAction, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = run_frequency_study(
        Path(args.config),
        repo_root=Path(args.repo_root),
        output_root=Path(args.output_dir) if args.output_dir else None,
        stage=str(args.stage),
        make_plots=args.plot,
    )
    print(f"Canonical frequency study completed: {artifacts.output_root}")
    print(f"Protocol: {artifacts.protocol_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "PROTOCOL_SCHEMA_VERSION",
    "CanonicalFrequencyArtifacts",
    "CanonicalFrequencyContractError",
    "CanonicalFrequencyStudyError",
    "run_frequency_study",
    "validate_frequency_config",
]
