from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v6 as downstream_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_holdout_campaign_once_relay as relay,
)


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _calibration_contract(config: relay.RelayConfig) -> dict[str, object]:
    unsigned: dict[str, object] = {
        "schema_version": relay.CALIBRATION_CONTRACT_SCHEMA_VERSION,
        "configuration": {
            "repo": str(config.repo.resolve()),
            "development_plan_dir": str(config.v4_plan_dir.resolve()),
            "development_run_dir": str(config.v4_run_dir.resolve()),
            "holdout_plan_dir": str(config.calibration_plan_dir.resolve()),
            "holdout_run_dir": str(config.calibration_run_dir.resolve()),
            "sidecar_dir": str(config.sidecar_dir.resolve()),
            "supervision_dir": str(config.calibration_status.parent.resolve()),
            "workers": config.calibration_workers,
        },
        "module_hashes": {
            "orchestrator_sha256": relay.AUDITED_V6_SHA256[
                "etudecas/prototypes/scan_2027_risk_control/continue_supplier_v6_calibration.py"
            ],
            "holdout_driver_sha256": relay.AUDITED_V6_SHA256[
                "etudecas/prototypes/scan_2027_risk_control/supplier_fresh_holdout_v6.py"
            ],
            "sidecar_driver_sha256": relay.AUDITED_V6_SHA256[
                "etudecas/prototypes/scan_2027_risk_control/supplier_holdout_curve_sidecar_v6.py"
            ],
        },
        "scientific_contract": {
            "development_evidence_cases": 150,
            "new_development_engine_runs": 60,
            "fresh_holdout_engine_runs_if_selected": 90,
            "holdout_matrix": "3x30_fresh_reserved",
            "watcher_ready_required_before_first_holdout_engine": True,
            "retuning_after_holdout": False,
            "quality_incident_included": False,
            "capacity_incident_included": False,
            "availability_incident_included": False,
            "downstream_execution_supported": False,
        },
    }
    return relay._signed(unsigned, "contract_signature")  # noqa: SLF001


def _terminal_proofs(config: relay.RelayConfig) -> tuple[str, str]:
    holdout_unsigned: dict[str, object] = {
        "schema_version": relay.HOLDOUT_RESULT_SCHEMA_VERSION,
        "status": relay.ACCEPTED_HOLDOUT_STATUS,
        "accepted": True,
        "publishable": True,
        "retuning_after_holdout": False,
        "execution_mode": relay.OFFICIAL_HOLDOUT_EXECUTION_MODE,
        "holdout_evidence_case_count": relay.EXPECTED_HOLDOUT_CASES,
    }
    holdout = relay._signed(holdout_unsigned, "holdout_signature")  # noqa: SLF001
    _write_json(config.calibration_run_dir / "holdout_result.json", holdout)

    inventory_unsigned: dict[str, object] = {
        "schema_version": relay.SIDECAR_INVENTORY_SCHEMA_VERSION,
        "status": "complete",
        "case_count": relay.EXPECTED_HOLDOUT_CASES,
        "compatibility_filename": relay.SIDECAR_INVENTORY_FILENAME,
    }
    inventory = relay._signed(  # noqa: SLF001
        inventory_unsigned, "inventory_signature"
    )
    _write_json(config.sidecar_dir / relay.SIDECAR_INVENTORY_FILENAME, inventory)
    return str(holdout["holdout_signature"]), str(inventory["inventory_signature"])


