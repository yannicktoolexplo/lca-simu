#!/usr/bin/env python3
"""Fresh 3 x 30 holdout protocol for a successful V6 development selection.

This is a separate additive protocol.  Planning is impossible unless the V6
development result is complete, signed, publishable and selected.  The chosen
three states are copied into an immutable holdout plan before any reserved seed
is opened.  The module never tunes or replaces a selected state.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v6 as development_v6,
)
SCHEMA_VERSION = "etudecas.multiseed_operating_point_holdout.v6"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.development_authorization"
HOLDOUT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.holdout_result"

EXPECTED_HOLDOUT_SEEDS = tuple(development_v6.EXPECTED_HOLDOUT_SEEDS)
TARGETS = development_v6.TARGETS
MIN_ORDERED_SEEDS = development_v6.MIN_ORDERED_SEEDS
SERVICE_DAYS = development_v6.SERVICE_DAYS
INCIDENT_DESIGN_SEED = v5.INCIDENT_DESIGN_SEED
EXPECTED_HOLDOUT_CASES = 3 * len(EXPECTED_HOLDOUT_SEEDS)

OFFICIAL_EXECUTION_MODE = "official_v6_fresh_holdout"
TEST_ONLY_EXECUTION_MODE = "test_only_v6_fresh_holdout_injected_executor"
SOURCE_SUCCESS_STATUS = development_v6.SUCCESS_STATUS
ACCEPTED_HOLDOUT_STATUS = "holdout_validated_30_fresh_reserved_seeds"
REJECTED_HOLDOUT_STATUS = "holdout_rejected_no_retuning"

DEFAULT_ARTIFACT_ROOT = development_v6.DEFAULT_ARTIFACT_ROOT
DEFAULT_DEVELOPMENT_PLAN = development_v6.DEFAULT_PLAN_OUTPUT
DEFAULT_DEVELOPMENT_RUN = development_v6.DEFAULT_RUN_OUTPUT
DEFAULT_PLAN_OUTPUT = DEFAULT_ARTIFACT_ROOT / "supplier_v6_fresh_holdout_plan_20260905"
DEFAULT_RUN_OUTPUT = DEFAULT_ARTIFACT_ROOT / "supplier_v6_fresh_holdout_run_20260905"

Candidate = v4.Candidate
Executor = Callable[..., Mapping[str, Any]]


class V6HoldoutError(ValueError):
    """The separate V6 holdout contract is incomplete or inconsistent."""


@dataclass(frozen=True)
class ValidatedPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    candidates: tuple[Candidate, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    return v4.stable_sha256(payload)


def sha256_file(path: Path) -> str:
    return v4.sha256_file(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V6HoldoutError(f"Invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise V6HoldoutError(f"JSON artifact is not an object: {path}")
    return payload


def _read_json_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    """Parse and hash the exact same bytes to close authorization TOCTOU gaps."""

    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V6HoldoutError(f"Unreadable authorization JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V6HoldoutError(f"Authorization JSON object expected: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v4._write_json(path, payload)  # noqa: SLF001


def _verify_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise V6HoldoutError(f"Invalid {label} signature")
    return signature


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _candidate_payload(candidate: Candidate) -> dict[str, Any]:
    return {
        "key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "offset_days_268091": candidate.offset_days_268091,
        "offset_days_268967": candidate.offset_days_268967,
        "evidence_mode": candidate.evidence_mode,
        "source_operating_point_id": candidate.source_operating_point_id,
    }


def _assert_source_holdout_unseen(run_dir: Path) -> None:
    forbidden = (
        run_dir / "evidence" / "holdout",
        run_dir / "shipment_traces" / "holdout",
        run_dir / "engine_attempts" / "holdout",
        run_dir / "holdout_progress.json",
        run_dir / "holdout_result.json",
    )
    if any(path.exists() for path in forbidden):
        raise V6HoldoutError("V6 development source has exposed holdout material")


def _load_development_source(
    plan_dir: Path, run_dir: Path, *, allow_test_source: bool
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = development_v6.validate_plan(
        plan_dir.resolve(),
        verify_runtime_dependencies=not allow_test_source,
        allow_test_source=allow_test_source,
    )
    run_dir = run_dir.resolve()
    _assert_source_holdout_unseen(run_dir)
    mode = development_v6._registered_execution_mode(plan, run_dir)  # noqa: SLF001
    if not allow_test_source and mode != development_v6.OFFICIAL_EXECUTION_MODE:
        raise V6HoldoutError("Only an official V6 development may authorize holdout")
    expected_run = development_v6._run_manifest(plan, mode)  # noqa: SLF001
    run_manifest = _read_json(run_dir / "run_manifest.json")
    if run_manifest != expected_run:
        raise V6HoldoutError("V6 development run registration changed")

    jobs = development_v6._jobs(plan)  # noqa: SLF001
    evidence: dict[tuple[str, int], dict[str, Any]] = {}
    for candidate, seed in jobs:
        path = development_v6._evidence_path(  # noqa: SLF001
            run_dir, candidate.key, seed
        )
        if not path.is_file():
            raise V6HoldoutError("V6 development evidence matrix is incomplete")
        payload = development_v6._validate_evidence(  # noqa: SLF001
            _read_json(path),
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
            mode=mode,
        )
        evidence[(candidate.key, seed)] = payload
    progress = _read_json(run_dir / "development_progress.json")
    development_v6._verify_signature(  # noqa: SLF001
        progress, "progress_signature", "V6 development progress"
    )
    if (
        progress.get("schema_version")
        != f"{development_v6.SCHEMA_VERSION}.development.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("stage") != "development"
        or progress.get("status") != "complete"
        or progress.get("completed_case_count")
        != development_v6.EXPECTED_DEVELOPMENT_CASES
        or progress.get("expected_case_count")
        != development_v6.EXPECTED_DEVELOPMENT_CASES
        or progress.get("execution_mode") != mode
        or progress.get("publishable")
        is not (mode == development_v6.OFFICIAL_EXECUTION_MODE)
        or progress.get("error")
    ):
        raise V6HoldoutError("V6 development is not terminal and complete")

    selection_path = run_dir / "development_selection.json"
    selection = _read_json(selection_path)
    development_v6._verify_signature(  # noqa: SLF001
        selection, "selection_signature", "V6 development selection"
    )
    rebuilt = development_v6._build_development_selection(  # noqa: SLF001
        plan, evidence, execution_mode=mode
    )
    if selection != rebuilt:
        raise V6HoldoutError("V6 development selection is not reproducible")
    if (
        selection.get("status") != SOURCE_SUCCESS_STATUS
        or selection.get("holdout_cases_read") != 0
        or selection.get("holdout_execution_supported_by_this_module") is not False
        or selection.get("retuning_after_development") is not False
        or selection.get("publishable") is not (mode == development_v6.OFFICIAL_EXECUTION_MODE)
        or set(selection.get("selected_candidate_keys") or {}) != set(TARGETS)
    ):
        raise V6HoldoutError("V6 development did not authorize a separate holdout")
    # Refuse a development/holdout race that began while the 150 proofs were
    # being reopened.  This check is intentionally the final source read.
    _assert_source_holdout_unseen(run_dir)
    return plan, run_manifest, selection, progress


def _protected_development_sources(
    development_plan: Any, development_run_dir: Path
) -> tuple[Path, ...]:
    """Return every direct and transitive immutable source root inherited by V6."""

    v5_source = development_plan.manifest["v5_no_go_source"]
    upstream = development_plan.manifest["source"]
    return (
        development_plan.plan_dir,
        development_run_dir.resolve(),
        Path(v5_source["plan_dir"]).resolve(),
        Path(v5_source["run_dir"]).resolve(),
        Path(v5_source["holdout_non_use_audit"]["sidecar_root"]).resolve(),
        Path(upstream["campaign_manifest"]["path"]).resolve().parent,
        Path(upstream["v3_plan"]["path"]).resolve().parent,
    )


def _protected_holdout_sources(
    plan: ValidatedPlan, *, allow_test_source: bool
) -> tuple[Path, ...]:
    source = plan.manifest["v6_development_source"]
    development_plan = development_v6.validate_plan(
        Path(source["plan_dir"]),
        verify_runtime_dependencies=not allow_test_source,
        allow_test_source=allow_test_source,
    )
    return (
        plan.plan_dir,
        *_protected_development_sources(
            development_plan, Path(source["run_dir"])
        ),
    )


def _authorization_payload(
    *, plan_signature: str, source: Mapping[str, Any], execution_mode: str
) -> dict[str, Any]:
    unsigned = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "plan_signature": plan_signature,
        "source_v6_selection_signature": source["selection_signature"],
        "status": "development_selected_pending_fresh_holdout",
        "selected_candidate_keys": copy.deepcopy(source["selected_candidate_keys"]),
        "holdout_seeds_sealed_and_unread": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "retuning_after_development": False,
    }
    return {**unsigned, "selection_signature": stable_sha256(unsigned)}


def _holdout_contract() -> dict[str, Any]:
    source = copy.deepcopy(v5._holdout_contract())  # noqa: SLF001
    source.update(
        {
            "status_before_holdout": "fresh_reserved_sealed_unread",
            "seeds": list(EXPECTED_HOLDOUT_SEEDS),
            "state_count": 3,
            "case_count": EXPECTED_HOLDOUT_CASES,
            "selection_locked_before_first_holdout_read": True,
            "retuning_after_holdout": False,
            "freshness_basis": (
                "pre-registered cohort carried through V5 no-go and V6 development "
                "with signed zero-read checks before this separate plan"
            ),
            "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
        }
    )
    return source


def _execution_contract(source_plan: Any) -> dict[str, Any]:
    execution = copy.deepcopy(source_plan.manifest["execution_contract"])
    execution.update(
        {
            "stage": "fresh_holdout_only",
            "holdout_engine_runs": EXPECTED_HOLDOUT_CASES,
            "development_engine_runs": 0,
            "selected_states_locked": True,
            "retuning_supported": False,
        }
    )
    return execution


def _downstream_contract() -> dict[str, Any]:
    return {
        "campaign_rows": 3330,
        "campaign_state_count": 3,
        "campaign_repetitions_per_test": 30,
        "compact_shipment_trace_per_holdout_case": True,
        "lot_replay": "required_for_selected_dossiers",
        "physical_qualification": "required",
        "action_replay": "required_or_explicitly_not_representable",
        "final_standalone_html": "required",
    }


def prepare_plan(
    output_dir: Path,
    *,
    development_plan_dir: Path,
    development_run_dir: Path,
    allow_test_source: bool = False,
) -> Path:
    """Freeze a separate holdout plan without opening any reserved seed."""

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite holdout plan: {output_dir}")
    source_plan, run_manifest, selection, progress = _load_development_source(
        development_plan_dir,
        development_run_dir,
        allow_test_source=allow_test_source,
    )
    development_run_dir = development_run_dir.resolve()
    if any(
        _paths_overlap(output_dir, path)
        for path in _protected_development_sources(
            source_plan, development_run_dir
        )
    ):
        raise V6HoldoutError("Holdout plan overlaps an immutable upstream source")
    by_key = {candidate.key: candidate for candidate in source_plan.candidates}
    selected = selection["selected_candidate_keys"]
    candidates = tuple(
        Candidate(
            by_key[selected[group]].key,
            by_key[selected[group]].candidate_id,
            group,
            by_key[selected[group]].offset_days_268091,
            by_key[selected[group]].offset_days_268967,
            "execute_fresh_holdout",
            by_key[selected[group]].key,
        )
        for group in TARGETS
    )
    temporary = output_dir.parent / f".{output_dir.name}.building-{os.getpid()}"
    if temporary.exists():
        raise FileExistsError(f"Temporary holdout plan exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        inventory: dict[str, dict[str, str]] = {}
        for candidate in candidates:
            source_item = source_plan.manifest["inventory"][candidate.key]
            source_graph = (source_plan.plan_dir / source_item["graph_path"]).resolve()
            target_graph = temporary / "graphs" / f"{candidate.key}.json"
            target_graph.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_graph, target_graph)
            if sha256_file(target_graph) != source_item["graph_sha256"]:
                raise V6HoldoutError("Copied selected graph differs from V6 source")
            inventory[candidate.key] = {
                "graph_path": target_graph.relative_to(temporary).as_posix(),
                "graph_sha256": source_item["graph_sha256"],
            }
        module_path = Path(__file__).resolve()
        source_files = {
            "development_plan": source_plan.plan_dir / "refinement_plan.json",
            "development_run_manifest": development_run_dir / "run_manifest.json",
            "development_progress": development_run_dir / "development_progress.json",
            "development_selection": development_run_dir / "development_selection.json",
        }
        source_ref = {
            "plan_dir": str(source_plan.plan_dir),
            "run_dir": str(development_run_dir),
            "plan_signature": source_plan.manifest["plan_signature"],
            "run_signature": run_manifest["run_signature"],
            "development_progress_signature": progress["progress_signature"],
            "development_selection_signature": selection["selection_signature"],
            "source_file_sha256": {
                key: sha256_file(path) for key, path in source_files.items()
            },
            "development_evidence_signature_set_sha256": selection[
                "development_evidence_signature_set_sha256"
            ],
            "holdout_cases_read_at_freeze": 0,
        }
        manifest: dict[str, Any] = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "status": "frozen_before_first_holdout_read",
            "source": copy.deepcopy(source_plan.manifest["source"]),
            "v6_development_source": source_ref,
            "source_hashes": {
                **copy.deepcopy(source_plan.manifest["source_hashes"]),
                "v6_holdout_driver_sha256": sha256_file(module_path),
            },
            "runtime_dependencies": copy.deepcopy(
                source_plan.manifest["runtime_dependencies"]
            ),
            "candidates": [_candidate_payload(candidate) for candidate in candidates],
            "inventory": inventory,
            "development_authorization_source": copy.deepcopy(selection),
            "holdout_cases": [
                {
                    "stage": "holdout",
                    "candidate_key": candidate.key,
                    "target_group": candidate.target_group,
                    "seed": seed,
                }
                for candidate in candidates
                for seed in EXPECTED_HOLDOUT_SEEDS
            ],
            "expected_holdout_case_count": EXPECTED_HOLDOUT_CASES,
            "selection_contract": copy.deepcopy(
                source_plan.manifest["selection_contract"]
            ),
            "holdout_contract": _holdout_contract(),
            "execution_contract": _execution_contract(source_plan),
            "downstream_contract": _downstream_contract(),
        }
        manifest["plan_signature"] = stable_sha256(manifest)
        _write_json(temporary / "refinement_plan.json", manifest)
        refreshed = _load_development_source(
            development_plan_dir,
            development_run_dir,
            allow_test_source=allow_test_source,
        )
        if (
            refreshed[0].manifest != source_plan.manifest
            or refreshed[1:] != (run_manifest, selection, progress)
        ):
            raise V6HoldoutError(
                "V6 development source changed while freezing the holdout plan"
            )
        os.replace(temporary, output_dir)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return output_dir


def _manifest_without_signature(manifest: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(manifest)
    unsigned.pop("plan_signature", None)
    return unsigned


def validate_plan(
    plan_dir: Path,
    *,
    verify_runtime_dependencies: bool = True,
    allow_test_source: bool = False,
) -> ValidatedPlan:
    plan_dir = plan_dir.resolve()
    manifest = _read_json(plan_dir / "refinement_plan.json")
    if manifest.get("plan_signature") != stable_sha256(
        _manifest_without_signature(manifest)
    ):
        raise V6HoldoutError("Invalid V6 holdout plan signature")
    expected_fields = {
        "schema_version",
        "status",
        "source",
        "v6_development_source",
        "source_hashes",
        "runtime_dependencies",
        "candidates",
        "inventory",
        "development_authorization_source",
        "holdout_cases",
        "expected_holdout_case_count",
        "selection_contract",
        "holdout_contract",
        "execution_contract",
        "downstream_contract",
        "plan_signature",
    }
    if set(manifest) != expected_fields:
        raise V6HoldoutError("Unexpected V6 holdout plan field")
    source = manifest.get("v6_development_source") or {}
    source_plan, run_manifest, selection, progress = _load_development_source(
        Path(str(source.get("plan_dir") or ".")),
        Path(str(source.get("run_dir") or ".")),
        allow_test_source=allow_test_source,
    )
    source_files = {
        "development_plan": source_plan.plan_dir / "refinement_plan.json",
        "development_run_manifest": Path(source["run_dir"]) / "run_manifest.json",
        "development_progress": Path(source["run_dir"]) / "development_progress.json",
        "development_selection": Path(source["run_dir"])
        / "development_selection.json",
    }
    expected_source = {
        "plan_dir": str(source_plan.plan_dir),
        "run_dir": str(Path(source["run_dir"]).resolve()),
        "plan_signature": source_plan.manifest["plan_signature"],
        "run_signature": run_manifest["run_signature"],
        "development_progress_signature": progress["progress_signature"],
        "development_selection_signature": selection["selection_signature"],
        "source_file_sha256": {
            key: sha256_file(path) for key, path in source_files.items()
        },
        "development_evidence_signature_set_sha256": selection[
            "development_evidence_signature_set_sha256"
        ],
        "holdout_cases_read_at_freeze": 0,
    }
    if source != expected_source:
        raise V6HoldoutError("V6 development source changed after holdout freeze")
    if (
        manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "frozen_before_first_holdout_read"
        or manifest.get("source") != source_plan.manifest["source"]
        or manifest.get("runtime_dependencies")
        != source_plan.manifest["runtime_dependencies"]
        or manifest.get("selection_contract")
        != source_plan.manifest["selection_contract"]
        or manifest.get("holdout_contract") != _holdout_contract()
        or manifest.get("execution_contract") != _execution_contract(source_plan)
        or manifest.get("downstream_contract") != _downstream_contract()
        or manifest.get("expected_holdout_case_count") != EXPECTED_HOLDOUT_CASES
    ):
        raise V6HoldoutError("V6 holdout frozen contract changed")
    expected_hashes = {
        **copy.deepcopy(source_plan.manifest["source_hashes"]),
        "v6_holdout_driver_sha256": sha256_file(Path(__file__).resolve()),
    }
    if manifest.get("source_hashes") != expected_hashes:
        raise V6HoldoutError("V6 holdout driver or source hashes changed")
    if manifest.get("development_authorization_source") != selection:
        raise V6HoldoutError("V6 selected states changed after plan freeze")
    candidates = tuple(
        Candidate(
            str(row["key"]),
            str(row["candidate_id"]),
            str(row["target_group"]),
            float(row["offset_days_268091"]),
            float(row["offset_days_268967"]),
            str(row["evidence_mode"]),
            str(row["source_operating_point_id"]),
        )
        for row in manifest.get("candidates") or []
    )
    source_by_key = {candidate.key: candidate for candidate in source_plan.candidates}
    selected = selection["selected_candidate_keys"]
    expected_candidates = tuple(
        Candidate(
            source_by_key[selected[group]].key,
            source_by_key[selected[group]].candidate_id,
            group,
            source_by_key[selected[group]].offset_days_268091,
            source_by_key[selected[group]].offset_days_268967,
            "execute_fresh_holdout",
            source_by_key[selected[group]].key,
        )
        for group in TARGETS
    )
    if candidates != expected_candidates:
        raise V6HoldoutError("V6 holdout candidates differ from frozen selection")
    inventory = manifest.get("inventory") or {}
    if set(inventory) != {candidate.key for candidate in candidates}:
        raise V6HoldoutError("V6 holdout graph inventory changed")
    for candidate in candidates:
        item = inventory.get(candidate.key) or {}
        graph = (plan_dir / str(item.get("graph_path") or "")).resolve()
        source_item = source_plan.manifest["inventory"][candidate.key]
        if (
            set(item) != {"graph_path", "graph_sha256"}
            or not graph.is_relative_to(plan_dir)
            or item.get("graph_sha256") != source_item["graph_sha256"]
            or sha256_file(graph) != source_item["graph_sha256"]
        ):
            raise V6HoldoutError("Selected V6 holdout graph changed")
    expected_cases = [
        {
            "stage": "holdout",
            "candidate_key": candidate.key,
            "target_group": candidate.target_group,
            "seed": seed,
        }
        for candidate in candidates
        for seed in EXPECTED_HOLDOUT_SEEDS
    ]
    if manifest.get("holdout_cases") != expected_cases:
        raise V6HoldoutError("V6 holdout matrix is not exactly three states by 30 seeds")
    if verify_runtime_dependencies:
        try:
            v4._assert_runtime_dependencies_current(  # noqa: SLF001
                v4.ValidatedPlan(plan_dir, manifest, candidates)
            )
        except Exception as exc:
            raise V6HoldoutError("Pinned execution dependencies changed") from exc
    return ValidatedPlan(plan_dir, manifest, candidates)


def _case_key(stage: str, candidate_key: str, seed: int) -> str:
    return f"{stage}__{candidate_key}__seed_{seed}"


def _evidence_path(run_dir: Path, stage: str, candidate_key: str, seed: int) -> Path:
    digest = hashlib.sha256(_case_key(stage, candidate_key, seed).encode()).hexdigest()[:24]
    return run_dir / "evidence" / stage / f"{digest}.json"


def _run_manifest(plan: ValidatedPlan, execution_mode: str) -> dict[str, Any]:
    if execution_mode not in {OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE}:
        raise V6HoldoutError("Unknown V6 holdout execution mode")
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_path": str(plan.plan_dir),
        "plan_sha256": sha256_file(plan.plan_dir / "refinement_plan.json"),
        "plan_signature": plan.manifest["plan_signature"],
        "source_v6_selection_signature": plan.manifest[
            "v6_development_source"
        ]["development_selection_signature"],
        "development_seeds": [],
        "holdout_seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "incident_design_seed_excluded": INCIDENT_DESIGN_SEED,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "development_engine_runs": 0,
        "holdout_engine_runs": EXPECTED_HOLDOUT_CASES,
        "retuning_supported": False,
    }
    return {**unsigned, "run_signature": stable_sha256(unsigned)}


def _registered_execution_mode(plan: ValidatedPlan, run_dir: Path) -> str:
    payload = _read_json(run_dir / "run_manifest.json")
    for mode in (OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE):
        if payload == _run_manifest(plan, mode):
            return mode
    raise V6HoldoutError("Invalid V6 holdout run registration")


def _load_development_selection(
    plan: ValidatedPlan, run_dir: Path
) -> dict[str, Any]:
    mode = _registered_execution_mode(plan, run_dir)
    expected = _authorization_payload(
        plan_signature=plan.manifest["plan_signature"],
        source=plan.manifest["development_authorization_source"],
        execution_mode=mode,
    )
    payload = _read_json(run_dir / "development_selection.json")
    _verify_signature(payload, "selection_signature", "V6 holdout authorization")
    if payload != expected:
        raise V6HoldoutError("V6 holdout selected states changed")
    return payload


def _register_run(plan: ValidatedPlan, run_dir: Path, mode: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "run_manifest.json"
    selection_path = run_dir / "development_selection.json"
    expected_manifest = _run_manifest(plan, mode)
    expected_selection = _authorization_payload(
        plan_signature=plan.manifest["plan_signature"],
        source=plan.manifest["development_authorization_source"],
        execution_mode=mode,
    )
    allowed = {
        ".v6-holdout.lock",
        "run_manifest.json",
        "development_selection.json",
        "holdout_progress.json",
        "holdout_result.json",
        "evidence",
        "engine_attempts",
        "shipment_traces",
    }
    unexpected = {item.name for item in run_dir.iterdir()} - allowed
    if unexpected:
        raise V6HoldoutError("Unexpected item exists in V6 holdout run")
    if any(item.name not in {".v6-holdout.lock"} for item in run_dir.iterdir()) and not manifest_path.is_file():
        raise V6HoldoutError("Refusing an unregistered non-empty holdout run")
    if manifest_path.exists() and _read_json(manifest_path) != expected_manifest:
        raise V6HoldoutError("Holdout run belongs to another plan")
    if selection_path.exists() and _read_json(selection_path) != expected_selection:
        raise V6HoldoutError("Holdout run contains another frozen selection")
    if not manifest_path.exists():
        _write_json(manifest_path, expected_manifest)
    if not selection_path.exists():
        _write_json(selection_path, expected_selection)


def prepare_holdout_run(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[str, Any]:
    """Register the immutable selection before a watcher starts; run no engine."""

    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    if any(
        _paths_overlap(run_dir, path)
        for path in _protected_holdout_sources(
            plan, allow_test_source=test_only
        )
    ):
        raise V6HoldoutError("Holdout run overlaps an immutable upstream source")
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    with _run_lock(run_dir):
        _register_run(plan, run_dir, mode)
        _validate_trace_inventory(plan, run_dir, mode, require_complete=False)
        completed, _missing = _collect(plan, run_dir, mode)
        return {
            "status": (
                "registered_before_watcher_and_first_holdout_engine"
                if not completed
                else "registered_resume_of_existing_holdout_evidence"
            ),
            "plan_signature": plan.manifest["plan_signature"],
            "run_signature": _run_manifest(plan, mode)["run_signature"],
            "selection_signature": _authorization_payload(
                plan_signature=plan.manifest["plan_signature"],
                source=plan.manifest["development_authorization_source"],
                execution_mode=mode,
            )["selection_signature"],
            "completed_evidence_case_count": len(completed),
            "new_engine_runs_by_registration": 0,
        }


def _validate_sidecar_authorization(
    plan: ValidatedPlan,
    run_dir: Path,
    *,
    sidecar_dir: Path | None,
    watcher_pid: int | None,
) -> dict[str, Any]:
    """Require a live, signed V6 watcher before every official engine start."""

    if sidecar_dir is None or watcher_pid is None or int(watcher_pid) <= 0:
        raise V6HoldoutError(
            "Official V6 holdout requires --sidecar-dir and --watcher-pid"
        )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_holdout_curve_sidecar_v6 as sidecar_v6,
    )

    sidecar_dir = sidecar_dir.resolve()
    ready_path = sidecar_dir / "watcher_ready.json"
    contract_path = sidecar_dir / "capture_contract.json"
    ready_payload, ready_sha256 = _read_json_snapshot(ready_path)
    contract_payload, contract_sha256 = _read_json_snapshot(contract_path)
    ready = sidecar_v6.validate_ready_payload(
        ready_payload,
        expected_output_dir=sidecar_dir,
        expected_watcher_pid=int(watcher_pid),
    )
    contract = sidecar_v6.validate_contract(contract_payload)
    try:
        sidecar_v6.assert_watcher_lease_active(sidecar_dir)
    except Exception as exc:
        raise V6HoldoutError("V6 sidecar watcher lease is not active") from exc
    expected_cases = [
        asdict(case) for case in sidecar_v6.load_official_cases(plan.plan_dir, run_dir)
    ]
    plan_binding = contract.get("plan") or {}
    run_binding = contract.get("run") or {}
    plan_manifest = plan.plan_dir / "refinement_plan.json"
    run_manifest = run_dir / "run_manifest.json"
    if (
        ready.get("contract_signature") != contract.get("contract_signature")
        or contract.get("producer_protocol") != SCHEMA_VERSION
        or int(contract.get("expected_case_count") or -1) != EXPECTED_HOLDOUT_CASES
        or contract.get("cases") != expected_cases
        or Path(str(contract.get("output_directory") or "")).resolve()
        != sidecar_dir
        or Path(str(plan_binding.get("directory") or "")).resolve() != plan.plan_dir
        or Path(str(plan_binding.get("manifest_path") or "")).resolve()
        != plan_manifest.resolve()
        or plan_binding.get("manifest_sha256") != sha256_file(plan_manifest)
        or Path(str(run_binding.get("directory") or "")).resolve() != run_dir
        or Path(str(run_binding.get("manifest_path") or "")).resolve()
        != run_manifest.resolve()
        or run_binding.get("manifest_sha256") != sha256_file(run_manifest)
        or not sidecar_v6.implementation_v5._process_running(  # noqa: SLF001
            int(watcher_pid)
        )
    ):
        raise V6HoldoutError("V6 holdout watcher authorization is not current")
    return {
        "ready": ready,
        "contract": contract,
        "ready_path": ready_path,
        "ready_sha256": ready_sha256,
        "contract_path": contract_path,
        "contract_sha256": contract_sha256,
    }


def _stage_jobs(
    plan: ValidatedPlan, run_dir: Path, stage: str
) -> tuple[tuple[Candidate, int], ...]:
    if stage != "holdout":
        raise V6HoldoutError("V6 holdout protocol supports holdout only")
    selection = _load_development_selection(plan, run_dir)
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    chosen = selection["selected_candidate_keys"]
    candidates = tuple(by_key[chosen[group]] for group in TARGETS)
    return tuple(
        (candidate, seed)
        for candidate in candidates
        for seed in EXPECTED_HOLDOUT_SEEDS
    )


EVIDENCE_FIELDS = v5.EVIDENCE_FIELDS


def _validate_evidence(
    payload: Mapping[str, Any],
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: Candidate,
    seed: int,
    mode: str,
) -> dict[str, Any]:
    _verify_signature(payload, "evidence_signature", "V6 holdout evidence")
    if (
        set(payload) != EVIDENCE_FIELDS
        or payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("stage") != "holdout"
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or int(payload.get("seed") or -1) != seed
        or payload.get("evidence_mode") != "execute_fresh_holdout"
        or payload.get("graph_sha256")
        != plan.manifest["inventory"][candidate.key]["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("source_evidence") is not None
        or payload.get("valid") is not True
    ):
        raise V6HoldoutError(f"V6 holdout evidence mismatch: {candidate.key}/{seed}")
    proof = payload.get("executor_proof")
    if not isinstance(proof, Mapping):
        raise V6HoldoutError("V6 holdout evidence lacks executor proof")
    expected_kind = (
        "coarse_execute_candidate"
        if mode == OFFICIAL_EXECUTION_MODE
        else "injected_test_executor"
    )
    if proof.get("kind") != expected_kind:
        raise V6HoldoutError("V6 holdout executor proof mode changed")
    adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)
    raw = proof.get("raw_evidence") if mode == OFFICIAL_EXECUTION_MODE else proof.get("raw_payload")
    try:
        raw_metrics = (
            v4._validate_coarse_executor_evidence(  # noqa: SLF001
                raw, candidate=candidate, seed=seed, plan=adapter
            )
            if mode == OFFICIAL_EXECUTION_MODE
            else v4._normalize_metrics((raw or {}).get("metrics") or raw or {})  # noqa: SLF001
        )
    except Exception as exc:
        raise V6HoldoutError("Underlying V6 holdout executor proof is invalid") from exc
    if raw_metrics != v4._normalize_metrics(payload.get("metrics") or {}):  # noqa: SLF001
        raise V6HoldoutError("V6 holdout outer/executor metrics differ")
    if mode == OFFICIAL_EXECUTION_MODE:
        try:
            v4._validate_shipment_trace_reference(  # noqa: SLF001
                payload.get("shipment_trace"),
                plan=adapter,
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
            )
        except Exception as exc:
            raise V6HoldoutError("Invalid V6 compact shipment trace") from exc
    elif payload.get("shipment_trace") is not None:
        raise V6HoldoutError("Test-only holdout must not claim a shipment trace")
    result = dict(payload)
    result["metrics"] = v4._normalize_metrics(payload.get("metrics") or {})  # noqa: SLF001
    return result


def _progress(
    plan: ValidatedPlan,
    run_dir: Path,
    completed: int,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    mode = _registered_execution_mode(plan, run_dir)
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.holdout.progress",
        "plan_signature": plan.manifest["plan_signature"],
        "stage": "holdout",
        "status": status,
        "completed_case_count": completed,
        "expected_case_count": EXPECTED_HOLDOUT_CASES,
        "execution_mode": mode,
        "publishable": mode == OFFICIAL_EXECUTION_MODE,
        "error": error,
        "updated_at_utc": _now(),
    }
    payload = {**unsigned, "progress_signature": stable_sha256(unsigned)}
    _write_json(run_dir / "holdout_progress.json", payload)
    return payload


def _collect(
    plan: ValidatedPlan, run_dir: Path, mode: str
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[tuple[Candidate, int]]]:
    completed: dict[tuple[str, int], dict[str, Any]] = {}
    missing: list[tuple[Candidate, int]] = []
    jobs = _stage_jobs(plan, run_dir, "holdout")
    expected_names = {
        _evidence_path(run_dir, "holdout", candidate.key, seed).name
        for candidate, seed in jobs
    }
    evidence_dir = run_dir / "evidence" / "holdout"
    if evidence_dir.exists() and {
        path.name for path in evidence_dir.glob("*.json")
    } - expected_names:
        raise V6HoldoutError("Unexpected V6 holdout evidence exists")
    for candidate, seed in jobs:
        path = _evidence_path(run_dir, "holdout", candidate.key, seed)
        if not path.is_file():
            missing.append((candidate, seed))
            continue
        completed[(candidate.key, seed)] = _validate_evidence(
            _read_json(path),
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
            mode=mode,
        )
    return completed, missing


def _validate_trace_inventory(
    plan: ValidatedPlan,
    run_dir: Path,
    mode: str,
    *,
    require_complete: bool,
) -> None:
    jobs = _stage_jobs(plan, run_dir, "holdout")
    root = run_dir / "shipment_traces"
    actual = (
        {path.resolve() for path in root.rglob("*") if path.is_file()}
        if root.exists()
        else set()
    )
    expected_by_path: dict[Path, tuple[Candidate, int]] = {}
    if mode == OFFICIAL_EXECUTION_MODE:
        expected_by_path = {
            (
                run_dir
                / v4._shipment_trace_relative_path(candidate, seed)  # noqa: SLF001
            ).resolve(): (candidate, seed)
            for candidate, seed in jobs
        }
    if not actual.issubset(expected_by_path):
        raise V6HoldoutError("Unexpected compact trace exists in V6 holdout run")
    adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)
    for path in sorted(actual, key=str):
        candidate, seed = expected_by_path[path]
        try:
            v4._load_shipment_trace_file(  # noqa: SLF001
                plan=adapter,
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
            )
        except Exception as exc:
            raise V6HoldoutError("Stored V6 compact trace is invalid") from exc
    if require_complete and (
        actual != set(expected_by_path)
        or any(
            not _evidence_path(run_dir, "holdout", candidate.key, seed).is_file()
            for candidate, seed in jobs
        )
    ):
        raise V6HoldoutError("Official V6 holdout trace inventory is incomplete")


@contextmanager
def _run_lock(run_dir: Path):
    path = run_dir / ".v6-holdout.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise V6HoldoutError("Another V6 holdout process is active") from exc
        yield
    finally:
        try:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def run_holdout(
    plan_dir: Path,
    run_dir: Path,
    *,
    executor: Executor | None = None,
    max_workers: int = 2,
    test_only: bool = False,
    sidecar_dir: Path | None = None,
    watcher_pid: int | None = None,
) -> dict[str, Any]:
    """Execute exactly the frozen 3 x 30 holdout matrix; safely resumable."""

    if max_workers not in {1, 2}:
        raise V6HoldoutError("V6 holdout permits one or two workers")
    if (executor is None) is test_only:
        raise V6HoldoutError("Injected executors require test_only=True")
    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    if any(
        _paths_overlap(run_dir, path)
        for path in _protected_holdout_sources(
            plan, allow_test_source=test_only
        )
    ):
        raise V6HoldoutError("Holdout run overlaps an immutable upstream source")
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    selected_executor = executor or v4._real_executor  # noqa: SLF001
    adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)
    sidecar_authorization: dict[str, Any] | None = None
    with _run_lock(run_dir):
        _register_run(plan, run_dir, mode)
        if mode == OFFICIAL_EXECUTION_MODE:
            authorization = _validate_sidecar_authorization(
                plan,
                run_dir,
                sidecar_dir=sidecar_dir,
                watcher_pid=watcher_pid,
            )
            sidecar_authorization = {
                "watcher_pid": int(watcher_pid or 0),
                "ready_path": authorization["ready_path"],
                "ready_sha256": authorization["ready_sha256"],
                "ready_signature": authorization["ready"]["ready_signature"],
                "contract_path": authorization["contract_path"],
                "contract_sha256": authorization["contract_sha256"],
                "contract_signature": authorization["ready"]["contract_signature"],
            }
        _validate_trace_inventory(plan, run_dir, mode, require_complete=False)
        completed, missing = _collect(plan, run_dir, mode)
        _progress(plan, run_dir, len(completed), "running")

        def execute(candidate: Candidate, seed: int) -> dict[str, Any]:
            if mode == OFFICIAL_EXECUTION_MODE:
                from etudecas.prototypes.scan_2027_risk_control import (
                    supplier_holdout_curve_sidecar_v6 as sidecar_v6,
                )

                authorization = sidecar_authorization or {}
                ready_path = Path(str(authorization.get("ready_path") or ""))
                contract_path = Path(
                    str(authorization.get("contract_path") or "")
                )
                try:
                    sidecar_v6.assert_watcher_lease_active(
                        ready_path.parent
                    )
                except Exception as exc:
                    raise V6HoldoutError(
                        "V6 curve watcher lease ended before an engine execution"
                    ) from exc
                if (
                    not sidecar_v6.implementation_v5._process_running(  # noqa: SLF001
                        int(authorization.get("watcher_pid") or 0)
                    )
                    or _read_json_snapshot(ready_path)[1]
                    != authorization.get("ready_sha256")
                    or _read_json_snapshot(contract_path)[1]
                    != authorization.get("contract_sha256")
                ):
                    raise V6HoldoutError(
                        "V6 curve watcher authorization changed before an engine execution"
                    )
            attempt_key = _case_key("holdout", candidate.key, seed)
            digest = hashlib.sha256(attempt_key.encode()).hexdigest()[:24]
            attempt_root = (
                run_dir
                / "engine_attempts"
                / "holdout"
                / digest
                / f"attempt-{os.getpid()}-{os.urandom(8).hex()}"
            )
            raw = selected_executor(
                candidate=candidate,
                seed=seed,
                stage="holdout",
                run_dir=run_dir,
                plan=plan.manifest,
                validated_plan=adapter,
                attempt_root=attempt_root,
            )
            if not isinstance(raw, Mapping):
                raise V6HoldoutError("V6 holdout executor must return a mapping")
            if mode == OFFICIAL_EXECUTION_MODE:
                try:
                    v4._assert_runtime_dependencies_current(adapter)  # noqa: SLF001
                except Exception as exc:
                    raise V6HoldoutError(
                        "Pinned dependencies changed during V6 holdout"
                    ) from exc
            metrics, proof = v4._executor_output(  # noqa: SLF001
                raw,
                candidate=candidate,
                seed=seed,
                plan=adapter,
                injected=test_only,
            )
            trace = None
            if mode == OFFICIAL_EXECUTION_MODE:
                case_dir = v4._coarse_case_dir(  # noqa: SLF001
                    raw, run_dir, candidate, seed
                )
                trace = v4._write_holdout_shipment_trace(  # noqa: SLF001
                    plan=adapter,
                    run_dir=run_dir,
                    candidate=candidate,
                    seed=seed,
                    source_csv=case_dir / v4.SHIPMENT_TRACE_SOURCE_RELATIVE_PATH,
                )
            unsigned = {
                "schema_version": EVIDENCE_SCHEMA_VERSION,
                "plan_signature": plan.manifest["plan_signature"],
                "stage": "holdout",
                "candidate_key": candidate.key,
                "candidate_id": candidate.candidate_id,
                "target_group": candidate.target_group,
                "seed": seed,
                "evidence_mode": "execute_fresh_holdout",
                "graph_sha256": plan.manifest["inventory"][candidate.key][
                    "graph_sha256"
                ],
                "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
                "metrics": metrics,
                "source_evidence": None,
                "executor_proof": proof,
                "shipment_trace": trace,
                "valid": True,
                "created_at_utc": _now(),
            }
            payload = {**unsigned, "evidence_signature": stable_sha256(unsigned)}
            _validate_evidence(
                payload,
                plan=plan,
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
                mode=mode,
            )
            _write_json(
                _evidence_path(run_dir, "holdout", candidate.key, seed), payload
            )
            if proof.get("kind") == "coarse_execute_candidate":
                v4._prune_real_executor_case(  # noqa: SLF001
                    proof, run_dir, candidate, seed
                )
            return payload

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                pending = iter(missing)
                futures: dict[Any, tuple[Candidate, int]] = {}
                for _ in range(max_workers):
                    try:
                        candidate, seed = next(pending)
                    except StopIteration:
                        break
                    futures[pool.submit(execute, candidate, seed)] = (candidate, seed)
                while futures:
                    future = next(as_completed(futures))
                    candidate, seed = futures.pop(future)
                    completed[(candidate.key, seed)] = future.result()
                    _progress(plan, run_dir, len(completed), "running")
                    try:
                        candidate, seed = next(pending)
                    except StopIteration:
                        continue
                    futures[pool.submit(execute, candidate, seed)] = (candidate, seed)
            # The frozen development selection and all pinned sources must still
            # revalidate after the last fresh engine execution.
            validate_plan(
                plan.plan_dir,
                verify_runtime_dependencies=not test_only,
                allow_test_source=test_only,
            )
        except BaseException as exc:
            completed, _missing = _collect(plan, run_dir, mode)
            _progress(plan, run_dir, len(completed), "failed", str(exc))
            raise
        if len(completed) != EXPECTED_HOLDOUT_CASES:
            raise V6HoldoutError("V6 holdout evidence matrix is incomplete")
        _validate_trace_inventory(plan, run_dir, mode, require_complete=True)
        return _progress(plan, run_dir, len(completed), "complete")


def _load_stage_evidence(
    plan: ValidatedPlan, run_dir: Path, stage: str
) -> dict[tuple[str, int], dict[str, Any]]:
    if stage != "holdout":
        raise V6HoldoutError("V6 holdout protocol has no development stage")
    mode = _registered_execution_mode(plan, run_dir)
    _validate_trace_inventory(plan, run_dir, mode, require_complete=True)
    evidence, missing = _collect(plan, run_dir, mode)
    progress = _read_json(run_dir / "holdout_progress.json")
    _verify_signature(progress, "progress_signature", "V6 holdout progress")
    if (
        missing
        or len(evidence) != EXPECTED_HOLDOUT_CASES
        or progress.get("status") != "complete"
        or progress.get("completed_case_count") != EXPECTED_HOLDOUT_CASES
        or progress.get("execution_mode") != mode
    ):
        raise V6HoldoutError("V6 holdout is not complete")
    return evidence


def _build_holdout_result(
    plan: ValidatedPlan,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    selection: Mapping[str, Any],
    *,
    execution_mode: str,
) -> dict[str, Any]:
    chosen = selection["selected_candidate_keys"]
    ordered_keys = [chosen[group] for group in TARGETS]
    try:
        v4._validate_paired_demand(  # noqa: SLF001
            evidence, ordered_keys, EXPECTED_HOLDOUT_SEEDS
        )
    except Exception as exc:
        raise V6HoldoutError("V6 paired holdout demand changed") from exc
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    rows = {
        group: [evidence[(key, seed)] for seed in EXPECTED_HOLDOUT_SEEDS]
        for group, key in chosen.items()
    }
    summaries = {
        group: v4._candidate_summary(by_key[key], rows[group], False)  # noqa: SLF001
        for group, key in chosen.items()
    }
    bootstrap = v4._paired_bootstrap_global(rows)  # noqa: SLF001
    pooled, joint, pf967 = v4._ordered_pair(  # noqa: SLF001
        summaries["op_100"], summaries["op_93"], summaries["op_80"]
    )
    accepted = (
        all(row["admissible_individually"] for row in summaries.values())
        and pooled
        and joint >= MIN_ORDERED_SEEDS
    )
    unsigned = {
        "schema_version": HOLDOUT_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "development_selection_signature": selection["selection_signature"],
        "source_v6_selection_signature": selection["source_v6_selection_signature"],
        "status": ACCEPTED_HOLDOUT_STATUS if accepted else REJECTED_HOLDOUT_STATUS,
        "holdout_seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_evidence_case_count": len(evidence),
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "holdout_evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "selected_candidate_keys": copy.deepcopy(chosen),
        "state_summaries": summaries,
        "paired_bootstrap_global_descriptive_only": {
            "contract": plan.manifest["holdout_contract"]["bootstrap"],
            "intervals": bootstrap,
        },
        "product_gap_warning_above_5pp_by_state": {
            group: row["product_gap_warning"] for group, row in summaries.items()
        },
        "pooled_strict_order": pooled,
        "same_seed_joint_strict_order_count": joint,
        "same_seed_pf268967_strict_order_count": pf967,
        "accepted": accepted,
        "retuning_after_holdout": False,
        "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
    }
    return {**unsigned, "holdout_signature": stable_sha256(unsigned)}


def finalize_holdout(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[str, Any]:
    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    with _run_lock(run_dir):
        if _read_json(run_dir / "run_manifest.json") != _run_manifest(plan, mode):
            raise V6HoldoutError("Official/test-only V6 holdout registrations differ")
        selection = _load_development_selection(plan, run_dir)
        evidence = _load_stage_evidence(plan, run_dir, "holdout")
        validate_plan(
            plan.plan_dir,
            verify_runtime_dependencies=not test_only,
            allow_test_source=test_only,
        )
        result = _build_holdout_result(
            plan, evidence, selection, execution_mode=mode
        )
        output = run_dir / "holdout_result.json"
        if output.exists() and _read_json(output) != result:
            raise V6HoldoutError("Existing V6 holdout finalization differs")
        if not output.exists():
            _write_json(output, result)
        return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--output-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    plan.add_argument("--development-plan-dir", type=Path, default=DEFAULT_DEVELOPMENT_PLAN)
    plan.add_argument("--development-run-dir", type=Path, default=DEFAULT_DEVELOPMENT_RUN)
    validate = sub.add_parser("validate")
    validate.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    prepare_run = sub.add_parser("prepare-run")
    prepare_run.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    prepare_run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run = sub.add_parser("run-holdout")
    run.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run.add_argument("--workers", type=int, choices=(1, 2), default=2)
    run.add_argument("--sidecar-dir", type=Path, required=True)
    run.add_argument("--watcher-pid", type=int, required=True)
    finalize = sub.add_parser("finalize-holdout")
    finalize.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    finalize.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        print(
            prepare_plan(
                args.output_dir,
                development_plan_dir=args.development_plan_dir,
                development_run_dir=args.development_run_dir,
            )
        )
    elif args.command == "validate":
        print(validate_plan(args.plan_dir).manifest["plan_signature"])
    elif args.command == "prepare-run":
        print(prepare_holdout_run(args.plan_dir, args.run_dir))
    elif args.command == "run-holdout":
        print(
            run_holdout(
                args.plan_dir,
                args.run_dir,
                max_workers=args.workers,
                sidecar_dir=args.sidecar_dir,
                watcher_pid=args.watcher_pid,
            )
        )
    else:
        print(finalize_holdout(args.plan_dir, args.run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
