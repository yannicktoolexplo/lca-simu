from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v4 as relay,
)


REPO = Path(__file__).resolve().parents[4]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _config(tmp_path: Path, **overrides: object) -> relay.RelayConfig:
    upstream = tmp_path / "upstream"
    plan = upstream / "plan"
    run = upstream / "run"
    calibration_supervision = upstream / "calibration_supervision"
    sidecar = upstream / "sidecar"
    for path in (plan, run, calibration_supervision, sidecar):
        path.mkdir(parents=True, exist_ok=True)
    values: dict[str, object] = {
        "repo": REPO,
        "calibration_plan_dir": plan,
        "calibration_run_dir": run,
        "calibration_supervision_dir": calibration_supervision,
        "sidecar_dir": sidecar,
        "bridge_json": tmp_path / "outputs" / "bridge.json",
        "campaign_root": tmp_path / "outputs" / "campaign",
        "results_dir": tmp_path / "outputs" / "results",
        "lot_replay_root": tmp_path / "outputs" / "lots",
        "dashboard_html": tmp_path / "outputs" / "dashboard.html",
        "final_html": None,
        "supervision_dir": tmp_path / "outputs" / "supervision",
        "relay_poll_seconds": 0.1,
        "max_wait_hours": 1.0,
    }
    values.update(overrides)
    return relay.RelayConfig(**values).resolved()  # type: ignore[arg-type]


def _accepted_calibration(config: relay.RelayConfig) -> None:
    _write_json(
        config.calibration_supervision_dir / "status.json",
        {
            "schema_version": relay.CALIBRATION_RELAY_SCHEMA,
            "stage": relay.CALIBRATION_ACCEPTED_STAGE,
            "accepted": True,
        },
    )
    _write_json(
        config.calibration_run_dir / "holdout_result.json",
        {
            "status": relay.CALIBRATION_HOLDOUT_STATUS,
            "accepted": True,
            "state_summaries": {state: {} for state in relay.EXPECTED_STATE_IDS},
        },
    )


def _prepared(tmp_path: Path, **overrides: object) -> relay.FullCampaignRelay:
    instance = relay.FullCampaignRelay(_config(tmp_path, **overrides))
    instance.prepare()
    return instance


def test_prepare_pins_sources_and_refuses_contract_drift(tmp_path: Path) -> None:
    instance = _prepared(tmp_path)
    contract = json.loads(instance.contract_path.read_text(encoding="utf-8"))
    assert contract["scientific_contract"] == {
        "accepted_holdout_case_count": 90,
        "availability_incident_included": False,
        "capacity_incident_included": False,
        "forced_top_three": False,
        "historical_incident_probability_estimated": False,
        "isolated_shard_count": 18,
        "mandatory_non_reusable_op93_smoke_rows": 3,
        "maximum_signed_lot_replays": 3,
        "operating_point_holdout_reruns_in_campaign": 0,
        "operating_point_ids": ["op_100", "op_93", "op_80"],
        "paired_repetitions_per_cell": 30,
        "quality_incident_included": False,
        "reported_campaign_row_count": 3330,
        "stock_incident_included": False,
        "supplier_incident_mechanisms": [
            "transport_delay",
            "planned_delivery_shortfall",
        ],
        "target_discovery_engine_runs": 3,
    }
    assert len(contract["source_inventory"]) == len(relay.PINNED_MODULES) + 1
    changed = _config(tmp_path, parallel_shards=1)
    with pytest.raises(relay.FullCampaignRelayError, match="contrat existant diffère"):
        relay.FullCampaignRelay(changed).prepare()


def test_legacy_archive_links_are_hash_pinned(tmp_path: Path) -> None:
    legacy = tmp_path / "archive" / "old.html"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("ancienne page", encoding="utf-8")
    instance = _prepared(tmp_path, legacy_risk_html=legacy)
    inventory = instance.contract["legacy_html_inventory"]
    assert inventory == [
        {
            "role": "legacy_risk_html",
            "path": str(legacy.resolve()),
            "size_bytes": legacy.stat().st_size,
            "sha256": relay.sha256_file(legacy),
        }
    ]
    legacy.write_text("page modifiée", encoding="utf-8")
    with pytest.raises(relay.FullCampaignRelayError, match="archive a changé"):
        instance._validate_legacy_html_inventory()


