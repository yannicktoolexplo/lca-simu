from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

import pytest

from etudecas.simulation.engine.control_provider import (
    CanonicalObservation,
    ControlProviderError,
    REGIMES,
    load_state_feedback_control_provider,
)
from etudecas.simulation.engine.control_schedule import (
    ACTION_FIELDS,
    CONTROL_BOUNDS,
    ControlCatalog,
)


NEUTRAL_ACTIONS = {
    name: spec.neutral
    for name, spec in CONTROL_BOUNDS.items()
}

SUPPLIER_PROTECTION = {
    "order_multiplier": 1.50,
    "safety_stock_multiplier": 1.60,
    "production_target_multiplier": 1.20,
    "capacity_multiplier": 1.20,
    "external_procurement_multiplier": 1.60,
    "expedite_level": 0.40,
    "lead_time_adjustment_days": -4,
    "priority_weight": 1.50,
}

CRISIS_PROTECTION = {
    "order_multiplier": 1.80,
    "safety_stock_multiplier": 2.00,
    "production_target_multiplier": 1.40,
    "capacity_multiplier": 1.40,
    "external_procurement_multiplier": 2.00,
    "expedite_level": 0.80,
    "lead_time_adjustment_days": -8,
    "priority_weight": 2.00,
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


def _stress(day: int) -> CanonicalObservation:
    return _observation(
        day,
        supplier_disruption_score=0.40,
        active_supplier_event_count=1,
    )


def _crisis(day: int) -> CanonicalObservation:
    return _observation(
        day,
        served_qty=70.0,
        service_level=0.70,
        backlog_qty=200.0,
        backlog_days=2.0,
        supplier_disruption_score=0.40,
        active_supplier_event_count=1,
    )


def _command(
    actions: Mapping[str, float | int],
    *,
    scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "scope": dict(scope or {}),
        "actions": dict(actions),
    }


def _playbook(
    actions: Mapping[str, float | int],
    *,
    scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {"commands": [_command(actions, scope=scope)]}


def _policy_payload(
    *,
    review_period_days: int = 1,
    confirmation_days: int = 1,
    minimum_dwell_days: int = 0,
    playbooks: Mapping[str, Mapping[str, Any]] | None = None,
    slew_limits: Mapping[str, float | int] | None = None,
) -> dict[str, Any]:
    configured_playbooks: dict[str, Mapping[str, Any]] = {
        "mrp_reference": _playbook(NEUTRAL_ACTIONS),
        "supplier_protection": _playbook(SUPPLIER_PROTECTION),
        "crisis_protection": _playbook(CRISIS_PROTECTION),
    }
    configured_playbooks.update(playbooks or {})
    regime_policy = {
        regime: "mrp_reference"
        for regime in REGIMES
    }
    regime_policy.update(
        {
            "MATERIAL_TENSION": "supplier_protection",
            "CAPACITY_SATURATION": "supplier_protection",
            "SUPPLIER_STRESS": "supplier_protection",
            "OSCILLATORY": "supplier_protection",
            "CRISIS": "crisis_protection",
        }
    )
    return {
        "schema_version": "scan.canonical_state_feedback.v1",
        "name": "pytest_state_feedback",
        "review_period_days": review_period_days,
        "confirmation_days": confirmation_days,
        "minimum_dwell_days": minimum_dwell_days,
        "fallback_policy": "mrp_reference",
        "emergency_regimes": ["CRISIS"],
        "thresholds": {
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
        },
        # Remove hidden state persistence from the unit fixture.  Classification
        # still reacts to the current physical disruption signal itself.
        "dynamics": {
            "stress_memory": 0.0,
            "nervousness_gain": 0.0,
            "pressure_gain": 0.0,
            "disruption_gain": 0.0,
            "capacity_pressure_start": 0.75,
            "recent_disruption_memory_days": 28.0,
        },
        "slew_limits": {
            name: float(spec.upper) - float(spec.lower)
            for name, spec in CONTROL_BOUNDS.items()
        }
        if slew_limits is None
        else dict(slew_limits),
        "regime_policy": regime_policy,
        "playbooks": configured_playbooks,
    }


def _write_policy(
    tmp_path: Path,
    *,
    filename: str = "closed_loop_policy.json",
    **overrides: Any,
) -> Path:
    path = tmp_path / filename
    path.write_text(
        json.dumps(_policy_payload(**overrides), indent=2),
        encoding="utf-8",
    )
    return path


def _write_raw_policy(
    tmp_path: Path,
    payload: Mapping[str, Any],
    filename: str,
) -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _control_values(resolved: Any) -> dict[str, float | int]:
    return {
        name: getattr(resolved, name)
        for name in ACTION_FIELDS
    }


def _assert_neutral(resolved: Any) -> None:
    assert _control_values(resolved) == NEUTRAL_ACTIONS


def _decision(provider: Any, day: int) -> dict[str, Any]:
    matches = [
        row
        for row in provider.decision_rows
        if int(row["decision_day"]) == day
    ]
    assert len(matches) == 1
    return matches[0]


def test_neutral_configuration_is_causal_and_emits_no_day_zero_action(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))

    _assert_neutral(provider.resolve(0))
    assert (
        provider.audit_metadata_for_day(0)["control_source_kind"]
        == "state_feedback_no_prior_observation"
    )
    commands = provider.observe(_observation(0), last_effective_day=3)

    assert len(commands) == 1
    assert commands[0].decision_day == 0
    assert commands[0].effective_day == 1
    assert not commands[0].active
    assert provider.rows == ()
    _assert_neutral(provider.resolve(1))

    decision = _decision(provider, 0)
    assert decision["effective_day"] == 1
    assert decision["causal_lag_days"] == 1
    assert decision["raw_regime"] == "NOMINAL"
    assert decision["confirmed_regime"] == "NOMINAL"
    assert decision["selected_policy"] == "mrp_reference"
    assert decision["fallback_applied"] == 0
    assert decision["active_command_row_count"] == 0
    day_one_audit = provider.audit_metadata_for_day(1)
    assert day_one_audit["control_source_kind"] == "state_feedback_generated_online"
    assert day_one_audit["decision_day"] == 0
    assert day_one_audit["effective_day"] == 1
    assert day_one_audit["observation_hash"] == decision["observation_hash"]
    metadata = provider.summary_metadata()
    assert metadata["causal_contract_satisfied"] is True
    assert metadata["closed_loop_claimed"] is False
    assert metadata["future_realization_access"] is False
    assert metadata["direct_future_realization_access"] is False
    assert metadata["controller_observation_forecast_lookahead_days"] == 0
    assert metadata["observation_count"] == 1
    assert metadata["decision_count"] == 1


def test_state_perturbation_changes_only_the_following_day(
    tmp_path: Path,
) -> None:
    path = _write_policy(tmp_path)
    nominal = load_state_feedback_control_provider(path)
    stressed = load_state_feedback_control_provider(path)

    for provider in (nominal, stressed):
        provider.observe(_observation(0), last_effective_day=4)
    assert _control_values(nominal.resolve(1)) == _control_values(stressed.resolve(1))

    nominal.observe(_observation(1), last_effective_day=4)
    already_effective = _control_values(stressed.resolve(1))
    stressed.observe(_stress(1), last_effective_day=4)

    # An end-of-day J=1 observation cannot rewrite the J=1 command.
    assert _control_values(stressed.resolve(1)) == already_effective
    assert _control_values(nominal.resolve(1)) == _control_values(stressed.resolve(1))
    assert nominal.resolve(2).order_multiplier == 1.0
    assert stressed.resolve(2).order_multiplier == 1.5
    assert _decision(stressed, 1)["effective_day"] == 2


def test_confirmation_days_provide_temporal_debounce(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(
        _write_policy(tmp_path, confirmation_days=2)
    )

    # A one-day pulse is rejected and NOMINAL resets the pending transition.
    provider.observe(_stress(0), last_effective_day=10)
    assert _decision(provider, 0)["confirmed_regime"] == "NOMINAL"
    provider.observe(_observation(1), last_effective_day=10)
    assert _decision(provider, 1)["pending_count"] == 0

    provider.observe(_stress(2), last_effective_day=10)
    assert _decision(provider, 2)["confirmed_regime"] == "NOMINAL"
    provider.observe(_stress(3), last_effective_day=10)
    assert _decision(provider, 3)["confirmed_regime"] == "SUPPLIER_STRESS"
    assert provider.resolve(4).order_multiplier == 1.5

    # Exiting the accepted regime also requires two consistent observations.
    provider.observe(_observation(4), last_effective_day=10)
    assert _decision(provider, 4)["confirmed_regime"] == "SUPPLIER_STRESS"
    provider.observe(_observation(5), last_effective_day=10)
    assert _decision(provider, 5)["confirmed_regime"] == "NOMINAL"
    _assert_neutral(provider.resolve(6))


def test_review_cadence_holds_policy_between_reviews(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(
        _write_policy(tmp_path, review_period_days=3)
    )

    provider.observe(_stress(0), last_effective_day=5)
    assert provider.resolve(1).order_multiplier == 1.5
    provider.observe(_observation(1), last_effective_day=5)
    provider.observe(_observation(2), last_effective_day=5)

    assert _decision(provider, 1)["review_due"] == 0
    assert _decision(provider, 1)["switch_reason"] == "hold_between_reviews"
    assert provider.resolve(2).order_multiplier == 1.5
    assert provider.resolve(3).order_multiplier == 1.5

    provider.observe(_observation(3), last_effective_day=5)
    assert _decision(provider, 3)["review_due"] == 1
    _assert_neutral(provider.resolve(4))


def test_minimum_dwell_blocks_normal_switch_but_not_emergency(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(
        _write_policy(tmp_path, minimum_dwell_days=3)
    )

    provider.observe(_stress(0), last_effective_day=6)
    assert _decision(provider, 0)["selected_policy"] == "supplier_protection"

    provider.observe(_observation(1), last_effective_day=6)
    held = _decision(provider, 1)
    assert held["confirmed_regime"] == "NOMINAL"
    assert held["selected_policy"] == "supplier_protection"
    assert held["switch_reason"] == "minimum_dwell_hold"
    assert provider.resolve(2).order_multiplier == 1.5

    provider.observe(_crisis(2), last_effective_day=6)
    emergency = _decision(provider, 2)
    assert emergency["raw_regime"] == "CRISIS"
    assert emergency["confirmed_regime"] == "CRISIS"
    assert emergency["selected_policy"] == "crisis_protection"
    assert emergency["switch_reason"] == "emergency_regime_switch"
    assert provider.resolve(3).order_multiplier == 1.8


def test_slew_limits_and_absolute_bounds_are_applied_and_audited(
    tmp_path: Path,
) -> None:
    extreme = {
        "order_multiplier": 3.0,
        "safety_stock_multiplier": 5.0,
        "production_target_multiplier": 3.0,
        "capacity_multiplier": 2.0,
        "external_procurement_multiplier": 5.0,
        "expedite_level": 2.0,
        "lead_time_adjustment_days": -50,
        "priority_weight": 12.0,
    }
    slew = {
        "order_multiplier": 0.10,
        "safety_stock_multiplier": 0.20,
        "production_target_multiplier": 0.10,
        "capacity_multiplier": 0.05,
        "external_procurement_multiplier": 0.20,
        "expedite_level": 0.10,
        "lead_time_adjustment_days": 2,
        "priority_weight": 0.25,
    }
    provider = load_state_feedback_control_provider(
        _write_policy(
            tmp_path,
            playbooks={"supplier_protection": _playbook(extreme)},
            slew_limits=slew,
        )
    )

    commands = provider.observe(_stress(0), last_effective_day=45)
    first = provider.resolve(1)
    assert first.order_multiplier == pytest.approx(1.10)
    assert first.safety_stock_multiplier == pytest.approx(1.20)
    assert first.production_target_multiplier == pytest.approx(1.10)
    assert first.capacity_multiplier == pytest.approx(1.05)
    assert first.external_procurement_multiplier == pytest.approx(1.20)
    assert first.expedite_level == pytest.approx(0.10)
    assert first.lead_time_adjustment_days == -2
    assert first.priority_weight == pytest.approx(1.25)
    assert set(commands[0].slew_limited_actions) == set(ACTION_FIELDS)
    # Absolute bounds are applied before slew; the raw out-of-range request is
    # retained in loader warnings instead of reaching the physical engine.
    assert commands[0].requested["order_multiplier"] == 2.0
    assert any("order_multiplier requested 3.0" in warning for warning in provider.warnings)

    for day in range(1, 41):
        provider.observe(_stress(day), last_effective_day=45)
        resolved = provider.resolve(day + 1)
        for name, spec in CONTROL_BOUNDS.items():
            value = getattr(resolved, name)
            assert float(spec.lower) <= float(value) <= float(spec.upper), name
        assert isinstance(resolved.lead_time_adjustment_days, int)

    final = provider.resolve(41)
    assert final.order_multiplier == 2.0
    assert final.safety_stock_multiplier == 3.0
    assert final.production_target_multiplier == 2.0
    assert final.capacity_multiplier == 1.5
    assert final.external_procurement_multiplier == 3.0
    assert final.expedite_level == 1.0
    assert final.lead_time_adjustment_days == -30
    assert final.priority_weight == 10.0


def test_zero_slew_retains_requested_action_in_command_audit(
    tmp_path: Path,
) -> None:
    order_only = _playbook({"order_multiplier": 1.5})
    provider = load_state_feedback_control_provider(
        _write_policy(
            tmp_path,
            playbooks={
                "supplier_protection": order_only,
                "crisis_protection": order_only,
            },
            slew_limits={
                name: (
                    0.0
                    if name == "order_multiplier"
                    else float(spec.upper) - float(spec.lower)
                )
                for name, spec in CONTROL_BOUNDS.items()
            },
        )
    )

    commands = provider.observe(_stress(0), last_effective_day=2)

    assert len(commands) == 1
    assert commands[0].active is False
    assert commands[0].requested["order_multiplier"] == 1.5
    assert commands[0].effective["order_multiplier"] == 1.0
    assert commands[0].slew_limited_actions == ("order_multiplier",)
    assert provider.rows == ()


@pytest.mark.parametrize("non_finite", [math.nan, math.inf, -math.inf])
def test_non_finite_observation_uses_explicit_neutral_fallback(
    tmp_path: Path,
    non_finite: float,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))

    commands = provider.observe(
        _stress(0).__class__(
            **{
                **_stress(0).__dict__,
                "supplier_disruption_score": non_finite,
            }
        ),
        last_effective_day=2,
    )

    assert len(commands) == 1
    assert not commands[0].active
    _assert_neutral(provider.resolve(1))
    decision = _decision(provider, 0)
    assert decision["fallback_applied"] == 1
    assert decision["selected_policy"] == "mrp_reference"
    assert "finite" in decision["invalid_reason"].lower()
    assert re.fullmatch(r"[0-9a-f]{64}", decision["observation_hash"])
    assert provider.summary_metadata()["fallback_count"] == 1


def test_observation_hash_is_deterministic_and_state_sensitive(
    tmp_path: Path,
) -> None:
    path = _write_policy(tmp_path)
    first = load_state_feedback_control_provider(path)
    same = load_state_feedback_control_provider(path)
    changed = load_state_feedback_control_provider(path)

    first.observe(_observation(0), last_effective_day=2)
    same.observe(_observation(0), last_effective_day=2)
    changed.observe(_observation(0, backlog_days=0.01), last_effective_day=2)

    first_hash = first.observation_rows[0]["observation_hash"]
    assert re.fullmatch(r"[0-9a-f]{64}", first_hash)
    assert same.observation_rows[0]["observation_hash"] == first_hash
    assert changed.observation_rows[0]["observation_hash"] != first_hash
    assert _decision(first, 0)["observation_hash"] == first_hash


def test_recent_disruption_default_still_arms_on_any_positive_score(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))

    provider.observe(
        _observation(0, supplier_disruption_score=1e-12),
        last_effective_day=1,
    )

    assert provider.dynamics["recent_disruption_score_floor"] == 0.0
    assert provider.observation_rows[0]["recent_disruption_signal"] == 1


def test_recent_disruption_floor_is_strict_and_memory_lasts_21_days(
    tmp_path: Path,
) -> None:
    payload = _policy_payload()
    payload["dynamics"].update(
        {
            "recent_disruption_score_floor": 0.30,
            "recent_disruption_memory_days": 21.0,
        }
    )
    provider = load_state_feedback_control_provider(
        _write_raw_policy(tmp_path, payload, "incident_floor.json")
    )

    provider.observe(
        _observation(0, supplier_disruption_score=0.29),
        last_effective_day=23,
    )
    provider.observe(
        _observation(1, supplier_disruption_score=0.30),
        last_effective_day=23,
    )
    provider.observe(
        _observation(2, supplier_disruption_score=0.31),
        last_effective_day=23,
    )
    for day in range(3, 24):
        provider.observe(_observation(day), last_effective_day=23)

    signals = {
        int(row["day"]): int(row["recent_disruption_signal"])
        for row in provider.observation_rows
    }
    assert signals[0] == 0
    assert signals[1] == 0
    assert signals[2] == 1
    assert signals[23] == 1

    provider.observe(_observation(24), last_effective_day=24)
    assert provider.observation_rows[-1]["recent_disruption_signal"] == 0


@pytest.mark.parametrize("invalid_floor", [-0.01, 1.01, math.nan, math.inf])
def test_recent_disruption_floor_must_be_finite_and_bounded(
    tmp_path: Path,
    invalid_floor: float,
) -> None:
    payload = _policy_payload()
    payload["dynamics"]["recent_disruption_score_floor"] = invalid_floor

    with pytest.raises(
        ControlProviderError,
        match="recent_disruption_score_floor must (?:be finite|be in \\[0, 1\\])",
    ):
        load_state_feedback_control_provider(
            _write_raw_policy(tmp_path, payload, "invalid_incident_floor.json")
        )


def test_targeted_scope_does_not_leak_to_other_lanes(
    tmp_path: Path,
) -> None:
    target_scope = {
        "supplier_id": "S1",
        "item_id": "item:A",
        "dst_node_id": "F1",
    }
    # Production-target and safety-stock levers cannot be resolved on a
    # supplier/destination scope.  Keep this lane command to the levers that the
    # canonical supplier execution stages can actually consume.
    targeted_actions = {
        name: SUPPLIER_PROTECTION[name]
        for name in (
            "order_multiplier",
            "capacity_multiplier",
            "external_procurement_multiplier",
            "expedite_level",
            "lead_time_adjustment_days",
            "priority_weight",
        )
    }
    scoped_protection = {
        "commands": [
            _command(targeted_actions, scope=target_scope),
        ]
    }
    scoped_crisis = {
        "commands": [
            _command(targeted_actions, scope=target_scope),
        ]
    }
    catalog = ControlCatalog(
        node_ids={"F1"},
        supplier_ids={"S1", "S2"},
        item_ids={"item:A", "item:B"},
        dst_node_ids={"F1"},
    )
    provider = load_state_feedback_control_provider(
        _write_policy(
            tmp_path,
            playbooks={
                "supplier_protection": scoped_protection,
                "crisis_protection": scoped_crisis,
            },
        ),
        catalog=catalog,
    )

    commands = provider.observe(_stress(0), last_effective_day=3)
    targeted = provider.resolve(1, **target_scope)
    other_supplier = provider.resolve(
        1,
        supplier_id="S2",
        item_id="item:A",
        dst_node_id="F1",
    )
    other_item = provider.resolve(
        1,
        supplier_id="S1",
        item_id="item:B",
        dst_node_id="F1",
    )

    assert targeted.order_multiplier == 1.5
    _assert_neutral(other_supplier)
    _assert_neutral(other_item)
    active_commands = [command for command in commands if command.active]
    assert len(active_commands) == 1
    assert active_commands[0].supplier_id == "S1"
    assert active_commands[0].item_id == "item:A"
    assert active_commands[0].dst_node_id == "F1"
    assert all(row.day == 1 for row in provider.rows)


def test_unknown_target_scope_is_rejected_by_catalog(tmp_path: Path) -> None:
    invalid = _playbook(
        SUPPLIER_PROTECTION,
        scope={"supplier_id": "UNKNOWN", "item_id": "item:A"},
    )
    path = _write_policy(
        tmp_path,
        playbooks={"supplier_protection": invalid},
    )

    with pytest.raises(ControlProviderError, match="unknown supplier_id"):
        load_state_feedback_control_provider(
            path,
            catalog=ControlCatalog(
                supplier_ids={"S1"},
                item_ids={"item:A"},
            ),
        )


def test_terminal_observation_is_audited_without_orphan_command(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))

    commands = provider.observe(_stress(2), last_effective_day=2)

    assert commands == ()
    assert provider.observation_rows[-1]["day"] == 2
    assert not any(row.day == 3 for row in provider.rows)
    decision = _decision(provider, 2)
    assert decision["effective_day"] == 3
    assert decision["generated_command_count"] == 0
    assert decision["active_command_row_count"] == 0
    metadata = provider.summary_metadata()
    assert metadata["causal_contract_satisfied"] is True
    assert metadata["closed_loop_claimed"] is False


def test_observations_must_be_strictly_sequential(tmp_path: Path) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))
    provider.observe(_observation(0), last_effective_day=3)

    with pytest.raises(ControlProviderError, match="strictly sequential"):
        provider.observe(_observation(2), last_effective_day=3)


