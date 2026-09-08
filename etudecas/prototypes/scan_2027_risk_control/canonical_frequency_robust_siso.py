#!/usr/bin/env python3
"""Plan, execute, resume and aggregate the robust lead-time SISO campaign.

The default CLI mode is plan-only.  Each amplitude/phase cell invokes
``canonical_frequency_study.py`` in ``designed`` mode with only
``supplier_lead_time_multiplier`` enabled.  Cell attempts are append-only:
verified complete attempts are skipped and a partial attempt is never reused.

Aggregation reads verified complete cells only.  Even a complete matrix is
reported as evidence for scientific review, never as automatic proof of a
zero-amplitude local derivative, dynamic closed-loop stability, or global
stability.
"""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shlex
import statistics
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
DEFAULT_CONFIG_PATH = HERE.parent / "config" / "canonical_frequency_robust_siso_config.json"
STUDY_RUNNER_PATH = HERE.parent / "canonical_frequency_study.py"
CONFIG_SCHEMA_VERSION = "scan.canonical_frequency_robust_siso_config.v1"
PLAN_SCHEMA_VERSION = "scan.canonical_frequency_robust_siso_plan.v1"
AGGREGATE_SCHEMA_VERSION = "scan.canonical_frequency_robust_siso_aggregate.v1"
CELL_CONFIG_SCHEMA_VERSION = "scan.canonical_frequency_study.v1"
TARGET_INPUT_SIGNAL = "supplier_lead_time_multiplier"


class RobustSisoError(RuntimeError):
    """Base error for the robust SISO campaign."""


class RobustSisoContractError(RobustSisoError):
    """Raised when configuration or cell evidence violates the contract."""


@dataclass(frozen=True)
class AttemptInspection:
    """Validation result for one immutable cell attempt."""

    attempt_dir: Path
    state: str
    reason: str
    response_path: Path | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RobustSisoContractError(f"{label} is not valid UTF-8 JSON: {resolved}") from exc
    if not isinstance(payload, dict):
        raise RobustSisoContractError(f"{label} must contain a JSON object: {resolved}")
    return payload


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise RobustSisoContractError(f"{label} keys are not exact ({'; '.join(details)}).")


def _strict_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise RobustSisoContractError(f"{label} must be boolean.")
    return value


def _strict_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RobustSisoContractError(f"{label} must be an integer >= {minimum}.")
    return int(value)


