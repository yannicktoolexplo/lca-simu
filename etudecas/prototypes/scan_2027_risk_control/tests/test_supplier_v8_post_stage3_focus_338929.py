from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_post_stage3_focus_338929 as focus,
)


def _minimal_plan(root: Path) -> dict:
    closure = root / "closure.json"
    closure.write_text("{}", encoding="utf-8")
    unsigned = {
        "schema_version": focus.PLAN_SCHEMA,
        "selection_basis": focus.SELECTION_BASIS,
        "supplier_id": focus.DEFAULT_SUPPLIER,
        "item_id": focus.DEFAULT_ITEM,
        "output_root": str(root.resolve()),
        "stage3_supervision": str((root / "stage3").resolve()),
        "stage3_status_signature": "stage3-signature",
        "closure_report": str(closure.resolve()),
        "closure_report_sha256": focus.common.sha256_file(closure),
        "lot_validator_path": str(Path(focus.lot_v4.__file__).resolve()),
        "lot_validator_sha256": focus.common.sha256_file(Path(focus.lot_v4.__file__)),
        "scientific_contract": {
            "priority_claimed": False,
            "quality_included": False,
            "state_dependent_risks_enabled": False,
            "capacity_or_availability_modified": False,
            "common_random_numbers": True,
            "seed_selection_uses_outcomes": False,
            "maximum_engine_runs": 0,
        },
        "common_seed": 20,
        "dossiers": [
            {
                "mode": "reuse_stage3",
                "selection_basis": focus.SELECTION_BASIS,
                "source_priority_status": "dossier_to_investigate",
                "dossier": {
                    "dossier_id": f"focus_{mechanism}",
                    "seed": 20,
                    "priority": {
                        "operating_point_id": focus.DEFAULT_POINT,
                        "mechanism": mechanism,
                        "lane_id": focus.DEFAULT_LANE,
                        "supplier_id": focus.DEFAULT_SUPPLIER,
                        "item_id": focus.DEFAULT_ITEM,
                        "dst_node_id": focus.DEFAULT_DESTINATION,
                        "edge_id": focus.DEFAULT_EDGE,
                        "target_product_id": focus.DEFAULT_PRODUCT,
                    },
                },
            }
            for mechanism in focus.MECHANISMS
        ],
    }
    for row in unsigned["dossiers"]:
        row["stage3_dossier_sha256"] = focus.common.stable_sha256(row["dossier"])
    return focus._signed(unsigned, "plan_signature")


def test_default_matrix_is_op93_two_separate_mechanisms() -> None:
    assert focus._matrix(None) == [
        {
            "operating_point_id": "op_93",
            "mechanism": "transport_delay",
            "supplier_id": focus.DEFAULT_SUPPLIER,
            "item_id": focus.DEFAULT_ITEM,
            "dst_node_id": focus.DEFAULT_DESTINATION,
            "edge_id": focus.DEFAULT_EDGE,
            "lane_id": focus.DEFAULT_LANE,
            "target_product_id": focus.DEFAULT_PRODUCT,
        },
        {
            "operating_point_id": "op_93",
            "mechanism": "planned_delivery_shortfall",
            "supplier_id": focus.DEFAULT_SUPPLIER,
            "item_id": focus.DEFAULT_ITEM,
            "dst_node_id": focus.DEFAULT_DESTINATION,
            "edge_id": focus.DEFAULT_EDGE,
            "lane_id": focus.DEFAULT_LANE,
            "target_product_id": focus.DEFAULT_PRODUCT,
        },
    ]


def test_explicit_matrix_is_always_rejected(tmp_path: Path) -> None:
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "operating_point_id": "op_93",
                        "mechanism": "transport_delay",
                        "supplier_id": "OTHER",
                        "priority_status": "robust_priority",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(focus.FocusError, match="fixe"):
        focus._matrix(path)


