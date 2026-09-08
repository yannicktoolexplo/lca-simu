#!/usr/bin/env python3
"""Paired canonical MRP versus state-feedback campaign runner.

The runner deliberately does not infer closed-loop operation from the command
line used to start the engine.  A feedback run is labelled ``true state
feedback`` only when the canonical engine writes the authoritative provider
claim and the runner independently validates its zero-lookahead J-to-J+1
evidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.canonical_replay import (  # noqa: E402
    CANONICAL_KPI_NAMES,
    MANAGED_CANONICAL_ENGINE_FLAGS,
    _attach_canonical_rci,
    _attach_mrp_reference_deltas,
    _paired_canonical_summary,
    _student_t_critical_95,
    discover_canonical_graph,
    extract_canonical_kpis,
    load_canonical_engine_profile,
)
from etudecas.simulation.engine.control_schedule import CONTROL_BOUNDS  # noqa: E402


DEFAULT_CONFIG_PATH = HERE.parent / "config" / "canonical_closed_loop_config.json"
DEFAULT_ENGINE_PROFILE_PATH = (
    HERE.parent / "config" / "canonical_real_baseline_engine_profile.json"
)
DEFAULT_OUTPUT_ROOT = HERE.parent / "outputs" / "canonical_closed_loop"
DEFAULT_ENGINE_SCRIPT = (
    REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
)

REFERENCE_POLICY = "mrp_reference"
FEEDBACK_POLICY = "canonical_feedback"
_CONTROL_POLICY_FLAG = "--control-policy-json"
_CONTROL_POLICY_V2_FLAG = "--control-policy-v2-json"
_CONTROL_POLICY_V3_FLAG = "--control-policy-v3-json"
_MANAGED_ENGINE_FLAGS = frozenset(
    {
        *MANAGED_CANONICAL_ENGINE_FLAGS,
        _CONTROL_POLICY_FLAG,
        _CONTROL_POLICY_V2_FLAG,
        _CONTROL_POLICY_V3_FLAG,
    }
)

ENGINE_ARTIFACT_PROFILE_COMPACT = "compact"
ENGINE_ARTIFACT_PROFILE_FULL = "full"
ENGINE_ARTIFACT_PROFILES = (
    ENGINE_ARTIFACT_PROFILE_COMPACT,
    ENGINE_ARTIFACT_PROFILE_FULL,
)
_ENGINE_ARTIFACT_PROFILE_ARGS: dict[str, tuple[str, ...]] = {
    ENGINE_ARTIFACT_PROFILE_COMPACT: (
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
    ),
    ENGINE_ARTIFACT_PROFILE_FULL: (
        "--output-profile",
        "full",
        "--lot-trace",
    ),
}
_FULL_ARTIFACT_REQUIRED_FILES = (
    "data/production_input_consumption_daily.csv",
    "data/production_input_replenishment_shipments_daily.csv",
    "data/production_input_stocks_pivot.csv",
    "data/production_lot_events.csv",
    "data/production_lot_genealogy.csv",
    "reports/lot_path_audit.md",
    "data/lot_path_audit_issues.csv",
)


class CanonicalClosedLoopError(RuntimeError):
    """Base error raised by the paired canonical campaign."""


class CanonicalClosedLoopContractError(CanonicalClosedLoopError):
    """The engine returned successfully but its output contract is invalid."""


@dataclass(frozen=True)
class CanonicalClosedLoopArtifacts:
    """In-memory and on-disk results of one completed campaign."""

    runs: pd.DataFrame
    paired_deltas: pd.DataFrame
    paired_summary: pd.DataFrame
    output_root: Path
    manifest_path: Path
    plot_path: Path | None
    control_diagnostics_plot_path: Path | None = None
    control_diagnostics_plot_status: str = "disabled"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_provenance(repo_root: Path) -> dict[str, Any]:
    """Return best-effort local Git provenance without changing repository state."""

    def git_text(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    commit = git_text("rev-parse", "HEAD")
    branch = git_text("branch", "--show-current")
    status = git_text("status", "--porcelain")
    return {
        "commit": commit,
        "branch": branch,
        "working_tree_dirty": bool(status),
        "available": bool(commit),
    }


def _require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} does not exist or is not a file: {resolved}")
    return resolved


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    resolved = _require_file(path, label)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object: {resolved}")
    return payload


def _resolve_path(
    value: str | Path,
    *,
    repo_root: Path,
    relative_to: Path | None = None,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (repo_root / path).resolve()
    local_candidate = (
        (relative_to / path).resolve() if relative_to is not None else None
    )
    if repo_candidate.exists() or local_candidate is None:
        return repo_candidate
    return local_candidate


def _ordered_seeds(seeds: Sequence[int]) -> tuple[int, ...]:
    parsed = tuple(int(seed) for seed in seeds)
    if not parsed:
        raise ValueError("At least one paired seed is required.")
    if len(set(parsed)) != len(parsed):
        raise ValueError("Paired seeds must be unique.")
    if any(seed < 0 for seed in parsed):
        raise ValueError("Paired seeds must be non-negative integers.")
    return tuple(sorted(parsed))


def _validate_extra_args(args: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(item).strip() for item in args)
    if any(not item for item in normalized):
        raise ValueError("Engine arguments must be non-empty strings.")
    for token in normalized:
        if "\x00" in token or "\n" in token or "\r" in token:
            raise ValueError("Engine arguments cannot contain control characters.")
        flag = token.split("=", 1)[0]
        if flag in _MANAGED_ENGINE_FLAGS:
            raise ValueError(
                f"Engine arguments cannot override campaign-managed flag {flag}."
            )
    return normalized


def _engine_artifact_args(profile: str) -> tuple[str, ...]:
    if not isinstance(profile, str):
        raise ValueError(
            "engine_artifact_profile must be 'compact' or 'full'."
        )
    normalized = profile.strip()
    try:
        return _ENGINE_ARTIFACT_PROFILE_ARGS[normalized]
    except KeyError as exc:
        raise ValueError(
            "engine_artifact_profile must be 'compact' or 'full'."
        ) from exc


def _prepare_output_root(output_root: Path) -> Path:
    output = output_root.resolve()
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(
                "Campaign output root exists and is not a directory: "
                f"{output}"
            )
        if any(output.iterdir()):
            raise FileExistsError(
                "Refusing to overwrite or mix a reproducible campaign with "
                f"an existing non-empty output root: {output}"
            )
    else:
        output.mkdir(parents=True, exist_ok=False)
    return output


def _validate_full_artifact_contract(
    *,
    result_dir: Path,
    engine_summary: Mapping[str, Any],
) -> dict[str, Any]:
    policy = engine_summary.get("policy")
    policy = policy if isinstance(policy, Mapping) else {}
    failures: list[str] = []
    if policy.get("output_profile") != ENGINE_ARTIFACT_PROFILE_FULL:
        failures.append("summary policy.output_profile is not 'full'")
    if policy.get("lot_trace_enabled") is not True:
        failures.append("summary policy.lot_trace_enabled is not true")

    required_files: list[str] = []
    for relative_name in _FULL_ARTIFACT_REQUIRED_FILES:
        path = result_dir / Path(relative_name)
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing non-empty {relative_name}")
        else:
            required_files.append(relative_name)

    map_files = sorted(
        path.relative_to(result_dir).as_posix()
        for path in (result_dir / "maps").rglob("*.html")
        if path.is_file() and path.stat().st_size > 0
    )
    if not map_files:
        failures.append("missing non-empty maps/*.html")
    plot_files = sorted(
        path.relative_to(result_dir).as_posix()
        for path in (result_dir / "plots").rglob("*.png")
        if path.is_file() and path.stat().st_size > 0
    )
    if not plot_files:
        failures.append("missing non-empty plots/*.png")

    if failures:
        raise CanonicalClosedLoopContractError(
            "Full engine artifact contract failed under "
            f"{result_dir}: " + "; ".join(failures)
        )
    return {
        "result_dir": str(result_dir),
        "status": "validated_full",
        "summary_output_profile": str(policy["output_profile"]),
        "summary_lot_trace_enabled": True,
        "required_files": required_files,
        "map_html_files": map_files,
        "plot_png_files": plot_files,
    }


def _summary_path(result_dir: Path) -> Path:
    return result_dir / "summaries" / "first_simulation_summary.json"


def _daily_path(result_dir: Path) -> Path:
    candidates = (
        result_dir / "data" / "first_simulation_daily.csv",
        result_dir / "first_simulation_daily.csv",
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    raise CanonicalClosedLoopContractError(
        f"Missing non-empty first_simulation_daily.csv under {result_dir}"
    )


def _closed_loop_claim(summary: Mapping[str, Any]) -> tuple[bool, str, str]:
    """Read the sole authoritative provider claim and reject conflicting aliases."""

    policy = summary.get("policy")
    policy = policy if isinstance(policy, Mapping) else {}
    provider = policy.get("control_provider")
    provider = provider if isinstance(provider, Mapping) else {}
    authority_path = "$.policy.control_provider.closed_loop_claimed"
    authoritative = provider.get("closed_loop_claimed")
    if authoritative is None:
        return False, "", "missing_engine_summary_claim"
    if type(authoritative) is not bool:
        return False, authority_path, "invalid_non_boolean_engine_summary_claim"

    aliases = (
        ("$.closed_loop_claimed", summary.get("closed_loop_claimed")),
        ("$.policy.closed_loop_claimed", policy.get("closed_loop_claimed")),
    )
    for path, value in aliases:
        if value is None:
            continue
        if type(value) is not bool:
            return False, path, "invalid_non_boolean_engine_summary_claim"
        if value is not authoritative:
            return False, authority_path, "conflicting_engine_summary_claims"
    if authoritative:
        return True, authority_path, "confirmed_by_engine_summary"
    return False, authority_path, "not_claimed_by_engine_summary"


def _strict_integer_series(
    frame: pd.DataFrame,
    column: str,
    *,
    artifact: str,
) -> pd.Series:
    if column not in frame.columns:
        raise CanonicalClosedLoopContractError(
            f"{artifact} is missing required column {column!r}."
        )
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise CanonicalClosedLoopContractError(
            f"{artifact}.{column} contains a non-finite or non-numeric value."
        )
    if not (values == np.floor(values)).all():
        raise CanonicalClosedLoopContractError(
            f"{artifact}.{column} contains a non-integer value."
        )
    return values.astype(int)


def _read_claim_evidence_csv(result_dir: Path, name: str) -> pd.DataFrame:
    path = result_dir / "data" / name
    if not path.is_file() or path.stat().st_size <= 0:
        raise CanonicalClosedLoopContractError(
            f"Missing non-empty closed-loop evidence file: {path}"
        )
    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        raise CanonicalClosedLoopContractError(
            f"Cannot read closed-loop evidence file {path}: {exc}"
        ) from exc
    if frame.empty:
        raise CanonicalClosedLoopContractError(
            f"Closed-loop evidence file contains no rows: {path}"
        )
    return frame


def _validate_claimed_feedback_evidence(result_dir: Path) -> None:
    observations = _read_claim_evidence_csv(
        result_dir, "canonical_closed_loop_observations.csv"
    )
    decisions = _read_claim_evidence_csv(
        result_dir, "canonical_closed_loop_decisions.csv"
    )
    commands = _read_claim_evidence_csv(
        result_dir, "canonical_closed_loop_commands.csv"
    )
    ledger = _read_claim_evidence_csv(result_dir, "canonical_action_ledger.csv")

    observation_days = _strict_integer_series(
        observations, "day", artifact="closed-loop observations"
    )
    decision_days = _strict_integer_series(
        decisions, "decision_day", artifact="closed-loop decisions"
    )
    decision_effective_days = _strict_integer_series(
        decisions, "effective_day", artifact="closed-loop decisions"
    )
    decision_lags = _strict_integer_series(
        decisions, "causal_lag_days", artifact="closed-loop decisions"
    )
    if len(observations) != len(decisions):
        raise CanonicalClosedLoopContractError(
            "Closed-loop observation and decision row counts differ."
        )
    if observation_days.tolist() != decision_days.tolist():
        raise CanonicalClosedLoopContractError(
            "Closed-loop observation days do not match decision days."
        )
    if not (decision_effective_days == decision_days + 1).all() or not (
        decision_lags == 1
    ).all():
        raise CanonicalClosedLoopContractError(
            "Closed-loop decisions violate observation J -> action J+1."
        )
    for column in ("observation_hash",):
        if column not in observations or column not in decisions:
            raise CanonicalClosedLoopContractError(
                f"Closed-loop observation/decision evidence is missing {column!r}."
            )
    if observations["observation_hash"].astype(str).tolist() != decisions[
        "observation_hash"
    ].astype(str).tolist():
        raise CanonicalClosedLoopContractError(
            "Closed-loop decisions do not reference the matching observation hashes."
        )

    if "active" not in commands:
        raise CanonicalClosedLoopContractError(
            "Closed-loop commands are missing the active flag."
        )
    active = pd.to_numeric(commands["active"], errors="coerce")
    if active.isna().any() or not active.isin([0, 1]).all() or not active.eq(1).any():
        raise CanonicalClosedLoopContractError(
            "A claimed closed loop has no auditable active command row."
        )
    active_commands = commands.loc[active.eq(1)].copy()
    inactive_commands = commands.loc[active.eq(0)].copy()
    if not _non_neutral_effective_command_levers(inactive_commands).empty:
        raise CanonicalClosedLoopContractError(
            "An inactive command row contains a non-neutral effective lever."
        )
    if _non_neutral_effective_command_levers(active_commands).empty:
        raise CanonicalClosedLoopContractError(
            "A claimed closed loop has no non-neutral active command."
        )
    command_source_lines = _strict_integer_series(
        active_commands, "source_line", artifact="closed-loop commands"
    )
    command_effective_days = _strict_integer_series(
        active_commands, "effective_day", artifact="closed-loop commands"
    )
    command_expectations: dict[tuple[int, str], tuple[int, float]] = {}
    for position, (_, row) in enumerate(active_commands.iterrows()):
        payload = json.loads(str(row["effective_json"]))
        for action_name, raw_value in payload.items():
            action_name = str(action_name)
            value, is_neutral = _validated_control_value(
                action_name,
                raw_value,
                context=(
                    "active command source_line="
                    f"{int(command_source_lines.iloc[position])}"
                ),
            )
            # Slew limiting can leave a requested lever exactly at its physical
            # neutral value.  Preserve that value in the command audit, but do
            # not require an action-ledger row for an action that did nothing.
            if is_neutral:
                continue
            key = (int(command_source_lines.iloc[position]), action_name)
            if key in command_expectations:
                raise CanonicalClosedLoopContractError(
                    f"Duplicate active command identity {key!r}."
                )
            command_expectations[key] = (
                int(command_effective_days.iloc[position]),
                value,
            )
    if not command_expectations:
        raise CanonicalClosedLoopContractError(
            "A claimed closed loop has no non-neutral command action to audit."
        )

    required_ledger = {
        "day",
        "decision_day",
        "effective_day",
        "causal_lag_days",
        "control_source_kind",
        "source_line",
        "action",
        "effective",
        "status",
        "executed_control_volume_qty",
    }
    missing_ledger = sorted(required_ledger - set(ledger.columns))
    if missing_ledger:
        raise CanonicalClosedLoopContractError(
            "Closed-loop action ledger is missing columns: "
            + ", ".join(missing_ledger)
        )
    provider_rows = ledger.loc[
        ledger["control_source_kind"].eq("state_feedback_generated_online")
    ].copy()
    if provider_rows.empty:
        raise CanonicalClosedLoopContractError(
            "A claimed closed loop has no provider-authored action ledger row."
        )
    ledger_days = _strict_integer_series(
        provider_rows, "day", artifact="closed-loop action ledger"
    )
    ledger_decisions = _strict_integer_series(
        provider_rows, "decision_day", artifact="closed-loop action ledger"
    )
    ledger_effective = _strict_integer_series(
        provider_rows, "effective_day", artifact="closed-loop action ledger"
    )
    ledger_lags = _strict_integer_series(
        provider_rows, "causal_lag_days", artifact="closed-loop action ledger"
    )
    if not (ledger_effective == ledger_decisions + 1).all() or not (
        ledger_days == ledger_effective
    ).all() or not (ledger_lags == 1).all():
        raise CanonicalClosedLoopContractError(
            "Closed-loop action ledger violates decision J -> execution J+1."
        )
    ledger_source_lines = _strict_integer_series(
        provider_rows, "source_line", artifact="closed-loop action ledger"
    )
    observed_command_actions: set[tuple[int, str]] = set()
    for position, (_, row) in enumerate(provider_rows.iterrows()):
        key = (
            int(ledger_source_lines.iloc[position]),
            str(row["action"]),
        )
        expected = command_expectations.get(key)
        if expected is None:
            raise CanonicalClosedLoopContractError(
                f"Action ledger row has no matching active command: {key!r}."
            )
        expected_day, expected_value = expected
        try:
            ledger_value = float(row["effective"])
        except (TypeError, ValueError) as exc:
            raise CanonicalClosedLoopContractError(
                f"Action ledger effective value is not numeric for {key!r}."
            ) from exc
        if not math.isfinite(ledger_value) or not math.isclose(
            ledger_value,
            expected_value,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise CanonicalClosedLoopContractError(
                f"Action ledger effective value does not match command {key!r}."
            )
        if int(ledger_days.iloc[position]) != expected_day:
            raise CanonicalClosedLoopContractError(
                f"Action ledger day does not match command {key!r}."
            )
        observed_command_actions.add(key)
    missing_command_actions = sorted(
        set(command_expectations) - observed_command_actions
    )
    if missing_command_actions:
        raise CanonicalClosedLoopContractError(
            "Active command actions are absent from the action ledger: "
            + ", ".join(repr(item) for item in missing_command_actions[:5])
        )
    executed = pd.to_numeric(
        provider_rows["executed_control_volume_qty"], errors="coerce"
    )
    physically_applied = provider_rows["status"].eq("applied") & executed.gt(1e-9)
    if not physically_applied.any():
        raise CanonicalClosedLoopContractError(
            "A claimed closed loop has no physically applied feedback action."
        )


def _same_path(value: Any, expected: Path) -> bool:
    if not str(value or "").strip():
        return False
    try:
        return Path(str(value)).resolve() == expected.resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def _validate_and_extract(
    *,
    result_dir: Path,
    graph_path: Path,
    graph_sha256: str,
    risk_events_path: Path | None,
    risk_events_sha256: str,
    expected_risk_event_count: int | None,
    expected_seed: int,
    expected_days: int,
    expected_scenario_id: str,
    expect_state_dependent_risks: bool,
    run_policy: str,
) -> tuple[dict[str, Any], dict[str, float | str], bool, str, str]:
    summary_file = _summary_path(result_dir)
    summary = _load_json_object(summary_file, "canonical engine summary")
    errors: list[str] = []

    if str(summary.get("scenario_id") or "") != str(expected_scenario_id):
        errors.append(
            "scenario mismatch: "
            f"expected {expected_scenario_id}, got {summary.get('scenario_id')!r}"
        )
    try:
        actual_days = int(summary.get("sim_days", -1))
    except (TypeError, ValueError):
        actual_days = -1
    if actual_days != int(expected_days):
        errors.append(
            f"horizon mismatch: expected {expected_days}, got {summary.get('sim_days')!r}"
        )
    if not _same_path(summary.get("input_file"), graph_path):
        errors.append(
            f"input graph mismatch: expected {graph_path}, "
            f"got {summary.get('input_file')!r}"
        )
    if str(summary.get("input_sha256") or "") != graph_sha256:
        errors.append("input graph SHA-256 mismatch")

    policy_summary = summary.get("policy")
    if not isinstance(policy_summary, Mapping):
        errors.append("summary.policy is missing or is not an object")
        policy_summary = {}
    try:
        actual_seed = int(policy_summary.get("seed", -1))
    except (TypeError, ValueError):
        actual_seed = -1
    if actual_seed != int(expected_seed):
        errors.append(
            f"seed mismatch: expected {expected_seed}, got {policy_summary.get('seed')!r}"
        )
    if policy_summary.get("common_random_numbers") is not True:
        errors.append("common_random_numbers is not explicitly true")

    state_risk = policy_summary.get("supplier_state_dependent_risk")
    if isinstance(state_risk, Mapping):
        if state_risk.get("enabled") is not bool(expect_state_dependent_risks):
            errors.append("supplier state-dependent-risk setting mismatch")

    supplier_risk = policy_summary.get("supplier_risk")
    if risk_events_path is not None:
        if not isinstance(supplier_risk, Mapping):
            errors.append("summary.policy.supplier_risk is missing")
        else:
            if supplier_risk.get("enabled") is not True:
                errors.append("configured supplier risk events are not enabled")
            if not _same_path(supplier_risk.get("events_csv"), risk_events_path):
                errors.append("supplier risk-events path mismatch")
            if (
                str(supplier_risk.get("events_csv_sha256") or "")
                != risk_events_sha256
            ):
                errors.append("supplier risk-events SHA-256 mismatch")
            if expected_risk_event_count is not None:
                try:
                    actual_count = int(supplier_risk.get("event_count", -1))
                except (TypeError, ValueError):
                    actual_count = -1
                if actual_count != expected_risk_event_count:
                    errors.append(
                        "supplier risk-event count mismatch: "
                        f"expected {expected_risk_event_count}, got "
                        f"{supplier_risk.get('event_count')!r}"
                    )

    daily_file = _daily_path(result_dir)
    daily = pd.read_csv(daily_file)
    if len(daily) != int(expected_days):
        errors.append(
            f"daily trajectory length mismatch: expected {expected_days}, got {len(daily)}"
        )

    claimed, claim_path, claim_status = _closed_loop_claim(summary)
    if run_policy == REFERENCE_POLICY and claimed:
        errors.append("MRP reference unexpectedly claims closed-loop operation")
    if run_policy == FEEDBACK_POLICY and claimed:
        control_provider = policy_summary.get("control_provider")
        if not isinstance(control_provider, Mapping):
            errors.append("summary.policy.control_provider is missing")
        else:
            lookahead = control_provider.get(
                "controller_observation_forecast_lookahead_days"
            )
            if isinstance(lookahead, bool) or not isinstance(lookahead, int):
                errors.append(
                    "controller observation lookahead is not an integer"
                )
            elif lookahead != 0:
                errors.append(
                    f"controller observation lookahead is {lookahead}, expected 0"
                )
            demand_window = control_provider.get(
                "demand_realization_window_days_effective"
            )
            if (
                isinstance(demand_window, bool)
                or not isinstance(demand_window, int)
                or demand_window != 1
            ):
                errors.append(
                    "effective realized-demand window is not exactly one day"
                )
            if control_provider.get("future_realization_access") is not False:
                errors.append("future_realization_access is not explicitly false")
            if control_provider.get("causal_lag_days") != 1 or isinstance(
                control_provider.get("causal_lag_days"), bool
            ):
                errors.append("controller causal_lag_days is not exactly 1")
            if (
                control_provider.get("provider_causal_contract_satisfied")
                is not True
            ):
                errors.append("provider causal contract is not explicitly satisfied")
            if (
                control_provider.get("observation_causal_contract_satisfied")
                is not True
            ):
                errors.append(
                    "controller observation causal contract is not explicitly satisfied"
                )
            if control_provider.get("physical_action_applied") is not True:
                errors.append("physical feedback application is not explicitly true")
            if (
                control_provider.get("controller_warmup_matches_physical_warmup")
                is not True
            ):
                errors.append(
                    "controller dynamic warm-up does not match physical warm-up"
                )
        try:
            _validate_claimed_feedback_evidence(result_dir)
        except CanonicalClosedLoopContractError as exc:
            errors.append(str(exc))

    kpis = extract_canonical_kpis(result_dir)
    if not kpis:
        errors.append("canonical KPI extraction returned no values")
    if errors:
        raise CanonicalClosedLoopContractError(
            f"Invalid {run_policy} seed {expected_seed} output: " + "; ".join(errors)
        )
    return summary, kpis, claimed, claim_path, claim_status


def _risk_event_count(path: Path | None) -> int | None:
    if path is None:
        return None
    frame = pd.read_csv(path)
    return int(len(frame))


def _run_engine(command: Sequence[str], *, cwd: Path, result_dir: Path) -> None:
    """Run the engine, retain both streams, and re-raise any process failure."""

    result_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        (result_dir / "engine_stdout.log").write_text(
            exc.stdout or "", encoding="utf-8"
        )
        (result_dir / "engine_stderr.log").write_text(
            exc.stderr or "", encoding="utf-8"
        )
        raise
    (result_dir / "engine_stdout.log").write_text(
        completed.stdout or "", encoding="utf-8"
    )
    (result_dir / "engine_stderr.log").write_text(
        completed.stderr or "", encoding="utf-8"
    )


def _pairing_contract(runs: pd.DataFrame, seeds: Sequence[int]) -> None:
    for seed in seeds:
        paired = runs.loc[runs["seed"].eq(int(seed))]
        policies = set(paired["policy"].astype(str))
        if policies != {REFERENCE_POLICY, FEEDBACK_POLICY} or len(paired) != 2:
            raise CanonicalClosedLoopContractError(
                f"Seed {seed} is not an exact MRP/feedback pair: {sorted(policies)}"
            )
        for column in (
            "graph_sha256",
            "risk_events_sha256",
            "scenario_id",
            "days",
            "common_random_numbers",
            "state_dependent_risks",
            "state_risk_observation_warmup_days",
        ):
            if paired[column].nunique(dropna=False) != 1:
                raise CanonicalClosedLoopContractError(
                    f"Seed {seed} violates paired contract for {column}."
                )


def _paired_delta_frame(runs: pd.DataFrame) -> pd.DataFrame:
    feedback = runs.loc[runs["policy"].eq(FEEDBACK_POLICY)].copy()
    identity = [
        "seed",
        "policy",
        "status",
        "result_dir",
        "true_state_feedback",
        "engine_closed_loop_claimed",
        "closed_loop_claim_path",
        "closed_loop_evidence_status",
        "graph_sha256",
        "risk_events_sha256",
        "control_policy_sha256",
    ]
    metric_columns: list[str] = []
    for metric in CANONICAL_KPI_NAMES:
        metric_columns.extend(
            [metric, f"mrp_reference_{metric}", f"delta_vs_mrp_{metric}"]
        )
    extra = ["delta_vs_mrp_recovery_time_status"]
    columns = [
        name for name in [*identity, *metric_columns, *extra] if name in feedback
    ]
    result = feedback[columns].sort_values("seed").reset_index(drop=True)
    result.insert(3, "pairing_contract_verified", True)
    return result


def _augment_summary(summary: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    evidence = (
        runs.groupby("policy", sort=False)
        .agg(
            completed_run_count=("seed", "size"),
            engine_closed_loop_claim_count=(
                "engine_closed_loop_claimed",
                "sum",
            ),
            true_state_feedback_count=("true_state_feedback", "sum"),
        )
        .reset_index()
    )
    result = summary.merge(evidence, on="policy", how="left", validate="one_to_one")
    result["all_feedback_runs_confirmed_by_engine"] = np.where(
        result["policy"].eq(FEEDBACK_POLICY),
        result["true_state_feedback_count"].eq(result["completed_run_count"]),
        False,
    )
    return result


def _numeric(frame: pd.DataFrame, names: Sequence[str]) -> pd.Series:
    for name in names:
        if name in frame:
            return pd.to_numeric(frame[name], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=frame.index, dtype=float)


def _save_comparison_plot(
    output_root: Path,
    runs: pd.DataFrame,
    paired_deltas: pd.DataFrame,
) -> tuple[Path | None, str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("matplotlib"):
            return None, "matplotlib_unavailable"
        raise

    first_seed = int(paired_deltas["seed"].min())
    daily_by_policy: dict[str, pd.DataFrame] = {}
    for policy in (REFERENCE_POLICY, FEEDBACK_POLICY):
        result_dir = Path(
            runs.loc[
                runs["seed"].eq(first_seed) & runs["policy"].eq(policy),
                "result_dir",
            ].iloc[0]
        )
        daily_by_policy[policy] = pd.read_csv(_daily_path(result_dir))

    baseline = daily_by_policy[REFERENCE_POLICY]
    demand_scale = max(
        float(_numeric(baseline, ("demand", "demand_qty")).replace(0, np.nan).median()),
        1.0,
    )
    colors = {REFERENCE_POLICY: "#68768a", FEEDBACK_POLICY: "#167d73"}
    labels = {REFERENCE_POLICY: "MRP", FEEDBACK_POLICY: "Feedback canonique"}
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.5), constrained_layout=True)
    for policy, daily in daily_by_policy.items():
        day = _numeric(daily, ("day",)) if "day" in daily else pd.Series(range(len(daily)))
        demand = _numeric(daily, ("demand", "demand_qty"))
        served = _numeric(daily, ("served", "served_qty"))
        service = (served / demand.replace(0.0, np.nan)).fillna(1.0).clip(0, 1)
        backlog = _numeric(daily, ("backlog_end", "backlog")) / demand_scale
        axes[0, 0].plot(day, service, color=colors[policy], label=labels[policy])
        axes[0, 1].plot(day, backlog, color=colors[policy], label=labels[policy])
    axes[0, 0].set(title=f"Service journalier — graine {first_seed}", ylabel="taux")
    axes[0, 1].set(title="Backlog — même trajectoire", ylabel="jours de demande")
    for axis in axes[0]:
        axis.set_xlabel("jour")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False)

    for policy, daily in daily_by_policy.items():
        day = (
            _numeric(daily, ("day",))
            if "day" in daily
            else pd.Series(range(len(daily)))
        )
        inventory = _numeric(daily, ("inventory_total",)) / demand_scale
        axes[1, 0].plot(
            day,
            inventory,
            color=colors[policy],
            label=labels[policy],
        )
    axes[1, 0].set(
        title="Stock total — trajectoires comparées",
        xlabel="jour",
        ylabel="stock / demande médiane",
    )
    axes[1, 0].grid(alpha=0.2)
    axes[1, 0].legend(frameon=False)

    relative_specs = (
        ("mean_inventory_days", "Stock\nmoyen"),
        ("order_nervousness", "Nervosité\ncommandes"),
        ("production_nervousness", "Nervosité\nproduction"),
        ("supplier_risk_area", "Risque\nfournisseur"),
        ("total_economic_exposure", "Exposition\néconomique"),
    )
    relative_values: list[float] = []
    relative_ci_low_errors: list[float] = []
    relative_ci_high_errors: list[float] = []
    relative_labels: list[str] = []
    for metric, label in relative_specs:
        baseline_mean = float(
            pd.to_numeric(
                paired_deltas[f"mrp_reference_{metric}"], errors="coerce"
            ).mean()
        )
        paired_metric_deltas = pd.to_numeric(
            paired_deltas[f"delta_vs_mrp_{metric}"], errors="coerce"
        ).dropna()
        delta_mean = float(paired_metric_deltas.mean())
        relative_labels.append(label)
        relative_value = (
            100.0 * delta_mean / baseline_mean
            if math.isfinite(baseline_mean) and abs(baseline_mean) > 1e-12
            else math.nan
        )
        relative_values.append(relative_value)
        if (
            math.isfinite(relative_value)
            and len(paired_metric_deltas) >= 2
        ):
            half_width = (
                _student_t_critical_95(len(paired_metric_deltas) - 1)
                * float(paired_metric_deltas.std(ddof=1))
                / math.sqrt(len(paired_metric_deltas))
            )
            relative_bounds = sorted(
                (
                    100.0 * (delta_mean - half_width) / baseline_mean,
                    100.0 * (delta_mean + half_width) / baseline_mean,
                )
            )
            relative_ci_low_errors.append(
                max(0.0, relative_value - relative_bounds[0])
            )
            relative_ci_high_errors.append(
                max(0.0, relative_bounds[1] - relative_value)
            )
        else:
            relative_ci_low_errors.append(0.0)
            relative_ci_high_errors.append(0.0)
    bar_colors = [
        "#b9473f" if value > 0.0 else "#167d73"
        for value in relative_values
    ]
    bars = axes[1, 1].bar(
        range(len(relative_values)),
        relative_values,
        color=bar_colors,
        alpha=0.88,
        yerr=np.asarray(
            [relative_ci_low_errors, relative_ci_high_errors], dtype=float
        ),
        capsize=4,
        error_kw={"ecolor": "#374151", "elinewidth": 1.0, "capthick": 1.0},
    )
    axes[1, 1].axhline(0.0, color="#4b5563", linewidth=0.8)
    axes[1, 1].set(
        title="Effets dominants — moyenne et IC95 Student appariés",
        ylabel="delta feedback − MRP (%)",
        xticks=range(len(relative_labels)),
        xticklabels=relative_labels,
    )
    axes[1, 1].grid(axis="y", alpha=0.2)
    for bar, value in zip(bars, relative_values):
        if math.isfinite(value):
            axes[1, 1].annotate(
                f"{value:+.1f}%",
                (bar.get_x() + bar.get_width() / 2.0, bar.get_height()),
                xytext=(0, 4 if value >= 0 else -12),
                textcoords="offset points",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8,
            )
    expedite_delta = float(
        pd.to_numeric(
            paired_deltas["delta_vs_mrp_expedited_qty"], errors="coerce"
        ).mean()
    )
    risk_creation_delta = float(
        pd.to_numeric(
            paired_deltas["delta_vs_mrp_canonical_risk_creation_proxy"],
            errors="coerce",
        ).mean()
    )
    axes[1, 1].set_title(
        "Effets dominants — moyenne et IC95 Student appariés\n"
        f"Expediting {expedite_delta / 1_000_000.0:+.1f} M unités ; "
        f"risque créé {risk_creation_delta:+.3f}"
    )

    confirmed = int(paired_deltas["true_state_feedback"].sum())
    fig.suptitle(
        "Boucle fermée canonique — comparaison appariée\n"
        f"claim moteur confirmé pour {confirmed}/{len(paired_deltas)} runs feedback",
        fontsize=13,
    )
    plot_path = output_root / "canonical_closed_loop_comparison.png"
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)
    return plot_path, "written"


def _validated_control_value(
    action_name: str,
    raw_value: Any,
    *,
    context: str,
) -> tuple[float, bool]:
    """Return a finite value and whether it equals the engine neutral value."""

    bound = CONTROL_BOUNDS.get(action_name)
    if bound is None:
        raise CanonicalClosedLoopContractError(
            f"Unknown effective control lever {action_name!r} in {context}."
        )
    if isinstance(raw_value, bool):
        raise CanonicalClosedLoopContractError(
            f"Boolean effective lever {action_name!r} in {context}."
        )
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise CanonicalClosedLoopContractError(
            f"Non-numeric effective lever {action_name!r} in {context}."
        ) from exc
    if not math.isfinite(value):
        raise CanonicalClosedLoopContractError(
            f"Non-finite effective lever {action_name!r} in {context}."
        )
    neutral = float(bound.neutral)
    return value, math.isclose(value, neutral, rel_tol=1e-12, abs_tol=1e-12)


def _non_neutral_effective_command_levers(commands: pd.DataFrame) -> pd.DataFrame:
    """Expand commands and retain only levers that can change the plant."""

    levers = _effective_command_levers(commands)
    if levers.empty:
        return levers
    neutral_by_action = {
        action_name: float(bound.neutral)
        for action_name, bound in CONTROL_BOUNDS.items()
    }
    unknown = sorted(set(levers["action"]) - set(neutral_by_action))
    if unknown:
        raise CanonicalClosedLoopContractError(
            "Unknown effective control lever(s): " + ", ".join(unknown)
        )
    neutral_values = levers["action"].map(neutral_by_action).astype(float)
    is_neutral = np.isclose(
        levers["effective_value"].to_numpy(dtype=float),
        neutral_values.to_numpy(dtype=float),
        rtol=1e-12,
        atol=1e-12,
    )
    return levers.loc[~is_neutral].copy()


def _effective_command_levers(commands: pd.DataFrame) -> pd.DataFrame:
    """Expand engine ``effective_json`` commands and verify their causal lag."""

    required = {"decision_day", "effective_day", "effective_json"}
    missing = sorted(required - set(commands.columns))
    if missing:
        raise CanonicalClosedLoopContractError(
            "Closed-loop commands CSV is missing columns: " + ", ".join(missing)
        )
    rows: list[dict[str, Any]] = []
    for source_row, row in commands.iterrows():
        try:
            decision_day = int(row["decision_day"])
            effective_day = int(row["effective_day"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise CanonicalClosedLoopContractError(
                f"Invalid command causal days at CSV row {source_row}."
            ) from exc
        if effective_day != decision_day + 1:
            raise CanonicalClosedLoopContractError(
                "Closed-loop command violates decision J -> action J+1 at "
                f"CSV row {source_row}: decision_day={decision_day}, "
                f"effective_day={effective_day}."
            )
        raw = row.get("effective_json", "")
        if pd.isna(raw) or not str(raw).strip():
            payload: Any = {}
        else:
            try:
                payload = json.loads(str(raw))
            except json.JSONDecodeError as exc:
                raise CanonicalClosedLoopContractError(
                    f"Invalid effective_json at command CSV row {source_row}: {exc}"
                ) from exc
        if not isinstance(payload, Mapping):
            raise CanonicalClosedLoopContractError(
                f"effective_json must be an object at command CSV row {source_row}."
            )
        for action, raw_value in payload.items():
            action = str(action)
            value, _ = _validated_control_value(
                action,
                raw_value,
                context=f"command CSV row {source_row}",
            )
            rows.append(
                {
                    "decision_day": decision_day,
                    "effective_day": effective_day,
                    "causal_lag_days": 1,
                    "action": action,
                    "effective_value": value,
                    "scope_type": str(row.get("scope_type") or ""),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "decision_day",
                "effective_day",
                "causal_lag_days",
                "action",
                "effective_value",
                "scope_count",
            ]
        )
    expanded = pd.DataFrame(rows)
    return (
        expanded.groupby(
            ["decision_day", "effective_day", "causal_lag_days", "action"],
            as_index=False,
            sort=True,
        )
        .agg(
            effective_value=("effective_value", "mean"),
            scope_count=("scope_type", "size"),
        )
        .sort_values(["effective_day", "action"])
        .reset_index(drop=True)
    )


def _trajectory_delta(
    reference: pd.DataFrame,
    feedback: pd.DataFrame,
) -> tuple[pd.DataFrame, str, str] | None:
    """Return one aligned feedback-minus-MRP physical trajectory."""

    def day_axis(frame: pd.DataFrame) -> pd.Series:
        if "day" in frame:
            return pd.to_numeric(frame["day"], errors="raise").astype(int)
        return pd.Series(range(len(frame)), index=frame.index, dtype=int)

    signal_name = ""
    label = ""
    if "inventory_total" in reference and "inventory_total" in feedback:
        reference_signal = pd.to_numeric(
            reference["inventory_total"], errors="raise"
        ).astype(float)
        feedback_signal = pd.to_numeric(
            feedback["inventory_total"], errors="raise"
        ).astype(float)
        signal_name = "inventory_total"
        label = "Delta inventaire / demande mediane"
    else:
        order_columns = (
            "estimated_source_ordered_qty",
            "external_procured_ordered_qty",
        )
        available = [
            name for name in order_columns if name in reference and name in feedback
        ]
        if not available:
            return None
        reference_signal = sum(
            (
                pd.to_numeric(reference[name], errors="raise").astype(float)
                for name in available
            ),
            start=pd.Series(0.0, index=reference.index),
        )
        feedback_signal = sum(
            (
                pd.to_numeric(feedback[name], errors="raise").astype(float)
                for name in available
            ),
            start=pd.Series(0.0, index=feedback.index),
        )
        signal_name = "total_ordered_qty"
        label = "Delta commandes / demande mediane"

    demand = _numeric(reference, ("demand", "demand_qty"))
    scale_value = float(demand.replace(0.0, np.nan).median())
    scale = scale_value if math.isfinite(scale_value) and scale_value > 0.0 else 1.0
    reference_frame = pd.DataFrame(
        {"day": day_axis(reference), "reference": reference_signal / scale}
    )
    feedback_frame = pd.DataFrame(
        {"day": day_axis(feedback), "feedback": feedback_signal / scale}
    )
    aligned = reference_frame.merge(
        feedback_frame,
        on="day",
        how="inner",
        validate="one_to_one",
    )
    if aligned.empty:
        return None
    aligned["delta_feedback_minus_mrp"] = (
        aligned["feedback"] - aligned["reference"]
    )
    return aligned, signal_name, label


def _save_control_diagnostics_plot(
    output_root: Path,
    runs: pd.DataFrame,
) -> tuple[Path | None, str]:
    """Plot canonical feedback evidence for the first paired feedback seed."""

    feedback_rows = runs.loc[runs["policy"].eq(FEEDBACK_POLICY)].sort_values("seed")
    if feedback_rows.empty:
        return None, "no_feedback_run"
    first_seed = int(feedback_rows.iloc[0]["seed"])
    feedback_dir = Path(feedback_rows.iloc[0]["result_dir"])
    reference_match = runs.loc[
        runs["policy"].eq(REFERENCE_POLICY) & runs["seed"].eq(first_seed)
    ]
    if reference_match.empty:
        return None, "missing_paired_mrp_run"
    reference_dir = Path(reference_match.iloc[0]["result_dir"])

    audit_paths = {
        "observations": feedback_dir
        / "data"
        / "canonical_closed_loop_observations.csv",
        "decisions": feedback_dir
        / "data"
        / "canonical_closed_loop_decisions.csv",
        "commands": feedback_dir
        / "data"
        / "canonical_closed_loop_commands.csv",
    }
    missing_files = sorted(
        path.name
        for path in audit_paths.values()
        if not path.is_file() or path.stat().st_size <= 0
    )
    if missing_files:
        return None, "missing_feedback_audit_csvs:" + ",".join(missing_files)

    observations = pd.read_csv(audit_paths["observations"])
    decisions = pd.read_csv(audit_paths["decisions"])
    commands = pd.read_csv(audit_paths["commands"])
    empty_frames = sorted(
        name
        for name, frame in {
            "observations": observations,
            "decisions": decisions,
            "commands": commands,
        }.items()
        if frame.empty
    )
    if empty_frames:
        return None, "empty_feedback_audit_csvs:" + ",".join(empty_frames)

    required_observation_columns = {
        "day",
        "service_level",
        "backlog_days",
        "supplier_disruption_score",
        "supplier_stress",
        "production_utilization",
        "supplier_utilization",
    }
    required_decision_columns = {
        "decision_day",
        "effective_day",
        "confirmed_regime",
        "selected_policy",
    }
    missing_observations = sorted(
        required_observation_columns - set(observations.columns)
    )
    missing_decisions = sorted(required_decision_columns - set(decisions.columns))
    if missing_observations or missing_decisions:
        details: list[str] = []
        if missing_observations:
            details.append("observations=" + ",".join(missing_observations))
        if missing_decisions:
            details.append("decisions=" + ",".join(missing_decisions))
        return None, "missing_feedback_audit_columns:" + ";".join(details)

    levers = _effective_command_levers(commands)
    if levers.empty:
        return None, "no_effective_feedback_levers"
    reference_daily = pd.read_csv(_daily_path(reference_dir))
    feedback_daily = pd.read_csv(_daily_path(feedback_dir))
    delta_result = _trajectory_delta(reference_daily, feedback_daily)
    if delta_result is None:
        return None, "missing_comparable_inventory_or_order_trajectory"
    trajectory_delta, delta_signal_name, delta_label = delta_result

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("matplotlib"):
            return None, "matplotlib_unavailable"
        raise

    observation_day = pd.to_numeric(observations["day"], errors="raise").astype(int)
    decision_day = pd.to_numeric(decisions["decision_day"], errors="raise").astype(int)
    colors = {
        "service": "#2463a6",
        "backlog": "#a64242",
        "disruption": "#d17a22",
        "stress": "#8c4aa8",
        "production_utilization": "#287f6f",
        "supplier_utilization": "#577590",
    }
    fig, axes = plt.subplots(3, 2, figsize=(15.0, 12.0), constrained_layout=True)

    service_axis = axes[0, 0]
    backlog_axis = service_axis.twinx()
    service_axis.plot(
        observation_day,
        pd.to_numeric(observations["service_level"], errors="raise"),
        color=colors["service"],
        label="service",
    )
    backlog_axis.plot(
        observation_day,
        pd.to_numeric(observations["backlog_days"], errors="raise"),
        color=colors["backlog"],
        label="backlog (jours)",
    )
    service_axis.set(
        title="Etat observe en fin de jour J : service et backlog",
        xlabel="jour observe J",
        ylabel="service",
    )
    backlog_axis.set_ylabel("backlog (jours)", color=colors["backlog"])
    service_axis.set_ylim(-0.02, 1.02)
    service_axis.grid(alpha=0.2)
    service_axis.legend(loc="lower left", frameon=False)
    backlog_axis.legend(loc="upper right", frameon=False)

    state_axis = axes[0, 1]
    for column, label, color in (
        ("supplier_disruption_score", "severite disruption", colors["disruption"]),
        ("supplier_stress", "stress fournisseur", colors["stress"]),
        ("production_utilization", "utilisation production", colors["production_utilization"]),
        ("supplier_utilization", "utilisation fournisseur", colors["supplier_utilization"]),
    ):
        state_axis.plot(
            observation_day,
            pd.to_numeric(observations[column], errors="raise"),
            label=label,
            color=color,
        )
    state_axis.set(
        title="Etat observe : disruption, stress et utilisations",
        xlabel="jour observe J",
        ylabel="niveau / ratio",
    )
    state_axis.grid(alpha=0.2)
    state_axis.legend(frameon=False, fontsize=8, ncol=2)

    regime_axis = axes[1, 0]
    policy_axis = regime_axis.twinx()
    canonical_regime_order = [
        "NOMINAL",
        "MATERIAL_TENSION",
        "CAPACITY_SATURATION",
        "SUPPLIER_STRESS",
        "OSCILLATORY",
        "CRISIS",
        "RECOVERY",
        "POST_CRISIS_OVERSTOCK",
    ]
    observed_regimes = decisions["confirmed_regime"].fillna("UNKNOWN").astype(str)
    regime_order = [
        name for name in canonical_regime_order if name in set(observed_regimes)
    ]
    regime_order.extend(
        sorted(set(observed_regimes) - set(canonical_regime_order))
    )
    selected_policies = decisions["selected_policy"].fillna("UNKNOWN").astype(str)
    policy_order = list(dict.fromkeys(selected_policies.tolist()))
    regime_codes = observed_regimes.map({name: index for index, name in enumerate(regime_order)})
    policy_codes = selected_policies.map({name: index for index, name in enumerate(policy_order)})
    regime_axis.step(
        decision_day,
        regime_codes,
        where="post",
        color="#4f5d75",
        marker="o",
        markersize=2.5,
        label="regime confirme",
    )
    policy_axis.step(
        decision_day,
        policy_codes,
        where="post",
        color="#167d73",
        linestyle="--",
        label="politique selectionnee",
    )
    regime_axis.set_yticks(range(len(regime_order)), regime_order, fontsize=7)
    policy_axis.set_yticks(range(len(policy_order)), policy_order, fontsize=7)
    regime_axis.set(
        title="Chronologie regime confirme / politique selectionnee",
        xlabel="jour de decision J",
    )
    regime_axis.grid(alpha=0.2, axis="x")
    regime_axis.legend(loc="upper left", frameon=False, fontsize=8)
    policy_axis.legend(loc="lower right", frameon=False, fontsize=8)

    lever_axis = axes[1, 1]
    direct_axis = lever_axis.twinx()
    lever_pivot = levers.pivot(
        index="effective_day", columns="action", values="effective_value"
    ).sort_index()
    neutral_values = {
        "order_multiplier": 1.0,
        "safety_stock_multiplier": 1.0,
        "production_target_multiplier": 1.0,
        "capacity_multiplier": 1.0,
        "external_procurement_multiplier": 1.0,
        "priority_weight": 1.0,
        "expedite_level": 0.0,
        "lead_time_adjustment_days": 0.0,
    }
    informative_actions = [
        name
        for name in lever_pivot.columns
        if lever_pivot[name].nunique(dropna=True) > 1
        or (
            lever_pivot[name].sub(neutral_values.get(name, 0.0)).abs().max()
            > 1e-12
        )
    ]
    if not informative_actions:
        informative_actions = list(lever_pivot.columns)
    direct_actions = {"expedite_level", "lead_time_adjustment_days"}
    for index, action in enumerate(informative_actions):
        target_axis = direct_axis if action in direct_actions else lever_axis
        target_axis.step(
            lever_pivot.index,
            lever_pivot[action],
            where="post",
            label=action,
            linestyle="--" if action in direct_actions else "-",
            color=f"C{index % 10}",
        )
    lever_axis.axhline(1.0, color="#777777", linewidth=0.8, alpha=0.45)
    direct_axis.axhline(0.0, color="#777777", linewidth=0.8, alpha=0.35)
    lever_axis.set(
        title="Levers effectifs au jour J+1 (calcules en fin de J)",
        xlabel="jour effectif J+1",
        ylabel="multiplicateurs / poids",
    )
    direct_axis.set_ylabel("expedite / ajustement de lead time")
    lever_axis.grid(alpha=0.2)
    lines_left, labels_left = lever_axis.get_legend_handles_labels()
    lines_right, labels_right = direct_axis.get_legend_handles_labels()
    lever_axis.legend(
        [*lines_left, *lines_right],
        [*labels_left, *labels_right],
        frameon=False,
        fontsize=7,
        ncol=2,
        loc="best",
    )

    causal_axis = axes[2, 0]
    causal_pairs = levers[["decision_day", "effective_day"]].drop_duplicates()
    for _, pair in causal_pairs.iterrows():
        causal_axis.plot(
            [pair["decision_day"], pair["effective_day"]],
            [0.0, 1.0],
            color="#6a7a89",
            alpha=0.35,
            linewidth=0.8,
        )
    causal_axis.scatter(
        causal_pairs["decision_day"],
        np.zeros(len(causal_pairs)),
        label="decision J",
        color="#4f5d75",
        s=14,
    )
    causal_axis.scatter(
        causal_pairs["effective_day"],
        np.ones(len(causal_pairs)),
        label="action J+1",
        color="#d17a22",
        marker=">",
        s=20,
    )
    causal_axis.set_yticks([0.0, 1.0], ["decision J", "action J+1"])
    causal_axis.set(
        title="Preuve temporelle : decision J -> action J+1 (lag = 1 jour)",
        xlabel="jour mesure",
        ylim=(-0.35, 1.35),
    )
    causal_axis.grid(alpha=0.2, axis="x")
    causal_axis.legend(frameon=False, fontsize=8)

    delta_axis = axes[2, 1]
    delta_axis.plot(
        trajectory_delta["day"],
        trajectory_delta["delta_feedback_minus_mrp"],
        color="#167d73",
        linewidth=1.6,
        label="feedback - MRP",
    )
    delta_axis.fill_between(
        trajectory_delta["day"],
        0.0,
        trajectory_delta["delta_feedback_minus_mrp"],
        color="#167d73",
        alpha=0.16,
    )
    delta_axis.axhline(0.0, color="#333333", linewidth=0.9)
    delta_axis.set(
        title=f"Delta de trajectoire apparie : {delta_signal_name}",
        xlabel="jour",
        ylabel=delta_label,
    )
    delta_axis.grid(alpha=0.2)
    delta_axis.legend(frameon=False)

    fig.suptitle(
        "Diagnostic de regulation canonique en boucle fermee\n"
        f"premier seed feedback={first_seed}; observation fin J, commande effective J+1",
        fontsize=14,
    )
    plot_path = output_root / "canonical_closed_loop_control_diagnostics.png"
    try:
        fig.savefig(plot_path, dpi=160)
    finally:
        plt.close(fig)
    return plot_path, "written"


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


def run_canonical_closed_loop(
    *,
    repo_root: Path,
    graph_path: Path,
    control_policy_path: Path,
    seeds: Sequence[int],
    output_root: Path,
    days: int,
    scenario_id: str = "scn:BASE",
    engine_script: Path | None = None,
    python_executable: str | None = None,
    supplier_risk_events_path: Path | None = None,
    enable_state_dependent_risks: bool = True,
    engine_extra_args: Sequence[str] = (),
    feedback_engine_extra_args: Sequence[str] = (),
    control_policy_flag: str = _CONTROL_POLICY_FLAG,
    engine_profile_metadata: Mapping[str, Any] | None = None,
    engine_artifact_profile: str = ENGINE_ARTIFACT_PROFILE_COMPACT,
    make_plot: bool = True,
) -> CanonicalClosedLoopArtifacts:
    """Execute strict, reproducible MRP/feedback pairs on the canonical engine."""

    root = repo_root.resolve()
    graph = _require_file(graph_path, "canonical graph")
    policy_config = _require_file(control_policy_path, "control-policy JSON")
    _load_json_object(policy_config, "control-policy JSON")
    engine = _require_file(
        engine_script
        or root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py",
        "canonical engine",
    )
    risk_events = (
        _require_file(supplier_risk_events_path, "supplier risk-events CSV")
        if supplier_risk_events_path is not None
        else None
    )
    paired_seeds = _ordered_seeds(seeds)
    if int(days) <= 0:
        raise ValueError("days must be a positive integer")
    if not str(scenario_id).strip():
        raise ValueError("scenario_id cannot be empty")
    extra_args = _validate_extra_args(engine_extra_args)
    feedback_extra_args = _validate_extra_args(feedback_engine_extra_args)
    artifact_args = _engine_artifact_args(engine_artifact_profile)
    artifact_profile = str(engine_artifact_profile).strip()
    if control_policy_flag not in {
        _CONTROL_POLICY_FLAG,
        _CONTROL_POLICY_V2_FLAG,
        _CONTROL_POLICY_V3_FLAG,
    }:
        raise ValueError(
            "control_policy_flag must select the V1, V2 or V3 engine interface."
        )

    output = _prepare_output_root(output_root)
    graph_hash = _sha256(graph)
    policy_hash = _sha256(policy_config)
    risk_hash = _sha256(risk_events) if risk_events is not None else ""
    risk_count = _risk_event_count(risk_events)
    interpreter = python_executable or sys.executable
    profile_metadata = dict(engine_profile_metadata or {})
    commands: list[dict[str, Any]] = []
    full_artifact_contracts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for seed in paired_seeds:
        for run_policy in (REFERENCE_POLICY, FEEDBACK_POLICY):
            result_dir = output / run_policy / f"seed_{seed}"
            if result_dir.exists() and any(result_dir.iterdir()):
                raise FileExistsError(
                    "Refusing to mix a reproducible campaign with existing run "
                    f"artifacts: {result_dir}"
                )
            command = [
                interpreter,
                str(engine),
                "--input",
                str(graph),
                "--output-dir",
                str(result_dir),
                "--scenario-id",
                str(scenario_id),
                "--days",
                str(int(days)),
                "--seed",
                str(seed),
                *artifact_args,
                *extra_args,
                "--common-random-numbers",
                (
                    "--supplier-state-dependent-risks"
                    if enable_state_dependent_risks
                    else "--no-supplier-state-dependent-risks"
                ),
            ]
            if risk_events is not None:
                command.extend(["--supplier-risk-events-csv", str(risk_events)])
            if run_policy == FEEDBACK_POLICY:
                command.extend([control_policy_flag, str(policy_config)])
                command.extend(feedback_extra_args)

            commands.append(
                {
                    "policy": run_policy,
                    "seed": seed,
                    "result_dir": str(result_dir),
                    "command": command,
                }
            )
            _run_engine(command, cwd=root, result_dir=result_dir)
            engine_summary, kpis, claimed, claim_path, claim_status = _validate_and_extract(
                result_dir=result_dir,
                graph_path=graph,
                graph_sha256=graph_hash,
                risk_events_path=risk_events,
                risk_events_sha256=risk_hash,
                expected_risk_event_count=risk_count,
                expected_seed=seed,
                expected_days=int(days),
                expected_scenario_id=str(scenario_id),
                expect_state_dependent_risks=enable_state_dependent_risks,
                run_policy=run_policy,
            )
            if artifact_profile == ENGINE_ARTIFACT_PROFILE_FULL:
                full_artifact_contracts.append(
                    {
                        "policy": run_policy,
                        "seed": seed,
                        **_validate_full_artifact_contract(
                            result_dir=result_dir,
                            engine_summary=engine_summary,
                        ),
                    }
                )
            engine_policy_summary = engine_summary.get("policy")
            engine_policy_summary = (
                engine_policy_summary
                if isinstance(engine_policy_summary, Mapping)
                else {}
            )
            state_risk_summary = engine_policy_summary.get(
                "supplier_state_dependent_risk"
            )
            state_risk_summary = (
                state_risk_summary
                if isinstance(state_risk_summary, Mapping)
                else {}
            )
            try:
                state_risk_observation_warmup_days = int(
                    state_risk_summary.get("observation_warmup_days", -1)
                )
            except (TypeError, ValueError):
                state_risk_observation_warmup_days = -1
            rows.append(
                {
                    "policy": run_policy,
                    "seed": seed,
                    "status": "ok",
                    "returncode": 0,
                    "error": "",
                    "result_dir": str(result_dir),
                    "run_kind": "physical_closed_loop_candidate"
                    if run_policy == FEEDBACK_POLICY
                    else "physical_reference",
                    "is_derived": 0,
                    "integration_mode": "daily_state_feedback_candidate"
                    if run_policy == FEEDBACK_POLICY
                    else "historical_mrp_no_external_control",
                    "control_policy_requested": run_policy == FEEDBACK_POLICY,
                    "engine_closed_loop_claimed": bool(claimed),
                    "true_state_feedback": bool(
                        run_policy == FEEDBACK_POLICY and claimed is True
                    ),
                    "closed_loop_claim_path": claim_path,
                    "closed_loop_evidence_status": claim_status
                    if run_policy == FEEDBACK_POLICY
                    else "not_applicable_mrp_reference",
                    "scenario_id": str(scenario_id),
                    "days": int(days),
                    "engine_artifact_profile": artifact_profile,
                    "engine_artifact_contract_status": (
                        "validated_full"
                        if artifact_profile == ENGINE_ARTIFACT_PROFILE_FULL
                        else "compact_legacy_contract"
                    ),
                    "common_random_numbers": True,
                    "state_dependent_risks": bool(enable_state_dependent_risks),
                    "state_risk_observation_warmup_days": (
                        state_risk_observation_warmup_days
                    ),
                    "graph_path": str(graph),
                    "graph_sha256": graph_hash,
                    "risk_events_path": str(risk_events or ""),
                    "risk_events_sha256": risk_hash,
                    "control_policy_path": str(policy_config)
                    if run_policy == FEEDBACK_POLICY
                    else "",
                    "control_policy_sha256": policy_hash
                    if run_policy == FEEDBACK_POLICY
                    else "",
                    "engine_profile_name": str(profile_metadata.get("name") or ""),
                    "engine_profile_sha256": str(profile_metadata.get("sha256") or ""),
                    **kpis,
                }
            )

    raw_runs = pd.DataFrame(rows)
    _pairing_contract(raw_runs, paired_seeds)
    runs = _attach_canonical_rci(raw_runs)
    runs = _attach_mrp_reference_deltas(runs)
    runs = runs.sort_values(["seed", "policy"]).reset_index(drop=True)
    paired_deltas = _paired_delta_frame(runs)
    paired_summary = _augment_summary(_paired_canonical_summary(runs), runs)

    runs_path = output / "canonical_closed_loop_runs.csv"
    deltas_path = output / "canonical_closed_loop_paired_deltas.csv"
    summary_path = output / "canonical_closed_loop_paired_summary.csv"
    commands_path = output / "canonical_closed_loop_commands.json"
    runs.to_csv(runs_path, index=False)
    paired_deltas.to_csv(deltas_path, index=False)
    paired_summary.to_csv(summary_path, index=False)
    commands_path.write_text(
        json.dumps(_json_safe(commands), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    plot_path: Path | None = None
    plot_status = "disabled"
    control_diagnostics_plot_path: Path | None = None
    control_diagnostics_plot_status = "disabled"
    if make_plot:
        plot_path, plot_status = _save_comparison_plot(
            output, runs, paired_deltas
        )
        (
            control_diagnostics_plot_path,
            control_diagnostics_plot_status,
        ) = _save_control_diagnostics_plot(output, runs)

    output_artifact_paths = {
        "runs": runs_path,
        "paired_deltas": deltas_path,
        "paired_summary": summary_path,
        "commands": commands_path,
    }
    if plot_path is not None:
        output_artifact_paths["comparison_plot"] = plot_path
    if control_diagnostics_plot_path is not None:
        output_artifact_paths["control_diagnostics_plot"] = (
            control_diagnostics_plot_path
        )
    output_sha256 = {
        name: _sha256(path)
        for name, path in output_artifact_paths.items()
        if path.is_file()
    }
    provider_source_name = {
        _CONTROL_POLICY_FLAG: "control_provider.py",
        _CONTROL_POLICY_V2_FLAG: "control_provider_v2.py",
        _CONTROL_POLICY_V3_FLAG: "control_provider_v3.py",
    }[control_policy_flag]
    provider_source = (
        root / "etudecas" / "simulation" / "engine" / provider_source_name
    )
    feedback_rows = runs.loc[runs["policy"].eq(FEEDBACK_POLICY)]
    state_risk_warmup_values = sorted(
        {
            int(value)
            for value in runs["state_risk_observation_warmup_days"].tolist()
        }
    )
    manifest = {
        "schema_version": "scan.canonical_closed_loop_campaign.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "comparison": "paired_mrp_vs_canonical_feedback",
        "graph": {"path": str(graph), "sha256": graph_hash},
        "supplier_risk_events": {
            "path": str(risk_events or ""),
            "sha256": risk_hash,
            "row_count": risk_count,
        },
        "control_policy": {
            "path": str(policy_config),
            "sha256": policy_hash,
            "engine_flag": control_policy_flag,
        },
        "scenario_id": str(scenario_id),
        "days": int(days),
        "seeds": list(paired_seeds),
        "common_random_numbers": True,
        "state_dependent_risks": bool(enable_state_dependent_risks),
        "supplier_state_risk_observation_warmup_days": (
            state_risk_warmup_values[0]
            if len(state_risk_warmup_values) == 1
            else state_risk_warmup_values
        ),
        "engine": str(engine),
        "engine_sha256": _sha256(engine),
        "runner": {
            "path": str(HERE),
            "sha256": _sha256(HERE),
        },
        "control_provider_source": {
            "path": str(provider_source),
            "sha256": (
                _sha256(provider_source) if provider_source.is_file() else ""
            ),
        },
        "git": _git_provenance(root),
        "engine_profile": profile_metadata,
        "engine_artifact_profile": artifact_profile,
        "engine_artifact_contract": {
            "status": (
                "validated_full"
                if artifact_profile == ENGINE_ARTIFACT_PROFILE_FULL
                else "compact_legacy_contract"
            ),
            "validated_run_count": len(full_artifact_contracts),
            **(
                {"runs": full_artifact_contracts}
                if full_artifact_contracts
                else {}
            ),
        },
        "engine_extra_args": list(extra_args),
        **(
            {"feedback_engine_extra_args": list(feedback_extra_args)}
            if feedback_extra_args
            else {}
        ),
        "completed_physical_run_count": int(len(runs)),
        "paired_seed_count": int(len(paired_deltas)),
        "feedback_engine_claim_count": int(
            feedback_rows["engine_closed_loop_claimed"].sum()
        ),
        "true_state_feedback_count": int(
            feedback_rows["true_state_feedback"].sum()
        ),
        "all_feedback_runs_confirmed_by_engine": bool(
            not feedback_rows.empty
            and feedback_rows["true_state_feedback"].all()
        ),
        "claim_rule": (
            "true_state_feedback requires the authoritative strict boolean at "
            "$.policy.control_provider.closed_loop_claimed, zero observation "
            "lookahead, J-to-J+1 audit evidence and a physically applied action; "
            f"passing {control_policy_flag} is insufficient"
        ),
        "output_sha256": output_sha256,
        "outputs": {
            "runs": str(runs_path),
            "paired_deltas": str(deltas_path),
            "paired_summary": str(summary_path),
            "commands": str(commands_path),
            "comparison_plot": str(plot_path or ""),
            "comparison_plot_status": plot_status,
            "control_diagnostics_plot": str(
                control_diagnostics_plot_path or ""
            ),
            "control_diagnostics_plot_status": (
                control_diagnostics_plot_status
            ),
        },
    }
    manifest_path = output / "canonical_closed_loop_manifest.json"
    manifest_path.write_text(
        json.dumps(_json_safe(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return CanonicalClosedLoopArtifacts(
        runs=runs,
        paired_deltas=paired_deltas,
        paired_summary=paired_summary,
        output_root=output,
        manifest_path=manifest_path,
        plot_path=plot_path,
        control_diagnostics_plot_path=control_diagnostics_plot_path,
        control_diagnostics_plot_status=control_diagnostics_plot_status,
    )


def _campaign_section(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    campaign = payload.get("campaign", {})
    if campaign is None:
        return {}
    if not isinstance(campaign, Mapping):
        raise ValueError("canonical closed-loop config 'campaign' must be an object")
    return campaign


def _parse_seed_text(value: str) -> tuple[int, ...]:
    return _ordered_seeds(
        [int(item.strip()) for item in value.split(",") if item.strip()]
    )


def run_from_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    repo_root: Path = REPO_ROOT,
    graph: str | Path | None = None,
    output_root: Path | None = None,
    days: int | None = None,
    seeds: Sequence[int] | None = None,
    scenario_id: str | None = None,
    supplier_risk_events_path: Path | None = None,
    engine_script: Path | None = None,
    engine_profile_path: Path | None = None,
    engine_artifact_profile: str | None = None,
    make_plot: bool | None = None,
) -> CanonicalClosedLoopArtifacts:
    """Load optional campaign defaults while passing the policy JSON unchanged."""

    root = repo_root.resolve()
    config = _require_file(config_path, "canonical closed-loop config")
    payload = _load_json_object(config, "canonical closed-loop config")
    campaign = _campaign_section(payload)

    graph_value = graph if graph is not None else campaign.get("graph", "auto")
    if str(graph_value) == "auto":
        graph_path = discover_canonical_graph(root, "auto")
        if graph_path is None:
            raise FileNotFoundError("No canonical graph candidate was discovered.")
    else:
        graph_path = _resolve_path(
            str(graph_value), repo_root=root, relative_to=config.parent
        )

    policy_value = campaign.get("control_policy_json", str(config))
    policy_path = _resolve_path(
        str(policy_value), repo_root=root, relative_to=config.parent
    )
    policy_payload = _load_json_object(policy_path, "control-policy JSON")
    policy_schema = str(policy_payload.get("schema_version") or "")
    control_policy_flag = {
        "scan.canonical_state_feedback.v2": _CONTROL_POLICY_V2_FLAG,
        "scan.canonical_state_feedback.v3": _CONTROL_POLICY_V3_FLAG,
    }.get(policy_schema, _CONTROL_POLICY_FLAG)
    output_value = output_root or campaign.get("output_dir") or (
        root
        / "etudecas"
        / "prototypes"
        / "scan_2027_risk_control"
        / "outputs"
        / "canonical_closed_loop"
    )
    output_path = _resolve_path(
        str(output_value), repo_root=root, relative_to=config.parent
    )
    selected_days = int(days if days is not None else campaign.get("days", 90))
    configured_seeds = campaign.get("seeds")
    if (
        seeds is None
        and configured_seeds is None
        and any(
            name in campaign
            for name in ("training_seeds", "validation_seeds")
        )
    ):
        raise ValueError(
            "The generic closed-loop runner does not select training_seeds or "
            "validation_seeds automatically; pass --seeds explicitly or use "
            "the dedicated phase runner."
        )
    selected_seeds = _ordered_seeds(
        seeds if seeds is not None else configured_seeds or [200260]
    )
    selected_scenario = str(
        scenario_id if scenario_id is not None else campaign.get("scenario_id", "scn:BASE")
    )

    risk_value: str | Path | None = supplier_risk_events_path
    if risk_value is None:
        risk_value = campaign.get("supplier_risk_events_csv") or None
    risk_path = (
        _resolve_path(str(risk_value), repo_root=root, relative_to=config.parent)
        if risk_value is not None
        else None
    )
    engine_value = engine_script or campaign.get("engine_script") or (
        root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
    )
    resolved_engine = _resolve_path(
        str(engine_value), repo_root=root, relative_to=config.parent
    )

    profile_value: str | Path | None = engine_profile_path
    if profile_value is None:
        profile_value = campaign.get("engine_profile")
    default_profile = (
        root
        / "etudecas"
        / "prototypes"
        / "scan_2027_risk_control"
        / "config"
        / "canonical_real_baseline_engine_profile.json"
    )
    if profile_value is None and default_profile.exists():
        profile_value = default_profile
    profile_args: tuple[str, ...] = ()
    profile_metadata: dict[str, Any] = {}
    if profile_value is not None and str(profile_value).strip():
        resolved_profile = _resolve_path(
            str(profile_value), repo_root=root, relative_to=config.parent
        )
        profile_args, profile_metadata = load_canonical_engine_profile(
            root, str(resolved_profile)
        )
    configured_args = campaign.get("engine_args", [])
    if not isinstance(configured_args, list):
        raise ValueError("campaign.engine_args must be a JSON list")
    all_engine_args = (*profile_args, *(str(item) for item in configured_args))
    state_risks = campaign.get("state_dependent_risks", True)
    if not isinstance(state_risks, bool):
        raise ValueError("campaign.state_dependent_risks must be boolean")
    prime_controller = campaign.get("controller_prime_during_warmup", False)
    if not isinstance(prime_controller, bool):
        raise ValueError(
            "campaign.controller_prime_during_warmup must be boolean"
        )
    if prime_controller and control_policy_flag not in {
        _CONTROL_POLICY_V2_FLAG,
        _CONTROL_POLICY_V3_FLAG,
    }:
        raise ValueError(
            "controller priming is available only for V2 or V3 control policies"
        )
    feedback_engine_args = (
        ("--controller-prime-during-warmup",)
        if prime_controller
        else ()
    )
    plot = make_plot if make_plot is not None else bool(campaign.get("plot", True))
    selected_artifact_profile = (
        engine_artifact_profile
        if engine_artifact_profile is not None
        else campaign.get(
            "engine_artifact_profile",
            ENGINE_ARTIFACT_PROFILE_COMPACT,
        )
    )
    _engine_artifact_args(selected_artifact_profile)

    return run_canonical_closed_loop(
        repo_root=root,
        graph_path=graph_path,
        control_policy_path=policy_path,
        seeds=selected_seeds,
        output_root=output_path,
        days=selected_days,
        scenario_id=selected_scenario,
        engine_script=resolved_engine,
        supplier_risk_events_path=risk_path,
        enable_state_dependent_risks=state_risks,
        engine_extra_args=all_engine_args,
        feedback_engine_extra_args=feedback_engine_args,
        control_policy_flag=control_policy_flag,
        engine_profile_metadata=profile_metadata,
        engine_artifact_profile=selected_artifact_profile,
        make_plot=plot,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run paired canonical MRP versus state-feedback simulations."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--graph", default=None, help="Canonical graph path or 'auto'.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--seeds", default=None, help="Comma-separated paired seeds.")
    parser.add_argument("--scenario-id", default=None)
    parser.add_argument("--supplier-risk-events-csv", default=None)
    parser.add_argument("--engine-script", default=None)
    parser.add_argument("--engine-profile", default=None)
    parser.add_argument(
        "--engine-artifact-profile",
        choices=ENGINE_ARTIFACT_PROFILES,
        default=None,
        help=(
            "Engine artifact volume. Defaults to campaign.engine_artifact_profile "
            "or 'compact'."
        ),
    )
    parser.add_argument(
        "--plot",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Write the trajectory and paired-comparison PNG when matplotlib exists.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = run_from_config(
        Path(args.config),
        repo_root=Path(args.repo_root),
        graph=args.graph,
        output_root=Path(args.output_dir) if args.output_dir else None,
        days=args.days,
        seeds=_parse_seed_text(args.seeds) if args.seeds else None,
        scenario_id=args.scenario_id,
        supplier_risk_events_path=(
            Path(args.supplier_risk_events_csv)
            if args.supplier_risk_events_csv
            else None
        ),
        engine_script=Path(args.engine_script) if args.engine_script else None,
        engine_profile_path=(
            Path(args.engine_profile) if args.engine_profile else None
        ),
        engine_artifact_profile=args.engine_artifact_profile,
        make_plot=args.plot,
    )
    feedback = artifacts.runs.loc[
        artifacts.runs["policy"].eq(FEEDBACK_POLICY)
    ]
    print(f"Canonical paired campaign completed: {artifacts.output_root}")
    print(f"Paired seeds: {len(artifacts.paired_deltas)}")
    print(
        "True state-feedback claims confirmed by engine: "
        f"{int(feedback['true_state_feedback'].sum())}/{len(feedback)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