def _strict_number(value: Any, label: str, *, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RobustSisoContractError(f"{label} must be numeric.")
    parsed = float(value)
    if not math.isfinite(parsed) or not lower <= parsed <= upper:
        raise RobustSisoContractError(f"{label} must be finite in [{lower}, {upper}].")
    return parsed


def validate_robust_siso_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate and normalize the campaign master protocol."""

    _require_exact_keys(
        payload,
        {
            "schema_version",
            "name",
            "base_study_config",
            "target_input_signal",
            "required_operating_conditions",
            "output_dir",
            "profiles",
            "execution",
            "claims",
        },
        "config",
    )
    if payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise RobustSisoContractError(f"schema_version must be {CONFIG_SCHEMA_VERSION!r}.")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise RobustSisoContractError("name must be non-empty.")
    target = str(payload.get("target_input_signal") or "")
    if target != TARGET_INPUT_SIGNAL:
        raise RobustSisoContractError(
            f"target_input_signal must be {TARGET_INPUT_SIGNAL!r}."
        )
    base_config = str(payload.get("base_study_config") or "").strip()
    output_dir = str(payload.get("output_dir") or "").strip()
    if not base_config or not output_dir:
        raise RobustSisoContractError("base_study_config and output_dir must be non-empty.")
    raw_conditions = payload.get("required_operating_conditions")
    if not isinstance(raw_conditions, list) or len(raw_conditions) != 2:
        raise RobustSisoContractError(
            "required_operating_conditions must contain exactly two condition names."
        )
    conditions = [str(value).strip() for value in raw_conditions]
    if any(not value for value in conditions) or len(set(conditions)) != 2:
        raise RobustSisoContractError(
            "required_operating_conditions must contain two unique non-empty names."
        )

    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, Mapping):
        raise RobustSisoContractError("profiles must be an object.")
    _require_exact_keys(raw_profiles, {"confirmatory", "pilot"}, "profiles")
    profiles: dict[str, dict[str, Any]] = {}
    expected_amplitudes = (0.5, 1.0, 2.0, 5.0)
    for profile_name in ("confirmatory", "pilot"):
        raw = raw_profiles[profile_name]
        if not isinstance(raw, Mapping):
            raise RobustSisoContractError(f"profiles.{profile_name} must be an object.")
        _require_exact_keys(
            raw,
            {
                "confirmatory",
                "amplitudes_percent",
                "phase_seeds",
                "measured_periods",
                "discarded_periods",
                "retained_periods",
                "interpretation",
            },
            f"profiles.{profile_name}",
        )
        confirmatory = _strict_bool(
            raw["confirmatory"], f"profiles.{profile_name}.confirmatory"
        )
        if confirmatory != (profile_name == "confirmatory"):
            raise RobustSisoContractError(
                f"profiles.{profile_name}.confirmatory has inconsistent semantics."
            )
        raw_amplitudes = raw["amplitudes_percent"]
        if not isinstance(raw_amplitudes, list) or not raw_amplitudes:
            raise RobustSisoContractError(
                f"profiles.{profile_name}.amplitudes_percent must be a non-empty list."
            )
        amplitudes = tuple(
            _strict_number(
                value,
                f"profiles.{profile_name}.amplitudes_percent[{index}]",
                lower=0.01,
                upper=20.0,
            )
            for index, value in enumerate(raw_amplitudes)
        )
        if len(set(amplitudes)) != len(amplitudes):
            raise RobustSisoContractError(
                f"profiles.{profile_name}.amplitudes_percent must be unique."
            )
        raw_seeds = raw["phase_seeds"]
        if not isinstance(raw_seeds, list) or not raw_seeds:
            raise RobustSisoContractError(
                f"profiles.{profile_name}.phase_seeds must be a non-empty list."
            )
        seeds = tuple(
            _strict_int(value, f"profiles.{profile_name}.phase_seeds[{index}]")
            for index, value in enumerate(raw_seeds)
        )
        if len(set(seeds)) != len(seeds):
            raise RobustSisoContractError(
                f"profiles.{profile_name}.phase_seeds must be unique."
            )
        measured = _strict_int(
            raw["measured_periods"], f"profiles.{profile_name}.measured_periods", minimum=3
        )
        discarded = _strict_int(
            raw["discarded_periods"], f"profiles.{profile_name}.discarded_periods", minimum=1
        )
        retained = _strict_int(
            raw["retained_periods"], f"profiles.{profile_name}.retained_periods", minimum=2
        )
        if discarded != 1 or retained != measured - discarded:
            raise RobustSisoContractError(
                f"profiles.{profile_name} must encode one discarded period and measured-discarded retained periods."
            )
        interpretation = str(raw.get("interpretation") or "").strip()
        if not interpretation:
            raise RobustSisoContractError(
                f"profiles.{profile_name}.interpretation must be non-empty."
            )
        if profile_name == "confirmatory":
            if amplitudes != expected_amplitudes:
                raise RobustSisoContractError(
                    "confirmatory amplitudes must be exactly 0.5, 1, 2 and 5 percent."
                )
            if len(seeds) < 5 or measured < 10 or retained < 9:
                raise RobustSisoContractError(
                    "confirmatory profile requires at least five phase seeds and 10 periods (1 discarded + at least 9 retained)."
                )
        else:
            if measured >= int(raw_profiles["confirmatory"]["measured_periods"]):
                raise RobustSisoContractError(
                    "pilot measured_periods must be shorter than confirmatory measured_periods."
                )
        profiles[profile_name] = {
            "confirmatory": confirmatory,
            "amplitudes_percent": amplitudes,
            "phase_seeds": seeds,
            "measured_periods": measured,
            "discarded_periods": discarded,
            "retained_periods": retained,
            "interpretation": interpretation,
        }

    execution = payload.get("execution")
    if not isinstance(execution, Mapping):
        raise RobustSisoContractError("execution must be an object.")
    _require_exact_keys(
        execution,
        {"python_executable", "stage", "plots", "existing_output_policy"},
        "execution",
    )
    python_executable = str(execution.get("python_executable") or "").strip()
    if not python_executable:
        raise RobustSisoContractError("execution.python_executable must be non-empty.")
    if execution.get("stage") != "designed":
        raise RobustSisoContractError("execution.stage must be 'designed'.")
    if _strict_bool(execution.get("plots"), "execution.plots"):
        raise RobustSisoContractError("execution.plots must be false for the cell campaign.")
    expected_policy = "skip_verified_complete_refuse_partial_unless_retry_as_new_attempt"
    if execution.get("existing_output_policy") != expected_policy:
        raise RobustSisoContractError(
            f"execution.existing_output_policy must be {expected_policy!r}."
        )

    claims = payload.get("claims")
    if not isinstance(claims, Mapping):
        raise RobustSisoContractError("claims must be an object.")
    claim_keys = {
        "local_derivative_automatically_proven",
        "dynamic_closed_loop_automatically_proven",
        "global_stability_automatically_proven",
        "incomplete_matrix_is_confirmatory_evidence",
    }
    _require_exact_keys(claims, claim_keys, "claims")
    for key in claim_keys:
        if _strict_bool(claims[key], f"claims.{key}"):
            raise RobustSisoContractError(f"claims.{key} must remain false.")

    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "name": name,
        "base_study_config": base_config,
        "target_input_signal": target,
        "required_operating_conditions": tuple(conditions),
        "output_dir": output_dir,
        "profiles": profiles,
        "execution": {
            "python_executable": python_executable,
            "stage": "designed",
            "plots": False,
            "existing_output_policy": expected_policy,
        },
        "claims": {key: False for key in sorted(claim_keys)},
    }


def _resolve_repo_path(value: str | Path, repo_root: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _amplitude_slug(percent: float) -> str:
    rendered = f"{percent:.12g}".replace(".", "p")
    return f"amp_{rendered}pct"


def _cell_id(profile: str, amplitude_percent: float, phase_seed: int) -> str:
    return f"{profile}__{_amplitude_slug(amplitude_percent)}__phase_{phase_seed}"


def _cell_config(
    base: Mapping[str, Any],
    *,
    cell_id: str,
    target: str,
    amplitude_percent: float,
    phase_seed: int,
    measured_periods: int,
) -> dict[str, Any]:
    payload = deepcopy(dict(base))
    if payload.get("schema_version") != CELL_CONFIG_SCHEMA_VERSION:
        raise RobustSisoContractError(
            f"base study schema_version must be {CELL_CONFIG_SCHEMA_VERSION!r}."
        )
    identification = payload.get("identification")
    if not isinstance(identification, dict):
        raise RobustSisoContractError("base identification must be an object.")
    input_bins = identification.get("input_bins")
    peak_fraction = identification.get("peak_fraction")
    if not isinstance(input_bins, Mapping) or target not in input_bins:
        raise RobustSisoContractError(f"base input_bins does not contain {target!r}.")
    if not isinstance(peak_fraction, dict) or target not in peak_fraction:
        raise RobustSisoContractError(f"base peak_fraction does not contain {target!r}.")
    identification["enabled_input_signals"] = [target]
    identification["peak_fraction"][target] = amplitude_percent / 100.0
    identification["phase_seed"] = int(phase_seed)
    identification["measured_periods"] = int(measured_periods)

    actuator = payload.get("actuator_probe")
    if not isinstance(actuator, dict):
        raise RobustSisoContractError("base actuator_probe must be an object.")
    actuator["enabled"] = False

    campaign = payload.get("campaign")
    if not isinstance(campaign, dict):
        raise RobustSisoContractError("base campaign must be an object.")
    campaign["output_dir"] = "ignored_by_robust_siso_cli_output_override"

    reporting = payload.get("reporting")
    if isinstance(reporting, dict):
        reporting["plots"] = False
    claims = payload.get("claims")
    if isinstance(claims, dict):
        for key in (
            "small_signal_local_derivative_claimed",
            "amplitude_sweep_verified",
            "active_set_invariance_verified",
            "isolated_lti_frf_claimed",
            "local_stability_proven",
            "global_stability_claimed",
            "industrial_validation_claimed",
        ):
            if key in claims:
                claims[key] = False
    payload["name"] = f"{payload.get('name', 'canonical_frequency_study')}__{cell_id}"
    return payload


def _cell_support_files(
    base: Mapping[str, Any],
    *,
    base_config_path: Path,
    repo_root: Path,
    cell_root: Path,
) -> list[dict[str, Any]]:
    """Locate config-local dependencies that must travel with a moved cell config."""

    campaign = base.get("campaign")
    if not isinstance(campaign, Mapping):
        raise RobustSisoContractError("base campaign must be an object.")
    support: list[dict[str, Any]] = []
    for field in ("control_policy_json", "engine_profile"):
        raw_value = str(campaign.get(field) or "").strip()
        if not raw_value:
            continue
        declared = Path(raw_value)
        if declared.is_absolute():
            if not declared.is_file():
                raise RobustSisoContractError(
                    f"base campaign.{field} does not exist: {declared}"
                )
            continue
        repo_candidate = (repo_root / declared).resolve()
        if repo_candidate.is_file():
            continue
        source = (base_config_path.parent / declared).resolve()
        if not source.is_file():
            raise RobustSisoContractError(
                f"base campaign.{field} cannot be resolved from repo or base-config directory: {raw_value}"
            )
        destination = (cell_root / declared).resolve()
        try:
            destination.relative_to(cell_root.resolve())
        except ValueError as exc:
            raise RobustSisoContractError(
                f"Refusing config-local dependency outside the cell root: {raw_value}"
            ) from exc
        support.append(
            {
                "field": field,
                "declared_path": raw_value,
                "source_path": str(source),
                "source_sha256": _sha256(source),
                "destination_path": str(destination),
            }
        )
    return support


def _command_argv(
    *,
    python_executable: str,
    repo_root: Path,
    config_path: Path,
    artifact_dir: Path,
) -> list[str]:
    return [
        python_executable,
        str(STUDY_RUNNER_PATH),
        "--config",
        str(config_path),
        "--repo-root",
        str(repo_root),
        "--output-dir",
        str(artifact_dir),
        "--stage",
        "designed",
        "--no-plot",
    ]


def _display_command(argv: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(argv)) if sys.platform == "win32" else shlex.join(argv)


def _matching_amplitude(value: float, candidates: Iterable[float]) -> float | None:
    for candidate in candidates:
        if math.isclose(float(value), float(candidate), rel_tol=0.0, abs_tol=1e-12):
            return float(candidate)
    return None


def build_campaign_plan(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    repo_root: Path = REPO_ROOT,
    campaign_dir: Path | None = None,
    profile: str = "confirmatory",
    cell_filters: Sequence[str] = (),
    amplitude_filters_percent: Sequence[float] = (),
    phase_filters: Sequence[int] = (),
    python_executable: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic full-grid plan and mark the requested cell subset."""

    root = repo_root.resolve()
    config = config_path.resolve()
    normalized = validate_robust_siso_config(_read_json_object(config, "robust SISO config"))
    if profile not in normalized["profiles"]:
        raise RobustSisoContractError(f"Unknown profile: {profile}")
    selected_profile = normalized["profiles"][profile]
    base_path = _resolve_repo_path(normalized["base_study_config"], root)
    base = _read_json_object(base_path, "base frequency-study config")
    conditions = base.get("operating_conditions")
    if not isinstance(conditions, list):
        raise RobustSisoContractError("base operating_conditions must be a list.")
    condition_names = tuple(
        str(row.get("name") or "") for row in conditions if isinstance(row, Mapping)
    )
    if condition_names != normalized["required_operating_conditions"]:
        raise RobustSisoContractError(
            "base operating conditions do not exactly match required_operating_conditions: "
            f"expected {normalized['required_operating_conditions']}, got {condition_names}."
        )
    campaign_base = (
        campaign_dir.resolve()
        if campaign_dir is not None
        else _resolve_repo_path(normalized["output_dir"], root)
    )
    output_root = campaign_base / profile
    executable = python_executable or normalized["execution"]["python_executable"]
    amplitudes = tuple(selected_profile["amplitudes_percent"])
    phases = tuple(selected_profile["phase_seeds"])
    requested_cells = set(cell_filters)
    unknown_amplitudes = [
        value for value in amplitude_filters_percent if _matching_amplitude(value, amplitudes) is None
    ]
    if unknown_amplitudes:
        raise RobustSisoContractError(
            "Amplitude filter is outside the profile grid (percentage points): "
            + ", ".join(str(value) for value in unknown_amplitudes)
        )
    unknown_phases = sorted(set(int(value) for value in phase_filters) - set(phases))
    if unknown_phases:
        raise RobustSisoContractError(
            "Phase filter is outside the profile grid: "
            + ", ".join(str(value) for value in unknown_phases)
        )

    cells: list[dict[str, Any]] = []
    all_ids: set[str] = set()
    for amplitude_percent in amplitudes:
        for phase_seed in phases:
            cell_id = _cell_id(profile, amplitude_percent, phase_seed)
            all_ids.add(cell_id)
            cell_root = output_root / "cells" / cell_id
            cell_config_path = cell_root / "canonical_frequency_study_config.json"
            generated = _cell_config(
                base,
                cell_id=cell_id,
                target=normalized["target_input_signal"],
                amplitude_percent=float(amplitude_percent),
                phase_seed=int(phase_seed),
                measured_periods=int(selected_profile["measured_periods"]),
            )
            support_files = _cell_support_files(
                base,
                base_config_path=base_path,
                repo_root=root,
                cell_root=cell_root,
            )
            config_bytes = _json_bytes(generated)
            passes_cell = not requested_cells or cell_id in requested_cells
            passes_amplitude = not amplitude_filters_percent or any(
                math.isclose(float(amplitude_percent), float(value), rel_tol=0.0, abs_tol=1e-12)
                for value in amplitude_filters_percent
            )
            passes_phase = not phase_filters or int(phase_seed) in set(phase_filters)
            attempt_dir = cell_root / "attempts" / "attempt_001"
            argv = _command_argv(
                python_executable=executable,
                repo_root=root,
                config_path=cell_config_path,
                artifact_dir=attempt_dir / "artifacts",
            )
            cells.append(
                {
                    "cell_id": cell_id,
                    "selected": bool(passes_cell and passes_amplitude and passes_phase),
                    "profile": profile,
                    "confirmatory": bool(selected_profile["confirmatory"]),
                    "target_input_signal": normalized["target_input_signal"],
                    "amplitude_percent": float(amplitude_percent),
                    "peak_fraction": float(amplitude_percent) / 100.0,
                    "phase_seed": int(phase_seed),
                    "measured_periods": int(selected_profile["measured_periods"]),
                    "discarded_periods": int(selected_profile["discarded_periods"]),
                    "retained_periods": int(selected_profile["retained_periods"]),
                    "operating_conditions": list(condition_names),
                    "cell_root": str(cell_root),
                    "config_path": str(cell_config_path),
                    "config_sha256": _sha256_bytes(config_bytes),
                    "config_payload": generated,
                    "support_files": support_files,
                    "planned_attempt": "attempt_001",
                    "planned_artifact_dir": str(attempt_dir / "artifacts"),
                    "argv": argv,
                    "command": _display_command(argv),
                }
            )
    unknown_cells = sorted(requested_cells - all_ids)
    if unknown_cells:
        raise RobustSisoContractError("Unknown cell filter(s): " + ", ".join(unknown_cells))
    if not any(bool(cell["selected"]) for cell in cells):
        raise RobustSisoContractError("Filters selected no cells.")

    identity = {
        "config_sha256": _sha256(config),
        "base_config_sha256": _sha256(base_path),
        "profile": profile,
        "target_input_signal": normalized["target_input_signal"],
        "cell_ids": [cell["cell_id"] for cell in cells],
    }
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "mode": "plan_only_until_execute_is_explicit",
        "campaign_name": normalized["name"],
        "campaign_identity_sha256": _sha256_bytes(_json_bytes(identity)),
        "profile": profile,
        "confirmatory": bool(selected_profile["confirmatory"]),
        "profile_interpretation": selected_profile["interpretation"],
        "config_path": str(config),
        "config_sha256": _sha256(config),
        "base_study_config_path": str(base_path),
        "base_study_config_sha256": _sha256(base_path),
        "repo_root": str(root),
        "campaign_base_dir": str(campaign_base),
        "campaign_dir": str(output_root),
        "study_runner_path": str(STUDY_RUNNER_PATH),
        "study_runner_sha256": _sha256(STUDY_RUNNER_PATH),
        "target_input_signal": normalized["target_input_signal"],
        "enabled_input_signals": [normalized["target_input_signal"]],
        "operating_conditions": list(condition_names),
        "actuator_probe_enabled": False,
        "stage": "designed",
        "plots": False,
        "configured_cell_count": len(cells),
        "selected_cell_count": sum(bool(cell["selected"]) for cell in cells),
        "cells": cells,
        "automatic_claims": {
            "local_derivative_proven": False,
            "dynamic_closed_loop_proven": False,
            "global_stability_proven": False,
            "reason": "A plan is not evidence; complete replicated cells still require scientific review.",
        },
    }