def test_common_seed_is_independent_of_impact_outcomes() -> None:
    rows = []
    for mechanism in focus.MECHANISMS:
        for seed, exposure in ((10, 10.0), (20, 20.0), (30, 30.0)):
            row = {
                "stage": "incident",
                "operating_point_id": focus.DEFAULT_POINT,
                "mechanism": mechanism,
                "lane_id": focus.DEFAULT_LANE,
                "supplier_id": focus.DEFAULT_SUPPLIER,
                "item_id": focus.DEFAULT_ITEM,
                "dst_node_id": focus.DEFAULT_DESTINATION,
                "edge_id": focus.DEFAULT_EDGE,
                "target_product_id": focus.DEFAULT_PRODUCT,
                "status": "valid",
                "valid": True,
                "incident_physically_exercised": True,
                "risk_applied_row_count": 1,
                "risk_applied_event_count": 1,
                "target_planned_qty": 4,
                "target_shipped_qty": 3,
                "incident_effective_dose_qty": 2,
                "incident_effective_dose_qty_days": 200,
                "baseline_lane_shipped_qty_state_window": exposure,
                "seed": seed,
                "impact_service_loss_fed_product_pp": -seed,
            }
            rows.append(row)
    before = focus.select_common_seed(rows)
    for index, row in enumerate(rows):
        row["impact_service_loss_fed_product_pp"] = 100000 - index
    assert before == 20
    assert focus.select_common_seed(rows) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lane_id", "wrong_lane"),
        ("status", "invalid"),
        ("incident_physically_exercised", False),
        ("target_planned_qty", 0),
        ("target_shipped_qty", 0),
        ("risk_applied_row_count", 0),
        ("risk_applied_event_count", 0),
        ("baseline_lane_shipped_qty_state_window", 0),
    ],
)
def test_seed_selection_rejects_wrong_identity_or_exposure(
    field: str, value: object
) -> None:
    rows = []
    for mechanism in focus.MECHANISMS:
        row = {
            "stage": "incident",
            "operating_point_id": focus.DEFAULT_POINT,
            "mechanism": mechanism,
            "lane_id": focus.DEFAULT_LANE,
            "supplier_id": focus.DEFAULT_SUPPLIER,
            "item_id": focus.DEFAULT_ITEM,
            "dst_node_id": focus.DEFAULT_DESTINATION,
            "edge_id": focus.DEFAULT_EDGE,
            "target_product_id": focus.DEFAULT_PRODUCT,
            "status": "valid",
            "valid": True,
            "incident_physically_exercised": True,
            "risk_applied_row_count": 1,
            "risk_applied_event_count": 1,
            "target_planned_qty": 4,
            "target_shipped_qty": 3,
            "incident_effective_dose_qty": 2,
            "incident_effective_dose_qty_days": 200,
            "baseline_lane_shipped_qty_state_window": 20,
            "seed": 20,
        }
        row[field] = value
        rows.append(row)
    with pytest.raises(focus.FocusError, match="graine commune"):
        focus.select_common_seed(rows)


