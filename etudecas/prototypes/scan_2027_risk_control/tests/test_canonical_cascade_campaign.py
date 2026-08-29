from __future__ import annotations

import csv
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

import pytest

from etudecas.prototypes.scan_2027_risk_control import canonical_cascade_campaign
from etudecas.prototypes.scan_2027_risk_control.canonical_cascade_campaign import (
    CascadeCampaignError,
    _action_evidence,
    _cost_metrics,
    _load_measurement_start_hashes,
    _risk_evidence,
    expand_variants,
    run_campaign,
    validate_only,
)


SCAN_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = SCAN_DIR / "config" / "canonical_cascade_campaign_config.json"
ENGINE_PATH = (
    SCAN_DIR.parents[1] / "simulation" / "engine" / "run_first_simulation.py"
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _command_flag_values(command: list[str], flag: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(command):
        if token == flag and index + 1 < len(command):
            values.append(command[index + 1])
        elif token.startswith(f"{flag}="):
            values.append(token.split("=", 1)[1])
    return values


def test_real_config_defines_two_complete_additive_comparisons() -> None:
    validation = validate_only(CONFIG_PATH)
    assert validation["valid"] is True
    assert validation["cascade_count"] == 2
    assert validation["solution_count"] == 14
    assert validation["variant_count"] == 18

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    variants = expand_variants(config)
    by_cascade: dict[str, list[object]] = {}
    for variant in variants:
        by_cascade.setdefault(variant.cascade_id, []).append(variant)
    assert set(by_cascade) == {
        "quality_quarantine_021081_to_268967",
        "lead_time_delay_338929_to_268091",
    }
    assert all(len(rows) == 9 for rows in by_cascade.values())
    assert all(
        {row.case_type for row in rows}
        == {"normal", "incident_no_action", "incident_with_solution"}
        for rows in by_cascade.values()
    )

    lookup = {(row.cascade_id, row.solution_id): row for row in variants}
    native_second_source = lookup[
        ("quality_quarantine_021081_to_268967", "second_supplier")
    ]
    assert native_second_source.lever_fidelity == "native_graph"
    assert native_second_source.approximation_levers == ()
    delay_proxy = lookup[
        ("lead_time_delay_338929_to_268091", "second_supplier_proxy")
    ]
    assert delay_proxy.lever_fidelity == "approximation"
    assert delay_proxy.approximation_levers


def test_positive_customer_exposure_guard_must_be_boolean(tmp_path: Path) -> None:
    validation = validate_only(CONFIG_PATH)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["scientific_guards"][
        "require_positive_incremental_customer_backlog"
    ] = "false"
    config_path = tmp_path / "invalid-guard.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(CascadeCampaignError, match="must be boolean"):
        validate_only(config_path, graph_path=Path(validation["graph_path"]))


def test_physical_incident_absorbed_before_customer_remains_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_hash = "a" * 64
    components = json.dumps({"inventory": "b" * 64})
    effects = json.dumps(
        {
            "lead_time_extra_days": {
                "unique_applied_flow_rows": 4,
                "effect_sum": 140,
            }
        }
    )
    rows = [
        {
            "cascade_id": "delay",
            "variant_id": "normal",
            "seed": 9,
            "status": "ok",
            "result_dir": "normal",
            "measurement_start_state_sha256": state_hash,
            "measurement_start_component_sha256_json": components,
        },
        {
            "cascade_id": "delay",
            "variant_id": "incident_no_action",
            "seed": 9,
            "status": "ok",
            "result_dir": "untreated",
            "supplier_risk_applied_event_ids": "delay-event",
            "supplier_risk_applied_row_count": 4,
            "supplier_risk_effects_json": effects,
            "measurement_start_state_sha256": state_hash,
            "measurement_start_component_sha256_json": components,
        },
        {
            "cascade_id": "delay",
            "variant_id": "incident_expedite",
            "seed": 9,
            "status": "ok",
            "result_dir": "solution",
            "measurement_start_state_sha256": state_hash,
            "measurement_start_component_sha256_json": components,
        },
    ]
    config = {
        "scientific_guards": {
            "require_positive_incremental_customer_backlog": False
        },
        "cascades": [
            {
                "id": "delay",
                "customer_id": "C-XXXXX",
                "finished_item_id": "item:268091",
                "incident": {
                    "risk_events": [
                        {
                            "event_id": "delay-event",
                            "risk_type": "lead_time_extra_days",
                        }
                    ]
                },
            }
        ],
    }
    zero_backlog = {
        day: {"demand": 10.0, "served": 10.0, "backlog": 0.0}
        for day in range(3)
    }
    monkeypatch.setattr(
        canonical_cascade_campaign,
        "customer_daily_series",
        lambda *args, **kwargs: zero_backlog,
    )

    failures = canonical_cascade_campaign._validate_physical_campaign_rows(
        rows, config=config, expected_days=3
    )

    assert failures == 0
    assert all(row["status"] == "ok" for row in rows)
    assert rows[1]["incident_validation_status"] == (
        "physically_applied_no_customer_exposure"
    )
    assert rows[2]["incident_validation_status"] == (
        "paired_untreated_incident_no_customer_exposure"
    )


def test_incident_with_zero_physical_effect_remains_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_hash = "a" * 64
    components = json.dumps({"inventory": "b" * 64})
    rows = [
        {
            "cascade_id": "delay",
            "variant_id": "normal",
            "seed": 9,
            "status": "ok",
            "result_dir": "normal",
            "measurement_start_state_sha256": state_hash,
            "measurement_start_component_sha256_json": components,
        },
        {
            "cascade_id": "delay",
            "variant_id": "incident_no_action",
            "seed": 9,
            "status": "ok",
            "result_dir": "untreated",
            "supplier_risk_applied_event_ids": "delay-event",
            "supplier_risk_applied_row_count": 4,
            "supplier_risk_effects_json": json.dumps(
                {
                    "lead_time_extra_days": {
                        "unique_applied_flow_rows": 4,
                        "effect_sum": 0,
                    }
                }
            ),
            "measurement_start_state_sha256": state_hash,
            "measurement_start_component_sha256_json": components,
        },
    ]
    config = {
        "scientific_guards": {
            "require_positive_incremental_customer_backlog": False
        },
        "cascades": [
            {
                "id": "delay",
                "customer_id": "C-XXXXX",
                "finished_item_id": "item:268091",
                "incident": {
                    "risk_events": [
                        {
                            "event_id": "delay-event",
                            "risk_type": "lead_time_extra_days",
                        }
                    ]
                },
            }
        ],
    }
    monkeypatch.setattr(
        canonical_cascade_campaign,
        "customer_daily_series",
        lambda *args, **kwargs: {},
    )

    failures = canonical_cascade_campaign._validate_physical_campaign_rows(
        rows, config=config, expected_days=3
    )

    assert failures == 1
    assert rows[1]["status"] == "invalid_incident"
    assert rows[1]["incident_validation_status"] == "incident_not_physically_applied"
    assert "without positive physical application evidence" in rows[1]["error"]


def test_pair_scoped_j0_args_are_shared_within_but_not_across_cascades() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = copy.deepcopy(config)
    config["cascades"][0]["paired_engine_args"] = [
        "--measurement-start-stock-scale-csv",
        "quality-j0.csv",
    ]
    config["cascades"][1]["paired_engine_args"] = [
        "--measurement-start-stock-scale-csv=delay-stock-j0.csv",
        "--measurement-start-in-transit-scale-csv",
        "delay-pipeline-j0.csv",
    ]

    variants = expand_variants(config)
    quality_args = {
        row.engine_args
        for row in variants
        if row.cascade_id == "quality_quarantine_021081_to_268967"
    }
    delay_args = {
        row.engine_args
        for row in variants
        if row.cascade_id == "lead_time_delay_338929_to_268091"
    }

    assert quality_args == {
        ("--measurement-start-stock-scale-csv", "quality-j0.csv")
    }
    assert delay_args == {
        (
            "--measurement-start-stock-scale-csv=delay-stock-j0.csv",
            "--measurement-start-in-transit-scale-csv",
            "delay-pipeline-j0.csv",
        )
    }


def test_pair_scoped_j0_args_reject_non_initialization_flags() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["cascades"][0]["paired_engine_args"] = ["--warmup-days", "10"]

    with pytest.raises(CascadeCampaignError, match="not a permitted pair-scoped"):
        expand_variants(config)


def test_prepare_only_validates_schedules_and_preserves_engine(tmp_path: Path) -> None:
    engine_digest = _digest(ENGINE_PATH)
    output = tmp_path / "new-cascade-campaign"
    manifest_path = run_campaign(
        config_path=CONFIG_PATH,
        output_dir=output,
        seeds=[330281],
        artifact_profile="compact",
        prepare_only=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "prepared_only"
    assert manifest["run_count"] == 18
    assert manifest["failure_count"] == 0
    assert manifest["common_random_numbers"] is True
    assert manifest["state_dependent_risks"] is False
    rows = _read_csv(output / "canonical_cascade_runs.csv")
    assert len(rows) == 18
    assert {row["status"] for row in rows} == {"planned"}
    assert not (output / "runs").exists()

    commands = json.loads(
        (output / "canonical_cascade_commands.json").read_text(encoding="utf-8")
    )
    normal = next(
        row
        for row in commands
        if row["cascade_id"] == "quality_quarantine_021081_to_268967"
        and row["variant_id"] == "normal"
    )
    untreated = next(
        row
        for row in commands
        if row["cascade_id"] == "quality_quarantine_021081_to_268967"
        and row["variant_id"] == "incident_no_action"
    )
    treated = next(
        row
        for row in commands
        if row["cascade_id"] == "quality_quarantine_021081_to_268967"
        and row["variant_id"] == "incident_second_supplier"
    )
    assert normal["risk_events_csv"] == ""
    assert normal["control_schedule_csv"] == ""
    assert untreated["risk_events_csv"]
    assert untreated["control_schedule_csv"] == ""
    assert treated["risk_events_csv"] == untreated["risk_events_csv"]
    assert treated["control_schedule_csv"]
    assert "--common-random-numbers" in treated["command"]
    assert "--no-supplier-state-dependent-risks" in treated["command"]
    assert _digest(ENGINE_PATH) == engine_digest


def test_prepare_only_freezes_paired_csvs_and_is_portable_from_external_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external_cwd = tmp_path / "outside-repository"
    external_cwd.mkdir()
    output = tmp_path / "portable-campaign"
    original_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    monkeypatch.chdir(external_cwd)

    manifest_path = run_campaign(
        config_path=CONFIG_PATH,
        output_dir=output,
        seeds=[330281, 330282],
        artifact_profile="compact",
        prepare_only=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commands = json.loads(
        (output / "canonical_cascade_commands.json").read_text(encoding="utf-8")
    )
    snapshot_config = json.loads(
        (output / "canonical_cascade_config_snapshot.json").read_text(encoding="utf-8")
    )
    assert snapshot_config == original_config

    ledger = manifest["paired_state_inputs"]
    expected_entry_count = sum(
        len(cascade.get("paired_engine_args", [])) // 2
        for cascade in original_config["cascades"]
    )
    expected_entries = {
        (cascade["id"], paired_args[index])
        for cascade in original_config["cascades"]
        for paired_args in [cascade.get("paired_engine_args", [])]
        for index in range(0, len(paired_args), 2)
    }
    assert len(ledger) == expected_entry_count == len(expected_entries)
    assert {(row["cascade_id"], row["flag"]) for row in ledger} == expected_entries
    assert len({row["snapshot"] for row in ledger}) == len(ledger)
    assert {
        Path(row["snapshot"]).parent.parent.name for row in ledger
    } == {cascade["id"] for cascade in original_config["cascades"]}

    for row in ledger:
        source = Path(row["source"])
        frozen = Path(row["snapshot"])
        assert source.is_absolute()
        assert frozen.is_absolute()
        assert frozen.parent.name == "paired_state"
        expected_stem = row["flag"][2:].removesuffix("-csv").replace("-", "_")
        assert frozen.name == f"{expected_stem}.csv"
        assert frozen.read_bytes() == source.read_bytes()
        assert row["sha256"] == _digest(source) == _digest(frozen)
        cascade_commands = [
            command
            for command in commands
            if command["cascade_id"] == row["cascade_id"]
        ]
        assert len(cascade_commands) == 18
        assert all(
            _command_flag_values(command["command"], row["flag"])
            == [str(frozen)]
            for command in cascade_commands
        )
        assert all(str(source) not in command["command"] for command in commands)

    by_cascade = {
        cascade_id: {
            tuple(
                (row["flag"], _command_flag_values(command["command"], row["flag"])[0])
                for row in ledger
                if row["cascade_id"] == cascade_id
            )
            for command in commands
            if command["cascade_id"] == cascade_id
        }
        for cascade_id in manifest["cascade_ids"]
    }
    assert all(len(argument_sets) == 1 for argument_sets in by_cascade.values())
    assert by_cascade[
        "quality_quarantine_021081_to_268967"
    ] != by_cascade["lead_time_delay_338929_to_268091"]


def test_paired_csv_resolution_is_explicit_and_rejects_missing_or_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    config_dir = tmp_path / "configuration"
    repository.mkdir()
    config_dir.mkdir()
    monkeypatch.setattr(canonical_cascade_campaign, "REPO_ROOT", repository)

    absolute_csv = tmp_path / "absolute.csv"
    absolute_csv.write_text("node_id,item_id,scale\nN,I,0.5\n", encoding="utf-8")
    resolved, mode = canonical_cascade_campaign._resolve_paired_state_csv(
        str(absolute_csv), config_dir=config_dir, label="absolute"
    )
    assert resolved == absolute_csv.resolve()
    assert mode == "absolute"

    config_csv = config_dir / "config-only.csv"
    config_csv.write_text("node_id,item_id,scale\nN,I,0.4\n", encoding="utf-8")
    resolved, mode = canonical_cascade_campaign._resolve_paired_state_csv(
        "config-only.csv", config_dir=config_dir, label="config relative"
    )
    assert resolved == config_csv.resolve()
    assert mode == "config_relative"

    repo_csv = repository / "inputs" / "repo-only.csv"
    repo_csv.parent.mkdir()
    repo_csv.write_text("node_id,item_id,scale\nN,I,0.3\n", encoding="utf-8")
    resolved, mode = canonical_cascade_campaign._resolve_paired_state_csv(
        "inputs/repo-only.csv", config_dir=config_dir, label="repo relative"
    )
    assert resolved == repo_csv.resolve()
    assert mode == "repo_relative"

    with pytest.raises(CascadeCampaignError, match="is missing"):
        canonical_cascade_campaign._resolve_paired_state_csv(
            "missing.csv", config_dir=config_dir, label="missing"
        )

    relative = Path("shared/state.csv")
    config_ambiguous = config_dir / relative
    repo_ambiguous = repository / relative
    config_ambiguous.parent.mkdir()
    repo_ambiguous.parent.mkdir()
    config_ambiguous.write_text("config", encoding="utf-8")
    repo_ambiguous.write_text("repository", encoding="utf-8")
    with pytest.raises(CascadeCampaignError, match="ambiguous"):
        canonical_cascade_campaign._resolve_paired_state_csv(
            str(relative), config_dir=config_dir, label="ambiguous"
        )


def test_pair_scoped_j0_args_reject_duplicate_csv_flag() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["cascades"][0]["paired_engine_args"] = [
        "--measurement-start-stock-scale-csv=first.csv",
        "--measurement-start-stock-scale-csv",
        "second.csv",
    ]

    with pytest.raises(CascadeCampaignError, match="duplicate flag"):
        expand_variants(config)


def test_refuses_nonempty_campaign_output(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("historical result", encoding="utf-8")

    with pytest.raises(CascadeCampaignError, match="Refusing to"):
        run_campaign(
            config_path=CONFIG_PATH,
            output_dir=output,
            seeds=[330281],
            artifact_profile="compact",
            prepare_only=True,
        )
    assert marker.read_text(encoding="utf-8") == "historical result"


def test_multi_effect_risk_evidence_is_separate_without_row_double_count() -> None:
    events = [
        {"event_id": "hold", "risk_type": "quality_delay"},
        {"event_id": "yield", "risk_type": "quality_yield"},
    ]
    rows = [
        {
            "day": "12",
            "supplier_id": "S1",
            "dst_node_id": "D1",
            "item_id": "I1",
            "edge_id": "E1",
            "event_ids": "hold,yield",
            "quality_delay_days": "45",
            "quality_yield_multiplier": "0.1",
        }
    ]

    evidence = _risk_evidence(rows, events, context="synthetic risk evidence")

    assert evidence["applied_event_ids"] == ["hold", "yield"]
    assert evidence["unique_applied_row_count"] == 1
    assert evidence["effects"]["quality_delay"]["effect_sum"] == pytest.approx(45)
    assert evidence["effects"]["quality_yield"]["effect_sum"] == pytest.approx(0.9)


def test_action_evidence_requires_exact_applied_status_and_keeps_uoms_separate() -> None:
    schedule = [
        {
            "day": 0,
            "node_id": "N1",
            "supplier_id": "",
            "item_id": "I1",
            "dst_node_id": "",
            "order_multiplier": 1.2,
        },
        {
            "day": 0,
            "node_id": "",
            "supplier_id": "S1",
            "item_id": "I1",
            "dst_node_id": "D1",
            "priority_weight": 2.0,
        },
    ]
    common_order = {
        "day": "0",
        "action": "order_multiplier",
        "source_line": "2",
        "requested": "1.2",
        "effective": "1.2",
        "resolved_node_id": "N1",
        "resolved_supplier_id": "",
        "resolved_item_id": "I1",
        "resolved_dst_node_id": "",
        "source_node_id": "N1",
        "source_supplier_id": "",
        "source_item_id": "I1",
        "source_dst_node_id": "",
        "edge_id": "",
        "action_stage": "mrp",
    }
    ledger = [
        {
            **common_order,
            "status": "applied",
            "executed_control_volume_qty": "10",
            "quantity_uom": "KG",
        },
        {
            **common_order,
            "status": "applied",
            "executed_control_volume_qty": "2",
            "quantity_uom": "EA",
        },
        {
            **common_order,
            "status": "applied_no_effect",
            "executed_control_volume_qty": "999",
            "quantity_uom": "KG",
        },
        {
            "day": "0",
            "action": "priority_weight",
            "status": "applied",
            "source_line": "3",
            "requested": "2.0",
            "effective": "2.0",
            "executed_control_volume_qty": "",
            "quantity_uom": "",
            "resolved_node_id": "",
            "resolved_supplier_id": "S1",
            "resolved_item_id": "I1",
            "resolved_dst_node_id": "D1",
            "source_node_id": "",
            "source_supplier_id": "S1",
            "source_item_id": "I1",
            "source_dst_node_id": "D1",
            "edge_id": "E1",
            "action_stage": "supplier_allocation",
        },
    ]
    shipments = [
        {
            "day": "0",
            "src_node_id": "S1",
            "dst_node_id": "D1",
            "item_id": "I1",
            "edge_id": "E1",
            "shipped_qty": "7",
            "uom": "KG",
        }
    ]

    evidence = _action_evidence(
        ledger=ledger,
        shipments=shipments,
        schedule_rows=schedule,
        context="synthetic action evidence",
    )

    assert evidence["status"] == "fully_verified"
    assert evidence["expected_signature_count"] == 2
    assert evidence["verified_signature_count"] == 2
    assert evidence["verified_row_count"] == 3
    groups = evidence["evidence"]["verified_groups"]
    assert {(row["action"], row["uom"]) for row in groups} == {
        ("order_multiplier", "KG"),
        ("order_multiplier", "EA"),
        ("priority_weight", "KG"),
    }
    assert sorted(row["physical_volume_qty"] for row in groups) == [2.0, 7.0, 10.0]


def test_action_evidence_rejects_wrong_planned_value_and_day() -> None:
    schedule = [
        {
            "day": 4,
            "node_id": "N1",
            "supplier_id": "",
            "item_id": "I1",
            "dst_node_id": "",
            "order_multiplier": 1.2,
        }
    ]
    ledger = [
        {
            "day": "3",
            "action": "order_multiplier",
            "status": "applied",
            "source_line": "2",
            "requested": "1.2",
            "effective": "1.0",
            "executed_control_volume_qty": "10",
            "quantity_uom": "KG",
            "resolved_node_id": "N1",
            "resolved_supplier_id": "",
            "resolved_item_id": "I1",
            "resolved_dst_node_id": "",
            "source_node_id": "N1",
            "source_supplier_id": "",
            "source_item_id": "I1",
            "source_dst_node_id": "",
            "edge_id": "",
            "action_stage": "mrp",
        }
    ]

    evidence = _action_evidence(
        ledger=ledger,
        shipments=[],
        schedule_rows=schedule,
        context="synthetic wrong plan",
    )

    assert evidence["status"] == "not_verified"
    assert evidence["verified_signature_count"] == 0
    assert evidence["evidence"]["rejected_applied_rows"]


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("schema_version", "old"),
        ("scope", "inventory_only"),
        ("physical_warmup_days", 239),
        ("measured_cutover_day", 1),
        ("restart_checkpoint_available", True),
    ],
)
def test_measurement_start_audit_contract_is_strict(
    tmp_path: Path, field: str, invalid: object
) -> None:
    result = tmp_path / "result"
    summary = result / "summaries" / "first_simulation_summary.json"
    summary.parent.mkdir(parents=True)
    audit = {
        "schema_version": "etudecas.engine_warmup_boundary_audit.v1",
        "method": "deterministic_paired_burn_in_replay",
        "scope": "core_dynamic_engine_state_not_restart_checkpoint",
        "physical_warmup_days": 240,
        "measured_cutover_day": 0,
        "core_state_sha256": "a" * 64,
        "component_sha256": {"stock": "b" * 64},
        "restart_checkpoint_available": False,
    }
    audit[field] = invalid
    summary.write_text(
        json.dumps({"policy": {"warmup_boundary_audit": audit}}), encoding="utf-8"
    )

    with pytest.raises(CascadeCampaignError, match="audit contract"):
        _load_measurement_start_hashes(result, expected_warmup_days=240)


def test_cost_metrics_reconstructs_exhaustive_total_without_double_count(
    tmp_path: Path,
) -> None:
    result = tmp_path / "result"
    daily = result / "data" / "first_simulation_daily.csv"
    columns = [
        "day",
        "total_supply_cost_day",
        "operational_purchase_cost_day",
        "operational_transport_cost_day",
        "opening_open_order_purchase_cost_day",
        "opening_open_order_transport_cost_day",
        "external_procurement_purchase_cost_day",
        "external_procurement_transport_cost_day",
        "holding_cost_day",
        "warehouse_operating_cost_day",
        "inventory_risk_cost_day",
        "production_cost_day",
    ]
    rows = [
        {
            "day": day,
            "total_supply_cost_day": 138,
            "operational_purchase_cost_day": 100,
            "operational_transport_cost_day": 20,
            "opening_open_order_purchase_cost_day": 7,
            "opening_open_order_transport_cost_day": 8,
            "external_procurement_purchase_cost_day": 9,
            "external_procurement_transport_cost_day": 10,
            "holding_cost_day": 3,
            "warehouse_operating_cost_day": 4,
            "inventory_risk_cost_day": 5,
            "production_cost_day": 6,
        }
        for day in range(2)
    ]
    daily.parent.mkdir(parents=True)
    with daily.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    summary = result / "summaries" / "first_simulation_summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(
        json.dumps(
            {
                "kpis": {
                    "total_cost": 306,
                    "total_external_procurement_cost": 38,
                }
            }
        ),
        encoding="utf-8",
    )

    metrics = _cost_metrics(result, expected_days=2)

    assert metrics["base_operational_supply_cost"] == pytest.approx(276)
    assert metrics["controllable_operating_cost"] == pytest.approx(314)
    assert metrics["decision_total_cost"] == pytest.approx(344)
    assert metrics["decision_transport_cost"] == pytest.approx(76)
    assert metrics["decision_purchase_cost"] == pytest.approx(232)


def test_jobs_two_runs_in_parallel_and_keeps_deterministic_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_run_engine(command: object, *, result_dir: Path) -> subprocess.CompletedProcess[str]:
        nonlocal active, max_active
        result_dir.mkdir(parents=True, exist_ok=True)
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_metrics(
        result_dir: Path,
        cascade: object,
        *,
        expected_days: int,
        expected_warmup_days: int,
        expected_schedule_rows: object,
    ) -> dict[str, object]:
        return {
            "customer_id": "C-XXXXX",
            "finished_item_id": "item:268967",
            "measurement_start_state_sha256": "a" * 64,
            "measurement_start_component_sha256_json": json.dumps(
                {"inventory": "b" * 64}
            ),
            "pairing_status": "pending_pair_validation",
            "incident_validation_status": "pending_incident_validation",
        }

    monkeypatch.setattr(canonical_cascade_campaign, "_run_engine", fake_run_engine)
    monkeypatch.setattr(
        canonical_cascade_campaign, "extract_run_metrics", fake_metrics
    )
    monkeypatch.setattr(
        canonical_cascade_campaign,
        "_validate_physical_campaign_rows",
        lambda *args, **kwargs: 0,
    )
    output = tmp_path / "parallel"

    manifest_path = run_campaign(
        config_path=CONFIG_PATH,
        output_dir=output,
        seeds=[330281],
        cascade_ids=["quality_quarantine_021081_to_268967"],
        solution_ids=["expedited_transport"],
        artifact_profile="compact",
        jobs=2,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_csv(output / "canonical_cascade_runs.csv")
    assert max_active >= 2
    assert manifest["jobs"] == 2
    assert [row["variant_id"] for row in rows] == [
        "normal",
        "incident_no_action",
        "incident_expedited_transport",
    ]