def _calibration_status(
    config: relay.RelayConfig,
    *,
    status: str = "complete",
    authorized: bool = True,
) -> dict[str, object]:
    contract = relay._read_json(  # noqa: SLF001
        config.calibration_status.with_name("contract.json")
    )
    holdout_signature = ""
    inventory_signature = ""
    if status == "complete":
        holdout_signature, inventory_signature = _terminal_proofs(config)
    unsigned: dict[str, object] = {
        "schema_version": relay.CALIBRATION_STATUS_SCHEMA_VERSION,
        "contract_signature": contract["contract_signature"],
        "status": status,
        "stage": (
            relay.ACCEPTED_CALIBRATION_STAGE
            if status == "complete"
            else "development_running"
        ),
        "message": "fixture",
        "started_at_utc": "2026-09-05T00:00:00+00:00",
        "completed_at_utc": (
            "2026-09-05T01:00:00+00:00" if status == "complete" else ""
        ),
        "active_command": {},
        "downstream_authorized": authorized,
        "holdout_signature": holdout_signature,
        "inventory_signature": inventory_signature,
    }
    return relay._signed(unsigned, "status_signature")  # noqa: SLF001


def _no_go_status(config: relay.RelayConfig) -> dict[str, object]:
    contract = relay._read_json(  # noqa: SLF001
        config.calibration_status.with_name("contract.json")
    )
    unsigned: dict[str, object] = {
        "schema_version": relay.CALIBRATION_STATUS_SCHEMA_VERSION,
        "contract_signature": contract["contract_signature"],
        "status": "scientific_no_go",
        "stage": "scientific_no_go_after_holdout",
        "message": "rejected",
        "completed_at_utc": "2026-09-05T01:00:00+00:00",
        "downstream_authorized": False,
    }
    return relay._signed(unsigned, "status_signature")  # noqa: SLF001


def _receipt(config: relay.RelayConfig) -> relay.LaunchResult:
    command = relay._expected_downstream_child_command(config.resolved())  # noqa: SLF001
    unsigned = {
        "schema_version": relay.DOWNSTREAM_RECEIPT_SCHEMA_VERSION,
        "status": "detached_relay_started",
        "pid": 4242,
        "command": command,
        "command_sha256": relay.stable_sha256(command),
        "log_path": str(
            config.downstream_supervision_dir.resolve() / "detached_relay.log"
        ),
        "status_path": str(config.downstream_supervision_dir.resolve() / "status.json"),
        "started_at_utc": "2026-09-05T01:00:00+00:00",
        "preflight_completed_before_process_start": True,
    }
    payload = relay._signed(unsigned, "receipt_signature")  # noqa: SLF001
    return relay.LaunchResult(0, json.dumps(payload), "")


@pytest.fixture
def configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> relay.RelayConfig:
    repo = tmp_path / "repo"
    repo.mkdir()
    audited: dict[str, str] = {}
    for index, relative in enumerate(relay.AUDITED_V6_SHA256):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"AUDITED = {index}\n", encoding="utf-8")
        audited[relative] = relay.sha256_file(path)
    monkeypatch.setattr(relay, "AUDITED_V6_SHA256", audited)

    sources = tmp_path / "sources"
    for name in (
        "development-plan",
        "development-run",
        "holdout-plan",
        "holdout-run",
        "sidecar",
    ):
        (sources / name).mkdir(parents=True)
    legacy_risk = sources / "risk.html"
    legacy_control = sources / "control.html"
    legacy_risk.write_text("<html>risk archive</html>", encoding="utf-8")
    legacy_control.write_text("<html>control archive</html>", encoding="utf-8")
    monkeypatch.setattr(
        relay,
        "HISTORICAL_HTML_SHA256",
        {
            "legacy_risk_html": relay.sha256_file(legacy_risk),
            "legacy_control_html": relay.sha256_file(legacy_control),
        },
    )
    status = sources / "calibration-supervision" / "status.json"
    output = tmp_path / "outputs"
    config = relay.RelayConfig(
        repo=repo,
        calibration_status=status,
        handoff_supervision_dir=tmp_path / "handoff",
        v4_plan_dir=sources / "development-plan",
        v4_run_dir=sources / "development-run",
        v4_sidecar_root=sources / "forbidden-sidecar",
        calibration_plan_dir=sources / "holdout-plan",
        calibration_run_dir=sources / "holdout-run",
        sidecar_dir=sources / "sidecar",
        bridge_json=output / "bridge.json",
        campaign_root=output / "campaign",
        results_dir=output / "results",
        lot_replay_root=output / "lots",
        qualification_dir=output / "qualification",
        action_replay_root=output / "actions",
        dashboard_html=output / "dashboard.html",
        final_html=output / "final.html",
        downstream_supervision_dir=output / "downstream-supervision",
        legacy_risk_html=legacy_risk,
        legacy_control_html=legacy_control,
        wait_timeout_hours=0.001,
        poll_seconds=0.1,
    )
    contract = _calibration_contract(config)
    monkeypatch.setattr(
        relay,
        "EXPECTED_CALIBRATION_CONTRACT_SIGNATURE",
        contract["contract_signature"],
    )
    _write_json(status.with_name("contract.json"), contract)
    _write_json(status, _calibration_status(config))
    return config