def test_load_plan_binds_validator_hash_and_selection_basis(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        focus,
        "_closure_context",
        lambda *_: SimpleNamespace(
            status={"status_signature": "stage3-signature"},
            contract={},
            paths=SimpleNamespace(
                campaign_root=tmp_path / "campaign",
                results_dir=tmp_path / "results",
            ),
        ),
    )
    monkeypatch.setattr(focus.lot_v4, "_verify_campaign_manifest", lambda _path: {})
    monkeypatch.setattr(
        focus.lot_v4,
        "_validate_campaign_results",
        lambda **_kwargs: ({}, tmp_path / "priority.csv", []),
    )
    monkeypatch.setattr(focus.lot_v4, "_load_metric_rows", lambda _paths: [])
    monkeypatch.setattr(focus, "select_common_seed", lambda _rows: 20)
    plan = _minimal_plan(tmp_path)
    monkeypatch.setattr(
        focus,
        "_stage3_dossiers",
        lambda _context: {
            (
                row["dossier"]["priority"]["operating_point_id"],
                row["dossier"]["priority"]["mechanism"],
                row["dossier"]["priority"]["lane_id"],
            ): row["dossier"]
            for row in plan["dossiers"]
        },
    )
    (tmp_path / "focus_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    assert focus.load_plan(tmp_path)["plan_signature"] == plan["plan_signature"]
    plan["common_seed"] = 30
    for row in plan["dossiers"]:
        row["dossier"]["seed"] = 30
        row["stage3_dossier_sha256"] = focus.common.stable_sha256(row["dossier"])
    plan = focus._signed(
        {key: value for key, value in plan.items() if key != "plan_signature"},
        "plan_signature",
    )
    (tmp_path / "focus_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(focus.FocusError, match="redérivée"):
        focus.load_plan(tmp_path)
    plan["common_seed"] = 20
    for row in plan["dossiers"]:
        row["dossier"]["seed"] = 20
        row["stage3_dossier_sha256"] = focus.common.stable_sha256(row["dossier"])
    plan = focus._signed(
        {key: value for key, value in plan.items() if key != "plan_signature"},
        "plan_signature",
    )
    plan["selection_basis"] = "priority"
    (tmp_path / "focus_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(focus.FocusError, match="Plan focus invalide"):
        focus.load_plan(tmp_path)


def test_load_plan_new_focus_rederives_physical_common_seed_without_service_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "focus"
    root.mkdir()
    campaign = tmp_path / "campaign"
    results = tmp_path / "results"
    campaign.mkdir()
    results.mkdir()
    manifest_path = campaign / "campaign_manifest.json"
    metric_path = results / "metrics.csv"
    closure_path = tmp_path / "closure.json"
    engine = tmp_path / "engine.py"
    profile = tmp_path / "profile.json"
    graph = tmp_path / "graph.json"
    evidence = tmp_path / "evidence.json"
    for path in (manifest_path, metric_path, closure_path, profile, graph, evidence):
        path.write_text("{}", encoding="utf-8")
    engine.write_text("# synthetic fixture only\n", encoding="utf-8")

    incidents: list[dict] = []
    baselines: dict[str, dict] = {}
    for mechanism in focus.MECHANISMS:
        for seed, exposure in ((10, 10.0), (20, 20.0), (30, 30.0)):
            incidents.append(
                {
                    "stage": "incident",
                    "case_key": f"{mechanism}-{seed}",
                    "case_signature": f"signature-{mechanism}-{seed}",
                    "operating_point_id": focus.DEFAULT_POINT,
                    "mechanism": mechanism,
                    "lane_id": focus.DEFAULT_LANE,
                    "supplier_id": focus.DEFAULT_SUPPLIER,
                    "item_id": focus.DEFAULT_ITEM,
                    "dst_node_id": focus.DEFAULT_DESTINATION,
                    "edge_id": focus.DEFAULT_EDGE,
                    "target_product_id": focus.DEFAULT_PRODUCT,
                    "status": "valid",
                    "valid": True,
                    "incident_physically_exercised": True,
                    "risk_applied_row_count": 1,
                    "risk_applied_event_count": 1,
                    "target_planned_qty": 4,
                    "target_shipped_qty": 3,
                    "incident_effective_dose_qty": 2,
                    "incident_effective_dose_qty_days": 200,
                    "baseline_lane_shipped_qty_state_window": exposure,
                    "required_simulation_days": 365,
                    "warmup_core_state_sha256": "warmup",
                    "seed": seed,
                    "impact_service_loss_fed_product_pp": seed * 1000,
                }
            )
        selected = incidents[-2]
        baselines[mechanism] = {
            **selected,
            "stage": "reference",
            "case_key": f"baseline-{mechanism}-20",
            "case_signature": f"baseline-signature-{mechanism}-20",
        }
    metric_rows = [*incidents, *baselines.values()]

    context = SimpleNamespace(
        status={"status_signature": "stage3-status"},
        contract={"contract_signature": "stage3-contract"},
        paths=SimpleNamespace(campaign_root=campaign, results_dir=results),
    )
    monkeypatch.setattr(focus, "_closure_context", lambda *_args: context)
    monkeypatch.setattr(focus, "_stage3_dossiers", lambda _context: {})
    monkeypatch.setattr(focus.lot_v4, "_verify_campaign_manifest", lambda _path: {})
    monkeypatch.setattr(
        focus.lot_v4,
        "_validate_campaign_results",
        lambda **_kwargs: ({}, results / "priority.csv", [metric_path]),
    )
    monkeypatch.setattr(focus.lot_v4, "_load_metric_rows", lambda _paths: metric_rows)
    monkeypatch.setattr(
        focus.lot_v4,
        "_baseline_for",
        lambda _rows, incident: baselines[str(incident["mechanism"])],
    )
    monkeypatch.setattr(focus.lot_v4, "_validate_case_evidence", lambda *_a, **_k: None)
    risk_row = {"event": "synthetic"}
    monkeypatch.setattr(focus.lot_v4, "_risk_row_contract", lambda *_a, **_k: risk_row)
    monkeypatch.setattr(focus.lot_v4, "_read_csv", lambda _path: [risk_row])

    dossiers = []
    for mechanism in focus.MECHANISMS:
        incident = next(
            row
            for row in incidents
            if row["mechanism"] == mechanism and row["seed"] == 20
        )
        risk = root / "inputs" / mechanism / "supplier_risk_events.csv"
        risk.parent.mkdir(parents=True)
        risk.write_text("event\nsynthetic\n", encoding="utf-8")
        source_files = {
            "engine": {"path": str(engine), "sha256": focus.common.sha256_file(engine)},
            "profile": {
                "path": str(profile),
                "sha256": focus.common.sha256_file(profile),
            },
            "graph": {"path": str(graph), "sha256": focus.common.sha256_file(graph)},
            "supplier_floors": {"path": "", "sha256": ""},
            "factory_capacities": {"path": "", "sha256": ""},
        }
        priority = {
            "supplier_id": focus.DEFAULT_SUPPLIER,
            "item_id": focus.DEFAULT_ITEM,
            "dst_node_id": focus.DEFAULT_DESTINATION,
            "edge_id": focus.DEFAULT_EDGE,
            "lane_id": focus.DEFAULT_LANE,
            "target_product_id": focus.DEFAULT_PRODUCT,
            "operating_point_id": focus.DEFAULT_POINT,
            "mechanism": mechanism,
        }
        arms = {}
        for arm in ("baseline", "incident"):
            run_dir = root / "runs" / mechanism / arm
            command = focus.lot_v4._build_command(  # noqa: SLF001
                python_executable=focus.sys.executable,
                engine=engine,
                graph=graph,
                output_dir=run_dir,
                horizon=365,
                seed=20,
                supplier_floors=None,
                factory_capacities=None,
                profile_args=[],
                managed_args=[],
                risk_csv=risk if arm == "incident" else None,
            )
            arms[arm] = {
                "run_dir": str(run_dir),
                "command": command,
                "command_sha256": focus.common.stable_sha256(command),
            }
        provenance = {
            "incident_metric": incident,
            "baseline_metric": baselines[mechanism],
            "incident_evidence": {
                "path": str(evidence),
                "sha256": focus.common.sha256_file(evidence),
            },
            "baseline_evidence": {
                "path": str(evidence),
                "sha256": focus.common.sha256_file(evidence),
            },
            "metric_sources": [
                {
                    "path": str(metric_path.resolve()),
                    "sha256": focus.common.sha256_file(metric_path),
                }
            ],
            "campaign_manifest": {
                "path": str(manifest_path.resolve()),
                "sha256": focus.common.sha256_file(manifest_path),
            },
            "stage3_contract_signature": "stage3-contract",
            "stage3_status_signature": "stage3-status",
        }
        dossier = {
            "dossier_id": f"focus-{mechanism}",
            "selection_basis": focus.SELECTION_BASIS,
            "priority": priority,
            "risk_row": risk_row,
            "risk_csv": str(risk),
            "risk_csv_sha256": focus.common.sha256_file(risk),
            "source_files": source_files,
            "source_provenance": provenance,
            "command_contract": {"profile_args": [], "managed_args": []},
            "horizon_days": 365,
            "seed": 20,
            "warmup_core_state_sha256": "warmup",
            "arms": arms,
        }
        dossiers.append(
            {
                "mode": "new_focus",
                "selection_basis": focus.SELECTION_BASIS,
                "source_priority_status": None,
                "dossier": dossier,
            }
        )

    unsigned = {
        "schema_version": focus.PLAN_SCHEMA,
        "selection_basis": focus.SELECTION_BASIS,
        "supplier_id": focus.DEFAULT_SUPPLIER,
        "item_id": focus.DEFAULT_ITEM,
        "output_root": str(root.resolve()),
        "stage3_supervision": str((tmp_path / "stage3").resolve()),
        "stage3_status_signature": "stage3-status",
        "closure_report": str(closure_path.resolve()),
        "closure_report_sha256": focus.common.sha256_file(closure_path),
        "lot_validator_path": str(Path(focus.lot_v4.__file__).resolve()),
        "lot_validator_sha256": focus.common.sha256_file(Path(focus.lot_v4.__file__)),
        "scientific_contract": {
            "priority_claimed": False,
            "quality_included": False,
            "state_dependent_risks_enabled": False,
            "capacity_or_availability_modified": False,
            "common_random_numbers": True,
            "seed_selection_uses_outcomes": False,
            "maximum_engine_runs": 4,
        },
        "common_seed": 20,
        "dossiers": dossiers,
    }

    def publish() -> None:
        signed = focus._signed(unsigned, "plan_signature")
        (root / "focus_plan.json").write_text(json.dumps(signed), encoding="utf-8")

    publish()
    assert focus.load_plan(root)["common_seed"] == 20
    for row in metric_rows:
        row["impact_service_loss_fed_product_pp"] = -999999
    publish()
    assert focus.load_plan(root)["common_seed"] == 20

    selected_incident = dossiers[0]["dossier"]["source_provenance"]["incident_metric"]
    selected_incident["risk_applied_event_count"] = 0
    publish()
    with pytest.raises(focus.FocusError, match="(?i:graine commune|physique complet)"):
        focus.load_plan(root)


def test_run_without_execute_never_starts_engine(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        focus,
        "_closure_context",
        lambda *_: SimpleNamespace(status={"status_signature": "stage3-signature"}),
    )
    plan = _minimal_plan(tmp_path)
    plan["dossiers"] = [
        {
            "mode": "new_focus",
            "selection_basis": focus.SELECTION_BASIS,
            "source_priority_status": None,
            "dossier": {
                "dossier_id": "focus",
                "arms": {
                    "baseline": {"command": ["forbidden"]},
                    "incident": {"command": ["forbidden"]},
                },
            },
        }
    ]
    plan = focus._signed(
        {key: value for key, value in plan.items() if key != "plan_signature"},
        "plan_signature",
    )
    monkeypatch.setattr(focus, "load_plan", lambda _root: plan)
    monkeypatch.setattr(
        focus.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("engine must not run"),
    )
    result = focus.run(tmp_path, execute=False)
    assert result["status"] == "validated_not_executed"
    assert result["planned_engine_runs"] == 2


def test_path_confinement_rejects_root_and_escape(tmp_path: Path) -> None:
    with pytest.raises(focus.FocusError, match="hors"):
        focus._inside(tmp_path, tmp_path, "run")
    with pytest.raises(focus.FocusError, match="hors"):
        focus._inside(tmp_path, tmp_path.parent / "escape", "run")
    assert focus._inside(tmp_path, tmp_path / "runs" / "x", "run").is_relative_to(
        tmp_path.resolve()
    )


def test_cli_has_explicit_execute_opt_in() -> None:
    args = focus._parser().parse_args(["run", "--root", "x"])
    assert args.execute is False
    args = focus._parser().parse_args(["run", "--root", "x", "--execute"])
    assert args.execute is True


def test_zero_run_still_publishes_strict_receipt(tmp_path: Path, monkeypatch) -> None:
    plan = _minimal_plan(tmp_path)
    monkeypatch.setattr(focus.lot_v4, "_validate_pair", lambda _dossier: {})
    receipt = focus._execute_locked(tmp_path, plan, [])
    assert receipt["planned_arm_count"] == 0
    assert receipt["executed_arm_count"] == 0
    assert receipt["preexisting_validated_arm_count"] == 0
    assert (tmp_path / "focus_run_receipt.json").is_file()


def test_stale_zero_run_receipt_is_rejected(tmp_path: Path, monkeypatch) -> None:
    plan = _minimal_plan(tmp_path)
    monkeypatch.setattr(focus.lot_v4, "_validate_pair", lambda _dossier: {})
    receipt = focus._execute_locked(tmp_path, plan, [])
    unsigned = {
        key: value for key, value in receipt.items() if key != "receipt_signature"
    }
    unsigned["planned_arm_count"] = 2
    stale = focus._signed(unsigned, "receipt_signature")
    (tmp_path / "focus_run_receipt.json").write_text(
        json.dumps(stale), encoding="utf-8"
    )
    with pytest.raises(focus.FocusError, match="administrativement"):
        focus._execute_locked(tmp_path, plan, [])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("planned_arm_count", -1),
        ("executed_arm_count", 1),
        ("preexisting_validated_arm_count", 1),
        ("schema_version", "wrong"),
        ("partial_policy", "overwrite_partial"),
    ],
)
def test_receipt_rejects_bad_counters_schema_and_policy(
    tmp_path: Path, monkeypatch, field: str, value: object
) -> None:
    plan = _minimal_plan(tmp_path)
    monkeypatch.setattr(focus.lot_v4, "_validate_pair", lambda _dossier: {})
    receipt = focus._execute_locked(tmp_path, plan, [])
    unsigned = {
        key: item for key, item in receipt.items() if key != "receipt_signature"
    }
    unsigned[field] = value
    bad = focus._signed(unsigned, "receipt_signature")
    with pytest.raises(focus.FocusError):
        focus._validate_receipt(plan, bad)


def test_contract_contains_lock_transaction_and_exact_command_guards() -> None:
    source = Path(focus.__file__).read_text(encoding="utf-8")
    assert "2 * new_count not in {0, 2, 4}" in source
    assert '".focus_338929.lock"' in source
    assert "staging.replace(output_root)" in source
    assert "Commande non liée exactement" in source
    assert "Trace ou niveau de complétude falsifié" in source
    load_source = source.split("def load_plan", 1)[1].split("def run", 1)[0]
    assert "if not _is_focus_incident(incident_metric, mechanism):" in load_source
    assert "risk_applied_row_count" not in load_source
    assert "risk_applied_event_count" not in load_source


def test_finalize_never_publishes_from_bad_receipt(tmp_path: Path, monkeypatch) -> None:
    plan = _minimal_plan(tmp_path)
    monkeypatch.setattr(focus, "load_plan", lambda _root: plan)
    bad = focus._signed(
        {
            "schema_version": "wrong",
            "status": "complete_validated",
            "plan_signature": plan["plan_signature"],
            "planned_arm_count": 0,
            "executed_arm_count": 0,
            "preexisting_validated_arm_count": 0,
            "partial_policy": "wrong",
            "arms": [],
        },
        "receipt_signature",
    )
    (tmp_path / "focus_run_receipt.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(focus.FocusError):
        focus._finalize_locked(tmp_path)
    assert not (tmp_path / "focus_validation.json").exists()
