#!/usr/bin/env python3
"""Refine robust finished-product service states without touching V1 evidence.

The V1 multi-seed calibration is immutable source evidence.  This additive
protocol reuses every V1 calibration case, executes only candidates frozen in
its own signed plan on seeds 340282--340286, and keeps seeds 340287--340316
sealed for a later one-shot holdout.

Only planned supplier lead-time offsets are changed.  No quality event,
capacity override, availability multiplier or acute incident is introduced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_calibration as v1,
)


SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v2"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selection"
POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selected_operating_points"
DESIGN_SEEDS = (v1.DESIGN_SEED,)
CALIBRATION_SEEDS = v1.CALIBRATION_SEEDS
HOLDOUT_SEEDS = v1.HOLDOUT_SEEDS
SERVICE_WINDOW = dict(v1.SERVICE_WINDOW)
NON_SATURATION_LIMIT = 0.995
REFERENCE_MINIMUM = 0.985
PRODUCT_GAP_WARNING_PP = v1.PRODUCT_GAP_WARNING_PP
INTERPRETATION = (
    "Hypotheses de fonctionnement simulees; aucune performance fournisseur "
    "historique n'est inferee."
)
TARGETS = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}
INNER_BANDS = {
    "op_93": (0.9225, 0.9375),
    "op_80": (0.7925, 0.8075),
}
OUTER_LOO_BANDS = {
    "op_93": (0.915, 0.945),
    "op_80": (0.785, 0.815),
}
ARTIFACT_PARENT = coarse.protocol.ARTIFACT_PARENT
DEFAULT_SOURCE_PLAN = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_calibration_plan_20260904_v1"
)
DEFAULT_SOURCE_RUN = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_calibration_run_20260904_v1"
)
DEFAULT_PLAN_OUTPUT = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_refinement_plan_20260904_v2"
)
DEFAULT_RUN_OUTPUT = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_refinement_run_20260904_v2"
)


@dataclass(frozen=True)
class CandidateSpec:
    key: str
    offset_days_268091: float
    offset_days_268967: float
    target_group: str
    evidence_mode: str

    @property
    def candidate(self) -> coarse.Candidate:
        return coarse.Candidate(
            candidate_id=coarse._candidate_id(
                self.offset_days_268091, self.offset_days_268967
            ),
            offset_days_268091=self.offset_days_268091,
            offset_days_268967=self.offset_days_268967,
        )


# Fixed after review of the complete V1 calibration and before any V2
# simulation.  Importing this module does not create a production plan.
OP93_REFINEMENT_WAVE = (
    CandidateSpec("op93_refine_7_75", 7.0, 75.0, "op_93", "execute"),
    CandidateSpec("op93_refine_7_81", 7.0, 81.0, "op_93", "execute"),
    CandidateSpec("op93_refine_7_86", 7.0, 86.0, "op_93", "execute"),
)
OP80_REFINEMENT_WAVE = (
    CandidateSpec("op80_refine_17_95", 17.0, 95.0, "op_80", "execute"),
    CandidateSpec("op80_refine_17_94", 17.0, 94.0, "op_80", "execute"),
    CandidateSpec("op80_refine_18_94", 18.0, 94.0, "op_80", "execute"),
)


RESULT_FIELDS = (
    "candidate_key",
    "candidate_id",
    "target_group",
    "offset_days_268091",
    "offset_days_268967",
    "seed",
    "system_on_due_service",
    "on_due_service_268091",
    "on_due_service_268967",
    "minimum_product_on_due_service",
    "on_due_qty_268091",
    "demand_qty_268091",
    "on_due_qty_268967",
    "demand_qty_268967",
    "source_kind",
    "graph_sha256",
    "evidence_signature",
    "valid",
)


@dataclass(frozen=True)
class RefinementPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    source_plan: v1.CalibrationPlan
    specs: tuple[CandidateSpec, ...]
    inventory: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class V1Source:
    plan: v1.CalibrationPlan
    run_dir: Path
    evidence: dict[str, dict[str, Any]]
    artifact_hashes: dict[str, str | None]


RawExecutor = Callable[
    [coarse.Candidate, coarse.ValidatedPlan, Path, int], dict[str, Any]
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    coarse.campaign_core.write_json_atomic(path, payload)


def _write_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    coarse.campaign_core.write_csv_atomic(path, rows, fields)


def _sha256(path: Path) -> str:
    return coarse.protocol.sha256_file(path)


def _stable_sha256(payload: Any) -> str:
    return coarse.protocol.stable_sha256(payload)


def _case_key(candidate_key: str, seed: int) -> str:
    return f"{candidate_key}__seed_{seed}"


def _evidence_path(output_dir: Path, case_key: str) -> Path:
    digest = hashlib.sha256(case_key.encode("utf-8")).hexdigest()[:24]
    return output_dir / "evidence" / f"{digest}.json"


def _metric(payload: Mapping[str, Any], field: str) -> float:
    return v1._metric(payload, field)


def _quantity(payload: Mapping[str, Any], field: str) -> float:
    return v1._quantity(payload, field)


def _validate_quantities(payload: Mapping[str, Any]) -> None:
    v1._validate_quantities(payload)


def _pooled(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    return v1._pooled(rows)


def _quantile(values: Sequence[float], probability: float) -> float:
    return v1._quantile(values, probability)


def _stats(values: Sequence[float]) -> dict[str, float]:
    return v1._stats(values)


def _v1_run_manifest(plan: v1.CalibrationPlan) -> dict[str, Any]:
    return {
        "schema_version": f"{v1.SCHEMA_VERSION}.run",
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_excluded": list(HOLDOUT_SEEDS),
        "expected_case_count": plan.manifest["expected_case_count"],
        "new_case_count": plan.manifest["new_case_count"],
        "reused_case_count": plan.manifest["reused_case_count"],
    }


def _validated_v1_source(plan_dir: Path, run_dir: Path) -> V1Source:
    """Validate the complete immutable V1 run without writing to it."""

    plan = v1.validate_plan(plan_dir)
    run_dir = run_dir.resolve()
    required = (
        "run_manifest.json",
        "progress.json",
        "candidate_metrics.csv",
        "selection.json",
    )
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Incomplete V1 source run; missing={missing}")
    if (run_dir / ".multiseed_calibration.lock").exists():
        raise RuntimeError("V1 source run is still locked/running")
    if _read_json(run_dir / "run_manifest.json") != _v1_run_manifest(plan):
        raise ValueError("V1 run manifest does not match its signed plan")
    evidence = v1._load_evidence(plan, run_dir)
    expected = {str(case["case_key"]) for case in plan.manifest["cases"]}
    if set(evidence) != expected:
        raise ValueError(f"V1 evidence incomplete: {len(evidence)}/{len(expected)}")
    progress = _read_json(run_dir / "progress.json")
    if (
        progress.get("schema_version") != f"{v1.SCHEMA_VERSION}.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("status") != "complete"
        or progress.get("error") not in (None, "")
        or progress.get("completed_case_count") != len(expected)
        or progress.get("expected_case_count") != len(expected)
    ):
        raise ValueError("V1 progress does not prove a complete run")
    expected_selection, expected_points = v1._select(plan, evidence)
    if _read_json(run_dir / "selection.json") != expected_selection:
        raise ValueError("V1 selection is not reproducible from V1 evidence")
    points_path = run_dir / "selected_operating_points.json"
    if expected_points is None:
        if points_path.exists():
            raise ValueError("V1 run contains stale selected operating points")
    elif not points_path.is_file() or _read_json(points_path) != expected_points:
        raise ValueError("V1 selected operating points are not reproducible")
    artifacts: dict[str, str | None] = {
        "plan_manifest_sha256": _sha256(plan.plan_dir / "calibration_plan.json"),
        "plan_case_ledger_sha256": _sha256(plan.plan_dir / "case_ledger.csv"),
        "run_manifest_sha256": _sha256(run_dir / "run_manifest.json"),
        "progress_sha256": _sha256(run_dir / "progress.json"),
        "candidate_metrics_sha256": _sha256(run_dir / "candidate_metrics.csv"),
        "selection_sha256": _sha256(run_dir / "selection.json"),
        "selected_operating_points_sha256": (
            _sha256(points_path) if points_path.is_file() else None
        ),
    }
    return V1Source(plan, run_dir, evidence, artifacts)


def _reused_specs(source: V1Source) -> tuple[CandidateSpec, ...]:
    return tuple(
        CandidateSpec(
            key=spec.key,
            offset_days_268091=spec.offset_days_268091,
            offset_days_268967=spec.offset_days_268967,
            target_group=spec.target_group,
            evidence_mode="reuse_v1",
        )
        for spec in source.plan.specs
    )


def _canonical_op80_candidates(
    candidates: Sequence[CandidateSpec],
) -> tuple[CandidateSpec, ...]:
    result: list[CandidateSpec] = []
    for spec in candidates:
        candidate = CandidateSpec(
            key=str(spec.key),
            offset_days_268091=float(spec.offset_days_268091),
            offset_days_268967=float(spec.offset_days_268967),
            target_group=str(spec.target_group),
            evidence_mode=str(spec.evidence_mode),
        )
        if (
            not candidate.key.startswith("op80_refine_")
            or candidate.target_group != "op_80"
            or candidate.evidence_mode != "execute"
            or not math.isfinite(candidate.offset_days_268091)
            or not math.isfinite(candidate.offset_days_268967)
            or candidate.offset_days_268091 < 0.0
            or candidate.offset_days_268967 < 0.0
        ):
            raise ValueError(f"Invalid additional low-state candidate: {spec}")
        result.append(candidate)
    return tuple(result)


def load_op80_candidates(path: Path) -> tuple[CandidateSpec, ...]:
    payload = _read_json(path)
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("The op80 candidate file must contain a candidates list")
    candidates = _canonical_op80_candidates(
        tuple(
            CandidateSpec(
                key=str(row["key"]),
                offset_days_268091=float(row["offset_days_268091"]),
                offset_days_268967=float(row["offset_days_268967"]),
                target_group="op_80",
                evidence_mode="execute",
            )
            for row in rows
        )
    )
    if candidates != OP80_REFINEMENT_WAVE:
        raise ValueError("The op80 proposal does not match the frozen V2 wave")
    return candidates


def _spec_payload(spec: CandidateSpec) -> dict[str, Any]:
    return {**asdict(spec), "candidate_id": spec.candidate.candidate_id}


def _manifest_signature_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "status": manifest.get("status"),
        "interpretation": manifest.get("interpretation"),
        "source": manifest.get("source"),
        "source_hashes": manifest.get("source_hashes"),
        "cohorts": manifest.get("cohorts"),
        "candidates": manifest.get("candidates"),
        "candidate_design": manifest.get("candidate_design"),
        "inventory": manifest.get("inventory"),
        "cases": manifest.get("cases"),
        "expected_case_count": manifest.get("expected_case_count"),
        "new_case_count": manifest.get("new_case_count"),
        "reused_case_count": manifest.get("reused_case_count"),
        "selection_contract": manifest.get("selection_contract"),
        "holdout_contract": manifest.get("holdout_contract"),
        "execution_contract": manifest.get("execution_contract"),
    }


def _base_plan(source_plan: v1.CalibrationPlan) -> Any:
    return source_plan.source_plan.fine_plan.coarse_plan


def _selection_contract() -> dict[str, Any]:
    return {
        "measure": "ratio_of_summed_on_due_quantities_to_summed_demand",
        "service_window": SERVICE_WINDOW,
        "op100_minimum_global_and_each_product": REFERENCE_MINIMUM,
        "inner_pooled_and_median_bands": {
            key: list(value) for key, value in INNER_BANDS.items()
        },
        "outer_leave_one_seed_out_bands": {
            key: list(value) for key, value in OUTER_LOO_BANDS.items()
        },
        "leave_one_seed_out_count_per_candidate": len(CALIBRATION_SEEDS),
        "degraded_product_pooled_strictly_below": NON_SATURATION_LIMIT,
        "product_gap_warning_pp": PRODUCT_GAP_WARNING_PP,
        "product_gap_is_rejection_criterion": False,
        "pooled_strict_order_required_for": [
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        ],
        "same_seed_joint_strict_order_required": 4,
        "same_seed_joint_strict_order_fields": [
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        ],
        "monotone_offsets_required": True,
        "same_seed_product_demand_must_match_reference": True,
        "demand_comparison_relative_tolerance": 1e-9,
        "demand_comparison_absolute_tolerance": 1e-7,
        "tie_break": [
            "minimum_pair_maximum_absolute_global_target_error_over_pool_median_loo",
            "minimum_pair_sum_of_state_maximum_absolute_global_target_errors",
            "minimum_pair_maximum_product_service_gap_pp",
            "minimum_pair_sum_product_service_gap_pp",
            "minimum_pair_summed_global_service_iqr",
            "minimum_demand_weighted_offset_days",
            "lexicographic_candidate_ids",
        ],
        "selection_score_numeric_round_digits": 12,
        "candidate_must_have_all_five_calibration_seeds": True,
        "no_interpolation": True,
        "no_holdout_retuning": True,
    }


def _holdout_contract() -> dict[str, Any]:
    return {
        "status": "sealed_unread",
        "status_only_if_passed": "holdout_validated_30_seed",
        "fixed_point_count": 3,
        "seeds": list(HOLDOUT_SEEDS),
        "seed_count": len(HOLDOUT_SEEDS),
        "baseline_case_count": 3 * len(HOLDOUT_SEEDS),
        "cases_in_this_plan": 0,
        "service_window": SERVICE_WINDOW,
        "op100_minimum_global_and_each_product": REFERENCE_MINIMUM,
        "op93_global_pooled_and_median_band": [0.915, 0.945],
        "op80_global_pooled_and_median_band": [0.785, 0.815],
        "degraded_product_strictly_below": NON_SATURATION_LIMIT,
        "pooled_strict_order_required_for": [
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        ],
        "same_seed_joint_strict_order_required": 24,
        "bootstrap_repetitions_descriptive": 10000,
        "retuning_after_holdout": False,
        "selected_output_status": (
            "selected_on_five_seed_refinement_pending_30_seed_holdout"
        ),
        "failure_rule": (
            "No pair passing the five-seed LOO screen means no holdout launch "
            "and no target-state claim."
        ),
    }


def _execution_contract() -> dict[str, Any]:
    return {
        "scenario": "scn:BASE",
        "common_random_numbers": True,
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "quality_incident": False,
        "supplier_availability_incident": False,
        "capacity_override": False,
        "acute_incident": False,
        "state_dependent_risk": False,
        "changed_dimension": "planned_supplier_lead_time_days_only",
        "maximum_workers": 2,
        "v1_evidence_is_read_only": True,
    }


def _candidate_design(proposal_path: Path) -> dict[str, Any]:
    return {
        "fixed_op93_candidates": [_spec_payload(spec) for spec in OP93_REFINEMENT_WAVE],
        "fixed_op80_candidates": [_spec_payload(spec) for spec in OP80_REFINEMENT_WAVE],
        "op80_candidates_file": proposal_path.name,
        "op80_candidates_sha256": _sha256(proposal_path),
        "op80_candidates_frozen_count": len(OP80_REFINEMENT_WAVE),
        "interpolation_used": False,
    }


def prepare_plan(
    output_dir: Path,
    *,
    source_plan_dir: Path = DEFAULT_SOURCE_PLAN,
    source_run_dir: Path = DEFAULT_SOURCE_RUN,
    op80_candidates: Sequence[CandidateSpec] = OP80_REFINEMENT_WAVE,
) -> Path:
    """Freeze a V2 plan before any V2 candidate is executed."""

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite refinement plan: {output_dir}")
    source = _validated_v1_source(source_plan_dir, source_run_dir)
    low_specs = _canonical_op80_candidates(op80_candidates)
    if low_specs != OP80_REFINEMENT_WAVE:
        raise ValueError("The low-state candidates must match the frozen V2 wave")
    specs = _reused_specs(source) + OP93_REFINEMENT_WAVE + low_specs
    if len({spec.key for spec in specs}) != len(specs):
        raise ValueError("Duplicate candidate key")
    if len({spec.candidate.candidate_id for spec in specs}) != len(specs):
        raise ValueError("Duplicate physical candidate")
    output_dir.mkdir(parents=True)
    base = _base_plan(source.plan)
    source_graph = coarse._read_json(base.source_graph)
    inventory: dict[str, dict[str, Any]] = {}
    for spec in specs:
        graph, changes = coarse.apply_product_delays(
            source_graph,
            base.lanes_by_product,
            offset_days_268091=spec.offset_days_268091,
            offset_days_268967=spec.offset_days_268967,
        )
        relative_graph = Path("inputs") / spec.key / "candidate_graph.json"
        relative_ledger = Path("inputs") / spec.key / "change_ledger.json"
        graph_path = output_dir / relative_graph
        ledger_path = output_dir / relative_ledger
        graph_path.parent.mkdir(parents=True)
        _write_json(graph_path, graph)
        _write_json(
            ledger_path,
            {
                "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
                **_spec_payload(spec),
                "changed_dimension": "planned_supplier_lead_time_days",
                "changes": changes,
            },
        )
        inventory[spec.key] = {
            "graph_path": relative_graph.as_posix(),
            "graph_sha256": _sha256(graph_path),
            "change_ledger_path": relative_ledger.as_posix(),
            "change_ledger_sha256": _sha256(ledger_path),
        }
    proposal = {
        "schema_version": f"{PLAN_SCHEMA_VERSION}.op80_candidates",
        "status": "pre_registered_before_v2_execution",
        "candidates": [_spec_payload(spec) for spec in low_specs],
    }
    proposal_path = output_dir / "op80_refinement_candidates.json"
    _write_json(proposal_path, proposal)
    source_evidence_hashes = {
        key: _sha256(v1._evidence_path(source.run_dir, key))
        for key in sorted(source.evidence)
    }
    cases = [
        {
            "case_key": _case_key(spec.key, seed),
            "candidate_key": spec.key,
            "seed": seed,
            "evidence_mode": spec.evidence_mode,
        }
        for spec in specs
        for seed in CALIBRATION_SEEDS
    ]
    cohorts = {
        "design": list(DESIGN_SEEDS),
        "calibration": list(CALIBRATION_SEEDS),
        "holdout_sealed": list(HOLDOUT_SEEDS),
    }
    cohort_sets = [set(values) for values in cohorts.values()]
    if any(
        cohort_sets[left] & cohort_sets[right]
        for left in range(len(cohort_sets))
        for right in range(left + 1, len(cohort_sets))
    ):
        raise ValueError("Design, calibration and holdout cohorts must be disjoint")
    manifest: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": "planned_not_executed",
        "created_at_utc": _now(),
        "interpretation": INTERPRETATION,
        "source": {
            "v1_plan_dir": str(source.plan.plan_dir),
            "v1_plan_signature": source.plan.manifest["plan_signature"],
            "v1_run_dir": str(source.run_dir),
            "v1_selection_status": _read_json(source.run_dir / "selection.json")[
                "status"
            ],
            "v1_artifact_hashes": source.artifact_hashes,
            "reused_evidence_sha256": source_evidence_hashes,
            "relationship": "additive_refinement_reusing_all_v1_evidence",
        },
        "source_hashes": {
            "source_graph_sha256": _sha256(base.source_graph),
            "engine_sha256": _sha256(base.engine),
            "profile_sha256": _sha256(base.profile),
            "driver_sha256": _sha256(Path(__file__).resolve()),
            "v1_driver_sha256": _sha256(Path(v1.__file__).resolve()),
        },
        "cohorts": cohorts,
        "candidates": [_spec_payload(spec) for spec in specs],
        "candidate_design": _candidate_design(proposal_path),
        "inventory": inventory,
        "cases": cases,
        "expected_case_count": len(cases),
        "new_case_count": sum(case["evidence_mode"] == "execute" for case in cases),
        "reused_case_count": sum(case["evidence_mode"] == "reuse_v1" for case in cases),
        "selection_contract": _selection_contract(),
        "holdout_contract": _holdout_contract(),
        "execution_contract": _execution_contract(),
    }
    manifest["plan_signature"] = _stable_sha256(_manifest_signature_payload(manifest))
    _write_json(output_dir / "refinement_plan.json", manifest)
    _write_csv(
        output_dir / "case_ledger.csv",
        cases,
        ("case_key", "candidate_key", "seed", "evidence_mode"),
    )
    return output_dir


def _parse_specs(rows: Sequence[Mapping[str, Any]]) -> tuple[CandidateSpec, ...]:
    return tuple(
        CandidateSpec(
            key=str(row["key"]),
            offset_days_268091=float(row["offset_days_268091"]),
            offset_days_268967=float(row["offset_days_268967"]),
            target_group=str(row["target_group"]),
            evidence_mode=str(row["evidence_mode"]),
        )
        for row in rows
    )


def validate_plan(plan_dir: Path) -> RefinementPlan:
    plan_dir = plan_dir.resolve()
    manifest_path = plan_dir / "refinement_plan.json"
    ledger_path = plan_dir / "case_ledger.csv"
    proposal_path = plan_dir / "op80_refinement_candidates.json"
    if not all(path.is_file() for path in (manifest_path, ledger_path, proposal_path)):
        raise FileNotFoundError(f"Incomplete V2 refinement plan: {plan_dir}")
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "planned_not_executed"
        or manifest.get("plan_signature")
        != _stable_sha256(_manifest_signature_payload(manifest))
        or manifest.get("source_hashes", {}).get("driver_sha256")
        != _sha256(Path(__file__).resolve())
        or manifest.get("cohorts")
        != {
            "design": list(DESIGN_SEEDS),
            "calibration": list(CALIBRATION_SEEDS),
            "holdout_sealed": list(HOLDOUT_SEEDS),
        }
    ):
        raise ValueError("V2 refinement plan/signature mismatch")
    if (
        manifest.get("interpretation") != INTERPRETATION
        or manifest.get("selection_contract") != _selection_contract()
        or manifest.get("holdout_contract") != _holdout_contract()
        or manifest.get("execution_contract") != _execution_contract()
    ):
        raise ValueError("V2 signed scientific contracts are not canonical")
    source_info = manifest.get("source") or {}
    source = _validated_v1_source(
        Path(str(source_info.get("v1_plan_dir") or "")),
        Path(str(source_info.get("v1_run_dir") or "")),
    )
    current_evidence_hashes = {
        key: _sha256(v1._evidence_path(source.run_dir, key))
        for key in sorted(source.evidence)
    }
    if (
        source.plan.manifest["plan_signature"] != source_info.get("v1_plan_signature")
        or source.artifact_hashes != source_info.get("v1_artifact_hashes")
        or current_evidence_hashes != source_info.get("reused_evidence_sha256")
        or source_info.get("relationship")
        != "additive_refinement_reusing_all_v1_evidence"
        or source_info.get("v1_selection_status")
        != _read_json(source.run_dir / "selection.json").get("status")
    ):
        raise ValueError("V1 source evidence changed after V2 planning")
    design = manifest.get("candidate_design") or {}
    proposal = _read_json(proposal_path)
    if (
        design != _candidate_design(proposal_path)
        or proposal.get("schema_version") != f"{PLAN_SCHEMA_VERSION}.op80_candidates"
        or proposal.get("status") != "pre_registered_before_v2_execution"
    ):
        raise ValueError("V2 low-state candidate design changed")
    low_specs = _canonical_op80_candidates(_parse_specs(proposal["candidates"]))
    expected_specs = _reused_specs(source) + OP93_REFINEMENT_WAVE + low_specs
    specs = _parse_specs(manifest.get("candidates") or [])
    if (
        specs != expected_specs
        or [_spec_payload(spec) for spec in specs] != manifest.get("candidates")
        or [_spec_payload(spec) for spec in OP93_REFINEMENT_WAVE]
        != design.get("fixed_op93_candidates")
        or [_spec_payload(spec) for spec in OP80_REFINEMENT_WAVE]
        != design.get("fixed_op80_candidates")
        or low_specs != OP80_REFINEMENT_WAVE
        or len(low_specs) != design.get("op80_candidates_frozen_count")
    ):
        raise ValueError("V2 candidate catalogue is not canonical")
    if len({spec.key for spec in specs}) != len(specs) or len(
        {spec.candidate.candidate_id for spec in specs}
    ) != len(specs):
        raise ValueError("Duplicate V2 candidate")
    expected_cases = [
        {
            "case_key": _case_key(spec.key, seed),
            "candidate_key": spec.key,
            "seed": seed,
            "evidence_mode": spec.evidence_mode,
        }
        for spec in specs
        for seed in CALIBRATION_SEEDS
    ]
    expected_new = sum(case["evidence_mode"] == "execute" for case in expected_cases)
    if (
        manifest.get("cases") != expected_cases
        or manifest.get("expected_case_count") != len(expected_cases)
        or manifest.get("new_case_count") != expected_new
        or manifest.get("reused_case_count") != len(expected_cases) - expected_new
        or (manifest.get("holdout_contract") or {}).get("cases_in_this_plan") != 0
    ):
        raise ValueError("V2 case catalogue/count mismatch")
    base = _base_plan(source.plan)
    expected_hashes = {
        "source_graph_sha256": _sha256(base.source_graph),
        "engine_sha256": _sha256(base.engine),
        "profile_sha256": _sha256(base.profile),
        "driver_sha256": _sha256(Path(__file__).resolve()),
        "v1_driver_sha256": _sha256(Path(v1.__file__).resolve()),
    }
    if manifest.get("source_hashes") != expected_hashes:
        raise ValueError("V2 source hashes changed")
    inventory = dict(manifest.get("inventory") or {})
    source_graph = coarse._read_json(base.source_graph)
    for spec in specs:
        item = inventory.get(spec.key) or {}
        graph_path = plan_dir / str(item.get("graph_path") or "")
        change_path = plan_dir / str(item.get("change_ledger_path") or "")
        expected_graph, expected_changes = coarse.apply_product_delays(
            source_graph,
            base.lanes_by_product,
            offset_days_268091=spec.offset_days_268091,
            offset_days_268967=spec.offset_days_268967,
        )
        expected_change_payload = {
            "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
            **_spec_payload(spec),
            "changed_dimension": "planned_supplier_lead_time_days",
            "changes": expected_changes,
        }
        if (
            not graph_path.is_file()
            or not change_path.is_file()
            or coarse._read_json(graph_path) != expected_graph
            or _read_json(change_path) != expected_change_payload
            or _sha256(graph_path) != item.get("graph_sha256")
            or _sha256(change_path) != item.get("change_ledger_sha256")
        ):
            raise ValueError(f"V2 candidate input changed: {spec.key}")
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as stream:
        actual_cases = list(csv.DictReader(stream))
    canonical_cases = [
        {key: str(value) for key, value in row.items()} for row in expected_cases
    ]
    if actual_cases != canonical_cases:
        raise ValueError("V2 case ledger changed")
    return RefinementPlan(plan_dir, manifest, source.plan, specs, inventory)


def _spec(plan: RefinementPlan, key: str) -> CandidateSpec:
    matches = [spec for spec in plan.specs if spec.key == key]
    if len(matches) != 1:
        raise ValueError(f"Unknown V2 candidate: {key}")
    return matches[0]


def _adapter(plan: RefinementPlan, spec: CandidateSpec) -> coarse.ValidatedPlan:
    candidate = spec.candidate
    item = plan.inventory[spec.key]
    base = _base_plan(plan.source_plan)
    return coarse.ValidatedPlan(
        plan_dir=plan.plan_dir,
        manifest={
            "plan_signature": plan.manifest["plan_signature"],
            "targets": [0.93, 0.80],
            "target_tolerance": 0.015,
        },
        candidates=(candidate,),
        inventory={
            candidate.candidate_id: {
                **asdict(candidate),
                "graph_path": item["graph_path"],
                "graph_sha256": item["graph_sha256"],
            }
        },
        lanes_by_product=base.lanes_by_product,
        source_graph=base.source_graph,
        engine=base.engine,
        profile=base.profile,
    )


def _wrap_evidence(
    plan: RefinementPlan,
    spec: CandidateSpec,
    seed: int,
    source: Mapping[str, Any],
    *,
    source_kind: str,
    source_v1_case_key: str = "",
    reused_from: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "case_key": _case_key(spec.key, seed),
        **_spec_payload(spec),
        "candidate_key": spec.key,
        "seed": seed,
        "source_kind": source_kind,
        "source_v1_case_key": source_v1_case_key,
        "reused_from": reused_from,
        "source_evidence": dict(source),
        "metrics": dict(source.get("metrics") or {}),
        "graph_sha256": str(source.get("graph_sha256") or ""),
        "engine_sha256": str(source.get("engine_sha256") or ""),
        "valid": True,
        "created_at_utc": _now(),
    }
    payload["evidence_signature"] = _stable_sha256(payload)
    return payload


def _validate_evidence(
    payload: Mapping[str, Any], plan: RefinementPlan
) -> tuple[str, int]:
    unsigned = dict(payload)
    signature = str(unsigned.pop("evidence_signature", ""))
    key = str(payload.get("candidate_key") or "")
    seed = int(payload.get("seed") or -1)
    spec = _spec(plan, key)
    source = payload.get("source_evidence") or {}
    adapter = _adapter(plan, spec)
    allowed_kind = {
        "reuse_v1": "reused_v1_calibration_evidence",
        "execute": "canonical_v2_refinement_execution",
    }[spec.evidence_mode]
    if (
        payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or signature != _stable_sha256(unsigned)
        or payload.get("case_key") != _case_key(key, seed)
        or seed not in CALIBRATION_SEEDS
        or payload.get("candidate_id") != spec.candidate.candidate_id
        or float(payload.get("offset_days_268091")) != spec.offset_days_268091
        or float(payload.get("offset_days_268967")) != spec.offset_days_268967
        or payload.get("target_group") != spec.target_group
        or payload.get("evidence_mode") != spec.evidence_mode
        or payload.get("source_kind") != allowed_kind
        or payload.get("valid") is not True
    ):
        raise ValueError(f"V2 evidence contract mismatch: {key}/{seed}")
    coarse._validate_evidence(source, spec.candidate, adapter, seed)
    if (
        payload.get("metrics") != source.get("metrics")
        or payload.get("graph_sha256") != plan.inventory[key]["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
    ):
        raise ValueError(f"V2/source evidence mismatch: {key}/{seed}")
    if spec.evidence_mode == "reuse_v1":
        source_key = str(payload.get("source_v1_case_key") or "")
        expected_key = v1._case_key(spec.key, seed)
        expected_hash = plan.manifest["source"]["reused_evidence_sha256"].get(
            expected_key
        )
        reused_path = Path(str(payload.get("reused_from") or ""))
        if (
            source_key != expected_key
            or not expected_hash
            or not reused_path.is_file()
            or reused_path
            != v1._evidence_path(
                Path(plan.manifest["source"]["v1_run_dir"]), expected_key
            )
            or _sha256(reused_path) != expected_hash
        ):
            raise ValueError(f"V2 reused evidence provenance mismatch: {key}/{seed}")
    elif payload.get("source_v1_case_key") or payload.get("reused_from"):
        raise ValueError(f"Unexpected V1 provenance on new evidence: {key}/{seed}")
    _validate_quantities(payload)
    return key, seed


def _load_evidence(plan: RefinementPlan, output_dir: Path) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((output_dir / "evidence").glob("*.json")):
        payload = _read_json(path)
        key, seed = _validate_evidence(payload, plan)
        case_key = _case_key(key, seed)
        if case_key in found or path != _evidence_path(output_dir, case_key):
            raise ValueError(f"Duplicate or misnamed V2 evidence: {case_key}")
        found[case_key] = payload
    return found


def _result_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_key": payload["candidate_key"],
        "candidate_id": payload["candidate_id"],
        "target_group": payload["target_group"],
        "offset_days_268091": payload["offset_days_268091"],
        "offset_days_268967": payload["offset_days_268967"],
        "seed": payload["seed"],
        **{
            field: _metric(payload, field)
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
                "minimum_product_on_due_service",
            )
        },
        **{
            field: _quantity(payload, field)
            for field in (
                "on_due_qty_268091",
                "demand_qty_268091",
                "on_due_qty_268967",
                "demand_qty_268967",
            )
        },
        "source_kind": payload["source_kind"],
        "graph_sha256": payload["graph_sha256"],
        "evidence_signature": payload["evidence_signature"],
        "valid": payload["valid"],
    }


def _write_progress(
    output_dir: Path,
    plan: RefinementPlan,
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    status: str,
    error: str = "",
) -> None:
    rows = sorted(
        (_result_row(row) for row in evidence.values()),
        key=lambda row: (row["candidate_key"], row["seed"]),
    )
    _write_csv(output_dir / "candidate_metrics.csv", rows, RESULT_FIELDS)
    _write_json(
        output_dir / "progress.json",
        {
            "schema_version": f"{SCHEMA_VERSION}.progress",
            "plan_signature": plan.manifest["plan_signature"],
            "status": status,
            "completed_case_count": len(evidence),
            "expected_case_count": plan.manifest["expected_case_count"],
            "new_case_count": plan.manifest["new_case_count"],
            "reused_case_count": plan.manifest["reused_case_count"],
            "holdout_case_count": 0,
            "error": error,
            "updated_at_utc": _now(),
        },
    )


def _leave_one_seed_out(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    by_seed = {int(row["seed"]): row for row in rows}
    if set(by_seed) != set(CALIBRATION_SEEDS):
        raise ValueError("Candidate must contain each calibration seed exactly once")
    return {
        str(seed): _pooled([row for other, row in by_seed.items() if other != seed])
        for seed in CALIBRATION_SEEDS
    }


def _candidate_summary(
    spec: CandidateSpec, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if len(rows) != len(CALIBRATION_SEEDS):
        raise ValueError(f"Incomplete candidate: {spec.key}")
    for row in rows:
        _validate_quantities(row)
    pooled = _pooled(rows)
    loo = _leave_one_seed_out(rows)
    service_fields = (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
        "minimum_product_on_due_service",
    )
    per_seed = {
        field: {str(int(row["seed"])): _metric(row, field) for row in rows}
        for field in service_fields[:-1]
    }
    stats = {
        field: _stats([_metric(row, field) for row in rows]) for field in service_fields
    }
    target = TARGETS[spec.target_group]
    reasons: list[str] = []
    if spec.target_group == "op_100":
        if any(
            pooled[field] < REFERENCE_MINIMUM - 1e-12 for field in service_fields[:3]
        ):
            reasons.append("reference_below_98p5pct")
    else:
        lower, upper = INNER_BANDS[spec.target_group]
        global_median = stats["system_on_due_service"]["median"]
        if not lower - 1e-12 <= pooled["system_on_due_service"] <= upper + 1e-12:
            reasons.append("pooled_global_service_outside_inner_band")
        if not lower - 1e-12 <= global_median <= upper + 1e-12:
            reasons.append("median_global_service_outside_inner_band")
        loo_lower, loo_upper = OUTER_LOO_BANDS[spec.target_group]
        failing_loo = [
            seed
            for seed, metrics in loo.items()
            if not loo_lower - 1e-12
            <= metrics["system_on_due_service"]
            <= loo_upper + 1e-12
        ]
        if failing_loo:
            reasons.append("leave_one_seed_out_global_service_outside_outer_band")
        if any(
            pooled[field] >= NON_SATURATION_LIMIT - 1e-12
            for field in ("on_due_service_268091", "on_due_service_268967")
        ):
            reasons.append("degraded_product_pooled_saturated")
    estimator_services = {
        "pooled": pooled["system_on_due_service"],
        "median": stats["system_on_due_service"]["median"],
        **{
            f"loo_without_seed_{seed}": metrics["system_on_due_service"]
            for seed, metrics in loo.items()
        },
    }
    errors = {key: abs(service - target) for key, service in estimator_services.items()}
    gap_pp = 100.0 * abs(
        pooled["on_due_service_268091"] - pooled["on_due_service_268967"]
    )
    return {
        **_spec_payload(spec),
        "target_service": target,
        "replication_count": len(rows),
        "pooled_ratio_of_sums": pooled,
        "individual_seed_metrics": stats,
        "service_by_seed": per_seed,
        "leave_one_seed_out_ratio_of_sums": loo,
        "global_target_error_by_estimator": errors,
        "maximum_absolute_global_target_error": max(errors.values()),
        "total_absolute_global_target_error": sum(errors.values()),
        "global_service_iqr": stats["system_on_due_service"]["iqr"],
        "product_service_gap_pp": gap_pp,
        "product_gap_warning": gap_pp > PRODUCT_GAP_WARNING_PP + 1e-12,
        "admissible_individually": not reasons,
        "exclusion_reasons": reasons,
    }


def _pair_score(high: Mapping[str, Any], low: Mapping[str, Any]) -> tuple[Any, ...]:
    demands = high["pooled_ratio_of_sums"]
    total_demand = demands["demand_qty_268091"] + demands["demand_qty_268967"]
    weighted_offset = (
        (high["offset_days_268091"] + low["offset_days_268091"])
        * demands["demand_qty_268091"]
        + (high["offset_days_268967"] + low["offset_days_268967"])
        * demands["demand_qty_268967"]
    ) / total_demand
    numeric = (
        max(
            high["maximum_absolute_global_target_error"],
            low["maximum_absolute_global_target_error"],
        ),
        high["maximum_absolute_global_target_error"]
        + low["maximum_absolute_global_target_error"],
        max(high["product_service_gap_pp"], low["product_service_gap_pp"]),
        high["product_service_gap_pp"] + low["product_service_gap_pp"],
        high["global_service_iqr"] + low["global_service_iqr"],
        weighted_offset,
    )
    return (
        *(round(float(value), 12) for value in numeric),
        str(high["candidate_id"]),
        str(low["candidate_id"]),
    )


def _validate_comparable_demand(
    plan: RefinementPlan, evidence: Mapping[str, Mapping[str, Any]]
) -> None:
    references = [spec for spec in plan.specs if spec.target_group == "op_100"]
    if len(references) != 1:
        raise ValueError("Selection expects exactly one reference candidate")
    reference = references[0]
    for seed in CALIBRATION_SEEDS:
        reference_row = evidence[_case_key(reference.key, seed)]
        for spec in plan.specs:
            row = evidence[_case_key(spec.key, seed)]
            for product in ("268091", "268967"):
                field = f"demand_qty_{product}"
                expected = _quantity(reference_row, field)
                actual = _quantity(row, field)
                if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-7):
                    raise ValueError(
                        "Demand mismatch across candidates for "
                        f"seed={seed}, product={product}, candidate={spec.key}: "
                        f"{actual} != {expected}"
                    )


def _select(
    plan: RefinementPlan, evidence: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    _validate_comparable_demand(plan, evidence)
    summaries = {
        spec.key: _candidate_summary(
            spec,
            [evidence[_case_key(spec.key, seed)] for seed in CALIBRATION_SEEDS],
        )
        for spec in plan.specs
    }
    references = [
        row
        for row in summaries.values()
        if row["target_group"] == "op_100" and row["admissible_individually"]
    ]
    if len(references) > 1:
        raise ValueError("Selection expects at most one admissible reference")
    reference = references[0] if references else None
    candidates_93 = [
        row
        for row in summaries.values()
        if row["target_group"] == "op_93" and row["admissible_individually"]
    ]
    candidates_80 = [
        row
        for row in summaries.values()
        if row["target_group"] == "op_80" and row["admissible_individually"]
    ]
    order_fields = (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
    )
    eligible_pairs: list[dict[str, Any]] = []
    if reference is not None:
        for high in candidates_93:
            for low in candidates_80:
                monotone_offsets = (
                    low["offset_days_268091"] >= high["offset_days_268091"]
                    and low["offset_days_268967"] >= high["offset_days_268967"]
                )
                pooled_order = {
                    field: (
                        reference["pooled_ratio_of_sums"][field]
                        > high["pooled_ratio_of_sums"][field]
                        > low["pooled_ratio_of_sums"][field]
                    )
                    for field in order_fields
                }
                per_field_count = {
                    field: sum(
                        reference["service_by_seed"][field][str(seed)]
                        > high["service_by_seed"][field][str(seed)]
                        > low["service_by_seed"][field][str(seed)]
                        for seed in CALIBRATION_SEEDS
                    )
                    for field in order_fields
                }
                joint_count = sum(
                    all(
                        reference["service_by_seed"][field][str(seed)]
                        > high["service_by_seed"][field][str(seed)]
                        > low["service_by_seed"][field][str(seed)]
                        for field in order_fields
                    )
                    for seed in CALIBRATION_SEEDS
                )
                if (
                    not monotone_offsets
                    or not all(pooled_order.values())
                    or joint_count < 4
                ):
                    continue
                score = _pair_score(high, low)
                eligible_pairs.append(
                    {
                        "op93_candidate_key": high["key"],
                        "op80_candidate_key": low["key"],
                        "monotone_offsets": monotone_offsets,
                        "pooled_strict_order": pooled_order,
                        "per_seed_strict_order_count": per_field_count,
                        "same_seed_joint_strict_order_count": joint_count,
                        "selection_score": list(score),
                    }
                )
    eligible_pairs.sort(key=lambda row: tuple(row["selection_score"]))
    chosen = eligible_pairs[0] if eligible_pairs else None
    selection: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": (
            "five_seed_loo_screen_passed_pending_holdout"
            if chosen
            else "five_seed_loo_screen_failed_no_holdout"
        ),
        "plan_signature": plan.manifest["plan_signature"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_sealed_and_unread": list(HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "candidate_summaries": list(summaries.values()),
        "eligible_pairs": eligible_pairs,
        "selected_pair": chosen,
        "selection_contract": plan.manifest["selection_contract"],
        "holdout_contract": plan.manifest["holdout_contract"],
        "holdout_launch_permitted": chosen is not None,
        "fallback_required": chosen is None,
    }
    selection["selection_signature"] = _stable_sha256(selection)
    if chosen is None:
        return selection, None
    selected_keys = {
        "op_100": str(reference["key"]),
        "op_93": chosen["op93_candidate_key"],
        "op_80": chosen["op80_candidate_key"],
    }
    labels = {
        "op_100": "Fonctionnement de reference simule",
        "op_93": "Fonctionnement intermediaire simule (cible globale 93 %)",
        "op_80": "Fonctionnement degrade simule (cible globale 80 %)",
    }
    selected: dict[str, Any] = {
        "schema_version": POINTS_SCHEMA_VERSION,
        "status": "selected_on_five_seed_refinement_pending_30_seed_holdout",
        "plan": {
            "path": str(plan.plan_dir),
            "plan_signature": plan.manifest["plan_signature"],
        },
        "selection_signature": selection["selection_signature"],
        "selection": {
            "relative_path": "selection.json",
            "schema_version": SELECTION_SCHEMA_VERSION,
            "selection_signature": selection["selection_signature"],
        },
        "source_hashes": plan.manifest["source_hashes"],
        "service_evaluation_window": SERVICE_WINDOW,
        "cohorts": plan.manifest["cohorts"],
        "holdout_contract": plan.manifest["holdout_contract"],
        "simulation_hypotheses_not_observed_performance": True,
        "target_labels_apply_to_global_service_only": True,
        "holdout_validated": False,
        "holdout_cases_read": 0,
        "operating_points": [],
    }
    for point_id, candidate_key in selected_keys.items():
        summary = summaries[candidate_key]
        spec = _spec(plan, candidate_key)
        selected["operating_points"].append(
            {
                "operating_point_id": point_id,
                "operating_point_label": labels[point_id],
                "target_service": summary["target_service"],
                "calibration_pooled_service": summary["pooled_ratio_of_sums"][
                    "system_on_due_service"
                ],
                "calibration_median_service": summary["individual_seed_metrics"][
                    "system_on_due_service"
                ]["median"],
                "calibration_product_268091_service": summary["pooled_ratio_of_sums"][
                    "on_due_service_268091"
                ],
                "calibration_product_268967_service": summary["pooled_ratio_of_sums"][
                    "on_due_service_268967"
                ],
                "maximum_global_target_error_over_pool_median_and_leave_one_out": summary[
                    "maximum_absolute_global_target_error"
                ],
                "candidate_key": candidate_key,
                "candidate_id": spec.candidate.candidate_id,
                "offset_days_268091": spec.offset_days_268091,
                "offset_days_268967": spec.offset_days_268967,
                "graph": str(
                    (
                        plan.plan_dir / plan.inventory[candidate_key]["graph_path"]
                    ).resolve()
                ),
                "graph_sha256": plan.inventory[candidate_key]["graph_sha256"],
            }
        )
    selected["artifact_signature"] = _stable_sha256(selected)
    return selection, selected


def finalize(
    plan: RefinementPlan,
    output_dir: Path,
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected = {str(case["case_key"]) for case in plan.manifest["cases"]}
    if set(evidence) != expected:
        raise ValueError(f"V2 refinement incomplete: {len(evidence)}/{len(expected)}")
    selection, selected = _select(plan, evidence)
    _write_json(output_dir / "selection.json", selection)
    destination = output_dir / "selected_operating_points.json"
    if selected is not None:
        _write_json(destination, selected)
    elif destination.exists():
        raise RuntimeError("Refusing stale selected points after failed V2 selection")
    return {"selection": selection, "selected_operating_points": selected}


def validate_selected_operating_points(path: Path) -> dict[str, Any]:
    """Fail closed on the complete signed V2 selection provenance chain."""

    path = path.resolve()
    payload = _read_json(path)
    unsigned = dict(payload)
    artifact_signature = str(unsigned.pop("artifact_signature", ""))
    if (
        payload.get("schema_version") != POINTS_SCHEMA_VERSION
        or payload.get("status")
        != "selected_on_five_seed_refinement_pending_30_seed_holdout"
        or not artifact_signature
        or artifact_signature != _stable_sha256(unsigned)
        or payload.get("simulation_hypotheses_not_observed_performance") is not True
        or payload.get("target_labels_apply_to_global_service_only") is not True
        or payload.get("holdout_validated") is not False
        or payload.get("holdout_cases_read") != 0
    ):
        raise ValueError("Invalid V2 selected operating-point artifact/signature")
    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, Mapping):
        raise ValueError("V2 selected points have no signed plan reference")
    plan_path = Path(str(plan_reference.get("path") or ""))
    if not plan_path.is_absolute():
        plan_path = path.parent / plan_path
    plan = validate_plan(plan_path.resolve())
    if (
        plan_reference.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("source_hashes") != plan.manifest["source_hashes"]
        or payload.get("cohorts") != plan.manifest["cohorts"]
        or payload.get("holdout_contract") != plan.manifest["holdout_contract"]
        or payload.get("service_evaluation_window") != SERVICE_WINDOW
    ):
        raise ValueError("V2 selected points do not match their signed plan")
    selection_reference = payload.get("selection")
    if not isinstance(selection_reference, Mapping):
        raise ValueError("V2 selected points have no selection provenance")
    relative_selection = Path(str(selection_reference.get("relative_path") or ""))
    selection_path = (path.parent / relative_selection).resolve()
    if (
        relative_selection.is_absolute()
        or selection_path.parent != path.parent
        or selection_path.name != "selection.json"
        or not selection_path.is_file()
    ):
        raise ValueError("V2 selection provenance must be the sibling selection.json")
    selection = _read_json(selection_path)
    unsigned_selection = dict(selection)
    selection_signature = str(unsigned_selection.pop("selection_signature", ""))
    if (
        selection_reference.get("schema_version") != SELECTION_SCHEMA_VERSION
        or selection_reference.get("selection_signature") != selection_signature
        or payload.get("selection_signature") != selection_signature
        or not selection_signature
        or selection_signature != _stable_sha256(unsigned_selection)
        or selection.get("schema_version") != SELECTION_SCHEMA_VERSION
        or selection.get("status") != "five_seed_loo_screen_passed_pending_holdout"
        or selection.get("plan_signature") != plan.manifest["plan_signature"]
        or selection.get("calibration_seeds") != list(CALIBRATION_SEEDS)
        or selection.get("holdout_seeds_sealed_and_unread") != list(HOLDOUT_SEEDS)
        or selection.get("holdout_cases_read") != 0
        or selection.get("selection_contract") != plan.manifest["selection_contract"]
        or selection.get("holdout_contract") != plan.manifest["holdout_contract"]
        or selection.get("holdout_launch_permitted") is not True
        or selection.get("fallback_required") is not False
    ):
        raise ValueError("Invalid V2 selection evidence/signature")
    selected_pair = selection.get("selected_pair")
    eligible_pairs = selection.get("eligible_pairs")
    if (
        not isinstance(selected_pair, Mapping)
        or not isinstance(eligible_pairs, list)
        or not eligible_pairs
        or selected_pair != eligible_pairs[0]
    ):
        raise ValueError("V2 selection has no canonical winning pair")
    run_manifest_path = path.parent / "run_manifest.json"
    progress_path = path.parent / "progress.json"
    if (
        not run_manifest_path.is_file()
        or _read_json(run_manifest_path) != _run_manifest(plan)
        or not progress_path.is_file()
    ):
        raise ValueError("V2 selected points have no complete registered run")
    progress = _read_json(progress_path)
    if (
        progress.get("schema_version") != f"{SCHEMA_VERSION}.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("status") != "complete"
        or progress.get("completed_case_count") != plan.manifest["expected_case_count"]
        or progress.get("expected_case_count") != plan.manifest["expected_case_count"]
        or progress.get("holdout_case_count") != 0
        or progress.get("error") not in (None, "")
    ):
        raise ValueError("V2 selected points come from an incomplete run")
    evidence = _load_evidence(plan, path.parent)
    expected_cases = {str(case["case_key"]) for case in plan.manifest["cases"]}
    if set(evidence) != expected_cases:
        raise ValueError("V2 selected points do not have complete evidence")
    reproduced_selection, reproduced_payload = _select(plan, evidence)
    if selection != reproduced_selection or payload != reproduced_payload:
        raise ValueError("V2 selected points are not reproducible from evidence")
    references = [spec for spec in plan.specs if spec.target_group == "op_100"]
    if len(references) != 1:
        raise ValueError("V2 plan has no unique reference")
    expected_keys = {
        "op_100": references[0].key,
        "op_93": str(selected_pair.get("op93_candidate_key") or ""),
        "op_80": str(selected_pair.get("op80_candidate_key") or ""),
    }
    rows = payload.get("operating_points")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("V2 selection must expose exactly three operating points")
    by_id = {
        str(row.get("operating_point_id") or ""): row
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != set(expected_keys) or len(by_id) != 3:
        raise ValueError("V2 operating-point identifiers are not canonical")
    for point_id, candidate_key in expected_keys.items():
        point = by_id[point_id]
        spec = _spec(plan, candidate_key)
        graph = (plan.plan_dir / plan.inventory[candidate_key]["graph_path"]).resolve()
        if (
            point.get("candidate_key") != candidate_key
            or point.get("candidate_id") != spec.candidate.candidate_id
            or float(point.get("offset_days_268091")) != spec.offset_days_268091
            or float(point.get("offset_days_268967")) != spec.offset_days_268967
            or Path(str(point.get("graph") or "")).resolve() != graph
            or point.get("graph_sha256")
            != plan.inventory[candidate_key]["graph_sha256"]
            or _sha256(graph) != point.get("graph_sha256")
            or float(point.get("target_service")) != TARGETS[point_id]
        ):
            raise ValueError(f"V2 selected point differs from plan: {point_id}")
        for field in (
            "calibration_pooled_service",
            "calibration_median_service",
            "calibration_product_268091_service",
            "calibration_product_268967_service",
            "maximum_global_target_error_over_pool_median_and_leave_one_out",
        ):
            value = coarse.protocol.finite_float(point.get(field), math.nan)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"Invalid V2 point metric: {point_id}/{field}")
    return payload


def _run_manifest(plan: RefinementPlan) -> dict[str, Any]:
    return {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_excluded": list(HOLDOUT_SEEDS),
        "holdout_case_count": 0,
        "expected_case_count": plan.manifest["expected_case_count"],
        "new_case_count": plan.manifest["new_case_count"],
        "reused_case_count": plan.manifest["reused_case_count"],
    }


def _register_run(plan: RefinementPlan, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    expected = _run_manifest(plan)
    if path.is_file():
        if _read_json(path) != expected:
            raise ValueError("Output directory belongs to another V2 run")
        return
    if any(output_dir.iterdir()):
        raise ValueError("Refusing a non-empty unregistered V2 output")
    _write_json(path, expected)


@contextmanager
def _exclusive_lock(output_dir: Path):
    path = output_dir / ".multiseed_refinement_v2.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another process owns {path}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} utc={_now()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def _import_reused(
    plan: RefinementPlan,
    output_dir: Path,
    evidence: dict[str, dict[str, Any]],
) -> None:
    source = _validated_v1_source(
        Path(plan.manifest["source"]["v1_plan_dir"]),
        Path(plan.manifest["source"]["v1_run_dir"]),
    )
    for spec in plan.specs:
        if spec.evidence_mode != "reuse_v1":
            continue
        for seed in CALIBRATION_SEEDS:
            case_key = _case_key(spec.key, seed)
            if case_key in evidence:
                continue
            source_key = v1._case_key(spec.key, seed)
            wrapper = source.evidence[source_key]
            raw = wrapper["source_evidence"]
            reused_from = v1._evidence_path(source.run_dir, source_key)
            payload = _wrap_evidence(
                plan,
                spec,
                seed,
                raw,
                source_kind="reused_v1_calibration_evidence",
                source_v1_case_key=source_key,
                reused_from=str(reused_from),
            )
            _validate_evidence(payload, plan)
            path = _evidence_path(output_dir, case_key)
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite V2 evidence: {path}")
            _write_json(path, payload)
            evidence[case_key] = payload


def run(
    plan_dir: Path,
    output_dir: Path,
    *,
    workers: int = 2,
    executor: RawExecutor = coarse.execute_candidate,
) -> dict[str, Any]:
    if workers not in (1, 2):
        raise ValueError("Use one or two workers to bound memory use")
    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    _register_run(plan, output_dir)
    with _exclusive_lock(output_dir):
        evidence = _load_evidence(plan, output_dir)
        try:
            _import_reused(plan, output_dir, evidence)
            _write_progress(output_dir, plan, evidence, status="running")
            missing = [
                case
                for case in plan.manifest["cases"]
                if case["evidence_mode"] == "execute"
                and case["case_key"] not in evidence
            ]

            def execute_one(case: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
                key = str(case["candidate_key"])
                seed = int(case["seed"])
                spec = _spec(plan, key)
                adapter = _adapter(plan, spec)
                raw = executor(spec.candidate, adapter, output_dir, seed)
                coarse._validate_evidence(raw, spec.candidate, adapter, seed)
                payload = _wrap_evidence(
                    plan,
                    spec,
                    seed,
                    raw,
                    source_kind="canonical_v2_refinement_execution",
                )
                _validate_evidence(payload, plan)
                return str(case["case_key"]), payload

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(execute_one, case): case for case in missing}
                for future in as_completed(futures):
                    case_key, payload = future.result()
                    path = _evidence_path(output_dir, case_key)
                    if path.exists():
                        raise FileExistsError(
                            f"Refusing to overwrite V2 evidence: {path}"
                        )
                    _write_json(path, payload)
                    evidence[case_key] = payload
                    _write_progress(output_dir, plan, evidence, status="running")
            result = finalize(plan, output_dir, evidence)
            _write_progress(output_dir, plan, evidence, status="complete")
            return result
        except Exception as exc:
            _write_progress(
                output_dir, plan, evidence, status="interrupted", error=str(exc)
            )
            raise


def finalize_existing(plan_dir: Path, output_dir: Path) -> dict[str, Any]:
    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    _register_run(plan, output_dir)
    evidence = _load_evidence(plan, output_dir)
    result = finalize(plan, output_dir, evidence)
    _write_progress(output_dir, plan, evidence, status="complete")
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("plan", "validate", "run", "finalize"), required=True
    )
    parser.add_argument("--source-plan-dir", type=Path, default=DEFAULT_SOURCE_PLAN)
    parser.add_argument("--source-run-dir", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--op80-candidates-json", type=Path)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        low_specs = (
            load_op80_candidates(args.op80_candidates_json)
            if args.op80_candidates_json
            else OP80_REFINEMENT_WAVE
        )
        path = prepare_plan(
            args.plan_dir,
            source_plan_dir=args.source_plan_dir,
            source_run_dir=args.source_run_dir,
            op80_candidates=low_specs,
        )
        print(f"V2 refinement plan prepared; no candidate executed: {path}")
    elif args.mode == "validate":
        plan = validate_plan(args.plan_dir)
        print(
            f"Valid V2 plan: {plan.manifest['expected_case_count']} total cases, "
            f"{plan.manifest['new_case_count']} new, 0 holdout"
        )
    elif args.mode == "run":
        print(
            json.dumps(
                run(args.plan_dir, args.output_dir, workers=args.workers), indent=2
            )
        )
    else:
        print(json.dumps(finalize_existing(args.plan_dir, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