def _runner(
    config: relay.RelayConfig,
    calls: list[list[str]],
    *,
    clock: Clock | None = None,
) -> relay.HoldoutCampaignOnceRelay:
    actual_clock = clock or Clock()

    def launch(command: object, _config: relay.RelayConfig) -> relay.LaunchResult:
        calls.append(list(command))  # type: ignore[arg-type]
        return _receipt(_config)

    return relay.HoldoutCampaignOnceRelay(
        config,
        launcher=launch,
        sleep=actual_clock.sleep,
        monotonic=actual_clock.monotonic,
        prevent_sleep=lambda _enabled: None,
    )


def test_accepted_signed_status_invokes_exact_public_detach_once(
    configured: relay.RelayConfig,
) -> None:
    calls: list[list[str]] = []
    protected_before = {
        path: relay.sha256_file(path)
        for path in (configured.legacy_risk_html, configured.legacy_control_html)
    }
    result = _runner(configured, calls).execute()

    assert result["status"] == "downstream_detach_started"
    assert len(calls) == 1
    command = calls[0]
    assert command == relay.downstream_command(configured.resolved())
    assert command[1:3] == ["-m", relay.DOWNSTREAM_MODULE]
    assert command.count("--detach") == 1
    assert command[-1] == "--detach"
    assert "--detached-child" not in command
    assert command[command.index("--action-replay-mode") + 1] == "required"
    assert {
        path: relay.sha256_file(path)
        for path in (configured.legacy_risk_html, configured.legacy_control_html)
    } == protected_before
    persisted = relay._read_json(  # noqa: SLF001
        configured.handoff_supervision_dir / "status.json"
    )
    relay._verify_signature(  # noqa: SLF001
        persisted, "status_signature", "fixture status"
    )
    reservation = relay._read_json(  # noqa: SLF001
        configured.handoff_supervision_dir / "launch_reservation.json"
    )
    assert reservation["attempt"] == 1
    assert len(reservation["protected_inventory"]["audited_v6"]) == 10
    assert len(reservation["protected_inventory"]["historical_html"]) == 2

    with pytest.raises(relay.HandoffRelayError, match="déjà été réservée"):
        _runner(configured, calls).execute()
    assert len(calls) == 1


def test_expected_receipt_command_equals_pinned_downstream_child_builder(
    configured: relay.RelayConfig,
) -> None:
    config = configured.resolved()
    public_command = relay.downstream_command(config)
    with downstream_v6._v6_downstream_binding():  # noqa: SLF001
        args = downstream_v6.implementation_v5._parser().parse_args(  # noqa: SLF001
            public_command[3:]
        )
        actual = downstream_v6._child_command(args)  # noqa: SLF001

    assert actual == relay._expected_downstream_child_command(config)  # noqa: SLF001


