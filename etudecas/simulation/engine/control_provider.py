"""Causal control providers for the canonical daily simulation loop.

The historical :class:`~etudecas.simulation.engine.control_schedule.ControlSchedule`
is an open-loop provider: every command is known before the run.  This module
adds a deliberately small state-feedback provider whose only mutation point is
``observe(end_of_day_state)``.  An observation for measured day ``J`` can only
create a command for ``J + 1``.

The finite-state selector is a research safety layer around the existing MRP;
it does not replace MRP, lot sizing, capacity checks or campaigns.  Its
supplier-disruption input is a physical severity proxy, never an incident
probability.  Configuration, observations, regime changes, fallbacks and slew
limits remain auditable through flat ledgers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from .control_schedule import (
    ACTION_FIELDS,
    CONTROL_BOUNDS,
    SCOPE_FIELDS,
    ControlCatalog,
    ControlNumber,
    ControlSchedule,
    ControlScheduleError,
    ControlScheduleRow,
    ResolvedControl,
    _validate_action_scope_compatibility,
    _validate_catalog,
    _validate_row_relationships,
)


REGIMES: tuple[str, ...] = (
    "NOMINAL",
    "MATERIAL_TENSION",
    "CAPACITY_SATURATION",
    "SUPPLIER_STRESS",
    "OSCILLATORY",
    "CRISIS",
    "RECOVERY",
    "POST_CRISIS_OVERSTOCK",
)

DEFAULT_THRESHOLDS: Mapping[str, float] = {
    "material_tension_days": 0.85,
    "capacity_saturation": 0.94,
    "supplier_disruption": 0.25,
    "supplier_stress": 0.72,
    "oscillation_nervousness": 0.38,
    "crisis_backlog_days": 1.60,
    "crisis_disruption_floor": 0.15,
    "recovery_backlog_days": 0.15,
    "overstock_days": 7.0,
    "nominal_finished_inventory_days": 1.2,
}


class ControlProviderError(ValueError):
    """Raised when a feedback policy or observation is unsafe or ambiguous."""


@dataclass(frozen=True)
class CanonicalObservation:
    """End-of-day state exposed by the canonical engine to a policy.

    All quantities are realized values for ``day``.  Cover and backlog signals
    are already normalized in days, which avoids summing incompatible item
    units in regime predicates.
    """

    day: int
    demand_qty: float
    served_qty: float
    service_level: float
    backlog_qty: float
    backlog_days: float
    inventory_qty: float
    finished_inventory_cover_days: float | None
    material_cover_days: float | None
    production_utilization: float
    supplier_utilization: float
    order_nervousness: float
    active_order_pair_count: int
    supplier_disruption_score: float
    active_supplier_event_count: int


@dataclass(frozen=True)
class ControlCommand:
    """One online decision for one exact or global operational scope."""

    decision_day: int
    effective_day: int
    policy: str
    node_id: str = ""
    supplier_id: str = ""
    item_id: str = ""
    dst_node_id: str = ""
    requested: Mapping[str, ControlNumber] | None = None
    effective: Mapping[str, ControlNumber] | None = None
    slew_limited_actions: tuple[str, ...] = ()
    source_line: int | None = None

    @property
    def scope_key(self) -> tuple[str, str, str, str]:
        return (self.node_id, self.supplier_id, self.item_id, self.dst_node_id)

    @property
    def active(self) -> bool:
        return any(
            name in CONTROL_BOUNDS
            and abs(
                float(value) - float(CONTROL_BOUNDS[name].neutral)
            )
            > 1e-12
            for name, value in (self.effective or {}).items()
        )

    def to_schedule_row(self) -> ControlScheduleRow | None:
        """Translate an active online command to the existing resolver contract."""

        if not self.active or self.source_line is None:
            return None
        effective = {
            name: value
            for name, value in (self.effective or {}).items()
            if name in CONTROL_BOUNDS
            and abs(float(value) - float(CONTROL_BOUNDS[name].neutral)) > 1e-12
        }
        requested = {
            name: (self.requested or {}).get(name, value)
            for name, value in effective.items()
        }
        return ControlScheduleRow(
            day=int(self.effective_day),
            policy=self.policy,
            node_id=self.node_id,
            supplier_id=self.supplier_id,
            item_id=self.item_id,
            dst_node_id=self.dst_node_id,
            requested=requested,
            effective=effective,
            bound={name: "none" for name in effective},
            source_line=int(self.source_line),
        )


@runtime_checkable
class ControlProvider(Protocol):
    """Minimal interface consumed by the canonical daily engine."""

    @property
    def enabled(self) -> bool: ...

    @property
    def rows(self) -> tuple[ControlScheduleRow, ...]: ...

    @property
    def warnings(self) -> tuple[str, ...]: ...

    def resolve(
        self,
        day: int,
        node_id: str = "",
        supplier_id: str = "",
        item_id: str = "",
        dst_node_id: str = "",
    ) -> ResolvedControl: ...


def _finite_float(value: Any, *, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ControlProviderError(f"{label} must be numeric, got {value!r}.") from exc
    if not math.isfinite(parsed):
        raise ControlProviderError(f"{label} must be finite, got {value!r}.")
    return parsed


def _positive_int(value: Any, *, label: str, allow_zero: bool = False) -> int:
    if isinstance(value, bool):
        raise ControlProviderError(f"{label} must be an integer, got {value!r}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ControlProviderError(f"{label} must be an integer, got {value!r}.") from exc
    if str(value).strip() not in {str(parsed), f"{parsed}.0"}:
        raise ControlProviderError(f"{label} must be an integer, got {value!r}.")
    minimum = 0 if allow_zero else 1
    if parsed < minimum:
        raise ControlProviderError(f"{label} must be >= {minimum}, got {parsed}.")
    return parsed


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scope_dict(raw: Mapping[str, Any], *, label: str) -> dict[str, str]:
    unknown = sorted(set(raw) - set(SCOPE_FIELDS))
    if unknown:
        raise ControlProviderError(
            f"{label} contains unknown scope fields: {', '.join(unknown)}."
        )
    scope: dict[str, str] = {}
    for name in SCOPE_FIELDS:
        if name not in raw:
            scope[name] = ""
            continue
        value = raw[name]
        if not isinstance(value, str):
            raise ControlProviderError(
                f"{label}.{name} must be a string; got {value!r}."
            )
        scope[name] = value.strip()
    return scope


def _compatible_scope_keys(
    left: tuple[str, str, str, str],
    right: tuple[str, str, str, str],
) -> bool:
    return all(not lhs or not rhs or lhs == rhs for lhs, rhs in zip(left, right))


class StateFeedbackControlProvider:
    """Declarative finite-state feedback controller with causal J-to-J+1 output."""

    mode = "canonical_state_feedback_t_plus_1"

    def __init__(
        self,
        payload: Mapping[str, Any],
        *,
        config_path: Path,
        config_sha256: str,
        catalog: ControlCatalog | None = None,
    ) -> None:
        self.config_path = config_path
        self.config_sha256 = str(config_sha256)
        self.catalog = catalog
        self.name = str(payload.get("name") or "canonical_state_feedback")
        schema_version = str(payload.get("schema_version") or "")
        if schema_version != "scan.canonical_state_feedback.v1":
            raise ControlProviderError(
                "control policy schema_version must be "
                "'scan.canonical_state_feedback.v1'."
            )
        self.schema_version = schema_version
        self.review_period_days = _positive_int(
            payload.get("review_period_days", 7), label="review_period_days"
        )
        self.confirmation_days = _positive_int(
            payload.get("confirmation_days", 2), label="confirmation_days"
        )
        self.minimum_dwell_days = _positive_int(
            payload.get("minimum_dwell_days", 7),
            label="minimum_dwell_days",
            allow_zero=True,
        )
        self.fallback_policy = str(payload.get("fallback_policy") or "mrp_reference")
        emergency = payload.get("emergency_regimes", ["CRISIS"])
        if not isinstance(emergency, list) or not all(str(item) in REGIMES for item in emergency):
            raise ControlProviderError("emergency_regimes must be a JSON list of known regimes.")
        self.emergency_regimes = tuple(str(item) for item in emergency)

        thresholds_raw = payload.get("thresholds", {})
        if not isinstance(thresholds_raw, Mapping):
            raise ControlProviderError("thresholds must be a JSON object.")
        unknown_thresholds = sorted(set(thresholds_raw) - set(DEFAULT_THRESHOLDS))
        if unknown_thresholds:
            raise ControlProviderError(
                "thresholds contain unknown fields: " + ", ".join(unknown_thresholds)
            )
        self.thresholds = {
            name: _finite_float(thresholds_raw.get(name, default), label=f"thresholds.{name}")
            for name, default in DEFAULT_THRESHOLDS.items()
        }

        dynamics_raw = payload.get("dynamics", {})
        if not isinstance(dynamics_raw, Mapping):
            raise ControlProviderError("dynamics must be a JSON object.")
        dynamics_defaults = {
            "stress_memory": 0.86,
            "nervousness_gain": 0.28,
            "pressure_gain": 0.42,
            "disruption_gain": 0.55,
            "capacity_pressure_start": 0.75,
            "recent_disruption_memory_days": 28.0,
            # Zero preserves the historical rule: every strictly positive
            # physical disruption score arms the recent-incident memory.
            "recent_disruption_score_floor": 0.0,
        }
        unknown_dynamics = sorted(set(dynamics_raw) - set(dynamics_defaults))
        if unknown_dynamics:
            raise ControlProviderError(
                "dynamics contain unknown fields: " + ", ".join(unknown_dynamics)
            )
        self.dynamics = {
            name: _finite_float(dynamics_raw.get(name, default), label=f"dynamics.{name}")
            for name, default in dynamics_defaults.items()
        }
        if not 0.0 <= self.dynamics["stress_memory"] <= 1.0:
            raise ControlProviderError("dynamics.stress_memory must be in [0, 1].")
        if not 0.0 <= self.dynamics["recent_disruption_score_floor"] <= 1.0:
            raise ControlProviderError(
                "dynamics.recent_disruption_score_floor must be in [0, 1]."
            )

        slew_raw = payload.get("slew_limits", {})
        if not isinstance(slew_raw, Mapping):
            raise ControlProviderError("slew_limits must be a JSON object.")
        unknown_slew = sorted(set(slew_raw) - set(ACTION_FIELDS))
        if unknown_slew:
            raise ControlProviderError(
                "slew_limits contain unknown actions: " + ", ".join(unknown_slew)
            )
        self.slew_limits: dict[str, float] = {}
        for name in ACTION_FIELDS:
            default = float(CONTROL_BOUNDS[name].upper) - float(CONTROL_BOUNDS[name].lower)
            value = _finite_float(slew_raw.get(name, default), label=f"slew_limits.{name}")
            if value < 0.0:
                raise ControlProviderError(f"slew_limits.{name} must be non-negative.")
            if CONTROL_BOUNDS[name].integer and not float(value).is_integer():
                raise ControlProviderError(f"slew_limits.{name} must be an integer number of days.")
            self.slew_limits[name] = value

        regime_policy_raw = payload.get("regime_policy")
        if not isinstance(regime_policy_raw, Mapping):
            raise ControlProviderError("regime_policy must be a JSON object.")
        missing_regimes = sorted(set(REGIMES) - set(regime_policy_raw))
        unknown_regimes = sorted(set(regime_policy_raw) - set(REGIMES))
        if missing_regimes or unknown_regimes:
            raise ControlProviderError(
                "regime_policy must define exactly the known regimes; "
                f"missing={missing_regimes}, unknown={unknown_regimes}."
            )
        self.regime_policy = {name: str(regime_policy_raw[name]) for name in REGIMES}

        playbooks_raw = payload.get("playbooks")
        if not isinstance(playbooks_raw, Mapping) or not playbooks_raw:
            raise ControlProviderError("playbooks must be a non-empty JSON object.")
        self._warnings: list[str] = []
        self.playbooks: dict[str, tuple[dict[str, Any], ...]] = {}
        for policy_name, raw_playbook in playbooks_raw.items():
            self.playbooks[str(policy_name)] = self._parse_playbook(
                str(policy_name), raw_playbook
            )
        referenced = {self.fallback_policy, *self.regime_policy.values()}
        missing_playbooks = sorted(referenced - set(self.playbooks))
        if missing_playbooks:
            raise ControlProviderError(
                "Missing referenced playbooks: " + ", ".join(missing_playbooks)
            )
        self._validate_scope_topology(referenced)
        self._validate_fallback_policy()

        self._rows_by_day: dict[int, tuple[ControlScheduleRow, ...]] = {}
        self._commands: list[ControlCommand] = []
        self._observation_rows: list[dict[str, Any]] = []
        self._decision_rows: list[dict[str, Any]] = []
        self._last_observed_day: int | None = None
        self._last_backlog_days = 0.0
        self._previous_order_nervousness = 0.0
        self._supplier_stress = 0.0
        self._last_disruption_day: int | None = None
        self._confirmed_regime = "NOMINAL"
        self._pending_regime = ""
        self._pending_count = 0
        self._selected_policy = self.fallback_policy
        self._last_switch_day = -10**9
        self._current_by_scope: dict[
            tuple[str, str, str, str], dict[str, ControlNumber]
        ] = {}
        self._next_source_line = 1_000_000

    @property
    def enabled(self) -> bool:
        return True

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    @property
    def rows(self) -> tuple[ControlScheduleRow, ...]:
        return tuple(
            row
            for day in sorted(self._rows_by_day)
            for row in self._rows_by_day[day]
        )

    @property
    def commands(self) -> tuple[ControlCommand, ...]:
        return tuple(self._commands)

    @property
    def observation_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(row) for row in self._observation_rows)

    @property
    def decision_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(row) for row in self._decision_rows)

    def _parse_playbook(self, name: str, raw: Any) -> tuple[dict[str, Any], ...]:
        if not isinstance(raw, Mapping):
            raise ControlProviderError(f"playbooks.{name} must be a JSON object.")
        raw_commands = raw.get("commands")
        if raw_commands is None and "actions" in raw:
            raw_commands = [{"scope": raw.get("scope", {}), "actions": raw.get("actions")}]
        if not isinstance(raw_commands, list) or not raw_commands:
            raise ControlProviderError(f"playbooks.{name}.commands must be a non-empty list.")
        parsed: list[dict[str, Any]] = []
        scope_keys: list[tuple[str, str, str, str]] = []
        for index, raw_command in enumerate(raw_commands):
            label = f"playbooks.{name}.commands[{index}]"
            if not isinstance(raw_command, Mapping):
                raise ControlProviderError(f"{label} must be a JSON object.")
            raw_scope = raw_command.get("scope", {})
            raw_actions = raw_command.get("actions", {})
            if not isinstance(raw_scope, Mapping) or not isinstance(raw_actions, Mapping):
                raise ControlProviderError(f"{label}.scope/actions must be JSON objects.")
            scope = _scope_dict(raw_scope, label=f"{label}.scope")
            unknown_actions = sorted(set(raw_actions) - set(ACTION_FIELDS))
            if unknown_actions:
                raise ControlProviderError(
                    f"{label}.actions contains unknown fields: {', '.join(unknown_actions)}."
                )
            actions: dict[str, ControlNumber] = {}
            for action_name, raw_value in raw_actions.items():
                value = _finite_float(raw_value, label=f"{label}.actions.{action_name}")
                if CONTROL_BOUNDS[action_name].integer and not value.is_integer():
                    raise ControlProviderError(
                        f"{label}.actions.{action_name} must be an integer number of days."
                    )
                requested: ControlNumber = int(value) if CONTROL_BOUNDS[action_name].integer else value
                bounded, status = CONTROL_BOUNDS[action_name].apply(requested)
                actions[action_name] = bounded
                if status != "none":
                    self._warnings.append(
                        f"{label}: {action_name} requested {requested}; effective={bounded} ({status})."
                    )
            if not actions:
                raise ControlProviderError(f"{label}.actions must define at least one lever.")
            scope_key = tuple(scope[field] for field in SCOPE_FIELDS)
            specificity = sum(bool(value) for value in scope_key)
            for prior in scope_keys:
                if prior == scope_key:
                    raise ControlProviderError(f"{label} duplicates an earlier command scope.")
                if sum(bool(value) for value in prior) == specificity and _compatible_scope_keys(prior, scope_key):
                    raise ControlProviderError(f"{label} ambiguously overlaps an earlier command scope.")
            scope_keys.append(scope_key)
            test_row = ControlScheduleRow(
                day=0,
                policy=name,
                **scope,
                requested=actions,
                effective=actions,
                bound={field: "none" for field in actions},
                source_line=index + 1,
            )
            try:
                if self.catalog is not None:
                    _validate_catalog(test_row, catalog=self.catalog)
                _validate_action_scope_compatibility(test_row, catalog=self.catalog)
            except ControlScheduleError as exc:
                raise ControlProviderError(f"Invalid {label}: {exc}") from exc
            parsed.append({"scope": scope, "actions": actions})
        return tuple(parsed)

    def resolve(
        self,
        day: int,
        node_id: str = "",
        supplier_id: str = "",
        item_id: str = "",
        dst_node_id: str = "",
    ) -> ResolvedControl:
        rows = (
            self._rows_by_day.get(day, ())
            if isinstance(day, int) and not isinstance(day, bool)
            else ()
        )
        schedule = ControlSchedule(rows=rows)
        return schedule.resolve(
            day,
            node_id=node_id,
            supplier_id=supplier_id,
            item_id=item_id,
            dst_node_id=dst_node_id,
        )

    def _normalize_observation(
        self, observation: CanonicalObservation
    ) -> tuple[dict[str, Any], str]:
        payload = asdict(observation)
        if isinstance(observation.day, bool) or not isinstance(observation.day, int) or observation.day < 0:
            return payload, "day must be a zero-based non-negative integer"
        if (
            isinstance(observation.active_supplier_event_count, bool)
            or not isinstance(observation.active_supplier_event_count, int)
            or observation.active_supplier_event_count < 0
        ):
            return payload, "active_supplier_event_count must be non-negative"
        if (
            isinstance(observation.active_order_pair_count, bool)
            or not isinstance(observation.active_order_pair_count, int)
            or observation.active_order_pair_count < 0
        ):
            return payload, "active_order_pair_count must be non-negative"
        optional = {"finished_inventory_cover_days", "material_cover_days"}
        for name, value in payload.items():
            if name in {
                "day",
                "active_order_pair_count",
                "active_supplier_event_count",
            } or (name in optional and value is None):
                continue
            if isinstance(value, bool):
                return payload, f"{name} must be numeric and not boolean"
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return payload, f"{name} is not numeric"
            if not math.isfinite(parsed):
                return payload, f"{name} is not finite"
            payload[name] = parsed
        if not 0.0 <= float(payload["service_level"]) <= 1.0:
            return payload, "service_level is outside [0, 1]"
        if not 0.0 <= float(payload["supplier_disruption_score"]) <= 1.0:
            return payload, "supplier_disruption_score is outside [0, 1]"
        for name in (
            "demand_qty",
            "served_qty",
            "backlog_qty",
            "backlog_days",
            "inventory_qty",
            "production_utilization",
            "supplier_utilization",
            "order_nervousness",
            "finished_inventory_cover_days",
            "material_cover_days",
        ):
            value = payload.get(name)
            if value is not None and float(value) < 0.0:
                return payload, f"{name} must be non-negative"
        return payload, ""

    def _classify(self, signals: Mapping[str, Any]) -> str:
        threshold = self.thresholds
        backlog_days = float(signals["backlog_days"])
        service = float(signals["service_level"])
        disruption = float(signals["supplier_disruption_score"])
        stress = float(signals["supplier_stress"])
        nervousness = float(signals["nervousness"])
        utilization = max(
            float(signals["production_utilization"]),
            float(signals["supplier_utilization"]),
        )
        if backlog_days >= threshold["crisis_backlog_days"] and (
            service < 0.95 or disruption >= threshold["crisis_disruption_floor"]
        ):
            return "CRISIS"
        if disruption >= threshold["supplier_disruption"] or stress >= threshold["supplier_stress"]:
            return "SUPPLIER_STRESS"
        if nervousness >= threshold["oscillation_nervousness"] and backlog_days > 0.05:
            return "OSCILLATORY"
        if utilization >= threshold["capacity_saturation"] and backlog_days > 0.02:
            return "CAPACITY_SATURATION"
        material_cover = signals.get("material_cover_days")
        if material_cover is not None and float(material_cover) <= threshold["material_tension_days"]:
            return "MATERIAL_TENSION"
        if self._last_backlog_days > backlog_days and backlog_days >= threshold["recovery_backlog_days"]:
            return "RECOVERY"
        finished_cover = signals.get("finished_inventory_cover_days")
        if (
            finished_cover is not None
            and float(finished_cover) >= threshold["overstock_days"]
            and backlog_days <= 0.02
            and float(signals["inventory_excess_ratio"]) >= 1.05
            and bool(signals["recent_disruption_signal"])
        ):
            return "POST_CRISIS_OVERSTOCK"
        return "NOMINAL"

    def _update_recent_disruption_memory(self, *, day: int, score: float) -> bool:
        """Arm incident memory only above the configured physical-score floor."""

        if score > self.dynamics["recent_disruption_score_floor"]:
            self._last_disruption_day = day
        return (
            self._last_disruption_day is not None
            and day - self._last_disruption_day
            <= int(self.dynamics["recent_disruption_memory_days"])
        )

    def _update_confirmed_regime(self, raw_regime: str) -> None:
        if raw_regime in self.emergency_regimes:
            self._confirmed_regime = raw_regime
            self._pending_regime = ""
            self._pending_count = 0
            return
        if raw_regime == self._confirmed_regime:
            self._pending_regime = ""
            self._pending_count = 0
            return
        if raw_regime == self._pending_regime:
            self._pending_count += 1
        else:
            self._pending_regime = raw_regime
            self._pending_count = 1
        if self._pending_count >= self.confirmation_days:
            self._confirmed_regime = raw_regime
            self._pending_regime = ""
            self._pending_count = 0

    def _target_by_scope(self, policy: str) -> dict[tuple[str, str, str, str], dict[str, ControlNumber]]:
        targets: dict[tuple[str, str, str, str], dict[str, ControlNumber]] = {}
        for command in self.playbooks[policy]:
            scope = command["scope"]
            scope_key = tuple(scope[field] for field in SCOPE_FIELDS)
            target = {
                field: CONTROL_BOUNDS[field].neutral
                for field in ACTION_FIELDS
            }
            target.update(command["actions"])
            targets[scope_key] = target
        return targets

    def _validate_scope_topology(self, referenced: set[str]) -> None:
        """Reject scope layouts that can break resolution or effective slew.

        Version 1 permits identical scopes, disjoint scopes, and a neutral
        general scope beneath a more-specific active scope.  A compatible
        general scope may not itself be active in any reachable playbook;
        otherwise inheritance could make the resolved action jump farther than
        the configured per-scope slew limit during a policy transition.
        """

        targets_by_policy = {
            policy: self._target_by_scope(policy)
            for policy in sorted(referenced)
        }
        scope_keys = sorted(
            {
                scope_key
                for targets in targets_by_policy.values()
                for scope_key in targets
            }
        )
        for left_index, left in enumerate(scope_keys):
            for right in scope_keys[left_index + 1 :]:
                if not _compatible_scope_keys(left, right):
                    continue
                left_specificity = sum(bool(value) for value in left)
                right_specificity = sum(bool(value) for value in right)
                if left_specificity == right_specificity:
                    raise ControlProviderError(
                        "Reachable playbooks contain compatible, equally specific "
                        f"scopes {left!r} and {right!r}; online resolution would be ambiguous."
                    )
                general = left if left_specificity < right_specificity else right
                for policy, targets in targets_by_policy.items():
                    general_target = targets.get(general)
                    if general_target is None:
                        continue
                    active = [
                        name
                        for name in ACTION_FIELDS
                        if abs(
                            float(general_target[name])
                            - float(CONTROL_BOUNDS[name].neutral)
                        )
                        > 1e-12
                    ]
                    if active:
                        raise ControlProviderError(
                            "A compatible general scope must remain neutral in all "
                            "reachable playbooks so resolved slew limits remain valid; "
                            f"policy={policy!r}, scope={general!r}, active={active}."
                        )

    def _validate_fallback_policy(self) -> None:
        active = [
            (scope_key, name)
            for scope_key, target in self._target_by_scope(
                self.fallback_policy
            ).items()
            for name in ACTION_FIELDS
            if abs(
                float(target[name]) - float(CONTROL_BOUNDS[name].neutral)
            )
            > 1e-12
        ]
        if active:
            raise ControlProviderError(
                "fallback_policy must be physically neutral; active scope/actions="
                f"{active}."
            )

    def _advance_commands(self, *, decision_day: int, effective_day: int) -> tuple[ControlCommand, ...]:
        targets = self._target_by_scope(self._selected_policy)
        scope_keys = sorted(set(self._current_by_scope) | set(targets))
        commands: list[ControlCommand] = []
        rows: list[ControlScheduleRow] = []
        next_state: dict[tuple[str, str, str, str], dict[str, ControlNumber]] = {}
        for scope_key in scope_keys:
            current = {
                name: CONTROL_BOUNDS[name].neutral
                for name in ACTION_FIELDS
            }
            current.update(self._current_by_scope.get(scope_key, {}))
            target = {
                name: CONTROL_BOUNDS[name].neutral
                for name in ACTION_FIELDS
            }
            target.update(targets.get(scope_key, {}))
            effective_full: dict[str, ControlNumber] = {}
            slew_limited: list[str] = []
            for name in ACTION_FIELDS:
                current_value = float(current[name])
                target_value = float(target[name])
                limit = float(self.slew_limits[name])
                delta = target_value - current_value
                if abs(delta) > limit + 1e-12:
                    value = current_value + math.copysign(limit, delta)
                    slew_limited.append(name)
                else:
                    value = target_value
                bounded, _ = CONTROL_BOUNDS[name].apply(value)
                if CONTROL_BOUNDS[name].integer:
                    bounded = int(round(float(bounded)))
                effective_full[name] = bounded
            active_names = [
                name
                for name in ACTION_FIELDS
                if abs(float(effective_full[name]) - float(CONTROL_BOUNDS[name].neutral)) > 1e-12
            ]
            requested_names = [
                name
                for name in ACTION_FIELDS
                if abs(float(target[name]) - float(CONTROL_BOUNDS[name].neutral))
                > 1e-12
            ]
            audited_names = sorted(
                set(active_names) | set(requested_names) | set(slew_limited),
                key=ACTION_FIELDS.index,
            )
            source_line: int | None = None
            if active_names:
                source_line = self._next_source_line
                self._next_source_line += 1
            scope = dict(zip(SCOPE_FIELDS, scope_key))
            command = ControlCommand(
                decision_day=decision_day,
                effective_day=effective_day,
                policy=self._selected_policy,
                **scope,
                requested={name: target[name] for name in audited_names},
                effective={name: effective_full[name] for name in audited_names},
                slew_limited_actions=tuple(
                    name for name in slew_limited if name in audited_names
                ),
                source_line=source_line,
            )
            commands.append(command)
            row = command.to_schedule_row()
            if row is not None:
                rows.append(row)
            if active_names or scope_key in targets:
                next_state[scope_key] = effective_full
        try:
            _validate_row_relationships(rows)
        except ControlScheduleError as exc:
            raise ControlProviderError(f"Generated ambiguous feedback commands: {exc}") from exc
        self._current_by_scope = next_state
        self._rows_by_day[effective_day] = tuple(rows)
        self._commands.extend(commands)
        return tuple(commands)

    def observe(
        self,
        observation: CanonicalObservation,
        last_effective_day: int | None = None,
    ) -> tuple[ControlCommand, ...]:
        """Observe realized end-of-day state and generate only J+1 commands."""

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
        raw, invalid_reason = self._normalize_observation(observation)
        previous_backlog_days = self._last_backlog_days
        previous_order_nervousness = self._previous_order_nervousness
        if invalid_reason:
            nervousness = 0.0
            supplier_stress = self._supplier_stress
            recent_disruption = False
            raw_regime = "INVALID_OBSERVATION"
            fallback_applied = True
            previous_policy = self._selected_policy
            self._selected_policy = self.fallback_policy
            self._confirmed_regime = "NOMINAL"
            self._pending_regime = ""
            self._pending_count = 0
            review_due = True
            switch_reason = f"fallback_invalid_observation:{invalid_reason}"
            if previous_policy != self._selected_policy:
                self._last_switch_day = day
            # Safety fallback is immediate: do not retain a stale external action.
            self._current_by_scope = {}
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
            review_due = day % self.review_period_days == 0
            emergency_review = raw_regime in self.emergency_regimes
            fallback_applied = False
            previous_policy = self._selected_policy
            switch_reason = "hold_between_reviews"
            if review_due or emergency_review:
                candidate = self.regime_policy[self._confirmed_regime]
                dwell_elapsed = day - self._last_switch_day
                if candidate == self._selected_policy:
                    switch_reason = "review_keep_policy"
                elif emergency_review or dwell_elapsed >= self.minimum_dwell_days:
                    self._selected_policy = candidate
                    self._last_switch_day = day
                    switch_reason = (
                        "emergency_regime_switch" if emergency_review else "scheduled_regime_switch"
                    )
                else:
                    switch_reason = "minimum_dwell_hold"

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
        self._observation_rows.append(_json_safe(normalized))

        effective_day = day + 1
        commands: tuple[ControlCommand, ...] = ()
        if last_effective_day is None or effective_day <= int(last_effective_day):
            commands = self._advance_commands(
                decision_day=day,
                effective_day=effective_day,
            )
        active_rows = sum(command.active for command in commands)
        slew_actions = sorted(
            {
                name
                for command in commands
                for name in command.slew_limited_actions
            }
        )
        decision = {
            "decision_day": day,
            "effective_day": effective_day,
            "causal_lag_days": 1,
            "observation_hash": observation_hash,
            "observation_valid": int(not invalid_reason),
            "invalid_reason": invalid_reason,
            "raw_regime": raw_regime,
            "confirmed_regime": self._confirmed_regime,
            "pending_regime": self._pending_regime,
            "pending_count": self._pending_count,
            "review_due": int(review_due),
            "previous_policy": previous_policy,
            "selected_policy": self._selected_policy,
            "policy_switched": int(previous_policy != self._selected_policy),
            "switch_reason": switch_reason,
            "fallback_applied": int(fallback_applied),
            "generated_command_count": len(commands),
            "active_command_row_count": active_rows,
            "slew_limited_actions": ";".join(slew_actions),
        }
        self._decision_rows.append(decision)
        self._last_observed_day = day
        if not invalid_reason:
            self._last_backlog_days = float(raw["backlog_days"])
            self._previous_order_nervousness = nervousness
            self._supplier_stress = supplier_stress
        return commands

    def audit_metadata_for_day(self, day: int) -> dict[str, Any]:
        for decision in reversed(self._decision_rows):
            if int(decision["effective_day"]) == int(day):
                return {
                    "control_mode": self.mode,
                    "control_source_kind": "state_feedback_generated_online",
                    **decision,
                }
        return {
            "control_mode": self.mode,
            "control_source_kind": "state_feedback_no_prior_observation",
            "effective_day": int(day),
        }

    def summary_metadata(self) -> dict[str, Any]:
        causal = all(
            int(row["effective_day"]) == int(row["decision_day"]) + 1
            for row in self._decision_rows
        )
        causal_contract_satisfied = bool(self._observation_rows and causal)
        return {
            "enabled": True,
            "mode": self.mode,
            "integration_mode": self.mode,
            "causal_contract_satisfied": causal_contract_satisfied,
            "closed_loop_claimed": bool(
                causal_contract_satisfied and self.rows
            ),
            "causal_lag_days": 1,
            "config_path": str(self.config_path),
            "config_sha256": self.config_sha256,
            "schema_version": self.schema_version,
            "policy_name": self.name,
            "observation_count": len(self._observation_rows),
            "decision_count": len(self._decision_rows),
            "generated_command_count": len(self._commands),
            "active_command_row_count": len(self.rows),
            "policy_switch_count": sum(
                int(row["policy_switched"]) for row in self._decision_rows
            ),
            "fallback_count": sum(
                int(row["fallback_applied"]) for row in self._decision_rows
            ),
            "review_period_days": self.review_period_days,
            "confirmation_days": self.confirmation_days,
            "minimum_dwell_days": self.minimum_dwell_days,
            "final_regime": self._confirmed_regime,
            "final_policy": self._selected_policy,
            "supplier_disruption_signal_semantics": (
                "bounded_physical_severity_proxy_not_incident_probability"
            ),
            "order_nervousness_semantics": (
                "median_pairwise_relative_change_no_cross_uom_aggregation"
            ),
            "scope_topology_contract": (
                "no_compatible_active_general_scopes_or_equal_specificity_ambiguity"
            ),
            "direct_future_realization_access": False,
            "controller_observation_forecast_lookahead_days": 0,
            "future_realization_access": False,
            "warnings": list(self.warnings),
        }


def load_state_feedback_control_provider(
    path: Path | str,
    *,
    catalog: ControlCatalog | None = None,
) -> StateFeedbackControlProvider:
    """Load and validate one declarative causal feedback policy JSON."""

    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ControlProviderError(
            f"Control policy does not exist or is not a file: {config_path}"
        )
    try:
        raw_bytes = config_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ControlProviderError(f"Cannot read control policy {config_path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ControlProviderError("Control policy JSON root must be an object.")
    return StateFeedbackControlProvider(
        payload,
        config_path=config_path,
        config_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        catalog=catalog,
    )


__all__ = [
    "CanonicalObservation",
    "ControlCommand",
    "ControlProvider",
    "ControlProviderError",
    "REGIMES",
    "StateFeedbackControlProvider",
    "load_state_feedback_control_provider",
]
