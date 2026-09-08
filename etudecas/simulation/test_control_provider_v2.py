from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from etudecas.simulation.engine.control_provider import (
    CanonicalObservation,
    ControlProviderError,
    REGIMES,
    load_state_feedback_control_provider,
)
from etudecas.simulation.engine.control_provider_v2 import (
    EXCEPTIONAL_COST_GATE,
    SCHEMA_VERSION_V2,
    SERVICE_RECOVERY_GATE,
    StateFeedbackControlProviderV2,
    load_state_feedback_control_provider_v2,
)
from etudecas.simulation.engine.control_schedule import (
    ACTION_FIELDS,
    CONTROL_BOUNDS,
)


NEUTRAL = {name: spec.neutral for name, spec in CONTROL_BOUNDS.items()}
PROTECTION = {
    "order_multiplier": 1.20,
    "safety_stock_multiplier": 1.20,
    "production_target_multiplier": 1.20,
    "external_procurement_multiplier": 1.20,
    "expedite_level": 0.20,
}


def _observation(day: int, **overrides: Any) -> CanonicalObservation:
    values: dict[str, Any] = {
        "day": day,
        "demand_qty": 100.0,
        "served_qty": 100.0,
        "service_level": 1.0,
        "backlog_qty": 0.0,
        "backlog_days": 0.0,
        "inventory_qty": 400.0,
        "finished_inventory_cover_days": 1.2,
        "material_cover_days": 3.0,
        "production_utilization": 0.50,
        "supplier_utilization": 0.50,
        "order_nervousness": 0.0,
        "active_order_pair_count": 1,
        "supplier_disruption_score": 0.0,
        "active_supplier_event_count": 0,
    }
    values.update(overrides)
    return CanonicalObservation(**values)


def _stress(day: int, **overrides: Any) -> CanonicalObservation:
    return _observation(
        day,
        supplier_disruption_score=0.40,
        active_supplier_event_count=1,
        **overrides,
    )


def _playbook(actions: Mapping[str, float | int]) -> dict[str, Any]:
    return {"commands": [{"scope": {}, "actions": dict(actions)}]}


def _payload(
    *,
    review_period_days: int = 1,
    slew_limits: Mapping[str, float | int] | None = None,
) -> dict[str, Any]:
    regime_policy = {regime: "reference" for regime in REGIMES}
    for regime in (
        "MATERIAL_TENSION",
        "CAPACITY_SATURATION",
        "SUPPLIER_STRESS",
        "OSCILLATORY",
        "CRISIS",
    ):
        regime_policy[regime] = "protection"
    return {
        "schema_version": SCHEMA_VERSION_V2,
        "name": "pytest_state_feedback_v2",
        "review_period_days": review_period_days,
        "confirmation_days": 1,
        "minimum_dwell_days": 0,
        "fallback_policy": "reference",
        "emergency_regimes": ["CRISIS"],
        "dynamics": {
            "stress_memory": 0.0,
            "nervousness_gain": 0.0,
            "pressure_gain": 0.0,
            "disruption_gain": 0.0,
            "capacity_pressure_start": 0.75,
            "recent_disruption_memory_days": 28.0,
        },
        "slew_limits": dict(slew_limits)
        if slew_limits is not None
        else {
            name: float(spec.upper) - float(spec.lower)
            for name, spec in CONTROL_BOUNDS.items()
        },
        "regime_policy": regime_policy,
        "playbooks": {
            "reference": _playbook(NEUTRAL),
            "protection": _playbook(PROTECTION),
        },
        "gates": {
            SERVICE_RECOVERY_GATE: {
                "require_any": [
                    {
                        "signal": "backlog_days",
                        "operator": "ge",
                        "threshold": 0.10,
                    },
                    {
                        "signal": "service_level",
                        "operator": "le",
                        "threshold": 0.99,
                    },
                ]
            },
            EXCEPTIONAL_COST_GATE: {
                "require_any": [
                    {
                        "signal": "backlog_days",
                        "operator": "ge",
                        "threshold": 0.50,
                    },
                    {
                        "signal": "service_level",
                        "operator": "le",
                        "threshold": 0.97,
                    },
                ]
            },
        },
        "action_gate_map": {
            "order_multiplier": {
                "gate": SERVICE_RECOVERY_GATE,
                "direction": "above_neutral",
            },
            "safety_stock_multiplier": {
                "gate": SERVICE_RECOVERY_GATE,
                "direction": "above_neutral",
            },
            "production_target_multiplier": {
                "gate": SERVICE_RECOVERY_GATE,
                "direction": "above_neutral",
            },
            "external_procurement_multiplier": {
                "gate": EXCEPTIONAL_COST_GATE,
                "direction": "above_neutral",
            },
            "expedite_level": {
                "gate": EXCEPTIONAL_COST_GATE,
                "direction": "above_neutral",
            },
        },
    }