@pytest.mark.parametrize("invalid_scope", [0, False, None])
def test_non_string_scope_value_cannot_become_global(
    tmp_path: Path,
    invalid_scope: Any,
) -> None:
    payload = _policy_payload()
    payload["playbooks"]["supplier_protection"] = {
        "commands": [
            {
                "scope": {"supplier_id": invalid_scope},
                "actions": {"order_multiplier": 1.2},
            }
        ]
    }
    path = _write_raw_policy(tmp_path, payload, "invalid_scope.json")

    with pytest.raises(ControlProviderError, match="must be a string"):
        load_state_feedback_control_provider(path)


def test_cross_playbook_equal_specificity_ambiguity_is_rejected_at_load(
    tmp_path: Path,
) -> None:
    payload = _policy_payload(
        playbooks={
            "supplier_protection": {
                "commands": [
                    _command(
                        {"order_multiplier": 1.2},
                        scope={"supplier_id": "S1"},
                    )
                ]
            },
            "crisis_protection": {
                "commands": [
                    _command(
                        {"order_multiplier": 1.3},
                        scope={"item_id": "item:A"},
                    )
                ]
            },
        }
    )
    path = _write_raw_policy(tmp_path, payload, "ambiguous_transition.json")

    with pytest.raises(ControlProviderError, match="equally specific"):
        load_state_feedback_control_provider(path)


