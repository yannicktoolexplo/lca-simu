#!/usr/bin/env python3
"""Additive V5 operating-point refinement after the signed V4 development no-go.

V5 does not reinterpret or overwrite V4.  It imports the thirty signed V4
``op100_source`` development proofs, executes exactly six pre-registered lead-time
offset candidates on the same thirty development seeds, and applies the unchanged
V4 acceptance and paired-ordering rules.  The V4 holdout cohort may be carried
forward only while a strict non-use audit proves that no V4 holdout output exists.
After selection, the three selected states are executed once on that sealed cohort.

The public CLI never exposes an injected executor.  Tests can inject one only by
calling :func:`run_stage` with ``test_only=True``.
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


SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v5"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.development_selection"
HOLDOUT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.holdout_result"

DEVELOPMENT_SEEDS = v4.DEVELOPMENT_SEEDS
EXPECTED_HOLDOUT_SEEDS = v4.EXPECTED_HOLDOUT_SEEDS
INCIDENT_DESIGN_SEED = v4.INCIDENT_DESIGN_SEED
TARGETS = v4.TARGETS
DEVELOPMENT_INNER_BANDS = v4.DEVELOPMENT_INNER_BANDS
OUTER_BANDS = v4.OUTER_BANDS
REFERENCE_MINIMUM = v4.REFERENCE_MINIMUM
NON_SATURATION_LIMIT = v4.NON_SATURATION_LIMIT
MIN_ORDERED_SEEDS = v4.MIN_ORDERED_SEEDS
SERVICE_DAYS = v4.SERVICE_DAYS
PRODUCTS = v4.PRODUCTS
PRODUCT_FACTORY = v4.PRODUCT_FACTORY
BOOTSTRAP_REPLICATES = v4.BOOTSTRAP_REPLICATES
BOOTSTRAP_SEED = v4.BOOTSTRAP_SEED
DEMAND_REL_TOLERANCE = v4.DEMAND_REL_TOLERANCE
DEMAND_ABS_TOLERANCE = v4.DEMAND_ABS_TOLERANCE
PRODUCT_GAP_WARNING_PP = v4.PRODUCT_GAP_WARNING_PP
SHIPMENT_TRACE_SCHEMA_VERSION = v4.SHIPMENT_TRACE_SCHEMA_VERSION
SHIPMENT_TRACE_COMPRESSION = v4.SHIPMENT_TRACE_COMPRESSION
SHIPMENT_TRACE_FIELDS = v4.SHIPMENT_TRACE_FIELDS
SHIPMENT_TRACE_SOURCE_RELATIVE_PATH = v4.SHIPMENT_TRACE_SOURCE_RELATIVE_PATH
OFFICIAL_EXECUTION_MODE = "official_v5_additive_execute_candidate"
TEST_ONLY_EXECUTION_MODE = "test_only_v5_injected_executor"

OFFICIAL_V4_PLAN_SIGNATURE = (
    "b99e02fa56b10d8b72747ab2d7827cdcb284a7513586bb64c1e2a346845d982c"
)
OFFICIAL_V4_PLAN_SHA256 = (
    "f05cd536718dd4043bf472a1310ea1b66d226df1d91457263ac6d122658291e7"
)
OFFICIAL_V4_RUN_SIGNATURE = (
    "ea47d9d32bb662acdff90e63a0352381630f0045593fb4504139bd05bed3ab05"
)
OFFICIAL_V4_RUN_MANIFEST_SHA256 = (
    "074f1068ffce7616a38cd02c15bb7a98dd8812ea2af32f773c93e4938239ae0e"
)
OFFICIAL_V4_SELECTION_SIGNATURE = (
    "74afe36c3f294d3d74a84d0cdf1e22623570aaf65db0d905edf835f0f137f5fe"
)
OFFICIAL_V4_SELECTION_SHA256 = (
    "0f8a61874ad25a83900908ed271e24bf0cd6de2160d4122c55ecc71c0fd1b0b7"
)

# Pre-registered from the separable reconstruction of signed V4 development
# proofs.  The reconstruction is screening evidence only; these candidates must
# still be executed on every DEVELOPMENT_SEED before they can be selected.
OP93_GRID = (
    ("op93_v5_8p2_80p6", 8.2, 80.6),
    ("op93_v5_8p3_80p6", 8.3, 80.6),
    ("op93_v5_8p4_80p6", 8.4, 80.6),
)
OP80_GRID = (
    ("op80_v5_19p4_96p6", 19.4, 96.6),
    ("op80_v5_19p5_96p6", 19.5, 96.6),
    ("op80_v5_19p6_96p6", 19.6, 96.6),
)

SCREENING_PROJECTIONS = {
    "units": "service_ratio",
    "method": (
        "separable reconstruction from signed V4 development product components; "
        "used only to pre-register a small grid"
    ),
    "not_acceptance_evidence": True,
    "why_both_states_move": {
        "op80_only_search_domain": (
            "offset_268091=18.0..22.0 and offset_268967=94.0..98.0, step 0.1"
        ),
        "best_projected_joint_count_with_v4_op93_8p5_80p5": 20,
        "best_projected_joint_count_with_v4_op93_8p5_81p5": 19,
        "required_joint_count": MIN_ORDERED_SEEDS,
        "conclusion": "OP80 offsets alone did not satisfy the frozen order gate",
    },
    "op93": {
        "op93_v5_8p2_80p6": {
            "pooled_global": 0.93430,
            "median_global": 0.93651,
            "leave_one_out_global_min": 0.93280,
            "leave_one_out_global_max": 0.93697,
        },
        "op93_v5_8p3_80p6": {
            "pooled_global": 0.93327,
            "median_global": 0.93259,
            "leave_one_out_global_min": 0.93168,
            "leave_one_out_global_max": 0.93581,
        },
        "op93_v5_8p4_80p6": {
            "pooled_global": 0.93224,
            "median_global": 0.92996,
            "leave_one_out_global_min": 0.93057,
            "leave_one_out_global_max": 0.93465,
        },
    },
    "op80": {
        "op80_v5_19p4_96p6": {
            "pooled_global": 0.79924,
            "median_global": 0.80610,
            "leave_one_out_global_min": 0.79232,
            "leave_one_out_global_max": 0.80608,
        },
        "op80_v5_19p5_96p6": {
            "pooled_global": 0.79847,
            "median_global": 0.80451,
            "leave_one_out_global_min": 0.79152,
            "leave_one_out_global_max": 0.80552,
        },
        "op80_v5_19p6_96p6": {
            "pooled_global": 0.79769,
            "median_global": 0.80324,
            "leave_one_out_global_min": 0.79072,
            "leave_one_out_global_max": 0.80496,
        },
    },
    "projected_same_seed_joint_strict_order_count": {
        "op93_v5_8p2_80p6": {
            "op80_v5_19p4_96p6": 25,
            "op80_v5_19p5_96p6": 25,
            "op80_v5_19p6_96p6": 25,
        },
        "op93_v5_8p3_80p6": {
            "op80_v5_19p4_96p6": 25,
            "op80_v5_19p5_96p6": 25,
            "op80_v5_19p6_96p6": 24,
        },
        "op93_v5_8p4_80p6": {
            "op80_v5_19p4_96p6": 25,
            "op80_v5_19p5_96p6": 24,
            "op80_v5_19p6_96p6": 24,
        },
    },
}

EXPECTED_NEW_DEVELOPMENT_CASES = 6 * len(DEVELOPMENT_SEEDS)
EXPECTED_REUSED_DEVELOPMENT_CASES = len(DEVELOPMENT_SEEDS)
EXPECTED_DEVELOPMENT_CASES = (
    EXPECTED_NEW_DEVELOPMENT_CASES + EXPECTED_REUSED_DEVELOPMENT_CASES
)
EXPECTED_HOLDOUT_CASES = 3 * len(EXPECTED_HOLDOUT_SEEDS)

INTERPRETATION = (
    "Simulation hypotheses only; V5 is an additive pre-registered development "
    "extension after the signed V4 no-go. No observed supplier performance or "
    "incident probability is inferred."
)

DEFAULT_ARTIFACT_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
)
DEFAULT_PLAN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_plan_20260905_v5"
)
DEFAULT_RUN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_run_20260905_v5"
)


class V5ProtocolError(ValueError):
    """Raised when the additive V5 scientific contract is not exact."""


Candidate = v4.Candidate


@dataclass(frozen=True)
class ValidatedPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    candidates: tuple[Candidate, ...]


Executor = Callable[..., Mapping[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    return v4.stable_sha256(payload)


def sha256_file(path: Path) -> str:
    return v4.sha256_file(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return v4._read_json(path)  # noqa: SLF001 - pinned producer primitive
    except Exception as exc:
        raise V5ProtocolError(f"Invalid JSON artifact: {path}") from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v4._write_json(path, payload)  # noqa: SLF001 - atomic Windows-safe writer


def _verify_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise V5ProtocolError(f"Invalid {label} signature")
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
            "v5_op100_imported_from_v4",
            "op_100",
            0.0,
            0.0,
            "reuse_v4_development",
            "op100_source",
        )
    ]
    candidates.extend(
        Candidate(key, f"v5_{key}", "op_93", left, right, "execute", "")
        for key, left, right in OP93_GRID
    )
    candidates.extend(
        Candidate(key, f"v5_{key}", "op_80", left, right, "execute", "")
        for key, left, right in OP80_GRID
    )
    if len({candidate.key for candidate in candidates}) != len(candidates):
        raise V5ProtocolError("Duplicate V5 candidate key")
    return tuple(candidates)


def _selection_contract() -> dict[str, Any]:
    return {
        "primary_measure": "ratio_of_summed_on_due_quantities_to_summed_demand",
        "service_window_days": SERVICE_DAYS,
        "development_seed_count": len(DEVELOPMENT_SEEDS),
        "op100_pooled_global_and_each_product_minimum": REFERENCE_MINIMUM,
        "op100_seed_median_global_minimum": REFERENCE_MINIMUM,
        "development_inner_pooled_and_median_bands": {
            key: list(value) for key, value in DEVELOPMENT_INNER_BANDS.items()
        },
        "development_leave_one_out_outer_bands": {
            key: list(value) for key, value in OUTER_BANDS.items()
        },
        "degraded_product_pooled_strictly_below": NON_SATURATION_LIMIT,
        "pooled_strict_order_global_and_each_product": True,
        "same_seed_joint_strict_order_required": MIN_ORDERED_SEEDS,
        "same_seed_joint_strict_order_definition": (
            "op100>op93>op80 simultaneously for global, PF268091 and PF268967 "
            "within one common-random-number seed"
        ),
        "candidate_must_have_all_development_seeds": True,
        "candidate_acceptance_requires_executed_proofs_not_reconstruction": True,
        "pair_tie_break": list(v4._selection_contract()["pair_tie_break_v4"]),  # noqa: SLF001
        "paired_demand_tolerance": copy.deepcopy(
            v4._selection_contract()["paired_demand_tolerance"]  # noqa: SLF001
        ),
        "no_interpolation": True,
        "no_holdout_read_before_selection": True,
    }


def _holdout_contract() -> dict[str, Any]:
    return {
        **copy.deepcopy(v4._holdout_contract()),  # noqa: SLF001
        "status_before_development_selection": "carried_from_v4_but_sealed_unread",
        "seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "freshness_basis": (
            "same pre-registered V4 cohort, carried only after signed V4 development "
            "no-go and an exact audit showing zero V4 holdout output"
        ),
        "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
    }


def _candidate_design_contract() -> dict[str, Any]:
    return {
        "scientific_basis": (
            "pre-registered separable screening on signed V4 development proofs; "
            "screening values are not acceptance evidence"
        ),
        "screening_projections": copy.deepcopy(SCREENING_PROJECTIONS),
        "op100": "reuse_exactly_30_signed_v4_development_proofs_without_engine",
        "op93_exact_grid": [
            {
                "key": key,
                "offset_days_268091": left,
                "offset_days_268967": right,
                "evidence_mode": "execute",
            }
            for key, left, right in OP93_GRID
        ],
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
        "new_candidate_count": 6,
        "new_development_engine_run_count": EXPECTED_NEW_DEVELOPMENT_CASES,
        "fractional_offsets_are_model_parameters_not_operational_precision_claims": True,
    }


def _execution_contract(source_plan: Any) -> dict[str, Any]:
    source = copy.deepcopy(source_plan.manifest["execution_contract"])
    source.update(
        {
            "changed_dimension": "planned_supplier_lead_time_days_only",
            "quality_incident": False,
            "availability_incident": False,
            "capacity_override": False,
            "state_dependent_risk": False,
            "v5_new_development_engine_runs": EXPECTED_NEW_DEVELOPMENT_CASES,
            "v4_development_engine_reruns": 0,
            "holdout_engine_runs_if_selected": EXPECTED_HOLDOUT_CASES,
        }
    )
    return source


def _holdout_forbidden_paths(v4_run_dir: Path) -> tuple[Path, ...]:
    return (
        v4_run_dir / "evidence" / "holdout",
        v4_run_dir / "shipment_traces" / "holdout",
        v4_run_dir / "engine_attempts" / "holdout",
        v4_run_dir / "holdout_progress.json",
        v4_run_dir / "holdout_result.json",
    )


def _assert_empty_or_absent(path: Path, label: str) -> None:
    if not path.exists():
        return
    if path.is_dir() and not any(path.iterdir()):
        return
    raise V5ProtocolError(f"{label} is not empty: {path}")


def _source_reference(
    *,
    v4_plan_dir: Path,
    v4_run_dir: Path,
    v4_sidecar_root: Path,
    allow_test_source: bool,
) -> tuple[dict[str, Any], Any, dict[tuple[str, int], dict[str, Any]]]:
    """Revalidate the complete V4 development no-go and prove holdout non-use."""

    v4_plan_dir = v4_plan_dir.resolve()
    v4_run_dir = v4_run_dir.resolve()
    v4_sidecar_root = v4_sidecar_root.resolve()
    try:
        source_plan = v4.validate_plan(
            v4_plan_dir, verify_runtime_dependencies=not allow_test_source
        )
        mode = v4._registered_execution_mode(source_plan, v4_run_dir)  # noqa: SLF001
        evidence = v4._load_stage_evidence(  # noqa: SLF001
            source_plan, v4_run_dir, "development"
        )
        expected = v4._build_development_selection(  # noqa: SLF001
            source_plan, evidence, execution_mode=mode
        )
    except Exception as exc:
        raise V5ProtocolError("The V4 development source does not revalidate") from exc
    selection_path = v4_run_dir / "development_selection.json"
    selection = _read_json(selection_path)
    if selection != expected:
        raise V5ProtocolError("The signed V4 no-go is not reproducible")
    _verify_signature(selection, "selection_signature", "V4 selection")
    if (
        selection.get("status") != "development_failed_no_holdout"
        or selection.get("selected_candidate_keys") is not None
        or selection.get("eligible_pairs") != []
        or selection.get("holdout_cases_read") != 0
        or selection.get("retuning_after_development") is not False
    ):
        raise V5ProtocolError("V5 requires the exact signed V4 development no-go")
    if not allow_test_source and (
        mode != v4.OFFICIAL_EXECUTION_MODE
        or selection.get("publishable") is not True
        or len(evidence) != 330
    ):
        raise V5ProtocolError("Only the complete official 330-case V4 no-go is usable")
    if allow_test_source and mode not in {
        v4.OFFICIAL_EXECUTION_MODE,
        v4.TEST_ONLY_EXECUTION_MODE,
    }:
        raise V5ProtocolError("Unknown V4 source execution mode")

    forbidden = _holdout_forbidden_paths(v4_run_dir)
    for path in forbidden:
        if path.exists():
            raise V5ProtocolError(f"V4 holdout is not unseen: {path}")
    _assert_empty_or_absent(v4_sidecar_root, "V4 holdout sidecar")

    op100_rows = {
        seed: evidence[("op100_source", seed)] for seed in DEVELOPMENT_SEEDS
    }
    op100_index = [
        {
            "seed": seed,
            "path": str(
                v4._evidence_path(  # noqa: SLF001
                    v4_run_dir, "development", "op100_source", seed
                ).resolve()
            ),
            "sha256": sha256_file(
                v4._evidence_path(  # noqa: SLF001
                    v4_run_dir, "development", "op100_source", seed
                )
            ),
            "evidence_signature": op100_rows[seed]["evidence_signature"],
        }
        for seed in DEVELOPMENT_SEEDS
    ]
    run_manifest_path = v4_run_dir / "run_manifest.json"
    progress_path = v4_run_dir / "development_progress.json"
    run_manifest = _read_json(run_manifest_path)
    if not allow_test_source and (
        source_plan.manifest["plan_signature"] != OFFICIAL_V4_PLAN_SIGNATURE
        or sha256_file(v4_plan_dir / "refinement_plan.json")
        != OFFICIAL_V4_PLAN_SHA256
        or run_manifest.get("run_signature") != OFFICIAL_V4_RUN_SIGNATURE
        or sha256_file(run_manifest_path) != OFFICIAL_V4_RUN_MANIFEST_SHA256
        or selection.get("selection_signature")
        != OFFICIAL_V4_SELECTION_SIGNATURE
        or sha256_file(selection_path) != OFFICIAL_V4_SELECTION_SHA256
    ):
        raise V5ProtocolError("V5 is pinned to the exact official V4 no-go source")
    reference = {
        "protocol": "signed_v4_development_no_go",
        "plan_dir": str(v4_plan_dir),
        "plan_manifest": str((v4_plan_dir / "refinement_plan.json").resolve()),
        "plan_manifest_sha256": sha256_file(v4_plan_dir / "refinement_plan.json"),
        "plan_signature": source_plan.manifest["plan_signature"],
        "run_dir": str(v4_run_dir),
        "run_manifest": str(run_manifest_path.resolve()),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "run_signature": run_manifest["run_signature"],
        "development_progress": str(progress_path.resolve()),
        "development_progress_sha256": sha256_file(progress_path),
        "development_selection": str(selection_path.resolve()),
        "development_selection_sha256": sha256_file(selection_path),
        "development_selection_signature": selection["selection_signature"],
        "development_status": selection["status"],
        "development_evidence_case_count": len(evidence),
        "development_evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "op100_evidence": op100_index,
        "op100_evidence_index_sha256": stable_sha256(op100_index),
        "execution_mode": mode,
        "holdout_non_use_audit": {
            "checked_paths": [str(path.resolve()) for path in forbidden],
            "all_absent": True,
            "sidecar_root": str(v4_sidecar_root),
            "sidecar_absent_or_empty": True,
            "holdout_cases_read_reported_by_v4": 0,
        },
    }
    return reference, source_plan, evidence


def _source_graph_and_lanes(source_plan: Any) -> tuple[dict[str, Any], Any]:
    source = source_plan.manifest["source"]
    v3_plan = _read_json(Path(source["v3_plan"]["path"]))
    lanes = v4._base_lane_scope(v3_plan)  # noqa: SLF001
    if sum(len(rows) for rows in lanes.values()) != 18:
        raise V5ProtocolError("V5 requires the same exact 18 V4 supplier lanes")
    base_item = source_plan.manifest["inventory"]["op100_source"]
    base_path = (source_plan.plan_dir / base_item["graph_path"]).resolve()
    if sha256_file(base_path) != base_item["graph_sha256"]:
        raise V5ProtocolError("The V4 op100 graph changed")
    return _read_json(base_path), lanes


def _protected_source_directories(
    source_plan: Any, source_ref: Mapping[str, Any]
) -> tuple[Path, ...]:
    source = source_plan.manifest["source"]
    return (
        source_plan.plan_dir,
        Path(str(source_ref["run_dir"])).resolve(),
        Path(str(source["campaign_manifest"]["path"])).resolve().parent,
        Path(str(source["v3_plan"]["path"])).resolve().parent,
    )


def prepare_plan(
    output_dir: Path,
    *,
    v4_plan_dir: Path,
    v4_run_dir: Path,
    v4_sidecar_root: Path,
    allow_test_source: bool = False,
) -> Path:
    """Create the immutable additive V5 plan; never execute the engine."""

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite V5 plan: {output_dir}")
    source_ref, source_plan, _evidence = _source_reference(
        v4_plan_dir=v4_plan_dir,
        v4_run_dir=v4_run_dir,
        v4_sidecar_root=v4_sidecar_root,
        allow_test_source=allow_test_source,
    )
    for protected in _protected_source_directories(source_plan, source_ref):
        if _paths_overlap(output_dir, protected):
            raise V5ProtocolError("V5 plan overlaps a protected V4 source")
    candidates = _all_candidates()
    base_graph, lanes = _source_graph_and_lanes(source_plan)
    temporary = output_dir.parent / f".{output_dir.name}.building-{os.getpid()}"
    if temporary.exists():
        raise FileExistsError(f"Temporary V5 plan already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        inventory: dict[str, dict[str, str]] = {}
        for candidate in candidates:
            graph_path = temporary / "graphs" / f"{candidate.key}.json"
            ledger_path = temporary / "ledgers" / f"{candidate.key}.json"
            if candidate.key == "op100_source":
                graph = copy.deepcopy(base_graph)
                changes = v4._apply_offsets(  # noqa: SLF001
                    base_graph, lanes, 0.0, 0.0
                )[1]
            else:
                graph, changes = v4._apply_offsets(  # noqa: SLF001
                    base_graph,
                    lanes,
                    candidate.offset_days_268091,
                    candidate.offset_days_268967,
                )
            _write_json(graph_path, graph)
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
            "status": "frozen_before_v5_development",
            "interpretation": INTERPRETATION,
            "supersedes": {
                "protocol": "v4_development_no_go",
                "v4_plan_signature": source_ref["plan_signature"],
                "v4_selection_signature": source_ref[
                    "development_selection_signature"
                ],
                "v4_status": "development_failed_no_holdout",
                "modifies_v4_artifacts": False,
            },
            "source": copy.deepcopy(source_plan.manifest["source"]),
            "v4_no_go_source": source_ref,
            "source_hashes": {
                **copy.deepcopy(source_plan.manifest["source_hashes"]),
                "v5_driver_sha256": sha256_file(module_path),
            },
            "runtime_dependencies": copy.deepcopy(
                source_plan.manifest["runtime_dependencies"]
            ),
            "cohorts": {
                "development_common_random_numbers": list(DEVELOPMENT_SEEDS),
                "v4_op100_proofs_reused": list(DEVELOPMENT_SEEDS),
                "v4_candidate_proofs_not_reused_for_v5_acceptance": True,
                "holdout_carried_forward_sealed_unread": list(
                    EXPECTED_HOLDOUT_SEEDS
                ),
                "incident_design_reserved": [INCIDENT_DESIGN_SEED],
            },
            "candidate_design": _candidate_design_contract(),
            "candidates": [_candidate_payload(candidate) for candidate in candidates],
            "inventory": inventory,
            "development_cases": cases,
            "expected_development_case_count": len(cases),
            "reused_development_case_count": EXPECTED_REUSED_DEVELOPMENT_CASES,
            "new_development_case_count": EXPECTED_NEW_DEVELOPMENT_CASES,
            "selection_contract": _selection_contract(),
            "holdout_contract": _holdout_contract(),
            "execution_contract": _execution_contract(source_plan),
        }
        manifest["plan_signature"] = stable_sha256(manifest)
        _write_json(temporary / "refinement_plan.json", manifest)
        os.replace(temporary, output_dir)
    except BaseException:
        if temporary.exists():
            import shutil

            shutil.rmtree(temporary)
        raise
    return output_dir


def validate_plan(
    plan_dir: Path,
    *,
    verify_runtime_dependencies: bool = True,
    allow_test_source: bool = False,
) -> ValidatedPlan:
    plan_dir = plan_dir.resolve()
    manifest = _read_json(plan_dir / "refinement_plan.json")
    _verify_signature(manifest, "plan_signature", "V5 plan")
    expected_fields = {
        "schema_version",
        "status",
        "interpretation",
        "supersedes",
        "source",
        "v4_no_go_source",
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
        or manifest.get("status") != "frozen_before_v5_development"
        or manifest.get("interpretation") != INTERPRETATION
    ):
        raise V5ProtocolError("Unexpected V5 plan field or status")
    source_declared = manifest.get("v4_no_go_source") or {}
    source_ref, source_plan, _source_evidence = _source_reference(
        v4_plan_dir=Path(str(source_declared.get("plan_dir") or "")),
        v4_run_dir=Path(str(source_declared.get("run_dir") or "")),
        v4_sidecar_root=Path(
            str(
                (source_declared.get("holdout_non_use_audit") or {}).get(
                    "sidecar_root"
                )
                or ""
            )
        ),
        allow_test_source=allow_test_source,
    )
    if source_ref != source_declared:
        raise V5ProtocolError("V4 no-go source provenance changed")
    if manifest.get("source") != source_plan.manifest["source"]:
        raise V5ProtocolError("V4 execution source changed")
    if any(
        _paths_overlap(plan_dir, protected)
        for protected in _protected_source_directories(source_plan, source_ref)
    ):
        raise V5ProtocolError("V5 plan overlaps a protected V4 source")
    module_hash = sha256_file(Path(__file__).resolve())
    expected_source_hashes = {
        **copy.deepcopy(source_plan.manifest["source_hashes"]),
        "v5_driver_sha256": module_hash,
    }
    candidates = _all_candidates()
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
    supersedes = manifest.get("supersedes") or {}
    cohorts = manifest.get("cohorts") or {}
    if (
        manifest.get("source_hashes") != expected_source_hashes
        or manifest.get("runtime_dependencies")
        != source_plan.manifest["runtime_dependencies"]
        or manifest.get("candidate_design") != _candidate_design_contract()
        or manifest.get("selection_contract") != _selection_contract()
        or manifest.get("holdout_contract") != _holdout_contract()
        or manifest.get("execution_contract") != _execution_contract(source_plan)
        or manifest.get("candidates")
        != [_candidate_payload(candidate) for candidate in candidates]
        or manifest.get("development_cases") != expected_cases
        or manifest.get("expected_development_case_count")
        != EXPECTED_DEVELOPMENT_CASES
        or manifest.get("reused_development_case_count")
        != EXPECTED_REUSED_DEVELOPMENT_CASES
        or manifest.get("new_development_case_count")
        != EXPECTED_NEW_DEVELOPMENT_CASES
        or supersedes
        != {
            "protocol": "v4_development_no_go",
            "v4_plan_signature": source_ref["plan_signature"],
            "v4_selection_signature": source_ref[
                "development_selection_signature"
            ],
            "v4_status": "development_failed_no_holdout",
            "modifies_v4_artifacts": False,
        }
        or tuple(cohorts.get("development_common_random_numbers") or ())
        != DEVELOPMENT_SEEDS
        or tuple(cohorts.get("v4_op100_proofs_reused") or ())
        != DEVELOPMENT_SEEDS
        or cohorts.get("v4_candidate_proofs_not_reused_for_v5_acceptance")
        is not True
        or tuple(cohorts.get("holdout_carried_forward_sealed_unread") or ())
        != EXPECTED_HOLDOUT_SEEDS
        or cohorts.get("incident_design_reserved") != [INCIDENT_DESIGN_SEED]
    ):
        raise V5ProtocolError("V5 frozen scientific contract changed")

    base_graph, lanes = _source_graph_and_lanes(source_plan)
    inventory = manifest.get("inventory") or {}
    if set(inventory) != {candidate.key for candidate in candidates}:
        raise V5ProtocolError("V5 graph inventory changed")
    for candidate in candidates:
        item = inventory[candidate.key]
        if not isinstance(item, Mapping) or set(item) != {
            "graph_path",
            "graph_sha256",
            "ledger_path",
            "ledger_sha256",
        }:
            raise V5ProtocolError("Invalid V5 graph inventory item")
        graph_path = (plan_dir / str(item["graph_path"])).resolve()
        ledger_path = (plan_dir / str(item["ledger_path"])).resolve()
        if (
            not graph_path.is_relative_to(plan_dir)
            or not ledger_path.is_relative_to(plan_dir)
            or item["graph_path"] != f"graphs/{candidate.key}.json"
            or item["ledger_path"] != f"ledgers/{candidate.key}.json"
            or sha256_file(graph_path) != item["graph_sha256"]
            or sha256_file(ledger_path) != item["ledger_sha256"]
        ):
            raise V5ProtocolError(f"V5 graph/ledger changed: {candidate.key}")
        expected_graph, expected_changes = v4._apply_offsets(  # noqa: SLF001
            base_graph,
            lanes,
            candidate.offset_days_268091,
            candidate.offset_days_268967,
        )
        if _read_json(graph_path) != expected_graph:
            raise V5ProtocolError(f"V5 canonical graph changed: {candidate.key}")
        expected_ledger = {
            "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
            "candidate": _candidate_payload(candidate),
            "changed_dimension": "planned_supplier_lead_time_days_only",
            "changes": expected_changes,
        }
        if _read_json(ledger_path) != expected_ledger:
            raise V5ProtocolError(f"V5 canonical ledger changed: {candidate.key}")
    if verify_runtime_dependencies:
        try:
            v4._assert_runtime_dependencies_current(source_plan)  # noqa: SLF001
        except Exception as exc:
            raise V5ProtocolError("Pinned execution dependencies changed") from exc
    return ValidatedPlan(plan_dir, manifest, candidates)


def _case_key(stage: str, candidate_key: str, seed: int) -> str:
    return f"{stage}__{candidate_key}__seed_{seed}"


def _evidence_path(run_dir: Path, stage: str, candidate_key: str, seed: int) -> Path:
    digest = hashlib.sha256(
        _case_key(stage, candidate_key, seed).encode("utf-8")
    ).hexdigest()[:24]
    return run_dir / "evidence" / stage / f"{digest}.json"


def _run_manifest(plan: ValidatedPlan, execution_mode: str) -> dict[str, Any]:
    if execution_mode not in {OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE}:
        raise V5ProtocolError("Unknown V5 execution mode")
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_path": str(plan.plan_dir),
        "plan_sha256": sha256_file(plan.plan_dir / "refinement_plan.json"),
        "plan_signature": plan.manifest["plan_signature"],
        "v4_selection_signature": plan.manifest["supersedes"][
            "v4_selection_signature"
        ],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "development_seeds": list(DEVELOPMENT_SEEDS),
        "holdout_seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "incident_design_seed_excluded": INCIDENT_DESIGN_SEED,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "v4_candidate_engine_reruns": 0,
    }
    return {**unsigned, "run_signature": stable_sha256(unsigned)}


def _registered_execution_mode(plan: ValidatedPlan, run_dir: Path) -> str:
    payload = _read_json(run_dir / "run_manifest.json")
    for mode in (OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE):
        if payload == _run_manifest(plan, mode):
            return mode
    raise V5ProtocolError("Invalid V5 run registration")


def _validate_run_location(plan: ValidatedPlan, run_dir: Path) -> None:
    protected = (
        plan.plan_dir,
        Path(plan.manifest["v4_no_go_source"]["plan_dir"]),
        Path(plan.manifest["v4_no_go_source"]["run_dir"]),
        Path(plan.manifest["source"]["campaign_manifest"]["path"]).parent,
    )
    if any(_paths_overlap(run_dir, path) for path in protected):
        raise V5ProtocolError("V5 run overlaps a protected plan/source")


def _register_run(plan: ValidatedPlan, run_dir: Path, mode: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run_manifest.json"
    expected = _run_manifest(plan, mode)
    if path.exists():
        if _read_json(path) != expected:
            raise V5ProtocolError("Run directory belongs to another V5 plan")
    elif any(item.name != ".v5.lock" for item in run_dir.iterdir()):
        raise V5ProtocolError("Refusing an unregistered non-empty V5 run directory")
    else:
        _write_json(path, expected)


@contextmanager
def _run_lock(run_dir: Path):
    lock = run_dir / ".v5.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise V5ProtocolError("Another V5 stage process is active") from exc
        else:  # pragma: no cover - CI is Windows for this campaign
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise V5ProtocolError("Another V5 stage process is active") from exc
        acquired = True
        yield
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(descriptor)


def _assert_v5_holdout_unseen(run_dir: Path) -> None:
    forbidden = (
        run_dir / "evidence" / "holdout",
        run_dir / "shipment_traces" / "holdout",
        run_dir / "engine_attempts" / "holdout",
        run_dir / "holdout_progress.json",
        run_dir / "holdout_result.json",
    )
    if any(path.exists() for path in forbidden):
        raise V5ProtocolError("Development is invalid because V5 holdout is visible")


def _source_op100_row(plan: ValidatedPlan, seed: int) -> dict[str, Any]:
    index = {
        int(row["seed"]): row
        for row in plan.manifest["v4_no_go_source"]["op100_evidence"]
    }
    ref = index.get(seed)
    if ref is None:
        raise V5ProtocolError(f"Missing V4 op100 proof for seed {seed}")
    path = Path(str(ref["path"])).resolve()
    if sha256_file(path) != ref["sha256"]:
        raise V5ProtocolError("Imported V4 op100 evidence hash changed")
    payload = _read_json(path)
    _verify_signature(payload, "evidence_signature", "imported V4 op100 evidence")
    if payload.get("evidence_signature") != ref["evidence_signature"]:
        raise V5ProtocolError("Imported V4 op100 evidence signature changed")
    return payload


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
    stage: str,
    candidate: Candidate,
    seed: int,
    mode: str,
) -> dict[str, Any]:
    _verify_signature(payload, "evidence_signature", "V5 evidence")
    expected_evidence_mode = (
        candidate.evidence_mode if stage == "development" else "execute_fresh_holdout"
    )
    if (
        set(payload) != EVIDENCE_FIELDS
        or payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("stage") != stage
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or int(payload.get("seed") or -1) != seed
        or payload.get("evidence_mode") != expected_evidence_mode
        or payload.get("graph_sha256")
        != plan.manifest["inventory"][candidate.key]["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("valid") is not True
        or not isinstance(payload.get("created_at_utc"), str)
    ):
        raise V5ProtocolError(f"V5 evidence mismatch: {candidate.key}/{seed}")
    source_proof = payload.get("source_evidence")
    executor_proof = payload.get("executor_proof")
    if stage == "development" and candidate.key == "op100_source":
        source = _source_op100_row(plan, seed)
        expected_ref = next(
            row
            for row in plan.manifest["v4_no_go_source"]["op100_evidence"]
            if int(row["seed"]) == seed
        )
        if source_proof != expected_ref or executor_proof is not None:
            raise V5ProtocolError("V5 op100 proof is not the exact V4 proof")
        if v4._normalize_metrics(source.get("metrics") or {}) != v4._normalize_metrics(  # noqa: SLF001
            payload.get("metrics") or {}
        ):
            raise V5ProtocolError("Imported V4/V5 op100 metrics differ")
    else:
        if source_proof is not None or not isinstance(executor_proof, Mapping):
            raise V5ProtocolError("Executed V5 evidence lacks executor proof")
        expected_kind = (
            "coarse_execute_candidate"
            if mode == OFFICIAL_EXECUTION_MODE
            else "injected_test_executor"
        )
        if executor_proof.get("kind") != expected_kind:
            raise V5ProtocolError("V5 executor proof mode changed")
        try:
            adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)
            raw = (
                executor_proof.get("raw_evidence")
                if expected_kind == "coarse_execute_candidate"
                else executor_proof.get("raw_payload")
            )
            raw_metrics = (
                v4._validate_coarse_executor_evidence(  # noqa: SLF001
                    raw, candidate=candidate, seed=seed, plan=adapter
                )
                if expected_kind == "coarse_execute_candidate"
                else v4._normalize_metrics((raw or {}).get("metrics") or raw or {})  # noqa: SLF001
            )
        except Exception as exc:
            raise V5ProtocolError("Underlying V5 executor proof is invalid") from exc
        if raw_metrics != v4._normalize_metrics(payload.get("metrics") or {}):  # noqa: SLF001
            raise V5ProtocolError("V5 outer/executor metrics differ")
    trace_required = stage == "holdout" and mode == OFFICIAL_EXECUTION_MODE
    if trace_required:
        try:
            v4._validate_shipment_trace_reference(  # noqa: SLF001
                payload.get("shipment_trace"),
                plan=v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates),
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
            )
        except Exception as exc:
            raise V5ProtocolError("Invalid V5 holdout shipment trace") from exc
    elif payload.get("shipment_trace") is not None:
        raise V5ProtocolError("Shipment trace must be null outside official holdout")
    result = dict(payload)
    result["metrics"] = v4._normalize_metrics(payload.get("metrics") or {})  # noqa: SLF001
    return result


def _stage_jobs(
    plan: ValidatedPlan, run_dir: Path, stage: str
) -> tuple[tuple[Candidate, int], ...]:
    if stage == "development":
        return tuple(
            (candidate, seed)
            for candidate in plan.candidates
            for seed in DEVELOPMENT_SEEDS
        )
    if stage != "holdout":
        raise V5ProtocolError("Stage must be development or holdout")
    selection = _load_development_selection(plan, run_dir)
    selected = selection["selected_candidate_keys"]
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    try:
        candidates = tuple(by_key[selected[group]] for group in TARGETS)
    except (KeyError, TypeError) as exc:
        raise V5ProtocolError("V5 selection is incomplete") from exc
    return tuple(
        (candidate, seed)
        for candidate in candidates
        for seed in EXPECTED_HOLDOUT_SEEDS
    )


def _progress(
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    completed: int,
    expected: int,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    mode = _registered_execution_mode(plan, run_dir)
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.{stage}.progress",
        "plan_signature": plan.manifest["plan_signature"],
        "stage": stage,
        "status": status,
        "completed_case_count": completed,
        "expected_case_count": expected,
        "execution_mode": mode,
        "publishable": mode == OFFICIAL_EXECUTION_MODE,
        "error": error,
        "updated_at_utc": _now(),
    }
    payload = {**unsigned, "progress_signature": stable_sha256(unsigned)}
    _write_json(run_dir / f"{stage}_progress.json", payload)
    return payload


def _validate_existing_inventory(
    run_dir: Path, stage: str, jobs: Sequence[tuple[Candidate, int]]
) -> None:
    directory = run_dir / "evidence" / stage
    if not directory.exists():
        return
    expected = {
        _evidence_path(run_dir, stage, candidate.key, seed).name
        for candidate, seed in jobs
    }
    actual = {path.name for path in directory.glob("*.json") if path.is_file()}
    if not actual.issubset(expected):
        raise V5ProtocolError(f"Unexpected V5 {stage} evidence exists")


def _validate_trace_inventory(
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    jobs: Sequence[tuple[Candidate, int]],
    mode: str,
    *,
    require_complete: bool,
) -> None:
    """Keep the compact-trace inventory closed while allowing safe resume."""

    root = run_dir / "shipment_traces"
    actual = (
        {path.resolve() for path in root.rglob("*") if path.is_file()}
        if root.exists()
        else set()
    )
    expected_by_path: dict[Path, tuple[Candidate, int]] = {}
    if stage == "holdout" and mode == OFFICIAL_EXECUTION_MODE:
        expected_by_path = {
            (
                run_dir
                / v4._shipment_trace_relative_path(candidate, seed)  # noqa: SLF001
            ).resolve(): (candidate, seed)
            for candidate, seed in jobs
        }
    expected = set(expected_by_path)
    if not actual.issubset(expected):
        raise V5ProtocolError("Unexpected compact trace exists in the V5 run")
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
            raise V5ProtocolError("Stored V5 compact trace is invalid") from exc
    if require_complete:
        evidence_complete = all(
            _evidence_path(run_dir, stage, candidate.key, seed).is_file()
            for candidate, seed in jobs
        )
        if actual != expected or not evidence_complete:
            raise V5ProtocolError("Official V5 holdout trace inventory is incomplete")


def _collect_stage(
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    jobs: Sequence[tuple[Candidate, int]],
    mode: str,
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[tuple[Candidate, int]]]:
    completed: dict[tuple[str, int], dict[str, Any]] = {}
    missing: list[tuple[Candidate, int]] = []
    for candidate, seed in jobs:
        path = _evidence_path(run_dir, stage, candidate.key, seed)
        if not path.is_file():
            missing.append((candidate, seed))
            continue
        validated = _validate_evidence(
            _read_json(path),
            plan=plan,
            run_dir=run_dir,
            stage=stage,
            candidate=candidate,
            seed=seed,
            mode=mode,
        )
        completed[(candidate.key, seed)] = validated
        proof = validated.get("executor_proof") or {}
        if proof.get("kind") == "coarse_execute_candidate":
            try:
                v4._prune_real_executor_case(  # noqa: SLF001
                    proof, run_dir, candidate, seed
                )
            except Exception as exc:
                raise V5ProtocolError("Cannot prune a resumed V5 engine case") from exc
    return completed, missing


def _validate_progress_if_present(
    plan: ValidatedPlan, run_dir: Path, stage: str, expected: int
) -> None:
    path = run_dir / f"{stage}_progress.json"
    if not path.exists():
        return
    payload = _read_json(path)
    _verify_signature(payload, "progress_signature", f"V5 {stage} progress")
    completed = payload.get("completed_case_count")
    if (
        payload.get("schema_version") != f"{SCHEMA_VERSION}.{stage}.progress"
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("stage") != stage
        or payload.get("status") not in {"running", "failed", "complete"}
        or type(completed) is not int
        or not 0 <= completed <= expected
        or payload.get("expected_case_count") != expected
        or payload.get("execution_mode")
        != _registered_execution_mode(plan, run_dir)
    ):
        raise V5ProtocolError(f"Invalid V5 {stage} progress")


def run_stage(
    plan_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    executor: Executor | None = None,
    max_workers: int = 2,
    test_only: bool = False,
) -> dict[str, Any]:
    """Execute/resume one V5 stage; imports op100 without an engine call."""

    if stage not in {"development", "holdout"}:
        raise V5ProtocolError("Stage must be development or holdout")
    if max_workers not in {1, 2}:
        raise V5ProtocolError("V5 permits one or two workers")
    if (executor is None) is test_only:
        raise V5ProtocolError("Injected executors require explicit test_only=True")
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    _validate_run_location(plan, run_dir)
    if stage == "development":
        _assert_v5_holdout_unseen(run_dir)
    jobs = _stage_jobs(plan, run_dir, stage)
    _validate_existing_inventory(run_dir, stage, jobs)
    _register_run(plan, run_dir, mode)
    _validate_trace_inventory(
        plan, run_dir, stage, jobs, mode, require_complete=False
    )
    selected_executor = executor or v4._real_executor  # noqa: SLF001
    adapter = v4.ValidatedPlan(plan.plan_dir, plan.manifest, plan.candidates)

    def execute(candidate: Candidate, seed: int) -> dict[str, Any]:
        source_evidence: Mapping[str, Any] | None = None
        executor_proof: Mapping[str, Any] | None = None
        shipment_trace: Mapping[str, Any] | None = None
        if stage == "development" and candidate.key == "op100_source":
            raw_source = _source_op100_row(plan, seed)
            metrics = v4._normalize_metrics(raw_source.get("metrics") or {})  # noqa: SLF001
            source_evidence = next(
                row
                for row in plan.manifest["v4_no_go_source"]["op100_evidence"]
                if int(row["seed"]) == seed
            )
            evidence_mode = "reuse_v4_development"
        else:
            if mode == OFFICIAL_EXECUTION_MODE:
                try:
                    v4._assert_runtime_dependencies_current(adapter)  # noqa: SLF001
                except Exception as exc:
                    raise V5ProtocolError("Pinned dependencies changed before run") from exc
            attempt_key = _case_key(stage, candidate.key, seed)
            attempt_digest = hashlib.sha256(attempt_key.encode("utf-8")).hexdigest()[
                :24
            ]
            attempt_root = (
                run_dir
                / "engine_attempts"
                / stage
                / attempt_digest
                / f"attempt-{os.getpid()}-{os.urandom(8).hex()}"
            )
            raw = selected_executor(
                candidate=candidate,
                seed=seed,
                stage=stage,
                run_dir=run_dir,
                plan=plan.manifest,
                validated_plan=adapter,
                attempt_root=attempt_root,
            )
            if not isinstance(raw, Mapping):
                raise V5ProtocolError("V5 executor must return a mapping")
            if mode == OFFICIAL_EXECUTION_MODE:
                try:
                    v4._assert_runtime_dependencies_current(adapter)  # noqa: SLF001
                except Exception as exc:
                    raise V5ProtocolError("Pinned dependencies changed after run") from exc
            metrics, executor_proof = v4._executor_output(  # noqa: SLF001
                raw,
                candidate=candidate,
                seed=seed,
                plan=adapter,
                injected=test_only,
            )
            if stage == "holdout" and mode == OFFICIAL_EXECUTION_MODE:
                case_dir = v4._coarse_case_dir(  # noqa: SLF001
                    raw, run_dir, candidate, seed
                )
                shipment_trace = v4._write_holdout_shipment_trace(  # noqa: SLF001
                    plan=adapter,
                    run_dir=run_dir,
                    candidate=candidate,
                    seed=seed,
                    source_csv=case_dir / v4.SHIPMENT_TRACE_SOURCE_RELATIVE_PATH,
                )
            evidence_mode = (
                "execute_fresh_holdout" if stage == "holdout" else "execute"
            )
        unsigned = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "plan_signature": plan.manifest["plan_signature"],
            "stage": stage,
            "candidate_key": candidate.key,
            "candidate_id": candidate.candidate_id,
            "target_group": candidate.target_group,
            "seed": seed,
            "evidence_mode": evidence_mode,
            "graph_sha256": plan.manifest["inventory"][candidate.key][
                "graph_sha256"
            ],
            "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
            "metrics": metrics,
            "source_evidence": source_evidence,
            "executor_proof": executor_proof,
            "shipment_trace": shipment_trace,
            "valid": True,
            "created_at_utc": _now(),
        }
        payload = {**unsigned, "evidence_signature": stable_sha256(unsigned)}
        _validate_evidence(
            payload,
            plan=plan,
            run_dir=run_dir,
            stage=stage,
            candidate=candidate,
            seed=seed,
            mode=mode,
        )
        _write_json(_evidence_path(run_dir, stage, candidate.key, seed), payload)
        if executor_proof and executor_proof.get("kind") == "coarse_execute_candidate":
            v4._prune_real_executor_case(  # noqa: SLF001
                executor_proof, run_dir, candidate, seed
            )
        return payload

    with _run_lock(run_dir):
        if mode == OFFICIAL_EXECUTION_MODE:
            try:
                v4._assert_runtime_dependencies_current(adapter)  # noqa: SLF001
            except Exception as exc:
                raise V5ProtocolError("Pinned dependencies changed before stage") from exc
        _validate_existing_inventory(run_dir, stage, jobs)
        _validate_trace_inventory(
            plan, run_dir, stage, jobs, mode, require_complete=False
        )
        completed, missing = _collect_stage(plan, run_dir, stage, jobs, mode)
        _validate_progress_if_present(plan, run_dir, stage, len(jobs))
        _progress(plan, run_dir, stage, len(completed), len(jobs), "running")
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                pending = iter(missing)
                futures: dict[Any, tuple[Candidate, int]] = {}
                for _index in range(max_workers):
                    try:
                        candidate, seed = next(pending)
                    except StopIteration:
                        break
                    futures[pool.submit(execute, candidate, seed)] = (candidate, seed)
                while futures:
                    future = next(as_completed(futures))
                    candidate, seed = futures.pop(future)
                    payload = future.result()
                    completed[(candidate.key, seed)] = payload
                    _progress(
                        plan, run_dir, stage, len(completed), len(jobs), "running"
                    )
                    try:
                        next_candidate, next_seed = next(pending)
                    except StopIteration:
                        continue
                    futures[pool.submit(execute, next_candidate, next_seed)] = (
                        next_candidate,
                        next_seed,
                    )
        except BaseException as exc:
            completed, _missing = _collect_stage(plan, run_dir, stage, jobs, mode)
            _progress(
                plan, run_dir, stage, len(completed), len(jobs), "failed", str(exc)
            )
            raise
        if len(completed) != len(jobs):
            raise V5ProtocolError("V5 stage evidence matrix is incomplete")
        _validate_trace_inventory(
            plan, run_dir, stage, jobs, mode, require_complete=True
        )
        if mode == OFFICIAL_EXECUTION_MODE:
            try:
                v4._assert_runtime_dependencies_current(adapter)  # noqa: SLF001
            except Exception as exc:
                raise V5ProtocolError("Pinned dependencies changed during stage") from exc
        return _progress(
            plan, run_dir, stage, len(completed), len(jobs), "complete"
        )


def _load_stage_evidence(
    plan: ValidatedPlan, run_dir: Path, stage: str
) -> dict[tuple[str, int], dict[str, Any]]:
    jobs = _stage_jobs(plan, run_dir, stage)
    mode = _registered_execution_mode(plan, run_dir)
    _validate_existing_inventory(run_dir, stage, jobs)
    _validate_trace_inventory(
        plan, run_dir, stage, jobs, mode, require_complete=True
    )
    evidence, missing = _collect_stage(plan, run_dir, stage, jobs, mode)
    _validate_progress_if_present(plan, run_dir, stage, len(jobs))
    progress = _read_json(run_dir / f"{stage}_progress.json")
    if (
        missing
        or len(evidence) != len(jobs)
        or progress.get("status") != "complete"
        or progress.get("completed_case_count") != len(jobs)
    ):
        raise V5ProtocolError(f"V5 {stage} is not complete")
    return evidence


def _candidate_summary(
    candidate: Candidate, rows: Sequence[Mapping[str, Any]], inner: bool
) -> dict[str, Any]:
    try:
        return v4._candidate_summary(candidate, rows, inner)  # noqa: SLF001
    except Exception as exc:
        raise V5ProtocolError("Invalid V5 candidate evidence matrix") from exc


def _ordered_pair(
    reference: Mapping[str, Any],
    high: Mapping[str, Any],
    low: Mapping[str, Any],
) -> tuple[bool, int, int]:
    return v4._ordered_pair(reference, high, low)  # noqa: SLF001


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
        raise V5ProtocolError("V5 paired development demand changed") from exc
    summaries = {
        key: _candidate_summary(
            candidate,
            [evidence[(key, seed)] for seed in DEVELOPMENT_SEEDS],
            True,
        )
        for key, candidate in by_key.items()
    }
    reference = summaries["op100_source"]
    highs = [
        row
        for key, row in summaries.items()
        if by_key[key].target_group == "op_93" and row["admissible_individually"]
    ]
    lows = [
        row
        for key, row in summaries.items()
        if by_key[key].target_group == "op_80" and row["admissible_individually"]
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
                pooled, joint, pf967 = _ordered_pair(reference, high, low)
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
        "v4_selection_signature": plan.manifest["supersedes"][
            "v4_selection_signature"
        ],
        "status": (
            "development_selected_pending_fresh_holdout"
            if winner
            else "development_failed_no_holdout"
        ),
        "development_seeds": list(DEVELOPMENT_SEEDS),
        "holdout_seeds_sealed_and_unread": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "new_candidate_evidence_case_count": EXPECTED_NEW_DEVELOPMENT_CASES,
        "v4_op100_evidence_case_count": EXPECTED_REUSED_DEVELOPMENT_CASES,
        "v4_candidate_engine_rerun_count": 0,
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
    }
    return {**unsigned, "selection_signature": stable_sha256(unsigned)}


def _load_development_selection(
    plan: ValidatedPlan, run_dir: Path
) -> dict[str, Any]:
    path = run_dir / "development_selection.json"
    if not path.is_file():
        raise V5ProtocolError("V5 holdout is not authorized before selection")
    selection = _read_json(path)
    _verify_signature(selection, "selection_signature", "V5 development selection")
    mode = _registered_execution_mode(plan, run_dir)
    if (
        selection.get("schema_version") != SELECTION_SCHEMA_VERSION
        or selection.get("plan_signature") != plan.manifest["plan_signature"]
        or selection.get("status")
        != "development_selected_pending_fresh_holdout"
        or selection.get("holdout_cases_read") != 0
        or selection.get("execution_mode") != mode
        or selection.get("publishable") is not (mode == OFFICIAL_EXECUTION_MODE)
    ):
        raise V5ProtocolError("V5 fresh holdout is not authorized")
    expected = _build_development_selection(
        plan,
        _load_stage_evidence(plan, run_dir, "development"),
        execution_mode=mode,
    )
    if selection != expected:
        raise V5ProtocolError("V5 development selection is not reproducible")
    return selection


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
        raise V5ProtocolError("V5 paired holdout demand changed") from exc
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    rows_by_group = {
        group: [evidence[(key, seed)] for seed in EXPECTED_HOLDOUT_SEEDS]
        for group, key in chosen.items()
    }
    summaries = {
        group: _candidate_summary(by_key[key], rows_by_group[group], False)
        for group, key in chosen.items()
    }
    bootstrap = v4._paired_bootstrap_global(rows_by_group)  # noqa: SLF001
    pooled, joint, pf967 = _ordered_pair(
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
        "status": (
            "holdout_validated_30_carried_unseen_seeds"
            if accepted
            else "holdout_rejected_no_retuning"
        ),
        "holdout_seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_evidence_case_count": len(evidence),
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "holdout_evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "selected_candidate_keys": chosen,
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


def finalize_stage(
    plan_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    test_only: bool = False,
) -> dict[str, Any]:
    if stage not in {"development", "holdout"}:
        raise V5ProtocolError("Stage must be development or holdout")
    plan = validate_plan(
        plan_dir,
        verify_runtime_dependencies=not test_only,
        allow_test_source=test_only,
    )
    run_dir = run_dir.resolve()
    _validate_run_location(plan, run_dir)
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    if _read_json(run_dir / "run_manifest.json") != _run_manifest(plan, mode):
        raise V5ProtocolError("Official/test-only V5 registrations differ")
    if stage == "development":
        _assert_v5_holdout_unseen(run_dir)
    evidence = _load_stage_evidence(plan, run_dir, stage)
    if stage == "development":
        result = _build_development_selection(
            plan, evidence, execution_mode=mode
        )
        output = run_dir / "development_selection.json"
        signature_field = "selection_signature"
    else:
        selection = _load_development_selection(plan, run_dir)
        result = _build_holdout_result(
            plan, evidence, selection, execution_mode=mode
        )
        output = run_dir / "holdout_result.json"
        signature_field = "holdout_signature"
    if output.exists():
        existing = _read_json(output)
        if existing != result or existing.get(signature_field) != result.get(
            signature_field
        ):
            raise V5ProtocolError(f"Existing V5 {stage} finalization differs")
    else:
        _write_json(output, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Create the signed V5 additive plan")
    plan.add_argument("--output-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    plan.add_argument("--v4-plan-dir", type=Path, required=True)
    plan.add_argument("--v4-run-dir", type=Path, required=True)
    plan.add_argument("--v4-sidecar-root", type=Path, required=True)
    validate = sub.add_parser("validate", help="Revalidate a signed V5 plan")
    validate.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run = sub.add_parser("run", help="Execute/resume one frozen V5 stage")
    run.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run.add_argument("--stage", choices=("development", "holdout"), required=True)
    run.add_argument("--workers", type=int, choices=(1, 2), default=2)
    finalize = sub.add_parser("finalize", help="Finalize a complete V5 stage")
    finalize.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    finalize.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    finalize.add_argument(
        "--stage", choices=("development", "holdout"), required=True
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        print(
            prepare_plan(
                args.output_dir,
                v4_plan_dir=args.v4_plan_dir,
                v4_run_dir=args.v4_run_dir,
                v4_sidecar_root=args.v4_sidecar_root,
            )
        )
    elif args.command == "validate":
        print(validate_plan(args.plan_dir).manifest["plan_signature"])
    elif args.command == "run":
        print(
            json.dumps(
                run_stage(
                    args.plan_dir,
                    args.run_dir,
                    stage=args.stage,
                    max_workers=args.workers,
                ),
                ensure_ascii=False,
            )
        )
    else:
        print(
            json.dumps(
                finalize_stage(args.plan_dir, args.run_dir, stage=args.stage),
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
