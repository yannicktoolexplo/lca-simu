"""Additive V3 provider with continuous supplier-relief feedback.

V2 remains unchanged and continues to own warm-up priming, regime selection,
safety gates and the causal J-to-J+1 command contract.  V3 adds one optional,
bounded proportional law inside a configured supervisory regime.  A V3 policy
must be selected explicitly through its own loader and engine flag.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .control_provider import (
    CanonicalObservation,
    ControlCommand,
    ControlProviderError,
    REGIMES,
)
from .control_provider_v2 import (
    SCHEMA_VERSION_V2,
    StateFeedbackControlProviderV2,
)
from .control_schedule import (
    CONTROL_BOUNDS,
    ControlCatalog,
    ControlNumber,
)


SCHEMA_VERSION_V3 = "scan.canonical_state_feedback.v3"
CONTINUOUS_RELIEF_ACTIONS = (
    "order_multiplier",
    "production_target_multiplier",
)
_CONTINUOUS_RELIEF_KEYS = {
    "enabled",
    "active_regime",
    "active_policy",
    "stress_start",
    "stress_span",
    "order_relief_gain",
    "production_relief_gain",
    "minimum_order_multiplier",
    "minimum_production_target_multiplier",
    "backlog_guard_days",
    "service_guard_level",
    "finished_cover_guard_days",
    "material_cover_guard_days",
    "maximum_relief_step_per_day",
}


def _finite_number(
    value: Any,
    *,
    label: str,
    lower: float,
    upper: float,
    lower_inclusive: bool = True,
) -> float:
    if isinstance(value, bool):
        raise ControlProviderError(f"{label} must be numeric and not boolean.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ControlProviderError(f"{label} must be numeric, got {value!r}.") from exc
    if not math.isfinite(parsed):
        raise ControlProviderError(f"{label} must be finite, got {value!r}.")
    below = parsed < lower if lower_inclusive else parsed <= lower
    if below or parsed > upper:
        left = "[" if lower_inclusive else "]"
        raise ControlProviderError(
            f"{label} must be in {left}{lower}, {upper}], got {parsed}."
        )
    return parsed


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


class StateFeedbackControlProviderV3(StateFeedbackControlProviderV2):
    """V2 supervisor plus a weak continuous supplier-relief correction."""

    mode = "canonical_state_feedback_v3_continuous_t_plus_1"

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
        if str(payload.get("schema_version") or "") != SCHEMA_VERSION_V3:
            raise ControlProviderError(
                "control policy V3 schema_version must be "
                f"'{SCHEMA_VERSION_V3}'."
            )

        # V2 construction calls the virtual target method while validating the
        # playbook topology.  Keep the V3 layer inert until V2 is fully ready.
        self._continuous_enabled = False
        self._continuous_spec: dict[str, Any] = {}
        self._continuous_context: dict[str, Any] = {}
        self._continuous_audit_current: dict[str, Any] = {}
        self._continuous_audit_by_effective_day: dict[int, dict[str, Any]] = {}

        compatibility_payload = dict(payload)
        compatibility_payload["schema_version"] = SCHEMA_VERSION_V2
        super().__init__(
            compatibility_payload,
            config_path=config_path,
            config_sha256=config_sha256,
            catalog=catalog,
        )
        self.schema_version = SCHEMA_VERSION_V3
        self._continuous_spec = self._parse_continuous_relief(
            payload.get("continuous_relief")
        )
        self._continuous_enabled = bool(self._continuous_spec["enabled"])

    def _parse_continuous_relief(self, raw: Any) -> dict[str, Any]:
        label = "continuous_relief"
        if not isinstance(raw, Mapping):
            raise ControlProviderError(f"{label} must be a JSON object.")
        missing = sorted(_CONTINUOUS_RELIEF_KEYS - set(raw))
        unknown = sorted(set(raw) - _CONTINUOUS_RELIEF_KEYS)
        if missing or unknown:
            details: list[str] = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if unknown:
                details.append("unknown=" + ",".join(unknown))
            raise ControlProviderError(
                f"{label} keys are not exact ({'; '.join(details)})."
            )
        enabled = raw["enabled"]
        if not isinstance(enabled, bool):
            raise ControlProviderError(f"{label}.enabled must be boolean.")
        active_regime = str(raw["active_regime"] or "").strip()
        if active_regime not in REGIMES:
            raise ControlProviderError(
                f"{label}.active_regime must be a known supervisory regime."
            )
        active_policy = str(raw["active_policy"] or "").strip()
        if active_policy not in self.playbooks:
            raise ControlProviderError(
                f"{label}.active_policy must name an existing playbook."
            )

        parsed = {
            "enabled": enabled,
            "active_regime": active_regime,
            "active_policy": active_policy,
            "stress_start": _finite_number(
                raw["stress_start"], label=f"{label}.stress_start", lower=0.0, upper=2.0
            ),
            "stress_span": _finite_number(
                raw["stress_span"],
                label=f"{label}.stress_span",
                lower=0.0,
                upper=2.0,
                lower_inclusive=False,
            ),
            "order_relief_gain": _finite_number(
                raw["order_relief_gain"],
                label=f"{label}.order_relief_gain",
                lower=0.0,
                upper=0.50,
            ),
            "production_relief_gain": _finite_number(
                raw["production_relief_gain"],
                label=f"{label}.production_relief_gain",
                lower=0.0,
                upper=0.50,
            ),
            "minimum_order_multiplier": _finite_number(
                raw["minimum_order_multiplier"],
                label=f"{label}.minimum_order_multiplier",
                lower=float(CONTROL_BOUNDS["order_multiplier"].lower),
                upper=1.0,
            ),
            "minimum_production_target_multiplier": _finite_number(
                raw["minimum_production_target_multiplier"],
                label=f"{label}.minimum_production_target_multiplier",
                lower=float(CONTROL_BOUNDS["production_target_multiplier"].lower),
                upper=1.0,
            ),
            "backlog_guard_days": _finite_number(
                raw["backlog_guard_days"],
                label=f"{label}.backlog_guard_days",
                lower=0.0,
                upper=365.0,
                lower_inclusive=False,
            ),
            "service_guard_level": _finite_number(
                raw["service_guard_level"],
                label=f"{label}.service_guard_level",
                lower=0.0,
                upper=1.0,
            ),
            "finished_cover_guard_days": _finite_number(
                raw["finished_cover_guard_days"],
                label=f"{label}.finished_cover_guard_days",
                lower=0.0,
                upper=365.0,
            ),
            "material_cover_guard_days": _finite_number(
                raw["material_cover_guard_days"],
                label=f"{label}.material_cover_guard_days",
                lower=0.0,
                upper=365.0,
            ),
            "maximum_relief_step_per_day": _finite_number(
                raw["maximum_relief_step_per_day"],
                label=f"{label}.maximum_relief_step_per_day",
                lower=0.0,
                upper=1.0,
                lower_inclusive=False,
            ),
        }
        if parsed["service_guard_level"] >= 1.0:
            raise ControlProviderError(
                f"{label}.service_guard_level must be strictly below 1.0."
            )
        return parsed

    def _prepare_continuous_context(
        self,
        observation: CanonicalObservation,
    ) -> None:
        raw, invalid_reason = super()._normalize_observation(observation)
        if invalid_reason:
            self._continuous_context = {
                "observation_valid": False,
                "invalid_reason": invalid_reason,
            }
            return
        nervousness = float(raw["order_nervousness"])
        pressure = max(
            0.0,
            float(raw["supplier_utilization"])
            - self.dynamics["capacity_pressure_start"],
        )
        projected_stress = _clip(
            self.dynamics["stress_memory"] * self._supplier_stress
            + self.dynamics["nervousness_gain"] * min(2.0, nervousness)
            + self.dynamics["pressure_gain"] * pressure
            + self.dynamics["disruption_gain"]
            * float(raw["supplier_disruption_score"]),
            0.0,
            2.0,
        )
        self._continuous_context = {
            **raw,
            "observation_valid": True,
            "projected_supplier_stress": projected_stress,
        }

    def _continuous_factors(self) -> tuple[float, float]:
        spec = self._continuous_spec
        context = self._continuous_context
        stress = float(context["projected_supplier_stress"])
        relief = _clip(
            (stress - float(spec["stress_start"])) / float(spec["stress_span"]),
            0.0,
            1.0,
        )
        backlog_guard = _clip(
            float(context["backlog_days"]) / float(spec["backlog_guard_days"]),
            0.0,
            1.0,
        )
        service_shortfall = max(0.0, 1.0 - float(context["service_level"]))
        service_guard = _clip(
            service_shortfall / (1.0 - float(spec["service_guard_level"])),
            0.0,
            1.0,
        )
        finished_cover = context.get("finished_inventory_cover_days")
        finished_guard = float(
            finished_cover is not None
            and float(finished_cover) <= float(spec["finished_cover_guard_days"])
        )
        material_cover = context.get("material_cover_days")
        material_guard = float(
            material_cover is not None
            and float(material_cover) <= float(spec["material_cover_guard_days"])
        )
        protection = max(
            backlog_guard,
            service_guard,
            finished_guard,
            material_guard,
        )
        return relief, protection

    def _target_by_scope(
        self, policy: str
    ) -> dict[tuple[str, str, str, str], dict[str, ControlNumber]]:
        targets = super()._target_by_scope(policy)
        if not self._continuous_enabled:
            return targets
        context_valid = bool(self._continuous_context.get("observation_valid"))
        active = bool(
            self._continuous_enabled
            and context_valid
            and self._confirmed_regime == self._continuous_spec.get("active_regime")
            and policy == self._continuous_spec.get("active_policy")
        )
        audit: dict[str, Any] = {
            "control_continuous_relief_enabled": int(self._continuous_enabled),
            "control_continuous_relief_active": int(active),
            "control_continuous_relief_observation_valid": int(context_valid),
            "control_continuous_relief_regime": self._confirmed_regime,
            "control_continuous_relief_policy": policy,
            "control_continuous_relief_supplier_stress": self._continuous_context.get(
                "projected_supplier_stress", ""
            ),
            "control_continuous_relief_intensity": 0.0,
            "control_continuous_service_protection": 0.0,
            "control_continuous_requested_order_multiplier": "",
            "control_continuous_requested_production_target_multiplier": "",
            "control_continuous_daily_step_limited": 0,
            "control_continuous_safety_return_to_neutral": 0,
        }
        if not active:
            self._continuous_audit_current = audit
            return targets

        relief, protection = self._continuous_factors()
        spec = self._continuous_spec
        requested = {
            "order_multiplier": _clip(
                1.0
                - float(spec["order_relief_gain"])
                * relief
                * (1.0 - protection),
                float(spec["minimum_order_multiplier"]),
                1.0,
            ),
            "production_target_multiplier": _clip(
                1.0
                - float(spec["production_relief_gain"])
                * relief
                * (1.0 - protection),
                float(spec["minimum_production_target_multiplier"]),
                1.0,
            ),
        }
        daily_step_limited = False
        safety_return = protection >= 1.0 - 1e-12
        for scope_key, target in targets.items():
            current = self._current_by_scope.get(scope_key, {})
            for action_name in CONTINUOUS_RELIEF_ACTIONS:
                current_value = float(
                    current.get(action_name, CONTROL_BOUNDS[action_name].neutral)
                )
                value = float(requested[action_name])
                if safety_return:
                    # A service/material guard cancels relief on J+1 instead of
                    # trailing a deliberately conservative downward slew.
                    if scope_key in self._current_by_scope:
                        self._current_by_scope[scope_key][action_name] = 1.0
                    value = 1.0
                elif value < current_value:
                    limited = max(
                        value,
                        current_value
                        - float(spec["maximum_relief_step_per_day"]),
                    )
                    daily_step_limited = daily_step_limited or not math.isclose(
                        limited, value, rel_tol=0.0, abs_tol=1e-12
                    )
                    value = limited
                target[action_name] = value
                if self._action_is_blocked(action_name, value):
                    target[action_name] = CONTROL_BOUNDS[action_name].neutral
                    if self._gate_evaluation_active:
                        self._forced_neutral_actions_current.add(action_name)

        audit.update(
            {
                "control_continuous_relief_intensity": relief,
                "control_continuous_service_protection": protection,
                "control_continuous_requested_order_multiplier": requested[
                    "order_multiplier"
                ],
                "control_continuous_requested_production_target_multiplier": requested[
                    "production_target_multiplier"
                ],
                "control_continuous_daily_step_limited": int(daily_step_limited),
                "control_continuous_safety_return_to_neutral": int(safety_return),
            }
        )
        self._continuous_audit_current = audit
        return targets

    def observe(
        self,
        observation: CanonicalObservation,
        last_effective_day: int | None = None,
    ) -> tuple[ControlCommand, ...]:
        """Prepare the continuous J state, then delegate causal output to V2."""

        self._prepare_continuous_context(observation)
        self._continuous_audit_current = {}
        commands = super().observe(
            observation,
            last_effective_day=last_effective_day,
        )
        decision = self._decision_rows[-1]
        audit = dict(self._continuous_audit_current)
        if not audit:
            audit = {
                "control_continuous_relief_enabled": int(self._continuous_enabled),
                "control_continuous_relief_active": 0,
                "control_continuous_relief_observation_valid": int(
                    bool(self._continuous_context.get("observation_valid"))
                ),
            }
        decision.update(audit)
        self._continuous_audit_by_effective_day[int(decision["effective_day"])] = audit
        return commands

    def command_audit_metadata_for_day(self, day: int) -> dict[str, Any]:
        """Return V2 gate fields plus V3 continuous-relief evidence."""

        continuous = self._continuous_audit_by_effective_day.get(int(day))
        if continuous is None:
            continuous = {
                "control_continuous_relief_enabled": int(self._continuous_enabled),
                "control_continuous_relief_active": 0,
                "control_continuous_relief_observation_valid": 0,
            }
        return {
            **super().command_audit_metadata_for_day(day),
            **continuous,
        }

    def summary_metadata(self) -> dict[str, Any]:
        """Return V2 evidence plus V3 configuration and activity counts."""

        metadata = super().summary_metadata()
        metadata.update(
            {
                "schema_version": SCHEMA_VERSION_V3,
                "mode": self.mode,
                "integration_mode": self.mode,
                "continuous_relief_enabled": self._continuous_enabled,
                "continuous_relief_active_regime": self._continuous_spec[
                    "active_regime"
                ],
                "continuous_relief_active_policy": self._continuous_spec[
                    "active_policy"
                ],
                "continuous_relief_decision_count": sum(
                    int(row.get("control_continuous_relief_active", 0))
                    for row in self._decision_rows
                ),
                "continuous_relief_safety_return_count": sum(
                    int(row.get("control_continuous_safety_return_to_neutral", 0))
                    for row in self._decision_rows
                ),
                "continuous_relief_integral_action": False,
                "continuous_relief_future_information_access": False,
            }
        )
        return metadata


def load_state_feedback_control_provider_v3(
    path: Path | str,
    *,
    catalog: ControlCatalog | None = None,
) -> StateFeedbackControlProviderV3:
    """Load and validate one explicit V3 continuous-feedback policy."""

    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ControlProviderError(
            f"Control policy V3 does not exist or is not a file: {config_path}"
        )
    try:
        raw_bytes = config_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ControlProviderError(
            f"Cannot read control policy V3 {config_path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ControlProviderError("Control policy V3 JSON root must be an object.")
    return StateFeedbackControlProviderV3(
        payload,
        config_path=config_path,
        config_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        catalog=catalog,
    )


__all__ = [
    "CONTINUOUS_RELIEF_ACTIONS",
    "SCHEMA_VERSION_V3",
    "StateFeedbackControlProviderV3",
    "load_state_feedback_control_provider_v3",
]
