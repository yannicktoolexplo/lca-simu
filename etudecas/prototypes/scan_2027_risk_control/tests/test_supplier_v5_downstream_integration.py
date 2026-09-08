from __future__ import annotations

import csv
import gzip
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v5 as bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v5 as relay,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v5 as finalizer_adapter,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v5 as launcher_adapter,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v5 as campaign_adapter,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v5 as sidecar_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as qualification_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v5_final_standalone_delivery as delivery_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as action_replay,
)


def _bridge_payload() -> dict[str, Any]:
    source = {field: "a" * 64 for field in bridge.SOURCE_REFERENCE_FIELDS}
    for field in (
        "plan_dir",
        "plan_manifest",
        "run_dir",
        "run_manifest",
        "development_selection",
        "holdout_result",
    ):
        source[field] = f"C:/fixture/{field}"
    points = []
    for index, point_id in enumerate(bridge.campaign_contract.OPERATING_POINT_IDS):
        point = {field: "" for field in bridge.POINT_FIELDS}
        point.update(
            {
                "operating_point_id": point_id,
                "operating_point_label": point_id,
                "candidate_key": f"candidate_{index}",
                "candidate_id": f"candidate-id-{index}",
                "target_service": 1.0 - index * 0.1,
                "calibration_pooled_service": 1.0 - index * 0.1,
                "calibration_product_268091_service": 1.0 - index * 0.1,
                "calibration_product_268967_service": 1.0 - index * 0.1,
                "offset_days_268091": float(index),
                "offset_days_268967": float(index),
                "degradation_family": "baseline" if not index else "test",
                "degradation_value": {},
                "degradation_unit": "days",
                "holdout_seed_count": 30,
                "holdout_state_summary": {},
            }
        )
        points.append(point)
    traces = []
    for point_id in bridge.campaign_contract.OPERATING_POINT_IDS:
        for seed in bridge.campaign_contract.CAMPAIGN_SEEDS:
            row = {field: "" for field in bridge.TRACE_INDEX_FIELDS}
            row.update(
                {
                    "operating_point_id": point_id,
                    "candidate_key": f"candidate_{point_id}",
                    "candidate_id": f"candidate-id-{point_id}",
                    "seed": seed,
                    "evidence_relative_path": f"evidence/{point_id}/{seed}.json",
                    "evidence_sha256": "b" * 64,
                    "evidence_signature": "c" * 64,
                    "shipment_trace": {},
                }
            )
            traces.append(row)
    producer_path = Path(bridge.__file__).resolve()
    unsigned = {
        "schema_version": bridge.BRIDGE_SCHEMA_VERSION,
        "status": bridge.BRIDGE_ACCEPTED_STATUS,
        "interpretation": bridge.INTERPRETATION,
        "producer": {
            "path": str(producer_path),
            "sha256": bridge.campaign_contract.sha256_file(producer_path),
        },
        "source": source,
        "source_hashes": {
            "v5_driver_sha256": "d" * 64,
            "engine_sha256": "e" * 64,
            "engine_profile_sha256": "f" * 64,
        },
        "cohorts": {
            bridge.COMPATIBILITY_COHORT_KEY: list(
                bridge.campaign_contract.CAMPAIGN_SEEDS
            ),
            "incident_window_design_reserved": [
                bridge.campaign_contract.INCIDENT_DESIGN_SEED
            ],
            "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
        },
        "operating_points": points,
        "lane_contract": {},
        "holdout_contract": {
            "status": bridge.ACCEPTED_HOLDOUT_STATUS,
            "accepted": True,
            "publishable": True,
            "retuning_after_holdout": False,
            "evidence_case_count": 90,
        },
        "trace_contract": {},
        "trace_index": traces,
        "trace_index_signature": bridge.campaign_contract.stable_sha256(traces),
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "simulation_hypotheses_not_observed_performance": True,
        "retuning_after_holdout": False,
    }
    assert set(unsigned) | {"artifact_signature"} == bridge.BRIDGE_FIELDS
    return {
        **unsigned,
        "artifact_signature": bridge.campaign_contract.stable_sha256(unsigned),
    }


def _corridor_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(relay.EXPECTED_CORRIDORS):
        supplier_index = index if index < relay.EXPECTED_UNIQUE_SUPPLIERS else index - 16
        rows.append(
            {
                "lane_id": f"lane_{index:02d}",
                "supplier_id": f"SUP-{supplier_index:02d}",
                "item_id": f"item:{index:06d}",
                "dst_node_id": "M-1810" if index % 2 == 0 else "M-1430",
                "edge_id": f"edge:{index:02d}",
                "target_product_id": "268091" if index % 2 == 0 else "268967",
                "planned_lead_days": 10.0 + index,
            }
        )
    return rows


def _strict_config(tmp_path: Path) -> relay.V5RelayConfig:
    v4_plan = tmp_path / "v4" / "plan"
    v4_run = tmp_path / "v4" / "run"
    v4_sidecar = tmp_path / "v4" / "sidecar"
    for directory in (v4_plan, v4_run, v4_sidecar):
        directory.mkdir(parents=True)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_risk = legacy_dir / "risk.html"
    legacy_control = legacy_dir / "control.html"
    legacy_risk.write_text("risk", encoding="utf-8")
    legacy_control.write_text("control", encoding="utf-8")
    output = tmp_path / "v5"
    return relay.V5RelayConfig(
        repo=Path(__file__).resolve().parents[4],
        v4_plan_dir=v4_plan,
        v4_run_dir=v4_run,
        v4_sidecar_root=v4_sidecar,
        calibration_plan_dir=output / "calibration-plan",
        calibration_run_dir=output / "calibration-run",
        sidecar_dir=output / "sidecar",
        bridge_json=output / "bridge.json",
        campaign_root=output / "campaign",
        results_dir=output / "results",
        lot_replay_root=output / "lots",
        qualification_dir=output / "qualification",
        dashboard_html=output / "dashboard.html",
        final_html=output / "final.html",
        supervision_dir=output / "supervision",
        action_replay_root=output / "actions",
        legacy_risk_html=legacy_risk,
        legacy_control_html=legacy_control,
        action_replay_mode="required",
    ).resolved()


