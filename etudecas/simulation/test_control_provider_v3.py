from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from etudecas.simulation.engine.control_provider import (
    CanonicalObservation,
    ControlProviderError,
    load_state_feedback_control_provider,
)
from etudecas.simulation.engine.control_provider_v2 import (
    SCHEMA_VERSION_V2,
    StateFeedbackControlProviderV2,
    load_state_feedback_control_provider_v2,
)
from etudecas.simulation.engine.control_provider_v3 import (
    SCHEMA_VERSION_V3,
    StateFeedbackControlProviderV3,
    load_state_feedback_control_provider_v3,
)


BASE_V2_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_closed_loop_v2_config.json"
)


def _continuous_relief(*, enabled: bool = True) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "active_regime": "SUPPLIER_STRESS",
        "active_policy": "supplier_relief",
        "stress_start": 0.30,
        "stress_span": 0.40,
        "order_relief_gain": 0.04,
        "production_relief_gain": 0.02,
        "minimum_order_multiplier": 0.970,
        "minimum_production_target_multiplier": 0.985,
        "backlog_guard_days": 0.10,
        "service_guard_level": 0.995,
        "finished_cover_guard_days": 1.20,
        "material_cover_guard_days": 0.75,
        "maximum_relief_step_per_day": 0.01,
    }


def _v3_payload(*, enabled: bool = True) -> dict[str, Any]:
    payload = json.loads(BASE_V2_CONFIG.read_text(encoding="utf-8"))
    payload["schema_version"] = SCHEMA_VERSION_V3
    payload["name"] = "pytest_continuous_supplier_relief_v3"
    payload["review_period_days"] = 1
    payload["confirmation_days"] = 1
    payload["minimum_dwell_days"] = 0
    payload["dynamics"].update(
        {
            "stress_memory": 0.0,
            "nervousness_gain": 0.0,
            "pressure_gain": 0.0,
            "disruption_gain": 1.0,
        }
    )
    payload["continuous_relief"] = _continuous_relief(enabled=enabled)
    return payload


def _write_policy(
    tmp_path: Path,
    payload: Mapping[str, Any],
    *,
    name: str = "policy.json",
) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(dict(payload), indent=2), encoding="utf-8")
    return path


def _observation(day: int, **overrides: Any) -> CanonicalObservation:
    values: dict[str, Any] = {
        "day": day,
        "demand_qty": 100.0,
        "served_qty": 100.0,
        "service_level": 1.0,
        "backlog_qty": 0.0,
        "backlog_days": 0.0,
        "inventory_qty": 1_000.0,
        "finished_inventory_cover_days": 12.0,
        "material_cover_days": 10.0,
        "production_utilization": 0.50,
        "supplier_utilization": 0.50,
        "order_nervousness": 0.0,
        "active_order_pair_count": 1,
        "supplier_disruption_score": 0.60,
        "active_supplier_event_count": 1,
    }
    values.update(overrides)
    return CanonicalObservation(**values)


def _command_signature(provider: StateFeedbackControlProviderV2) -> list[dict[str, Any]]:
    return [
        {
            "decision_day": command.decision_day,
            "effective_day": command.effective_day,
            "policy": command.policy,
            "requested": dict(command.requested or {}),
            "effective": dict(command.effective or {}),
            "slew": tuple(command.slew_limited_actions),
        }
        for command in provider.commands
    ]


def test_v3_loaders_are_explicit_and_schema_strict(tmp_path: Path) -> None:
    v3_path = _write_policy(tmp_path, _v3_payload())
    provider = load_state_feedback_control_provider_v3(v3_path)

    assert isinstance(provider, StateFeedbackControlProviderV3)
    assert provider.schema_version == SCHEMA_VERSION_V3
    assert provider.mode == "canonical_state_feedback_v3_continuous_t_plus_1"
    with pytest.raises(ControlProviderError, match="V2 schema_version"):
        load_state_feedback_control_provider_v2(v3_path)
    with pytest.raises(ControlProviderError, match="scan.canonical_state_feedback.v1"):
        load_state_feedback_control_provider(v3_path)

    v2_payload = _v3_payload()
    v2_payload["schema_version"] = SCHEMA_VERSION_V2
    with pytest.raises(ControlProviderError, match="V3 schema_version"):
        load_state_feedback_control_provider_v3(
            _write_policy(tmp_path, v2_payload, name="v2.json")
        )


def test_disabled_v3_preserves_v2_commands_and_decisions(tmp_path: Path) -> None:
    v3_payload = _v3_payload(enabled=False)
    v2_payload = deepcopy(v3_payload)
    v2_payload["schema_version"] = SCHEMA_VERSION_V2
    v2_payload.pop("continuous_relief")
    v3 = load_state_feedback_control_provider_v3(
        _write_policy(tmp_path, v3_payload, name="v3.json")
    )
    v2 = load_state_feedback_control_provider_v2(
        _write_policy(tmp_path, v2_payload, name="v2.json")
    )

    for day, score in enumerate((0.60, 0.80, 0.40, 0.70)):
        observation = _observation(day, supplier_disruption_score=score)
        v2.observe(observation, last_effective_day=4)
        v3.observe(observation, last_effective_day=4)

    assert _command_signature(v3) == _command_signature(v2)
    v3_core = [
        {key: value for key, value in row.items() if not key.startswith("control_continuous_")}
        for row in v3.decision_rows
    ]
    assert v3_core == list(v2.decision_rows)


