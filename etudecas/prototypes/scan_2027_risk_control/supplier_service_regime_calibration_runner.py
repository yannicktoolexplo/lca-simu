#!/usr/bin/env python3
"""Execute the signed service-regime calibration plan in resumable stages.

The runner is deliberately separate from the calibration protocol.  It accepts
only the frozen V2 plan artifact, executes the 36 one-seed screening points,
freezes the discrete point/bracket selection, and then confirms that selection
on an exact 15-seed prefix before a later invocation adds seeds 16--30.

No acute supplier incident is loaded.  Results are conditional simulation
hypotheses, not observed supplier performance or an action recommendation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Callable, Iterable, Mapping, Sequence

_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as campaign_core,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)


SCHEMA_VERSION = "etudecas.supplier_service_regime_calibration_runner.v1"
LEDGER_SCHEMA_VERSION = f"{SCHEMA_VERSION}.ledger"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
CHECKPOINT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.checkpoint_15_of_30"
CONTRACT_REVISION = "isolated_regime_screen_select_checkpoint_resume_2026_09"
EXPECTED_PROTOCOL_BUILDER_SHA256 = (
    "6da3c120bc89b26fe578c6d0877c749d94437f1aba647f694a9d32bc89b53ae8"
)
EXPECTED_PLAN_ARTIFACT_SHA256 = (
    "73ad91b0857e59eea2ff7ebb6a2f69d048299e443d56931fed13756dc564adb1"
)
EXPECTED_PLAN_FILE_COUNT = 77
RUNNER_MANIFEST = "calibration_runner_manifest.json"
LEDGER_FILE = "execution_ledger.json"
CHECKPOINT_FILE = "preliminary_checkpoint_15_manifest.json"
SELECTION_FILE = "screening_selection.json"
LOCK_FILE = ".calibration_runner.lock"
SCREENING_METRICS_FILE = "screening_metrics.csv"
CONFIRMATION_METRICS_FILE = "confirmation_metrics.csv"
CONFIRMATION_SUMMARY_FILE = "confirmation_summary.csv"
REFERENCE_METRICS_FILE = "reference_baseline_metrics.csv"
SEED_SCHEDULING_POLICY = "signed_cumulative_seed_prefix_15_then_30"


@dataclass(frozen=True)
class ValidatedPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    inventory: dict[str, dict[str, Any]]
    candidates: tuple[protocol.Candidate, ...]
    plan_artifact_sha256: str
    calibration_plan_sha256: str
    reference_campaign: Path
    graph: Path
    engine: Path
    profile: Path


@dataclass(frozen=True)
class PlannedCase:
    scenario_id: str
    seed: int
    stage: str

    @property
    def key(self) -> str:
        return f"{self.scenario_id}::seed_{self.seed}"


CaseExecutor = Callable[[PlannedCase, ValidatedPlan, Path], dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return protocol.sha256_file(path)


def _stable_sha256(payload: Any) -> str:
    return protocol.stable_sha256(payload)


def _read_json(path: Path) -> dict[str, Any]:
    return protocol.read_json(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    campaign_core.write_json_atomic(path, payload)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    campaign_core.write_csv_atomic(path, rows)


def _directory_file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _directory_digest(directory: Path) -> tuple[str, dict[str, str]]:
    hashes = _directory_file_hashes(directory)
    return _stable_sha256(hashes), hashes


def _strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    text = str(value).strip()
    if not text or any(character in text for character in ".eE"):
        raise ValueError(f"{label} must be an integer")
    try:
        parsed = int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    return parsed


def _safe_plan_file(plan_dir: Path, configured: Any, expected: Path) -> Path:
    path = Path(str(configured or ""))
    if not path.is_absolute():
        raise ValueError(f"Plan path is not absolute: {configured!r}")
    expected = expected.resolve()
    if path.is_symlink() or not path.is_file() or path.resolve() != expected:
        raise ValueError(f"Plan path is missing or redirected: {configured!r}")
    try:
        expected.relative_to(plan_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"Candidate input escapes the plan: {configured!r}") from exc
    return expected


def _plan_signature_payload(
    manifest: Mapping[str, Any], inventory: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": protocol.SCHEMA_VERSION,
        "reference_audit": manifest.get("reference_audit"),
        "families": [asdict(family) for family in protocol.FAMILIES],
        "candidate_inputs": {
            key: {
                "input_sha256": value["input_sha256"],
                "change_ledger_sha256": value["change_ledger_sha256"],
            }
            for key, value in sorted(inventory.items())
        },
        "stages": manifest.get("stages"),
        "selection_rule": manifest.get("selection_rule"),
        "service_definition": manifest.get("service_definition"),
        "execution_contract": manifest.get("execution_contract"),
    }


def validate_plan_artifact(plan_dir: Path) -> ValidatedPlan:
    plan_dir = plan_dir.resolve()
    protocol_hash = _sha256(Path(protocol.__file__).resolve())
    if protocol_hash != EXPECTED_PROTOCOL_BUILDER_SHA256:
        raise ValueError(
            "Calibration protocol builder differs from the frozen V2 contract"
        )
    if not plan_dir.is_dir() or plan_dir.is_symlink():
        raise FileNotFoundError(f"Calibration plan directory missing: {plan_dir}")
    digest, file_hashes = _directory_digest(plan_dir)
    if (
        len(file_hashes) != EXPECTED_PLAN_FILE_COUNT
        or digest != EXPECTED_PLAN_ARTIFACT_SHA256
    ):
        raise ValueError(
            "Calibration plan inventory/digest differs from the frozen V2 artifact"
        )
    root_files = {
        "AUDIT_ET_PROTOCOLE.md",
        "calibration_plan.json",
        "existing_results_audit.json",
        "input_inventory.json",
        "scenario_design.csv",
    }
    manifest = _read_json(plan_dir / "calibration_plan.json")
    inventory_raw = _read_json(plan_dir / "input_inventory.json")
    if not isinstance(inventory_raw, dict):
        raise ValueError("input_inventory.json is not an object")
    inventory = {str(key): dict(value) for key, value in inventory_raw.items()}
    candidates = tuple(protocol.build_candidates())
    candidate_by_id = {candidate.scenario_id: candidate for candidate in candidates}
    if (
        manifest.get("schema_version") != protocol.SCHEMA_VERSION
        or manifest.get("status") != "planned_not_executed"
        or manifest.get("screening_candidate_count") != 36
        or set(inventory) != set(candidate_by_id)
    ):
        raise ValueError("Calibration plan scope/schema is not the frozen 36-point design")
    expected_signature = _stable_sha256(
        _plan_signature_payload(manifest, inventory)
    )
    if str(manifest.get("plan_signature") or "") != expected_signature:
        raise ValueError("Calibration plan signature is inconsistent")
    expected_files = set(root_files)
    for scenario_id, candidate in candidate_by_id.items():
        item = inventory[scenario_id]
        scenario_dir = plan_dir / "inputs" / scenario_id
        filename_by_kind = {
            "supplier_floor": "supplier_capacity_floors.csv",
            "factory_capacity": "factory_capacities.csv",
            "graph_lead": "candidate_graph.json",
            "graph_reliability": "candidate_graph.json",
            "graph_demand": "candidate_graph.json",
        }
        expected_input = scenario_dir / filename_by_kind[candidate.kind]
        expected_change = scenario_dir / "change_ledger.json"
        input_path = _safe_plan_file(
            plan_dir, item.get("input_path"), expected_input
        )
        change_path = _safe_plan_file(
            plan_dir, item.get("change_ledger_path"), expected_change
        )
        expected_files.update(
            {
                input_path.relative_to(plan_dir).as_posix(),
                change_path.relative_to(plan_dir).as_posix(),
            }
        )
        if (
            item.get("family") != candidate.family
            or not math.isclose(
                float(item.get("value")), candidate.value, rel_tol=0.0, abs_tol=1e-12
            )
            or _sha256(input_path) != str(item.get("input_sha256") or "")
            or _sha256(change_path)
            != str(item.get("change_ledger_sha256") or "")
        ):
            raise ValueError(f"Candidate inventory mismatch: {scenario_id}")
        change = _read_json(change_path)
        changes = change.get("changes")
        if (
            change.get("schema_version")
            != f"{protocol.SCHEMA_VERSION}.change_ledger"
            or change.get("scenario_id") != scenario_id
            or change.get("family") != candidate.family
            or change.get("changed_family_count") != 1
            or change.get("acute_incident_event_count") != 0
            or not isinstance(changes, list)
            or len(changes) != int(item.get("changed_row_count") or -1)
        ):
            raise ValueError(f"Candidate change ledger mismatch: {scenario_id}")
        execution_inputs = item.get("execution_inputs") or {}
        if any(
            str(execution_inputs.get(key) or "")
            for key in (
                "supplier_risk_events",
                "demand_perturbation",
                "control_schedule",
            )
        ):
            raise ValueError(f"Acute/control input present in candidate {scenario_id}")
        for path_key, hash_key in (
            ("graph", "graph_sha256"),
            ("supplier_floors", "supplier_floors_sha256"),
            ("factory_capacities", "factory_capacities_sha256"),
        ):
            path_text = str(execution_inputs.get(path_key) or "")
            expected_hash = str(execution_inputs.get(hash_key) or "")
            if not path_text:
                if path_key != "factory_capacities" or expected_hash:
                    raise ValueError(f"Missing execution input {path_key}: {scenario_id}")
                continue
            path = Path(path_text).resolve()
            if not path.is_file() or path.is_symlink() or _sha256(path) != expected_hash:
                raise ValueError(f"Execution input hash mismatch: {scenario_id}/{path_key}")
    if set(file_hashes) != expected_files:
        raise ValueError("Calibration plan disk inventory is not exact")
    design = protocol.read_csv_rows(plan_dir / "scenario_design.csv")
    if len(design) != 37 or design[0].get("scenario_id") != "baseline_nominal":
        raise ValueError("Scenario design does not contain baseline + 36 candidates")
    design_by_id = {str(row.get("scenario_id") or ""): row for row in design[1:]}
    if len(design_by_id) != 36 or set(design_by_id) != set(candidate_by_id):
        raise ValueError("Scenario design ids are missing or duplicated")
    for scenario_id, candidate in candidate_by_id.items():
        row = design_by_id[scenario_id]
        if (
            row.get("family") != candidate.family
            or _strict_int(row.get("severity_index"), "severity_index")
            != candidate.severity_index
            or row.get("input_sha256") != inventory[scenario_id]["input_sha256"]
            or protocol.truthy(row.get("acute_supplier_incident"))
            or _strict_int(row.get("changed_family_count"), "changed_family_count")
            != 1
        ):
            raise ValueError(f"Scenario design row mismatch: {scenario_id}")
    source_paths = manifest.get("source_paths") or {}
    reference_campaign = Path(str(source_paths.get("reference_campaign") or "")).resolve()
    graph = Path(str(source_paths.get("graph") or "")).resolve()
    engine = Path(str(source_paths.get("engine") or "")).resolve()
    profile = Path(str(source_paths.get("profile") or "")).resolve()
    fresh_reference = protocol.validate_reference(
        reference_campaign=reference_campaign,
        graph_path=graph,
        engine_path=engine,
        profile_path=profile,
    )
    if fresh_reference != manifest.get("reference_audit"):
        raise ValueError("Live reference inputs differ from the frozen plan audit")
    return ValidatedPlan(
        plan_dir=plan_dir,
        manifest=manifest,
        inventory=inventory,
        candidates=candidates,
        plan_artifact_sha256=digest,
        calibration_plan_sha256=_sha256(plan_dir / "calibration_plan.json"),
        reference_campaign=reference_campaign,
        graph=graph,
        engine=engine,
        profile=profile,
    )


def _campaign_signature(plan: ValidatedPlan, *, smoke_only: bool) -> str:
    return _stable_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "plan_signature": plan.manifest["plan_signature"],
            "plan_artifact_sha256": plan.plan_artifact_sha256,
            "runner_builder_sha256": _sha256(Path(__file__).resolve()),
            "protocol_builder_sha256": _sha256(Path(protocol.__file__).resolve()),
            "screening_seed": protocol.SCREENING_SEED,
            "confirmation_seeds": list(protocol.FINAL_CONFIRMATION_SEEDS),
            "seed_scheduling_policy": SEED_SCHEDULING_POLICY,
            "candidate_ids": [candidate.scenario_id for candidate in plan.candidates],
            "scope": "smoke_one_case_nonreusable" if smoke_only else "staged_full_36_then_15_then_30",
        }
    )


def _candidate(plan: ValidatedPlan, scenario_id: str) -> protocol.Candidate:
    for candidate in plan.candidates:
        if candidate.scenario_id == scenario_id:
            return candidate
    raise ValueError(f"Unknown candidate: {scenario_id}")


def _execution_inputs(
    plan: ValidatedPlan, scenario_id: str
) -> tuple[Path, Path, Path | None, dict[str, Any]]:
    item = plan.inventory[scenario_id]
    execution = dict(item["execution_inputs"])
    graph = Path(str(execution["graph"])).resolve()
    floors = Path(str(execution["supplier_floors"])).resolve()
    factory_text = str(execution.get("factory_capacities") or "")
    factory = Path(factory_text).resolve() if factory_text else None
    for path, hash_key in (
        (graph, "graph_sha256"),
        (floors, "supplier_floors_sha256"),
        (factory, "factory_capacities_sha256"),
    ):
        if path is None:
            continue
        if not path.is_file() or path.is_symlink() or _sha256(path) != execution[hash_key]:
            raise ValueError(f"Execution input changed: {scenario_id}/{hash_key}")
    return graph, floors, factory, execution


def build_engine_command(
    case: PlannedCase, plan: ValidatedPlan, case_dir: Path
) -> list[str]:
    graph, floors, factory, _ = _execution_inputs(plan, case.scenario_id)
    command = [
        sys.executable,
        str(plan.engine),
        "--input",
        str(graph),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(protocol.MEASURED_DAYS),
        "--seed",
        str(case.seed),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--common-random-numbers",
        "--supplier-neutral-floors-csv",
        str(floors),
    ]
    if factory is not None:
        command.extend(["--factory-nominal-capacities-csv", str(factory)])
    command.extend(campaign_core.engine_profile_args(plan.profile))
    command.extend(protocol.MANAGED_REFERENCE_PROTOCOL_ARGS)
    return command


def _policy_errors(
    summary: Mapping[str, Any],
    *,
    case: PlannedCase,
    graph: Path,
    floors: Path,
    factory: Path | None,
) -> list[str]:
    errors: list[str] = []
    policy = summary.get("policy") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    floor_test = policy.get("supplier_neutral_floor_test") or {}
    factory_test = policy.get("factory_nominal_capacity_test") or {}
    if summary.get("input_sha256") != _sha256(graph):
        errors.append("graph input hash mismatch")
    if int(summary.get("sim_days") or -1) != protocol.MEASURED_DAYS:
        errors.append("measured horizon mismatch")
    if str(summary.get("scenario_id") or "") != "scn:BASE":
        errors.append("engine scenario mismatch")
    if int(policy.get("seed") or -1) != case.seed:
        errors.append("seed mismatch")
    if not protocol.truthy(policy.get("common_random_numbers")):
        errors.append("common random numbers disabled")
    if protocol.truthy(policy.get("lot_trace_enabled")):
        errors.append("lot trace unexpectedly enabled")
    if int(warmup.get("physical_warmup_days") or -1) != protocol.WARMUP_DAYS:
        errors.append("warmup duration mismatch")
    if not str(warmup.get("core_state_sha256") or ""):
        errors.append("warmup state hash absent")
    if (
        protocol.truthy(supplier_risk.get("enabled"))
        or int(supplier_risk.get("event_count") or 0) != 0
        or supplier_risk.get("warnings")
    ):
        errors.append("acute supplier risk layer is not neutral")
    if protocol.truthy(state_risk.get("enabled")):
        errors.append("state-dependent supplier risk is enabled")
    if (
        not protocol.truthy(floor_test.get("enabled"))
        or Path(str(floor_test.get("floors_csv") or "")).resolve() != floors
        or floor_test.get("warnings")
    ):
        errors.append("supplier floor input not proven by engine summary")
    if factory is None:
        if protocol.truthy(factory_test.get("enabled")):
            errors.append("unexpected factory capacity override")
    elif (
        not protocol.truthy(factory_test.get("enabled"))
        or Path(str(factory_test.get("capacities_csv") or "")).resolve() != factory
        or int(factory_test.get("applied_processes") or 0) != 2
        or factory_test.get("warnings")
    ):
        errors.append("factory capacity override not proven by engine summary")
    return errors


def _validate_daily_service_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    indexed: set[tuple[str, int]] = set()
    for row in rows:
        if str(row.get("node_id") or "") != protocol.CLIENT_NODE_ID:
            continue
        product = str(row.get("item_id") or "").replace("item:", "")
        if product not in protocol.PRODUCTS:
            continue
        day = _strict_int(row.get("day"), "service day")
        key = (product, day)
        if key in indexed:
            raise ValueError(f"Duplicate product/day service row: {key}")
        indexed.add(key)
        for field in (
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
        ):
            value = protocol.finite_float(row.get(field))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"Invalid {field} in product/day service row: {key}")
        if protocol.finite_float(row.get("required_with_backlog_qty")) + 1e-9 < protocol.finite_float(
            row.get("demand_qty")
        ):
            raise ValueError(f"Required quantity below current demand: {key}")
    expected = {
        (product, day)
        for product in protocol.PRODUCTS
        for day in range(protocol.MEASURED_DAYS)
    }
    if indexed != expected:
        raise ValueError("Product/day service matrix is not exactly 2 x 720")


def execute_engine_case(
    case: PlannedCase, plan: ValidatedPlan, output_dir: Path
) -> dict[str, Any]:
    candidate = _candidate(plan, case.scenario_id)
    graph, floors, factory, execution = _execution_inputs(plan, case.scenario_id)
    case_dir = output_dir / "cases" / case.scenario_id / f"seed_{case.seed}"
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    summary_exists = summary_path.is_file()
    service_exists = service_path.is_file()
    if summary_exists != service_exists:
        raise RuntimeError(f"Partial engine case requires review: {case.key}")
    status = "reextracted" if summary_exists else "executed"
    command = build_engine_command(case, plan, case_dir)
    if status == "executed":
        if case_dir.exists() and any(case_dir.iterdir()):
            raise RuntimeError(f"Non-empty unregistered engine case: {case.key}")
        case_dir.mkdir(parents=True, exist_ok=True)
        log_path = case_dir / "calibration_engine.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{_utc_now()}] COMMAND {json.dumps(command)}\n")
            completed = subprocess.run(
                command,
                cwd=plan.engine.parents[3],
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failed for {case.key}; see {log_path}")
    summary = _read_json(summary_path)
    daily_rows = protocol.read_csv_rows(service_path)
    _validate_daily_service_rows(daily_rows)
    metrics = protocol.service_from_daily_rows(
        daily_rows, days=protocol.MEASURED_DAYS
    )
    errors = _policy_errors(
        summary,
        case=case,
        graph=graph,
        floors=floors,
        factory=factory,
    )
    for key in (
        "system_on_due_service",
        "minimum_product_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
    ):
        value = float(metrics[key])
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            errors.append(f"invalid service metric {key}")
    for product in protocol.PRODUCTS:
        if float(metrics[f"demand_qty_{product}"]) <= 0.0:
            errors.append(f"non-positive demand for {product}")
    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "case_key": case.key,
        "scenario_id": case.scenario_id,
        "family": candidate.family,
        "severity_index": candidate.severity_index,
        "parameter_value": candidate.value,
        "parameter_unit": candidate.unit,
        "seed": case.seed,
        "stage": case.stage,
        "status": status,
        "valid": not errors,
        "validation_errors": errors,
        "metrics": metrics,
        "candidate_input_sha256": plan.inventory[case.scenario_id]["input_sha256"],
        "execution_input_hashes": {
            key: execution[key]
            for key in (
                "graph_sha256",
                "supplier_floors_sha256",
                "factory_capacities_sha256",
            )
        },
        "summary_sha256": _sha256(summary_path),
        "service_daily_sha256": _sha256(service_path),
        "warmup_core_state_sha256": str(
            ((summary.get("policy") or {}).get("warmup_boundary_audit") or {}).get(
                "core_state_sha256"
            )
            or ""
        ),
        "command_sha256": _stable_sha256(command),
        "run_dir": str(case_dir.resolve()),
        "acute_incident_event_count": 0,
        "supplier_state_dependent_risks_enabled": False,
        "created_at_utc": _utc_now(),
    }
    unsigned = dict(evidence)
    evidence["evidence_signature"] = _stable_sha256(unsigned)
    if errors:
        raise RuntimeError(f"Invalid engine evidence {case.key}: {' | '.join(errors)}")
    return evidence


def _canonical_evidence_relative(case_key: str) -> Path:
    digest = hashlib.sha256(case_key.encode("utf-8")).hexdigest()[:20]
    return Path("ledger_cases") / f"{digest}.json"


def _validate_evidence(
    evidence: Mapping[str, Any], case: PlannedCase, plan: ValidatedPlan
) -> None:
    signature = str(evidence.get("evidence_signature") or "")
    unsigned = dict(evidence)
    unsigned.pop("evidence_signature", None)
    candidate = _candidate(plan, case.scenario_id)
    metrics = evidence.get("metrics") or {}
    if (
        evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("contract_revision") != CONTRACT_REVISION
        or not signature
        or _stable_sha256(unsigned) != signature
        or evidence.get("case_key") != case.key
        or evidence.get("scenario_id") != case.scenario_id
        or evidence.get("family") != candidate.family
        or evidence.get("seed") != case.seed
        or evidence.get("stage") != case.stage
        or evidence.get("valid") is not True
        or evidence.get("validation_errors") != []
        or evidence.get("acute_incident_event_count") != 0
        or evidence.get("supplier_state_dependent_risks_enabled") is not False
        or evidence.get("candidate_input_sha256")
        != plan.inventory[case.scenario_id]["input_sha256"]
    ):
        raise ValueError(f"Case evidence contract mismatch: {case.key}")
    for key in (
        "system_on_due_service",
        "minimum_product_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
    ):
        value = protocol.finite_float(metrics.get(key))
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"Invalid compact metric {case.key}/{key}")
    for product in protocol.PRODUCTS:
        if protocol.finite_float(metrics.get(f"demand_qty_{product}"), 0.0) <= 0.0:
            raise ValueError(f"Invalid demand denominator {case.key}/{product}")


def _new_ledger(signature: str) -> dict[str, Any]:
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "campaign_signature": signature,
        "case_files": {},
        "case_file_sha256": {},
        "updated_at_utc": _utc_now(),
    }


def _load_ledger(output_dir: Path, signature: str) -> dict[str, Any]:
    path = output_dir / LEDGER_FILE
    evidence_dir = output_dir / "ledger_cases"
    if not path.is_file():
        if evidence_dir.exists() and any(evidence_dir.iterdir()):
            raise ValueError("Evidence files exist without a ledger")
        return _new_ledger(signature)
    ledger = _read_json(path)
    if (
        ledger.get("schema_version") != LEDGER_SCHEMA_VERSION
        or ledger.get("campaign_signature") != signature
        or not isinstance(ledger.get("case_files"), dict)
        or not isinstance(ledger.get("case_file_sha256"), dict)
        or set(ledger["case_files"]) != set(ledger["case_file_sha256"])
    ):
        raise ValueError("Execution ledger signature/inventory mismatch")
    disk_files = {
        path.relative_to(output_dir).as_posix()
        for path in evidence_dir.rglob("*")
        if path.is_file()
    } if evidence_dir.exists() else set()
    if disk_files != set(ledger["case_files"].values()):
        raise ValueError("Execution ledger disk inventory is not exact")
    for case_key, relative_text in ledger["case_files"].items():
        relative = Path(str(relative_text))
        canonical = _canonical_evidence_relative(str(case_key))
        path = output_dir / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != canonical.as_posix()
            or path.is_symlink()
            or not path.is_file()
            or path.resolve() != (output_dir / canonical).resolve()
            or _sha256(path) != ledger["case_file_sha256"][case_key]
            or _read_json(path).get("case_key") != case_key
        ):
            raise ValueError(f"Execution ledger evidence mismatch: {case_key}")
    return ledger


def _load_evidence_rows(output_dir: Path, ledger: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(case_key): _read_json(output_dir / str(relative))
        for case_key, relative in (ledger.get("case_files") or {}).items()
    }


def _validate_all_ledger_evidence(
    evidence_by_key: Mapping[str, Mapping[str, Any]],
    plan: ValidatedPlan,
    *,
    smoke_only: bool,
) -> None:
    allowed_stages = {"smoke"} if smoke_only else {"screening", "confirmation"}
    for case_key, evidence in evidence_by_key.items():
        stage = str(evidence.get("stage") or "")
        seed = _strict_int(evidence.get("seed"), "evidence seed")
        if stage not in allowed_stages:
            raise ValueError(f"Unexpected evidence stage: {case_key}/{stage}")
        if stage in {"smoke", "screening"}:
            if seed != protocol.SCREENING_SEED:
                raise ValueError(f"Unexpected screening seed: {case_key}")
        elif seed not in protocol.FINAL_CONFIRMATION_SEEDS:
            raise ValueError(f"Unexpected confirmation seed: {case_key}")
        case = PlannedCase(str(evidence.get("scenario_id") or ""), seed, stage)
        if case.key != case_key:
            raise ValueError(f"Evidence key does not match its payload: {case_key}")
        _validate_evidence(evidence, case, plan)


def _persist_evidence(
    output_dir: Path,
    ledger: dict[str, Any],
    evidence: Mapping[str, Any],
) -> None:
    case_key = str(evidence["case_key"])
    relative = _canonical_evidence_relative(case_key)
    path = output_dir / relative
    if case_key in ledger["case_files"]:
        if (
            ledger["case_files"][case_key] != relative.as_posix()
            or not path.is_file()
            or _sha256(path) != ledger["case_file_sha256"][case_key]
        ):
            raise ValueError(f"Existing evidence changed: {case_key}")
        return
    _write_json(path, evidence)
    ledger["case_files"][case_key] = relative.as_posix()
    ledger["case_file_sha256"][case_key] = _sha256(path)
    ledger["updated_at_utc"] = _utc_now()
    _write_json(output_dir / LEDGER_FILE, ledger)


def _metric_row(evidence: Mapping[str, Any]) -> dict[str, Any]:
    metrics = dict(evidence["metrics"])
    return {
        "scenario_id": evidence["scenario_id"],
        "family": evidence["family"],
        "severity_index": evidence["severity_index"],
        "parameter_value": evidence["parameter_value"],
        "parameter_unit": evidence["parameter_unit"],
        "seed": evidence["seed"],
        "stage": evidence["stage"],
        "valid": evidence["valid"],
        **{key: metrics[key] for key in sorted(metrics)},
        "candidate_input_sha256": evidence["candidate_input_sha256"],
        "warmup_core_state_sha256": evidence["warmup_core_state_sha256"],
        "case_evidence_signature": evidence["evidence_signature"],
    }


def _screening_rows(evidence_by_key: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        _metric_row(evidence)
        for evidence in evidence_by_key.values()
        if evidence.get("stage") == "screening"
    ]
    return sorted(rows, key=lambda row: str(row["scenario_id"]))


def _confirmation_rows(
    evidence_by_key: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows = [
        _metric_row(evidence)
        for evidence in evidence_by_key.values()
        if evidence.get("stage") == "confirmation"
    ]
    return sorted(rows, key=lambda row: (str(row["scenario_id"]), int(row["seed"])))


def _freeze_selection(output_dir: Path, screening_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(screening_rows) != 36:
        raise ValueError("Selection requires the exact 36-row screening matrix")
    base = protocol.select_target_candidates(screening_rows)
    deterministic = {
        **base,
        "contract_revision": CONTRACT_REVISION,
        "screening_seed": protocol.SCREENING_SEED,
        "screening_row_count": 36,
        "screening_metrics_sha256": _sha256(output_dir / SCREENING_METRICS_FILE),
        "selection_is_confirmation_result": False,
        "final_regime_claim_allowed": False,
    }
    path = output_dir / SELECTION_FILE
    if path.is_file():
        existing = _read_json(path)
        existing_unsigned = dict(existing)
        existing_signature = str(existing_unsigned.pop("selection_signature", ""))
        existing_deterministic = dict(existing_unsigned)
        existing_deterministic.pop("selection_frozen_at_utc", None)
        if (
            not existing_signature
            or _stable_sha256(existing_unsigned) != existing_signature
            or existing_deterministic != deterministic
        ):
            raise ValueError("Frozen screening selection changed")
        return existing
    payload = {**deterministic, "selection_frozen_at_utc": _utc_now()}
    unsigned = dict(payload)
    payload["selection_signature"] = _stable_sha256(unsigned)
    _write_json(path, payload)
    return payload


def _reference_baseline_rows(plan: ValidatedPlan) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in protocol.baseline_rows(plan.reference_campaign):
        demand = {
            product: protocol.finite_float(source.get(f"demand_qty_{product}"), 0.0)
            for product in protocol.PRODUCTS
        }
        on_due = {
            product: protocol.finite_float(
                source.get(f"on_due_volume_proxy_{product}"), math.nan
            )
            for product in protocol.PRODUCTS
        }
        denominator = sum(demand.values())
        numerator = sum(demand[product] * on_due[product] for product in protocol.PRODUCTS)
        rows.append(
            {
                "scenario_id": "baseline_nominal",
                "seed": _strict_int(source.get("seed"), "baseline seed"),
                "valid": protocol.truthy(source.get("valid")),
                "system_on_due_service": numerator / denominator,
                "on_due_service_268091": on_due["268091"],
                "on_due_service_268967": on_due["268967"],
                "demand_qty_268091": demand["268091"],
                "demand_qty_268967": demand["268967"],
                "backlog_qty_days_268091": protocol.finite_float(
                    source.get("backlog_qty_days_268091"), 0.0
                ),
                "backlog_qty_days_268967": protocol.finite_float(
                    source.get("backlog_qty_days_268967"), 0.0
                ),
                "uom": "UN",
            }
        )
    if len(rows) != 31 or {row["seed"] for row in rows} != {
        protocol.SCREENING_SEED,
        *protocol.FINAL_CONFIRMATION_SEEDS,
    }:
        raise ValueError("Reference baseline projection is incomplete")
    return sorted(rows, key=lambda row: int(row["seed"]))


def _summary_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_scenario: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_scenario.setdefault(str(row["scenario_id"]), []).append(row)
    output: list[dict[str, Any]] = []
    metric_names = (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
        "minimum_product_on_due_service",
        "backlog_qty_days_268091",
        "backlog_qty_days_268967",
        "ending_backlog_qty_268091",
        "ending_backlog_qty_268967",
    )
    for scenario_id, group in sorted(by_scenario.items()):
        row: dict[str, Any] = {
            "scenario_id": scenario_id,
            "family": group[0]["family"],
            "parameter_value": group[0]["parameter_value"],
            "parameter_unit": group[0]["parameter_unit"],
            "seed_count": len(group),
            "seed_ids": "|".join(str(item["seed"]) for item in sorted(group, key=lambda item: int(item["seed"]))),
            "preliminary_not_final": len(group) < len(protocol.FINAL_CONFIRMATION_SEEDS),
            "confidence_interval_reported": False,
            "business_materiality_threshold_validated": False,
        }
        for metric in metric_names:
            values = [float(item[metric]) for item in group]
            row[f"{metric}_mean"] = fmean(values)
            row[f"{metric}_std"] = pstdev(values)
            row[f"{metric}_min"] = min(values)
            row[f"{metric}_max"] = max(values)
        output.append(row)
    return output


def _case_map(
    plan: ValidatedPlan,
    *,
    scenario_ids: Sequence[str],
    seeds: Sequence[int],
    stage: str,
) -> dict[str, PlannedCase]:
    result: dict[str, PlannedCase] = {}
    known = {candidate.scenario_id for candidate in plan.candidates}
    for scenario_id in scenario_ids:
        if scenario_id not in known:
            raise ValueError(f"Selected candidate is outside the plan: {scenario_id}")
        for seed in seeds:
            case = PlannedCase(scenario_id, int(seed), stage)
            if case.key in result:
                raise ValueError(f"Duplicate planned case: {case.key}")
            result[case.key] = case
    return result


def _write_checkpoint(
    *,
    output_dir: Path,
    signature: str,
    selection: Mapping[str, Any],
    ledger: Mapping[str, Any],
    expected_cases: Mapping[str, PlannedCase],
) -> dict[str, Any]:
    evidence = {
        key: {
            "relative_path": ledger["case_files"][key],
            "sha256": ledger["case_file_sha256"][key],
        }
        for key in sorted(expected_cases)
    }
    deterministic: dict[str, Any] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "status": "paused_preliminary_15_of_30",
        "campaign_signature": signature,
        "selection_signature": selection["selection_signature"],
        "selected_scenario_ids": selection["selected_scenario_ids"],
        "completed_seed_ids": list(protocol.PRELIMINARY_CONFIRMATION_SEEDS),
        "signed_final_seed_ids": list(protocol.FINAL_CONFIRMATION_SEEDS),
        "seed_scheduling_policy": SEED_SCHEDULING_POLICY,
        "screening_case_count": 36,
        "confirmation_case_count": len(selection["selected_scenario_ids"]) * 15,
        "case_evidence_file_sha256": evidence,
        "preliminary_not_final": True,
        "selection_is_screening_only": True,
        "final_regime_claim_allowed": False,
        "confirmatory_release_allowed": False,
        "action_promotion_allowed": False,
    }
    path = output_dir / CHECKPOINT_FILE
    if path.is_file():
        existing = _read_json(path)
        existing_unsigned = dict(existing)
        existing_signature = str(existing_unsigned.pop("checkpoint_signature", ""))
        existing_deterministic = dict(existing_unsigned)
        existing_deterministic.pop("created_at_utc", None)
        if (
            not existing_signature
            or _stable_sha256(existing_unsigned) != existing_signature
            or existing_deterministic != deterministic
        ):
            raise ValueError(
                "Preliminary checkpoint already exists with different content"
            )
        return existing
    payload = {**deterministic, "created_at_utc": _utc_now()}
    unsigned = dict(payload)
    payload["checkpoint_signature"] = _stable_sha256(unsigned)
    _write_json(path, payload)
    return payload


def _validate_checkpoint(
    output_dir: Path,
    signature: str,
    ledger: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> dict[str, Any] | None:
    path = output_dir / CHECKPOINT_FILE
    if not path.is_file():
        return None
    payload = _read_json(path)
    unsigned = dict(payload)
    checkpoint_signature = str(unsigned.pop("checkpoint_signature", ""))
    expected_count = 36 + len(selection["selected_scenario_ids"]) * 15
    evidence = payload.get("case_evidence_file_sha256") or {}
    if (
        payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION
        or payload.get("contract_revision") != CONTRACT_REVISION
        or not checkpoint_signature
        or _stable_sha256(unsigned) != checkpoint_signature
        or payload.get("campaign_signature") != signature
        or payload.get("selection_signature") != selection["selection_signature"]
        or payload.get("selected_scenario_ids") != selection["selected_scenario_ids"]
        or payload.get("completed_seed_ids") != list(protocol.PRELIMINARY_CONFIRMATION_SEEDS)
        or payload.get("signed_final_seed_ids") != list(protocol.FINAL_CONFIRMATION_SEEDS)
        or len(evidence) != expected_count
        or payload.get("preliminary_not_final") is not True
        or payload.get("final_regime_claim_allowed") is not False
        or payload.get("confirmatory_release_allowed") is not False
        or payload.get("action_promotion_allowed") is not False
    ):
        raise ValueError("Preliminary checkpoint contract mismatch")
    for key, item in evidence.items():
        if (
            ledger["case_files"].get(key) != item.get("relative_path")
            or ledger["case_file_sha256"].get(key) != item.get("sha256")
        ):
            raise ValueError("Preliminary checkpoint is not an exact ledger subset")
    return payload


@contextmanager
def _exclusive_lock(output_dir: Path) -> Iterable[None]:
    path = output_dir / LOCK_FILE
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Calibration runner lock exists; inspect before manual recovery: {path}"
        ) from exc
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if path.is_file():
            path.unlink()


def _base_manifest(
    *,
    plan: ValidatedPlan,
    signature: str,
    output_dir: Path,
    workers: int,
    retention: str,
    custom_executor_used: bool,
    smoke_only: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "status": "running",
        "campaign_signature": signature,
        "runner_builder_sha256": _sha256(Path(__file__).resolve()),
        "protocol_builder_sha256": _sha256(Path(protocol.__file__).resolve()),
        "plan_artifact_sha256": plan.plan_artifact_sha256,
        "calibration_plan_sha256": plan.calibration_plan_sha256,
        "plan_signature": plan.manifest["plan_signature"],
        "output_dir": str(output_dir),
        "workers": workers,
        "retention": retention,
        "executor_contract": (
            "custom_executor_nonpublishable"
            if custom_executor_used
            else "builtin_execute_engine_case"
        ),
        "custom_executor_used": custom_executor_used,
        "smoke_only": smoke_only,
        "screening_seed": protocol.SCREENING_SEED,
        "preliminary_seed_ids": list(protocol.PRELIMINARY_CONFIRMATION_SEEDS),
        "final_seed_ids": list(protocol.FINAL_CONFIRMATION_SEEDS),
        "seed_scheduling_policy": SEED_SCHEDULING_POLICY,
        "acute_supplier_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "selection_interpolation_allowed": False,
        "simulation_hypothesis_not_observed_performance": True,
        "final_regime_claim_allowed": False,
        "confirmatory_release_allowed": False,
        "action_promotion_allowed": False,
        "started_at_utc": _utc_now(),
    }


def run_calibration(
    *,
    plan_dir: Path,
    output_dir: Path,
    mode: str,
    workers: int = 2,
    retention: str = "summary",
    checkpoint_after_repetitions: int | None = None,
    case_executor: CaseExecutor | None = None,
) -> dict[str, Any]:
    if mode not in {"validate", "smoke", "screening", "confirmation"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if retention != "summary":
        raise ValueError("Only summary retention is allowed")
    if checkpoint_after_repetitions not in {None, 15}:
        raise ValueError("Checkpoint must be omitted or exactly 15")
    if checkpoint_after_repetitions is not None and mode != "confirmation":
        raise ValueError("Checkpoint is allowed only in confirmation mode")
    plan = validate_plan_artifact(plan_dir)
    if mode == "validate":
        return {
            "status": "valid",
            "plan_signature": plan.manifest["plan_signature"],
            "plan_artifact_sha256": plan.plan_artifact_sha256,
            "candidate_count": len(plan.candidates),
        }
    smoke_only = mode == "smoke"
    signature = _campaign_signature(plan, smoke_only=smoke_only)
    output_dir = output_dir.resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Output path is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    custom_executor_used = case_executor is not None
    executor = case_executor or execute_engine_case
    with _exclusive_lock(output_dir):
        manifest_path = output_dir / RUNNER_MANIFEST
        manifest = _base_manifest(
            plan=plan,
            signature=signature,
            output_dir=output_dir,
            workers=workers,
            retention=retention,
            custom_executor_used=custom_executor_used,
            smoke_only=smoke_only,
        )
        if manifest_path.is_file():
            previous = _read_json(manifest_path)
            if previous.get("campaign_signature") != signature:
                raise ValueError("Existing output belongs to another campaign signature")
            if bool(previous.get("smoke_only")) != smoke_only:
                raise ValueError("Smoke output cannot be reused by the staged campaign")
            if bool(previous.get("custom_executor_used")) != custom_executor_used:
                raise ValueError("Executor contract changed within one output directory")
            manifest["first_started_at_utc"] = previous.get(
                "first_started_at_utc", previous.get("started_at_utc")
            )
        else:
            if any(output_dir.iterdir()):
                unexpected = [path.name for path in output_dir.iterdir()]
                if unexpected != [LOCK_FILE]:
                    raise ValueError("Refusing unregistered non-empty output directory")
            manifest["first_started_at_utc"] = manifest["started_at_utc"]
        _write_json(manifest_path, manifest)
        try:
            ledger = _load_ledger(output_dir, signature)
            evidence_by_key = _load_evidence_rows(output_dir, ledger)
            _validate_all_ledger_evidence(
                evidence_by_key, plan, smoke_only=smoke_only
            )
            reference_rows = _reference_baseline_rows(plan)
            reference_path = output_dir / REFERENCE_METRICS_FILE
            if reference_path.is_file():
                actual_rows = protocol.read_csv_rows(reference_path)
                expected_rows = [
                    {key: str(value) for key, value in row.items()}
                    for row in reference_rows
                ]
                if actual_rows != expected_rows:
                    raise ValueError("Reference baseline projection changed")
            else:
                _write_csv(reference_path, reference_rows)
            if smoke_only:
                scenario_ids = [plan.candidates[0].scenario_id]
                seeds = [protocol.SCREENING_SEED]
                stage = "smoke"
            elif mode == "screening":
                scenario_ids = [candidate.scenario_id for candidate in plan.candidates]
                seeds = [protocol.SCREENING_SEED]
                stage = "screening"
            else:
                screening = _screening_rows(evidence_by_key)
                if len(screening) != 36:
                    raise ValueError(
                        "Confirmation requires a complete 36-row screening in this output"
                    )
                _write_csv(output_dir / SCREENING_METRICS_FILE, screening)
                selection = _freeze_selection(output_dir, screening)
                checkpoint = _validate_checkpoint(
                    output_dir, signature, ledger, selection
                )
                if checkpoint_after_repetitions is None and checkpoint is None:
                    raise ValueError(
                        "Final 30-seed completion requires the signed 15-seed checkpoint"
                    )
                if checkpoint_after_repetitions == 15 and any(
                    evidence.get("stage") == "confirmation"
                    and int(evidence.get("seed") or -1)
                    not in protocol.PRELIMINARY_CONFIRMATION_SEEDS
                    for evidence in evidence_by_key.values()
                ):
                    raise ValueError(
                        "Preliminary checkpoint cannot coexist with future-seed evidence"
                    )
                scenario_ids = list(selection["selected_scenario_ids"])
                seeds = list(
                    protocol.PRELIMINARY_CONFIRMATION_SEEDS
                    if checkpoint_after_repetitions == 15
                    else protocol.FINAL_CONFIRMATION_SEEDS
                )
                stage = "confirmation"
            planned = _case_map(
                plan,
                scenario_ids=scenario_ids,
                seeds=seeds,
                stage=stage,
            )
            missing: list[PlannedCase] = []
            for key, case in planned.items():
                existing = evidence_by_key.get(key)
                if existing is None:
                    missing.append(case)
                else:
                    _validate_evidence(existing, case, plan)
            manifest.update(
                {
                    "invocation_mode": mode,
                    "checkpoint_after_repetitions": checkpoint_after_repetitions,
                    "planned_case_count_this_scope": len(planned),
                    "reused_valid_case_count_this_scope": len(planned) - len(missing),
                    "missing_case_count_at_invocation_start": len(missing),
                }
            )
            _write_json(manifest_path, manifest)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(executor, case, plan, output_dir): case
                    for case in missing
                }
                for future in as_completed(futures):
                    case = futures[future]
                    evidence = future.result()
                    _validate_evidence(evidence, case, plan)
                    _persist_evidence(output_dir, ledger, evidence)
                    evidence_by_key[case.key] = dict(evidence)
                    if retention == "summary" and not custom_executor_used:
                        campaign_core.prune_case_artifacts(
                            Path(str(evidence["run_dir"]))
                        )
                    print(
                        f"[{stage.upper()}] {case.scenario_id} seed={case.seed} "
                        f"service={float(evidence['metrics']['system_on_due_service']):.4%}",
                        flush=True,
                    )
            for key, case in planned.items():
                evidence = evidence_by_key.get(key)
                if evidence is None:
                    raise RuntimeError(f"Missing evidence after execution: {key}")
                _validate_evidence(evidence, case, plan)
            if smoke_only:
                smoke_rows = [_metric_row(evidence_by_key[key]) for key in sorted(planned)]
                _write_csv(output_dir / "smoke_metrics.csv", smoke_rows)
                manifest.update(
                    {
                        "status": "smoke_complete_nonreusable",
                        "completed_case_count": 1,
                        "selection_frozen": False,
                        "preliminary_not_final": True,
                    }
                )
            else:
                screening = _screening_rows(evidence_by_key)
                if screening:
                    _write_csv(output_dir / SCREENING_METRICS_FILE, screening)
                if mode == "screening":
                    selection = _freeze_selection(output_dir, screening)
                    manifest.update(
                        {
                            "status": "screening_complete_selection_frozen",
                            "screening_case_count": len(screening),
                            "selection_frozen": True,
                            "selection_signature": selection["selection_signature"],
                            "selected_scenario_ids": selection["selected_scenario_ids"],
                            "selected_scenario_count": selection["selected_scenario_count"],
                            "preliminary_not_final": True,
                        }
                    )
                else:
                    confirmation = _confirmation_rows(evidence_by_key)
                    selected_set = set(selection["selected_scenario_ids"])
                    requested_seed_set = set(seeds)
                    scoped_confirmation = [
                        row
                        for row in confirmation
                        if row["scenario_id"] in selected_set
                        and int(row["seed"]) in requested_seed_set
                    ]
                    expected_count = len(selected_set) * len(requested_seed_set)
                    if len(scoped_confirmation) != expected_count:
                        raise RuntimeError("Confirmation matrix is incomplete")
                    _write_csv(output_dir / CONFIRMATION_METRICS_FILE, confirmation)
                    _write_csv(
                        output_dir / CONFIRMATION_SUMMARY_FILE,
                        _summary_rows(scoped_confirmation),
                    )
                    if checkpoint_after_repetitions == 15:
                        screening_cases = _case_map(
                            plan,
                            scenario_ids=[candidate.scenario_id for candidate in plan.candidates],
                            seeds=[protocol.SCREENING_SEED],
                            stage="screening",
                        )
                        expected_checkpoint_cases = {
                            **screening_cases,
                            **planned,
                        }
                        checkpoint = _write_checkpoint(
                            output_dir=output_dir,
                            signature=signature,
                            selection=selection,
                            ledger=ledger,
                            expected_cases=expected_checkpoint_cases,
                        )
                        manifest.update(
                            {
                                "status": "paused_preliminary_15_of_30",
                                "completed_confirmation_seed_ids": list(seeds),
                                "confirmation_case_count": expected_count,
                                "checkpoint_signature": checkpoint["checkpoint_signature"],
                                "checkpoint_manifest_sha256": _sha256(
                                    output_dir / CHECKPOINT_FILE
                                ),
                                "preliminary_not_final": True,
                            }
                        )
                    else:
                        checkpoint = _validate_checkpoint(
                            output_dir, signature, ledger, selection
                        )
                        manifest.update(
                            {
                                "status": "complete_30_of_30",
                                "completed_confirmation_seed_ids": list(seeds),
                                "confirmation_case_count": expected_count,
                                "checkpoint_history_present": checkpoint is not None,
                                "checkpoint_manifest_sha256": (
                                    _sha256(output_dir / CHECKPOINT_FILE)
                                    if checkpoint is not None
                                    else ""
                                ),
                                "preliminary_not_final": False,
                                "final_regime_claim_allowed": False,
                                "calibration_characterization_complete": (
                                    not custom_executor_used
                                ),
                            }
                        )
            manifest.update(
                {
                    "completed_at_utc": _utc_now(),
                    "ledger_case_count": len(ledger["case_files"]),
                    "execution_ledger_sha256": _sha256(output_dir / LEDGER_FILE),
                    "reference_baseline_metrics_sha256": _sha256(reference_path),
                    "runner_source_unchanged_during_invocation": (
                        manifest["runner_builder_sha256"]
                        == _sha256(Path(__file__).resolve())
                    ),
                    "confirmatory_release_allowed": False,
                    "action_promotion_allowed": False,
                }
            )
            _write_json(manifest_path, manifest)
            return manifest
        except Exception as exc:
            manifest.update(
                {
                    "status": "failed",
                    "failed_at_utc": _utc_now(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "confirmatory_release_allowed": False,
                    "action_promotion_allowed": False,
                }
            )
            _write_json(manifest_path, manifest)
            raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("validate", "smoke", "screening", "confirmation"),
        default="validate",
    )
    parser.add_argument("--plan-dir", type=Path, default=protocol.DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retention", choices=("summary",), default="summary")
    parser.add_argument("--checkpoint-after-repetitions", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode != "validate" and args.output_dir is None:
        raise ValueError("--output-dir is required for execution modes")
    result = run_calibration(
        plan_dir=args.plan_dir,
        output_dir=(args.output_dir or Path.cwd()),
        mode=args.mode,
        workers=args.workers,
        retention=args.retention,
        checkpoint_after_repetitions=args.checkpoint_after_repetitions,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