def test_running_status_is_waited_for_then_revalidated(
    configured: relay.RelayConfig,
) -> None:
    _write_json(
        configured.calibration_status,
        _calibration_status(configured, status="running", authorized=False),
    )
    calls: list[list[str]] = []
    clock = Clock()

    def sleep(seconds: float) -> None:
        clock.sleep(seconds)
        _write_json(configured.calibration_status, _calibration_status(configured))

    instance = _runner(configured, calls, clock=clock)
    instance.sleep = sleep
    result = instance.execute()

    assert result["status"] == "downstream_detach_started"
    assert len(calls) == 1
    journal = relay._read_json(  # noqa: SLF001
        configured.handoff_supervision_dir / "journal.json"
    )
    assert "waiting" in [event["event"] for event in journal["events"]]


@pytest.mark.parametrize(
    "failure", ["bad_signature", "complete_without_authorization", "no_go"]
)
def test_adversarial_calibration_decisions_never_call_downstream(
    configured: relay.RelayConfig, failure: str
) -> None:
    if failure == "bad_signature":
        payload = _calibration_status(configured)
        payload["message"] = "tampered after signing"
    elif failure == "complete_without_authorization":
        payload = _calibration_status(configured, authorized=False)
    else:
        payload = _no_go_status(configured)
    _write_json(configured.calibration_status, payload)
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError):
        _runner(configured, calls).execute()

    assert calls == []
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()


def test_self_signed_status_not_bound_to_real_contract_is_rejected(
    configured: relay.RelayConfig,
) -> None:
    payload = _calibration_status(configured)
    payload.pop("status_signature")
    payload["contract_signature"] = "0" * 64
    _write_json(
        configured.calibration_status,
        relay._signed(payload, "status_signature"),  # noqa: SLF001
    )
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError, match="contrat signé réel"):
        _runner(configured, calls).execute()

    assert calls == []
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()


def test_self_consistent_but_unpinned_contract_and_status_are_rejected(
    configured: relay.RelayConfig,
) -> None:
    contract_path = configured.calibration_status.with_name("contract.json")
    contract = relay._read_json(contract_path)  # noqa: SLF001
    contract.pop("contract_signature")
    contract["foreign_copy"] = True
    foreign_contract = relay._signed(contract, "contract_signature")  # noqa: SLF001
    _write_json(contract_path, foreign_contract)

    status = _calibration_status(configured)
    _write_json(configured.calibration_status, status)
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError, match="signature figée"):
        _runner(configured, calls).execute()

    assert calls == []
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()


@pytest.mark.parametrize("proof", ["non_hex", "missing_holdout", "tampered_inventory"])
def test_terminal_status_requires_real_bound_proofs(
    configured: relay.RelayConfig, proof: str
) -> None:
    payload = _calibration_status(configured)
    if proof == "non_hex":
        payload.pop("status_signature")
        payload["holdout_signature"] = "h" * 64
        payload = relay._signed(payload, "status_signature")  # noqa: SLF001
    elif proof == "missing_holdout":
        (configured.calibration_run_dir / "holdout_result.json").unlink()
    else:
        inventory_path = configured.sidecar_dir / relay.SIDECAR_INVENTORY_FILENAME
        inventory = relay._read_json(inventory_path)  # noqa: SLF001
        inventory["case_count"] = 89
        _write_json(inventory_path, inventory)
    _write_json(configured.calibration_status, payload)
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError):
        _runner(configured, calls).execute()

    assert calls == []
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()


def test_calibration_contract_paths_are_bound_to_cli_sources(
    configured: relay.RelayConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_path = configured.calibration_status.with_name("contract.json")
    contract = relay._read_json(contract_path)  # noqa: SLF001
    contract.pop("contract_signature")
    contract["configuration"]["holdout_run_dir"] = str(  # type: ignore[index]
        configured.calibration_run_dir.with_name("foreign-holdout")
    )
    contract = relay._signed(contract, "contract_signature")  # noqa: SLF001
    monkeypatch.setattr(
        relay,
        "EXPECTED_CALIBRATION_CONTRACT_SIGNATURE",
        contract["contract_signature"],
    )
    _write_json(contract_path, contract)
    status = _calibration_status(configured)
    _write_json(configured.calibration_status, status)
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError, match="run holdout V6 attendu"):
        _runner(configured, calls).execute()

    assert calls == []


