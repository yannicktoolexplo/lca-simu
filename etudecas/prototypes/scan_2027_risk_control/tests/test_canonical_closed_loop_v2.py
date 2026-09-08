from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_closed_loop_v2 import (
    CanonicalClosedLoopV2ContractError,
    REQUIRED_TRAINING_SEED_COUNT,
    REQUIRED_VALIDATION_SEED_COUNT,
    command_gate_violations,
    terminal_stability_diagnostic,
    validate_pair_evidence,
    validate_protocol_payload,
)
from etudecas.simulation.engine.control_provider_v2 import (
    load_state_feedback_control_provider_v2,
)


CONFIG = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "canonical_closed_loop_v2_config.json"
)


def _boundary(core_hash: str = "b" * 64) -> dict[str, object]:
    return {
        "schema_version": "etudecas.engine_warmup_boundary_audit.v1",
        "method": "deterministic_paired_burn_in_replay",
        "scope": "core_dynamic_engine_state_not_restart_checkpoint",
        "physical_warmup_days": 60,
        "measured_cutover_day": 0,
        "core_state_sha256": core_hash,
        "component_sha256": {"stock": "c" * 64, "pipeline": "d" * 64},
        "restart_checkpoint_available": False,
    }


def _summary(*, feedback: bool, core_hash: str = "b" * 64) -> dict[str, object]:
    policy: dict[str, object] = {
        "warmup_days": 60,
        "warmup_profile_mode": "preperiod",
        "reset_backlog_after_warmup": False,
        "initialization_policy": {
            "restore_opening_stock_after_warmup": False,
        },
        "warmup_boundary_audit": _boundary(core_hash),
    }
    if feedback:
        policy["control_provider"] = {
            "schema_version": "scan.canonical_state_feedback.v2",
            "mode": "canonical_state_feedback_v2_t_plus_1",
            "closed_loop_claimed": True,
            "closed_loop_claim_reasons": [],
            "physical_warmup_days": 60,
            "controller_dynamic_warmup_days": 60,
            "controller_priming_observation_count": 60,
            "controller_priming_valid_observation_count": 60,
            "controller_priming_first_day": -60,
            "controller_priming_last_day": -1,
            "controller_warmup_matches_physical_warmup": True,
            "controller_primed_during_warmup": True,
            "controller_priming_sequential": True,
            "controller_priming_complete_at_day_minus_one": True,
            "controller_priming_all_observations_valid": True,
            "warmup_commands_disabled": True,
            "warmup_control_action_count": 0,
            "future_realization_access": False,
        }
    return {"policy": policy}


def _priming(*, inventory_terminal: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "day": list(range(-60, 0)),
            "observation_valid": [1] * 60,
            "generated_command_count": [0] * 60,
            "active_command_row_count": [0] * 60,
            "demand_qty": [100.0] * 60,
            "backlog_qty": [0.0] * 60,
            "inventory_qty": [1000.0] * 46 + [inventory_terminal] * 14,
        }
    )


def _commands(*, open_gates: str = "service_recovery_gate") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "effective_day": 1,
                "effective_json": json.dumps({"order_multiplier": 1.02}),
                "control_open_gate_ids": open_gates,
                "control_gate_observation_hash": "a" * 64,
                "control_gate_observation_valid": 1,
            }
        ]
    )


def test_v2_config_has_frozen_disjoint_seed_protocol_and_valid_provider() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    normalized = validate_protocol_payload(payload)

    assert len(normalized["training_seeds"]) == REQUIRED_TRAINING_SEED_COUNT
    assert len(normalized["validation_seeds"]) == REQUIRED_VALIDATION_SEED_COUNT
    assert not set(normalized["training_seeds"]) & set(
        normalized["validation_seeds"]
    )
    assert normalized["warmup_days"] == 60
    provider = load_state_feedback_control_provider_v2(CONFIG)
    assert provider.schema_version == "scan.canonical_state_feedback.v2"
    assert set(provider.summary_metadata()["gate_ids"]) == {
        "service_recovery_gate",
        "exceptional_cost_gate",
    }


def test_v2_config_rejects_training_validation_seed_leakage() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    broken = copy.deepcopy(payload)
    broken["campaign"]["validation_seeds"][0] = broken["campaign"][
        "training_seeds"
    ][0]

    with pytest.raises(
        CanonicalClosedLoopV2ContractError,
        match="must be disjoint",
    ):
        validate_protocol_payload(broken)


def test_pair_evidence_checks_boundary_priming_gates_and_j1_causality() -> None:
    evidence = validate_pair_evidence(
        reference_summary=_summary(feedback=False),
        feedback_summary=_summary(feedback=True),
        priming=_priming(),
        observations=pd.DataFrame({"day": list(range(90))}),
        commands=_commands(),
        action_ledger=pd.DataFrame({"day": [1]}),
        seed=310260,
        measured_days=90,
    )

    assert evidence["boundary_hashes_match"] is True
    assert evidence["controller_priming_rows"] == 60
    assert evidence["controller_warmup_action_count"] == 0
    assert evidence["first_feedback_effective_day"] == 1
    assert evidence["gate_violation_count"] == 0
    assert evidence["burn_in_stability_diagnostic"]["stationarity_claimed"] is False


def test_pair_evidence_rejects_boundary_or_gate_mismatch() -> None:
    common = {
        "reference_summary": _summary(feedback=False),
        "priming": _priming(),
        "observations": pd.DataFrame({"day": list(range(90))}),
        "action_ledger": pd.DataFrame({"day": [1]}),
        "seed": 310260,
        "measured_days": 90,
    }
    with pytest.raises(
        CanonicalClosedLoopV2ContractError,
        match="core state differs",
    ):
        validate_pair_evidence(
            **common,
            feedback_summary=_summary(feedback=True, core_hash="e" * 64),
            commands=_commands(),
        )
    with pytest.raises(
        CanonicalClosedLoopV2ContractError,
        match="command gate violation",
    ):
        validate_pair_evidence(
            **common,
            feedback_summary=_summary(feedback=True),
            commands=_commands(open_gates=""),
        )


def test_gate_validator_requires_exceptional_gate_for_costly_actions() -> None:
    commands = _commands(open_gates="service_recovery_gate")
    commands.loc[0, "effective_json"] = json.dumps(
        {"external_procurement_multiplier": 1.05, "expedite_level": 0.02}
    )

    violations = command_gate_violations(commands)

    assert {row["action"] for row in violations} == {
        "external_procurement_multiplier",
        "expedite_level",
    }


def test_terminal_stability_diagnostic_is_explicitly_non_stationary_claim() -> None:
    stable = terminal_stability_diagnostic(_priming())
    drifting = terminal_stability_diagnostic(_priming(inventory_terminal=1300.0))

    assert stable["status"] == (
        "terminal_window_heuristic_satisfied_not_stationarity_proof"
    )
    assert stable["stationarity_claimed"] is False
    assert drifting["status"] == "stability_not_demonstrated"
    assert drifting["signals"]["inventory_qty"]["criterion_satisfied"] is False