def test_bridge_envelope_requires_exact_90_and_accepted_v5_status(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bridge.json"
    bridge._write_json_atomic(path, _bridge_payload())  # noqa: SLF001
    assert (
        len(bridge.validate_bridge(path, revalidate_source=False)["trace_index"]) == 90
    )

    tampered = _bridge_payload()
    tampered["holdout_contract"]["status"] = "holdout_rejected_no_retuning"
    unsigned = dict(tampered)
    unsigned.pop("artifact_signature")
    tampered["artifact_signature"] = bridge.campaign_contract.stable_sha256(unsigned)
    bridge._write_json_atomic(tmp_path / "rejected.json", tampered)  # noqa: SLF001
    with pytest.raises(bridge.V5BridgeError, match="holdout contract"):
        bridge.validate_bridge(tmp_path / "rejected.json", revalidate_source=False)


def test_bridge_refuses_test_only_v5_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_plan = SimpleNamespace(
        manifest={
            "source_hashes": {
                "v5_driver_sha256": bridge.campaign_contract.sha256_file(
                    Path(bridge.refinement_v5.__file__).resolve()
                )
            }
        }
    )
    monkeypatch.setattr(
        bridge.refinement_v5, "validate_plan", lambda *_a, **_k: fake_plan
    )
    monkeypatch.setattr(
        bridge.refinement_v5,
        "_registered_execution_mode",
        lambda *_a, **_k: bridge.refinement_v5.TEST_ONLY_EXECUTION_MODE,
    )
    with pytest.raises(bridge.V5BridgeError, match="test-only"):
        bridge._load_official_source(tmp_path / "plan", tmp_path / "run")  # noqa: SLF001


def test_corridor_projection_requires_exactly_18_corridors_and_16_suppliers() -> None:
    rows = _corridor_rows()
    assert len(
        relay._validated_corridor_projection(rows, source_label="test")  # noqa: SLF001
    ) == relay.EXPECTED_CORRIDORS

    with pytest.raises(relay.FullCampaignRelayError, match="18 corridors"):
        relay._validated_corridor_projection(  # noqa: SLF001
            rows[:-1], source_label="test incomplet"
        )

    only_fifteen_suppliers = [dict(row) for row in rows]
    only_fifteen_suppliers[15]["supplier_id"] = "SUP-02"
    with pytest.raises(relay.FullCampaignRelayError, match="16 supplier_id"):
        relay._validated_corridor_projection(  # noqa: SLF001
            only_fifteen_suppliers, source_label="test fournisseurs"
        )


def test_downstream_preflight_binds_plan_manifest_and_real_corridor_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = _corridor_rows()
    lane_reference = tmp_path / "active_lane_reference.csv"
    with lane_reference.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "scope_status",
                "chain_id",
                "supplier_id",
                "item_id",
                "dst_node_id",
                "edge_id",
                "target_product_id",
                "planned_lead_days",
            ),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "scope_status": "active_simulated_reference_v10",
                    "chain_id": row["lane_id"],
                    **{key: value for key, value in row.items() if key != "lane_id"},
                }
            )
    source_manifest_path = tmp_path / "source_campaign_manifest.json"
    source_manifest = {
        "lanes": rows,
        "lane_reference_source": str(lane_reference),
        "lane_reference_source_sha256": relay.relay_v4.sha256_file(lane_reference),
    }
    relay.relay_v4._atomic_json(source_manifest_path, source_manifest)  # noqa: SLF001
    plan = SimpleNamespace(
        manifest={
            "plan_signature": "a" * 64,
            "source": {"campaign_manifest": {"path": str(source_manifest_path)}},
        }
    )
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.status = {}
    instance._validated_plan = lambda: plan
    instance._write_status = lambda: None
    monkeypatch.setattr(
        campaign_adapter.implementation_v4,
        "DEFAULT_LANE_REFERENCE",
        lane_reference,
    )

    result = relay.FullCampaignRelayV5.validate_downstream_corridor_preflight(
        instance
    )
    assert result["corridor_count"] == 18
    assert result["unique_supplier_count"] == 16
    assert instance.status["downstream_corridor_preflight"] == result

    source_manifest["lanes"][15]["supplier_id"] = "SUP-02"
    relay.relay_v4._atomic_json(source_manifest_path, source_manifest)  # noqa: SLF001
    with pytest.raises(relay.FullCampaignRelayError, match="16 supplier_id"):
        relay.FullCampaignRelayV5.validate_downstream_corridor_preflight(instance)


def test_complete_v5_requires_final_html_and_explicit_required_actions(
    tmp_path: Path,
) -> None:
    config = _strict_config(tmp_path)
    config.validate()
    invalid = (
        (replace(config, final_html=None), "HTML final autonome"),
        (replace(config, action_replay_root=None), "racine de résultats actions"),
        (replace(config, action_replay_mode="auto"), "explicitement.*required"),
        (replace(config, action_replay_mode="off"), "explicitement.*required"),
    )
    for candidate, message in invalid:
        with pytest.raises(relay.FullCampaignRelayError, match=message):
            candidate.validate()

    parser_actions = {action.dest: action for action in relay._parser()._actions}  # noqa: SLF001
    assert parser_actions["final_html"].required is True
    assert parser_actions["action_replay_root"].required is True
    assert parser_actions["action_replay_mode"].required is True
    assert parser_actions["qualification_dir"].required is True
    assert tuple(parser_actions["action_replay_mode"].choices) == ("required",)
    assert parser_actions["max_wait_hours"].default == 240.0


