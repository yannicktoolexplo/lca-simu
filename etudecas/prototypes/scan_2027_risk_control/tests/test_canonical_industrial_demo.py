from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

import etudecas.prototypes.scan_2027_risk_control.canonical_industrial_demo as demo_module

from etudecas.prototypes.scan_2027_risk_control.canonical_industrial_demo import (
    CASCADE_COMPARISON_FIELDS,
    CASCADE_RUN_FIELDS,
    _is_approximated_fidelity,
    build_industrial_demo_pack,
)


TEST_PLOTLY_BYTES = (
    b"/**\n* plotly.js v2.32.0\n*/\n" + b"/* scattergeo */\n" + b"x" * 3_000_000
)
TEST_TOPOJSON_PAYLOAD = {
    "type": "Topology",
    "objects": {"countries": {}, "land": {}},
    "arcs": [[[0, 0], [1, 1]]],
    "metadata": {"padding": "x" * 100_000},
}
TEST_TOPOJSON_BYTES = json.dumps(TEST_TOPOJSON_PAYLOAD).encode("utf-8")
TEST_GRAPH_BYTES = b'{"graph":"fixture"}\n'
TEST_ENGINE_BYTES = b"# fixture engine\n"
TEST_PROFILE_BYTES = b'{"profile":"fixture"}\n'
TEST_RISK_BYTES = {
    "quality_021081": b"event_id,risk_type\nINC-1,quality_delay\n",
    "delay_338929": b"event_id,risk_type\nINC-2,lead_time_extra_days\n",
}


