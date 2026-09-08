#!/usr/bin/env python3
"""Strict paired warm-start campaign for the additive V2 controller.

This wrapper deliberately leaves the V1 campaign untouched.  It delegates the
physical MRP/feedback executions and KPI calculations to
``canonical_closed_loop`` through its explicit V2 engine flag, then applies the
additional protocol required by the warm-start study:

* 60 causal pre-period burn-in days for both members of every pair;
* observation-only controller priming on days -60..-1;
* no controller command or action during priming;
* exact equality of the auditable core engine state at the J0 boundary;
* disjoint 10-seed development and 30-seed held-out validation sets.

The boundary artifact is a deterministic paired-replay fingerprint, not a
restart checkpoint.  Consequently this runner never describes the burn-in as
a serialized restart state or as proof that the plant is stationary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    canonical_closed_loop as canonical,
)


DEFAULT_CONFIG_PATH = (
    HERE.parent / "config" / "canonical_closed_loop_v2_config.json"
)
DEFAULT_OUTPUT_ROOT = (
    HERE.parent / "outputs" / "canonical_closed_loop_v2"
)
V2_CONTROL_FLAG = "--control-policy-v2-json"
REFERENCE_POLICY = canonical.REFERENCE_POLICY
FEEDBACK_POLICY = canonical.FEEDBACK_POLICY
REQUIRED_WARMUP_DAYS = 60
REQUIRED_TRAINING_SEED_COUNT = 10
REQUIRED_VALIDATION_SEED_COUNT = 30
PROTOCOL_SCHEMA_VERSION = "scan.canonical_closed_loop_v2_protocol.v1"


class CanonicalClosedLoopV2Error(RuntimeError):
    """Base error for the additive V2 campaign wrapper."""


class CanonicalClosedLoopV2ContractError(CanonicalClosedLoopV2Error):
    """Raised when config or engine evidence violates the V2 protocol."""


@dataclass(frozen=True)
class V2ProtocolArtifacts:
    """Completed per-split canonical artifacts and the protocol manifest."""

    split_artifacts: Mapping[str, canonical.CanonicalClosedLoopArtifacts]
    output_root: Path
    protocol_path: Path
    protocol: Mapping[str, Any]


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
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CanonicalClosedLoopV2ContractError(
            f"{label} must contain a JSON object: {resolved}"
        )
    return payload


def _resolve_path(
    value: str | Path,
    *,
    repo_root: Path,
    relative_to: Path,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (repo_root / path).resolve()
    local_candidate = (relative_to / path).resolve()
    return repo_candidate if repo_candidate.exists() else local_candidate


def _strict_seed_set(
    raw: Any,
    *,
    label: str,
    expected_count: int,
) -> tuple[int, ...]:
    if not isinstance(raw, list):
        raise CanonicalClosedLoopV2ContractError(f"{label} must be a JSON list.")
    seeds: list[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CanonicalClosedLoopV2ContractError(
                f"{label} must contain non-negative integers; got {value!r}."
            )
        seeds.append(value)
    if len(seeds) != expected_count:
        raise CanonicalClosedLoopV2ContractError(
            f"{label} must contain exactly {expected_count} seeds; got {len(seeds)}."
        )
    if len(set(seeds)) != len(seeds):
        raise CanonicalClosedLoopV2ContractError(f"{label} contains duplicates.")
    return tuple(sorted(seeds))


def _last_option(args: Sequence[str], flag: str) -> str | None:
    value: str | None = None
    for index, token in enumerate(args):
        if token == flag:
            if index + 1 >= len(args):
                raise CanonicalClosedLoopV2ContractError(
                    f"campaign.engine_args is missing a value after {flag}."
                )
            value = str(args[index + 1])
        elif token.startswith(flag + "="):
            value = token.split("=", 1)[1]
    return value


def _effective_boolean_option(
    args: Sequence[str],
    *,
    positive: str,
    negative: str,
) -> bool | None:
    selected: bool | None = None
    for token in args:
        if token == positive:
            selected = True
        elif token == negative:
            selected = False
    return selected


def validate_protocol_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the immutable V2 experiment contract."""

    if str(payload.get("schema_version") or "") != "scan.canonical_state_feedback.v2":
        raise CanonicalClosedLoopV2ContractError(
            "The V2 campaign config must use schema_version "
            "'scan.canonical_state_feedback.v2'."
        )
    campaign = payload.get("campaign")
    if not isinstance(campaign, Mapping):
        raise CanonicalClosedLoopV2ContractError("campaign must be a JSON object.")
    protocol = payload.get("protocol")
    if not isinstance(protocol, Mapping):
        raise CanonicalClosedLoopV2ContractError("protocol must be a JSON object.")

    training_seeds = _strict_seed_set(
        campaign.get("training_seeds"),
        label="campaign.training_seeds",
        expected_count=REQUIRED_TRAINING_SEED_COUNT,
    )
    validation_seeds = _strict_seed_set(
        campaign.get("validation_seeds"),
        label="campaign.validation_seeds",
        expected_count=REQUIRED_VALIDATION_SEED_COUNT,
    )
    overlap = sorted(set(training_seeds) & set(validation_seeds))
    if overlap:
        raise CanonicalClosedLoopV2ContractError(
            f"Training and validation seeds must be disjoint; overlap={overlap}."
        )

    raw_args = campaign.get("engine_args")
    if not isinstance(raw_args, list) or not all(
        isinstance(item, str) and item for item in raw_args
    ):
        raise CanonicalClosedLoopV2ContractError(
            "campaign.engine_args must be a list of non-empty strings."
        )
    engine_args = tuple(raw_args)
    warmup_text = _last_option(engine_args, "--warmup-days")
    try:
        warmup_days = int(warmup_text) if warmup_text is not None else -1
    except ValueError as exc:
        raise CanonicalClosedLoopV2ContractError(
            "--warmup-days must be an integer."
        ) from exc
    if warmup_days != REQUIRED_WARMUP_DAYS:
        raise CanonicalClosedLoopV2ContractError(
            f"V2 requires exactly {REQUIRED_WARMUP_DAYS} warm-up days; "
            f"got {warmup_days}."
        )
    if _last_option(engine_args, "--warmup-profile-mode") != "preperiod":
        raise CanonicalClosedLoopV2ContractError(
            "V2 requires --warmup-profile-mode preperiod."
        )
    if (
        _effective_boolean_option(
            engine_args,
            positive="--restore-opening-stock-after-warmup",
            negative="--no-restore-opening-stock-after-warmup",
        )
        is not False
    ):
        raise CanonicalClosedLoopV2ContractError(
            "V2 requires --no-restore-opening-stock-after-warmup."
        )
    if "--warmup-boundary-audit" not in engine_args:
        raise CanonicalClosedLoopV2ContractError(
            "V2 requires --warmup-boundary-audit on both paired runs."
        )
    smoothing_text = _last_option(
        engine_args, "--mrp-demand-signal-smoothing-days"
    )
    if smoothing_text != "1":
        raise CanonicalClosedLoopV2ContractError(
            "V2 requires a one-day realized demand window for zero lookahead."
        )
    if campaign.get("controller_prime_during_warmup") is not True:
        raise CanonicalClosedLoopV2ContractError(
            "campaign.controller_prime_during_warmup must be true."
        )
    if protocol.get("reset_backlog_after_warmup") is not False:
        raise CanonicalClosedLoopV2ContractError(
            "protocol.reset_backlog_after_warmup must be false."
        )
    expected_protocol_values = {
        "method": "deterministic_paired_burn_in_replay",
        "physical_warmup_days": REQUIRED_WARMUP_DAYS,
        "warmup_profile_mode": "preperiod",
        "restore_opening_stock_after_warmup": False,
        "controller_priming_days": REQUIRED_WARMUP_DAYS,
        "controller_warmup_action_count": 0,
        "boundary_scope": "core_dynamic_engine_state_not_restart_checkpoint",
        "stationarity_claimed": False,
        "validation_is_held_out": True,
        "automatic_retuning_on_validation": False,
    }
    for field, expected in expected_protocol_values.items():
        if protocol.get(field) != expected:
            raise CanonicalClosedLoopV2ContractError(
                f"protocol.{field} must be {expected!r}."
            )
    if protocol.get("restart_checkpoint_available") is not False:
        raise CanonicalClosedLoopV2ContractError(
            "The protocol must not claim that a restart checkpoint exists."
        )

    days = campaign.get("days", 90)
    if isinstance(days, bool) or not isinstance(days, int) or days <= 1:
        raise CanonicalClosedLoopV2ContractError(
            "campaign.days must be an integer greater than one."
        )
    state_risks = campaign.get("state_dependent_risks", True)
    if not isinstance(state_risks, bool):
        raise CanonicalClosedLoopV2ContractError(
            "campaign.state_dependent_risks must be boolean."
        )
    return {
        "campaign": dict(campaign),
        "protocol": dict(protocol),
        "training_seeds": training_seeds,
        "validation_seeds": validation_seeds,
        "engine_args": engine_args,
        "warmup_days": warmup_days,
        "days": days,
        "state_dependent_risks": state_risks,
    }