def test_detached_handoff_forwards_qualification_actions_sidecar_and_240_hours(
    tmp_path: Path,
) -> None:
    values = {
        "repo": tmp_path / "repo",
        "v4-plan-dir": tmp_path / "v4-plan",
        "v4-run-dir": tmp_path / "v4-run",
        "v4-sidecar-root": tmp_path / "v4-sidecar",
        "calibration-plan-dir": tmp_path / "v5-plan",
        "calibration-run-dir": tmp_path / "v5-run",
        "sidecar-dir": tmp_path / "v5-sidecar",
        "bridge-json": tmp_path / "bridge.json",
        "campaign-root": tmp_path / "campaign",
        "results-dir": tmp_path / "results",
        "lot-replay-root": tmp_path / "lots",
        "qualification-dir": tmp_path / "qualification",
        "dashboard-html": tmp_path / "dashboard.html",
        "final-html": tmp_path / "final.html",
        "action-replay-root": tmp_path / "actions",
        "supervision-dir": tmp_path / "supervision",
    }
    argv = [
        item
        for option, path in values.items()
        for item in (f"--{option}", str(path))
    ]
    argv.extend(
        [
            "--action-replay-mode",
            "required",
            "--max-wait-hours",
            "240",
            "--detach",
        ]
    )
    args = relay._parser().parse_args(argv)  # noqa: SLF001
    command = relay._child_command(args)  # noqa: SLF001

    def option_value(option: str) -> str:
        return command[command.index(option) + 1]

    assert option_value("--qualification-dir") == str(
        values["qualification-dir"].resolve()
    )
    assert option_value("--action-replay-root") == str(
        values["action-replay-root"].resolve()
    )
    assert option_value("--action-replay-mode") == "required"
    assert option_value("--sidecar-dir") == str(values["sidecar-dir"].resolve())
    assert option_value("--max-wait-hours") == "240.0"
    assert "--detached-child" in command


def test_every_v5_write_target_is_separate_from_v4_inputs_and_html(
    tmp_path: Path,
) -> None:
    config = _strict_config(tmp_path)
    write_fields = (
        "calibration_plan_dir",
        "calibration_run_dir",
        "sidecar_dir",
        "bridge_json",
        "campaign_root",
        "results_dir",
        "lot_replay_root",
        "qualification_dir",
        "dashboard_html",
        "final_html",
        "supervision_dir",
        "action_replay_root",
    )
    for field in write_fields:
        candidate = replace(
            config,
            **{field: config.v4_plan_dir / f"forbidden-{field}"},
        )
        with pytest.raises(relay.FullCampaignRelayError, match="V4"):
            candidate.validate()

    with pytest.raises(relay.FullCampaignRelayError, match="V4"):
        replace(config, final_html=config.legacy_risk_html).validate()
    with pytest.raises(relay.FullCampaignRelayError, match="V4"):
        replace(config, campaign_root=config.legacy_control_html.parent).validate()
    for candidate in (
        replace(config, bridge_json=config.campaign_root / "bridge.json"),
        replace(config, bridge_json=config.campaign_root.parent),
    ):
        with pytest.raises(relay.FullCampaignRelayError, match="chevauch"):
            candidate.validate()


def test_required_action_outcome_accepts_proven_scientific_absence_only_after_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    action_root = tmp_path / "actions"
    action_root.mkdir()
    validation_path = action_root / "action_replay_validation.json"
    relay.relay_v4._atomic_json(validation_path, {"status": "fixture"})  # noqa: SLF001
    instance.config = SimpleNamespace(action_replay_root=action_root)
    instance.status = {
        "action_replay": {
            "status": "complete_no_representable_action",
            "validation_sha256": relay.relay_v4.sha256_file(validation_path),
        },
        "steps": {
            "confirmation_execution_actions_v5": {
                "attempts": [
                    {
                        "return_code": 0,
                        "command": ["python", "run", "--execute"],
                    }
                ]
            }
        },
    }
    monkeypatch.setattr(
        action_replay,
        "validate_action_results",
        lambda _root: ({}, {"status": "complete_no_representable_action"}),
    )
    assert (
        relay.FullCampaignRelayV5.validate_required_action_outcome(instance)
        == "complete_no_representable_action"
    )
    instance.status["steps"] = {}
    with pytest.raises(relay.FullCampaignRelayError, match="tentative explicite"):
        relay.FullCampaignRelayV5.validate_required_action_outcome(instance)
    instance.status = {"action_replay": {"status": "not_configured"}}
    with pytest.raises(relay.FullCampaignRelayError, match="obligatoire"):
        relay.FullCampaignRelayV5.validate_required_action_outcome(instance)


def test_relay_start_requires_finalized_sidecar_inventory() -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(sidecar_dir=Path("sidecar"))
    instance._sidecar_inventory_ready = lambda: False
    with pytest.raises(relay.FullCampaignRelayError, match="avant lancement"):
        relay.FullCampaignRelayV5.validate_finalized_sidecar_handoff(instance)


