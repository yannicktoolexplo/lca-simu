"""Additive V2 state-feedback provider with warm-up priming and action gates.

The V1 provider remains the canonical implementation of the finite-state
controller and of the causal J-to-J+1 command contract.  This module extends
that implementation without changing it:

* negative-day warm-up observations may prime dynamic controller state;
* priming never emits a command, schedule row, or measured decision;
* two observation gates can immediately neutralize unsafe positive actions;
* every gate decision is linked to the measured observation hash.

The supported policy schema is deliberately distinct from V1:
``scan.canonical_state_feedback.v2``.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .control_provider import (
    CanonicalObservation,
    ControlCommand,
    ControlProviderError,
    StateFeedbackControlProvider,
    _json_safe,
    _stable_hash,
)
from .control_schedule import (
    ACTION_FIELDS,
    CONTROL_BOUNDS,
    ControlCatalog,
    ControlNumber,
)


SCHEMA_VERSION_V2 = "scan.canonical_state_feedback.v2"
SERVICE_RECOVERY_GATE = "service_recovery_gate"
EXCEPTIONAL_COST_GATE = "exceptional_cost_gate"
REQUIRED_GATE_IDS = (SERVICE_RECOVERY_GATE, EXCEPTIONAL_COST_GATE)

_GATE_SIGNALS = frozenset(
    {
        "service_level",
        "backlog_days",
        "backlog_qty",
        "demand_qty",
        "served_qty",
        "inventory_qty",
        "finished_inventory_cover_days",
        "material_cover_days",
        "production_utilization",
        "supplier_utilization",
        "order_nervousness",
        "supplier_disruption_score",
        "active_order_pair_count",
        "active_supplier_event_count",
    }
)
_GATE_OPERATORS = frozenset({"ge", "gt", "le", "lt", "eq"})
_GATE_DIRECTIONS = frozenset(
    {"above_neutral", "below_neutral", "away_from_neutral", "non_neutral"}
)

# These mappings are part of the V2 safety contract.  A configuration may map
# more actions, but it cannot remove or weaken these five gates.
_REQUIRED_ACTION_GATES: Mapping[str, str] = {
    "order_multiplier": SERVICE_RECOVERY_GATE,
    "safety_stock_multiplier": SERVICE_RECOVERY_GATE,
    "production_target_multiplier": SERVICE_RECOVERY_GATE,
    "external_procurement_multiplier": EXCEPTIONAL_COST_GATE,
    "expedite_level": EXCEPTIONAL_COST_GATE,
}


def _finite_gate_threshold(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ControlProviderError(f"{label} must be numeric and not boolean.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ControlProviderError(f"{label} must be numeric, got {value!r}.") from exc
    if not math.isfinite(parsed):
        raise ControlProviderError(f"{label} must be finite, got {value!r}.")
    return parsed


def _gate_predicate_matches(
    value: Any,
    *,
    operator: str,
    threshold: float,
) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(numeric):
        return False
    if operator == "ge":
        return numeric >= threshold
    if operator == "gt":
        return numeric > threshold
    if operator == "le":
        return numeric <= threshold
    if operator == "lt":
        return numeric < threshold
    return math.isclose(numeric, threshold, rel_tol=0.0, abs_tol=1e-12)


class StateFeedbackControlProviderV2(StateFeedbackControlProvider):
    """V1-compatible controller with opt-in priming and safety gates.

    Gate configuration uses two named ``require_any`` predicates.  Actions are
    associated with a gate and a direction relative to the action's neutral
    value.  When a gate closes, a blocked current action is set to neutral
    before the inherited slew calculation, so closure is effective on the next
    causal day rather than being trailed by the normal slew limit.
    """

    mode = "canonical_state_feedback_v2_t_plus_1"

    def __init__(
        self,
        payload: Mapping[str, Any],
        *,
        config_path: Path,
        config_sha256: str,
        catalog: ControlCatalog | None = None,
    ) -> None:
        if not isinstance(payload, Mapping):
            raise ControlProviderError("Control policy JSON root must be an object.")
        schema_version = str(payload.get("schema_version") or "")
        if schema_version != SCHEMA_VERSION_V2:
            raise ControlProviderError(
                "control policy V2 schema_version must be "
                f"'{SCHEMA_VERSION_V2}'."
            )

        # Base initialization calls the virtual _target_by_scope method while
        # validating topology.  Keep gates inert until their V2 configuration
        # has been parsed.  Only the copied payload is adapted for the V1
        # constructor; the caller's object and the V1 implementation are never
        # mutated.
        self._gates_enabled = False
        self._gate_specs: dict[str, tuple[dict[str, Any], ...]] = {}
        self._action_gate_map: dict[str, dict[str, str]] = {}
        self._gate_states: dict[str, dict[str, Any]] = {}
        self._gate_audit_by_effective_day: dict[int, dict[str, Any]] = {}
        self._forced_neutral_actions_current: set[str] = set()
        self._gate_evaluation_active = False
        self._priming_rows: list[dict[str, Any]] = []
        self._last_primed_day: int | None = None
        self._priming_final_regime = "NOMINAL"
        self._warmup_action_count = 0

        compatibility_payload = dict(payload)
        compatibility_payload["schema_version"] = "scan.canonical_state_feedback.v1"
        super().__init__(
            compatibility_payload,
            config_path=config_path,
            config_sha256=config_sha256,
            catalog=catalog,
        )
        self.schema_version = SCHEMA_VERSION_V2
        self._gate_specs = self._parse_gates(payload.get("gates"))
        self._action_gate_map = self._parse_action_gate_map(
            payload.get("action_gate_map")
        )
        self._gate_states = {
            gate_id: {
                "open": False,
                "reason": "closed:no_observation",
                "matched_predicates": (),
            }
            for gate_id in sorted(self._gate_specs)
        }
        self._gates_enabled = True

    @property
    def priming_rows(self) -> tuple[dict[str, Any], ...]:
        """Flat, immutable-copy rows for the optional warm-up audit CSV."""

        return tuple(dict(row) for row in self._priming_rows)

    @property
    def controller_dynamic_warmup_days(self) -> int:
        """Number of sequential negative-day observations used for priming."""

        return len(self._priming_rows)

    @property
    def warmup_action_count(self) -> int:
        """Number of actions produced during priming (always zero by design)."""

        return self._warmup_action_count

    def _parse_gates(self, raw: Any) -> dict[str, tuple[dict[str, Any], ...]]:
        if not isinstance(raw, Mapping):
            raise ControlProviderError("gates must be a JSON object.")
        missing = sorted(set(REQUIRED_GATE_IDS) - set(raw))
        if missing:
            raise ControlProviderError(
                "gates must define the required V2 gates: " + ", ".join(missing)
            )
        parsed: dict[str, tuple[dict[str, Any], ...]] = {}
        for raw_gate_id, raw_spec in raw.items():
            gate_id = str(raw_gate_id).strip()
            if not gate_id:
                raise ControlProviderError("gate identifiers must be non-empty strings.")
            label = f"gates.{gate_id}"
            if not isinstance(raw_spec, Mapping):
                raise ControlProviderError(f"{label} must be a JSON object.")
            unknown = sorted(set(raw_spec) - {"require_any"})
            if unknown:
                raise ControlProviderError(
                    f"{label} contains unknown fields: {', '.join(unknown)}."
                )
            predicates = raw_spec.get("require_any")
            if not isinstance(predicates, list) or not predicates:
                raise ControlProviderError(
                    f"{label}.require_any must be a non-empty JSON list."
                )
            parsed_predicates: list[dict[str, Any]] = []
            for index, predicate in enumerate(predicates):
                predicate_label = f"{label}.require_any[{index}]"
                if not isinstance(predicate, Mapping):
                    raise ControlProviderError(
                        f"{predicate_label} must be a JSON object."
                    )
                unknown_predicate = sorted(
                    set(predicate) - {"signal", "operator", "threshold"}
                )
                if unknown_predicate:
                    raise ControlProviderError(
                        f"{predicate_label} contains unknown fields: "
                        + ", ".join(unknown_predicate)
                    )
                signal = str(predicate.get("signal") or "")
                operator = str(predicate.get("operator") or "")
                if signal not in _GATE_SIGNALS:
                    raise ControlProviderError(
                        f"{predicate_label}.signal must be an auditable canonical "
                        f"observation field; got {signal!r}."
                    )
                if operator not in _GATE_OPERATORS:
                    raise ControlProviderError(
                        f"{predicate_label}.operator must be one of "
                        f"{sorted(_GATE_OPERATORS)}; got {operator!r}."
                    )
                if "threshold" not in predicate:
                    raise ControlProviderError(
                        f"{predicate_label}.threshold is required."
                    )
                threshold = _finite_gate_threshold(
                    predicate["threshold"],
                    label=f"{predicate_label}.threshold",
                )
                parsed_predicates.append(
                    {
                        "signal": signal,
                        "operator": operator,
                        "threshold": threshold,
                    }
                )
            parsed[gate_id] = tuple(parsed_predicates)
        return parsed

    def _parse_action_gate_map(self, raw: Any) -> dict[str, dict[str, str]]:
        if not isinstance(raw, Mapping):
            raise ControlProviderError("action_gate_map must be a JSON object.")
        unknown_actions = sorted(set(raw) - set(ACTION_FIELDS))
        if unknown_actions:
            raise ControlProviderError(
                "action_gate_map contains unknown actions: "
                + ", ".join(unknown_actions)
            )
        parsed: dict[str, dict[str, str]] = {}
        for action_name, raw_mapping in raw.items():
            label = f"action_gate_map.{action_name}"
            if not isinstance(raw_mapping, Mapping):
                raise ControlProviderError(f"{label} must be a JSON object.")
            unknown = sorted(set(raw_mapping) - {"gate", "direction"})
            if unknown:
                raise ControlProviderError(
                    f"{label} contains unknown fields: {', '.join(unknown)}."
                )
            gate_id = str(raw_mapping.get("gate") or "")
            direction = str(raw_mapping.get("direction") or "")
            if gate_id not in self._gate_specs:
                raise ControlProviderError(
                    f"{label}.gate references unknown gate {gate_id!r}."
                )
            if direction not in _GATE_DIRECTIONS:
                raise ControlProviderError(
                    f"{label}.direction must be one of "
                    f"{sorted(_GATE_DIRECTIONS)}; got {direction!r}."
                )
            parsed[str(action_name)] = {
                "gate": gate_id,
                "direction": direction,
            }

        missing = sorted(set(_REQUIRED_ACTION_GATES) - set(parsed))
        if missing:
            raise ControlProviderError(
                "action_gate_map must define the required V2 guarded actions: "
                + ", ".join(missing)
            )
        for action_name, required_gate in _REQUIRED_ACTION_GATES.items():
            mapping = parsed[action_name]
            if mapping["gate"] != required_gate:
                raise ControlProviderError(
                    f"action_gate_map.{action_name}.gate must be "
                    f"{required_gate!r}."
                )
            if mapping["direction"] != "above_neutral":
                raise ControlProviderError(
                    f"action_gate_map.{action_name}.direction must be "
                    "'above_neutral'."
                )
        return parsed

    def _evaluate_gates(
        self,
        signals: Mapping[str, Any],
        *,
        invalid_reason: str,
    ) -> dict[str, dict[str, Any]]:
        states: dict[str, dict[str, Any]] = {}
        for gate_id in sorted(self._gate_specs):
            if invalid_reason:
                states[gate_id] = {
                    "open": False,
                    "reason": f"closed:invalid_observation:{invalid_reason}",
                    "matched_predicates": (),
                }
                continue
            matches: list[str] = []
            for predicate in self._gate_specs[gate_id]:
                signal = str(predicate["signal"])
                operator = str(predicate["operator"])
                threshold = float(predicate["threshold"])
                if _gate_predicate_matches(
                    signals.get(signal),
                    operator=operator,
                    threshold=threshold,
                ):
                    matches.append(f"{signal}:{operator}:{threshold:.12g}")
            is_open = bool(matches)
            states[gate_id] = {
                "open": is_open,
                "reason": (
                    "open:" + "|".join(matches)
                    if is_open
                    else "closed:no_require_any_predicate_satisfied"
                ),
                "matched_predicates": tuple(matches),
            }
        return states

    @staticmethod
    def _direction_blocks(
        value: ControlNumber,
        *,
        neutral: ControlNumber,
        direction: str,
    ) -> bool:
        delta = float(value) - float(neutral)
        if direction == "above_neutral":
            return delta > 1e-12
        if direction == "below_neutral":
            return delta < -1e-12
        return abs(delta) > 1e-12

    def _action_is_blocked(self, action_name: str, value: ControlNumber) -> bool:
        mapping = self._action_gate_map.get(action_name)
        if mapping is None:
            return False
        gate_state = self._gate_states.get(mapping["gate"], {"open": False})
        if bool(gate_state.get("open")):
            return False
        return self._direction_blocks(
            value,
            neutral=CONTROL_BOUNDS[action_name].neutral,
            direction=mapping["direction"],
        )

    def _force_closed_gate_state_to_neutral(self) -> None:
        for state in self._current_by_scope.values():
            for action_name, value in tuple(state.items()):
                if self._action_is_blocked(action_name, value):
                    state[action_name] = CONTROL_BOUNDS[action_name].neutral
                    self._forced_neutral_actions_current.add(action_name)

    def _target_by_scope(
        self, policy: str
    ) -> dict[tuple[str, str, str, str], dict[str, ControlNumber]]:
        targets = super()._target_by_scope(policy)
        if not self._gates_enabled:
            return targets
        for target in targets.values():
            for action_name, value in tuple(target.items()):
                if self._action_is_blocked(action_name, value):
                    target[action_name] = CONTROL_BOUNDS[action_name].neutral
                    if self._gate_evaluation_active:
                        self._forced_neutral_actions_current.add(action_name)
        return targets

    def _gate_audit_payload(
        self,
        *,
        observation_hash: str,
        observation_valid: bool,
        forced_actions: set[str] | tuple[str, ...],
    ) -> dict[str, Any]:
        gate_ids = sorted(self._gate_states)
        open_ids = [
            gate_id
            for gate_id in gate_ids
            if bool(self._gate_states[gate_id]["open"])
        ]
        forced = sorted(set(forced_actions), key=ACTION_FIELDS.index)
        reasons = {
            gate_id: str(self._gate_states[gate_id]["reason"])
            for gate_id in gate_ids
        }
        return {
            "control_gate_ids": ";".join(gate_ids),
            "control_open_gate_ids": ";".join(open_ids),
            "control_closed_gate_ids": ";".join(
                gate_id for gate_id in gate_ids if gate_id not in open_ids
            ),
            "control_gate_reasons_json": json.dumps(
                reasons,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "control_action_gate_map_json": json.dumps(
                self._action_gate_map,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "control_gate_forced_neutral": int(bool(forced)),
            "control_gate_forced_neutral_actions": ";".join(forced),
            "control_gate_observation_hash": observation_hash,
            "control_gate_observation_valid": int(observation_valid),
        }

    def prime(
        self,
        observation: CanonicalObservation,
    ) -> tuple[ControlCommand, ...]:
        """Prime controller memory from one sequential negative-day state.

        Priming updates only dynamic observation memory and regime confirmation.
        It intentionally does not select a playbook and never writes measured
        observations, decisions, commands, or schedule rows.
        """

        if self._last_observed_day is not None or self._observation_rows:
            raise ControlProviderError(
                "Controller priming cannot continue after measured observations."
            )
        day = observation.day
        if isinstance(day, bool) or not isinstance(day, int) or day >= 0:
            raise ControlProviderError(
                "Priming observation day must be a negative integer, "
                f"got {day!r}."
            )
        if self._last_primed_day is not None and day != self._last_primed_day + 1:
            raise ControlProviderError(
                "Priming observations must be strictly sequential: "
                f"last={self._last_primed_day}, received={day}."
            )

        # The inherited normalizer treats negative days as invalid because V1
        # only accepts measured observations.  Validate the same physical
        # fields with a temporary non-negative day, then restore the real
        # negative audit day.
        raw, invalid_reason = super()._normalize_observation(
            replace(observation, day=0)
        )
        raw["day"] = day
        previous_backlog_days = self._last_backlog_days
        previous_order_nervousness = self._previous_order_nervousness
        if invalid_reason:
            nervousness = 0.0
            supplier_stress = self._supplier_stress
            recent_disruption = False
            raw_regime = "INVALID_OBSERVATION"
            self._confirmed_regime = "NOMINAL"
            self._pending_regime = ""
            self._pending_count = 0
        else:
            nervousness = float(raw["order_nervousness"])
            pressure = max(
                0.0,
                float(raw["supplier_utilization"])
                - self.dynamics["capacity_pressure_start"],
            )
            supplier_stress = max(
                0.0,
                min(
                    2.0,
                    self.dynamics["stress_memory"] * self._supplier_stress
                    + self.dynamics["nervousness_gain"] * min(2.0, nervousness)
                    + self.dynamics["pressure_gain"] * pressure
                    + self.dynamics["disruption_gain"]
                    * float(raw["supplier_disruption_score"]),
                ),
            )
            recent_disruption = self._update_recent_disruption_memory(
                day=day,
                score=float(raw["supplier_disruption_score"]),
            )
            finished_cover = raw.get("finished_inventory_cover_days")
            raw["inventory_excess_ratio"] = (
                float(finished_cover)
                / max(1e-9, self.thresholds["nominal_finished_inventory_days"])
                if finished_cover is not None
                else 1.0
            )
            raw["nervousness"] = nervousness
            raw["supplier_stress"] = supplier_stress
            raw["recent_disruption_signal"] = int(recent_disruption)
            raw_regime = self._classify(raw)
            self._update_confirmed_regime(raw_regime)

        normalized = dict(raw)
        normalized.update(
            {
                "previous_backlog_days": previous_backlog_days,
                "previous_order_nervousness": previous_order_nervousness,
                "nervousness": nervousness,
                "supplier_stress": supplier_stress,
                "recent_disruption_signal": int(recent_disruption),
                "raw_regime": raw_regime,
                "confirmed_regime": self._confirmed_regime,
            }
        )
        observation_hash = _stable_hash(normalized)
        normalized["observation_hash"] = observation_hash
        normalized["observation_valid"] = int(not invalid_reason)
        normalized["invalid_reason"] = invalid_reason
        self._gate_states = self._evaluate_gates(
            raw,
            invalid_reason=invalid_reason,
        )
        gate_audit = self._gate_audit_payload(
            observation_hash=observation_hash,
            observation_valid=not invalid_reason,
            forced_actions=set(),
        )
        normalized.update(gate_audit)
        normalized["priming_observation"] = 1
        normalized["generated_command_count"] = 0
        normalized["active_command_row_count"] = 0
        self._priming_rows.append(_json_safe(normalized))
        self._last_primed_day = day
        self._priming_final_regime = self._confirmed_regime
        if not invalid_reason:
            self._last_backlog_days = float(raw["backlog_days"])
            self._previous_order_nervousness = nervousness
            self._supplier_stress = supplier_stress
        return ()

    def observe(
        self,
        observation: CanonicalObservation,
        last_effective_day: int | None = None,
    ) -> tuple[ControlCommand, ...]:
        """Observe measured state, apply gates, and emit causal J+1 commands."""

        day = observation.day
        if isinstance(day, bool) or not isinstance(day, int) or day < 0:
            raise ControlProviderError(
                "Feedback observation day must be a zero-based non-negative "
                f"integer, got {day!r}."
            )
        if self._last_observed_day is not None and day != self._last_observed_day + 1:
            raise ControlProviderError(
                "Feedback observations must be strictly sequential: "
                f"last={self._last_observed_day}, received={day}."
            )
        if self._priming_rows and self._last_observed_day is None:
            if self._last_primed_day != -1 or observation.day != 0:
                raise ControlProviderError(
                    "A primed controller must end warm-up at day -1 and start "
                    "measured observations at day 0."
                )
        raw, invalid_reason = super()._normalize_observation(observation)
        self._gate_states = self._evaluate_gates(
            raw,
            invalid_reason=invalid_reason,
        )
        self._forced_neutral_actions_current = set()
        self._force_closed_gate_state_to_neutral()
        self._gate_evaluation_active = True
        try:
            commands = super().observe(
                observation,
                last_effective_day=last_effective_day,
            )
        finally:
            self._gate_evaluation_active = False

        decision = self._decision_rows[-1]
        audit = self._gate_audit_payload(
            observation_hash=str(decision["observation_hash"]),
            observation_valid=bool(decision["observation_valid"]),
            forced_actions=self._forced_neutral_actions_current,
        )
        decision.update(audit)
        effective_day = int(decision["effective_day"])
        self._gate_audit_by_effective_day[effective_day] = dict(audit)
        return commands

    def command_audit_metadata_for_day(self, day: int) -> dict[str, Any]:
        """Return flat V2 gate audit fields for commands effective on ``day``."""

        audit = self._gate_audit_by_effective_day.get(int(day))
        if audit is not None:
            return dict(audit)
        gate_ids = sorted(self._gate_specs)
        return {
            "control_gate_ids": ";".join(gate_ids),
            "control_open_gate_ids": "",
            "control_closed_gate_ids": ";".join(gate_ids),
            "control_gate_reasons_json": json.dumps(
                {gate_id: "closed:no_prior_observation" for gate_id in gate_ids},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "control_action_gate_map_json": json.dumps(
                self._action_gate_map,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "control_gate_forced_neutral": 0,
            "control_gate_forced_neutral_actions": "",
            "control_gate_observation_hash": "",
            "control_gate_observation_valid": 0,
        }

    def audit_metadata_for_day(self, day: int) -> dict[str, Any]:
        """Extend the inherited online command audit with V2 gate evidence."""

        return {
            **super().audit_metadata_for_day(day),
            **self.command_audit_metadata_for_day(day),
        }

    def summary_metadata(self) -> dict[str, Any]:
        """Return V1 metadata plus V2 priming and safety-gate evidence."""

        metadata = super().summary_metadata()
        first_day = (
            int(self._priming_rows[0]["day"])
            if self._priming_rows
            else None
        )
        last_day = self._last_primed_day
        valid_priming_count = sum(
            int(row.get("observation_valid", 0))
            for row in self._priming_rows
        )
        sequential = all(
            int(current["day"]) == int(previous["day"]) + 1
            for previous, current in zip(
                self._priming_rows,
                self._priming_rows[1:],
            )
        )
        metadata.update(
            {
                "schema_version": SCHEMA_VERSION_V2,
                "mode": self.mode,
                "integration_mode": self.mode,
                "controller_dynamic_warmup_days": len(self._priming_rows),
                "controller_priming_observation_count": len(self._priming_rows),
                "controller_priming_valid_observation_count": valid_priming_count,
                "controller_priming_invalid_observation_count": (
                    len(self._priming_rows) - valid_priming_count
                ),
                "controller_priming_all_observations_valid": bool(
                    self._priming_rows
                    and valid_priming_count == len(self._priming_rows)
                ),
                "controller_primed_during_warmup": bool(self._priming_rows),
                "controller_priming_first_day": first_day,
                "controller_priming_last_day": last_day,
                "controller_priming_sequential": sequential,
                "controller_priming_complete_at_day_minus_one": bool(
                    self._priming_rows and last_day == -1
                ),
                "controller_priming_last_observation_hash": (
                    str(self._priming_rows[-1]["observation_hash"])
                    if self._priming_rows
                    else ""
                ),
                "controller_priming_final_regime": self._priming_final_regime,
                "warmup_action_count": self._warmup_action_count,
                "warmup_commands_disabled": self._warmup_action_count == 0,
                "gate_ids": sorted(self._gate_specs),
                "gate_action_count": len(self._action_gate_map),
                "gate_forced_neutral_decision_count": sum(
                    int(row.get("control_gate_forced_neutral", 0))
                    for row in self._decision_rows
                ),
                "gate_invalid_observation_fail_closed": True,
                "gate_closure_bypasses_slew_to_neutral": True,
            }
        )
        return metadata


def load_state_feedback_control_provider_v2(
    path: Path | str,
    *,
    catalog: ControlCatalog | None = None,
) -> StateFeedbackControlProviderV2:
    """Load and validate one declarative V2 feedback policy JSON."""

    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ControlProviderError(
            f"Control policy V2 does not exist or is not a file: {config_path}"
        )
    try:
        raw_bytes = config_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ControlProviderError(
            f"Cannot read control policy V2 {config_path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ControlProviderError("Control policy V2 JSON root must be an object.")
    return StateFeedbackControlProviderV2(
        payload,
        config_path=config_path,
        config_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        catalog=catalog,
    )


__all__ = [
    "EXCEPTIONAL_COST_GATE",
    "SCHEMA_VERSION_V2",
    "SERVICE_RECOVERY_GATE",
    "StateFeedbackControlProviderV2",
    "load_state_feedback_control_provider_v2",
]