def _write_policy(
    tmp_path: Path,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Path:
    path = tmp_path / "closed_loop_policy_v2.json"
    path.write_text(json.dumps(payload or _payload(), indent=2), encoding="utf-8")
    return path


def _resolved_values(provider: StateFeedbackControlProviderV2, day: int) -> dict[str, Any]:
    resolved = provider.resolve(day)
    return {name: getattr(resolved, name) for name in ACTION_FIELDS}


def test_v2_loader_is_additive_and_schema_strict(tmp_path: Path) -> None:
    path = _write_policy(tmp_path)
    provider = load_state_feedback_control_provider_v2(path)

    assert isinstance(provider, StateFeedbackControlProviderV2)
    assert provider.schema_version == SCHEMA_VERSION_V2
    assert provider.mode == "canonical_state_feedback_v2_t_plus_1"
    with pytest.raises(ControlProviderError, match="scan.canonical_state_feedback.v1"):
        load_state_feedback_control_provider(path)

    v1_payload = _payload()
    v1_payload["schema_version"] = "scan.canonical_state_feedback.v1"
    with pytest.raises(ControlProviderError, match="V2 schema_version"):
        load_state_feedback_control_provider_v2(
            _write_policy(tmp_path, payload=v1_payload)
        )


def test_priming_updates_memory_without_measured_rows_or_actions(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider_v2(_write_policy(tmp_path))

    assert provider.prime(_stress(-2)) == ()
    assert provider.prime(_stress(-1)) == ()

    assert [row["day"] for row in provider.priming_rows] == [-2, -1]
    assert all(row["generated_command_count"] == 0 for row in provider.priming_rows)
    assert provider.observation_rows == ()
    assert provider.decision_rows == ()
    assert provider.commands == ()
    assert provider.rows == ()
    assert provider.warmup_action_count == 0
    metadata = provider.summary_metadata()
    assert metadata["controller_dynamic_warmup_days"] == 2
    assert metadata["controller_priming_complete_at_day_minus_one"] is True
    assert metadata["warmup_commands_disabled"] is True
    assert metadata["controller_priming_final_regime"] == "SUPPLIER_STRESS"

    commands = provider.observe(
        _stress(0, backlog_days=0.20, backlog_qty=20.0, service_level=0.98),
        last_effective_day=2,
    )
    assert commands
    assert commands[0].decision_day == 0
    assert commands[0].effective_day == 1
    assert len(provider.observation_rows) == 1
    assert len(provider.decision_rows) == 1


def test_v2_priming_uses_the_same_recent_disruption_floor_and_memory(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["dynamics"].update(
        {
            "recent_disruption_score_floor": 0.30,
            "recent_disruption_memory_days": 21.0,
        }
    )
    provider = load_state_feedback_control_provider_v2(
        _write_policy(tmp_path, payload=payload)
    )

    provider.prime(_observation(-24, supplier_disruption_score=0.29))
    provider.prime(_observation(-23, supplier_disruption_score=0.31))
    for day in range(-22, 0):
        provider.prime(_observation(day))

    signals = {
        int(row["day"]): int(row["recent_disruption_signal"])
        for row in provider.priming_rows
    }
    assert signals[-24] == 0
    assert signals[-23] == 1
    assert signals[-2] == 1
    assert signals[-1] == 0


def test_priming_requires_negative_sequential_days_and_day_zero_boundary(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider_v2(_write_policy(tmp_path))
    with pytest.raises(ControlProviderError, match="negative integer"):
        provider.prime(_observation(0))
    provider.prime(_observation(-3))
    with pytest.raises(ControlProviderError, match="strictly sequential"):
        provider.prime(_observation(-1))
    provider.prime(_observation(-2))
    with pytest.raises(ControlProviderError, match="end warm-up at day -1"):
        provider.observe(_observation(0))


def test_closed_service_gate_blocks_positive_recovery_actions(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider_v2(_write_policy(tmp_path))

    provider.observe(_stress(0), last_effective_day=2)

    assert _resolved_values(provider, 1) == NEUTRAL
    audit = provider.command_audit_metadata_for_day(1)
    assert audit["control_open_gate_ids"] == ""
    assert audit["control_gate_forced_neutral"] == 1
    forced = set(audit["control_gate_forced_neutral_actions"].split(";"))
    assert set(PROTECTION) <= forced
    assert audit["control_gate_observation_hash"] == provider.decision_rows[0][
        "observation_hash"
    ]


def test_service_gate_can_open_without_opening_exceptional_cost_gate(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider_v2(_write_policy(tmp_path))

    provider.observe(
        _stress(
            0,
            backlog_days=0.20,
            backlog_qty=20.0,
            served_qty=98.0,
            service_level=0.98,
        ),
        last_effective_day=2,
    )

    values = _resolved_values(provider, 1)
    assert values["order_multiplier"] == pytest.approx(1.20)
    assert values["safety_stock_multiplier"] == pytest.approx(1.20)
    assert values["production_target_multiplier"] == pytest.approx(1.20)
    assert values["external_procurement_multiplier"] == pytest.approx(1.0)
    assert values["expedite_level"] == pytest.approx(0.0)
    audit = provider.command_audit_metadata_for_day(1)
    assert audit["control_open_gate_ids"] == SERVICE_RECOVERY_GATE
    assert EXCEPTIONAL_COST_GATE in audit["control_closed_gate_ids"]


def test_gate_closure_forces_neutral_immediately_despite_slew(
    tmp_path: Path,
) -> None:
    slew_limits = {
        name: float(spec.upper) - float(spec.lower)
        for name, spec in CONTROL_BOUNDS.items()
    }
    for action in PROTECTION:
        slew_limits[action] = 0.01
    provider = load_state_feedback_control_provider_v2(
        _write_policy(
            tmp_path,
            payload=_payload(
                review_period_days=10,
                slew_limits=slew_limits,
            ),
        )
    )

    provider.observe(
        _stress(
            0,
            backlog_days=0.60,
            backlog_qty=60.0,
            served_qty=96.0,
            service_level=0.96,
        ),
        last_effective_day=3,
    )
    assert provider.resolve(1).order_multiplier == pytest.approx(1.01)
    provider.observe(_stress(1), last_effective_day=3)

    assert _resolved_values(provider, 2) == NEUTRAL
    audit = provider.command_audit_metadata_for_day(2)
    assert audit["control_gate_forced_neutral"] == 1
    assert "order_multiplier" in audit["control_gate_forced_neutral_actions"]
    assert provider.decision_rows[1]["selected_policy"] == "protection"


def test_invalid_observation_closes_every_gate_and_links_audit_hash(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider_v2(_write_policy(tmp_path))
    provider.observe(
        _stress(
            0,
            backlog_days=0.60,
            backlog_qty=60.0,
            served_qty=96.0,
            service_level=0.96,
        ),
        last_effective_day=3,
    )
    provider.observe(
        _stress(1, service_level=float("nan")),
        last_effective_day=3,
    )

    audit = provider.command_audit_metadata_for_day(2)
    assert audit["control_open_gate_ids"] == ""
    assert set(audit["control_closed_gate_ids"].split(";")) == set(
        (SERVICE_RECOVERY_GATE, EXCEPTIONAL_COST_GATE)
    )
    assert "invalid_observation" in audit["control_gate_reasons_json"]
    assert audit["control_gate_observation_valid"] == 0
    assert audit["control_gate_observation_hash"] == provider.decision_rows[1][
        "observation_hash"
    ]
    assert _resolved_values(provider, 2) == NEUTRAL


def test_rejected_non_sequential_observation_does_not_mutate_gate_state(
    tmp_path: Path,
) -> None:
    slew_limits = {
        name: float(spec.upper) - float(spec.lower)
        for name, spec in CONTROL_BOUNDS.items()
    }
    for action in PROTECTION:
        slew_limits[action] = 0.01
    provider = load_state_feedback_control_provider_v2(
        _write_policy(
            tmp_path,
            payload=_payload(review_period_days=10, slew_limits=slew_limits),
        )
    )
    open_gate = {
        "backlog_days": 0.60,
        "backlog_qty": 60.0,
        "served_qty": 96.0,
        "service_level": 0.96,
    }
    provider.observe(_stress(0, **open_gate), last_effective_day=3)
    assert provider.resolve(1).order_multiplier == pytest.approx(1.01)

    with pytest.raises(ControlProviderError, match="strictly sequential"):
        provider.observe(_stress(2), last_effective_day=3)
    provider.observe(_stress(1, **open_gate), last_effective_day=3)

    assert provider.resolve(2).order_multiplier == pytest.approx(1.02)


def test_required_action_gates_cannot_be_removed_or_weakened(
    tmp_path: Path,
) -> None:
    missing = _payload()
    del missing["action_gate_map"]["order_multiplier"]
    with pytest.raises(ControlProviderError, match="required V2 guarded actions"):
        load_state_feedback_control_provider_v2(
            _write_policy(tmp_path, payload=missing)
        )

    weakened = _payload()
    weakened["action_gate_map"]["external_procurement_multiplier"] = {
        "gate": SERVICE_RECOVERY_GATE,
        "direction": "above_neutral",
    }
    with pytest.raises(ControlProviderError, match="exceptional_cost_gate"):
        load_state_feedback_control_provider_v2(
            _write_policy(tmp_path, payload=weakened)
        )