def test_finalized_sidecar_handoff_is_bound_to_exact_plan_run_and_case_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    sidecar_dir = tmp_path / "sidecar"
    plan_dir.mkdir()
    run_dir.mkdir()
    sidecar_dir.mkdir()
    (plan_dir / "refinement_plan.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text("{}", encoding="utf-8")
    cases = tuple(
        sidecar_v5.ExpectedCase(
            target_group=group,
            candidate_key=f"candidate-{group}",
            candidate_id=f"candidate-id-{group}",
            seed=seed,
            graph_sha256="a" * 64,
        )
        for group in sidecar_v5.EXPECTED_TARGET_GROUPS
        for seed in relay.refinement_v5.EXPECTED_HOLDOUT_SEEDS
    )
    contract = sidecar_v5.build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=sidecar_dir,
        cases=cases,
    )
    relay.relay_v4._atomic_json(  # noqa: SLF001
        sidecar_dir / "capture_contract.json", contract
    )
    ready = sidecar_v5._ready_payload(contract, output_dir=sidecar_dir)  # noqa: SLF001
    relay.relay_v4._atomic_json(  # noqa: SLF001
        sidecar_dir / "watcher_ready.json", ready
    )

    captured = []
    for index, case in enumerate(cases):
        path = sidecar_dir / "case_manifests" / f"case-{index:02d}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'{{"case": {index}}}', encoding="utf-8")
        captured.append(
            {
                "target_group": case.target_group,
                "candidate_key": case.candidate_key,
                "candidate_id": case.candidate_id,
                "seed": case.seed,
                "case_manifest_path": str(path.resolve()),
                "case_manifest_sha256": relay.relay_v4.sha256_file(path),
                "case_signature": "b" * 64,
                "captured_csv_count": contract["required_file_count_per_case"],
            }
        )
    base_unsigned = {
        "schema_version": sidecar_v5.capture_v4.INVENTORY_SCHEMA_VERSION,
        "contract_signature": contract["contract_signature"],
        "status": "complete",
        "interpretation": contract["interpretation"],
        "capture_guarantee": contract["capture_guarantee"],
        "case_count": len(captured),
        "cases": sorted(
            captured, key=lambda row: (row["target_group"], row["seed"])
        ),
        "completed_at_utc": "2026-09-05T00:00:00+00:00",
    }
    base = {
        **base_unsigned,
        "inventory_signature": relay.relay_v4.stable_sha256(base_unsigned),
    }
    base_path = sidecar_dir / "capture_inventory.json"
    relay.relay_v4._atomic_json(base_path, base)  # noqa: SLF001
    v5_unsigned = {
        "schema_version": sidecar_v5.INVENTORY_SCHEMA_VERSION,
        "created_at_utc": "2026-09-05T00:00:00+00:00",
        "status": "complete",
        "contract_signature": contract["contract_signature"],
        "case_count": len(captured),
        "base_inventory_path": str(base_path.resolve()),
        "base_inventory_sha256": relay.relay_v4.sha256_file(base_path),
        "base_inventory_signature": base["inventory_signature"],
        "interpretation": (
            "Courbes descriptives de 90 simulations de holdout V5 fraîches; "
            "ni observations fournisseurs, ni probabilités historiques."
        ),
    }
    v5 = {
        **v5_unsigned,
        "inventory_signature": relay.relay_v4.stable_sha256(v5_unsigned),
    }
    relay.relay_v4._atomic_json(  # noqa: SLF001
        sidecar_dir / "capture_inventory_v5.json", v5
    )

    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        calibration_plan_dir=plan_dir.resolve(),
        calibration_run_dir=run_dir.resolve(),
        sidecar_dir=sidecar_dir.resolve(),
    )
    instance._sidecar_inventory_ready = lambda: True
    instance._validate_sidecar_snapshots_read_only = lambda **_kwargs: None
    monkeypatch.setattr(sidecar_v5, "load_official_cases", lambda *_args: cases)

    result = relay.FullCampaignRelayV5.validate_finalized_sidecar_handoff(instance)
    assert result["status"] == "complete"
    assert result["case_count"] == relay.EXPECTED_HOLDOUT_CASES

    first_manifest = Path(captured[0]["case_manifest_path"])
    first_manifest.write_text("altered", encoding="utf-8")
    with pytest.raises(relay.FullCampaignRelayError, match="lié exactement"):
        relay.FullCampaignRelayV5.validate_finalized_sidecar_handoff(instance)