def test_timeout_is_terminal_and_never_calls_downstream(
    configured: relay.RelayConfig,
) -> None:
    configured.calibration_status.unlink()
    config = relay.RelayConfig(
        **{
            **configured.__dict__,
            "wait_timeout_hours": 0.00005,
            "poll_seconds": 0.1,
        }
    )
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffTimeout):
        _runner(config, calls).execute()
    with pytest.raises(relay.HandoffRelayError, match="déjà terminal"):
        _runner(config, calls).execute()

    assert calls == []
    status = relay._read_json(config.handoff_supervision_dir / "status.json")  # noqa: SLF001
    assert status["status"] == "stopped_timeout"
    assert status["downstream_started"] is False


@pytest.mark.parametrize("tamper", ["audited_module", "historic_html", "destination"])
def test_initial_integrity_or_overwrite_violation_creates_no_state_and_no_process(
    configured: relay.RelayConfig, tamper: str
) -> None:
    if tamper == "audited_module":
        audited = next(iter(relay.AUDITED_V6_SHA256))
        (configured.repo / audited).write_text("changed\n", encoding="utf-8")
    elif tamper == "historic_html":
        configured.legacy_risk_html.write_text("changed", encoding="utf-8")
    else:
        configured.campaign_root.mkdir(parents=True)
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError):
        _runner(configured, calls).execute()

    assert calls == []
    assert not configured.handoff_supervision_dir.exists()


@pytest.mark.parametrize(
    "overlap", ["source", "calibration_supervision", "destination"]
)
def test_all_sources_supervisions_and_destinations_must_be_separate(
    configured: relay.RelayConfig, overlap: str
) -> None:
    values = dict(configured.__dict__)
    if overlap == "source":
        values["campaign_root"] = configured.v4_plan_dir / "new-campaign"
    elif overlap == "calibration_supervision":
        values["handoff_supervision_dir"] = (
            configured.calibration_status.parent / "handoff"
        )
    else:
        values["results_dir"] = configured.campaign_root / "nested-results"
    config = relay.RelayConfig(**values)
    calls: list[list[str]] = []

    with pytest.raises(relay.HandoffRelayError, match="chevauch"):
        _runner(config, calls).execute()

    assert calls == []
    assert not config.handoff_supervision_dir.exists()


def test_toctou_tamper_between_signed_gate_and_launch_is_blocked(
    configured: relay.RelayConfig,
) -> None:
    calls: list[list[str]] = []
    instance = _runner(configured, calls)
    original = instance._read_calibration_decision  # noqa: SLF001
    audited = configured.repo / next(iter(relay.AUDITED_V6_SHA256))
    first = True

    def decision() -> str:
        nonlocal first
        signature = original()
        if first:
            first = False
            audited.write_text("changed between gates\n", encoding="utf-8")
        return signature

    instance._read_calibration_decision = decision  # type: ignore[method-assign]  # noqa: SLF001
    with pytest.raises(relay.HandoffRelayError, match="Empreinte V6"):
        instance.execute()

    assert calls == []
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()


def test_invalid_downstream_receipt_consumes_attempt_without_retry(
    configured: relay.RelayConfig,
) -> None:
    calls: list[list[str]] = []

    def invalid(
        command: Sequence[str], _config: relay.RelayConfig
    ) -> relay.LaunchResult:
        calls.append(list(command))
        return relay.LaunchResult(0, "{}", "")

    instance = relay.HoldoutCampaignOnceRelay(
        configured,
        launcher=invalid,
        sleep=lambda _seconds: None,
        monotonic=lambda: 0.0,
        prevent_sleep=lambda _enabled: None,
    )
    with pytest.raises(relay.HandoffRelayError, match="aucun nouvel essai"):
        instance.execute()
    with pytest.raises(relay.HandoffRelayError, match="déjà été réservée"):
        instance.execute()

    assert len(calls) == 1
    status = relay._read_json(configured.handoff_supervision_dir / "status.json")  # noqa: SLF001
    assert status["status"] == "downstream_receipt_invalid_outcome_unknown_no_retry"
    assert status["downstream_started"] is None