def _digest(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _file_record(path: Path, *, row_count: int | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "filename": path.name,
        "path": str(path.resolve()),
        "exists": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


@pytest.fixture(autouse=True)
def _use_deterministic_distribution_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        demo_module,
        "PLOTLY_SHA256",
        hashlib.sha256(TEST_PLOTLY_BYTES).hexdigest(),
    )
    monkeypatch.setattr(
        demo_module,
        "WORLD_TOPOJSON_SHA256",
        hashlib.sha256(TEST_TOPOJSON_BYTES).hexdigest(),
    )


def _write_csv(
    path: Path, fieldnames: list[str], rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _row in csv.DictReader(handle))


def _refresh_fixture_integrity(cascade_dir: Path, trajectory_dir: Path) -> None:
    """Re-sign a synthetic fixture after an intentional semantic test mutation."""

    runs_path = cascade_dir / "canonical_cascade_runs.csv"
    comparison_path = cascade_dir / "canonical_cascade_comparison.csv"
    summary_path = cascade_dir / "canonical_cascade_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    campaign_source = Path(summary["campaign"]["path"])
    campaign_runs_path = campaign_source / "canonical_cascade_runs.csv"
    campaign_runs_path.write_bytes(runs_path.read_bytes())
    commands_path = campaign_source / "canonical_cascade_commands.json"
    config_snapshot_path = campaign_source / "canonical_cascade_config_snapshot.json"
    manifest_path = campaign_source / "canonical_cascade_manifest.json"
    graph_path = campaign_source / "graph.json"
    engine_path = campaign_source / "engine.py"
    profile_path = campaign_source / "engine-profile.json"
    profile_record = _file_record(profile_path)
    profile_record["source_path"] = profile_record.pop("path")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema_version": "scan.canonical_cascade_manifest.v2",
            "status": "complete",
            "artifact_profile": "full",
            "scenario_id": "scn:BASE",
            "failure_count": 0,
            "skipped_fail_fast_count": 0,
            "run_count": _csv_row_count(campaign_runs_path),
            "outputs": {
                "runs": str(campaign_runs_path.resolve()),
                "commands": str(commands_path.resolve()),
                "config_snapshot": str(config_snapshot_path.resolve()),
            },
            "output_sha256": {
                "runs": hashlib.sha256(campaign_runs_path.read_bytes()).hexdigest(),
                "commands": hashlib.sha256(commands_path.read_bytes()).hexdigest(),
                "config_snapshot": hashlib.sha256(
                    config_snapshot_path.read_bytes()
                ).hexdigest(),
            },
            "config": {
                "path": str(config_snapshot_path.resolve()),
                "snapshot": str(config_snapshot_path.resolve()),
                "sha256": hashlib.sha256(config_snapshot_path.read_bytes()).hexdigest(),
            },
            "graph": _file_record(graph_path),
            "engine": _file_record(engine_path),
            "engine_profile": profile_record,
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    summary.update(
        {
            "schema_version": "scan.canonical_cascade_summary.v2",
            "comparison_row_count": _csv_row_count(comparison_path),
            "campaign": {
                "path": str(campaign_source.resolve()),
                "manifest": str(manifest_path.resolve()),
                "manifest_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
                "runs": str(campaign_runs_path.resolve()),
                "runs_sha256": hashlib.sha256(
                    campaign_runs_path.read_bytes()
                ).hexdigest(),
                "status": "complete",
            },
            "outputs": {
                "runs_csv": str(runs_path.resolve()),
                "runs_csv_sha256": hashlib.sha256(runs_path.read_bytes()).hexdigest(),
                "comparison_csv": str(comparison_path.resolve()),
                "comparison_csv_sha256": hashlib.sha256(
                    comparison_path.read_bytes()
                ).hexdigest(),
            },
        }
    )
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    compact_path = trajectory_dir / "canonical_cascade_trajectories_compact.json"
    long_path = trajectory_dir / "canonical_cascade_trajectories_long.csv"
    trajectory_manifest_path = (
        trajectory_dir / "canonical_cascade_trajectories_manifest.json"
    )
    trajectory_manifest = json.loads(
        trajectory_manifest_path.read_text(encoding="utf-8")
    )
    compact = json.loads(compact_path.read_text(encoding="utf-8"))
    trajectory_manifest.update(
        {
            "schema_version": "scan.canonical_cascade_trajectory_manifest.v1",
            "status": "complete",
            "config_snapshot": {
                "path": str(config_snapshot_path.resolve()),
                "sha256": hashlib.sha256(config_snapshot_path.read_bytes()).hexdigest(),
            },
            "runs_csv": {
                "path": str(campaign_runs_path.resolve()),
                "sha256": hashlib.sha256(campaign_runs_path.read_bytes()).hexdigest(),
            },
            "days": len(compact["day_axis"]),
            "run_count": _csv_row_count(campaign_runs_path),
            "cascade_ids": sorted(compact["cascades"]),
            "long_row_count": _csv_row_count(long_path),
            "outputs": {
                "long_csv": str(long_path.resolve()),
                "long_csv_sha256": hashlib.sha256(long_path.read_bytes()).hexdigest(),
                "compact_json": str(compact_path.resolve()),
                "compact_json_sha256": hashlib.sha256(
                    compact_path.read_bytes()
                ).hexdigest(),
            },
        }
    )
    trajectory_manifest_path.write_text(
        json.dumps(trajectory_manifest), encoding="utf-8"
    )
    _refresh_registry_quality_contract(cascade_dir)


def _refresh_summary_manifest_hash(cascade_dir: Path) -> None:
    summary_path = cascade_dir / "canonical_cascade_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest_path = Path(summary["campaign"]["manifest"])
    summary["campaign"]["manifest_sha256"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")


def _refresh_registry_quality_contract(cascade_dir: Path) -> None:
    summary = json.loads(
        (cascade_dir / "canonical_cascade_summary.json").read_text(encoding="utf-8")
    )
    campaign_source = Path(summary["campaign"]["path"])
    runs_path = campaign_source / "canonical_cascade_runs.csv"
    with runs_path.open(encoding="utf-8", newline="") as handle:
        runs = list(csv.DictReader(handle))
    cascades = ("quality_021081", "delay_338929")
    for index, cascade_id in enumerate(cascades, start=1):
        registry = cascade_dir.parent / f"registry-{index}"
        if not registry.is_dir():
            continue
        matching = [
            row
            for row in runs
            if row["cascade_id"] == cascade_id
            and row["variant_id"] == "incident_no_action"
            and row["seed"] == "101"
        ]
        assert len(matching) == 1
        run_row = matching[0]
        run_root = Path(run_row["result_dir"])
        source_data = run_root / "data"
        source_data.mkdir(parents=True, exist_ok=True)
        lot_events = source_data / "production_lot_events.csv"
        if not lot_events.is_file():
            _write_csv(
                lot_events,
                ["event_id", "day", "event_type", "lot_id"],
                [
                    {
                        "event_id": f"LOT-{index}",
                        "day": 0,
                        "event_type": "opening_stock",
                        "lot_id": f"LOT-{index}",
                    }
                ],
            )
        risk_path = campaign_source / f"risk-{cascade_id}.csv"
        manifest_path = campaign_source / "canonical_cascade_manifest.json"
        commands_path = campaign_source / "canonical_cascade_commands.json"
        config_path = campaign_source / "canonical_cascade_config_snapshot.json"
        component_hashes = json.loads(
            run_row["measurement_start_component_sha256_json"]
        )
        provenance = {
            "schema_version": "risk-lot-impact-provenance/1.0",
            "verification_status": "campaign_run_verified",
            "identity": {
                "campaign_id": campaign_source.name,
                "cascade_id": cascade_id,
                "variant_id": "incident_no_action",
                "case_type": "incident_no_action",
                "solution_id": None,
                "seed": 101,
                "scenario_id": "scn:BASE",
            },
            "critical_hashes": {
                "campaign_manifest_sha256": _digest(manifest_path.read_bytes()),
                "campaign_runs_sha256": _digest(runs_path.read_bytes()),
                "campaign_commands_sha256": _digest(commands_path.read_bytes()),
                "campaign_config_snapshot_sha256": _digest(config_path.read_bytes()),
                "risk_events_sha256": _digest(risk_path.read_bytes()),
                "control_schedule_sha256": None,
                "measurement_start_state_sha256": run_row[
                    "measurement_start_state_sha256"
                ],
                "run_summary_sha256": None,
                "run_manifest_sha256": None,
            },
            "source_files": {
                "lot_events": {
                    **_file_record(lot_events, row_count=_csv_row_count(lot_events)),
                    "required": True,
                    "read_status": "read_from_single_byte_snapshot",
                }
            },
            "parent_run": {
                "detected": True,
                "root": str(run_root.resolve()),
                "measurement_start_state_sha256": run_row[
                    "measurement_start_state_sha256"
                ],
                "measurement_start_component_sha256": component_hashes,
            },
            "parent_campaign": {
                "detected": True,
                "root": str(campaign_source.resolve()),
                "manifest": _file_record(manifest_path),
                "runs": {
                    **_file_record(runs_path),
                    "row_count": _csv_row_count(runs_path),
                },
                "commands": {
                    **_file_record(commands_path),
                    "entry_count": len(
                        json.loads(commands_path.read_text(encoding="utf-8"))
                    ),
                },
                "config_snapshot": _file_record(config_path),
                "risk_events": {
                    **_file_record(risk_path),
                    "row_count": _csv_row_count(risk_path),
                },
                "control_schedule": None,
                "matched_run_ledger_row": {
                    "cascade_id": cascade_id,
                    "variant_id": "incident_no_action",
                    "case_type": "incident_no_action",
                    "solution_id": None,
                    "seed": 101,
                    "status": "ok",
                    "result_dir": str(run_root.resolve()),
                },
            },
        }
        output_records: dict[str, dict[str, object]] = {}
        for table_name, filename in demo_module.RISK_REGISTRY_CSV_FILENAMES.items():
            path = registry / filename
            output_records[table_name] = {
                "filename": filename,
                "sha256": _digest(path.read_bytes()),
                "size_bytes": path.stat().st_size,
                "row_count": _csv_row_count(path),
            }
        quality = {
            "status": "complete",
            "cascade_id": cascade_id,
            "provenance": provenance,
            "registry_outputs": {
                "output_dir": str(registry.resolve()),
                "csv_artifacts": output_records,
                "quality_json": {
                    "filename": "risk_impact_quality.json",
                    "sha256": None,
                    "self_hash_status": (
                        "intentionally_excluded_to_avoid_recursive_self_hash"
                    ),
                },
            },
        }
        (registry / "risk_impact_quality.json").write_text(
            json.dumps(quality), encoding="utf-8"
        )


def _run_row(
    cascade_id: str, seed: int, case_type: str, solution_id: str
) -> dict[str, object]:
    row: dict[str, object] = {field: "" for field in CASCADE_RUN_FIELDS}
    variant_id = (
        "normal"
        if case_type == "normal"
        else "incident_no_action"
        if case_type == "incident_no_action"
        else f"incident_{solution_id}"
    )
    row.update(
        {
            "cascade_id": cascade_id,
            "variant_id": variant_id,
            "case_type": case_type,
            "solution_id": solution_id if case_type == "incident_with_solution" else "",
            "seed": seed,
            "status": "ok",
            "result_dir": f"run-{seed}",
            "customer_id": "C-XXXXX",
            "finished_item_id": "item:268967"
            if "021081" in cascade_id
            else "item:268091",
            "customer_shortage_days": 4,
            "customer_backlog_qty_days": 1200,
            "recovery_day": 18,
            "customer_demand_qty": 10000,
            "customer_served_qty": 9800,
            "production_qty": 9700,
            "production_lot_count": 2,
            "target_stock_qty_days": 25000,
            "base_operational_supply_cost": 480000,
            "controllable_operating_cost": 500000,
            "decision_total_cost": 502000,
            "decision_transport_cost": 12000,
            "external_purchase_cost": 0,
            "supplier_risk_applied_row_count": 1,
            "supplier_risk_applied_event_ids": (
                "INC-1" if "021081" in cascade_id else "INC-2"
            ),
            "action_execution_status": "fully_verified",
            "measurement_start_state_sha256": _digest(f"j0-{cascade_id}-{seed}"),
            "measurement_start_component_sha256_json": json.dumps(
                {"inventory": _digest(f"inventory-{cascade_id}-{seed}")}
            ),
            "risk_events_sha256": _digest(TEST_RISK_BYTES[cascade_id]),
            "graph_sha256": _digest(TEST_GRAPH_BYTES),
            "engine_profile_sha256": _digest(TEST_PROFILE_BYTES),
            "pairing_status": "measurement_start_state_matched",
            "incident_validation_status": "physically_applied_with_customer_exposure",
        }
    )
    if case_type == "normal":
        row.update(
            {
                "customer_shortage_days": 0,
                "customer_backlog_qty_days": 0,
                "customer_served_qty": row["customer_demand_qty"],
                "supplier_risk_applied_row_count": 0,
                "supplier_risk_applied_event_ids": "",
                "incident_validation_status": "reference_no_incident",
            }
        )
    return row


def _comparison_row(
    cascade_id: str,
    solution_id: str,
    seed: int,
    *,
    fidelity: str = "native",
    notes: str = "action observee",
) -> dict[str, object]:
    row: dict[str, object] = {field: "" for field in CASCADE_COMPARISON_FIELDS}
    row.update(
        {
            "cascade_id": cascade_id,
            "solution_id": solution_id,
            "variant_id": f"incident_{solution_id}",
            "seed": seed,
            "lever_fidelity": fidelity,
            "pairing_status": "measurement_start_state_matched",
            "incident_application_verified": "true",
            "incident_signal_detected": "true",
            "customer_exposure_detected": "true",
            "customer_exposure_status": "customer_exposed",
            "ranking_eligible": "true",
            "ranking_exclusion_reasons": "",
            "days_recovered_vs_no_action": 3 + seed % 2,
            "recovery_status": "both_recovered",
            "shortage_days_avoided": 2,
            "gross_positive_customer_service_gain_qty": 800 + seed,
            "net_customer_service_gain_qty": 700 + seed,
            "gross_positive_production_gain_qty": 1000,
            "net_production_gain_qty": 800,
            "gross_positive_production_lot_equivalent": 0.5,
            "gross_additional_mrp_release_qty": 900,
            "net_mrp_release_qty": 700,
            "incremental_decision_total_cost_vs_no_action": 2400 + seed,
            "incremental_controllable_operating_cost_vs_no_action": 2200 + seed,
            "incremental_decision_transport_cost_vs_no_action": 200,
            "incremental_external_purchase_cost_vs_no_action": 0,
            "incremental_stock_qty_days": 450,
            "no_action_incremental_customer_backlog_qty_days": 900,
            "remaining_customer_impact_ratio": 0.35,
            "remaining_incremental_customer_backlog_qty_days": 300,
            "action_execution_status": "fully_verified",
            "evidence_notes": notes,
        }
    )
    return row


def _fixture(tmp_path: Path) -> tuple[Path, Path, list[Path], list[Path]]:
    cascade_dir = tmp_path / "cascade"
    campaign_source = tmp_path / "campaign-source"
    campaign_source.mkdir()
    (campaign_source / "graph.json").write_bytes(TEST_GRAPH_BYTES)
    (campaign_source / "engine.py").write_bytes(TEST_ENGINE_BYTES)
    (campaign_source / "engine-profile.json").write_bytes(TEST_PROFILE_BYTES)
    for cascade_id, content in TEST_RISK_BYTES.items():
        (campaign_source / f"risk-{cascade_id}.csv").write_bytes(content)
    cascades = ("quality_021081", "delay_338929")
    runs = []
    comparisons = []
    for cascade_id in cascades:
        for seed in range(101, 111):
            runs.extend(
                [
                    _run_row(cascade_id, seed, "normal", "none"),
                    _run_row(cascade_id, seed, "incident_no_action", "none"),
                    _run_row(cascade_id, seed, "incident_with_solution", "expedite"),
                ]
            )
            comparisons.append(
                _comparison_row(
                    cascade_id,
                    "expedite",
                    seed,
                    fidelity="mixed" if cascade_id == "delay_338929" else "native",
                    notes="equivalent lot; </script><script>alert('x')</script>",
                )
            )
    for row in runs:
        row["result_dir"] = str(
            (
                campaign_source
                / "runs"
                / str(row["cascade_id"])
                / str(row["variant_id"])
                / f"seed_{row['seed']}"
            ).resolve()
        )
    _write_csv(
        cascade_dir / "canonical_cascade_runs.csv", sorted(CASCADE_RUN_FIELDS), runs
    )
    _write_csv(
        cascade_dir / "canonical_cascade_comparison.csv",
        sorted(CASCADE_COMPARISON_FIELDS),
        comparisons,
    )
    (campaign_source / "canonical_cascade_config_snapshot.json").write_text(
        json.dumps(
            {
                "schema_version": "test",
                "cascades": [
                    {
                        "id": "quality_021081",
                        "customer_id": "C-XXXXX",
                        "finished_item_id": "item:268967",
                        "solutions": [{"id": "expedite"}],
                        "incident": {
                            "start_day": 0,
                            "end_day": 30,
                            "risk_events": [
                                {
                                    "event_id": "INC-1",
                                    "supplier_id": "SDC-VD0960508A",
                                    "dst_node_id": "SDC-1450",
                                    "item_id": "item:021081",
                                    "edge_id": "edge:quality",
                                    "multiplier": 45,
                                }
                            ],
                        },
                    },
                    {
                        "id": "delay_338929",
                        "customer_id": "C-XXXXX",
                        "finished_item_id": "item:268091",
                        "solutions": [{"id": "expedite"}],
                        "incident": {
                            "start_day": 120,
                            "end_day": 179,
                            "risk_events": [
                                {
                                    "event_id": "INC-2",
                                    "supplier_id": "SDC-VD0914360C",
                                    "dst_node_id": "M-1810",
                                    "item_id": "item:338929",
                                    "edge_id": "edge:delay",
                                    "multiplier": 35,
                                }
                            ],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (campaign_source / "canonical_cascade_runs.csv").write_bytes(
        (cascade_dir / "canonical_cascade_runs.csv").read_bytes()
    )
    (campaign_source / "canonical_cascade_commands.json").write_text(
        json.dumps(
            [
                {
                    "cascade_id": row["cascade_id"],
                    "variant_id": row["variant_id"],
                    "seed": row["seed"],
                    "command": ["python", "engine.py"],
                }
                for row in runs
            ]
        ),
        encoding="utf-8",
    )
    (campaign_source / "canonical_cascade_manifest.json").write_text(
        json.dumps({"schema_version": "pending"}), encoding="utf-8"
    )
    (cascade_dir / "canonical_cascade_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_cascade_summary.v2",
                "cascade_count": 2,
                "campaign": {"path": str(campaign_source)},
            }
        ),
        encoding="utf-8",
    )

    registries = []
    for index, cascade_id in enumerate(cascades, start=1):
        registry = tmp_path / f"registry-{index}"
        _write_csv(
            registry / "risk_impact_incidents.csv",
            [
                "registry_version",
                "incident_id",
                "causality_level",
                "supplier_id",
                "dst_node_id",
                "item_id",
                "edge_id",
            ],
            [
                {
                    "registry_version": "v1",
                    "incident_id": f"INC-{index}",
                    "causality_level": "native_transaction",
                    "supplier_id": (
                        "SDC-VD0960508A" if index == 1 else "SDC-VD0914360C"
                    ),
                    "dst_node_id": "SDC-1450" if index == 1 else "M-1810",
                    "item_id": "item:021081" if index == 1 else "item:338929",
                    "edge_id": "edge:quality" if index == 1 else "edge:delay",
                }
            ],
        )
        _write_csv(
            registry / "risk_impact_entities.csv",
            [
                "registry_version",
                "incident_id",
                "entity_type",
                "entity_id",
                "item_id",
                "node_id",
                "lower_qty",
                "upper_qty",
                "causality_level",
            ],
            [
                {
                    "registry_version": "v1",
                    "incident_id": f"INC-{index}",
                    "entity_type": "finished_lot",
                    "entity_id": f"LOT-{index}",
                    "item_id": "item:268967" if index == 1 else "item:268091",
                    "node_id": "M-1430" if index == 1 else "M-1810",
                    "lower_qty": 400,
                    "upper_qty": 500,
                    "causality_level": "physical_genealogy",
                }
            ],
        )
        _write_csv(
            registry / "risk_impact_client_service.csv",
            [
                "registry_version",
                "incident_id",
                "client_service_event_id",
                "client_lot_id",
                "day",
                "client_node_id",
                "item_id",
                "served_exposed_qty_lower",
                "served_exposed_qty_upper",
                "uom",
                "causality_level",
            ],
            [
                {
                    "registry_version": "v1",
                    "incident_id": f"INC-{index}",
                    "client_service_event_id": f"SERVICE-{index}",
                    "client_lot_id": f"LOT-{index}",
                    "day": 2,
                    "client_node_id": "C-XXXXX",
                    "item_id": "item:268967" if index == 1 else "item:268091",
                    "served_exposed_qty_lower": 100,
                    "served_exposed_qty_upper": 120,
                    "uom": "UN",
                    "causality_level": "native_transaction",
                }
            ],
        )
        _write_csv(
            registry / "risk_impact_costs.csv",
            [
                "registry_version",
                "exposure_bundle_id",
                "shipment_id",
                "transport_cost_actual_exposed",
                "incremental_total_cost_status",
            ],
            [
                {
                    "registry_version": "v1",
                    "exposure_bundle_id": f"BUNDLE-{index}",
                    "shipment_id": f"SHIP-{index}",
                    "transport_cost_actual_exposed": 42,
                    "incremental_total_cost_status": (
                        "not_identified_without_matched_counterfactual"
                    ),
                }
            ],
        )
        _write_csv(
            registry / "risk_impact_bundle_events.csv",
            [
                "registry_version",
                "incident_id",
                "exposure_bundle_id",
                "causality_level",
            ],
            [
                {
                    "registry_version": "v1",
                    "incident_id": f"INC-{index}",
                    "exposure_bundle_id": f"BUNDLE-{index}",
                    "causality_level": "native_transaction",
                }
            ],
        )
        _write_csv(
            registry / "risk_impact_exposure_bundles.csv",
            ["registry_version", "exposure_bundle_id", "shipment_id"],
            [
                {
                    "registry_version": "v1",
                    "exposure_bundle_id": f"BUNDLE-{index}",
                    "shipment_id": f"SHIP-{index}",
                }
            ],
        )
        _write_csv(
            registry / "risk_impact_edges.csv",
            [
                "registry_version",
                "incident_id",
                "edge_id",
                "source_uom",
                "target_uom",
            ],
            [
                {
                    "registry_version": "v1",
                    "incident_id": f"INC-{index}",
                    "edge_id": f"IMPACT-EDGE-{index}",
                    "source_uom": "UN",
                    "target_uom": "UN",
                }
            ],
        )
        (registry / "risk_impact_quality.json").write_text(
            json.dumps({"status": "complete", "cascade_id": cascade_id}),
            encoding="utf-8",
        )
        registries.append(registry)

    trajectory_dir = tmp_path / "trajectories"
    trajectory_dir.mkdir()
    trajectory_cascades: dict[str, object] = {}
    for cascade_id in cascades:
        finished_item = "item:268967" if "021081" in cascade_id else "item:268091"
        series = [
            {
                "path_stage_index": 5,
                "path_stage_kind": "transport",
                "path_node_role": "customer",
                "stage_from_node_id": "DC-1920",
                "stage_to_node_id": "C-XXXXX",
                "node_id": "C-XXXXX",
                "item_id": finished_item,
                "metric": "customer_backlog_end_qty",
                "uom": "UN",
                "source_semantics": "dense_exact_daily",
                "mean": [0.0, 10.0, 0.0],
                "min": [0.0, 8.0, 0.0],
                "max": [0.0, 12.0, 0.0],
            }
        ]
        trajectory_cascades[cascade_id] = {
            "customer_id": "C-XXXXX",
            "finished_item_id": finished_item,
            "path": [],
            "variants": {
                "normal": {
                    "variant_role": "normal",
                    "case_type": "normal",
                    "solution_id": "none",
                    "seed_count": 10,
                    "series": series,
                },
                "incident_no_action": {
                    "variant_role": "no_action",
                    "case_type": "incident_no_action",
                    "solution_id": "none",
                    "seed_count": 10,
                    "series": series,
                },
                "incident_expedite": {
                    "variant_role": "solution:expedite",
                    "case_type": "incident_with_solution",
                    "solution_id": "expedite",
                    "seed_count": 10,
                    "series": series,
                },
            },
        }
    (trajectory_dir / "canonical_cascade_trajectories_compact.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_cascade_trajectory_envelopes.v1",
                "day_axis": [0, 1, 2],
                "statistics": ["mean", "min", "max"],
                "cascades": trajectory_cascades,
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        trajectory_dir / "canonical_cascade_trajectories_long.csv",
        ["schema_version", "cascade_id", "day", "value"],
        [
            {
                "schema_version": "scan.canonical_cascade_trajectories.v1",
                "cascade_id": "quality_021081",
                "day": 0,
                "value": 0,
            }
        ],
    )
    (trajectory_dir / "canonical_cascade_trajectories_manifest.json").write_text(
        json.dumps({"schema_version": "pending", "series_count": 6}), encoding="utf-8"
    )
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    assets = []
    for name in ("industrial.html", "nodes.html"):
        path = tmp_path / name
        path.write_text(f"<!doctype html><title>{name}</title>", encoding="utf-8")
        assets.append(path)
    network_map = tmp_path / "map.html"
    network_map.write_text(
        '<!doctype html><script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>',
        encoding="utf-8",
    )
    assets.append(network_map)
    plotly_js = tmp_path / "plotly-2.32.0.min.js"
    plotly_js.write_bytes(TEST_PLOTLY_BYTES)
    assets.append(plotly_js)
    plotly_topojson = tmp_path / "world_110m.json"
    plotly_topojson.write_bytes(TEST_TOPOJSON_BYTES)
    assets.append(plotly_topojson)
    return cascade_dir, trajectory_dir, registries, assets


def _build_fixture_demo(
    tmp_path: Path,
    cascade_dir: Path,
    trajectory_dir: Path,
    registries: list[Path],
    assets: list[Path],
) -> object:
    return build_industrial_demo_pack(
        cascade_dir=cascade_dir,
        trajectory_dir=trajectory_dir,
        risk_registry_dirs=registries,
        output_dir=tmp_path / "demo",
        industrial_dashboard=assets[0],
        node_dashboard=assets[1],
        network_map=assets[2],
        plotly_js=assets[3],
        plotly_topojson=assets[4],
    )


def test_builds_french_offline_demo_and_preserves_sources(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    source_bytes = {path: path.read_bytes() for path in assets}

    result = build_industrial_demo_pack(
        cascade_dir=cascade_dir,
        trajectory_dir=trajectory_dir,
        risk_registry_dirs=registries,
        output_dir=tmp_path / "demo",
        industrial_dashboard=assets[0],
        node_dashboard=assets[1],
        network_map=assets[2],
        plotly_js=assets[3],
        plotly_topojson=assets[4],
    )

    document = result.index_path.read_text(encoding="utf-8")
    assert "Du risque fournisseur à la décision opérationnelle" in document
    assert (
        "Retenue de libération qualité simulée sur une chaîne multi-étages" in document
    )
    assert "Retard fournisseur" in document
    assert "Comparer toutes les solutions" in document
    assert "Des flux touchés aux lots livrés" in document
    assert "Part des simulations avec retard client" in document
    assert "unités·jours de retard en moyenne" in document
    assert "Ce n’est ni un nombre de commandes" in document
    assert "Périmètre de la preuve détaillée" in document
    assert "graine 101" in document
    assert "volumes livrés avec ascendance exposée" in document.lower()
    assert "allocation fifo simulée du stock source" in document.lower()
    assert (
        "attribution exacte d’une expédition source à une commande client" in document
    )
    assert "Référence saine" not in document
    assert "Quarantaine qualité multi-étages" not in document
    assert "partiellement approché" in document
    assert "Référence sans incident" in document
    assert "Incident sans action" in document
    assert "État au jour 0 identique" in document
    assert "Courbes quotidiennes" in document
    assert "Trajectoires scientifiques complètes incluses" in document
    assert "data/canonical_cascade_trajectories_long.csv" in document
    assert "sans troncature scientifique" in document
    assert "trajectory-data" in document
    assert "scroll-margin-top:96px" in document
    assert "comparaison(s)" not in document
    assert "simulation(s)" not in document
    assert "jour(s)" not in document
    assert "Retard cumulé restant moyen, zéros inclus" in document
    assert "rapport entre le retard moyen avec cette action" in document
    assert "Surcoût réseau" in document
    assert "dont 2 identifiés sur le mouvement" in document
    assert "fetch(" not in document
    assert "http://" not in document
    assert "https://" not in document
    assert "</script><script>alert" not in document
    assert "\\u003c/script\\u003e" in document
    assert (result.output_dir / "assets" / "resultats_mrp_v3.html").is_file()
    copied_map = (result.output_dir / "assets" / "carte_reseau.html").read_text(
        encoding="utf-8"
    )
    assert "https://cdn.plot.ly" not in copied_map
    assert 'src="plotly-2.32.0.min.js"' in copied_map
    assert "Plotly.setPlotConfig({topojsonURL:'./'})" in copied_map
    assert "data:application/json;base64," in copied_map
    assert (result.output_dir / "assets" / "plotly-2.32.0.min.js").is_file()
    assert (result.output_dir / "assets" / "world_110m.json").is_file()
    assert (
        result.output_dir / "data" / "risk_registry_01" / "risk_impact_incidents.csv"
    ).is_file()
    assert (
        result.output_dir
        / "data"
        / "risk_registry_01"
        / "risk_impact_client_service.csv"
    ).is_file()
    assert (
        result.output_dir / "data" / "canonical_cascade_trajectories_compact.json"
    ).is_file()
    copied_long = result.output_dir / "data" / "canonical_cascade_trajectories_long.csv"
    assert (
        copied_long.read_bytes()
        == (trajectory_dir / "canonical_cascade_trajectories_long.csv").read_bytes()
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["no_overwrite"] is True
    assert manifest["artifacts"]["trajectory_long_csv"] == {
        "path": "data/canonical_cascade_trajectories_long.csv",
        "sha256": _digest(copied_long.read_bytes()),
        "row_count": 1,
        "complete_without_scientific_truncation": True,
    }
    assert (
        manifest["scientific_evidence"]["upstream_integrity"][
            "trajectory_long_csv_scientific_truncation"
        ]
        is False
    )
    assert len(manifest["risk_registry_provenance"]) == 2
    assert all(
        proof["verification_status"]
        == "campaign_run_verified_and_paired_to_final_campaign"
        for proof in manifest["risk_registry_provenance"]
    )
    assert all(path.read_bytes() == source_bytes[path] for path in assets)


@pytest.mark.parametrize(
    ("filename", "message"),
    [
        ("canonical_cascade_runs.csv", "runs_csv_sha256"),
        ("canonical_cascade_comparison.csv", "comparison_csv_sha256"),
    ],
)
def test_rejects_a_cascade_table_changed_after_summary_signature(
    tmp_path: Path, filename: str, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    with (cascade_dir / filename).open("ab") as handle:
        handle.write(b"\n")

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_campaign_manifest_changed_after_comparison(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    summary = json.loads(
        (cascade_dir / "canonical_cascade_summary.json").read_text(encoding="utf-8")
    )
    manifest_path = Path(summary["campaign"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at_utc"] = "changed-after-comparison"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest_sha256"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "completed_with_failures", "Campagne non terminée"),
        ("failure_count", 1, "campagne contient des échecs"),
    ],
)
def test_rejects_an_unsuccessful_campaign_even_with_a_resigned_manifest(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    summary = json.loads(
        (cascade_dir / "canonical_cascade_summary.json").read_text(encoding="utf-8")
    )
    manifest_path = Path(summary["campaign"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_summary_manifest_hash(cascade_dir)

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    "filename",
    [
        "canonical_cascade_commands.json",
        "canonical_cascade_config_snapshot.json",
    ],
)
def test_rejects_a_campaign_input_changed_after_manifest_signature(
    tmp_path: Path, filename: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    summary = json.loads(
        (cascade_dir / "canonical_cascade_summary.json").read_text(encoding="utf-8")
    )
    campaign_source = Path(summary["campaign"]["path"])
    with (campaign_source / filename).open("ab") as handle:
        handle.write(b"\n")

    with pytest.raises(ValueError, match="Empreinte"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    "filename",
    [
        "canonical_cascade_trajectories_compact.json",
        "canonical_cascade_trajectories_long.csv",
    ],
)
def test_rejects_a_trajectory_output_changed_after_manifest_signature(
    tmp_path: Path, filename: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    with (trajectory_dir / filename).open("ab") as handle:
        handle.write(b"\n")

    with pytest.raises(ValueError, match="Empreinte"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_an_incomplete_trajectory_export(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    manifest_path = trajectory_dir / "canonical_cascade_trajectories_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "incomplete"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Export de trajectoires non terminé"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_wrong_long_trajectory_row_count(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    manifest_path = trajectory_dir / "canonical_cascade_trajectories_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["long_row_count"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Nombre de lignes incoherent"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_discloses_every_truncated_table_and_points_to_full_csvs(
    tmp_path: Path,
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    filenames = (
        "risk_impact_entities.csv",
        "risk_impact_client_service.csv",
        "risk_impact_costs.csv",
    )
    for filename in filenames:
        path = registries[0] / filename
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            source_row = next(reader)
        _write_csv(path, fieldnames, [source_row] * 120)
    _refresh_registry_quality_contract(cascade_dir)

    result = _build_fixture_demo(
        tmp_path, cascade_dir, trajectory_dir, registries, assets
    )
    document = result.index_path.read_text(encoding="utf-8")

    assert document.count("120 lignes affichées sur 121") == 3
    assert document.count("Le ou les CSV complets sont inclus") == 3
    for filename in filenames:
        assert f"data/risk_registry_XX/{filename}" in document


def test_refuses_to_overwrite_non_empty_output(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    output = tmp_path / "demo"
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refus d'ecraser"):
        build_industrial_demo_pack(
            cascade_dir=cascade_dir,
            trajectory_dir=trajectory_dir,
            risk_registry_dirs=registries,
            output_dir=output,
            industrial_dashboard=assets[0],
            node_dashboard=assets[1],
            network_map=assets[2],
            plotly_js=assets[3],
            plotly_topojson=assets[4],
        )

    assert (output / "keep.txt").read_text(encoding="utf-8") == "user data"


def test_requires_two_cascades(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    runs_path = cascade_dir / "canonical_cascade_runs.csv"
    rows = []
    with runs_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["cascade_id"] == "quality_021081"
        ]
    _write_csv(runs_path, sorted(CASCADE_RUN_FIELDS), rows)

    with pytest.raises(ValueError, match="au moins deux cascades"):
        build_industrial_demo_pack(
            cascade_dir=cascade_dir,
            trajectory_dir=trajectory_dir,
            risk_registry_dirs=registries,
            output_dir=tmp_path / "demo",
            industrial_dashboard=assets[0],
            node_dashboard=assets[1],
            network_map=assets[2],
            plotly_js=assets[3],
            plotly_topojson=assets[4],
        )


def test_rejects_missing_comparison_columns(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    _write_csv(
        cascade_dir / "canonical_cascade_comparison.csv",
        ["cascade_id", "solution_id"],
        [{"cascade_id": "quality_021081", "solution_id": "expedite"}],
    )

    with pytest.raises(ValueError, match="Colonnes manquantes"):
        build_industrial_demo_pack(
            cascade_dir=cascade_dir,
            trajectory_dir=trajectory_dir,
            risk_registry_dirs=registries,
            output_dir=tmp_path / "demo",
            industrial_dashboard=assets[0],
            node_dashboard=assets[1],
            network_map=assets[2],
            plotly_js=assets[3],
            plotly_topojson=assets[4],
        )


def test_rejects_an_incident_without_customer_signal(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    runs_path = cascade_dir / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as handle:
        run_rows = [dict(row) for row in csv.DictReader(handle)]
    untreated = next(
        row
        for row in run_rows
        if row["cascade_id"] == "quality_021081"
        and row["seed"] == "101"
        and row["case_type"] == "incident_no_action"
    )
    untreated["incident_validation_status"] = "physically_applied_no_customer_exposure"
    _write_csv(runs_path, sorted(CASCADE_RUN_FIELDS), run_rows)
    comparison_path = cascade_dir / "canonical_cascade_comparison.csv"
    with comparison_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    rows[0]["incident_signal_detected"] = "false"
    rows[0]["customer_exposure_detected"] = "false"
    rows[0]["customer_exposure_status"] = "absorbed_before_customer"
    rows[0]["ranking_eligible"] = "false"
    rows[0]["days_recovered_vs_no_action"] = ""
    rows[0]["remaining_customer_impact_ratio"] = ""
    rows[0]["recovery_status"] = "untreated_incident_absorbed_before_customer"
    _write_csv(comparison_path, sorted(CASCADE_COMPARISON_FIELDS), rows)
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Effet client non détecté"):
        build_industrial_demo_pack(
            cascade_dir=cascade_dir,
            trajectory_dir=trajectory_dir,
            risk_registry_dirs=registries,
            output_dir=tmp_path / "demo",
            industrial_dashboard=assets[0],
            node_dashboard=assets[1],
            network_map=assets[2],
            plotly_js=assets[3],
            plotly_topojson=assets[4],
        )


def test_reports_absorbed_incident_as_zero_exposure_not_missing_incident(
    tmp_path: Path,
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    config_path = (
        tmp_path / "campaign-source" / "canonical_cascade_config_snapshot.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["scientific_guards"] = {
        "require_positive_incremental_customer_backlog": False
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    runs_path = cascade_dir / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as handle:
        run_rows = [dict(row) for row in csv.DictReader(handle)]
    untreated = next(
        row
        for row in run_rows
        if row["cascade_id"] == "quality_021081"
        and row["seed"] == "101"
        and row["case_type"] == "incident_no_action"
    )
    untreated.update(
        {
            "customer_shortage_days": "0",
            "customer_backlog_qty_days": "0",
            "customer_served_qty": untreated["customer_demand_qty"],
            "incident_validation_status": ("physically_applied_no_customer_exposure"),
        }
    )
    _write_csv(runs_path, sorted(CASCADE_RUN_FIELDS), run_rows)

    comparison_path = cascade_dir / "canonical_cascade_comparison.csv"
    with comparison_path.open("r", encoding="utf-8", newline="") as handle:
        comparison_rows = [dict(row) for row in csv.DictReader(handle)]
    absorbed = next(
        row
        for row in comparison_rows
        if row["cascade_id"] == "quality_021081" and row["seed"] == "101"
    )
    absorbed.update(
        {
            "incident_signal_detected": "false",
            "customer_exposure_detected": "false",
            "customer_exposure_status": "absorbed_before_customer",
            "ranking_eligible": "false",
            "ranking_exclusion_reasons": (
                "untreated incident was physically applied but caused no customer exposure"
            ),
            "days_recovered_vs_no_action": "",
            "recovery_status": "untreated_incident_absorbed_before_customer",
            "no_action_incremental_customer_backlog_qty_days": "0",
            "remaining_incremental_customer_backlog_qty_days": "0",
            "remaining_customer_impact_ratio": "",
        }
    )
    _write_csv(
        comparison_path,
        sorted(CASCADE_COMPARISON_FIELDS),
        comparison_rows,
    )
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    artifacts = build_industrial_demo_pack(
        cascade_dir=cascade_dir,
        trajectory_dir=trajectory_dir,
        risk_registry_dirs=registries,
        output_dir=tmp_path / "demo",
        industrial_dashboard=assets[0],
        node_dashboard=assets[1],
        network_map=assets[2],
        plotly_js=assets[3],
        plotly_topojson=assets[4],
    )

    document = artifacts.index_path.read_text(encoding="utf-8")
    assert "90,0 %" in document
    assert "part des simulations avec retard client" in document
    assert "l’incident est absorbé avant de dégrader le service dans 1 cas" in document
    assert "pas que l’incident a été ignoré" in document


def test_rejects_a_degraded_normal_reference(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    runs_path = cascade_dir / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    normal = next(row for row in rows if row["case_type"] == "normal")
    normal["customer_shortage_days"] = "1"
    normal["customer_backlog_qty_days"] = "25"
    _write_csv(runs_path, sorted(CASCADE_RUN_FIELDS), rows)
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Fonctionnement normal déjà dégradé"):
        build_industrial_demo_pack(
            cascade_dir=cascade_dir,
            trajectory_dir=trajectory_dir,
            risk_registry_dirs=registries,
            output_dir=tmp_path / "demo",
            industrial_dashboard=assets[0],
            node_dashboard=assets[1],
            network_map=assets[2],
            plotly_js=assets[3],
            plotly_topojson=assets[4],
        )


def test_rejects_a_missing_comparison_cascade(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    comparison_path = cascade_dir / "canonical_cascade_comparison.csv"
    with comparison_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            dict(row)
            for row in csv.DictReader(handle)
            if row["cascade_id"] == "quality_021081"
        ]
    _write_csv(comparison_path, sorted(CASCADE_COMPARISON_FIELDS), rows)
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Grille de comparaisons différente"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_missing_solution_trajectory(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    trajectory_path = trajectory_dir / "canonical_cascade_trajectories_compact.json"
    payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
    del payload["cascades"]["delay_338929"]["variants"]["incident_expedite"]
    trajectory_path.write_text(json.dumps(payload), encoding="utf-8")
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Variantes de trajectoires incomplètes"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_an_empty_solution_trajectory(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    trajectory_path = trajectory_dir / "canonical_cascade_trajectories_compact.json"
    payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
    payload["cascades"]["delay_338929"]["variants"]["incident_expedite"]["series"] = []
    trajectory_path.write_text(json.dumps(payload), encoding="utf-8")
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Aucune série"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_registry_edges_without_source_or_target_unit(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    edges_path = registries[0] / "risk_impact_edges.csv"
    with edges_path.open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    rows[0]["target_uom"] = ""
    _write_csv(edges_path, list(rows[0]), rows)
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Unités source/cible absentes"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_accepts_same_metric_on_distinct_parallel_path_stages(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    trajectory_path = trajectory_dir / "canonical_cascade_trajectories_compact.json"
    payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
    series = payload["cascades"]["quality_021081"]["variants"]["normal"]["series"]
    parallel = dict(series[0])
    parallel["path_stage_index"] = int(series[0]["path_stage_index"]) + 1
    series.append(parallel)
    trajectory_path.write_text(json.dumps(payload), encoding="utf-8")
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_duplicate_series_on_the_same_path_stage(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    trajectory_path = trajectory_dir / "canonical_cascade_trajectories_compact.json"
    payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
    series = payload["cascades"]["quality_021081"]["variants"]["normal"]["series"]
    series.append(dict(series[0]))
    trajectory_path.write_text(json.dumps(payload), encoding="utf-8")
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match="Série ambiguë ou dupliquée"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    "filename",
    ["risk_impact_client_service.csv", "risk_impact_costs.csv"],
)
def test_requires_client_and_cost_files_in_every_registry(
    tmp_path: Path, filename: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    (registries[1] / filename).unlink()

    with pytest.raises(FileNotFoundError, match=filename):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    "filename",
    ["risk_impact_client_service.csv", "risk_impact_costs.csv"],
)
def test_rejects_empty_client_and_cost_files(tmp_path: Path, filename: str) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    path = registries[0] / filename
    with path.open("r", encoding="utf-8", newline="") as handle:
        fieldnames = list(csv.DictReader(handle).fieldnames or [])
    _write_csv(path, fieldnames, [])

    with pytest.raises(ValueError, match="Table vide"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_registry_csv_changed_after_its_signature(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    with (registries[0] / "risk_impact_edges.csv").open("ab") as handle:
        handle.write(b"\n")

    with pytest.raises(ValueError, match="Empreinte de registre incoherente"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_wrong_registry_row_count(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    quality_path = registries[0] / "risk_impact_quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["registry_outputs"]["csv_artifacts"]["entities"]["row_count"] += 1
    quality_path.write_text(json.dumps(quality), encoding="utf-8")

    with pytest.raises(ValueError, match="Nombre de lignes de registre incoherent"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "risk-lot-impact-provenance/0", "Version de provenance"),
        (
            "verification_status",
            "standalone_run_sources_hashed",
            "sans campagne source verifiee",
        ),
    ],
)
def test_requires_verified_registry_provenance_contract(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    quality_path = registries[0] / "risk_impact_quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["provenance"][field] = value
    quality_path.write_text(json.dumps(quality), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("identity_field", "value", "message"),
    [
        ("variant_id", "incident_expedite", "doit provenir de incident_no_action"),
        ("seed", 999, "Run de campagne absent ou duplique"),
    ],
)
def test_rejects_registry_identity_not_present_in_final_campaign(
    tmp_path: Path, identity_field: str, value: object, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    quality_path = registries[0] / "risk_impact_quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["provenance"]["identity"][identity_field] = value
    quality_path.write_text(json.dumps(quality), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("provenance_target", "message"),
    [
        ("config", "Empreinte critique incoherente"),
        ("state", "Etat J0 non apparie"),
        ("components", "Composantes de l'etat J0 non appariees"),
    ],
)
def test_rejects_registry_critical_hash_mismatch(
    tmp_path: Path, provenance_target: str, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    quality_path = registries[0] / "risk_impact_quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    provenance = quality["provenance"]
    if provenance_target == "config":
        provenance["critical_hashes"]["campaign_config_snapshot_sha256"] = "f" * 64
    elif provenance_target == "state":
        provenance["critical_hashes"]["measurement_start_state_sha256"] = "f" * 64
    else:
        provenance["parent_run"]["measurement_start_component_sha256"] = {
            "inventory": "f" * 64
        }
    quality_path.write_text(json.dumps(quality), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("run_field", "message"),
    [
        ("graph_sha256", "Graphe du run"),
        ("engine_profile_sha256", "Profil moteur"),
        ("risk_events_sha256", "Risque non apparie"),
    ],
)
def test_rejects_registry_run_hashes_different_from_final_campaign(
    tmp_path: Path, run_field: str, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    runs_path = cascade_dir / "canonical_cascade_runs.csv"
    with runs_path.open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    target = next(
        row
        for row in rows
        if row["cascade_id"] == "quality_021081"
        and row["variant_id"] == "incident_no_action"
        and row["seed"] == "101"
    )
    target[run_field] = "f" * 64
    _write_csv(runs_path, sorted(CASCADE_RUN_FIELDS), rows)
    _refresh_fixture_integrity(cascade_dir, trajectory_dir)

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_an_unrelated_native_registry(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    incident_path = registries[0] / "risk_impact_incidents.csv"
    with incident_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    rows[0]["incident_id"] = "UNRELATED-NATIVE"
    _write_csv(incident_path, list(rows[0]), rows)
    _refresh_registry_quality_contract(cascade_dir)

    with pytest.raises(ValueError, match="Incident de registre hors périmètre"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_native_incident_with_the_wrong_scope(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    incident_path = registries[0] / "risk_impact_incidents.csv"
    with incident_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    rows[0]["item_id"] = "item:999999"
    _write_csv(incident_path, list(rows[0]), rows)
    _refresh_registry_quality_contract(cascade_dir)

    with pytest.raises(ValueError, match="Périmètre de risque incohérent"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("relation", "message"),
    [
        ("finished", "Aucune relation native vers le produit fini"),
        ("customer", "Aucune relation native vers le client"),
        ("cost", "Aucune relation native vers les coûts"),
    ],
)
def test_requires_native_finished_customer_and_cost_relations(
    tmp_path: Path, relation: str, message: str
) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    if relation == "finished":
        path = registries[0] / "risk_impact_entities.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
        rows[0]["item_id"] = "item:999999"
    elif relation == "customer":
        path = registries[0] / "risk_impact_client_service.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
        rows[0]["client_node_id"] = "C-OTHER"
    else:
        path = registries[0] / "risk_impact_costs.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
        rows[0]["exposure_bundle_id"] = "BUNDLE-OTHER"
    _write_csv(path, list(rows[0]), rows)
    _refresh_registry_quality_contract(cascade_dir)

    with pytest.raises(ValueError, match=message):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_an_empty_plotly_distribution(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    assets[3].write_bytes(b"")

    with pytest.raises(ValueError, match="Distribution Plotly de taille inattendue"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_a_plotly_distribution_with_the_wrong_hash(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    corrupted = bytearray(assets[3].read_bytes())
    corrupted[-1] = ord("y")
    assets[3].write_bytes(corrupted)

    with pytest.raises(ValueError, match="Empreinte Plotly 2.32.0 non officielle"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


def test_rejects_an_invalid_world_topojson(tmp_path: Path) -> None:
    cascade_dir, trajectory_dir, registries, assets = _fixture(tmp_path)
    assets[4].write_bytes(b"{}")

    with pytest.raises(ValueError, match="Fond géographique Plotly incomplet"):
        _build_fixture_demo(tmp_path, cascade_dir, trajectory_dir, registries, assets)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("native", False),
        ("native_engine", False),
        ("native_graph", False),
        ("native_simplified", True),
        ("mixed", True),
        ("approximation", True),
    ],
)
def test_classifies_native_and_approximated_levers(value: str, expected: bool) -> None:
    assert _is_approximated_fidelity(value) is expected


def test_computes_the_business_ratio_from_the_two_backlog_means() -> None:
    metrics = {
        "no_action_incremental_customer_backlog_qty_days": {"mean": 200.0},
        "remaining_incremental_customer_backlog_qty_days": {"mean": 50.0},
    }

    assert demo_module._remaining_backlog_ratio_of_means(metrics) == 0.25
    metrics["no_action_incremental_customer_backlog_qty_days"]["mean"] = 0.0
    assert demo_module._remaining_backlog_ratio_of_means(metrics) is None


def test_entity_preview_is_balanced_across_business_stages() -> None:
    rows: list[dict[str, str]] = []
    for index in range(200):
        rows.append(
            {
                "_registry_source": "quality",
                "entity_type": "supplier_source_lot",
                "entity_id": f"SOURCE-{index:03d}",
                "day": str(index),
            }
        )
    for entity_type in (
        "physical_lot",
        "production_campaign",
        "finished_product_lot",
        "customer_receipt_lot",
    ):
        for index in range(3):
            rows.append(
                {
                    "_registry_source": "quality",
                    "entity_type": entity_type,
                    "entity_id": f"{entity_type}-{index}",
                    "day": str(index),
                }
            )

    preview = demo_module._business_entity_preview(rows, limit=15)
    types = [row["entity_type"] for row in preview]

    assert len(preview) == 15
    assert set(types) == {
        "physical_lot",
        "production_campaign",
        "finished_product_lot",
        "customer_receipt_lot",
        "supplier_source_lot",
    }
    assert types.count("supplier_source_lot") == 3


def test_pairs_full_trace_and_compact_states_by_identical_physical_core() -> None:
    trace_components = {
        "stock": _digest("stock"),
        "pipeline": _digest("pipeline"),
        "lot_ledger": _digest("full-lot-ledger"),
        "lot_arrivals_pipeline": _digest("full-lot-arrivals"),
    }
    final_components = {
        **trace_components,
        "lot_ledger": _digest("compact-lot-ledger"),
        "lot_arrivals_pipeline": _digest("compact-lot-arrivals"),
    }
    trace_row = {
        "status": "ok",
        "customer_backlog_qty_days": "125",
        "result_dir": "full",
        "measurement_start_state_sha256": _digest("full-state"),
        "measurement_start_component_sha256_json": json.dumps(trace_components),
    }
    final_row = {
        **trace_row,
        "result_dir": "compact",
        "measurement_start_state_sha256": _digest("compact-state"),
        "measurement_start_component_sha256_json": json.dumps(final_components),
    }

    pairing = demo_module._validate_measurement_start_pairing(
        registry_source="registre_test",
        provenance_state_hash=_digest("full-state"),
        trace_state_hash=_digest("full-state"),
        final_state_hash=_digest("compact-state"),
        provenance_components=trace_components,
        trace_components=trace_components,
        final_components=final_components,
        trace_artifact_profile="full",
        final_artifact_profile="compact",
        trace_row=trace_row,
        final_row=final_row,
    )

    assert pairing["mode"] == "same_physical_core_across_full_and_compact_profiles"
    assert pairing["core_component_sha256"] == {
        "stock": _digest("stock"),
        "pipeline": _digest("pipeline"),
    }
    assert set(pairing["profile_dependent_components"]) == {
        "lot_ledger",
        "lot_arrivals_pipeline",
    }


def test_rejects_a_physical_core_difference_between_trace_and_compact() -> None:
    trace_components = {
        "stock": _digest("stock"),
        "lot_ledger": _digest("full-lot-ledger"),
    }
    final_components = {
        "stock": _digest("different-stock"),
        "lot_ledger": _digest("compact-lot-ledger"),
    }

    with pytest.raises(ValueError, match="Composantes de l'etat J0 non appariees"):
        demo_module._validate_measurement_start_pairing(
            registry_source="registre_test",
            provenance_state_hash=_digest("full-state"),
            trace_state_hash=_digest("full-state"),
            final_state_hash=_digest("compact-state"),
            provenance_components=trace_components,
            trace_components=trace_components,
            final_components=final_components,
            trace_artifact_profile="full",
            final_artifact_profile="compact",
            trace_row={"status": "ok"},
            final_row={"status": "ok"},
        )