def test_read_only_sidecar_preflight_reopens_every_snapshot(tmp_path: Path) -> None:
    capture = sidecar_v5.capture_v4
    sidecar_dir = tmp_path / "sidecar"
    sidecar_dir.mkdir()
    case = sidecar_v5.ExpectedCase(
        target_group="op_100",
        candidate_key="candidate-op100",
        candidate_id="candidate-id-op100",
        seed=101,
        graph_sha256="a" * 64,
    )
    contract_unsigned = {
        "cases": [asdict(case)],
        "csv_specs": [
            {
                **asdict(spec),
                "columns": list(spec.columns),
                "key_columns": list(spec.key_columns),
                "numeric_columns": list(spec.numeric_columns),
            }
            for spec in capture.CSV_SPECS
        ],
        "required_file_count_per_case": sum(
            spec.required for spec in capture.CSV_SPECS
        ),
    }
    contract = {
        **contract_unsigned,
        "contract_signature": relay.relay_v4.stable_sha256(contract_unsigned),
    }

    def write_snapshot(data_path: Path, meta_path: Path, raw: bytes) -> dict[str, Any]:
        data_path.parent.mkdir(parents=True, exist_ok=True)
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        data_path.write_bytes(compressed)
        metadata_unsigned = {
            "schema_version": capture.SNAPSHOT_SCHEMA_VERSION,
            "snapshot_path": str(data_path.resolve()),
            "snapshot_gzip_sha256": capture.sha256_bytes(compressed),
            "snapshot_uncompressed_bytes": len(raw),
            "source_sha256": capture.sha256_bytes(raw),
        }
        metadata = {
            **metadata_unsigned,
            "snapshot_signature": relay.relay_v4.stable_sha256(metadata_unsigned),
        }
        relay.relay_v4._atomic_json(meta_path, metadata)  # noqa: SLF001
        return metadata

    summary_data, summary_meta = capture._summary_paths(sidecar_dir, case)  # noqa: SLF001
    summary = write_snapshot(summary_data, summary_meta, b'{"summary": true}')
    file_rows = []
    data_paths = []
    for spec in capture.CSV_SPECS:
        data_path, meta_path = capture._snapshot_paths(  # noqa: SLF001
            sidecar_dir, case, spec.filename
        )
        data_paths.append(data_path)
        metadata = write_snapshot(data_path, meta_path, b"day,value\n0,1\n")
        file_rows.append(
            {
                "filename": spec.filename,
                "required": spec.required,
                "snapshot_path": str(data_path.resolve()),
                "snapshot_gzip_sha256": metadata["snapshot_gzip_sha256"],
                "source_sha256": metadata["source_sha256"],
            }
        )
    manifest_unsigned = {
        "schema_version": capture.CASE_SCHEMA_VERSION,
        "contract_signature": contract["contract_signature"],
        **asdict(case),
        "summary": {
            "snapshot_path": str(summary_data.resolve()),
            "snapshot_gzip_sha256": summary["snapshot_gzip_sha256"],
            "source_sha256": summary["source_sha256"],
        },
        "files": file_rows,
        "required_files_complete": True,
        "completed_at_utc": "2026-09-05T00:00:00+00:00",
    }
    manifest = {
        **manifest_unsigned,
        "case_signature": relay.relay_v4.stable_sha256(manifest_unsigned),
    }
    manifest_path = capture._case_manifest_path(sidecar_dir, case)  # noqa: SLF001
    relay.relay_v4._atomic_json(manifest_path, manifest)  # noqa: SLF001
    base_inventory = {
        "cases": [
            {
                "candidate_id": case.candidate_id,
                "seed": case.seed,
                "case_manifest_path": str(manifest_path.resolve()),
                "case_manifest_sha256": relay.relay_v4.sha256_file(manifest_path),
                "case_signature": manifest["case_signature"],
                "captured_csv_count": len(capture.CSV_SPECS),
            }
        ]
    }
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(sidecar_dir=sidecar_dir)

    relay.FullCampaignRelayV5._validate_sidecar_snapshots_read_only(
        instance,
        capture=capture,
        contract=contract,
        base_inventory=base_inventory,
    )

    tampered_unsigned = {
        **manifest_unsigned,
        "summary": {
            **manifest_unsigned["summary"],
            "source_sha256": "0" * 64,
        },
    }
    tampered_manifest = {
        **tampered_unsigned,
        "case_signature": relay.relay_v4.stable_sha256(tampered_unsigned),
    }
    relay.relay_v4._atomic_json(manifest_path, tampered_manifest)  # noqa: SLF001
    base_row = base_inventory["cases"][0]
    base_row["case_manifest_sha256"] = relay.relay_v4.sha256_file(manifest_path)
    base_row["case_signature"] = tampered_manifest["case_signature"]
    with pytest.raises(relay.FullCampaignRelayError, match="Résumé"):
        relay.FullCampaignRelayV5._validate_sidecar_snapshots_read_only(
            instance,
            capture=capture,
            contract=contract,
            base_inventory=base_inventory,
        )

    relay.relay_v4._atomic_json(manifest_path, manifest)  # noqa: SLF001
    base_row["case_manifest_sha256"] = relay.relay_v4.sha256_file(manifest_path)
    base_row["case_signature"] = manifest["case_signature"]
    data_paths[-1].unlink()
    with pytest.raises(capture.CurveSidecarError, match="partiel"):
        relay.FullCampaignRelayV5._validate_sidecar_snapshots_read_only(
            instance,
            capture=capture,
            contract=contract,
            base_inventory=base_inventory,
        )


def test_calibration_handoff_only_reopens_complete_accepted_proofs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    run_dir = tmp_path / "run"
    plan_dir.mkdir()
    run_dir.mkdir()
    for path in (
        plan_dir / "refinement_plan.json",
        run_dir / "development_progress.json",
        run_dir / "development_selection.json",
        run_dir / "holdout_progress.json",
        run_dir / "holdout_result.json",
    ):
        path.write_text(path.name, encoding="utf-8")

    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        calibration_plan_dir=plan_dir,
        calibration_run_dir=run_dir,
    )
    calls: list[tuple[str, int]] = []
    instance._plan_ready = lambda: True
    instance._stage_complete = lambda stage, count: (
        calls.append((stage, count)) or True
    )
    instance._development_selection = lambda: {
        "status": "development_selected_pending_fresh_holdout",
        "selected_candidate_keys": {
            state: f"candidate-{state}" for state in relay.EXPECTED_STATE_IDS
        },
        "holdout_cases_read": 0,
        "selection_signature": "a" * 64,
    }
    instance._holdout_result = lambda: {
        "status": relay.bridge_v5.ACCEPTED_HOLDOUT_STATUS,
        "accepted": True,
        "publishable": True,
        "retuning_after_holdout": False,
        "holdout_evidence_case_count": relay.EXPECTED_HOLDOUT_CASES,
        "state_summaries": {state: {} for state in relay.EXPECTED_STATE_IDS},
        "holdout_signature": "b" * 64,
    }
    instance.validate_finalized_sidecar_handoff = lambda: {
        "status": "complete",
        "case_count": relay.EXPECTED_HOLDOUT_CASES,
    }
    monkeypatch.setattr(
        instance,
        "_python_module",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("le préflight a construit une commande")
        ),
    )

    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    result = relay.FullCampaignRelayV5.validate_calibration_handoff(instance)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert calls == [
        ("development", relay.EXPECTED_DEVELOPMENT_CASES),
        ("holdout", relay.EXPECTED_HOLDOUT_CASES),
    ]
    assert result["status"] == "accepted_read_only_handoff"
    assert result["relay_development_engine_runs"] == 0
    assert result["relay_holdout_engine_runs"] == 0
    assert result["retuning_after_holdout"] is False
    assert before == after