def test_wait_for_calibration_accepts_only_final_official_holdout(
    tmp_path: Path,
) -> None:
    instance = _prepared(tmp_path)
    _accepted_calibration(instance.config)
    result = instance.wait_for_calibration()
    assert result["accepted"] is True
    assert instance.status["progress"] == {"states": 3, "holdout_cases": 90}
    assert instance.status["artifacts"]["calibration_holdout"]["sha256"]


def test_final_calibration_status_cannot_claim_an_unaccepted_holdout(
    tmp_path: Path,
) -> None:
    instance = _prepared(tmp_path)
    _write_json(
        instance.config.calibration_supervision_dir / "status.json",
        {
            "schema_version": relay.CALIBRATION_RELAY_SCHEMA,
            "stage": relay.CALIBRATION_ACCEPTED_STAGE,
            "accepted": False,
        },
    )
    with pytest.raises(relay.FullCampaignRelayError, match="accepted=true"):
        instance.wait_for_calibration()


def test_rejected_holdout_payload_blocks_campaign_even_if_relay_says_accepted(
    tmp_path: Path,
) -> None:
    instance = _prepared(tmp_path)
    _accepted_calibration(instance.config)
    result_path = instance.config.calibration_run_dir / "holdout_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["accepted"] = False
    _write_json(result_path, result)
    with pytest.raises(relay.FullCampaignRelayError, match="30 graines fraîches"):
        instance.wait_for_calibration()


@pytest.mark.parametrize(
    "stage",
    ["scientific_no_go_after_development", "scientific_no_go_after_holdout"],
)
def test_wait_for_calibration_stops_on_scientific_no_go(
    tmp_path: Path, stage: str
) -> None:
    instance = _prepared(tmp_path)
    _write_json(
        instance.config.calibration_supervision_dir / "status.json",
        {"schema_version": relay.CALIBRATION_RELAY_SCHEMA, "stage": stage},
    )
    with pytest.raises(relay.ScientificNoGo, match="aucune campagne incident"):
        instance.wait_for_calibration()