def _write_immutable(path: Path, content: bytes, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        if not path.is_file() or path.read_bytes() != content:
            raise RobustSisoContractError(
                f"Refusing to overwrite conflicting {label}: {path.resolve()}"
            )


def _public_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(plan))
    for cell in payload["cells"]:
        cell.pop("config_payload", None)
    return payload


def materialize_plan(plan: Mapping[str, Any]) -> Path:
    """Write immutable cell configs and a versioned, append-only plan manifest."""

    campaign_dir = Path(str(plan["campaign_dir"]))
    campaign_dir.mkdir(parents=True, exist_ok=True)
    identity_path = campaign_dir / "campaign_identity.json"
    identity_payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "campaign_identity_sha256": plan["campaign_identity_sha256"],
        "config_sha256": plan["config_sha256"],
        "base_study_config_sha256": plan["base_study_config_sha256"],
        "profile": plan["profile"],
    }
    _write_immutable(identity_path, _json_bytes(identity_payload), "campaign identity")
    for cell in plan["cells"]:
        _write_immutable(
            Path(str(cell["config_path"])),
            _json_bytes(cell["config_payload"]),
            f"cell config {cell['cell_id']}",
        )
        for support in cell.get("support_files", ()):
            source = Path(str(support["source_path"]))
            if not source.is_file() or _sha256(source) != str(support["source_sha256"]):
                raise RobustSisoContractError(
                    f"Refusing to materialize drifted support file: {source}"
                )
            _write_immutable(
                Path(str(support["destination_path"])),
                source.read_bytes(),
                f"cell support file {support['declared_path']}",
            )
    manifest = _public_plan(plan)
    manifest["written_at_utc"] = _utc_now()
    manifest_path = campaign_dir / "plans" / f"plan_{_timestamp_slug()}.json"
    _write_immutable(manifest_path, _json_bytes(manifest), "plan manifest")
    return manifest_path


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _float_or_none(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def inspect_attempt(attempt_dir: Path, *, expected_config_sha256: str) -> AttemptInspection:
    """Verify a completed cell attempt without modifying it."""

    if not attempt_dir.exists():
        return AttemptInspection(attempt_dir, "missing", "attempt_directory_missing")
    artifacts = attempt_dir / "artifacts"
    protocol_path = artifacts / "canonical_frequency_protocol.json"
    manifest_path = artifacts / "canonical_frequency_manifest.json"
    response_path = artifacts / "canonical_frequency_response.csv"
    required = (protocol_path, manifest_path, response_path)
    if not all(path.is_file() for path in required):
        return AttemptInspection(attempt_dir, "partial", "required_artifact_missing")
    try:
        protocol = _read_json_object(protocol_path, "cell protocol")
        manifest = _read_json_object(manifest_path, "cell manifest")
    except (FileNotFoundError, RobustSisoContractError) as exc:
        return AttemptInspection(attempt_dir, "invalid", str(exc))
    if protocol != manifest:
        return AttemptInspection(attempt_dir, "invalid", "protocol_manifest_mismatch")
    if protocol.get("status") != "complete_designed":
        return AttemptInspection(attempt_dir, "partial", "protocol_not_complete_designed")
    config_meta = protocol.get("config")
    if not isinstance(config_meta, Mapping) or config_meta.get("sha256") != expected_config_sha256:
        return AttemptInspection(attempt_dir, "invalid", "cell_config_sha256_mismatch")
    hashes = protocol.get("output_sha256")
    if not isinstance(hashes, Mapping):
        return AttemptInspection(attempt_dir, "invalid", "protocol_output_hashes_missing")
    if hashes.get(response_path.name) != _sha256(response_path):
        return AttemptInspection(attempt_dir, "invalid", "response_sha256_mismatch")
    try:
        with response_path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            first = next(reader, None)
            fieldnames = set(reader.fieldnames or ())
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return AttemptInspection(attempt_dir, "invalid", f"response_csv_invalid:{exc}")
    required_columns = {
        "condition",
        "policy",
        "input_signal",
        "output_signal",
        "frequency_bin",
        "coherence",
        "valid_bin",
        "phase_deg",
    }
    if first is None or not required_columns.issubset(fieldnames):
        return AttemptInspection(attempt_dir, "invalid", "response_csv_contract_missing")
    return AttemptInspection(attempt_dir, "complete", "verified", response_path)


def _attempt_dirs(cell: Mapping[str, Any]) -> list[Path]:
    root = Path(str(cell["cell_root"])) / "attempts"
    if not root.is_dir():
        return []
    return sorted(
        (path for path in root.glob("attempt_[0-9][0-9][0-9]") if path.is_dir()),
        key=lambda path: path.name,
    )


def inspect_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    attempts = [
        inspect_attempt(path, expected_config_sha256=str(cell["config_sha256"]))
        for path in _attempt_dirs(cell)
    ]
    complete = [attempt for attempt in attempts if attempt.state == "complete"]
    if len(complete) > 1:
        return {
            "state": "invalid",
            "reason": "multiple_complete_attempts",
            "complete_attempt": None,
            "attempts": attempts,
        }
    if complete:
        return {
            "state": "complete",
            "reason": "verified_complete_attempt",
            "complete_attempt": complete[0],
            "attempts": attempts,
        }
    if any(attempt.state == "invalid" for attempt in attempts):
        return {
            "state": "invalid",
            "reason": "invalid_attempt_present",
            "complete_attempt": None,
            "attempts": attempts,
        }
    if attempts:
        return {
            "state": "partial",
            "reason": "partial_attempt_present",
            "complete_attempt": None,
            "attempts": attempts,
        }
    return {
        "state": "missing",
        "reason": "no_attempt",
        "complete_attempt": None,
        "attempts": [],
    }


def _next_attempt_dir(cell: Mapping[str, Any]) -> Path:
    attempts = _attempt_dirs(cell)
    next_index = 1
    if attempts:
        next_index = max(int(path.name.rsplit("_", 1)[1]) for path in attempts) + 1
    return Path(str(cell["cell_root"])) / "attempts" / f"attempt_{next_index:03d}"


def execute_plan(
    plan: Mapping[str, Any],
    *,
    retry_partial: bool = False,
) -> tuple[dict[str, Any], Path]:
    """Execute selected cells sequentially, resuming only at cell boundaries."""

    campaign_dir = Path(str(plan["campaign_dir"]))
    source_checks = (
        (Path(str(plan["config_path"])), str(plan["config_sha256"]), "robust config"),
        (
            Path(str(plan["base_study_config_path"])),
            str(plan["base_study_config_sha256"]),
            "base study config",
        ),
        (
            Path(str(plan["study_runner_path"])),
            str(plan["study_runner_sha256"]),
            "study runner",
        ),
    )
    for source, expected_hash, label in source_checks:
        if not source.is_file() or _sha256(source) != expected_hash:
            raise RobustSisoContractError(
                f"Refusing execution because the planned {label} changed: {source}"
            )
    for cell in plan["cells"]:
        config_path = Path(str(cell["config_path"]))
        if not config_path.is_file() or _sha256(config_path) != str(cell["config_sha256"]):
            raise RobustSisoContractError(
                f"Refusing execution because cell config drifted: {config_path}"
            )
        for support in cell.get("support_files", ()):
            destination = Path(str(support["destination_path"]))
            if not destination.is_file() or _sha256(destination) != str(
                support["source_sha256"]
            ):
                raise RobustSisoContractError(
                    f"Refusing execution because a cell support file drifted: {destination}"
                )
    records: list[dict[str, Any]] = []
    for cell in plan["cells"]:
        if not bool(cell["selected"]):
            continue
        inspection = inspect_cell(cell)
        if inspection["state"] == "complete":
            complete = inspection["complete_attempt"]
            records.append(
                {
                    "cell_id": cell["cell_id"],
                    "action": "skipped_verified_complete",
                    "attempt_dir": str(complete.attempt_dir),
                    "returncode": 0,
                }
            )
            continue
        if inspection["state"] in {"partial", "invalid"} and not retry_partial:
            records.append(
                {
                    "cell_id": cell["cell_id"],
                    "action": "blocked_existing_noncomplete_attempt",
                    "attempt_dir": None,
                    "returncode": None,
                    "reason": inspection["reason"],
                }
            )
            continue
        attempt_dir = _next_attempt_dir(cell)
        attempt_dir.mkdir(parents=True, exist_ok=False)
        artifact_dir = attempt_dir / "artifacts"
        argv = _command_argv(
            python_executable=str(cell["argv"][0]),
            repo_root=Path(str(plan["repo_root"])),
            config_path=Path(str(cell["config_path"])),
            artifact_dir=artifact_dir,
        )
        request = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "started_at_utc": _utc_now(),
            "cell_id": cell["cell_id"],
            "config_sha256": cell["config_sha256"],
            "argv": argv,
            "command": _display_command(argv),
        }
        _write_immutable(attempt_dir / "execution_request.json", _json_bytes(request), "execution request")
        completed = subprocess.run(
            argv,
            cwd=str(plan["repo_root"]),
            text=True,
            capture_output=True,
            check=False,
        )
        _write_immutable(
            attempt_dir / "stdout.log",
            completed.stdout.encode("utf-8", errors="replace"),
            "stdout log",
        )
        _write_immutable(
            attempt_dir / "stderr.log",
            completed.stderr.encode("utf-8", errors="replace"),
            "stderr log",
        )
        verification = inspect_attempt(
            attempt_dir, expected_config_sha256=str(cell["config_sha256"])
        )
        result = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "finished_at_utc": _utc_now(),
            "cell_id": cell["cell_id"],
            "returncode": int(completed.returncode),
            "verification_state": verification.state,
            "verification_reason": verification.reason,
        }
        _write_immutable(attempt_dir / "execution_result.json", _json_bytes(result), "execution result")
        records.append(
            {
                "cell_id": cell["cell_id"],
                "action": "executed",
                "attempt_dir": str(attempt_dir),
                "returncode": int(completed.returncode),
                "verification_state": verification.state,
                "verification_reason": verification.reason,
            }
        )
    summary = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "campaign_identity_sha256": plan["campaign_identity_sha256"],
        "started_from_plan_profile": plan["profile"],
        "finished_at_utc": _utc_now(),
        "retry_partial_as_new_attempt": bool(retry_partial),
        "records": records,
        "successful": all(
            record["action"] == "skipped_verified_complete"
            or (
                record["action"] == "executed"
                and record.get("returncode") == 0
                and record.get("verification_state") == "complete"
            )
            for record in records
        ),
    }
    summary_path = campaign_dir / "executions" / f"execution_{_timestamp_slug()}.json"
    _write_immutable(summary_path, _json_bytes(summary), "execution summary")
    return summary, summary_path