def test_required_curves_refuse_absent_or_incomplete_status() -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.status = {"nominal_curves": {"status": "complete_validated"}}
    relay.FullCampaignRelayV5.validate_required_curves_outcome(instance)
    for status in ("", "not_configured", "curve_capture_failed_or_incomplete"):
        instance.status = {"nominal_curves": {"status": status}}
        with pytest.raises(relay.FullCampaignRelayError, match="obligatoires"):
            relay.FullCampaignRelayV5.validate_required_curves_outcome(instance)


def test_curve_finalization_uses_v5_sidecar_wrapper(tmp_path: Path) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(sidecar_dir=tmp_path / "sidecar")
    commands: list[list[str]] = []
    instance._python_module = lambda module, *args: [module, *args]
    instance.run_step = lambda **kwargs: commands.append(list(kwargs["command"]))
    instance._record_artifact = lambda *_args: None

    relay.FullCampaignRelayV5.validate_and_aggregate_curves(instance)

    assert commands[0][0] == relay.SIDECAR_MODULE
    assert commands[0][0] != relay.relay_v4.SIDECAR_MODULE
    assert commands[1][0] == relay.relay_v4.AGGREGATOR_MODULE
    assert commands[2][0] == relay.relay_v4.AGGREGATOR_MODULE


def test_missing_physical_qualification_sidecar_is_not_ready(tmp_path: Path) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(qualification_dir=tmp_path / "missing")
    assert relay.FullCampaignRelayV5._qualification_ready(instance) is False


def test_campaign_launch_ready_accepts_exact_zero_terminal_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    expected_contract = {"launch_contract_signature": "contract-signature"}
    payload = {
        "status": "complete",
        "phase": "shards",
        "target_discovery_status": "complete",
        "planned_shard_count": relay.EXPECTED_SHARDS,
        "completed_shard_count": relay.EXPECTED_SHARDS,
        "failed_shard_count": 0,
        "active_shard_count": 0,
        "queued_shard_count": 0,
        "schema_version": launcher_adapter.implementation_v4.PROGRESS_SCHEMA_VERSION,
        "campaign_signature": "campaign-signature",
        "launch_contract_signature": "contract-signature",
    }
    relay.relay_v4._atomic_json(  # noqa: SLF001
        campaign_root / "launch_progress.json", payload
    )
    relay.relay_v4._atomic_json(  # noqa: SLF001
        campaign_root / "launch_contract.json", expected_contract
    )
    implementation = launcher_adapter.implementation_v4
    monkeypatch.setattr(
        implementation,
        "load_campaign_plan",
        lambda *_args: ({"campaign_signature": "campaign-signature"}, []),
    )
    monkeypatch.setattr(
        implementation, "_launch_contract", lambda **_kwargs: expected_contract
    )
    monkeypatch.setattr(
        implementation,
        "_discovery_completion_state",
        lambda *_args, **_kwargs: ("complete", "fixture"),
    )
    monkeypatch.setattr(
        implementation,
        "_smoke_completion_state",
        lambda *_args, **_kwargs: ("complete", "fixture"),
    )
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        campaign_root=campaign_root,
        repo=Path(__file__).resolve().parents[4],
    )

    assert relay.FullCampaignRelayV5._campaign_launch_ready(instance) is True


def test_qualification_ready_accepts_zero_scientific_and_selection_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qualification_dir = tmp_path / "qualification"
    qualification_dir.mkdir()
    payload = {
        "status": "complete_qualified",
        "counts": {
            "lane_count": relay.EXPECTED_CORRIDORS,
            "dynamic_mrp_lane_count": 2,
            "static_mrp_lane_count": 16,
            "full_dynamic_cascade_proven_count": 0,
            "selected_dossier_count": 0,
        },
        "selection_guard": {
            "all_selected_campaign_dossiers_shipment_exercised": True,
            "all_replayed_dossiers_shipment_to_receipt_exercised": True,
            "selection_proves_full_dynamic_cascade": False,
        },
    }
    monkeypatch.setattr(
        qualification_v5,
        "validate_qualification_sidecar",
        lambda **_kwargs: payload,
    )
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        lot_replay_root=tmp_path / "lots",
        qualification_dir=qualification_dir,
    )
    instance._lot_selection = lambda: []

    assert relay.FullCampaignRelayV5._qualification_ready(instance) is True


def test_relay_builds_and_validates_physical_qualification_before_delivery(
    tmp_path: Path,
) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        lot_replay_root=tmp_path / "lots",
        qualification_dir=tmp_path / "qualification",
    )
    commands: list[list[str]] = []
    instance._python_module = lambda module, *args: [module, *args]
    instance.run_step = lambda **kwargs: commands.append(list(kwargs["command"]))
    instance._selected_dossiers_physically_exercised = lambda: True
    instance._qualification_ready = lambda: True
    instance._record_artifact = lambda *_args: None

    relay.FullCampaignRelayV5.qualify_physical_cascades(instance)

    assert [command[1] for command in commands] == [
        "validate-selection",
        "build",
        "validate",
    ]
    assert all(command[0] == relay.QUALIFICATION_MODULE for command in commands)
    assert "--replay-root" not in commands[0]
    assert "--replay-root" in commands[1]
    assert "--output-dir" in commands[1]