def test_run_step_is_idempotent_and_can_force_a_validator(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    proof = tmp_path / "proof.txt"

    def executor(command: relay.Sequence[str], _cwd: Path, _log: Path) -> int:
        calls.append(list(command))
        proof.write_text(str(len(calls)), encoding="utf-8")
        return 0

    instance = relay.FullCampaignRelay(_config(tmp_path), command_executor=executor)
    instance.prepare()
    kwargs = {
        "step": "synthetic",
        "command": ["python", "-m", "synthetic"],
        "completion_check": proof.is_file,
        "message_fr": "Test synthétique.",
    }
    instance.run_step(**kwargs)
    instance.run_step(**kwargs)
    assert len(calls) == 1
    instance.run_step(**kwargs, run_even_if_complete=True)
    assert len(calls) == 2
    assert instance.status["steps"]["synthetic"]["status"] == "complete_validated"


def test_campaign_plan_contract_rejects_forbidden_incident(tmp_path: Path) -> None:
    instance = _prepared(tmp_path)
    root = instance.config.campaign_root
    root.mkdir(parents=True)
    manifest = {
        "status": "planned",
        "expected_counts": {
            "auxiliary_discovery_runs": 3,
            "total_rows": 3330,
            "shard_count": 18,
        },
        "mechanisms": [{"key": value} for value in relay.EXPECTED_MECHANISMS],
        "quality_branch_included": False,
        "quality_incident_included": False,
        "availability_incident_included": False,
        "capacity_incident_included": False,
        "stock_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "historical_incident_probability_estimated": False,
    }
    _write_json(root / "campaign_manifest.json", manifest)
    (root / "shard_plan.csv").write_text(
        "shard_id\n" + "".join(f"s{index}\n" for index in range(18)),
        encoding="utf-8",
    )
    assert instance._campaign_plan_ready() is True
    manifest["quality_incident_included"] = True
    _write_json(root / "campaign_manifest.json", manifest)
    with pytest.raises(relay.FullCampaignRelayError, match="quality_incident"):
        instance._campaign_plan_ready()


def test_exact_pipeline_commands_and_no_launcher_detach(tmp_path: Path) -> None:
    instance = _prepared(tmp_path)
    calls: list[dict[str, object]] = []

    def record(**kwargs: object) -> None:
        calls.append(kwargs)
        command = list(kwargs["command"])  # type: ignore[arg-type]
        if relay.DASHBOARD_MODULE in command:
            output = Path(command[command.index("--output-html") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("synthetic", encoding="utf-8")

    instance.run_step = record  # type: ignore[method-assign]
    instance._record_artifact = lambda *_args: None  # type: ignore[method-assign]
    instance._dashboard_path_ready = lambda path: path.is_file()  # type: ignore[method-assign]

    instance.build_and_validate_bridge()
    instance.plan_campaign()
    instance.launch_campaign()
    instance.finalize_campaign()
    instance.build_dashboard()

    commands = [entry["command"] for entry in calls]
    joined = "\n".join(" ".join(command) for command in commands)  # type: ignore[arg-type]
    assert f"-m {relay.BRIDGE_MODULE} build" in joined
    assert f"-m {relay.BRIDGE_MODULE} validate --path" in joined
    assert f"-m {relay.CAMPAIGN_MODULE} --mode plan" in joined
    assert f"-m {relay.LAUNCHER_MODULE} --campaign-root" in joined
    assert f"-m {relay.FINALIZER_MODULE} --campaign-root" in joined
    assert f"-m {relay.DASHBOARD_MODULE} --results-dir" in joined
    launcher = next(
        command
        for command in commands
        if relay.LAUNCHER_MODULE in command  # type: ignore[operator]
    )
    assert "--detach" not in launcher
    assert "quality" not in joined.casefold()
    assert "availability" not in joined.casefold()
    assert "capacity" not in joined.casefold()
    forced_steps = {
        entry["step"] for entry in calls if entry.get("run_even_if_complete") is True
    }
    assert {"validation_pont_v4", "planification_campagne"} <= forced_steps


def test_first_foreground_prepare_accepts_its_own_lock_file(tmp_path: Path) -> None:
    instance = relay.FullCampaignRelay(_config(tmp_path))
    with relay._relay_lock(instance.config.supervision_dir / ".relay.lock"):
        instance.prepare()
    assert instance.contract_path.is_file()


def test_missing_sidecar_directory_does_not_block_contract(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.sidecar_dir.rmdir()
    instance = relay.FullCampaignRelay(config)
    instance.prepare()
    assert instance.process_optional_curves() is False


def test_curve_capture_failure_is_visible_but_non_blocking(tmp_path: Path) -> None:
    instance = _prepared(tmp_path)
    assert instance.process_optional_curves() is False
    status = instance.status["nominal_curves"]
    assert status["status"] == "curve_capture_failed_or_incomplete"
    assert status["campaign_incident_results_remain_valid"] is True


def test_external_sidecar_watcher_is_observed_but_never_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = _prepared(tmp_path, sidecar_watcher_pid=8268)
    monkeypatch.setattr(
        relay, "_process_running", lambda process_id: process_id == 8268
    )
    instance.observe_sidecar_watcher()
    status = instance.status["sidecar_watcher"]
    assert status["status"] == "watching"
    assert status["pid"] == 8268
    assert status["process_running"] is True
    assert status["owned_or_restarted_by_relay"] is False
    assert status["incident_campaign_blocked"] is False


def test_stopped_sidecar_watcher_does_not_block_incident_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = _prepared(tmp_path, sidecar_watcher_pid=8268)
    monkeypatch.setattr(relay, "_process_running", lambda _process_id: False)
    instance.observe_sidecar_watcher()
    assert (
        instance.status["sidecar_watcher"]["status"] == "not_running_before_inventory"
    )


def test_complete_sidecar_inventory_is_strictly_signed(tmp_path: Path) -> None:
    instance = _prepared(tmp_path)
    unsigned = {
        "schema_version": "synthetic",
        "status": "complete",
        "case_count": 90,
        "cases": [{"seed": index} for index in range(90)],
    }
    inventory = {
        **unsigned,
        "inventory_signature": relay.stable_sha256(unsigned),
    }
    path = instance.config.sidecar_dir / "capture_inventory.json"
    _write_json(path, inventory)
    assert instance._sidecar_inventory_ready() is True
    inventory["case_count"] = 89
    _write_json(path, inventory)
    with pytest.raises(relay.FullCampaignRelayError, match="Signature incohérente"):
        instance._sidecar_inventory_ready()


@pytest.mark.parametrize(("curves_ok", "lot_count"), [(False, 0), (True, 2)])
def test_final_composer_receives_only_valid_optional_inputs(
    tmp_path: Path, curves_ok: bool, lot_count: int
) -> None:
    final_html = tmp_path / "outputs" / "final.html"
    instance = _prepared(tmp_path, final_html=final_html)
    instance.status["nominal_curves"] = {
        "status": (
            "complete_validated" if curves_ok else "curve_capture_failed_or_incomplete"
        )
    }
    calls: list[dict[str, object]] = []
    instance.run_step = lambda **kwargs: calls.append(kwargs)  # type: ignore[method-assign]
    instance._record_artifact = lambda *_args: None  # type: ignore[method-assign]
    instance.build_final_delivery(lot_count)
    build = list(calls[0]["command"])  # type: ignore[arg-type]
    validate = list(calls[1]["command"])  # type: ignore[arg-type]
    assert build[:4] == [
        relay.sys.executable,
        "-m",
        relay.FINAL_DELIVERY_MODULE,
        "build",
    ]
    assert ("--curves-dir" in build) is curves_ok
    assert ("--lot-replay-root" in build) is bool(lot_count)
    assert validate[3:5] == ["validate", "--path"]
    assert calls[1]["run_even_if_complete"] is True


def test_final_composer_receives_only_validated_action_results(
    tmp_path: Path,
) -> None:
    action_root = tmp_path / "outputs" / "actions"
    instance = _prepared(
        tmp_path,
        final_html=tmp_path / "outputs" / "final.html",
        action_replay_root=action_root,
    )
    instance.status["nominal_curves"] = {"status": "curve_capture_failed_or_incomplete"}
    instance.status["action_replay"] = {"status": "complete_validated"}
    calls: list[dict[str, object]] = []
    instance.run_step = lambda **kwargs: calls.append(kwargs)  # type: ignore[method-assign]
    instance._record_artifact = lambda *_args: None  # type: ignore[method-assign]
    instance.build_final_delivery(0)
    build = list(calls[0]["command"])  # type: ignore[arg-type]
    assert build[build.index("--action-results-root") + 1] == str(action_root)


def test_action_replay_uses_signed_references_and_executes_only_action_arms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_priority_action_replay_v4 as actions,
    )

    action_root = tmp_path / "outputs" / "actions"
    instance = _prepared(tmp_path, action_replay_root=action_root)
    instance._lot_selection = lambda: [{"dossier_id": "synthetic"}]  # type: ignore[method-assign]
    calls: list[dict[str, object]] = []
    instance.run_step = lambda **kwargs: calls.append(kwargs)  # type: ignore[method-assign]
    instance._record_artifact = lambda *_args: None  # type: ignore[method-assign]
    action_root.mkdir(parents=True)
    _write_json(action_root / "action_replay_validation.json", {})
    monkeypatch.setattr(
        actions,
        "validate_action_results",
        lambda _root: ({}, {"status": "complete_validated"}),
    )

    instance.process_optional_action_replay()

    commands = [list(call["command"]) for call in calls]  # type: ignore[arg-type]
    assert [command[3] for command in commands] == [
        "plan",
        "run",
        "run",
        "finalize",
        "validate",
    ]
    plan = commands[0]
    assert plan[plan.index("--reference-mode") + 1] == "signed_reference"
    assert "--execute" not in commands[1]
    assert "--execute" in commands[2]
    assert commands[2][commands[2].index("--workers") + 1] == "2"
    assert instance.status["action_replay"]["reference_engine_reruns"] == 0
    assert instance.status["action_replay"]["closed_loop_claimed"] is False


def test_terminal_action_product_is_reopened_and_hash_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_priority_action_replay_v4 as actions,
    )

    action_root = tmp_path / "outputs" / "actions"
    instance = _prepared(tmp_path, action_replay_root=action_root)
    validation_path = action_root / "action_replay_validation.json"
    _write_json(validation_path, {"synthetic": True})
    instance.status["nominal_curves"] = {"status": "curve_capture_failed_or_incomplete"}
    instance.status["action_replay"] = {
        "status": "complete_validated",
        "validation_sha256": relay.sha256_file(validation_path),
    }
    monkeypatch.setattr(
        actions,
        "validate_action_results",
        lambda _root: ({}, {"status": "complete_validated"}),
    )
    instance.revalidate_published_optional_products()
    validation_path.write_text("modified", encoding="utf-8")
    with pytest.raises(relay.FullCampaignRelayError, match="a changé"):
        instance.revalidate_published_optional_products()


def test_partial_replay_root_is_preserved_not_deleted(tmp_path: Path) -> None:
    instance = _prepared(tmp_path)
    root = instance.config.lot_replay_root
    root.mkdir(parents=True)
    marker = root / "partial.txt"
    marker.write_text("keep me", encoding="utf-8")
    destination = instance._archive_incomplete_replay_root("test")
    assert not root.exists()
    assert (destination / "partial.txt").read_text(encoding="utf-8") == "keep me"
    assert instance.status["recovery_archives"][-1]["preserved_at"] == str(destination)


def test_unowned_partial_replay_root_is_never_moved_or_overwritten(
    tmp_path: Path,
) -> None:
    instance = _prepared(tmp_path)
    root = instance.config.lot_replay_root
    root.mkdir(parents=True)
    marker = root / "user-result.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(relay.FullCampaignRelayError, match="préexistante"):
        instance._replay_plan_ready(1)
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_action_replay_detection_never_guesses_an_unfrozen_cli(tmp_path: Path) -> None:
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    config = _config(
        tmp_path,
        repo=fake_repo,
        action_replay_mode="auto",
        action_replay_root=tmp_path / "outputs" / "actions",
    )
    instance = relay.FullCampaignRelay(config)
    instance.status = {"steps": {}, "artifacts": {}}
    instance.status_path.parent.mkdir(parents=True, exist_ok=True)
    instance.contract = {"contract_signature": "x" * 64}
    instance.process_optional_action_replay()
    assert instance.status["action_replay"]["status"] == "module_not_available"


def test_crashed_action_plan_tree_is_hash_inventoried_and_preserved(
    tmp_path: Path,
) -> None:
    action_root = tmp_path / "outputs" / "actions"
    instance = _prepared(tmp_path, action_replay_root=action_root)
    instance.status["steps"]["planification_actions"] = {
        "status": "running",
        "attempts": [{"started_at_utc": "synthetic-crash"}],
    }
    source = action_root / "inputs" / "case.csv"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"signed synthetic input\n")
    expected_hash = relay.sha256_file(source)

    preserved = instance._archive_incomplete_action_root("plan_incomplet")

    assert not action_root.exists()
    assert (preserved / "inputs" / "case.csv").read_bytes() == (
        b"signed synthetic input\n"
    )
    recovery = instance.status["recovery_archives"][-1]
    inventory_path = Path(recovery["inventory_path"])
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    relay._verify_signed_json(
        inventory, "inventory_signature", "inventaire synthétique"
    )
    assert inventory["files"] == [
        {
            "relative_path": "inputs/case.csv",
            "size_bytes": len(b"signed synthetic input\n"),
            "sha256": expected_hash,
        }
    ]
    assert recovery["inventory_sha256"] == relay.sha256_file(inventory_path)


def test_signed_action_plan_without_commands_is_preserved_then_replanned(
    tmp_path: Path,
) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_priority_action_replay_v4 as actions,
    )

    action_root = tmp_path / "outputs" / "actions"
    instance = _prepared(tmp_path, action_replay_root=action_root)
    instance.status["steps"]["planification_actions"] = {
        "status": "running",
        "attempts": [{"started_at_utc": "synthetic-crash"}],
    }
    unsigned = {
        "schema_version": actions.PLAN_SCHEMA_VERSION,
        "replay_root": str(action_root.resolve()),
    }
    plan = {**unsigned, "plan_signature": actions.stable_sha256(unsigned)}
    _write_json(action_root / "action_replay_plan.json", plan)

    assert instance._action_plan_publication_ready(actions, action_root) is False
    assert not action_root.exists()
    recovery = instance.status["recovery_archives"][-1]
    preserved = Path(recovery["preserved_at"])
    assert (preserved / "action_replay_plan.json").is_file()
    assert recovery["reason"] == "publication_plan_incomplète"