def _median(values: Sequence[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _mean(values: Sequence[float]) -> float | None:
    return float(statistics.fmean(values)) if values else None


def _sample_std(values: Sequence[float]) -> float | None:
    return float(statistics.stdev(values)) if len(values) >= 2 else None


def _circular_phase(values: Sequence[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    radians = [math.radians(value) for value in values]
    mean_sin = statistics.fmean(math.sin(value) for value in radians)
    mean_cos = statistics.fmean(math.cos(value) for value in radians)
    mean_deg = math.degrees(math.atan2(mean_sin, mean_cos))
    resultant = min(1.0, max(0.0, math.hypot(mean_sin, mean_cos)))
    if resultant <= 0.0:
        return mean_deg, 180.0
    std_deg = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(resultant))))
    return mean_deg, std_deg


def _summarize_rows(rows: Sequence[Mapping[str, Any]], key_values: Mapping[str, Any]) -> dict[str, Any]:
    valid_rows = [row for row in rows if _parse_bool(row.get("valid_bin"))]
    coherences = [value for row in rows if (value := _float_or_none(row.get("coherence"))) is not None]
    gains = [
        value for row in valid_rows if (value := _float_or_none(row.get("gain"))) is not None
    ]
    phases = [
        value
        for row in valid_rows
        if (value := _float_or_none(row.get("phase_deg"))) is not None
    ]
    compatible_rows = [
        row for row in valid_rows if _parse_bool(row.get("regime_compatible"))
    ]
    coherent_rows = [
        row
        for row in rows
        if (coherence := _float_or_none(row.get("coherence"))) is not None
        and coherence
        >= (_float_or_none(row.get("coherence_threshold")) or 0.8)
    ]
    gain_mean = _mean(gains)
    gain_std = _sample_std(gains)
    phase_mean, phase_std = _circular_phase(phases)
    return {
        **dict(key_values),
        "row_count": len(rows),
        "cell_count": len({str(row["cell_id"]) for row in rows}),
        "phase_seed_count": len({int(row["phase_seed"]) for row in rows}),
        "amplitude_count": len({float(row["amplitude_percent"]) for row in rows}),
        "valid_row_count": len(valid_rows),
        "coherent_row_count": len(coherent_rows),
        "regime_compatible_valid_row_count": len(compatible_rows),
        "coherence_median": _median(coherences),
        "coherence_minimum": min(coherences) if coherences else None,
        "gain_basis": "elasticity_magnitude_preferred_else_magnitude",
        "gain_mean": gain_mean,
        "gain_median": _median(gains),
        "gain_sample_std": gain_std,
        "gain_relative_sample_std": (
            gain_std / abs(gain_mean)
            if gain_std is not None and gain_mean is not None and abs(gain_mean) > 1e-30
            else None
        ),
        "phase_circular_mean_deg": phase_mean,
        "phase_circular_std_deg": phase_std,
    }


def _group_summary(
    rows: Sequence[Mapping[str, Any]], keys: Sequence[str]
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        group_key = tuple(row.get(key) for key in keys)
        groups.setdefault(group_key, []).append(row)
    return [
        _summarize_rows(group_rows, dict(zip(keys, group_key)))
        for group_key, group_rows in sorted(groups.items(), key=lambda item: tuple(str(x) for x in item[0]))
    ]


def aggregate_campaign(plan: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Read only verified complete cells and compute coverage/dispersion summaries."""

    cell_states: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    required_conditions = set(str(value) for value in plan["operating_conditions"])
    for cell in plan["cells"]:
        inspection = inspect_cell(cell)
        attempt = inspection["complete_attempt"]
        state_row = {
            "cell_id": cell["cell_id"],
            "amplitude_percent": cell["amplitude_percent"],
            "phase_seed": cell["phase_seed"],
            "state": inspection["state"],
            "reason": inspection["reason"],
            "complete_attempt_dir": str(attempt.attempt_dir) if attempt else None,
        }
        cell_states.append(state_row)
        if attempt is None or attempt.response_path is None:
            continue
        cell_rows: list[dict[str, Any]] = []
        with attempt.response_path.open("r", encoding="utf-8", newline="") as stream:
            for source in csv.DictReader(stream):
                if str(source.get("input_signal") or "") != plan["target_input_signal"]:
                    raise RobustSisoContractError(
                        f"Verified cell {cell['cell_id']} contains a non-target input signal."
                    )
                gain = _float_or_none(source.get("elasticity_magnitude"))
                if gain is None:
                    gain = _float_or_none(source.get("magnitude"))
                regime_value = source.get("tested_amplitude_regime_trace_compatible")
                if regime_value is None:
                    regime_value = source.get("regime_compatible_for_local_claim", False)
                row = {
                    **source,
                    "cell_id": cell["cell_id"],
                    "amplitude_percent": float(cell["amplitude_percent"]),
                    "peak_fraction": float(cell["peak_fraction"]),
                    "phase_seed": int(cell["phase_seed"]),
                    "gain": gain,
                    "regime_compatible": _parse_bool(regime_value),
                }
                cell_rows.append(row)
        observed_conditions = {str(row.get("condition") or "") for row in cell_rows}
        if not required_conditions.issubset(observed_conditions):
            raise RobustSisoContractError(
                f"Verified cell {cell['cell_id']} is missing required condition response rows."
            )
        rows.extend(cell_rows)

    complete_count = sum(row["state"] == "complete" for row in cell_states)
    configured_count = len(cell_states)
    matrix_complete = configured_count > 0 and complete_count == configured_count
    valid_count = sum(_parse_bool(row.get("valid_bin")) for row in rows)
    compatible_valid_count = sum(
        _parse_bool(row.get("valid_bin")) and bool(row.get("regime_compatible")) for row in rows
    )
    coherence_values = [
        value for row in rows if (value := _float_or_none(row.get("coherence"))) is not None
    ]
    amplitude_summary = _group_summary(rows, ("amplitude_percent",))
    phase_summary = _group_summary(rows, ("phase_seed",))
    amplitude_line_dispersion = _group_summary(
        rows,
        (
            "amplitude_percent",
            "condition",
            "policy",
            "output_signal",
            "frequency_bin",
        ),
    )
    phase_line_dispersion = _group_summary(
        rows,
        (
            "phase_seed",
            "condition",
            "policy",
            "output_signal",
            "frequency_bin",
        ),
    )
    claim_reason = (
        "Complete matrix: eligible for scientific review of amplitude/phase robustness; no claim is automatic."
        if matrix_complete
        else "Incomplete matrix: local-derivative and dynamic closed-loop claims are blocked."
    )
    aggregate = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "campaign_identity_sha256": plan["campaign_identity_sha256"],
        "profile": plan["profile"],
        "confirmatory_profile": bool(plan["confirmatory"]),
        "target_input_signal": plan["target_input_signal"],
        "coverage": {
            "configured_cell_count": configured_count,
            "complete_cell_count": complete_count,
            "missing_cell_count": sum(row["state"] == "missing" for row in cell_states),
            "partial_cell_count": sum(row["state"] == "partial" for row in cell_states),
            "invalid_cell_count": sum(row["state"] == "invalid" for row in cell_states),
            "matrix_complete": matrix_complete,
            "completion_fraction": complete_count / configured_count if configured_count else 0.0,
        },
        "response_evidence": {
            "row_count": len(rows),
            "valid_row_count": valid_count,
            "regime_compatible_valid_row_count": compatible_valid_count,
            "coherence_median": _median(coherence_values),
            "coherence_minimum": min(coherence_values) if coherence_values else None,
            "amplitude_summary_row_count": len(amplitude_summary),
            "phase_summary_row_count": len(phase_summary),
            "amplitude_line_dispersion_row_count": len(amplitude_line_dispersion),
            "phase_line_dispersion_row_count": len(phase_line_dispersion),
        },
        "claim_gate": {
            "matrix_complete": matrix_complete,
            "eligible_for_scientific_review": bool(matrix_complete and plan["confirmatory"]),
            "local_derivative_proven": False,
            "dynamic_closed_loop_proven": False,
            "global_stability_proven": False,
            "reason": claim_reason,
        },
    }
    tables = {
        "cell_coverage": cell_states,
        "amplitude_summary": amplitude_summary,
        "phase_summary": phase_summary,
        "amplitude_line_dispersion": amplitude_line_dispersion,
        "phase_line_dispersion": phase_line_dispersion,
    }
    return aggregate, tables


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_aggregate(
    plan: Mapping[str, Any],
    aggregate: Mapping[str, Any],
    tables: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Path:
    """Write one append-only aggregate snapshot outside all cell attempts."""

    root = Path(str(plan["campaign_dir"])) / "aggregates" / f"aggregate_{_timestamp_slug()}"
    root.mkdir(parents=True, exist_ok=False)
    _write_immutable(root / "robust_siso_aggregate.json", _json_bytes(dict(aggregate)), "aggregate JSON")
    for name, rows in tables.items():
        _write_csv(root / f"robust_siso_{name}.csv", rows)
    ledger_rows = []
    for path in sorted(candidate for candidate in root.iterdir() if candidate.is_file()):
        ledger_rows.append(
            {
                "relative_path": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    _write_csv(root / "robust_siso_aggregate_ledger.csv", ledger_rows)
    return root


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plan by default, or explicitly execute/resume, the replicated supplier lead-time SISO campaign."
        )
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--campaign-dir", default=None)
    parser.add_argument("--profile", choices=("confirmatory", "pilot"), default="confirmatory")
    parser.add_argument("--cell", action="append", default=[], help="Exact cell id; repeatable.")
    parser.add_argument(
        "--amplitude",
        action="append",
        type=float,
        default=[],
        help="Amplitude in percentage points (0.5, 1, 2 or 5); repeatable.",
    )
    parser.add_argument("--phase", action="append", type=int, default=[], help="Phase seed; repeatable.")
    parser.add_argument("--python", dest="python_executable", default=None)
    parser.add_argument("--execute", action="store_true", help="Explicitly run selected cells.")
    parser.add_argument(
        "--retry-partial",
        action="store_true",
        help="With --execute, create a new attempt for partial/invalid cells; never overwrite the old attempt.",
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Write an append-only aggregate snapshot from verified complete cells.",
    )
    args = parser.parse_args(argv)
    if args.retry_partial and not args.execute:
        parser.error("--retry-partial requires --execute")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_campaign_plan(
        Path(args.config),
        repo_root=Path(args.repo_root),
        campaign_dir=Path(args.campaign_dir) if args.campaign_dir else None,
        profile=str(args.profile),
        cell_filters=tuple(args.cell),
        amplitude_filters_percent=tuple(args.amplitude),
        phase_filters=tuple(args.phase),
        python_executable=args.python_executable,
    )
    plan_path = materialize_plan(plan)
    print(
        f"Plan written: {plan_path} ({plan['selected_cell_count']}/{plan['configured_cell_count']} cells selected)"
    )
    execution_ok = True
    if args.execute:
        execution, execution_path = execute_plan(plan, retry_partial=bool(args.retry_partial))
        execution_ok = bool(execution["successful"])
        print(f"Execution summary: {execution_path}")
    if args.aggregate or args.execute:
        aggregate, tables = aggregate_campaign(plan)
        aggregate_root = write_aggregate(plan, aggregate, tables)
        coverage = aggregate["coverage"]
        print(
            f"Aggregate: {aggregate_root} ({coverage['complete_cell_count']}/{coverage['configured_cell_count']} verified complete)"
        )
    if not args.execute:
        print("Plan-only mode: no simulation was launched. Use --execute explicitly to run selected cells.")
    return 0 if execution_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AGGREGATE_SCHEMA_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "PLAN_SCHEMA_VERSION",
    "AttemptInspection",
    "RobustSisoContractError",
    "RobustSisoError",
    "aggregate_campaign",
    "build_campaign_plan",
    "execute_plan",
    "inspect_attempt",
    "inspect_cell",
    "materialize_plan",
    "parse_args",
    "validate_robust_siso_config",
    "write_aggregate",
]