def test_active_general_scope_beneath_targeted_scope_is_rejected_for_slew(
    tmp_path: Path,
) -> None:
    payload = _policy_payload(
        playbooks={
            "supplier_protection": {
                "commands": [
                    _command(
                        {"order_multiplier": 1.2},
                        scope={"supplier_id": "S1", "item_id": "item:A"},
                    )
                ]
            },
            "crisis_protection": {
                "commands": [
                    _command({"order_multiplier": 1.3})
                ]
            },
        }
    )
    path = _write_raw_policy(tmp_path, payload, "unsafe_inheritance.json")

    with pytest.raises(ControlProviderError, match="resolved slew limits"):
        load_state_feedback_control_provider(path)


def test_fallback_policy_must_be_physically_neutral(tmp_path: Path) -> None:
    payload = _policy_payload()
    payload["fallback_policy"] = "supplier_protection"
    path = _write_raw_policy(tmp_path, payload, "active_fallback.json")

    with pytest.raises(ControlProviderError, match="fallback_policy must be physically neutral"):
        load_state_feedback_control_provider(path)


def test_negative_observation_day_is_rejected_without_command(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))

    with pytest.raises(ControlProviderError, match="zero-based non-negative"):
        provider.observe(_observation(-1), last_effective_day=2)

    assert provider.commands == ()
    assert provider.rows == ()
    assert provider.observation_rows == ()