def test_unowned_action_tree_is_never_archived(tmp_path: Path) -> None:
    action_root = tmp_path / "outputs" / "actions"
    instance = _prepared(tmp_path, action_replay_root=action_root)
    marker = action_root / "user-result.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(relay.FullCampaignRelayError, match="préexistante"):
        instance._archive_incomplete_action_root("plan_incomplet")
    assert marker.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("fragment_kind", ["html", "manifest"])
def test_crash_between_final_html_and_manifest_is_preserved_and_resumable(
    tmp_path: Path, fragment_kind: str
) -> None:
    final_html = tmp_path / "outputs" / "final.html"
    instance = _prepared(tmp_path, final_html=final_html)
    instance.status["steps"]["livrable_final_autonome"] = {
        "status": "running",
        "attempts": [{"started_at_utc": "synthetic-crash"}],
    }
    fragment = (
        final_html
        if fragment_kind == "html"
        else Path(str(final_html) + ".manifest.json")
    )
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_bytes(f"partial-{fragment_kind}".encode())
    expected_hash = relay.sha256_file(fragment)

    assert instance._final_delivery_ready(recover_owned_partial=True) is False

    assert not fragment.exists()
    recovery = instance.status["recovery_archives"][-1]
    preserved = Path(recovery["preserved_at"])
    assert relay.sha256_file(preserved) == expected_hash
    inventory = json.loads(Path(recovery["inventory_path"]).read_text(encoding="utf-8"))
    relay._verify_signed_json(inventory, "inventory_signature", "fragment synthétique")
    assert inventory["fragments"][0]["sha256"] == expected_hash