def _assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise CanonicalClosedLoopV2ContractError(message)


def terminal_stability_diagnostic(
    priming: pd.DataFrame,
    *,
    window_days: int = 14,
    relative_mean_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare two terminal burn-in windows without claiming stationarity.

    A passing heuristic only says that the aggregate means of demand, backlog
    and inventory are close across these two windows.  Periodic MRP dynamics,
    slow drift and pair-level transients can still remain.
    """

    signals = ("demand_qty", "backlog_qty", "inventory_qty")
    if window_days <= 0 or len(priming) < 2 * window_days:
        return {
            "status": "stability_not_demonstrated",
            "reason": "insufficient_terminal_window_history",
            "window_days": int(window_days),
            "relative_mean_tolerance": float(relative_mean_tolerance),
            "stationarity_claimed": False,
            "signals": {},
        }
    missing = [name for name in signals if name not in priming]
    if missing:
        return {
            "status": "stability_not_demonstrated",
            "reason": "missing_priming_signals:" + ",".join(missing),
            "window_days": int(window_days),
            "relative_mean_tolerance": float(relative_mean_tolerance),
            "stationarity_claimed": False,
            "signals": {},
        }

    previous = priming.iloc[-2 * window_days : -window_days]
    terminal = priming.iloc[-window_days:]
    signal_rows: dict[str, dict[str, Any]] = {}
    for signal in signals:
        previous_values = pd.to_numeric(previous[signal], errors="coerce")
        terminal_values = pd.to_numeric(terminal[signal], errors="coerce")
        finite = bool(previous_values.notna().all() and terminal_values.notna().all())
        previous_mean = float(previous_values.mean()) if finite else math.nan
        terminal_mean = float(terminal_values.mean()) if finite else math.nan
        scale = max(abs(previous_mean), abs(terminal_mean), 1e-9)
        relative_shift = (
            abs(terminal_mean - previous_mean) / scale if finite else math.inf
        )
        signal_rows[signal] = {
            "previous_window_mean": previous_mean if finite else None,
            "terminal_window_mean": terminal_mean if finite else None,
            "absolute_mean_shift": (
                abs(terminal_mean - previous_mean) if finite else None
            ),
            "relative_mean_shift": relative_shift if finite else None,
            "criterion_satisfied": bool(
                finite and relative_shift <= relative_mean_tolerance
            ),
        }
    heuristic_pass = all(
        bool(row["criterion_satisfied"]) for row in signal_rows.values()
    )
    return {
        "status": (
            "terminal_window_heuristic_satisfied_not_stationarity_proof"
            if heuristic_pass
            else "stability_not_demonstrated"
        ),
        "reason": (
            "all_aggregate_relative_mean_shifts_within_tolerance"
            if heuristic_pass
            else "one_or_more_aggregate_relative_mean_shifts_exceed_tolerance"
        ),
        "window_days": int(window_days),
        "relative_mean_tolerance": float(relative_mean_tolerance),
        "stationarity_claimed": False,
        "signals": signal_rows,
    }


def command_gate_violations(commands: pd.DataFrame) -> list[dict[str, Any]]:
    """Return positive V2 actions lacking their required open safety gate."""

    required_columns = {
        "effective_day",
        "effective_json",
        "control_open_gate_ids",
        "control_gate_observation_hash",
        "control_gate_observation_valid",
    }
    missing = sorted(required_columns - set(commands.columns))
    if missing:
        raise CanonicalClosedLoopV2ContractError(
            "V2 command audit lacks gate columns: " + ", ".join(missing)
        )
    violations: list[dict[str, Any]] = []
    service_actions = {
        "order_multiplier": 1.0,
        "safety_stock_multiplier": 1.0,
        "production_target_multiplier": 1.0,
    }
    exceptional_actions = {
        "external_procurement_multiplier": 1.0,
        "expedite_level": 0.0,
    }
    for row_index, row in commands.reset_index(drop=True).iterrows():
        try:
            effective = json.loads(str(row["effective_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise CanonicalClosedLoopV2ContractError(
                f"V2 command row {row_index} has invalid effective_json."
            ) from exc
        if not isinstance(effective, Mapping):
            raise CanonicalClosedLoopV2ContractError(
                f"V2 command row {row_index} effective_json is not an object."
            )
        open_gates = {
            item.strip()
            for item in str(row["control_open_gate_ids"] or "").split(";")
            if item.strip()
        }
        observation_hash = str(row["control_gate_observation_hash"] or "")
        try:
            observation_valid = int(row["control_gate_observation_valid"])
        except (TypeError, ValueError) as exc:
            raise CanonicalClosedLoopV2ContractError(
                f"V2 command row {row_index} has invalid gate observation validity."
            ) from exc
        if len(observation_hash) != 64 or observation_valid != 1:
            violations.append(
                {
                    "row": int(row_index),
                    "effective_day": int(row["effective_day"]),
                    "action": "gate_observation_audit",
                    "required_gate": "valid_hashed_observation",
                    "reason": "missing_hash_or_invalid_observation",
                }
            )
        for action_name, neutral in service_actions.items():
            if action_name not in effective:
                continue
            value = float(effective[action_name])
            if value > neutral + 1e-12 and "service_recovery_gate" not in open_gates:
                violations.append(
                    {
                        "row": int(row_index),
                        "effective_day": int(row["effective_day"]),
                        "action": action_name,
                        "value": value,
                        "required_gate": "service_recovery_gate",
                        "reason": "positive_action_without_open_gate",
                    }
                )
        for action_name, neutral in exceptional_actions.items():
            if action_name not in effective:
                continue
            value = float(effective[action_name])
            if value > neutral + 1e-12 and "exceptional_cost_gate" not in open_gates:
                violations.append(
                    {
                        "row": int(row_index),
                        "effective_day": int(row["effective_day"]),
                        "action": action_name,
                        "value": value,
                        "required_gate": "exceptional_cost_gate",
                        "reason": "positive_action_without_open_gate",
                    }
                )
    return violations


def validate_pair_evidence(
    *,
    reference_summary: Mapping[str, Any],
    feedback_summary: Mapping[str, Any],
    priming: pd.DataFrame,
    observations: pd.DataFrame,
    commands: pd.DataFrame,
    action_ledger: pd.DataFrame,
    seed: int,
    measured_days: int,
    warmup_days: int = REQUIRED_WARMUP_DAYS,
    stability_window_days: int = 14,
    stability_relative_mean_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Validate one paired burn-in boundary and feedback priming audit."""

    summaries = {
        REFERENCE_POLICY: reference_summary,
        FEEDBACK_POLICY: feedback_summary,
    }
    boundaries: dict[str, Mapping[str, Any]] = {}
    for policy_name, summary in summaries.items():
        policy = summary.get("policy")
        _assert_true(
            isinstance(policy, Mapping),
            f"Seed {seed} {policy_name}: summary.policy is missing.",
        )
        assert isinstance(policy, Mapping)
        _assert_true(
            int(policy.get("warmup_days", -1)) == warmup_days,
            f"Seed {seed} {policy_name}: physical warm-up is not {warmup_days} days.",
        )
        _assert_true(
            policy.get("warmup_profile_mode") == "preperiod",
            f"Seed {seed} {policy_name}: warm-up profile is not preperiod.",
        )
        _assert_true(
            policy.get("reset_backlog_after_warmup") is False,
            f"Seed {seed} {policy_name}: backlog is reset at J0.",
        )
        initialization = policy.get("initialization_policy")
        _assert_true(
            isinstance(initialization, Mapping)
            and initialization.get("restore_opening_stock_after_warmup") is False,
            f"Seed {seed} {policy_name}: opening stock is restored at J0.",
        )
        boundary = policy.get("warmup_boundary_audit")
        _assert_true(
            isinstance(boundary, Mapping),
            f"Seed {seed} {policy_name}: warm-up boundary audit is missing.",
        )
        assert isinstance(boundary, Mapping)
        _assert_true(
            boundary.get("method") == "deterministic_paired_burn_in_replay",
            f"Seed {seed} {policy_name}: unexpected boundary method.",
        )
        _assert_true(
            boundary.get("scope")
            == "core_dynamic_engine_state_not_restart_checkpoint",
            f"Seed {seed} {policy_name}: boundary scope is ambiguous.",
        )
        _assert_true(
            boundary.get("restart_checkpoint_available") is False,
            f"Seed {seed} {policy_name}: false restart-checkpoint claim.",
        )
        core_hash = str(boundary.get("core_state_sha256") or "")
        _assert_true(
            len(core_hash) == 64,
            f"Seed {seed} {policy_name}: invalid core-state SHA-256.",
        )
        _assert_true(
            isinstance(boundary.get("component_sha256"), Mapping)
            and bool(boundary.get("component_sha256")),
            f"Seed {seed} {policy_name}: component hashes are missing.",
        )
        boundaries[policy_name] = boundary

    reference_boundary = boundaries[REFERENCE_POLICY]
    feedback_boundary = boundaries[FEEDBACK_POLICY]
    _assert_true(
        reference_boundary["core_state_sha256"]
        == feedback_boundary["core_state_sha256"],
        f"Seed {seed}: MRP/feedback core state differs at J0.",
    )
    _assert_true(
        reference_boundary["component_sha256"]
        == feedback_boundary["component_sha256"],
        f"Seed {seed}: MRP/feedback component state differs at J0.",
    )

    feedback_policy = feedback_summary["policy"]
    provider = feedback_policy.get("control_provider")
    _assert_true(
        isinstance(provider, Mapping),
        f"Seed {seed}: V2 control-provider summary is missing.",
    )
    assert isinstance(provider, Mapping)
    expected_provider_values = {
        "schema_version": "scan.canonical_state_feedback.v2",
        "mode": "canonical_state_feedback_v2_t_plus_1",
        "closed_loop_claimed": True,
        "controller_warmup_matches_physical_warmup": True,
        "controller_primed_during_warmup": True,
        "controller_priming_sequential": True,
        "controller_priming_complete_at_day_minus_one": True,
        "controller_priming_all_observations_valid": True,
        "warmup_commands_disabled": True,
        "future_realization_access": False,
    }
    for field, expected in expected_provider_values.items():
        _assert_true(
            provider.get(field) == expected,
            f"Seed {seed}: control_provider.{field}={provider.get(field)!r}, "
            f"expected {expected!r}.",
        )
    for field in (
        "physical_warmup_days",
        "controller_dynamic_warmup_days",
        "controller_priming_observation_count",
        "controller_priming_valid_observation_count",
    ):
        _assert_true(
            int(provider.get(field, -1)) == warmup_days,
            f"Seed {seed}: control_provider.{field} does not equal {warmup_days}.",
        )
    _assert_true(
        int(provider.get("controller_priming_first_day", 0)) == -warmup_days,
        f"Seed {seed}: priming does not start at day {-warmup_days}.",
    )
    _assert_true(
        int(provider.get("controller_priming_last_day", 0)) == -1,
        f"Seed {seed}: priming does not end at day -1.",
    )
    _assert_true(
        int(provider.get("warmup_control_action_count", -1)) == 0,
        f"Seed {seed}: a control action was generated during warm-up.",
    )
    _assert_true(
        list(provider.get("closed_loop_claim_reasons") or []) == [],
        f"Seed {seed}: strict closed-loop claim has failed reasons.",
    )

    required_priming_columns = {
        "day",
        "observation_valid",
        "generated_command_count",
        "active_command_row_count",
    }
    _assert_true(
        required_priming_columns.issubset(priming.columns),
        f"Seed {seed}: priming CSV lacks required columns.",
    )
    _assert_true(
        len(priming) == warmup_days,
        f"Seed {seed}: expected {warmup_days} priming rows, got {len(priming)}.",
    )
    _assert_true(
        pd.to_numeric(priming["day"], errors="raise").astype(int).tolist()
        == list(range(-warmup_days, 0)),
        f"Seed {seed}: priming days are not exactly {-warmup_days}..-1.",
    )
    for field, expected in (
        ("observation_valid", 1),
        ("generated_command_count", 0),
        ("active_command_row_count", 0),
    ):
        values = pd.to_numeric(priming[field], errors="raise").astype(int)
        _assert_true(
            bool(values.eq(expected).all()),
            f"Seed {seed}: invalid priming values in {field}.",
        )

    _assert_true(
        "day" in observations and len(observations) == measured_days,
        f"Seed {seed}: measured observation count is not {measured_days}.",
    )
    _assert_true(
        pd.to_numeric(observations["day"], errors="raise").astype(int).tolist()
        == list(range(measured_days)),
        f"Seed {seed}: measured observations are not J0..J{measured_days - 1}.",
    )
    _assert_true(
        not commands.empty and "effective_day" in commands,
        f"Seed {seed}: V2 command evidence is empty.",
    )
    gate_violations = command_gate_violations(commands)
    _assert_true(
        not gate_violations,
        f"Seed {seed}: {len(gate_violations)} command gate violation(s): "
        f"{gate_violations[:3]!r}.",
    )
    command_days = pd.to_numeric(commands["effective_day"], errors="raise").astype(int)
    _assert_true(
        int(command_days.min()) >= 1,
        f"Seed {seed}: a feedback command is effective on J0 or earlier.",
    )
    _assert_true(
        "day" in action_ledger and not action_ledger.empty,
        f"Seed {seed}: physical feedback action ledger is empty.",
    )
    ledger_days = pd.to_numeric(action_ledger["day"], errors="raise").astype(int)
    _assert_true(
        bool(ledger_days.ge(1).all()),
        f"Seed {seed}: action ledger contains J0 or warm-up actions.",
    )

    stability = terminal_stability_diagnostic(
        priming,
        window_days=stability_window_days,
        relative_mean_tolerance=stability_relative_mean_tolerance,
    )
    return {
        "seed": int(seed),
        "warmup_days": int(warmup_days),
        "measured_days": int(measured_days),
        "boundary_core_state_sha256": str(
            reference_boundary["core_state_sha256"]
        ),
        "boundary_component_sha256": dict(
            reference_boundary["component_sha256"]
        ),
        "boundary_hashes_match": True,
        "controller_priming_rows": int(len(priming)),
        "controller_warmup_action_count": 0,
        "first_feedback_effective_day": int(command_days.min()),
        "strict_closed_loop_claimed": True,
        "gate_violation_count": 0,
        "burn_in_stability_diagnostic": stability,
    }


def _read_summary(result_dir: Path) -> dict[str, Any]:
    return _read_json_object(
        result_dir / "summaries" / "first_simulation_summary.json",
        "engine summary",
    )


def _validate_split_artifacts(
    *,
    phase: str,
    artifacts: canonical.CanonicalClosedLoopArtifacts,
    seeds: Sequence[int],
    measured_days: int,
    warmup_days: int,
    stability_window_days: int,
    stability_relative_mean_tolerance: float,
) -> list[dict[str, Any]]:
    runs = artifacts.runs
    evidence: list[dict[str, Any]] = []
    for seed in seeds:
        paired = runs.loc[runs["seed"].eq(int(seed))]
        _assert_true(
            len(paired) == 2
            and set(paired["policy"].astype(str))
            == {REFERENCE_POLICY, FEEDBACK_POLICY},
            f"{phase} seed {seed}: missing exact MRP/feedback pair.",
        )
        result_dirs = {
            str(row["policy"]): Path(str(row["result_dir"]))
            for _, row in paired.iterrows()
        }
        feedback_row = paired.loc[paired["policy"].eq(FEEDBACK_POLICY)].iloc[0]
        _assert_true(
            bool(feedback_row["true_state_feedback"]),
            f"{phase} seed {seed}: canonical runner did not confirm true feedback.",
        )
        reference_dir = result_dirs[REFERENCE_POLICY]
        feedback_dir = result_dirs[FEEDBACK_POLICY]
        evidence.append(
            validate_pair_evidence(
                reference_summary=_read_summary(reference_dir),
                feedback_summary=_read_summary(feedback_dir),
                priming=pd.read_csv(
                    feedback_dir / "data" / "canonical_controller_priming.csv"
                ),
                observations=pd.read_csv(
                    feedback_dir
                    / "data"
                    / "canonical_closed_loop_observations.csv"
                ),
                commands=pd.read_csv(
                    feedback_dir / "data" / "canonical_closed_loop_commands.csv"
                ),
                action_ledger=pd.read_csv(
                    feedback_dir / "data" / "canonical_action_ledger.csv"
                ),
                seed=int(seed),
                measured_days=measured_days,
                warmup_days=warmup_days,
                stability_window_days=stability_window_days,
                stability_relative_mean_tolerance=(
                    stability_relative_mean_tolerance
                ),
            )
        )
    return evidence


def _phase_names(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("training", "validation")
    if value in {"pilot", "training", "validation"}:
        return (value,)
    raise ValueError(f"Unsupported phase: {value}")


def _artifact_hashes(output_dir: Path) -> dict[str, str]:
    candidates = {
        "manifest": output_dir / "canonical_closed_loop_manifest.json",
        "runs": output_dir / "canonical_closed_loop_runs.csv",
        "paired_deltas": output_dir / "canonical_closed_loop_paired_deltas.csv",
        "paired_summary": output_dir / "canonical_closed_loop_paired_summary.csv",
        "commands": output_dir / "canonical_closed_loop_commands.json",
        "comparison_plot": output_dir / "canonical_closed_loop_comparison.png",
        "control_diagnostics_plot": output_dir
        / "canonical_closed_loop_control_diagnostics.png",
    }
    return {
        name: _sha256(path)
        for name, path in candidates.items()
        if path.is_file()
    }


def run_v2_protocol(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path | None = None,
    phase: str = "all",
    make_plot: bool | None = None,
) -> V2ProtocolArtifacts:
    """Execute selected protocol splits and write the V2 protocol manifest."""

    root = repo_root.resolve()
    config = config_path.resolve()
    payload = _read_json_object(config, "V2 control-policy config")
    normalized = validate_protocol_payload(payload)
    campaign = normalized["campaign"]
    selected_phases = _phase_names(phase)

    graph_value = campaign.get("graph", "auto")
    if str(graph_value) == "auto":
        graph_path = canonical.discover_canonical_graph(root, "auto")
        if graph_path is None:
            raise FileNotFoundError("No canonical graph candidate was discovered.")
    else:
        graph_path = _resolve_path(
            str(graph_value), repo_root=root, relative_to=config.parent
        )
    policy_path = _resolve_path(
        str(campaign.get("control_policy_json") or config),
        repo_root=root,
        relative_to=config.parent,
    )
    policy_payload = _read_json_object(policy_path, "V2 control-policy JSON")
    _assert_true(
        str(policy_payload.get("schema_version") or "")
        == "scan.canonical_state_feedback.v2",
        "The configured policy is not a V2 provider policy.",
    )
    engine_path = _resolve_path(
        str(
            campaign.get("engine_script")
            or root
            / "etudecas"
            / "simulation"
            / "engine"
            / "run_first_simulation.py"
        ),
        repo_root=root,
        relative_to=config.parent,
    )
    profile_args: tuple[str, ...] = ()
    profile_metadata: dict[str, Any] = {}
    profile_value = campaign.get("engine_profile")
    if profile_value:
        profile_path = _resolve_path(
            str(profile_value), repo_root=root, relative_to=config.parent
        )
        profile_args, profile_metadata = canonical.load_canonical_engine_profile(
            root, str(profile_path)
        )
    common_engine_args = (
        *profile_args,
        *normalized["engine_args"],
    )
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

    risk_value = campaign.get("supplier_risk_events_csv")
    risk_path = (
        _resolve_path(str(risk_value), repo_root=root, relative_to=config.parent)
        if risk_value
        else None
    )
    selected_plot = (
        bool(campaign.get("plot", True)) if make_plot is None else make_plot
    )
    seed_sets = {
        "pilot": (normalized["training_seeds"][0],),
        "training": normalized["training_seeds"],
        "validation": normalized["validation_seeds"],
    }
    policy_hash_before_execution = _sha256(policy_path)
    split_artifacts: dict[str, canonical.CanonicalClosedLoopArtifacts] = {}
    split_evidence: dict[str, list[dict[str, Any]]] = {}
    protocol_config = normalized["protocol"]
    stability_window_days = int(
        protocol_config.get("terminal_stability_window_days", 14)
    )
    stability_relative_mean_tolerance = float(
        protocol_config.get("terminal_window_relative_mean_tolerance", 0.05)
    )

    for split_name in selected_phases:
        split_output = output / split_name
        artifacts = canonical.run_canonical_closed_loop(
            repo_root=root,
            graph_path=graph_path,
            control_policy_path=policy_path,
            seeds=seed_sets[split_name],
            output_root=split_output,
            days=int(normalized["days"]),
            scenario_id=str(campaign.get("scenario_id") or "scn:BASE"),
            engine_script=engine_path,
            supplier_risk_events_path=risk_path,
            enable_state_dependent_risks=bool(
                normalized["state_dependent_risks"]
            ),
            engine_extra_args=common_engine_args,
            feedback_engine_extra_args=(
                "--controller-prime-during-warmup",
            ),
            control_policy_flag=V2_CONTROL_FLAG,
            engine_profile_metadata=profile_metadata,
            make_plot=selected_plot,
        )
        _assert_true(
            _sha256(policy_path) == policy_hash_before_execution,
            "The V2 policy/config changed during campaign execution.",
        )
        split_artifacts[split_name] = artifacts
        split_evidence[split_name] = _validate_split_artifacts(
            phase=split_name,
            artifacts=artifacts,
            seeds=seed_sets[split_name],
            measured_days=int(normalized["days"]),
            warmup_days=int(normalized["warmup_days"]),
            stability_window_days=stability_window_days,
            stability_relative_mean_tolerance=stability_relative_mean_tolerance,
        )

    protocol: dict[str, Any] = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "complete_training_and_held_out_validation"
            if selected_phases == ("training", "validation")
            else f"partial_{selected_phases[0]}_only"
        ),
        "comparison": "paired_mrp_vs_canonical_feedback_v2",
        "method": "deterministic_paired_burn_in_replay",
        "scientific_claim": (
            "causal closed-loop V2 with paired warm-start boundary evidence; "
            "not a restart checkpoint, stationarity proof, or industrial validation"
        ),
        "runner": {"path": str(HERE), "sha256": _sha256(HERE)},
        "config": {
            "path": str(config),
            "sha256_frozen_before_execution": policy_hash_before_execution,
            "schema_version": str(payload["schema_version"]),
        },
        "graph": {"path": str(graph_path), "sha256": _sha256(graph_path)},
        "engine": {"path": str(engine_path), "sha256": _sha256(engine_path)},
        "control_interface": {
            "engine_flag": V2_CONTROL_FLAG,
            "controller_priming_flag": "--controller-prime-during-warmup",
            "causal_lag_days": 1,
            "first_feedback_effective_day_minimum": 1,
        },
        "warm_start_contract": {
            "physical_warmup_days": int(normalized["warmup_days"]),
            "profile_mode": "preperiod",
            "restore_opening_stock_after_warmup": False,
            "reset_backlog_after_warmup": False,
            "controller_priming_observation_count": int(
                normalized["warmup_days"]
            ),
            "controller_warmup_action_count": 0,
            "boundary_hash_scope": (
                "core_dynamic_engine_state_not_restart_checkpoint"
            ),
            "restart_checkpoint_available": False,
            "stationarity_claimed": False,
        },
        "seed_protocol": {
            "training": list(normalized["training_seeds"]),
            "validation": list(normalized["validation_seeds"]),
            "training_count": REQUIRED_TRAINING_SEED_COUNT,
            "validation_count": REQUIRED_VALIDATION_SEED_COUNT,
            "disjoint": True,
            "validation_is_held_out": True,
            "automatic_retuning_on_validation": False,
        },
        "executed_splits": list(selected_phases),
        "unexecuted_splits": sorted(
            {"training", "validation"} - set(selected_phases)
        ),
        "burn_in_stability": {
            "method": "two_terminal_aggregate_mean_windows",
            "window_days": stability_window_days,
            "relative_mean_tolerance": stability_relative_mean_tolerance,
            "stationarity_claimed": False,
            "status": (
                "terminal_window_heuristic_satisfied_not_stationarity_proof"
                if all(
                    row["burn_in_stability_diagnostic"]["status"]
                    == "terminal_window_heuristic_satisfied_not_stationarity_proof"
                    for rows in split_evidence.values()
                    for row in rows
                )
                else "stability_not_demonstrated"
            ),
        },
        "gate_audit": {
            "rule": (
                "positive order/safety/production requires service_recovery_gate; "
                "positive external procurement/expedite requires exceptional_cost_gate"
            ),
            "violation_count": sum(
                int(row["gate_violation_count"])
                for rows in split_evidence.values()
                for row in rows
            ),
            "all_command_rows_linked_to_valid_observation_hash": True,
        },
        "splits": {
            split_name: {
                "output_dir": str(split_artifacts[split_name].output_root),
                "canonical_manifest": str(
                    split_artifacts[split_name].manifest_path
                ),
                "paired_seed_count": len(seed_sets[split_name]),
                "all_boundary_hashes_match": all(
                    row["boundary_hashes_match"]
                    for row in split_evidence[split_name]
                ),
                "all_feedback_runs_strictly_claimed": all(
                    row["strict_closed_loop_claimed"]
                    for row in split_evidence[split_name]
                ),
                "gate_violation_count": sum(
                    int(row["gate_violation_count"])
                    for row in split_evidence[split_name]
                ),
                "pair_evidence": split_evidence[split_name],
                "output_sha256": _artifact_hashes(
                    split_artifacts[split_name].output_root
                ),
            }
            for split_name in selected_phases
        },
        "engine_profile": profile_metadata,
        "engine_args": list(common_engine_args),
        "git": canonical._git_provenance(root),
        "limitations": [
            "The J0 artifact is a deterministic paired-state fingerprint, not a loadable restart checkpoint.",
            "A fixed 60-day burn-in reduces cold-start bias but does not prove stationarity.",
            "Controller coefficients and gates remain research parameters.",
            "Validation is simulation-only and is not evidence for industrial deployment.",
        ],
    }
    protocol_path = output / "canonical_closed_loop_v2_protocol.json"
    protocol_path.write_text(
        json.dumps(protocol, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return V2ProtocolArtifacts(
        split_artifacts=split_artifacts,
        output_root=output,
        protocol_path=protocol_path,
        protocol=protocol,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the additive paired warm-start V2 controller protocol."
        )
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--phase",
        choices=["pilot", "training", "validation", "all"],
        default="all",
        help=(
            "Run one non-inferential pilot seed, the 10-seed development split, "
            "the 30-seed held-out split, or both protocol splits."
        ),
    )
    parser.add_argument(
        "--plot",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = run_v2_protocol(
        Path(args.config),
        repo_root=Path(args.repo_root),
        output_root=Path(args.output_dir) if args.output_dir else None,
        phase=str(args.phase),
        make_plot=args.plot,
    )
    print(f"Canonical closed-loop V2 protocol completed: {artifacts.output_root}")
    print(f"Protocol evidence: {artifacts.protocol_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