def test_numeric_string_observation_is_normalized_without_type_error(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))
    raw = _observation(0).__dict__
    observation = CanonicalObservation(
        **{
            **raw,
            "service_level": "1.0",
            "supplier_disruption_score": "0.0",
        }
    )

    provider.observe(observation, last_effective_day=2)

    assert provider.observation_rows[0]["observation_valid"] == 1
    assert provider.observation_rows[0]["service_level"] == 1.0


def test_non_integer_event_count_uses_neutral_fallback(tmp_path: Path) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))
    observation = CanonicalObservation(
        **{
            **_stress(0).__dict__,
            "active_supplier_event_count": 0.5,
        }
    )

    commands = provider.observe(observation, last_effective_day=2)

    assert all(not command.active for command in commands)
    assert _decision(provider, 0)["fallback_applied"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("material_cover_days", -1.0),
        ("finished_inventory_cover_days", -0.1),
        ("supplier_disruption_score", True),
        ("service_level", False),
    ],
)
def test_invalid_real_observation_uses_neutral_fallback(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    provider = load_state_feedback_control_provider(_write_policy(tmp_path))
    observation = _observation(0, **{field: value})

    commands = provider.observe(observation, last_effective_day=2)

    assert all(not command.active for command in commands)
    assert provider.observation_rows[0]["observation_valid"] == 0
    decision = _decision(provider, 0)
    assert decision["fallback_applied"] == 1
    assert decision["selected_policy"] == "mrp_reference"