def test_client_delivery_uses_v5_renderer_and_hides_technical_pages(
    tmp_path: Path,
) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        final_html=tmp_path / "final.html",
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        sidecar_dir=tmp_path / "curves",
        lot_replay_root=tmp_path / "lots",
        qualification_dir=tmp_path / "qualification",
        action_replay_root=tmp_path / "actions",
        dashboard_html=tmp_path / "technical-dashboard.html",
        legacy_risk_html=tmp_path / "legacy-risk.html",
        legacy_control_html=tmp_path / "legacy-control.html",
    )
    commands: list[list[str]] = []
    instance._qualification_ready = lambda: True
    instance.validate_required_action_outcome = lambda: "complete_validated"
    instance.validate_required_curves_outcome = lambda: None
    instance._python_module = lambda module, *args: [module, *args]
    instance.run_step = lambda **kwargs: commands.append(list(kwargs["command"]))
    instance._record_artifact = lambda *_args: None

    relay.FullCampaignRelayV5.build_final_delivery(instance, 3)

    assert commands[0][0] == relay.DELIVERY_MODULE
    assert "--qualification-dir" in commands[0]
    assert "--lot-replay-root" in commands[0]
    assert "--dashboard-html" not in commands[0]
    assert "--legacy-risk-html" not in commands[0]
    assert "--legacy-control-html" not in commands[0]
    assert commands[1][0] == relay.DELIVERY_MODULE
    assert commands[1][1] == "validate"