def test_continuous_relief_is_monotone_bounded_and_causal(tmp_path: Path) -> None:
    low_payload = _v3_payload()
    high_payload = _v3_payload()
    low_payload["continuous_relief"]["maximum_relief_step_per_day"] = 1.0
    high_payload["continuous_relief"]["maximum_relief_step_per_day"] = 1.0
    low = load_state_feedback_control_provider_v3(
        _write_policy(tmp_path, low_payload, name="low.json")
    )
    high = load_state_feedback_control_provider_v3(
        _write_policy(tmp_path, high_payload, name="high.json")
    )

    low_commands = low.observe(
        _observation(0, supplier_disruption_score=0.40),
        last_effective_day=1,
    )
    high_commands = high.observe(
        _observation(0, supplier_disruption_score=0.90),
        last_effective_day=1,
    )

    assert low.resolve(0).order_multiplier == pytest.approx(1.0)
    assert high.resolve(0).production_target_multiplier == pytest.approx(1.0)
    assert low_commands[0].effective_day == 1
    assert high_commands[0].effective_day == 1
    assert high.resolve(1).order_multiplier < low.resolve(1).order_multiplier < 1.0
    assert (
        high.resolve(1).production_target_multiplier
        < low.resolve(1).production_target_multiplier
        < 1.0
    )
    assert high.resolve(1).order_multiplier >= 0.970
    assert high.resolve(1).production_target_multiplier >= 0.985

    decision = high.decision_rows[-1]
    assert decision["control_continuous_relief_active"] == 1
    assert decision["control_continuous_relief_intensity"] == pytest.approx(1.0)
    assert decision["control_continuous_service_protection"] == pytest.approx(0.0)
    assert high.summary_metadata()["continuous_relief_integral_action"] is False


def test_service_guard_returns_to_neutral_on_next_day(tmp_path: Path) -> None:
    payload = _v3_payload()
    payload["continuous_relief"]["maximum_relief_step_per_day"] = 1.0
    provider = load_state_feedback_control_provider_v3(
        _write_policy(tmp_path, payload)
    )
    provider.observe(_observation(0), last_effective_day=2)
    assert provider.resolve(1).order_multiplier < 1.0

    provider.observe(
        _observation(1, service_level=0.994, served_qty=99.4),
        last_effective_day=2,
    )

    assert provider.resolve(2).order_multiplier == pytest.approx(1.0)
    assert provider.resolve(2).production_target_multiplier == pytest.approx(1.0)
    assert (
        provider.decision_rows[-1]["control_continuous_safety_return_to_neutral"]
        == 1
    )


def test_priming_emits_no_action_and_invalid_observation_fails_neutral(
    tmp_path: Path,
) -> None:
    provider = load_state_feedback_control_provider_v3(
        _write_policy(tmp_path, _v3_payload())
    )
    assert provider.prime(_observation(-2)) == ()
    assert provider.prime(_observation(-1)) == ()
    assert provider.commands == ()
    assert provider.rows == ()

    provider.observe(_observation(0), last_effective_day=2)
    assert provider.resolve(1).order_multiplier < 1.0
    provider.observe(
        _observation(1, service_level=float("nan")),
        last_effective_day=2,
    )
    assert provider.resolve(2).order_multiplier == pytest.approx(1.0)
    assert provider.decision_rows[-1]["fallback_applied"] == 1
    metadata = provider.summary_metadata()
    assert metadata["controller_priming_complete_at_day_minus_one"] is True
    assert metadata["warmup_commands_disabled"] is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("stress_span", 0.0, "stress_span"),
        ("service_guard_level", 1.0, "strictly below"),
        ("minimum_order_multiplier", 1.01, "minimum_order_multiplier"),
        ("maximum_relief_step_per_day", float("nan"), "finite"),
    ],
)
def test_continuous_relief_configuration_is_strict(
    tmp_path: Path,
    field: str,
    value: float,
    message: str,
) -> None:
    payload = _v3_payload()
    payload["continuous_relief"][field] = value
    with pytest.raises(ControlProviderError, match=message):
        load_state_feedback_control_provider_v3(
            _write_policy(tmp_path, payload)
        )

    payload = _v3_payload()
    payload["continuous_relief"]["unknown"] = 1
    with pytest.raises(ControlProviderError, match="unknown=unknown"):
        load_state_feedback_control_provider_v3(
            _write_policy(tmp_path, payload, name="unknown.json")
        )