def test_unowned_partial_final_delivery_is_not_moved(tmp_path: Path) -> None:
    final_html = tmp_path / "outputs" / "final.html"
    instance = _prepared(tmp_path, final_html=final_html)
    final_html.parent.mkdir(parents=True, exist_ok=True)
    final_html.write_text("user page", encoding="utf-8")
    with pytest.raises(relay.FullCampaignRelayError, match="préexistant"):
        instance._final_delivery_ready(recover_owned_partial=True)
    assert final_html.read_text(encoding="utf-8") == "user page"


def test_execute_order_starts_campaign_before_optional_curves(tmp_path: Path) -> None:
    instance = relay.FullCampaignRelay(_config(tmp_path))
    calls: list[str] = []
    instance.prepare = lambda: (
        setattr(
            instance,
            "status",
            {"status": "running", "steps": {}, "artifacts": {}, "active_command": {}},
        ),
        setattr(instance, "contract", {"scientific_contract": {}}),
    )  # type: ignore[method-assign]
    for name in (
        "wait_for_calibration",
        "build_and_validate_bridge",
        "plan_campaign",
        "launch_campaign",
        "finalize_campaign",
        "build_dashboard",
    ):
        setattr(instance, name, lambda name=name: calls.append(name))
    instance._lot_selection = lambda: []  # type: ignore[method-assign]
    instance.run_lot_replays = lambda _selection: calls.append("run_lot_replays")  # type: ignore[method-assign]
    instance.process_optional_action_replay = lambda: calls.append("actions")  # type: ignore[method-assign]

    def curves() -> bool:
        calls.append("curves")
        instance.status["nominal_curves"] = {
            "status": "curve_capture_failed_or_incomplete"
        }
        return False

    instance.process_optional_curves = curves  # type: ignore[method-assign]
    instance.build_final_delivery = lambda _count: calls.append("delivery")  # type: ignore[method-assign]
    instance._write_status = lambda: None  # type: ignore[method-assign]
    instance.update_status = lambda *args, **kwargs: instance.status.update(  # type: ignore[method-assign]
        {"stage": args[0], "status": kwargs.get("status", "running")}
    )
    assert instance.execute() == 0
    assert calls.index("launch_campaign") < calls.index("curves")
    assert calls == [
        "wait_for_calibration",
        "build_and_validate_bridge",
        "plan_campaign",
        "launch_campaign",
        "finalize_campaign",
        "build_dashboard",
        "run_lot_replays",
        "actions",
        "curves",
        "delivery",
    ]
    assert instance.status["status"] == "complete_with_limits"