def test_signed_receipt_for_a_different_child_command_is_not_accepted(
    configured: relay.RelayConfig,
) -> None:
    calls: list[list[str]] = []

    def wrong_receipt(
        command: Sequence[str], _config: relay.RelayConfig
    ) -> relay.LaunchResult:
        calls.append(list(command))
        payload = json.loads(_receipt(_config).stdout)
        payload.pop("receipt_signature")
        payload["command"] = [*payload["command"], "--foreign-option"]
        payload["command_sha256"] = relay.stable_sha256(payload["command"])
        payload = relay._signed(payload, "receipt_signature")  # noqa: SLF001
        return relay.LaunchResult(0, json.dumps(payload), "")

    instance = relay.HoldoutCampaignOnceRelay(
        configured,
        launcher=wrong_receipt,
        prevent_sleep=lambda _enabled: None,
    )
    with pytest.raises(relay.HandoffRelayError, match="sans reçu fiable"):
        instance.execute()

    assert len(calls) == 1
    status = relay._read_json(configured.handoff_supervision_dir / "status.json")  # noqa: SLF001
    assert status["status"] == "downstream_receipt_invalid_outcome_unknown_no_retry"
    assert status["downstream_started"] is None


def test_downstream_public_preflight_rejection_is_terminal_and_confirmed_not_started(
    configured: relay.RelayConfig,
) -> None:
    calls: list[list[str]] = []

    def rejected(
        command: Sequence[str], _config: relay.RelayConfig
    ) -> relay.LaunchResult:
        calls.append(list(command))
        return relay.LaunchResult(2, "", "preflight refused")

    instance = relay.HoldoutCampaignOnceRelay(
        configured,
        launcher=rejected,
        prevent_sleep=lambda _enabled: None,
    )
    with pytest.raises(relay.HandoffRelayError, match="non renouvelable"):
        instance.execute()

    assert len(calls) == 1
    status = relay._read_json(configured.handoff_supervision_dir / "status.json")  # noqa: SLF001
    assert status["status"] == "downstream_preflight_rejected_no_retry"
    assert status["downstream_started"] is False


