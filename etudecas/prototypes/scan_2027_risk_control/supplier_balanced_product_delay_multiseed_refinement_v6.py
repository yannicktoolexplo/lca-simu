#!/usr/bin/env python3
"""Conditional, development-only V6 refinement after an exact V5 no-go.

This module is deliberately dormant until the signed V5 development selection is
terminal with ``development_failed_no_holdout``.  It imports the signed V5
development proofs for OP100 and the two admissible OP93 candidates, executes
exactly two new OP80 recombinations on the same thirty development seeds, and
applies the unchanged V4/V5 selection rules.

V6 cannot execute a holdout.  A successful development result only authorizes a
separate, subsequently frozen holdout protocol.  No V5 holdout path is ever read.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as v5,
)


SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v6"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.development_selection"

DEVELOPMENT_SEEDS = v5.DEVELOPMENT_SEEDS
EXPECTED_HOLDOUT_SEEDS = v5.EXPECTED_HOLDOUT_SEEDS
TARGETS = v5.TARGETS
MIN_ORDERED_SEEDS = v5.MIN_ORDERED_SEEDS
SERVICE_DAYS = v5.SERVICE_DAYS
PRODUCTS = v5.PRODUCTS

SOURCE_OP93_KEYS = (
    "op93_v5_8p3_80p6",
    "op93_v5_8p4_80p6",
)
OP80_GRID = (
    ("op80_v6_17_96p6", 17.0, 96.6),
    ("op80_v6_17p5_96p6", 17.5, 96.6),
)

EXPECTED_IMPORTED_DEVELOPMENT_CASES = (
    1 + len(SOURCE_OP93_KEYS)
) * len(DEVELOPMENT_SEEDS)
EXPECTED_NEW_DEVELOPMENT_CASES = len(OP80_GRID) * len(DEVELOPMENT_SEEDS)
EXPECTED_DEVELOPMENT_CASES = (
    EXPECTED_IMPORTED_DEVELOPMENT_CASES + EXPECTED_NEW_DEVELOPMENT_CASES
)

OFFICIAL_EXECUTION_MODE = "official_v6_additive_execute_candidate"
TEST_ONLY_EXECUTION_MODE = "test_only_v6_injected_executor"
SOURCE_TERMINAL_STATUS = "development_failed_no_holdout"
SUCCESS_STATUS = "development_selected_pending_separate_fresh_holdout_protocol"
FAIL_STATUS = "development_failed_no_holdout"

INTERPRETATION = (
    "V6 is a conditional development-only recombination check. It changes only "
    "planned supplier lead-time offsets, imports only signed V5 development "
    "proofs, and makes no industrial precision claim for fractional offsets."
)

DEFAULT_ARTIFACT_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
)
DEFAULT_V5_PLAN = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_plan_20260905_v5"
)
DEFAULT_V5_RUN = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_run_20260905_v5"
)
DEFAULT_V5_SIDECAR = (
    DEFAULT_ARTIFACT_ROOT / "supplier_holdout_nominal_curves_sidecar_20260905_v5"
)
DEFAULT_PLAN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_plan_20260905_v6"
)
DEFAULT_RUN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_run_20260905_v6"
)


class V6ProtocolError(ValueError):
    """Raised when the conditional V6 scientific contract is not exact."""


Candidate = v4.Candidate
Executor = Callable[..., Mapping[str, Any]]


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
        return v4._read_json(path)  # noqa: SLF001
    except Exception as exc:
        raise V6ProtocolError(f"Invalid JSON artifact: {path}") from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v4._write_json(path, payload)  # noqa: SLF001


def _verify_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise V6ProtocolError(f"Invalid {label} signature")
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


def _all_candidates() -> tuple[Candidate, ...]:
    candidates = [
        Candidate(
            "op100_source",
            "v6_op100_imported_from_v5",
            "op_100",
            0.0,
            0.0,
            "reuse_v5_development",
            "op100_source",
        )
    ]
    candidates.extend(
        Candidate(
            key,
            f"v6_{key}_imported",
            "op_93",
            left,
            right,
            "reuse_v5_development",
            key,
        )
        for key, left, right in (
            ("op93_v5_8p3_80p6", 8.3, 80.6),
            ("op93_v5_8p4_80p6", 8.4, 80.6),
        )
    )
    candidates.extend(
        Candidate(key, f"v6_{key}", "op_80", left, right, "execute", "")
        for key, left, right in OP80_GRID
    )
    if len({candidate.key for candidate in candidates}) != len(candidates):
        raise V6ProtocolError("Duplicate V6 candidate key")
    return tuple(candidates)


def _v5_holdout_forbidden_paths(v5_run_dir: Path) -> tuple[Path, ...]:
    return (
        v5_run_dir / "evidence" / "holdout",
        v5_run_dir / "shipment_traces" / "holdout",
        v5_run_dir / "engine_attempts" / "holdout",
        v5_run_dir / "holdout_progress.json",
        v5_run_dir / "holdout_result.json",
    )


def _assert_empty_or_absent(path: Path, label: str) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise V6ProtocolError(f"{label} must be absent or empty: {path}")


def _assert_v5_holdout_unseen(v5_run_dir: Path, v5_sidecar_root: Path) -> None:
    for path in _v5_holdout_forbidden_paths(v5_run_dir.resolve()):
        if path.exists():
            raise V6ProtocolError(f"V5 holdout is visible: {path}")
    _assert_empty_or_absent(v5_sidecar_root.resolve(), "V5 holdout sidecar")


def _assert_local_holdout_unseen(run_dir: Path) -> None:
    forbidden = (
        run_dir / "evidence" / "holdout",
        run_dir / "shipment_traces",
        run_dir / "engine_attempts" / "holdout",
        run_dir / "holdout_progress.json",
        run_dir / "holdout_result.json",
    )
    if any(path.exists() for path in forbidden):
        raise V6ProtocolError("V6 is development-only; holdout material is forbidden")


def _validate_terminal_v5_selection(selection: Mapping[str, Any]) -> None:
    summaries = selection.get("candidate_summaries")
    if not isinstance(summaries, Mapping):
        raise V6ProtocolError("V5 candidate summaries are missing")
    admissible_op93 = tuple(
        sorted(
            key
            for key, summary in summaries.items()
            if isinstance(summary, Mapping)
            and (summary.get("candidate") or {}).get("target_group") == "op_93"
            and summary.get("admissible_individually") is True
        )
    )
    admissible_op80 = tuple(
        sorted(
            key
            for key, summary in summaries.items()
            if isinstance(summary, Mapping)
            and (summary.get("candidate") or {}).get("target_group") == "op_80"
            and summary.get("admissible_individually") is True
        )
    )
    reference = summaries.get("op100_source") or {}
    if (
        selection.get("status") != SOURCE_TERMINAL_STATUS
        or selection.get("selected_candidate_keys") is not None
        or selection.get("eligible_pairs") != []
        or selection.get("holdout_cases_read") != 0
        or selection.get("retuning_after_development") is not False
        or reference.get("admissible_individually") is not True
        or admissible_op93 != tuple(sorted(SOURCE_OP93_KEYS))
        or admissible_op80
    ):
        raise V6ProtocolError(
            "V6 requires the exact terminal V5 no-go with OP100 valid, only the "
            "two registered OP93 sources admissible, no OP80 admissible, and no "
            "holdout read"
        )


def _assert_development_source_path(path: Path, v5_run_dir: Path) -> None:
    expected_root = (v5_run_dir / "evidence" / "development").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(expected_root) or resolved.suffix != ".json":
        raise V6ProtocolError("V6 may import only V5 development evidence")


def _load_v5_development_read_only(
    source_plan: Any,
    v5_run_dir: Path,
    mode: str,
) -> dict[tuple[str, int], dict[str, Any]]:
    """Validate every V5 development proof without invoking V5 pruning code."""

    jobs = tuple(
        (candidate, seed)
        for candidate in source_plan.candidates
        for seed in DEVELOPMENT_SEEDS
    )
    evidence: dict[tuple[str, int], dict[str, Any]] = {}
    for candidate, seed in jobs:
        path = v5._evidence_path(  # noqa: SLF001
            v5_run_dir, "development", candidate.key, seed
        )
        _assert_development_source_path(path, v5_run_dir)
        if not path.is_file():
            raise V6ProtocolError(
                f"V5 development is incomplete: {candidate.key}/{seed}"
            )
        try:
            evidence[(candidate.key, seed)] = v5._validate_evidence(  # noqa: SLF001
                _read_json(path),
                plan=source_plan,
                run_dir=v5_run_dir,
                stage="development",
                candidate=candidate,
                seed=seed,
                mode=mode,
            )
        except Exception as exc:
            raise V6ProtocolError("Invalid V5 development proof") from exc
    try:
        v5._validate_progress_if_present(  # noqa: SLF001
            source_plan, v5_run_dir, "development", len(jobs)
        )
    except Exception as exc:
        raise V6ProtocolError("Invalid V5 development progress") from exc
    progress = _read_json(v5_run_dir / "development_progress.json")
    if (
        progress.get("status") != "complete"
        or progress.get("completed_case_count") != len(jobs)
        or progress.get("expected_case_count") != len(jobs)
    ):
        raise V6ProtocolError("V5 development is not terminal and complete")
    return evidence


def _source_reference(
    *,
    v5_plan_dir: Path,
    v5_run_dir: Path,
    v5_sidecar_root: Path,
    allow_test_source: bool,
) -> tuple[
    dict[str, Any],
    Any,
    dict[tuple[str, int], dict[str, Any]],
]:
    """Revalidate the full V5 development no-go without reading any holdout."""

    v5_plan_dir = v5_plan_dir.resolve()
    v5_run_dir = v5_run_dir.resolve()
    v5_sidecar_root = v5_sidecar_root.resolve()
    _assert_v5_holdout_unseen(v5_run_dir, v5_sidecar_root)
    try:
        source_plan = v5.validate_plan(
            v5_plan_dir,
            verify_runtime_dependencies=not allow_test_source,
            allow_test_source=allow_test_source,
        )
        mode = v5._registered_execution_mode(source_plan, v5_run_dir)  # noqa: SLF001
        evidence = _load_v5_development_read_only(
            source_plan, v5_run_dir, mode
        )
        expected = v5._build_development_selection(  # noqa: SLF001
            source_plan, evidence, execution_mode=mode
        )
    except Exception as exc:
        raise V6ProtocolError("The V5 development source does not revalidate") from exc
    selection_path = v5_run_dir / "development_selection.json"
    if not selection_path.is_file():
        raise V6ProtocolError(
            "V6 is dormant until V5 writes a terminal development selection"
        )
    selection = _read_json(selection_path)
    if selection != expected:
        raise V6ProtocolError("The signed V5 development result is not reproducible")
    _verify_signature(selection, "selection_signature", "V5 development selection")
    _validate_terminal_v5_selection(selection)
    if not allow_test_source and (
        mode != v5.OFFICIAL_EXECUTION_MODE
        or selection.get("publishable") is not True
        or len(evidence) != 210
    ):
        raise V6ProtocolError("Only the complete official 210-case V5 no-go is usable")
    if allow_test_source and mode not in {
        v5.OFFICIAL_EXECUTION_MODE,
        v5.TEST_ONLY_EXECUTION_MODE,
    }:
        raise V6ProtocolError("Unknown V5 source execution mode")

    imported_keys = ("op100_source", *SOURCE_OP93_KEYS)
    imported_index: list[dict[str, Any]] = []
    for candidate_key in imported_keys:
        for seed in DEVELOPMENT_SEEDS:
            path = v5._evidence_path(  # noqa: SLF001
                v5_run_dir, "development", candidate_key, seed
            ).resolve()
            _assert_development_source_path(path, v5_run_dir)
            row = evidence[(candidate_key, seed)]
            imported_index.append(
                {
                    "candidate_key": candidate_key,
                    "seed": seed,
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "evidence_signature": row["evidence_signature"],
                }
            )

    run_manifest_path = v5_run_dir / "run_manifest.json"
    progress_path = v5_run_dir / "development_progress.json"
    reference = {
        "protocol": "signed_v5_terminal_development_no_go",
        "plan_dir": str(v5_plan_dir),
        "plan_manifest": str((v5_plan_dir / "refinement_plan.json").resolve()),
        "plan_manifest_sha256": sha256_file(
            v5_plan_dir / "refinement_plan.json"
        ),
        "plan_signature": source_plan.manifest["plan_signature"],
        "run_dir": str(v5_run_dir),
        "run_manifest": str(run_manifest_path.resolve()),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "run_signature": _read_json(run_manifest_path)["run_signature"],
        "development_progress": str(progress_path.resolve()),
        "development_progress_sha256": sha256_file(progress_path),
        "development_selection": str(selection_path.resolve()),
        "development_selection_sha256": sha256_file(selection_path),
        "development_selection_signature": selection["selection_signature"],
        "development_status": SOURCE_TERMINAL_STATUS,
        "development_evidence_case_count": len(evidence),
        "development_evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "imported_development_evidence": imported_index,
        "imported_development_evidence_index_sha256": stable_sha256(imported_index),
        "execution_mode": mode,
        "holdout_non_use_audit": {
            "checked_paths": [
                str(path.resolve()) for path in _v5_holdout_forbidden_paths(v5_run_dir)
            ],
            "all_absent": True,
            "sidecar_root": str(v5_sidecar_root),
            "sidecar_absent_or_empty": True,
            "holdout_cases_read_reported_by_v5": 0,
        },
    }
    # Close the read-only audit window: a V5 holdout or sidecar appearing while
    # the 210 development proofs were being reopened invalidates the source.
    _assert_v5_holdout_unseen(v5_run_dir, v5_sidecar_root)
    return reference, source_plan, evidence


def _source_graph_and_lanes(source_plan: Any) -> tuple[dict[str, Any], Any]:
    item = source_plan.manifest["inventory"]["op100_source"]
    graph_path = (source_plan.plan_dir / item["graph_path"]).resolve()
    if sha256_file(graph_path) != item["graph_sha256"]:
        raise V6ProtocolError("The V5 OP100 graph changed")
    v3_plan = _read_json(Path(source_plan.manifest["source"]["v3_plan"]["path"]))
    lanes = v4._base_lane_scope(v3_plan)  # noqa: SLF001
    if sum(len(rows) for rows in lanes.values()) != 18:
        raise V6ProtocolError("V6 requires the exact same 18 supplier lanes")
    return _read_json(graph_path), lanes


def _selection_contract() -> dict[str, Any]:
    return copy.deepcopy(v5._selection_contract())  # noqa: SLF001


def _holdout_contract() -> dict[str, Any]:
    return {
        "seeds_sealed_and_unread": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "holdout_execution_supported_by_this_module": False,
        "authorization_rule": (
            "a successful V6 development selection requires a separate protocol "
            "frozen before any holdout execution"
        ),
        "failure_rule": "publish_no_go_without_holdout",
    }


def _execution_contract(source_plan: Any) -> dict[str, Any]:
    contract = copy.deepcopy(source_plan.manifest["execution_contract"])
    contract.update(
        {
            "changed_dimension": "planned_supplier_lead_time_days_only",
            "quality_incident": False,
            "availability_incident": False,
            "capacity_override": False,
            "state_dependent_risk": False,
            "v5_development_engine_reruns": 0,
            "v6_new_development_engine_runs": EXPECTED_NEW_DEVELOPMENT_CASES,
            "holdout_engine_runs": 0,
            "maximum_workers": 2,
        }
    )
    return contract


def _cohort_contract() -> dict[str, Any]:
    return {
        "development_common_random_numbers": list(DEVELOPMENT_SEEDS),
        "v5_op100_and_op93_proofs_reused": list(DEVELOPMENT_SEEDS),
        "v5_op80_proofs_not_reused_for_v6_acceptance": True,
        "holdout_carried_forward_sealed_unread": list(EXPECTED_HOLDOUT_SEEDS),
    }


def _candidate_design_contract() -> dict[str, Any]:
    return {
        "scientific_basis": (
            "exact same-cohort product-component recombination; screening "
            "only until both points are executed"
        ),
        "source_op93_keys": list(SOURCE_OP93_KEYS),
        "op80_exact_grid": [
            {
                "key": key,
                "offset_days_268091": left,
                "offset_days_268967": right,
                "evidence_mode": "execute",
            }
            for key, left, right in OP80_GRID
        ],
        "grid_expansion_allowed": False,
        "new_candidate_count": len(OP80_GRID),
        "fractional_offsets_are_model_parameters_not_operational_precision_claims": True,
    }


def prepare_plan(
    output_dir: Path,
    *,
    v5_plan_dir: Path,
    v5_run_dir: Path,
    v5_sidecar_root: Path,
    allow_test_source: bool = False,
) -> Path:
    """Create an immutable V6 plan; never execute the simulation engine."""

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite V6 plan: {output_dir}")
    source_ref, source_plan, _evidence = _source_reference(
        v5_plan_dir=v5_plan_dir,
        v5_run_dir=v5_run_dir,
        v5_sidecar_root=v5_sidecar_root,
        allow_test_source=allow_test_source,
    )
    protected = (
        source_plan.plan_dir,
        Path(source_ref["run_dir"]),
        Path(source_ref["holdout_non_use_audit"]["sidecar_root"]),
    )
    if any(_paths_overlap(output_dir, path) for path in protected):
        raise V6ProtocolError("V6 plan overlaps a protected V5 source")

    candidates = _all_candidates()
    base_graph, lanes = _source_graph_and_lanes(source_plan)
    temporary = output_dir.parent / f".{output_dir.name}.building-{os.getpid()}"
    if temporary.exists():
        raise FileExistsError(f"Temporary V6 plan already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        inventory: dict[str, dict[str, str]] = {}
        source_by_key = {candidate.key: candidate for candidate in source_plan.candidates}
        for candidate in candidates:
            graph, changes = v4._apply_offsets(  # noqa: SLF001
                base_graph,
                lanes,
                candidate.offset_days_268091,
                candidate.offset_days_268967,
            )
            graph_path = temporary / "graphs" / f"{candidate.key}.json"
            ledger_path = temporary / "ledgers" / f"{candidate.key}.json"
            _write_json(graph_path, graph)
            if candidate.evidence_mode == "reuse_v5_development":
                source_candidate = source_by_key.get(candidate.source_operating_point_id)
                if source_candidate is None:
                    raise V6ProtocolError("V5 imported candidate is missing")
                source_item = source_plan.manifest["inventory"][source_candidate.key]
                source_graph_path = (
                    source_plan.plan_dir / source_item["graph_path"]
                ).resolve()
                if _read_json(source_graph_path) != graph:
                    raise V6ProtocolError("V6 imported graph differs from V5")
            ledger = {
                "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
                "candidate": _candidate_payload(candidate),
                "changed_dimension": "planned_supplier_lead_time_days_only",
                "changes": changes,
            }
            _write_json(ledger_path, ledger)
            inventory[candidate.key] = {
                "graph_path": graph_path.relative_to(temporary).as_posix(),
                "graph_sha256": sha256_file(graph_path),
                "ledger_path": ledger_path.relative_to(temporary).as_posix(),
                "ledger_sha256": sha256_file(ledger_path),
            }

        cases = [
            {
                "stage": "development",
                "candidate_key": candidate.key,
                "seed": seed,
                "evidence_mode": candidate.evidence_mode,
            }
            for candidate in candidates
            for seed in DEVELOPMENT_SEEDS
        ]
        module_path = Path(__file__).resolve()
        manifest: dict[str, Any] = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "status": "frozen_before_v6_development",
            "interpretation": INTERPRETATION,
            "supersedes": {
                "protocol": "v5_development_no_go",
                "v5_plan_signature": source_ref["plan_signature"],
                "v5_selection_signature": source_ref[
                    "development_selection_signature"
                ],
                "v5_status": SOURCE_TERMINAL_STATUS,
                "modifies_v5_artifacts": False,
            },
            "source": copy.deepcopy(source_plan.manifest["source"]),
            "v5_no_go_source": source_ref,
            "source_hashes": {
                **copy.deepcopy(source_plan.manifest["source_hashes"]),
                "v6_driver_sha256": sha256_file(module_path),
            },
            "runtime_dependencies": copy.deepcopy(
                source_plan.manifest["runtime_dependencies"]
            ),
            "cohorts": _cohort_contract(),
            "candidate_design": _candidate_design_contract(),
            "candidates": [_candidate_payload(candidate) for candidate in candidates],
            "inventory": inventory,
            "development_cases": cases,
            "expected_development_case_count": EXPECTED_DEVELOPMENT_CASES,
            "reused_development_case_count": EXPECTED_IMPORTED_DEVELOPMENT_CASES,
            "new_development_case_count": EXPECTED_NEW_DEVELOPMENT_CASES,
            "selection_contract": _selection_contract(),
            "holdout_contract": _holdout_contract(),
            "execution_contract": _execution_contract(source_plan),
        }
        manifest["plan_signature"] = stable_sha256(manifest)
        _write_json(temporary / "refinement_plan.json", manifest)
        refreshed_ref, _refreshed_plan, _refreshed_evidence = _source_reference(
            v5_plan_dir=v5_plan_dir,
            v5_run_dir=v5_run_dir,
            v5_sidecar_root=v5_sidecar_root,
            allow_test_source=allow_test_source,
        )
        if refreshed_ref != source_ref:
            raise V6ProtocolError("V5 source changed while freezing the V6 plan")
        os.replace(temporary, output_dir)
    except BaseException:
        if temporary.exists():
            import shutil

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
        raise V6ProtocolError("Invalid V6 plan signature")
    expected_fields = {
        "schema_version",
        "status",
        "interpretation",
        "supersedes",
        "source",
        "v5_no_go_source",
        "source_hashes",
        "runtime_dependencies",
        "cohorts",
        "candidate_design",
        "candidates",
        "inventory",
        "development_cases",
        "expected_development_case_count",
        "reused_development_case_count",
        "new_development_case_count",
        "selection_contract",
        "holdout_contract",
        "execution_contract",
        "plan_signature",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "frozen_before_v6_development"
        or manifest.get("interpretation") != INTERPRETATION
    ):
        raise V6ProtocolError("Unexpected V6 plan field or status")

    declared = manifest.get("v5_no_go_source") or {}
    actual, source_plan, _source_evidence = _source_reference(
        v5_plan_dir=Path(str(declared.get("plan_dir") or ".")),
        v5_run_dir=Path(str(declared.get("run_dir") or ".")),
        v5_sidecar_root=Path(
            str((declared.get("holdout_non_use_audit") or {}).get("sidecar_root") or ".")
        ),
        allow_test_source=allow_test_source,
    )
    if declared != actual:
        raise V6ProtocolError("V5 source changed after V6 plan freeze")
    if manifest.get("supersedes") != {
        "protocol": "v5_development_no_go",
        "v5_plan_signature": actual["plan_signature"],
        "v5_selection_signature": actual["development_selection_signature"],
        "v5_status": SOURCE_TERMINAL_STATUS,
        "modifies_v5_artifacts": False,
    }:
        raise V6ProtocolError("Invalid V6 supersession contract")
    expected_source_hashes = {
        **copy.deepcopy(source_plan.manifest["source_hashes"]),
        "v6_driver_sha256": sha256_file(Path(__file__).resolve()),
    }
    if (
        manifest.get("source") != source_plan.manifest["source"]
        or manifest.get("source_hashes") != expected_source_hashes
        or manifest.get("runtime_dependencies")
        != source_plan.manifest["runtime_dependencies"]
        or manifest.get("cohorts") != _cohort_contract()
        or manifest.get("candidate_design") != _candidate_design_contract()
    ):
        raise V6ProtocolError("V6 pinned source or design contract changed")

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
    if candidates != _all_candidates():
        raise V6ProtocolError("V6 candidates changed")
    expected_cases = [
        {
            "stage": "development",
            "candidate_key": candidate.key,
            "seed": seed,
            "evidence_mode": candidate.evidence_mode,
        }
        for candidate in candidates
        for seed in DEVELOPMENT_SEEDS
    ]
    if (
        manifest.get("development_cases") != expected_cases
        or manifest.get("expected_development_case_count")
        != EXPECTED_DEVELOPMENT_CASES
        or manifest.get("reused_development_case_count")
        != EXPECTED_IMPORTED_DEVELOPMENT_CASES
        or manifest.get("new_development_case_count")
        != EXPECTED_NEW_DEVELOPMENT_CASES
        or manifest.get("selection_contract") != _selection_contract()
        or manifest.get("holdout_contract") != _holdout_contract()
        or manifest.get("execution_contract") != _execution_contract(source_plan)
    ):
        raise V6ProtocolError("V6 frozen contract changed")

    base_graph, lanes = _source_graph_and_lanes(source_plan)
    inventory = manifest.get("inventory") or {}
    if set(inventory) != {candidate.key for candidate in candidates}:
        raise V6ProtocolError("Invalid V6 graph inventory")
    for candidate in candidates:
        item = inventory[candidate.key]
        graph_path = (plan_dir / str(item.get("graph_path"))).resolve()
        ledger_path = (plan_dir / str(item.get("ledger_path"))).resolve()
        if (
            set(item)
            != {"graph_path", "graph_sha256", "ledger_path", "ledger_sha256"}
            or not graph_path.is_relative_to(plan_dir)
            or not ledger_path.is_relative_to(plan_dir)
            or item["graph_path"] != f"graphs/{candidate.key}.json"
            or item["ledger_path"] != f"ledgers/{candidate.key}.json"
            or sha256_file(graph_path) != item["graph_sha256"]
            or sha256_file(ledger_path) != item["ledger_sha256"]
        ):
            raise V6ProtocolError(f"V6 graph/ledger changed: {candidate.key}")
        expected_graph, expected_changes = v4._apply_offsets(  # noqa: SLF001
            base_graph,
            lanes,
            candidate.offset_days_268091,
            candidate.offset_days_268967,
        )
        if _read_json(graph_path) != expected_graph:
            raise V6ProtocolError(f"V6 canonical graph changed: {candidate.key}")
        expected_ledger = {
            "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
            "candidate": _candidate_payload(candidate),
            "changed_dimension": "planned_supplier_lead_time_days_only",
            "changes": expected_changes,
        }
        if _read_json(ledger_path) != expected_ledger:
            raise V6ProtocolError(f"V6 canonical ledger changed: {candidate.key}")
    if verify_runtime_dependencies:
        try:
            v4._assert_runtime_dependencies_current(  # noqa: SLF001
                v4.ValidatedPlan(plan_dir, manifest, candidates)
            )
        except Exception as exc:
            raise V6ProtocolError("Pinned execution dependencies changed") from exc
    return ValidatedPlan(plan_dir, manifest, candidates)


def _case_key(candidate_key: str, seed: int) -> str:
    return f"development|{candidate_key}|{seed}"


def _evidence_path(run_dir: Path, candidate_key: str, seed: int) -> Path:
    digest = hashlib.sha256(_case_key(candidate_key, seed).encode("utf-8")).hexdigest()[:24]
    return run_dir / "evidence" / "development" / f"{digest}.json"


def _run_manifest(plan: ValidatedPlan, mode: str) -> dict[str, Any]:
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_signature": plan.manifest["plan_signature"],
        "stage_supported": "development_only",
        "execution_mode": mode,
        "expected_development_case_count": EXPECTED_DEVELOPMENT_CASES,
        "expected_new_engine_case_count": EXPECTED_NEW_DEVELOPMENT_CASES,
        "holdout_execution_supported": False,
    }
    return {**unsigned, "run_signature": stable_sha256(unsigned)}


def _registered_execution_mode(plan: ValidatedPlan, run_dir: Path) -> str:
    manifest = _read_json(run_dir / "run_manifest.json")
    for mode in (OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE):
        if manifest == _run_manifest(plan, mode):
            return mode
    raise V6ProtocolError("Invalid V6 run registration")


def _validate_run_location(plan: ValidatedPlan, run_dir: Path) -> None:
    source = plan.manifest["v5_no_go_source"]
    protected = (
        plan.plan_dir,
        Path(source["plan_dir"]),
        Path(source["run_dir"]),
        Path(source["holdout_non_use_audit"]["sidecar_root"]),
    )
    if any(_paths_overlap(run_dir, path) for path in protected):
        raise V6ProtocolError("V6 run overlaps a plan or protected V5 source")


def _register_run(plan: ValidatedPlan, run_dir: Path, mode: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run_manifest.json"
    expected = _run_manifest(plan, mode)
    if path.exists():
        if _read_json(path) != expected:
            raise V6ProtocolError("Run directory belongs to another V6 plan")
    elif any(entry.name != ".v6.lock" for entry in run_dir.iterdir()):
        raise V6ProtocolError("Refusing an unregistered non-empty V6 run directory")
    else:
        _write_json(path, expected)


@contextmanager
def _run_lock(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / ".v6.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise V6ProtocolError("Another V6 process owns this run directory") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def _source_evidence(
    plan: ValidatedPlan, candidate: Candidate, seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    index = {
        (str(row["candidate_key"]), int(row["seed"])): row
        for row in plan.manifest["v5_no_go_source"][
            "imported_development_evidence"
        ]
    }
    source_key = candidate.source_operating_point_id
    ref = index.get((source_key, seed))
    if ref is None:
        raise V6ProtocolError("Missing registered V5 development proof")
    path = Path(str(ref["path"])).resolve()
    source_run = Path(plan.manifest["v5_no_go_source"]["run_dir"])
    _assert_development_source_path(path, source_run)
    if sha256_file(path) != ref["sha256"]:
        raise V6ProtocolError("Imported V5 evidence hash changed")
    payload = _read_json(path)
    _verify_signature(payload, "evidence_signature", "imported V5 evidence")
    if (
        payload.get("schema_version") != v5.EVIDENCE_SCHEMA_VERSION
        or payload.get("stage") != "development"
        or payload.get("candidate_key") != source_key
        or int(payload.get("seed") or -1) != seed
        or payload.get("evidence_signature") != ref["evidence_signature"]
        or payload.get("shipment_trace") is not None
    ):
        raise V6ProtocolError("Imported V5 evidence is incompatible")
    return payload, dict(ref)


EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "plan_signature",
        "stage",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "evidence_mode",
        "graph_sha256",
        "engine_sha256",
        "metrics",
        "source_evidence",
        "executor_proof",
        "shipment_trace",
        "valid",
        "created_at_utc",
        "evidence_signature",
    }
)


def _validate_evidence(
    payload: Mapping[str, Any],
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: Candidate,
    seed: int,
    mode: str,
) -> dict[str, Any]:
    _verify_signature(payload, "evidence_signature", "V6 evidence")
    if (
        set(payload) != EVIDENCE_FIELDS
        or payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("stage") != "development"
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or int(payload.get("seed") or -1) != seed
        or payload.get("evidence_mode") != candidate.evidence_mode
        or payload.get("graph_sha256")
        != plan.manifest["inventory"][candidate.key]["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("valid") is not True
        or payload.get("shipment_trace") is not None
    ):
        raise V6ProtocolError(f"V6 evidence mismatch: {candidate.key}/{seed}")
    if candidate.evidence_mode == "reuse_v5_development":
        source, ref = _source_evidence(plan, candidate, seed)
        if payload.get("source_evidence") != ref or payload.get("executor_proof") is not None:
            raise V6ProtocolError("V6 imported proof is not the exact V5 proof")
        if v4._normalize_metrics(source.get("metrics") or {}) != v4._normalize_metrics(  # noqa: SLF001
            payload.get("metrics") or {}
        ):
            raise V6ProtocolError("Imported V5/V6 metrics differ")
    else:
        proof = payload.get("executor_proof")
        if payload.get("source_evidence") is not None or not isinstance(proof, Mapping):
            raise V6ProtocolError("Executed V6 evidence lacks executor proof")
        expected_kind = (
            "coarse_execute_candidate"
            if mode == OFFICIAL_EXECUTION_MODE
            else "injected_test_executor"
        )
        if proof.get("kind") != expected_kind:
            raise V6ProtocolError("V6 executor proof mode changed")
        raw = (
            proof.get("raw_evidence")
            if expected_kind == "coarse_execute_candidate"
            else proof.get("raw_payload")
        )
        adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)
        try:
            raw_metrics = (
                v4._validate_coarse_executor_evidence(  # noqa: SLF001
                    raw, candidate=candidate, seed=seed, plan=adapter
                )
                if expected_kind == "coarse_execute_candidate"
                else v4._normalize_metrics((raw or {}).get("metrics") or raw or {})  # noqa: SLF001
            )
        except Exception as exc:
            raise V6ProtocolError("Underlying V6 executor proof is invalid") from exc
        if raw_metrics != v4._normalize_metrics(payload.get("metrics") or {}):  # noqa: SLF001
            raise V6ProtocolError("V6 outer/executor metrics differ")
    result = dict(payload)
    result["metrics"] = v4._normalize_metrics(payload.get("metrics") or {})  # noqa: SLF001
    return result


def _jobs(plan: ValidatedPlan) -> tuple[tuple[Candidate, int], ...]:
    return tuple(
        (candidate, seed)
        for candidate in plan.candidates
        for seed in DEVELOPMENT_SEEDS
    )


def _progress(
    plan: ValidatedPlan,
    run_dir: Path,
    completed: int,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.development.progress",
        "plan_signature": plan.manifest["plan_signature"],
        "stage": "development",
        "status": status,
        "completed_case_count": completed,
        "expected_case_count": EXPECTED_DEVELOPMENT_CASES,
        "execution_mode": _registered_execution_mode(plan, run_dir),
        "publishable": _registered_execution_mode(plan, run_dir)
        == OFFICIAL_EXECUTION_MODE,
        "error": error,
        "updated_at_utc": _now(),
    }
    payload = {**unsigned, "progress_signature": stable_sha256(unsigned)}
    _write_json(run_dir / "development_progress.json", payload)
    return payload


def _collect(
    plan: ValidatedPlan,
    run_dir: Path,
    jobs: Sequence[tuple[Candidate, int]],
    mode: str,
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[tuple[Candidate, int]]]:
    directory = run_dir / "evidence" / "development"
    expected_names = {
        _evidence_path(run_dir, candidate.key, seed).name
        for candidate, seed in jobs
    }
    if directory.exists():
        actual = {path.name for path in directory.glob("*.json") if path.is_file()}
        if not actual.issubset(expected_names):
            raise V6ProtocolError("Unexpected V6 development evidence exists")
    completed: dict[tuple[str, int], dict[str, Any]] = {}
    missing: list[tuple[Candidate, int]] = []
    for candidate, seed in jobs:
        path = _evidence_path(run_dir, candidate.key, seed)
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


def run_development(
    plan_dir: Path,
    run_dir: Path,
    *,
    executor: Executor | None = None,
    max_workers: int = 2,
    test_only: bool = False,
) -> dict[str, Any]:
    """Execute/resume V6 development; no holdout code path exists."""

    if max_workers not in {1, 2}:
        raise V6ProtocolError("V6 permits one or two workers")
    if (executor is None) is test_only:
        raise V6ProtocolError("Injected executors require explicit test_only=True")
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    _validate_run_location(plan, run_dir)
    _assert_local_holdout_unseen(run_dir)
    jobs = _jobs(plan)
    selected_executor = executor or v4._real_executor  # noqa: SLF001
    adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)
    source_ref = plan.manifest["v5_no_go_source"]

    def execute(candidate: Candidate, seed: int) -> dict[str, Any]:
        source_evidence: Mapping[str, Any] | None = None
        executor_proof: Mapping[str, Any] | None = None
        if candidate.evidence_mode == "reuse_v5_development":
            source_payload, source_evidence = _source_evidence(plan, candidate, seed)
            metrics = v4._normalize_metrics(  # noqa: SLF001
                source_payload.get("metrics") or {}
            )
        else:
            _assert_v5_holdout_unseen(
                Path(source_ref["run_dir"]),
                Path(source_ref["holdout_non_use_audit"]["sidecar_root"]),
            )
            if mode == OFFICIAL_EXECUTION_MODE:
                v4._assert_runtime_dependencies_current(adapter)  # noqa: SLF001
            digest = hashlib.sha256(
                _case_key(candidate.key, seed).encode("utf-8")
            ).hexdigest()[:24]
            attempt_root = (
                run_dir
                / "engine_attempts"
                / "development"
                / digest
                / f"attempt-{os.getpid()}-{os.urandom(8).hex()}"
            )
            raw = selected_executor(
                candidate=candidate,
                seed=seed,
                stage="development",
                run_dir=run_dir,
                plan=plan.manifest,
                validated_plan=adapter,
                attempt_root=attempt_root,
            )
            if not isinstance(raw, Mapping):
                raise V6ProtocolError("V6 executor must return a mapping")
            metrics, executor_proof = v4._executor_output(  # noqa: SLF001
                raw,
                candidate=candidate,
                seed=seed,
                plan=adapter,
                injected=test_only,
            )
        unsigned = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "plan_signature": plan.manifest["plan_signature"],
            "stage": "development",
            "candidate_key": candidate.key,
            "candidate_id": candidate.candidate_id,
            "target_group": candidate.target_group,
            "seed": seed,
            "evidence_mode": candidate.evidence_mode,
            "graph_sha256": plan.manifest["inventory"][candidate.key][
                "graph_sha256"
            ],
            "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
            "metrics": metrics,
            "source_evidence": source_evidence,
            "executor_proof": executor_proof,
            "shipment_trace": None,
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
        _write_json(_evidence_path(run_dir, candidate.key, seed), payload)
        if executor_proof and executor_proof.get("kind") == "coarse_execute_candidate":
            v4._prune_real_executor_case(  # noqa: SLF001
                executor_proof, run_dir, candidate, seed
            )
        return payload

    with _run_lock(run_dir):
        _register_run(plan, run_dir, mode)
        _assert_local_holdout_unseen(run_dir)
        completed, missing = _collect(plan, run_dir, jobs, mode)
        _progress(plan, run_dir, len(completed), "running")
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
                        next_candidate, next_seed = next(pending)
                    except StopIteration:
                        continue
                    futures[pool.submit(execute, next_candidate, next_seed)] = (
                        next_candidate,
                        next_seed,
                    )
            # Reopen the complete signed V5 source after the final engine call.
            # No completed V6 development may be published across a source race.
            validate_plan(
                plan.plan_dir,
                verify_runtime_dependencies=not test_only,
                allow_test_source=test_only,
            )
        except BaseException as exc:
            completed, _ = _collect(plan, run_dir, jobs, mode)
            _progress(plan, run_dir, len(completed), "failed", str(exc))
            raise
        if len(completed) != EXPECTED_DEVELOPMENT_CASES:
            raise V6ProtocolError("V6 development evidence matrix is incomplete")
        _assert_local_holdout_unseen(run_dir)
        return _progress(plan, run_dir, len(completed), "complete")


def _build_development_selection(
    plan: ValidatedPlan,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    execution_mode: str,
) -> dict[str, Any]:
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    try:
        v4._validate_paired_demand(  # noqa: SLF001
            evidence, tuple(by_key), DEVELOPMENT_SEEDS
        )
    except Exception as exc:
        raise V6ProtocolError("V6 paired development demand changed") from exc
    summaries = {
        key: v4._candidate_summary(  # noqa: SLF001
            candidate,
            [evidence[(key, seed)] for seed in DEVELOPMENT_SEEDS],
            True,
        )
        for key, candidate in by_key.items()
    }
    reference = summaries["op100_source"]
    highs = [
        summaries[key]
        for key in SOURCE_OP93_KEYS
        if summaries[key]["admissible_individually"]
    ]
    lows = [
        summary
        for key, summary in summaries.items()
        if by_key[key].target_group == "op_80"
        and summary["admissible_individually"]
    ]
    eligible: list[dict[str, Any]] = []
    if reference["admissible_individually"]:
        for high in highs:
            for low in lows:
                high_candidate = by_key[high["candidate"]["key"]]
                low_candidate = by_key[low["candidate"]["key"]]
                monotone = (
                    low_candidate.offset_days_268091
                    >= high_candidate.offset_days_268091
                    and low_candidate.offset_days_268967
                    >= high_candidate.offset_days_268967
                )
                pooled, joint, pf967 = v4._ordered_pair(  # noqa: SLF001
                    reference, high, low
                )
                if monotone and pooled and joint >= MIN_ORDERED_SEEDS:
                    eligible.append(
                        {
                            "op93_candidate_key": high_candidate.key,
                            "op80_candidate_key": low_candidate.key,
                            "same_seed_joint_strict_order_count": joint,
                            "same_seed_pf268967_strict_order_count": pf967,
                            "selection_score": list(
                                v4._pair_score(  # noqa: SLF001
                                    high,
                                    low,
                                    joint_order_count=joint,
                                    pf967_order_count=pf967,
                                )
                            ),
                        }
                    )
    eligible.sort(key=lambda row: tuple(row["selection_score"]))
    winner = eligible[0] if eligible else None
    unsigned = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "v5_selection_signature": plan.manifest["supersedes"][
            "v5_selection_signature"
        ],
        "status": SUCCESS_STATUS if winner else FAIL_STATUS,
        "development_seeds": list(DEVELOPMENT_SEEDS),
        "holdout_seeds_sealed_and_unread": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "holdout_execution_supported_by_this_module": False,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "new_candidate_evidence_case_count": EXPECTED_NEW_DEVELOPMENT_CASES,
        "v5_imported_development_evidence_case_count": (
            EXPECTED_IMPORTED_DEVELOPMENT_CASES
        ),
        "v5_candidate_engine_rerun_count": 0,
        "development_evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "candidate_summaries": summaries,
        "eligible_pairs": eligible,
        "selected_candidate_keys": (
            {
                "op_100": "op100_source",
                "op_93": winner["op93_candidate_key"],
                "op_80": winner["op80_candidate_key"],
            }
            if winner
            else None
        ),
        "selection_contract": plan.manifest["selection_contract"],
        "retuning_after_development": False,
        "next_step": (
            "freeze_a_separate_holdout_protocol_before_execution"
            if winner
            else "publish_development_no_go_without_holdout"
        ),
    }
    return {**unsigned, "selection_signature": stable_sha256(unsigned)}


def finalize_development(
    plan_dir: Path,
    run_dir: Path,
    *,
    test_only: bool = False,
) -> dict[str, Any]:
    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    _validate_run_location(plan, run_dir)
    _assert_local_holdout_unseen(run_dir)
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    with _run_lock(run_dir):
        if _read_json(run_dir / "run_manifest.json") != _run_manifest(plan, mode):
            raise V6ProtocolError("Official/test-only V6 registrations differ")
        evidence, missing = _collect(plan, run_dir, _jobs(plan), mode)
        if missing or len(evidence) != EXPECTED_DEVELOPMENT_CASES:
            raise V6ProtocolError("V6 development is not complete")
        # The source can change while evidence is reopened.  Revalidate it once
        # more immediately before publishing the signed selection.
        validate_plan(
            plan.plan_dir,
            verify_runtime_dependencies=not test_only,
            allow_test_source=test_only,
        )
        _assert_local_holdout_unseen(run_dir)
        result = _build_development_selection(
            plan, evidence, execution_mode=mode
        )
        output = run_dir / "development_selection.json"
        if output.exists():
            if _read_json(output) != result:
                raise V6ProtocolError("Existing V6 development finalization differs")
        else:
            _write_json(output, result)
        _assert_local_holdout_unseen(run_dir)
        return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Create the conditional signed V6 plan")
    plan.add_argument("--output-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    plan.add_argument("--v5-plan-dir", type=Path, default=DEFAULT_V5_PLAN)
    plan.add_argument("--v5-run-dir", type=Path, default=DEFAULT_V5_RUN)
    plan.add_argument("--v5-sidecar-root", type=Path, default=DEFAULT_V5_SIDECAR)
    validate = sub.add_parser("validate", help="Revalidate a signed V6 plan")
    validate.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run = sub.add_parser("run-development", help="Execute/resume V6 development")
    run.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run.add_argument("--workers", type=int, choices=(1, 2), default=2)
    finalize = sub.add_parser(
        "finalize-development", help="Finalize complete V6 development"
    )
    finalize.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    finalize.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        print(
            prepare_plan(
                args.output_dir,
                v5_plan_dir=args.v5_plan_dir,
                v5_run_dir=args.v5_run_dir,
                v5_sidecar_root=args.v5_sidecar_root,
            )
        )
    elif args.command == "validate":
        print(validate_plan(args.plan_dir).manifest["plan_signature"])
    elif args.command == "run-development":
        print(
            json.dumps(
                run_development(
                    args.plan_dir,
                    args.run_dir,
                    max_workers=args.workers,
                ),
                ensure_ascii=False,
            )
        )
    else:
        print(
            json.dumps(
                finalize_development(args.plan_dir, args.run_dir),
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