def test_existing_client_delivery_must_match_all_current_downstream_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "final.html"
    output.write_text("fixture", encoding="utf-8")
    manifest_path = Path(str(output) + ".manifest.json")
    expected_bindings = {
        "campaign": {"signature": "a" * 64},
        "curves": {"signature": "b" * 64},
        "lot_replay": {"signature": "c" * 64},
        "actions": {"signature": "d" * 64},
        "physical_qualification": {"signature": "e" * 64},
        "linked_pages_present_but_not_exposed_as_views": False,
    }
    manifest = {
        "generator": str(Path(delivery_v5.__file__).resolve()),
        "generator_sha256": relay.relay_v4.sha256_file(
            Path(delivery_v5.__file__).resolve()
        ),
        "source_bindings": {**expected_bindings, "curves": None},
    }
    relay.relay_v4._atomic_json(manifest_path, manifest)  # noqa: SLF001

    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(
        final_html=output,
        campaign_root=tmp_path / "campaign",
        results_dir=tmp_path / "results",
        sidecar_dir=tmp_path / "curves",
        lot_replay_root=tmp_path / "lots",
        qualification_dir=tmp_path / "qualification",
        action_replay_root=tmp_path / "actions",
    )
    instance._validate_legacy_html_inventory = lambda: None
    instance.validate_required_action_outcome = lambda: "complete_validated"
    instance.validate_required_curves_outcome = lambda: None
    instance.revalidate_published_optional_products = lambda: None
    instance._qualification_ready = lambda: True
    instance._lot_selection = lambda: [{"dossier": "selected"}]
    instance._step_child_running = lambda _step: False
    monkeypatch.setattr(delivery_v5, "validate_delivery", lambda _path: {})

    def payload(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        assert kwargs["curves_dir"] == instance.config.sidecar_dir
        assert kwargs["replay_root"] == instance.config.lot_replay_root
        assert kwargs["action_results_root"] == instance.config.action_replay_root
        assert kwargs["dashboard_html"] is None
        assert kwargs["legacy_risk_html"] is None
        assert kwargs["legacy_control_html"] is None
        return {}, expected_bindings

    monkeypatch.setattr(delivery_v5, "build_delivery_payload", payload)

    with pytest.raises(relay.FullCampaignRelayError, match="toutes les sources"):
        relay.FullCampaignRelayV5._final_delivery_ready(instance)

    manifest["source_bindings"] = expected_bindings
    relay.relay_v4._atomic_json(manifest_path, manifest)  # noqa: SLF001
    assert relay.FullCampaignRelayV5._final_delivery_ready(instance) is True


@pytest.mark.parametrize(
    ("adapter", "implementation", "patched_fields"),
    (
        (
            campaign_adapter,
            campaign_adapter.implementation_v4,
            ("v4_bridge", "__file__"),
        ),
        (
            launcher_adapter,
            launcher_adapter.implementation_v4,
            ("v4_bridge", "RUNNER"),
        ),
        (
            finalizer_adapter,
            finalizer_adapter.implementation_v4,
            ("v4_bridge", "SOURCE_RUNNER_SHA256"),
        ),
    ),
)
def test_adapters_patch_only_inside_context_and_restore(
    adapter: Any, implementation: Any, patched_fields: tuple[str, str]
) -> None:
    before = {field: getattr(implementation, field) for field in patched_fields}
    with adapter.patched_v5_context():
        assert implementation.v4_bridge is bridge
        if adapter is campaign_adapter:
            assert (
                Path(implementation.__file__).resolve() == campaign_adapter.ADAPTER_PATH
            )
        elif adapter is launcher_adapter:
            assert implementation.RUNNER == launcher_adapter.RUNNER
        else:
            assert (
                implementation.SOURCE_RUNNER_SHA256
                == finalizer_adapter._sha256_file(  # noqa: SLF001
                    finalizer_adapter.V5_CAMPAIGN_RUNNER
                )
            )
    assert {field: getattr(implementation, field) for field in patched_fields} == before


def test_campaign_adapter_refuses_changed_frozen_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(campaign_adapter, "EXPECTED_V4_IMPLEMENTATION_SHA256", "0" * 64)
    with pytest.raises(campaign_adapter.V5CampaignAdapterError, match="changed"):
        campaign_adapter.validate_frozen_implementation()


def test_prepare_fails_before_any_downstream_output_when_handoff_is_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _strict_config(tmp_path)
    instance = relay.FullCampaignRelayV5(config)

    def reject_handoff() -> dict[str, Any]:
        raise relay.FullCampaignRelayError("calibration incomplète")

    monkeypatch.setattr(instance, "validate_calibration_handoff", reject_handoff)

    with pytest.raises(relay.FullCampaignRelayError, match="incomplète"):
        instance.prepare()

    for path in (
        config.calibration_plan_dir,
        config.calibration_run_dir,
        config.sidecar_dir,
        config.bridge_json,
        config.campaign_root,
        config.results_dir,
        config.lot_replay_root,
        config.qualification_dir,
        config.dashboard_html,
        config.final_html,
        config.supervision_dir,
        config.action_replay_root,
    ):
        assert not path.exists()


def test_main_revalidates_handoff_before_acquiring_relay_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    config = SimpleNamespace(
        supervision_dir=Path("supervision"),
        validate=lambda: events.append("config"),
    )
    instance = SimpleNamespace(
        contract={},
        validate_calibration_handoff=lambda: events.append("handoff"),
        execute=lambda: events.append("execute") or 0,
    )

    class RecordingLock:
        def __enter__(self) -> None:
            events.append("lock_enter")

        def __exit__(self, *_args: Any) -> None:
            events.append("lock_exit")

    parser = SimpleNamespace(
        parse_args=lambda _argv: SimpleNamespace(detach=False)
    )
    monkeypatch.setattr(relay, "_parser", lambda: parser)
    monkeypatch.setattr(relay, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(relay, "FullCampaignRelayV5", lambda _config: instance)
    monkeypatch.setattr(relay, "_relay_lock", lambda _path: RecordingLock())
    monkeypatch.setattr(
        relay.relay_v4,
        "_prevent_sleep",
        lambda enabled: events.append(f"sleep_{enabled}"),
    )

    assert relay.main([]) == 0
    assert events == [
        "sleep_True",
        "config",
        "handoff",
        "lock_enter",
        "execute",
        "lock_exit",
        "sleep_False",
    ]


def test_execute_is_downstream_only_and_orders_qualified_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.status = {}
    instance.config = SimpleNamespace(action_replay_root=Path("actions"))
    events: list[str] = []

    def event(name: str, result: Any = None) -> Any:
        events.append(name)
        return result

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("une méthode de calibration a été appelée par le handoff")

    for method_name in (
        "prepare_v5_plan",
        "run_development",
        "finalize_development",
        "ensure_sidecar_watcher",
        "run_holdout",
        "finalize_holdout",
        "wait_for_sidecar_inventory",
    ):
        monkeypatch.setattr(instance, method_name, forbidden)

    monkeypatch.setattr(instance, "prepare", lambda: event("handoff_preflight"))
    monkeypatch.setattr(
        instance,
        "validate_downstream_corridor_preflight",
        lambda: event("corridor_preflight"),
    )
    monkeypatch.setattr(
        instance, "build_and_validate_bridge", lambda: event("bridge")
    )
    monkeypatch.setattr(instance, "plan_campaign", lambda: event("campaign_plan"))
    monkeypatch.setattr(instance, "launch_campaign", lambda: event("campaign_run"))
    monkeypatch.setattr(
        instance, "finalize_campaign", lambda: event("campaign_finalize")
    )
    monkeypatch.setattr(instance, "_lot_selection", lambda: event("selection", []))
    monkeypatch.setattr(instance, "run_lot_replays", lambda _rows: event("lots"))
    monkeypatch.setattr(
        instance,
        "qualify_physical_cascades",
        lambda: event("physical_qualification"),
    )

    def actions() -> None:
        event("actions")
        instance.status["action_replay"] = {
            "status": "complete_no_representable_action"
        }

    def curves() -> bool:
        event("curves")
        instance.status["nominal_curves"] = {"status": "complete_validated"}
        return True

    monkeypatch.setattr(instance, "process_optional_action_replay", actions)
    monkeypatch.setattr(
        instance,
        "validate_required_action_outcome",
        lambda: event("actions_validated"),
    )
    monkeypatch.setattr(instance, "process_optional_curves", curves)
    monkeypatch.setattr(
        instance,
        "validate_required_curves_outcome",
        lambda: event("curves_validated"),
    )
    monkeypatch.setattr(instance, "build_dashboard", lambda: event("dashboard"))
    monkeypatch.setattr(
        instance, "build_final_delivery", lambda _count: event("renderer_v5")
    )
    monkeypatch.setattr(
        instance, "update_status", lambda *_args, **_kwargs: event("complete")
    )

    assert relay.FullCampaignRelayV5.execute(instance) == 0
    assert events == [
        "handoff_preflight",
        "corridor_preflight",
        "bridge",
        "campaign_plan",
        "campaign_run",
        "campaign_finalize",
        "selection",
        "lots",
        "physical_qualification",
        "actions",
        "actions_validated",
        "curves",
        "curves_validated",
        "dashboard",
        "renderer_v5",
        "complete",
    ]


@pytest.mark.parametrize(
    ("method_name", "args"),
    (
        ("prepare_v5_plan", ()),
        ("run_development", ()),
        ("finalize_development", ()),
        ("ensure_sidecar_watcher", ()),
        ("run_holdout", (1234,)),
        ("finalize_holdout", ()),
    ),
)
def test_calibration_mutation_methods_are_disabled(
    method_name: str, args: tuple[Any, ...]
) -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    with pytest.raises(relay.FullCampaignRelayError, match="aval uniquement"):
        getattr(instance, method_name)(*args)


def test_relay_pins_the_frozen_v4_and_v5_implementation_hashes() -> None:
    instance = object.__new__(relay.FullCampaignRelayV5)
    instance.config = SimpleNamespace(repo=Path(__file__).resolve().parents[4])
    rows = relay.FullCampaignRelayV5._module_inventory_v5(instance)
    by_module = {row["module"]: row["sha256"] for row in rows}
    assert by_module[relay.CORE_MODULE] == relay.FROZEN_V5_SHA256[relay.CORE_MODULE]
    assert all(
        by_module[module] == digest for module, digest in relay.FROZEN_V4_SHA256.items()
    )