def test_default_launcher_uses_hidden_shell_free_windows_process(
    configured: relay.RelayConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class Completed:
        returncode = 2
        stdout = ""
        stderr = "fixture"

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        captured["command"] = command
        captured.update(kwargs)
        return Completed()

    monkeypatch.setattr(relay.subprocess, "run", fake_run)
    result = relay._default_launcher(  # noqa: SLF001
        relay.downstream_command(configured.resolved()), configured.resolved()
    )

    assert result.returncode == 2
    assert captured["shell"] is False
    assert captured["stdin"] is subprocess.DEVNULL
    if os.name == "nt":
        assert captured["creationflags"] == subprocess.CREATE_NO_WINDOW


def test_downstream_detach_timeout_records_unknown_outcome_and_never_retries(
    configured: relay.RelayConfig,
) -> None:
    calls: list[list[str]] = []

    def timeout(
        command: Sequence[str], _config: relay.RelayConfig
    ) -> relay.LaunchResult:
        calls.append(list(command))
        raise subprocess.TimeoutExpired(list(command), timeout=1.0)

    instance = relay.HoldoutCampaignOnceRelay(
        configured,
        launcher=timeout,
        prevent_sleep=lambda _enabled: None,
    )
    with pytest.raises(relay.HandoffRelayError, match="aucun nouvel essai"):
        instance.execute()
    with pytest.raises(relay.HandoffRelayError, match="déjà été réservée"):
        instance.execute()

    assert len(calls) == 1
    status = relay._read_json(configured.handoff_supervision_dir / "status.json")  # noqa: SLF001
    assert status["status"] == "downstream_detach_timeout_outcome_unknown_no_retry"
    assert status["downstream_started"] is None


def test_sleep_prevention_failure_blocks_launch(configured: relay.RelayConfig) -> None:
    calls: list[list[str]] = []

    def fail(_enabled: bool) -> None:
        raise OSError("sleep inhibitor unavailable")

    def launch(
        command: Sequence[str], _config: relay.RelayConfig
    ) -> relay.LaunchResult:
        calls.append(list(command))
        return _receipt(_config)

    instance = relay.HoldoutCampaignOnceRelay(
        configured,
        launcher=launch,
        prevent_sleep=fail,
    )
    with pytest.raises(OSError, match="sleep inhibitor"):
        instance.execute()
    assert calls == []
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()


def test_background_parent_releases_lock_before_spawning_child(
    configured: relay.RelayConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = argparse.Namespace(
        **configured.__dict__,
        background=True,
        foreground_child=False,
    )
    commands: list[list[str]] = []

    class Process:
        pid = os.getpid()

    def popen(command: Sequence[str], **_kwargs: object) -> Process:
        commands.append(list(command))
        with relay._exclusive_lock(  # noqa: SLF001
            configured.handoff_supervision_dir / ".handoff.lock"
        ):
            pass
        return Process()

    monkeypatch.setattr(relay.subprocess, "Popen", popen)
    payload = relay.start_background(args)

    assert payload["status"] == "watcher_started"
    assert payload["pid"] == os.getpid()
    relay._verify_signature(  # noqa: SLF001
        payload, "background_signature", "fixture background receipt"
    )
    assert (
        relay._read_json(  # noqa: SLF001
            configured.handoff_supervision_dir / "watcher_detached.json"
        )
        == payload
    )
    assert commands[0].count("--foreground-child") == 1
    assert commands[0].count("--background-reservation-token") == 1
    assert "--background" not in commands[0]
    child_args = relay._parser().parse_args(commands[0][3:])  # noqa: SLF001
    assert child_args.foreground_child is True
    assert relay._is_sha256(child_args.background_reservation_token)  # noqa: SLF001
    assert child_args.repo == configured.repo.resolve()
    assert child_args.downstream_supervision_dir == (
        configured.downstream_supervision_dir.resolve()
    )
    assert not (configured.handoff_supervision_dir / "launch_reservation.json").exists()

    inventory = relay._assert_integrity(configured.resolved())  # noqa: SLF001
    child = relay.HoldoutCampaignOnceRelay(
        configured,
        background_reservation_token=payload["reservation_token"],
    )
    with relay._exclusive_lock(  # noqa: SLF001
        configured.handoff_supervision_dir / ".handoff.lock"
    ):
        child._prepare(inventory)  # noqa: SLF001
    with pytest.raises(relay.HandoffRelayError, match="parent --background"):
        relay.HoldoutCampaignOnceRelay(configured)._prepare(inventory)  # noqa: SLF001


def test_background_spawn_failure_is_signed_and_cannot_be_retried(
    configured: relay.RelayConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = argparse.Namespace(
        **configured.__dict__,
        background=True,
        foreground_child=False,
        background_reservation_token="",
    )

    def fail_popen(_command: Sequence[str], **_kwargs: object) -> None:
        raise OSError("synthetic spawn failure")

    monkeypatch.setattr(relay.subprocess, "Popen", fail_popen)
    with pytest.raises(OSError, match="synthetic"):
        relay.start_background(args)

    receipt = relay._read_json(  # noqa: SLF001
        configured.handoff_supervision_dir / "watcher_detached.json"
    )
    relay._verify_signature(  # noqa: SLF001
        receipt, "background_signature", "fixture background failure"
    )
    assert receipt["status"] == "watcher_start_failed_no_retry"
    assert relay._is_sha256(receipt["reservation_token"])  # noqa: SLF001
    with pytest.raises(relay.HandoffRelayError, match="parent --background"):
        relay.start_background(args)
