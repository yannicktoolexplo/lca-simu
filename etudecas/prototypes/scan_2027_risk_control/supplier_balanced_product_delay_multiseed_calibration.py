#!/usr/bin/env python3
"""Calibrate robust finished-product service states on five independent seeds.

This additive protocol exists because the former one-seed operating points did
not generalise.  Seeds 340282--340286 are consequently a calibration cohort,
not validation evidence.  The untouched seeds 340287--340316 are sealed for a
single later holdout validation.

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
    supplier_balanced_product_delay_fine_prevalidation as previous,
)


SCHEMA_VERSION = "etudecas.multiseed_operating_point_calibration.v1"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selection"
POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selected_operating_points"
DESIGN_SEED = 340281
CALIBRATION_SEEDS = tuple(range(340282, 340287))
HOLDOUT_SEEDS = tuple(range(340287, 340317))
SERVICE_WINDOW = {"start_day": 0, "end_day": 719, "day_count": 720}
TARGET_TOLERANCE = 0.015
NON_SATURATION_LIMIT = 0.995
PRODUCT_GAP_WARNING_PP = 5.0
ARTIFACT_PARENT = coarse.protocol.ARTIFACT_PARENT
DEFAULT_SOURCE_PLAN = previous.DEFAULT_PLAN_OUTPUT
DEFAULT_SOURCE_RUN = previous.DEFAULT_RUN_OUTPUT
DEFAULT_PLAN_OUTPUT = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_calibration_plan_20260904_v1"
)
DEFAULT_RUN_OUTPUT = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_calibration_run_20260904_v1"
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


OP93_WAVE = (
    CandidateSpec("op93_wave_7_90", 7.0, 90.0, "op_93", "execute"),
    CandidateSpec("op93_wave_10_90", 10.0, 90.0, "op_93", "execute"),
)
OP80_HIGH_BRANCH = (
    CandidateSpec("op80_high_22_97", 22.0, 97.0, "op_80", "execute"),
    CandidateSpec("op80_high_30_96", 30.0, 96.0, "op_80", "execute"),
)
OP80_LOW_BRANCH = (
    CandidateSpec("op80_low_14_96", 14.0, 96.0, "op_80", "execute"),
    CandidateSpec("op80_low_16_95", 16.0, 95.0, "op_80", "execute"),
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
class CalibrationPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    source_plan: previous.PrevalidationPlan
    specs: tuple[CandidateSpec, ...]
    inventory: dict[str, dict[str, Any]]


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
    metrics = payload.get("metrics") or payload
    value = coarse.protocol.finite_float(metrics.get(field), math.nan)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"Invalid service metric: {field}")
    return value


def _quantity(payload: Mapping[str, Any], field: str) -> float:
    metrics = payload.get("metrics") or payload
    value = coarse.protocol.finite_float(metrics.get(field), math.nan)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"Invalid non-negative quantity: {field}")
    return value


def _validate_quantities(payload: Mapping[str, Any]) -> None:
    left_on = _quantity(payload, "on_due_qty_268091")
    left_demand = _quantity(payload, "demand_qty_268091")
    right_on = _quantity(payload, "on_due_qty_268967")
    right_demand = _quantity(payload, "demand_qty_268967")
    if left_demand <= 0.0 or right_demand <= 0.0:
        raise ValueError("Both finished products must have positive demand")
    if left_on > left_demand + 1e-7 or right_on > right_demand + 1e-7:
        raise ValueError("On-due quantity exceeds demand")
    derived = {
        "on_due_service_268091": left_on / left_demand,
        "on_due_service_268967": right_on / right_demand,
        "system_on_due_service": (left_on + right_on) / (left_demand + right_demand),
        "minimum_product_on_due_service": min(
            left_on / left_demand, right_on / right_demand
        ),
    }
    for field, expected in derived.items():
        if not math.isclose(
            _metric(payload, field), expected, rel_tol=1e-9, abs_tol=1e-12
        ):
            raise ValueError(f"Service/quantity mismatch: {field}")


def _pooled(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    if not rows:
        raise ValueError("Cannot pool an empty candidate")
    left_on = sum(_quantity(row, "on_due_qty_268091") for row in rows)
    left_demand = sum(_quantity(row, "demand_qty_268091") for row in rows)
    right_on = sum(_quantity(row, "on_due_qty_268967") for row in rows)
    right_demand = sum(_quantity(row, "demand_qty_268967") for row in rows)
    if left_demand <= 0.0 or right_demand <= 0.0:
        raise ValueError("Cannot pool zero demand")
    return {
        "system_on_due_service": (left_on + right_on) / (left_demand + right_demand),
        "on_due_service_268091": left_on / left_demand,
        "on_due_service_268967": right_on / right_demand,
        "on_due_qty_268091": left_on,
        "demand_qty_268091": left_demand,
        "on_due_qty_268967": right_on,
        "demand_qty_268967": right_demand,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty series")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _stats(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean": sum(values) / len(values),
        "median": _quantile(values, 0.5),
        "p10": _quantile(values, 0.1),
        "p90": _quantile(values, 0.9),
        "q1": _quantile(values, 0.25),
        "q3": _quantile(values, 0.75),
        "iqr": _quantile(values, 0.75) - _quantile(values, 0.25),
        "minimum": min(values),
        "maximum": max(values),
    }


def _source_evidence(
    source_plan: previous.PrevalidationPlan, source_run: Path
) -> dict[str, dict[str, Any]]:
    evidence = previous._load_evidence(source_plan, source_run)
    expected = {
        previous._case_key(point_id, seed)
        for point_id in previous.POINT_IDS
        for seed in CALIBRATION_SEEDS
    }
    if set(evidence) != expected:
        raise ValueError(f"Source calibration cohort incomplete: {len(evidence)}/15")
    return evidence


def _reused_specs(source_plan: previous.PrevalidationPlan) -> tuple[CandidateSpec, ...]:
    definitions = (
        ("op100_reference", "op_100"),
        ("op93_previous", "op_93"),
        ("op80_initial", "op_80"),
    )
    specs: list[CandidateSpec] = []
    for key, point_id in definitions:
        point = previous._point(source_plan, point_id)
        specs.append(
            CandidateSpec(
                key,
                float(point["offset_days_268091"]),
                float(point["offset_days_268967"]),
                point_id,
                "reuse",
            )
        )
    return tuple(specs)


def _branch_from_initial(
    evidence: Mapping[str, Mapping[str, Any]]
) -> tuple[str, tuple[CandidateSpec, ...], float]:
    rows = [evidence[previous._case_key("op_80", seed)] for seed in CALIBRATION_SEEDS]
    service = _pooled(rows)["system_on_due_service"]
    if service > 0.815 + 1e-12:
        return "initial_low_state_too_high", OP80_HIGH_BRANCH, service
    if service < 0.785 - 1e-12:
        return "initial_low_state_too_low", OP80_LOW_BRANCH, service
    return "initial_low_state_in_target_band", (), service


def _spec_payload(spec: CandidateSpec) -> dict[str, Any]:
    return {
        **asdict(spec),
        "candidate_id": spec.candidate.candidate_id,
    }


def _manifest_signature_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "source": manifest.get("source"),
        "source_hashes": manifest.get("source_hashes"),
        "cohorts": manifest.get("cohorts"),
        "candidates": manifest.get("candidates"),
        "inventory": manifest.get("inventory"),
        "cases": manifest.get("cases"),
        "expected_case_count": manifest.get("expected_case_count"),
        "new_case_count": manifest.get("new_case_count"),
        "reused_case_count": manifest.get("reused_case_count"),
        "adaptive_decision": manifest.get("adaptive_decision"),
        "selection_contract": manifest.get("selection_contract"),
        "holdout_contract": manifest.get("holdout_contract"),
        "execution_contract": manifest.get("execution_contract"),
    }


def prepare_plan(
    output_dir: Path,
    *,
    source_plan_dir: Path = DEFAULT_SOURCE_PLAN,
    source_run_dir: Path = DEFAULT_SOURCE_RUN,
) -> Path:
    """Freeze the multi-seed calibration plan before any new execution."""

    output_dir = output_dir.resolve()
    source_run_dir = source_run_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite calibration plan: {output_dir}")
    source_plan = previous.validate_plan(source_plan_dir)
    source_evidence = _source_evidence(source_plan, source_run_dir)
    branch, branch_specs, initial_low = _branch_from_initial(source_evidence)
    specs = _reused_specs(source_plan) + OP93_WAVE + branch_specs
    if len({spec.key for spec in specs}) != len(specs):
        raise ValueError("Duplicate candidate key")
    if len({spec.candidate.candidate_id for spec in specs}) != len(specs):
        raise ValueError("Duplicate physical candidate")
    output_dir.mkdir(parents=True)
    source_graph = coarse._read_json(source_plan.fine_plan.coarse_plan.source_graph)
    inventory: dict[str, dict[str, Any]] = {}
    for spec in specs:
        graph, changes = coarse.apply_product_delays(
            source_graph,
            source_plan.fine_plan.coarse_plan.lanes_by_product,
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
    source_paths = {
        key: previous._evidence_path(source_run_dir, key)
        for key in source_evidence
    }
    source_evidence_hashes = {
        key: _sha256(path) for key, path in source_paths.items()
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
        "design": [DESIGN_SEED],
        "calibration": list(CALIBRATION_SEEDS),
        "holdout_sealed": list(HOLDOUT_SEEDS),
    }
    if (
        set(cohorts["design"]) & set(cohorts["calibration"])
        or set(cohorts["design"]) & set(cohorts["holdout_sealed"])
        or set(cohorts["calibration"]) & set(cohorts["holdout_sealed"])
    ):
        raise ValueError("Design, calibration and holdout cohorts must be disjoint")
    manifest: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": "planned_not_executed",
        "created_at_utc": _now(),
        "interpretation": (
            "Hypotheses de fonctionnement simulees; aucune performance fournisseur "
            "historique n'est inferee."
        ),
        "source": {
            "prevalidation_plan_dir": str(source_plan.plan_dir),
            "prevalidation_plan_signature": source_plan.manifest["plan_signature"],
            "prevalidation_run_dir": str(source_run_dir),
            "prevalidation_summary_sha256": _sha256(
                source_run_dir / "prevalidation_summary.json"
            ),
            "reused_evidence_sha256": source_evidence_hashes,
            "reclassification": "calibration_after_single_seed_generalisation_failure",
        },
        "source_hashes": {
            "source_graph_sha256": _sha256(source_plan.fine_plan.coarse_plan.source_graph),
            "engine_sha256": _sha256(source_plan.fine_plan.coarse_plan.engine),
            "profile_sha256": _sha256(source_plan.fine_plan.coarse_plan.profile),
            "driver_sha256": _sha256(Path(__file__).resolve()),
            "previous_driver_sha256": _sha256(Path(previous.__file__).resolve()),
        },
        "cohorts": cohorts,
        "candidates": [_spec_payload(spec) for spec in specs],
        "inventory": inventory,
        "cases": cases,
        "expected_case_count": len(cases),
        "new_case_count": sum(case["evidence_mode"] == "execute" for case in cases),
        "reused_case_count": sum(case["evidence_mode"] == "reuse" for case in cases),
        "adaptive_decision": {
            "pre_registered_rule": (
                "If pooled (16,96) >81.5%, test (22,97)/(30,96); if <78.5%, "
                "test (14,96)/(16,95); otherwise add no low-state pair."
            ),
            "fixed_op93_wave": ["(7,90)", "(10,90)"],
            "observed_initial_low_service": initial_low,
            "selected_branch": branch,
            "scheduled_low_state_candidates": [spec.key for spec in branch_specs],
            "interpolation_used": False,
        },
        "selection_contract": {
            "measure": "ratio_of_summed_on_due_quantities_to_summed_demand",
            "service_window": SERVICE_WINDOW,
            "op100_minimum_global_and_each_product": 0.985,
            "op93_global_band": [0.915, 0.945],
            "op80_global_band": [0.785, 0.815],
            "degraded_product_strictly_below": NON_SATURATION_LIMIT,
            "product_gap_warning_pp": PRODUCT_GAP_WARNING_PP,
            "product_gap_is_rejection_criterion": False,
            "global_order": "op_100 > op_93 > op_80",
            "pooled_order_required_for": [
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            ],
            "per_seed_strict_order_required": 4,
            "per_seed_strict_order_required_for": [
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            ],
            "global_median_must_also_be_in_target_band": True,
            "tie_break": [
                "minimum_maximum_global_target_error",
                "minimum_sum_global_target_error",
                "minimum_demand_weighted_offset_sum",
                "lexicographic_candidate_ids",
            ],
            "candidate_must_be_jointly_executed_on_all_five_seeds": True,
            "no_interpolation": True,
            "no_holdout_retuning": True,
        },
        "holdout_contract": {
            "status_only_if_passed": "holdout_validated_30_seed",
            "fixed_point_count": 3,
            "seed_count": len(HOLDOUT_SEEDS),
            "baseline_case_count": 3 * len(HOLDOUT_SEEDS),
            "seeds": list(HOLDOUT_SEEDS),
            "service_window": SERVICE_WINDOW,
            "op100_minimum_global_and_each_product": 0.985,
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
            "failure_rule": (
                "No strict supplier-incident campaign and no op93/op80 target label; "
                "publish only the states actually obtained."
            ),
        },
        "execution_contract": {
            "scenario": "scn:BASE",
            "common_random_numbers": True,
            "calibration_seed_count": len(CALIBRATION_SEEDS),
            "quality_incident": False,
            "supplier_availability_incident": False,
            "capacity_override": False,
            "acute_incident": False,
            "state_dependent_risk": False,
            "changed_dimension": "planned_supplier_lead_time_days_only",
            "maximum_workers": 2,
            "fallback_if_no_selection": (
                "Freeze a new axial-search plan; every proposed joint pair must then "
                "be executed on all five calibration seeds before selection."
            ),
        },
    }
    manifest["plan_signature"] = _stable_sha256(_manifest_signature_payload(manifest))
    _write_json(output_dir / "calibration_plan.json", manifest)
    _write_csv(
        output_dir / "case_ledger.csv",
        cases,
        ("case_key", "candidate_key", "seed", "evidence_mode"),
    )
    return output_dir


def validate_plan(plan_dir: Path) -> CalibrationPlan:
    plan_dir = plan_dir.resolve()
    manifest_path = plan_dir / "calibration_plan.json"
    ledger_path = plan_dir / "case_ledger.csv"
    if not manifest_path.is_file() or not ledger_path.is_file():
        raise FileNotFoundError(f"Incomplete multi-seed calibration plan: {plan_dir}")
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
            "design": [DESIGN_SEED],
            "calibration": list(CALIBRATION_SEEDS),
            "holdout_sealed": list(HOLDOUT_SEEDS),
        }
    ):
        raise ValueError("Multi-seed calibration plan/signature mismatch")
    source = manifest["source"]
    source_plan = previous.validate_plan(Path(source["prevalidation_plan_dir"]))
    source_run = Path(source["prevalidation_run_dir"]).resolve()
    evidence = _source_evidence(source_plan, source_run)
    branch, branch_specs, initial_low = _branch_from_initial(evidence)
    expected_specs = _reused_specs(source_plan) + OP93_WAVE + branch_specs
    if (
        source_plan.manifest["plan_signature"]
        != source["prevalidation_plan_signature"]
        or _sha256(source_run / "prevalidation_summary.json")
        != source["prevalidation_summary_sha256"]
        or {
            key: _sha256(previous._evidence_path(source_run, key)) for key in evidence
        }
        != source["reused_evidence_sha256"]
    ):
        raise ValueError("Reused calibration evidence changed")
    expected_hashes = {
        "source_graph_sha256": _sha256(source_plan.fine_plan.coarse_plan.source_graph),
        "engine_sha256": _sha256(source_plan.fine_plan.coarse_plan.engine),
        "profile_sha256": _sha256(source_plan.fine_plan.coarse_plan.profile),
        "driver_sha256": _sha256(Path(__file__).resolve()),
        "previous_driver_sha256": _sha256(Path(previous.__file__).resolve()),
    }
    if manifest.get("source_hashes") != expected_hashes:
        raise ValueError("Calibration source hashes changed")
    specs = tuple(
        CandidateSpec(
            key=str(row["key"]),
            offset_days_268091=float(row["offset_days_268091"]),
            offset_days_268967=float(row["offset_days_268967"]),
            target_group=str(row["target_group"]),
            evidence_mode=str(row["evidence_mode"]),
        )
        for row in manifest["candidates"]
    )
    if [_spec_payload(spec) for spec in specs] != manifest["candidates"]:
        raise ValueError("Candidate catalogue is not canonical")
    expected_cases = len(expected_specs) * len(CALIBRATION_SEEDS)
    expected_new = sum(
        spec.evidence_mode == "execute" for spec in expected_specs
    ) * len(CALIBRATION_SEEDS)
    if (
        specs != expected_specs
        or manifest.get("adaptive_decision", {}).get("selected_branch") != branch
        or manifest.get("adaptive_decision", {}).get(
            "scheduled_low_state_candidates"
        )
        != [spec.key for spec in branch_specs]
        or not math.isclose(
            float(
                manifest.get("adaptive_decision", {}).get(
                    "observed_initial_low_service", math.nan
                )
            ),
            initial_low,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or manifest.get("expected_case_count") != expected_cases
        or manifest.get("new_case_count") != expected_new
        or manifest.get("reused_case_count") != expected_cases - expected_new
    ):
        raise ValueError("Adaptive branch or case counts do not match source evidence")
    inventory = dict(manifest["inventory"])
    source_graph = coarse._read_json(source_plan.fine_plan.coarse_plan.source_graph)
    for spec in specs:
        item = inventory.get(spec.key) or {}
        graph_path = plan_dir / str(item.get("graph_path") or "")
        ledger_path = plan_dir / str(item.get("change_ledger_path") or "")
        expected_graph, _ = coarse.apply_product_delays(
            source_graph,
            source_plan.fine_plan.coarse_plan.lanes_by_product,
            offset_days_268091=spec.offset_days_268091,
            offset_days_268967=spec.offset_days_268967,
        )
        if (
            not graph_path.is_file()
            or not ledger_path.is_file()
            or coarse._read_json(graph_path) != expected_graph
            or _sha256(graph_path) != item.get("graph_sha256")
            or _sha256(ledger_path) != item.get("change_ledger_sha256")
        ):
            raise ValueError(f"Candidate input changed: {spec.key}")
    with (plan_dir / "case_ledger.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        actual_cases = list(csv.DictReader(stream))
    expected_cases = [
        {key: str(value) for key, value in row.items()} for row in manifest["cases"]
    ]
    if actual_cases != expected_cases:
        raise ValueError("Calibration case ledger changed")
    return CalibrationPlan(plan_dir, manifest, source_plan, specs, inventory)


def _spec(plan: CalibrationPlan, key: str) -> CandidateSpec:
    matches = [spec for spec in plan.specs if spec.key == key]
    if len(matches) != 1:
        raise ValueError(f"Unknown calibration candidate: {key}")
    return matches[0]


def _adapter(plan: CalibrationPlan, spec: CandidateSpec) -> coarse.ValidatedPlan:
    candidate = spec.candidate
    item = plan.inventory[spec.key]
    return coarse.ValidatedPlan(
        plan_dir=plan.plan_dir,
        manifest={
            "plan_signature": plan.manifest["plan_signature"],
            "targets": [0.93, 0.80],
            "target_tolerance": TARGET_TOLERANCE,
        },
        candidates=(candidate,),
        inventory={
            candidate.candidate_id: {
                **asdict(candidate),
                "graph_path": item["graph_path"],
                "graph_sha256": item["graph_sha256"],
            }
        },
        lanes_by_product=plan.source_plan.fine_plan.coarse_plan.lanes_by_product,
        source_graph=plan.source_plan.fine_plan.coarse_plan.source_graph,
        engine=plan.source_plan.fine_plan.coarse_plan.engine,
        profile=plan.source_plan.fine_plan.coarse_plan.profile,
    )


def _wrap_evidence(
    plan: CalibrationPlan,
    spec: CandidateSpec,
    seed: int,
    source: Mapping[str, Any],
    *,
    source_kind: str,
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
    payload: Mapping[str, Any], plan: CalibrationPlan
) -> tuple[str, int]:
    unsigned = dict(payload)
    signature = str(unsigned.pop("evidence_signature", ""))
    key = str(payload.get("candidate_key") or "")
    seed = int(payload.get("seed") or -1)
    spec = _spec(plan, key)
    candidate = spec.candidate
    source = payload.get("source_evidence") or {}
    adapter = _adapter(plan, spec)
    if (
        payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or signature != _stable_sha256(unsigned)
        or payload.get("case_key") != _case_key(key, seed)
        or seed not in CALIBRATION_SEEDS
        or payload.get("candidate_id") != candidate.candidate_id
        or float(payload.get("offset_days_268091")) != spec.offset_days_268091
        or float(payload.get("offset_days_268967")) != spec.offset_days_268967
        or payload.get("target_group") != spec.target_group
        or payload.get("evidence_mode") != spec.evidence_mode
        or payload.get("valid") is not True
        or payload.get("source_kind")
        not in {"reused_prevalidation_evidence", "canonical_five_seed_execution"}
    ):
        raise ValueError(f"Calibration evidence contract mismatch: {key}/{seed}")
    coarse._validate_evidence(source, candidate, adapter, seed)
    if (
        payload.get("metrics") != source.get("metrics")
        or payload.get("graph_sha256") != plan.inventory[key]["graph_sha256"]
        or payload.get("engine_sha256") != plan.manifest["source_hashes"]["engine_sha256"]
    ):
        raise ValueError(f"Calibration/source evidence mismatch: {key}/{seed}")
    _validate_quantities(payload)
    return key, seed


def _load_evidence(
    plan: CalibrationPlan, output_dir: Path
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((output_dir / "evidence").glob("*.json")):
        payload = _read_json(path)
        key, seed = _validate_evidence(payload, plan)
        case_key = _case_key(key, seed)
        if case_key in found or path != _evidence_path(output_dir, case_key):
            raise ValueError(f"Duplicate or misnamed evidence: {case_key}")
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
    plan: CalibrationPlan,
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
            "error": error,
            "updated_at_utc": _now(),
        },
    )


def _candidate_summary(
    spec: CandidateSpec, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    pooled = _pooled(rows)
    service_fields = (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
        "minimum_product_on_due_service",
    )
    target = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}[spec.target_group]
    reasons: list[str] = []
    if spec.target_group == "op_100":
        if any(
            pooled[field] < 0.985 - 1e-12
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            )
        ):
            reasons.append("reference_below_98p5pct")
    else:
        lower, upper = (
            (0.915, 0.945) if spec.target_group == "op_93" else (0.785, 0.815)
        )
        if not lower - 1e-12 <= pooled["system_on_due_service"] <= upper + 1e-12:
            reasons.append("global_service_outside_target_band")
        global_median = _quantile(
            [_metric(row, "system_on_due_service") for row in rows], 0.5
        )
        if not lower - 1e-12 <= global_median <= upper + 1e-12:
            reasons.append("median_global_service_outside_target_band")
        if any(
            pooled[field] >= NON_SATURATION_LIMIT - 1e-12
            for field in ("on_due_service_268091", "on_due_service_268967")
        ):
            reasons.append("degraded_product_saturated")
    gap_pp = 100.0 * abs(
        pooled["on_due_service_268091"] - pooled["on_due_service_268967"]
    )
    return {
        **_spec_payload(spec),
        "target_service": target,
        "replication_count": len(rows),
        "pooled_ratio_of_sums": pooled,
        "individual_seed_metrics": {
            field: _stats([_metric(row, field) for row in rows])
            for field in service_fields
        },
        "service_by_seed": {
            field: {
                str(int(row["seed"])): _metric(row, field) for row in rows
            }
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            )
        },
        "product_service_gap_pp": gap_pp,
        "product_gap_warning": gap_pp > PRODUCT_GAP_WARNING_PP + 1e-12,
        "admissible_individually": not reasons,
        "exclusion_reasons": reasons,
    }


def _select(
    plan: CalibrationPlan, evidence: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    summaries = {
        spec.key: _candidate_summary(
            spec,
            [evidence[_case_key(spec.key, seed)] for seed in CALIBRATION_SEEDS],
        )
        for spec in plan.specs
    }
    reference = summaries["op100_reference"]
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
    eligible_pairs: list[dict[str, Any]] = []
    if reference["admissible_individually"]:
        for high in candidates_93:
            for low in candidates_80:
                monotone_offsets = (
                    low["offset_days_268091"] >= high["offset_days_268091"]
                    and low["offset_days_268967"] >= high["offset_days_268967"]
                )
                order_fields = (
                    "system_on_due_service",
                    "on_due_service_268091",
                    "on_due_service_268967",
                )
                pooled_order = {
                    field: (
                        reference["pooled_ratio_of_sums"][field]
                        > high["pooled_ratio_of_sums"][field]
                        > low["pooled_ratio_of_sums"][field]
                    )
                    for field in order_fields
                }
                seed_order_count = {
                    field: sum(
                        reference["service_by_seed"][field][str(seed)]
                        > high["service_by_seed"][field][str(seed)]
                        > low["service_by_seed"][field][str(seed)]
                        for seed in CALIBRATION_SEEDS
                    )
                    for field in order_fields
                }
                joint_seed_order_count = sum(
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
                    or joint_seed_order_count < 4
                ):
                    continue
                high_error = abs(
                    high["pooled_ratio_of_sums"]["system_on_due_service"] - 0.93
                )
                low_error = abs(
                    low["pooled_ratio_of_sums"]["system_on_due_service"] - 0.80
                )
                demands = high["pooled_ratio_of_sums"]
                weighted_offset = (
                    (high["offset_days_268091"] + low["offset_days_268091"])
                    * demands["demand_qty_268091"]
                    + (high["offset_days_268967"] + low["offset_days_268967"])
                    * demands["demand_qty_268967"]
                )
                score = (
                    max(high_error, low_error),
                    high_error + low_error,
                    weighted_offset,
                    str(high["candidate_id"]),
                    str(low["candidate_id"]),
                )
                eligible_pairs.append(
                    {
                        "op93_candidate_key": high["key"],
                        "op80_candidate_key": low["key"],
                        "pooled_strict_order": pooled_order,
                        "per_seed_strict_order_count": seed_order_count,
                        "same_seed_joint_strict_order_count": joint_seed_order_count,
                        "selection_score": list(score),
                    }
                )
    eligible_pairs.sort(key=lambda row: tuple(row["selection_score"]))
    chosen = eligible_pairs[0] if eligible_pairs else None
    selection: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "calibration_selected" if chosen else "target_not_attained",
        "plan_signature": plan.manifest["plan_signature"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_sealed_and_unread": list(HOLDOUT_SEEDS),
        "candidate_summaries": list(summaries.values()),
        "eligible_pairs": eligible_pairs,
        "selected_pair": chosen,
        "selection_contract": plan.manifest["selection_contract"],
        "fallback_required": chosen is None,
        "fallback_rule": plan.manifest["execution_contract"][
            "fallback_if_no_selection"
        ],
    }
    selection["selection_signature"] = _stable_sha256(selection)
    if chosen is None:
        return selection, None
    selected = {
        "schema_version": POINTS_SCHEMA_VERSION,
        "status": "selected_on_five_seed_calibration_pending_holdout",
        "plan": {
            "path": str(plan.plan_dir),
            "plan_signature": plan.manifest["plan_signature"],
        },
        "selection_signature": selection["selection_signature"],
        "source_hashes": plan.manifest["source_hashes"],
        "service_evaluation_window": SERVICE_WINDOW,
        "cohorts": plan.manifest["cohorts"],
        "simulation_hypotheses_not_observed_performance": True,
        "holdout_validated": False,
        "operating_points": [],
    }
    selected_keys = {
        "op_100": "op100_reference",
        "op_93": chosen["op93_candidate_key"],
        "op_80": chosen["op80_candidate_key"],
    }
    labels = {
        "op_100": "Fonctionnement de référence simulé",
        "op_93": "Fonctionnement intermédiaire simulé (cible globale 93 %)",
        "op_80": "Fonctionnement dégradé simulé (cible globale 80 %)",
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
                "calibration_product_268091_service": summary[
                    "pooled_ratio_of_sums"
                ]["on_due_service_268091"],
                "calibration_product_268967_service": summary[
                    "pooled_ratio_of_sums"
                ]["on_due_service_268967"],
                "candidate_key": candidate_key,
                "candidate_id": spec.candidate.candidate_id,
                "offset_days_268091": spec.offset_days_268091,
                "offset_days_268967": spec.offset_days_268967,
                "graph": str(
                    (plan.plan_dir / plan.inventory[candidate_key]["graph_path"]).resolve()
                ),
                "graph_sha256": plan.inventory[candidate_key]["graph_sha256"],
            }
        )
    selected["artifact_signature"] = _stable_sha256(selected)
    return selection, selected


def finalize(
    plan: CalibrationPlan,
    output_dir: Path,
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected = {str(case["case_key"]) for case in plan.manifest["cases"]}
    if set(evidence) != expected:
        raise ValueError(f"Calibration incomplete: {len(evidence)}/{len(expected)}")
    selection, selected = _select(plan, evidence)
    _write_json(output_dir / "selection.json", selection)
    destination = output_dir / "selected_operating_points.json"
    if selected is not None:
        _write_json(destination, selected)
    elif destination.exists():
        raise RuntimeError("Refusing stale selected operating points after failed selection")
    return {"selection": selection, "selected_operating_points": selected}


def _register_run(plan: CalibrationPlan, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    expected = {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_excluded": list(HOLDOUT_SEEDS),
        "expected_case_count": plan.manifest["expected_case_count"],
        "new_case_count": plan.manifest["new_case_count"],
        "reused_case_count": plan.manifest["reused_case_count"],
    }
    if path.is_file():
        if _read_json(path) != expected:
            raise ValueError("Output directory belongs to another calibration run")
        return
    if any(output_dir.iterdir()):
        raise ValueError("Refusing a non-empty unregistered calibration output")
    _write_json(path, expected)


@contextmanager
def _exclusive_lock(output_dir: Path):
    path = output_dir / ".multiseed_calibration.lock"
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
    plan: CalibrationPlan,
    output_dir: Path,
    evidence: dict[str, dict[str, Any]],
) -> None:
    source_run = Path(plan.manifest["source"]["prevalidation_run_dir"])
    source = _source_evidence(plan.source_plan, source_run)
    source_point = {
        "op100_reference": "op_100",
        "op93_previous": "op_93",
        "op80_initial": "op_80",
    }
    for spec in plan.specs:
        if spec.evidence_mode != "reuse":
            continue
        point_id = source_point[spec.key]
        for seed in CALIBRATION_SEEDS:
            case_key = _case_key(spec.key, seed)
            if case_key in evidence:
                continue
            source_key = previous._case_key(point_id, seed)
            wrapper = source[source_key]
            raw = wrapper["source_evidence"]
            payload = _wrap_evidence(
                plan,
                spec,
                seed,
                raw,
                source_kind="reused_prevalidation_evidence",
                reused_from=str(previous._evidence_path(source_run, source_key)),
            )
            _validate_evidence(payload, plan)
            path = _evidence_path(output_dir, case_key)
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite evidence: {path}")
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
                source = executor(spec.candidate, adapter, output_dir, seed)
                coarse._validate_evidence(source, spec.candidate, adapter, seed)
                payload = _wrap_evidence(
                    plan,
                    spec,
                    seed,
                    source,
                    source_kind="canonical_five_seed_execution",
                )
                _validate_evidence(payload, plan)
                return str(case["case_key"]), payload

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(execute_one, case): case for case in missing}
                for future in as_completed(futures):
                    case_key, payload = future.result()
                    path = _evidence_path(output_dir, case_key)
                    if path.exists():
                        raise FileExistsError(f"Refusing to overwrite evidence: {path}")
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
    parser.add_argument("--mode", choices=("plan", "validate", "run", "finalize"), required=True)
    parser.add_argument("--source-plan-dir", type=Path, default=DEFAULT_SOURCE_PLAN)
    parser.add_argument("--source-run-dir", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        path = prepare_plan(
            args.plan_dir,
            source_plan_dir=args.source_plan_dir,
            source_run_dir=args.source_run_dir,
        )
        print(f"Multi-seed calibration plan prepared; no new run executed: {path}")
    elif args.mode == "validate":
        plan = validate_plan(args.plan_dir)
        print(
            f"Valid plan: {plan.manifest['expected_case_count']} total cases, "
            f"{plan.manifest['new_case_count']} new"
        )
    elif args.mode == "run":
        print(json.dumps(run(args.plan_dir, args.output_dir, workers=args.workers), indent=2))
    else:
        print(json.dumps(finalize_existing(args.plan_dir, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