def test_child_command_keeps_detach_internal_and_all_paths_explicit(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    args = SimpleNamespace(
        repo=config.repo,
        calibration_plan_dir=config.calibration_plan_dir,
        calibration_run_dir=config.calibration_run_dir,
        calibration_supervision_dir=config.calibration_supervision_dir,
        sidecar_dir=config.sidecar_dir,
        sidecar_watcher_pid=8268,
        bridge_json=config.bridge_json,
        campaign_root=config.campaign_root,
        results_dir=config.results_dir,
        lot_replay_root=config.lot_replay_root,
        dashboard_html=config.dashboard_html,
        final_html=None,
        action_replay_root=None,
        supervision_dir=config.supervision_dir,
        legacy_risk_html=None,
        legacy_control_html=None,
        parallel_shards=2,
        workers_per_shard=2,
        launcher_poll_seconds=5.0,
        relay_poll_seconds=30.0,
        max_wait_hours=120.0,
        action_replay_mode="auto",
    )
    command = relay._child_command(args)
    assert command[:3] == [relay.sys.executable, "-m", relay.MODULE_NAME]
    assert command.count("--detached-child") == 1
    assert "--detach" not in command
    assert command[command.index("--action-replay-mode") + 1] == "auto"
    assert command[command.index("--sidecar-watcher-pid") + 1] == "8268"
