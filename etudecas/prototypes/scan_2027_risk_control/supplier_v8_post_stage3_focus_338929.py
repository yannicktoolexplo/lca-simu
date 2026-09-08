#!/usr/bin/env python3
"""Plan and validate an additive post-Stage3 lot focus for supplier 338929.

This is a user-requested diagnostic focus, never a supplier-priority result.
Execution is impossible unless ``run --execute`` is stated explicitly.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lot_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    verify_supplier_v8_stage3_closure as closure_v1,
)

SCHEMA_VERSION = "etudecas.supplier_v8_post_stage3_focus_338929.v1"
PLAN_SCHEMA = f"{SCHEMA_VERSION}.plan.v1"
RECEIPT_SCHEMA = f"{SCHEMA_VERSION}.receipt.v1"
VALIDATION_SCHEMA = f"{SCHEMA_VERSION}.validation.v1"
SELECTION_BASIS = "user_requested_focus_not_priority_signal"
DEFAULT_SUPPLIER = "SDC-VD0914360C"
DEFAULT_ITEM = "item:338929"
DEFAULT_DESTINATION = "M-1810"
DEFAULT_EDGE = "edge:SDC-VD0914360C_TO_M-1810_338929"
DEFAULT_LANE = "sdc_vd0914360c_338929_m_1810"
DEFAULT_PRODUCT = "268091"
DEFAULT_POINT = "op_93"
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")


class FocusError(RuntimeError):
    """Raised when the focus contract cannot be proven."""


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise FocusError(f"Objet JSON attendu: {path}")
    return value


def _signed(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**payload, field: common.stable_sha256(payload)}


def _verify(payload: Mapping[str, Any], field: str, label: str) -> None:
    try:
        common.verify_signature(payload, field, label)
    except Exception as exc:
        raise FocusError(str(exc)) from exc


def _inside(root: Path, candidate: Path, label: str) -> Path:
    root, candidate = root.resolve(), candidate.resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise FocusError(f"Chemin {label} hors de la racine dédiée")
    return candidate


def _closure_context(stage3: Path, closure_report: Path) -> Any:
    try:
        context = closure_v1.load_final_context(stage3)
    except Exception as exc:
        raise FocusError(f"Stage3 final signé requis: {exc}") from exc
    report = _read(closure_report.resolve())
    signature = str(report.get("closure_signature") or "")
    unsigned = {
        key: value for key, value in report.items() if key != "closure_signature"
    }
    if signature != closure_v1._stable_sha256(unsigned):  # noqa: SLF001
        raise FocusError("Signature du rapport de clôture invalide")
    rebuilt = closure_v1.build_closure_report(context)
    if report != rebuilt:
        raise FocusError("Rapport de clôture incomplet ou non conforme aux artefacts")
    technical = report.get("technical_verdict") or {}
    if (
        technical.get("code") != "CONFORME_TECHNIQUE"
        or technical.get("conforme") is not True
    ):
        raise FocusError("Clôture techniquement conforme requise")
    source = report.get("source") or {}
    if (
        Path(str(source.get("supervision_dir") or "")).resolve() != stage3.resolve()
        or source.get("contract_signature")
        != context.contract.get("contract_signature")
        or source.get("status_signature") != context.status.get("status_signature")
    ):
        raise FocusError("Rapport de clôture non lié au Stage3 demandé")
    return context


def _matrix(path: Path | None = None) -> list[dict[str, str]]:
    if path is not None:
        raise FocusError("La matrice du focus 338929 est fixe et non configurable")
    return [
        {
            "operating_point_id": DEFAULT_POINT,
            "mechanism": mechanism,
            "supplier_id": DEFAULT_SUPPLIER,
            "item_id": DEFAULT_ITEM,
            "dst_node_id": DEFAULT_DESTINATION,
            "edge_id": DEFAULT_EDGE,
            "lane_id": DEFAULT_LANE,
            "target_product_id": DEFAULT_PRODUCT,
        }
        for mechanism in MECHANISMS
    ]


def _is_focus_incident(row: Mapping[str, Any], mechanism: str) -> bool:
    dose = (
        row.get("incident_effective_dose_qty_days")
        if mechanism == "transport_delay"
        else row.get("incident_effective_dose_qty")
    )
    return bool(
        mechanism in MECHANISMS
        and str(row.get("stage") or "") == "incident"
        and str(row.get("operating_point_id") or "") == DEFAULT_POINT
        and str(row.get("mechanism") or "") == mechanism
        and str(row.get("lane_id") or "") == DEFAULT_LANE
        and str(row.get("supplier_id") or "") == DEFAULT_SUPPLIER
        and str(row.get("item_id") or "") == DEFAULT_ITEM
        and str(row.get("dst_node_id") or "") == DEFAULT_DESTINATION
        and str(row.get("edge_id") or "") == DEFAULT_EDGE
        and str(row.get("target_product_id") or "") == DEFAULT_PRODUCT
        and str(row.get("status") or "") == "valid"
        and lot_v4._truthy(row.get("valid"))  # noqa: SLF001
        and lot_v4._truthy(row.get("incident_physically_exercised"))  # noqa: SLF001
        and int(float(row.get("risk_applied_row_count") or 0)) >= 1
        and int(float(row.get("risk_applied_event_count") or 0)) >= 1
        and float(row.get("target_planned_qty") or 0) > 0
        and float(row.get("target_shipped_qty") or 0) > 0
        and float(row.get("baseline_lane_shipped_qty_state_window") or 0) > 0
        and float(dose or 0) > 0
    )


def select_common_seed(rows: Sequence[Mapping[str, Any]]) -> int:
    """Choose the physical-exposure median; never inspect an impact outcome."""
    by_mechanism: dict[str, dict[int, float]] = {}
    for mechanism in MECHANISMS:
        candidates: dict[int, float] = {}
        for row in rows:
            if not _is_focus_incident(row, mechanism):
                continue
            seed = int(row["seed"])
            exposure = float(row.get("baseline_lane_shipped_qty_state_window") or 0)
            if exposure > 0:
                candidates[seed] = exposure
        by_mechanism[mechanism] = candidates
    common_seeds = set.intersection(*(set(values) for values in by_mechanism.values()))
    if not common_seeds:
        raise FocusError("Aucune graine commune physiquement exercée")
    ranked = sorted(
        (min(by_mechanism[m][seed] for m in MECHANISMS), seed) for seed in common_seeds
    )
    return ranked[(len(ranked) - 1) // 2][1]


def _stage3_dossiers(context: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    root = context.paths.lot_replay_root.resolve()
    if not (root / "replay_plan.json").is_file():
        return {}
    plan = lot_v4.load_and_validate_plan(root)
    receipt = _read(root / "replay_run_receipt.json")
    _verify(receipt, "run_receipt_signature", "reçu lots Stage3")
    validation = _read(root / "finalized" / "replay_validation.json")
    _verify(validation, "validation_signature", "validation lots Stage3")
    if (
        receipt.get("plan_signature") != plan["plan_signature"]
        or validation.get("plan_signature") != plan["plan_signature"]
        or validation.get("run_receipt_signature")
        != receipt.get("run_receipt_signature")
    ):
        raise FocusError("Plan/reçu/validation Stage3 non appariés")
    expected_ids = [str(row.get("dossier_id") or "") for row in plan["dossiers"]]
    validation_ids = [
        str(row.get("dossier_id") or "") for row in validation.get("dossiers") or []
    ]
    if (
        len(expected_ids) != len(set(expected_ids))
        or len(validation_ids) != len(set(validation_ids))
        or set(validation_ids) != set(expected_ids)
    ):
        raise FocusError("Validation Stage3 ne contient pas exactement ses dossiers")
    output = {}
    for dossier in plan["dossiers"]:
        lot_v4._validate_pair(dossier)  # noqa: SLF001
        priority = dossier["priority"]
        key = tuple(
            str(priority.get(name) or "")
            for name in ("operating_point_id", "mechanism", "lane_id")
        )
        if key in output:
            raise FocusError("Cellule Stage3 dupliquée")
        output[key] = dossier
    return output


def _source_dossier(
    context: Any, cell: Mapping[str, str], *, common_seed: int
) -> dict[str, Any]:
    """Build a V4-validator-compatible dossier from signed campaign evidence."""
    campaign = context.paths.campaign_root.resolve()
    results = context.paths.results_dir.resolve()
    manifest = lot_v4._verify_campaign_manifest(campaign / "campaign_manifest.json")  # noqa: SLF001
    _, _, metric_paths = lot_v4._validate_campaign_results(  # noqa: SLF001
        campaign_root=campaign,
        results_dir=results,
        manifest_path=campaign / "campaign_manifest.json",
        manifest=manifest,
    )
    metrics = lot_v4._load_metric_rows(metric_paths)  # noqa: SLF001
    lanes = [
        dict(row)
        for row in manifest.get("lanes") or []
        if str(row.get("supplier_id") or "") == cell["supplier_id"]
        and (not cell["lane_id"] or str(row.get("lane_id") or "") == cell["lane_id"])
    ]
    if len(lanes) != 1:
        raise FocusError("Le lane_id doit identifier une voie 338929 unique")
    expected_lane = {
        "supplier_id": DEFAULT_SUPPLIER,
        "item_id": DEFAULT_ITEM,
        "dst_node_id": DEFAULT_DESTINATION,
        "edge_id": DEFAULT_EDGE,
        "lane_id": DEFAULT_LANE,
        "target_product_id": DEFAULT_PRODUCT,
    }
    if any(
        str(lanes[0].get(key) or "") != value for key, value in expected_lane.items()
    ):
        raise FocusError("La voie 338929 ne correspond pas à l'identité physique figée")
    priority = {
        **lanes[0],
        "operating_point_id": cell["operating_point_id"],
        "mechanism": cell["mechanism"],
    }
    matches = [
        row
        for row in metrics
        if str(row.get("stage") or "") == "incident"
        and str(row.get("operating_point_id") or "") == DEFAULT_POINT
        and str(row.get("mechanism") or "") == cell["mechanism"]
        and str(row.get("lane_id") or "") == DEFAULT_LANE
        and int(row.get("seed") or -1) == common_seed
    ]
    if len(matches) != 1:
        raise FocusError("Cas incident commun absent ou dupliqué")
    incident = dict(matches[0])
    baseline = lot_v4._baseline_for(metrics, incident)  # noqa: SLF001
    shard_root = campaign / "shards"
    incident_key, baseline_key = str(incident["case_key"]), str(baseline["case_key"])
    incident_evidence_path = lot_v4._find_unique(  # noqa: SLF001
        shard_root, f"case_evidence/{incident_key}.json", "preuve incident"
    )
    baseline_evidence_path = lot_v4._find_unique(  # noqa: SLF001
        shard_root, f"case_evidence/{baseline_key}.json", "preuve référence"
    )
    incident_evidence = lot_v4._validate_case_evidence(  # noqa: SLF001
        incident_evidence_path, manifest=manifest, metric_row=incident
    )
    lot_v4._validate_case_evidence(  # noqa: SLF001
        baseline_evidence_path, manifest=manifest, metric_row=baseline
    )
    risk_row = lot_v4._risk_row_contract(  # noqa: SLF001
        incident_evidence["risk_row"], priority=priority, incident=incident
    )
    risk_sha = str(incident_evidence["risk_csv_sha256"])
    risk_sources = list(shard_root.glob(f"**/inputs/risk_events/{incident_key}.csv"))
    if len(risk_sources) != 1 or common.sha256_file(risk_sources[0]) != risk_sha:
        raise FocusError("CSV risque signé absent ou ambigu")
    state = next(
        (
            row
            for row in manifest.get("states") or []
            if row.get("operating_point_id") == cell["operating_point_id"]
        ),
        None,
    )
    if not isinstance(state, Mapping):
        raise FocusError("Point de fonctionnement absent du manifeste")
    graph = lot_v4._resolve_declared_path(state["graph"], (campaign,), "graphe")  # noqa: SLF001
    floors = (
        lot_v4._resolve_declared_path(
            state["supplier_floors"], (campaign,), "planchers"
        )
        if state.get("supplier_floors")
        else None
    )  # noqa: E501, SLF001
    capacities = (
        lot_v4._resolve_declared_path(
            state["factory_capacities"], (campaign,), "capacités"
        )
        if state.get("factory_capacities")
        else None
    )  # noqa: E501, SLF001
    profile = lot_v4._resolve_declared_path(
        manifest["engine_profile"], (campaign,), "profil"
    )  # noqa: SLF001
    engine = lot_v4._resolve_declared_path(manifest["engine"], (campaign,), "moteur")  # noqa: SLF001
    lot_v4._verify_file(engine, manifest["engine_sha256"], "moteur")  # noqa: SLF001
    lot_v4._verify_file(profile, manifest["engine_profile_sha256"], "profil")  # noqa: SLF001
    lot_v4._verify_file(graph, state["graph_sha256"], "graphe")  # noqa: SLF001
    if floors is not None:
        lot_v4._verify_file(floors, state["supplier_floors_sha256"], "planchers")  # noqa: SLF001
    if capacities is not None:
        lot_v4._verify_file(capacities, state["factory_capacities_sha256"], "capacités")  # noqa: SLF001
    return {
        "priority": priority,
        "incident_metric": incident,
        "baseline_metric": baseline,
        "incident_evidence_path": incident_evidence_path,
        "incident_evidence_sha256": common.sha256_file(incident_evidence_path),
        "baseline_evidence_path": baseline_evidence_path,
        "baseline_evidence_sha256": common.sha256_file(baseline_evidence_path),
        "metric_sources": [
            {"path": str(path.resolve()), "sha256": common.sha256_file(path)}
            for path in metric_paths
        ],
        "manifest_path": campaign / "campaign_manifest.json",
        "manifest_sha256": common.sha256_file(campaign / "campaign_manifest.json"),
        "risk_row": risk_row,
        "risk_source": risk_sources[0],
        "risk_csv_sha256": risk_sha,
        "graph": graph,
        "graph_sha256": common.sha256_file(graph),
        "floors": floors,
        "capacities": capacities,
        "engine": engine,
        "engine_sha256": manifest["engine_sha256"],
        "profile": profile,
        "profile_sha256": manifest["engine_profile_sha256"],
        "floors_sha256": state.get("supplier_floors_sha256", ""),
        "capacities_sha256": state.get("factory_capacities_sha256", ""),
        "profile_args": lot_v4._profile_args(profile),  # noqa: SLF001
        "managed_args": manifest["managed_engine_args"],
        "horizon_days": int(
            incident.get("required_simulation_days") or incident["simulation_days"]
        ),
        "seed": int(incident["seed"]),
        "warmup_core_state_sha256": str(incident["warmup_core_state_sha256"]),
    }


def create_plan(stage3: Path, closure: Path, output_root: Path) -> dict[str, Any]:
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_root.parent / f".{output_root.name}.focus_plan.lock"
    with common.exclusive_lock(lock_path):
        return _create_plan_locked(stage3, closure, output_root)


def _create_plan_locked(
    stage3: Path, closure: Path, output_root: Path
) -> dict[str, Any]:
    output_root = output_root.resolve()
    if (output_root / "focus_plan.json").is_file():
        existing = load_plan(output_root)
        if (
            Path(existing["stage3_supervision"]).resolve() != stage3.resolve()
            or Path(existing["closure_report"]).resolve() != closure.resolve()
        ):
            raise FocusError("Plan existant lié à une autre clôture")
        return existing
    if output_root.exists() and any(output_root.iterdir()):
        raise FocusError("Racine de focus non vide")
    context = _closure_context(stage3, closure)
    protected = [
        Path(value).resolve()
        for value in vars(context.paths).values()
        if value is not None
    ]
    if any(common.paths_overlap(output_root, path) for path in protected):
        raise FocusError("La racine additive chevauche une racine Stage3 gelée")
    old = _stage3_dossiers(context)
    manifest = lot_v4._verify_campaign_manifest(  # noqa: SLF001
        context.paths.campaign_root / "campaign_manifest.json"
    )
    _, _, metric_paths = lot_v4._validate_campaign_results(  # noqa: SLF001
        campaign_root=context.paths.campaign_root,
        results_dir=context.paths.results_dir,
        manifest_path=context.paths.campaign_root / "campaign_manifest.json",
        manifest=manifest,
    )
    common_seed = select_common_seed(lot_v4._load_metric_rows(metric_paths))  # noqa: SLF001
    dossiers = []
    for cell in _matrix():
        matches = [
            key
            for key in old
            if key[:2] == (cell["operating_point_id"], cell["mechanism"])
            and (not cell["lane_id"] or key[2] == cell["lane_id"])
        ]
        if len(matches) > 1:
            raise FocusError("Déduplication ambiguë: préciser lane_id")
        if matches:
            dossier = old[matches[0]]
            identity = dossier["priority"]
            expected = {
                "supplier_id": DEFAULT_SUPPLIER,
                "item_id": DEFAULT_ITEM,
                "dst_node_id": DEFAULT_DESTINATION,
                "edge_id": DEFAULT_EDGE,
                "lane_id": DEFAULT_LANE,
                "target_product_id": DEFAULT_PRODUCT,
            }
            if any(
                str(identity.get(key) or "") != value for key, value in expected.items()
            ):
                raise FocusError("STAGE3_CELL_BINDING_CONFLICT")
            if int(dossier.get("seed") or -1) == common_seed:
                dossiers.append(
                    {
                        "mode": "reuse_stage3",
                        "selection_basis": SELECTION_BASIS,
                        "source_priority_status": dossier["priority"].get(
                            "priority_status"
                        ),
                        "stage3_dossier_sha256": common.stable_sha256(dossier),
                        "dossier": dossier,
                    }
                )
                continue
        source = _source_dossier(context, cell, common_seed=common_seed)
        dossier_id = f"focus_{cell['operating_point_id']}_{cell['mechanism']}_{source['priority']['lane_id']}"
        risk_path = output_root / "inputs" / dossier_id / "supplier_risk_events.csv"
        run_base = output_root / "runs" / dossier_id
        dossier = {
            "dossier_id": dossier_id,
            "selection_basis": SELECTION_BASIS,
            "source_priority_status": None,
            "priority": source["priority"],
            "risk_row": source["risk_row"],
            "risk_csv": str(risk_path),
            "risk_csv_sha256": source["risk_csv_sha256"],
            "graph_sha256": source["graph_sha256"],
            "source_files": {
                "engine": {
                    "path": str(source["engine"]),
                    "sha256": source["engine_sha256"],
                },
                "profile": {
                    "path": str(source["profile"]),
                    "sha256": source["profile_sha256"],
                },
                "graph": {
                    "path": str(source["graph"]),
                    "sha256": source["graph_sha256"],
                },
                "supplier_floors": {
                    "path": str(source["floors"] or ""),
                    "sha256": source["floors_sha256"],
                },
                "factory_capacities": {
                    "path": str(source["capacities"] or ""),
                    "sha256": source["capacities_sha256"],
                },
            },
            "source_provenance": {
                "incident_metric": source["incident_metric"],
                "baseline_metric": source["baseline_metric"],
                "incident_evidence": {
                    "path": str(source["incident_evidence_path"]),
                    "sha256": source["incident_evidence_sha256"],
                },
                "baseline_evidence": {
                    "path": str(source["baseline_evidence_path"]),
                    "sha256": source["baseline_evidence_sha256"],
                },
                "metric_sources": source["metric_sources"],
                "campaign_manifest": {
                    "path": str(source["manifest_path"]),
                    "sha256": source["manifest_sha256"],
                },
                "stage3_contract_signature": context.contract["contract_signature"],
                "stage3_status_signature": context.status["status_signature"],
            },
            "command_contract": {
                "profile_args": source["profile_args"],
                "managed_args": source["managed_args"],
            },
            "horizon_days": source["horizon_days"],
            "seed": source["seed"],
            "warmup_core_state_sha256": "",
        }
        dossier["warmup_core_state_sha256"] = source["warmup_core_state_sha256"]
        dossier["kpi_scope"] = {
            "service_node_id": lot_v4.V4_CLIENT_NODE_ID,
            "production_node_id": str(source["priority"]["dst_node_id"]),
            "product_id": str(source["priority"]["target_product_id"]),
            "service_definition": "current demand served after clearing starting backlog",
        }
        arms = {}
        for arm in ("baseline", "incident"):
            command = lot_v4._build_command(  # noqa: SLF001
                python_executable=sys.executable,
                engine=source["engine"],
                graph=Path(str(source["graph"])),
                output_dir=run_base / arm,
                horizon=source["horizon_days"],
                seed=source["seed"],
                supplier_floors=source["floors"],
                factory_capacities=source["capacities"],
                profile_args=source["profile_args"],
                managed_args=source["managed_args"],
                risk_csv=risk_path if arm == "incident" else None,
            )
            arms[arm] = {
                "run_dir": str(run_base / arm),
                "command": command,
                "command_sha256": common.stable_sha256(command),
            }
        dossier["arms"] = arms
        dossiers.append(
            {
                "mode": "new_focus",
                "selection_basis": SELECTION_BASIS,
                "source_priority_status": None,
                "dossier": dossier,
                "risk_source": str(source["risk_source"]),
            }
        )
    if len(dossiers) != 2:
        raise FocusError("Le plan doit contenir exactement deux dossiers")
    unsigned = {
        "schema_version": PLAN_SCHEMA,
        "selection_basis": SELECTION_BASIS,
        "supplier_id": DEFAULT_SUPPLIER,
        "item_id": DEFAULT_ITEM,
        "common_seed": common_seed,
        "stage3_supervision": str(stage3.resolve()),
        "stage3_status_signature": context.status["status_signature"],
        "closure_report": str(closure.resolve()),
        "closure_report_sha256": common.sha256_file(closure),
        "output_root": str(output_root),
        "lot_validator_path": str(Path(lot_v4.__file__).resolve()),
        "lot_validator_sha256": common.sha256_file(Path(lot_v4.__file__)),
        "scientific_contract": {
            "priority_claimed": False,
            "quality_included": False,
            "state_dependent_risks_enabled": False,
            "capacity_or_availability_modified": False,
            "common_random_numbers": True,
            "seed_selection_uses_outcomes": False,
            "maximum_engine_runs": 2
            * sum(row["mode"] == "new_focus" for row in dossiers),
        },
        "dossiers": dossiers,
    }
    plan = _signed(unsigned, "plan_signature")
    staging = output_root.parent / f".{output_root.name}.staging.{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        for row in dossiers:
            if row["mode"] == "new_focus":
                final_target = Path(row["dossier"]["risk_csv"])
                relative = final_target.resolve().relative_to(output_root)
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                data = Path(row["risk_source"]).read_bytes()
                if (
                    common.sha256_file(Path(row["risk_source"]))
                    != row["dossier"]["risk_csv_sha256"]
                ):
                    raise FocusError("Source risque modifiée")
                common.publish_new_or_identical(target, data)
        common.publish_new_or_identical(
            staging / "focus_plan.json",
            (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode(),
        )
        staging.replace(output_root)
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)
    return plan


def load_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    plan = _read(root / "focus_plan.json")
    if (
        plan.get("schema_version") != PLAN_SCHEMA
        or plan.get("selection_basis") != SELECTION_BASIS
        or Path(str(plan.get("output_root"))).resolve() != root
    ):
        raise FocusError("Plan focus invalide")
    _verify(plan, "plan_signature", "plan focus")
    dossiers = plan.get("dossiers") or []
    identities = [
        (
            str(
                row.get("dossier", {}).get("priority", {}).get("operating_point_id")
                or ""
            ),
            str(row.get("dossier", {}).get("priority", {}).get("mechanism") or ""),
            str(row.get("dossier", {}).get("priority", {}).get("lane_id") or ""),
        )
        for row in dossiers
    ]
    if (
        len(dossiers) != 2
        or len(set(identities)) != 2
        or {identity[1] for identity in identities} != set(MECHANISMS)
        or any(
            identity[0] != DEFAULT_POINT or identity[2] != DEFAULT_LANE
            for identity in identities
        )
        or {int(row.get("dossier", {}).get("seed") or -1) for row in dossiers}
        != {int(plan.get("common_seed") or -2)}
    ):
        raise FocusError("Ensemble exact des deux dossiers focus invalide")
    if (
        Path(str(plan["lot_validator_path"])).resolve()
        != Path(lot_v4.__file__).resolve()
        or common.sha256_file(Path(lot_v4.__file__)) != plan["lot_validator_sha256"]
    ):
        raise FocusError("Validateur lots lié au plan modifié")
    closure_path = Path(str(plan.get("closure_report") or ""))
    if not closure_path.is_file() or common.sha256_file(closure_path) != plan.get(
        "closure_report_sha256"
    ):
        raise FocusError("Rapport de clôture lié au plan modifié")
    context = _closure_context(Path(plan["stage3_supervision"]), closure_path)
    if context.status.get("status_signature") != plan.get("stage3_status_signature"):
        raise FocusError("Statut Stage3 lié au plan modifié")
    stage3_manifest_path = (
        context.paths.campaign_root / "campaign_manifest.json"
    ).resolve()
    stage3_manifest = lot_v4._verify_campaign_manifest(  # noqa: SLF001
        stage3_manifest_path
    )
    _, _, stage3_metric_paths = lot_v4._validate_campaign_results(  # noqa: SLF001
        campaign_root=context.paths.campaign_root,
        results_dir=context.paths.results_dir,
        manifest_path=stage3_manifest_path,
        manifest=stage3_manifest,
    )
    stage3_metric_rows = lot_v4._load_metric_rows(stage3_metric_paths)  # noqa: SLF001
    if select_common_seed(stage3_metric_rows) != int(plan.get("common_seed") or -1):
        raise FocusError("Graine commune non redérivée des métriques Stage3")
    stage3 = _stage3_dossiers(context)
    new_count = sum(row.get("mode") == "new_focus" for row in dossiers)
    expected_scientific = {
        "priority_claimed": False,
        "quality_included": False,
        "state_dependent_risks_enabled": False,
        "capacity_or_availability_modified": False,
        "common_random_numbers": True,
        "seed_selection_uses_outcomes": False,
        "maximum_engine_runs": 2 * new_count,
    }
    if (
        plan.get("supplier_id") != DEFAULT_SUPPLIER
        or plan.get("item_id") != DEFAULT_ITEM
        or plan.get("scientific_contract") != expected_scientific
        or 2 * new_count not in {0, 2, 4}
    ):
        raise FocusError("Nombre de bras 0/2/4 incohérent")
    for row in plan.get("dossiers") or []:
        if row.get("selection_basis") != SELECTION_BASIS or row.get("mode") not in {
            "reuse_stage3",
            "new_focus",
        }:
            raise FocusError("Dossier focus hors contrat")
        dossier = row.get("dossier") or {}
        identity = dossier.get("priority") or {}
        expected_identity = {
            "supplier_id": DEFAULT_SUPPLIER,
            "item_id": DEFAULT_ITEM,
            "dst_node_id": DEFAULT_DESTINATION,
            "edge_id": DEFAULT_EDGE,
            "lane_id": DEFAULT_LANE,
            "target_product_id": DEFAULT_PRODUCT,
            "operating_point_id": DEFAULT_POINT,
        }
        if any(
            str(identity.get(key) or "") != value
            for key, value in expected_identity.items()
        ):
            raise FocusError("Identité physique du dossier falsifiée")
        if dossier.get("selection_basis", SELECTION_BASIS) != SELECTION_BASIS:
            raise FocusError("Dossier présenté à tort comme une priorité")
        if row["mode"] == "new_focus":
            if row.get("source_priority_status") is not None:
                raise FocusError("Priorité artificielle interdite")
            risk = _inside(root, Path(dossier["risk_csv"]), "risque")
            if common.sha256_file(risk) != dossier.get("risk_csv_sha256"):
                raise FocusError("CSV risque du focus modifié")
            for label, source in (dossier.get("source_files") or {}).items():
                raw_path = str(source.get("path") or "")
                source_sha = str(source.get("sha256") or "")
                if not raw_path and not source_sha:
                    continue
                source_path = Path(raw_path)
                if (
                    not source_path.is_file()
                    or common.sha256_file(source_path) != source_sha
                ):
                    raise FocusError(f"Source déclarée modifiée: {label}")
            provenance = dossier.get("source_provenance") or {}
            if (
                provenance.get("stage3_contract_signature")
                != context.contract["contract_signature"]
                or provenance.get("stage3_status_signature")
                != context.status["status_signature"]
            ):
                raise FocusError("Provenance Stage3 du nouveau dossier modifiée")
            expected_manifest_path = stage3_manifest_path
            manifest = stage3_manifest
            expected_metric_paths = stage3_metric_paths
            expected_metric_sources = [
                {"path": str(path.resolve()), "sha256": common.sha256_file(path)}
                for path in expected_metric_paths
            ]
            if (
                provenance.get("campaign_manifest")
                != {
                    "path": str(expected_manifest_path),
                    "sha256": common.sha256_file(expected_manifest_path),
                }
                or provenance.get("metric_sources") != expected_metric_sources
            ):
                raise FocusError(
                    "Manifeste ou liste de métriques non dérivé du contexte Stage3"
                )
            for label in (
                "incident_evidence",
                "baseline_evidence",
                "campaign_manifest",
            ):
                source = provenance.get(label) or {}
                path = Path(str(source.get("path") or ""))
                if not path.is_file() or common.sha256_file(path) != source.get(
                    "sha256"
                ):
                    raise FocusError(f"Preuve source new_focus modifiée: {label}")
            for source in provenance.get("metric_sources") or []:
                path = Path(str(source.get("path") or ""))
                if not path.is_file() or common.sha256_file(path) != source.get(
                    "sha256"
                ):
                    raise FocusError("Shard métrique new_focus modifié")
            metric_sources = provenance.get("metric_sources") or []
            if not metric_sources:
                raise FocusError("Sources métriques new_focus absentes")
            metric_rows = stage3_metric_rows
            incident_metric = provenance["incident_metric"]
            occurrences = [
                metric
                for metric in metric_rows
                if str(metric.get("case_key") or "")
                == str(incident_metric.get("case_key") or "")
                and str(metric.get("case_signature") or "")
                == str(incident_metric.get("case_signature") or "")
            ]
            if len(occurrences) != 1 or occurrences[0] != incident_metric:
                raise FocusError("Métrique incident absente, dupliquée ou altérée")
            baseline_metric = lot_v4._baseline_for(  # noqa: SLF001
                metric_rows, incident_metric
            )
            if baseline_metric != provenance.get("baseline_metric"):
                raise FocusError("Métrique de référence non appariée à l'incident")
            for arm_name, metric in (
                ("incident", incident_metric),
                ("baseline", baseline_metric),
            ):
                lot_v4._validate_case_evidence(  # noqa: SLF001
                    Path(provenance[f"{arm_name}_evidence"]["path"]),
                    manifest=manifest,
                    metric_row=metric,
                )
                if int(metric.get("seed") or -1) != int(plan["common_seed"]):
                    raise FocusError("Graine de preuve new_focus modifiée")
            mechanism = str(dossier["priority"]["mechanism"])
            if not _is_focus_incident(incident_metric, mechanism):
                raise FocusError("Prédicat physique complet du focus non satisfait")
            expected_horizon = int(
                incident_metric.get("required_simulation_days")
                or incident_metric.get("simulation_days")
                or -1
            )
            warmups = {
                str(incident_metric.get("warmup_core_state_sha256") or ""),
                str(baseline_metric.get("warmup_core_state_sha256") or ""),
                str(dossier.get("warmup_core_state_sha256") or ""),
            }
            if (
                int(dossier.get("seed") or -1) != int(plan["common_seed"])
                or int(baseline_metric.get("seed") or -2) != int(plan["common_seed"])
                or int(dossier.get("horizon_days") or -1) != expected_horizon
                or int(
                    baseline_metric.get("required_simulation_days")
                    or baseline_metric.get("simulation_days")
                    or -2
                )
                != expected_horizon
                or len(warmups) != 1
                or not next(iter(warmups))
            ):
                raise FocusError("Seed, horizon ou warmup des bras appariés divergent")
            evidence = _read(Path(provenance["incident_evidence"]["path"]))
            reconstructed_risk = lot_v4._risk_row_contract(  # noqa: SLF001
                evidence.get("risk_row") or {},
                priority=dossier["priority"],
                incident=incident_metric,
            )
            if reconstructed_risk != dossier.get("risk_row"):
                raise FocusError("Contrat risque new_focus altéré")
            risk_rows = lot_v4._read_csv(risk)  # noqa: SLF001
            if len(risk_rows) != 1:
                raise FocusError(
                    "CSV risque new_focus doit contenir un événement exact"
                )
            if lot_v4._risk_row_contract(  # noqa: SLF001
                risk_rows[0],
                priority=dossier["priority"],
                incident=incident_metric,
            ) != dossier.get("risk_row"):
                raise FocusError("CSV risque et preuve incidente divergent")
            for arm in ("baseline", "incident"):
                arm_plan = dossier.get("arms", {}).get(arm) or {}
                command = arm_plan.get("command") or []
                if common.stable_sha256(command) != arm_plan.get("command_sha256"):
                    raise FocusError("Commande du focus modifiée")
                _inside(root, Path(arm_plan["run_dir"]), "run")
                lot_v4._validate_command(command, incident=arm == "incident")  # noqa: SLF001
                expected_flags = {
                    "--input": str(dossier["source_files"]["graph"]["path"]),
                    "--output-dir": str(Path(arm_plan["run_dir"]).resolve()),
                    "--days": str(dossier["horizon_days"]),
                    "--seed": str(dossier["seed"]),
                }
                for flag, expected_value in expected_flags.items():
                    values = lot_v4._flag_values(command, flag)  # noqa: SLF001
                    actual = str(values[0] if values else "")
                    if flag in {"--input", "--output-dir"}:
                        actual = str(Path(actual).resolve())
                        expected_value = str(Path(expected_value).resolve())
                    if actual != expected_value:
                        raise FocusError(f"Commande non liée exactement: {flag}")
                risks = lot_v4._flag_values(  # noqa: SLF001
                    command, "--supplier-risk-events-csv"
                )
                if (
                    arm == "incident"
                    and [str(Path(value).resolve()) for value in risks]
                    != [str(risk.resolve())]
                ) or (arm == "baseline" and risks):
                    raise FocusError("Commande risque non liée exactement")
                if (
                    Path(command[0]).resolve() != Path(sys.executable).resolve()
                    or Path(command[1]).resolve()
                    != Path(dossier["source_files"]["engine"]["path"]).resolve()
                ):
                    raise FocusError("Commande Python/moteur non liée exactement")
                sources = dossier["source_files"]
                rebuilt = lot_v4._build_command(  # noqa: SLF001
                    python_executable=sys.executable,
                    engine=Path(sources["engine"]["path"]),
                    graph=Path(sources["graph"]["path"]),
                    output_dir=Path(arm_plan["run_dir"]),
                    horizon=int(dossier["horizon_days"]),
                    seed=int(dossier["seed"]),
                    supplier_floors=(
                        Path(sources["supplier_floors"]["path"])
                        if sources["supplier_floors"]["path"]
                        else None
                    ),
                    factory_capacities=(
                        Path(sources["factory_capacities"]["path"])
                        if sources["factory_capacities"]["path"]
                        else None
                    ),
                    profile_args=dossier["command_contract"]["profile_args"],
                    managed_args=dossier["command_contract"]["managed_args"],
                    risk_csv=risk if arm == "incident" else None,
                )
                if command != rebuilt:
                    raise FocusError("Commande reconstruite différente du plan")
        else:
            priority = dossier["priority"]
            key = (
                str(priority["operating_point_id"]),
                str(priority["mechanism"]),
                str(priority["lane_id"]),
            )
            source = stage3.get(key)
            if (
                source is None
                or common.stable_sha256(source) != row.get("stage3_dossier_sha256")
                or source != dossier
            ):
                raise FocusError("Provenance du dossier Stage3 réutilisé invalide")
    return plan


def run(root: Path, execute: bool = False) -> dict[str, Any]:
    plan = load_plan(root)
    jobs = [
        (row["dossier"], arm)
        for row in plan["dossiers"]
        if row["mode"] == "new_focus"
        for arm in ("baseline", "incident")
    ]
    if not execute:
        return {
            "status": "validated_not_executed",
            "planned_engine_runs": len(jobs),
            "plan_signature": plan["plan_signature"],
        }
    with common.exclusive_lock(root.resolve() / ".focus_338929.lock"):
        return _execute_locked(root.resolve(), plan, jobs)


def _validate_receipt(plan: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
    _verify(receipt, "receipt_signature", "reçu focus")
    jobs = [
        (row["dossier"], arm)
        for row in plan["dossiers"]
        if row["mode"] == "new_focus"
        for arm in ("baseline", "incident")
    ]
    expected = [
        {
            "dossier_id": dossier["dossier_id"],
            **lot_v4.validate_arm(
                Path(dossier["arms"][arm]["run_dir"]), dossier=dossier, arm=arm
            ),
        }
        for dossier, arm in jobs
    ]
    counters = tuple(
        receipt.get(name)
        for name in (
            "planned_arm_count",
            "executed_arm_count",
            "preexisting_validated_arm_count",
        )
    )
    if any(type(value) is not int or value < 0 for value in counters):
        raise FocusError("Compteurs du reçu invalides")
    planned, executed, preexisting = counters
    keys = [
        (str(row.get("dossier_id") or ""), str(row.get("arm") or ""))
        for row in receipt.get("arms") or []
    ]
    expected_keys = [(str(dossier["dossier_id"]), arm) for dossier, arm in jobs]
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("status") != "complete_validated"
        or receipt.get("plan_signature") != plan["plan_signature"]
        or receipt.get("partial_policy")
        != "fail_closed_keep_validated_outputs_never_overwrite"
        or planned != len(jobs)
        or executed > planned
        or preexisting > planned
        or executed + preexisting != planned
        or keys != expected_keys
        or len(keys) != len(set(keys))
        or receipt.get("arms") != expected
    ):
        raise FocusError("Reçu administrativement incohérent")


def _execute_locked(
    root: Path,
    plan: Mapping[str, Any],
    jobs: Sequence[tuple[Mapping[str, Any], str]],
) -> dict[str, Any]:
    receipt_path = root / "focus_run_receipt.json"
    if receipt_path.is_file():
        receipt = _read(receipt_path)
        for row in plan["dossiers"]:
            lot_v4._validate_pair(row["dossier"])  # noqa: SLF001
        _validate_receipt(plan, receipt)
        return receipt
    proofs = []
    preexisting = 0
    executed = 0
    for dossier, arm in jobs:
        run_dir = Path(dossier["arms"][arm]["run_dir"])
        _inside(root, run_dir, "run")
        if run_dir.exists():
            preexisting += 1
        else:
            completed = subprocess.run(
                dossier["arms"][arm]["command"],
                cwd=Path(__file__).resolve().parents[3],
                check=False,
            )
            if completed.returncode:
                raise FocusError(f"Échec moteur {dossier['dossier_id']}/{arm}")
            executed += 1
        proofs.append(
            {
                "dossier_id": dossier["dossier_id"],
                **lot_v4.validate_arm(run_dir, dossier=dossier, arm=arm),
            }
        )
    for row in plan["dossiers"]:
        lot_v4._validate_pair(row["dossier"])  # noqa: SLF001
    receipt = _signed(
        {
            "schema_version": RECEIPT_SCHEMA,
            "status": "complete_validated",
            "plan_signature": plan["plan_signature"],
            "planned_arm_count": len(jobs),
            "executed_arm_count": executed,
            "preexisting_validated_arm_count": preexisting,
            "partial_policy": "fail_closed_keep_validated_outputs_never_overwrite",
            "arms": proofs,
        },
        "receipt_signature",
    )
    common.publish_new_or_identical(
        receipt_path,
        (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return receipt


def finalize(root: Path) -> dict[str, Any]:
    with common.exclusive_lock(root.resolve() / ".focus_338929.lock"):
        return _finalize_locked(root.resolve())


def _finalize_locked(root: Path) -> dict[str, Any]:
    plan = load_plan(root)
    receipt = _read(root.resolve() / "focus_run_receipt.json")
    _validate_receipt(plan, receipt)
    traces = []
    for row in plan["dossiers"]:
        dossier = row["dossier"]
        lot_v4._validate_pair(dossier)  # noqa: SLF001
        trace = lot_v4.extract_native_trace(
            Path(dossier["arms"]["incident"]["run_dir"]), dossier=dossier
        )
        counts = {key: len(value) for key, value in trace.items()}
        completeness = (
            "complete_to_aggregated_client"
            if all(counts[key] > 0 for key in counts)
            else "partial_native_contact_trace"
        )
        traces.append(
            {
                "dossier_id": dossier["dossier_id"],
                "mode": row["mode"],
                "counts": counts,
                "trace_sha256": common.stable_sha256(trace),
                "trace_completeness": completeness,
                "trace": trace,
            }
        )
    validation = _signed(
        {
            "schema_version": VALIDATION_SCHEMA,
            "status": "complete_validated",
            "selection_basis": SELECTION_BASIS,
            "plan_signature": plan["plan_signature"],
            "receipt_signature": receipt["receipt_signature"],
            "dossiers": traces,
        },
        "validation_signature",
    )
    common.publish_new_or_identical(
        root.resolve() / "focus_validation.json",
        (json.dumps(validation, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return validation


def validate(root: Path) -> dict[str, Any]:
    plan = load_plan(root)
    path = root.resolve() / "focus_validation.json"
    if not path.is_file():
        return {"status": "valid_plan_only", "plan_signature": plan["plan_signature"]}
    result = _read(path)
    _verify(result, "validation_signature", "validation focus")
    receipt = _read(root.resolve() / "focus_run_receipt.json")
    _validate_receipt(plan, receipt)
    if result.get("receipt_signature") != receipt.get("receipt_signature"):
        raise FocusError("Reçu focus périmé ou non lié")
    if (
        result.get("schema_version") != VALIDATION_SCHEMA
        or result.get("status") != "complete_validated"
        or result.get("selection_basis") != SELECTION_BASIS
        or result.get("plan_signature") != plan["plan_signature"]
    ):
        raise FocusError("Validation liée à un autre plan")
    declared_rows = result.get("dossiers") or []
    declared = {str(row.get("dossier_id") or ""): row for row in declared_rows}
    if len(declared_rows) != 2 or len(declared) != 2:
        raise FocusError("Doublon ou dossier supplémentaire dans la validation")
    for row in plan["dossiers"]:
        dossier = row["dossier"]
        dossier_id = str(dossier["dossier_id"])
        if (
            dossier_id not in declared
            or declared[dossier_id].get("mode") != row["mode"]
        ):
            raise FocusError("Validation focus incomplète")
        lot_v4._validate_pair(dossier)  # noqa: SLF001
        trace = lot_v4.extract_native_trace(
            Path(dossier["arms"]["incident"]["run_dir"]), dossier=dossier
        )
        if declared[dossier_id].get("counts") != {
            key: len(value) for key, value in trace.items()
        }:
            raise FocusError("Comptages de trace focus modifiés")
        if declared[dossier_id].get("trace_sha256") != common.stable_sha256(trace):
            raise FocusError("Contenu de trace focus modifié")
        expected_completeness = (
            "complete_to_aggregated_client"
            if all(len(value) > 0 for value in trace.values())
            else "partial_native_contact_trace"
        )
        if (
            declared[dossier_id].get("trace") != trace
            or declared[dossier_id].get("trace_completeness") != expected_completeness
        ):
            raise FocusError("Trace ou niveau de complétude falsifié")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--stage3-supervision", type=Path, required=True)
    plan.add_argument("--closure-report", type=Path, required=True)
    plan.add_argument("--output-root", type=Path, required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--root", type=Path, required=True)
    run_parser.add_argument("--execute", action="store_true")
    for name in ("finalize", "validate"):
        item = sub.add_parser(name)
        item.add_argument("--root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = create_plan(
                args.stage3_supervision, args.closure_report, args.output_root
            )
        elif args.command == "run":
            result = run(args.root, args.execute)
        elif args.command == "finalize":
            result = finalize(args.root)
        else:
            result = validate(args.root)
    except FocusError as exc:
        print(f"FOCUS 338929 INVALID: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
