#!/usr/bin/env python3
"""Adaptive fine calibration of the two product-specific supplier delays.

This module is additive.  It never changes the coarse Cartesian plan or its
active result directory.  It reuses the coarse module's graph transformation,
engine command and signed case evidence, but schedules only explicit pairs:

* PF 268091 at 93% is anchored at +7 days;
* PF 268091 at 80% is searched by explicit integer probes because the coarse
  response is demonstrably non-monotone (+22 days performed better than +14);
* PF 268967 at 93% starts with the explicit wave {50, 55, 58} days;
* PF 268967 at 80% starts with {95, 100, 105} days, then inspects the
  observed 95--100 day transition at integer resolution.

The axes are diagnostic searches.  The final 93% and 80% labels apply to the
global, demand-weighted finished-product service, not to each product
separately.  The selected pairs are executed together and accepted only when
the observed global service is within +/-1.5 percentage points of its target
and neither degraded product remains saturated at 100%.  The product gap is
published, with five points used as a descriptive warning rather than an
arbitrary rejection threshold.  No interpolation is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)


SCHEMA_VERSION = "etudecas.supplier_balanced_product_delay_fine_calibration.v1"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
PROGRESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.progress"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selection"
CAMPAIGN_POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.campaign_operating_points"

DEFAULT_COARSE_PLAN = coarse.DEFAULT_PLAN_OUTPUT
DEFAULT_COARSE_RUN = (
    coarse.protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_calibration_run_20260904_v1"
)
DEFAULT_PLAN_OUTPUT = (
    coarse.protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_fine_plan_20260904_v1"
)
DEFAULT_RUN_OUTPUT = (
    coarse.protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_fine_run_20260904_v1"
)
DEFAULT_SEED = coarse.DEFAULT_SEED
TARGET_TOLERANCE = 0.015
PRODUCT_BALANCE_LIMIT = 0.05
SERVICE_EVALUATION_WINDOW = {"start_day": 0, "end_day": 719, "day_count": 720}
PRODUCT_METRIC = {
    "268091": "on_due_service_268091",
    "268967": "on_due_service_268967",
}
RESULT_FIELDS = (
    "candidate_id",
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
    "graph_sha256",
    "source_kind",
    "evidence_signature",
    "valid",
)


@dataclass(frozen=True)
class AxisSpec:
    search_id: str
    product_id: str
    target_service: float
    mode: str
    lower_offset_days: float
    upper_offset_days: float
    initial_offset_days: float
    tolerance: float = TARGET_TOLERANCE

    @property
    def metric(self) -> str:
        return PRODUCT_METRIC[self.product_id]


AXES = (
    AxisSpec(
        search_id="pf268091_target_93",
        product_id="268091",
        target_service=0.93,
        mode="fixed_verified_anchor",
        lower_offset_days=7.0,
        upper_offset_days=7.0,
        initial_offset_days=7.0,
    ),
    AxisSpec(
        search_id="pf268091_target_80",
        product_id="268091",
        target_service=0.80,
        mode="explicit_nonmonotone_local_search",
        lower_offset_days=10.0,
        upper_offset_days=30.0,
        initial_offset_days=15.0,
    ),
    AxisSpec(
        search_id="pf268967_target_93",
        product_id="268967",
        target_service=0.93,
        mode="explicit_wave_then_integer_neighbors",
        lower_offset_days=45.0,
        upper_offset_days=60.0,
        initial_offset_days=50.0,
    ),
    AxisSpec(
        search_id="pf268967_target_80",
        product_id="268967",
        target_service=0.80,
        mode="explicit_wave_then_integer_neighbors",
        lower_offset_days=90.0,
        upper_offset_days=120.0,
        initial_offset_days=105.0,
    ),
)


PF268091_80_COARSE_SUPPORT = (10.0, 14.0, 22.0, 30.0)
PF268091_80_WAVE = (15.0, 16.0, 13.0, 12.0)
PF268091_80_COMPLETION = (11.0, 17.0, 18.0, 19.0, 20.0, 21.0)
PF268091_80_ADJACENT = tuple(float(value) for value in range(23, 30))
PF268967_WAVES = {
    "pf268967_target_93": (50.0, 55.0, 58.0),
    "pf268967_target_80": (105.0, 95.0, 100.0, 110.0, 115.0),
}
PF268967_80_OBSERVED_TRANSITION = (105.0, 95.0, 100.0, 96.0, 97.0, 98.0, 99.0)
TERMINAL_AXIS_STATUSES = {
    "within_tolerance",
    "target_not_attained_after_local_search",
}
ADAPTIVE_ALGORITHM_REVISION = "observed_pf268967_transition_95_100_integer_v2"
PROTOCOL_AMENDMENT = {
    "reason": (
        "Observed PF268967 service stayed near 87% at +95 days and fell below "
        "47% at +100 days; +110/+115 could not locate the target."
    ),
    "replacement_search": "integer offsets 96, 97, 98 and 99 days",
    "abandoned_uninformative_offsets_days": [110.0, 115.0],
    "interpolation_used": False,
}


@dataclass(frozen=True)
class ValidatedFinePlan:
    plan_dir: Path
    manifest: dict[str, Any]
    coarse_plan: coarse.ValidatedPlan
    coarse_run_dir: Path | None


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


def _candidate(left: float, right: float) -> coarse.Candidate:
    return coarse.Candidate(
        candidate_id=coarse._candidate_id(float(left), float(right)),
        offset_days_268091=float(left),
        offset_days_268967=float(right),
    )


def _axis_candidate(axis: AxisSpec, offset: float) -> coarse.Candidate:
    if axis.product_id == "268091":
        return _candidate(offset, 0.0)
    return _candidate(0.0, offset)


def _axis_candidate_universe(axis: AxisSpec) -> tuple[float, ...]:
    if axis.mode == "fixed_verified_anchor":
        return (axis.initial_offset_days,)
    return tuple(
        float(value)
        for value in range(
            int(axis.lower_offset_days), int(axis.upper_offset_days) + 1
        )
    )


def explicit_candidate_pairs() -> tuple[dict[str, Any], ...]:
    """Return every permitted one-axis probe; never a Cartesian product.

    The two final joint candidates are materialised only after one observed
    offset has been selected for both product axes.
    """

    roles_by_id: dict[str, list[str]] = {}
    candidates_by_id: dict[str, coarse.Candidate] = {}

    def register(candidate: coarse.Candidate, role: str) -> None:
        candidates_by_id[candidate.candidate_id] = candidate
        roles_by_id.setdefault(candidate.candidate_id, []).append(role)

    register(_candidate(0.0, 0.0), "op_100_baseline")
    for axis in AXES:
        for offset in _axis_candidate_universe(axis):
            if axis.mode == "fixed_verified_anchor":
                role = "fixed_anchor"
            elif axis.search_id == "pf268091_target_80":
                if offset in PF268091_80_WAVE:
                    role = "conditional_first_wave"
                elif offset in PF268091_80_COARSE_SUPPORT:
                    role = "coarse_support_read_or_reexecute"
                elif offset in PF268091_80_COMPLETION:
                    role = "integer_completion_if_needed"
                else:
                    role = "adjacent_interval_if_triggered"
            elif offset in PF268967_WAVES[axis.search_id]:
                role = "first_wave"
            else:
                role = "integer_neighbor_if_needed"
            register(_axis_candidate(axis, offset), f"{axis.search_id}:{role}")
    return tuple(
        {
            **asdict(candidate),
            "roles": roles_by_id[candidate.candidate_id],
        }
        for candidate in candidates_by_id.values()
    )


# Compatibility alias for the first unreleased draft of this additive module.
# The values form a permitted universe and are not executed eagerly.
explicit_initial_pairs = explicit_candidate_pairs


def _plan_signature_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "coarse_source": manifest.get("coarse_source"),
        "source_hashes": manifest.get("source_hashes"),
        "axes": manifest.get("axes"),
        "explicit_candidate_pairs": manifest.get("explicit_candidate_pairs"),
        "execution_contract": manifest.get("execution_contract"),
    }


def prepare_plan(
    output_dir: Path,
    *,
    coarse_plan_dir: Path = DEFAULT_COARSE_PLAN,
    coarse_run_dir: Path | None = DEFAULT_COARSE_RUN,
) -> Path:
    """Write the immutable fine-search plan without running a simulation."""

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing fine plan: {output_dir}")
    source_plan = coarse.validate_plan(coarse_plan_dir)
    coarse_manifest_path = source_plan.plan_dir / "calibration_plan.json"
    resolved_coarse_run = coarse_run_dir.resolve() if coarse_run_dir else None
    run_manifest_path = (
        resolved_coarse_run / "run_manifest.json" if resolved_coarse_run else None
    )
    if resolved_coarse_run is not None and resolved_coarse_run.exists():
        if run_manifest_path is None or not run_manifest_path.is_file():
            raise ValueError("Registered coarse run directory lacks run_manifest.json")
        run_manifest = _read_json(run_manifest_path)
        if (
            run_manifest.get("plan_signature")
            != source_plan.manifest["plan_signature"]
            or int(run_manifest.get("seed") or -1) != DEFAULT_SEED
        ):
            raise ValueError("Coarse run does not belong to the declared coarse plan/seed")

    candidate_pairs = explicit_candidate_pairs()
    manifest: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": "planned_not_executed",
        "created_at_utc": _now(),
        "interpretation": (
            "Fine one-seed structural calibration hypotheses; not observed supplier performance."
        ),
        "coarse_source": {
            "plan_dir": str(source_plan.plan_dir),
            "plan_signature": source_plan.manifest["plan_signature"],
            "plan_manifest_sha256": _sha256(coarse_manifest_path),
            "run_dir_read_only": str(resolved_coarse_run) if resolved_coarse_run else "",
            "run_manifest_sha256": (
                _sha256(run_manifest_path)
                if run_manifest_path is not None and run_manifest_path.is_file()
                else ""
            ),
        },
        "source_hashes": {
            "active_lanes_sha256": source_plan.manifest["source_hashes"][
                "active_lanes_sha256"
            ],
            "graph_sha256": _sha256(source_plan.source_graph),
            "engine_sha256": _sha256(source_plan.engine),
            "profile_sha256": _sha256(source_plan.profile),
        },
        "axes": [asdict(axis) for axis in AXES],
        "explicit_candidate_pairs": list(candidate_pairs),
        "explicit_candidate_pair_count": len(candidate_pairs),
        "execution_contract": {
            "seed": DEFAULT_SEED,
            "common_random_numbers": True,
            "adaptive_method": "explicit_observed_local_search_no_interpolation",
            "candidate_design": "explicit_pairs_only_not_cartesian",
            "joint_pair_verification_required": True,
            "stop_only_on_observed_service_within_tolerance": True,
            "local_adaptive_search_not_global_proof": True,
            "interpolation_used": False,
            "service_evaluation_window": SERVICE_EVALUATION_WINDOW,
            "quality_incident": False,
            "supplier_availability_incident": False,
            "capacity_override": False,
            "state_dependent_risk": False,
            "coarse_run_mutated": False,
        },
    }
    manifest["plan_signature"] = _stable_sha256(_plan_signature_payload(manifest))
    output_dir.mkdir(parents=True)
    _write_json(output_dir / "fine_calibration_plan.json", manifest)
    _write_csv(
        output_dir / "explicit_candidate_pairs.csv",
        [
            {
                **row,
                "roles": "|".join(str(role) for role in row["roles"]),
            }
            for row in candidate_pairs
        ],
        (
            "candidate_id",
            "offset_days_268091",
            "offset_days_268967",
            "roles",
        ),
    )
    return output_dir


def validate_plan(plan_dir: Path) -> ValidatedFinePlan:
    plan_dir = plan_dir.resolve()
    manifest_path = plan_dir / "fine_calibration_plan.json"
    pairs_path = plan_dir / "explicit_candidate_pairs.csv"
    if not manifest_path.is_file() or not pairs_path.is_file():
        raise FileNotFoundError(f"Incomplete fine calibration plan: {plan_dir}")
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "planned_not_executed"
        or manifest.get("plan_signature")
        != _stable_sha256(_plan_signature_payload(manifest))
        or manifest.get("axes") != [asdict(axis) for axis in AXES]
        or manifest.get("explicit_candidate_pairs")
        != list(explicit_candidate_pairs())
        or manifest.get("execution_contract", {}).get("candidate_design")
        != "explicit_pairs_only_not_cartesian"
    ):
        raise ValueError("Fine calibration plan/signature mismatch")
    source = manifest.get("coarse_source") or {}
    coarse_plan_dir = Path(str(source.get("plan_dir") or "")).resolve()
    source_plan = coarse.validate_plan(coarse_plan_dir)
    if (
        source.get("plan_signature") != source_plan.manifest["plan_signature"]
        or source.get("plan_manifest_sha256")
        != _sha256(source_plan.plan_dir / "calibration_plan.json")
    ):
        raise ValueError("Fine plan no longer matches its coarse source plan")
    expected_hashes = {
        "active_lanes_sha256": source_plan.manifest["source_hashes"][
            "active_lanes_sha256"
        ],
        "graph_sha256": _sha256(source_plan.source_graph),
        "engine_sha256": _sha256(source_plan.engine),
        "profile_sha256": _sha256(source_plan.profile),
    }
    if manifest.get("source_hashes") != expected_hashes:
        raise ValueError("Fine calibration source hashes changed")
    coarse_run_text = str(source.get("run_dir_read_only") or "")
    coarse_run_dir = Path(coarse_run_text).resolve() if coarse_run_text else None
    if coarse_run_dir is not None and coarse_run_dir.exists():
        run_manifest = coarse_run_dir / "run_manifest.json"
        if (
            not run_manifest.is_file()
            or _sha256(run_manifest) != source.get("run_manifest_sha256")
        ):
            raise ValueError("Coarse run manifest changed after fine planning")
    with pairs_path.open("r", encoding="utf-8-sig", newline="") as stream:
        actual_pairs = list(csv.DictReader(stream))
    expected_pairs = [
        {
            "candidate_id": str(row["candidate_id"]),
            "offset_days_268091": str(float(row["offset_days_268091"])),
            "offset_days_268967": str(float(row["offset_days_268967"])),
            "roles": "|".join(str(role) for role in row["roles"]),
        }
        for row in explicit_candidate_pairs()
    ]
    if actual_pairs != expected_pairs:
        raise ValueError("Explicit fine candidate-pair ledger differs from its plan")
    return ValidatedFinePlan(
        plan_dir=plan_dir,
        manifest=manifest,
        coarse_plan=source_plan,
        coarse_run_dir=coarse_run_dir,
    )


def _metric(row: Mapping[str, Any], field: str) -> float:
    metrics = row.get("metrics") or row
    value = coarse.protocol.finite_float(metrics.get(field), math.nan)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"Invalid service metric {field!r}")
    return value


def _quantity(row: Mapping[str, Any], field: str) -> float:
    metrics = row.get("metrics") or row
    value = coarse.protocol.finite_float(metrics.get(field), math.nan)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"Invalid non-negative quantity metric {field!r}")
    return value


def _validate_service_quantities(row: Mapping[str, Any]) -> None:
    left_on_due = _quantity(row, "on_due_qty_268091")
    left_demand = _quantity(row, "demand_qty_268091")
    right_on_due = _quantity(row, "on_due_qty_268967")
    right_demand = _quantity(row, "demand_qty_268967")
    if left_demand <= 0.0 or right_demand <= 0.0:
        raise ValueError("Finished-product demand must be strictly positive")
    if (
        left_on_due > left_demand + max(1e-9, 1e-10 * left_demand)
        or right_on_due > right_demand + max(1e-9, 1e-10 * right_demand)
    ):
        raise ValueError("On-due quantity cannot exceed finished-product demand")
    left = left_on_due / left_demand
    right = right_on_due / right_demand
    global_service = (left_on_due + right_on_due) / (left_demand + right_demand)
    checks = (
        ("on_due_service_268091", left),
        ("on_due_service_268967", right),
        ("system_on_due_service", global_service),
        ("minimum_product_on_due_service", min(left, right)),
    )
    for field, derived in checks:
        if not math.isclose(
            _metric(row, field), derived, rel_tol=1e-9, abs_tol=1e-12
        ):
            raise ValueError(f"Service metric is inconsistent with quantities: {field}")


def _axis_offset(axis: AxisSpec, candidate: coarse.Candidate) -> float | None:
    if axis.product_id == "268091":
        if not math.isclose(candidate.offset_days_268967, 0.0, abs_tol=1e-12):
            return None
        return candidate.offset_days_268091
    if not math.isclose(candidate.offset_days_268091, 0.0, abs_tol=1e-12):
        return None
    return candidate.offset_days_268967


def decide_axis(
    axis: AxisSpec, evidence_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Replay one deterministic, observation-only local search."""

    observations: dict[float, tuple[coarse.Candidate, Mapping[str, Any], float]] = {}
    for payload in evidence_by_id.values():
        candidate = _candidate(
            float(payload["offset_days_268091"]),
            float(payload["offset_days_268967"]),
        )
        offset = _axis_offset(axis, candidate)
        if offset is None:
            continue
        if axis.lower_offset_days - 1e-12 <= offset <= axis.upper_offset_days + 1e-12:
            observations[offset] = (candidate, payload, _metric(payload, axis.metric))

    ordered = sorted(observations.items())
    non_monotone_pairs = [
        {
            "lower_offset_days": lower_offset,
            "lower_service": lower_row[2],
            "higher_offset_days": higher_offset,
            "higher_service": higher_row[2],
            "service_increase_pp": 100.0 * (higher_row[2] - lower_row[2]),
        }
        for (lower_offset, lower_row), (higher_offset, higher_row) in zip(
            ordered, ordered[1:], strict=False
        )
        if higher_row[2] > lower_row[2] + 1e-9
    ]

    def best(offsets: Sequence[float]) -> float:
        return min(
            offsets,
            key=lambda offset: (
                abs(observations[offset][2] - axis.target_service),
                offset,
            ),
        )

    passing = [
        offset
        for offset in observations
        if abs(observations[offset][2] - axis.target_service)
        <= axis.tolerance + 1e-12
    ]

    def result(
        status: str,
        *,
        next_offset: float | None = None,
        selected_offset: float | None = None,
        scheduled_offsets: Sequence[float] = (),
        reason: str = "",
    ) -> dict[str, Any]:
        selected = (
            observations.get(float(selected_offset))
            if selected_offset is not None
            else None
        )
        return {
            "search_id": axis.search_id,
            "product_id": axis.product_id,
            "target_service": axis.target_service,
            "tolerance": axis.tolerance,
            "status": status,
            "next_offset_days": next_offset,
            "next_candidate_id": (
                _axis_candidate(axis, next_offset).candidate_id
                if next_offset is not None
                else ""
            ),
            "selected_offset_days": selected_offset,
            "selected_candidate_id": selected[0].candidate_id if selected else "",
            "selected_service": selected[2] if selected else None,
            "absolute_error_pp": (
                100.0 * abs(selected[2] - axis.target_service) if selected else None
            ),
            "evaluated_offsets_days": sorted(observations),
            "permitted_offsets_days": list(_axis_candidate_universe(axis)),
            "scheduled_offsets_days": list(dict.fromkeys(scheduled_offsets)),
            "target_attained": status == "within_tolerance",
            "selection_method": (
                "minimum_absolute_observed_error_then_minimum_delay"
            ),
            "interpolation_used": False,
            "non_monotone_response_observed": bool(non_monotone_pairs),
            "non_monotone_adjacent_pairs": non_monotone_pairs,
            "local_adaptive_search_not_global_proof": True,
            "reason": reason,
        }

    if axis.mode == "fixed_verified_anchor":
        offset = axis.initial_offset_days
        if offset not in observations:
            return result(
                "needs_candidate",
                next_offset=offset,
                scheduled_offsets=(offset,),
            )
        service = observations[offset][2]
        status = (
            "within_tolerance"
            if abs(service - axis.target_service) <= axis.tolerance + 1e-12
            else "fixed_anchor_outside_tolerance"
        )
        return result(
            status,
            selected_offset=offset,
            scheduled_offsets=(offset,),
            reason=(
                ""
                if status == "within_tolerance"
                else "The preregistered +7 day anchor does not attain 93% +/-1.5pp."
            ),
        )

    if passing:
        selected = best(passing)
        return result(
            "within_tolerance",
            selected_offset=selected,
            scheduled_offsets=tuple(sorted(observations)),
            reason="An actually simulated point is inside the acceptance band.",
        )

    if axis.search_id == "pf268091_target_80":
        # +15 is always the first fine probe.  Because the coarse response is
        # demonstrably non-monotone, +16 must also be observed whenever +15
        # misses the acceptance band; a low result at +15 does not prove that
        # +16 cannot rebound into the band.
        if 15.0 not in observations:
            return result(
                "needs_candidate", next_offset=15.0, scheduled_offsets=(15.0,)
            )
        schedule = [15.0]
        schedule.append(16.0)
        if 16.0 not in observations:
            return result(
                "needs_candidate",
                next_offset=16.0,
                scheduled_offsets=schedule,
            )
        schedule.extend((13.0, 12.0))
        for offset in (13.0, 12.0):
            if offset not in observations:
                return result(
                    "needs_candidate",
                    next_offset=offset,
                    scheduled_offsets=schedule,
                )
        core_support = tuple(
            offset for offset in PF268091_80_COARSE_SUPPORT if offset != 30.0
        )
        schedule.extend(core_support)
        for offset in core_support:
            if offset not in observations:
                return result(
                    "needs_candidate",
                    next_offset=offset,
                    scheduled_offsets=schedule,
                )
        schedule.extend(PF268091_80_COMPLETION)
        for offset in PF268091_80_COMPLETION:
            if offset not in observations:
                return result(
                    "needs_candidate",
                    next_offset=offset,
                    scheduled_offsets=schedule,
                )
        schedule.append(30.0)
        if 30.0 not in observations:
            return result(
                "needs_candidate",
                next_offset=30.0,
                scheduled_offsets=schedule,
            )
        error_at_30 = abs(observations[30.0][2] - axis.target_service)
        other_offsets = [offset for offset in observations if offset != 30.0]
        adjacent_triggered = (
            observations[30.0][2] < axis.target_service - axis.tolerance
            or error_at_30
            < min(
                abs(observations[offset][2] - axis.target_service)
                for offset in other_offsets
            )
        )
        if adjacent_triggered:
            schedule.extend(PF268091_80_ADJACENT)
            for offset in PF268091_80_ADJACENT:
                if offset not in observations:
                    return result(
                        "needs_candidate",
                        next_offset=offset,
                        scheduled_offsets=schedule,
                    )
        selected = best(list(observations))
        return result(
            "target_not_attained_after_local_search",
            selected_offset=selected,
            scheduled_offsets=schedule,
            reason=(
                "No simulated integer delay entered 78.5%-81.5%; the nearest "
                "observed service is reported and must not be labelled exact 80%."
            ),
        )

    if axis.search_id == "pf268967_target_80":
        # The observed response stays near 87% through +95 days and falls
        # below 47% at +100 days.  Probing +110/+115 cannot locate an 80%
        # state; inspect the only informative integer interval instead.
        schedule = list(PF268967_80_OBSERVED_TRANSITION)
        for offset in schedule:
            if offset not in observations:
                return result(
                    "needs_candidate",
                    next_offset=offset,
                    scheduled_offsets=schedule,
                )
        selected = best(list(observations))
        return result(
            "target_not_attained_after_local_search",
            selected_offset=selected,
            scheduled_offsets=schedule,
            reason=(
                "No simulated integer delay in the observed 95--100 day "
                "transition entered 78.5%--81.5%; the nearest observed "
                "service is retained for global paired verification."
            ),
        )

    wave = PF268967_WAVES[axis.search_id]
    schedule = list(wave)
    for offset in wave:
        if offset not in observations:
            return result(
                "needs_candidate",
                next_offset=offset,
                scheduled_offsets=schedule,
            )
    # Coarse boundary evidence, when available, is part of the observed
    # response.  It must guide the local neighbors as well: in the real PF
    # 268967 curve, +58 remains on the 100% plateau while +60 has already
    # crossed below the target, making +59 the only informative integer probe.
    wave_best = best(list(observations))
    for radius in (1.0, 2.0):
        neighbors = (
            wave_best - radius,
            wave_best + radius,
        )
        for offset in neighbors:
            if not axis.lower_offset_days <= offset <= axis.upper_offset_days:
                continue
            schedule.append(offset)
            if offset not in observations:
                return result(
                    "needs_candidate",
                    next_offset=offset,
                    scheduled_offsets=schedule,
                )
    selected = best(list(observations))
    return result(
        "target_not_attained_after_local_search",
        selected_offset=selected,
        scheduled_offsets=schedule,
        reason=(
            "No simulated first-wave or +/-1/2-day neighbor entered the "
            "acceptance band; the nearest observed service is reported."
        ),
    )


def _candidate_input(
    plan: ValidatedFinePlan,
    output_dir: Path,
    candidate: coarse.Candidate,
    *,
    create: bool,
) -> dict[str, Any]:
    source_graph = coarse._read_json(plan.coarse_plan.source_graph)
    graph, changes = coarse.apply_product_delays(
        source_graph,
        plan.coarse_plan.lanes_by_product,
        offset_days_268091=candidate.offset_days_268091,
        offset_days_268967=candidate.offset_days_268967,
    )
    directory = output_dir / "inputs" / candidate.candidate_id
    graph_path = directory / "candidate_graph.json"
    ledger_path = directory / "change_ledger.json"
    ledger = {
        "schema_version": f"{PLAN_SCHEMA_VERSION}.adaptive_change_ledger",
        "plan_signature": plan.manifest["plan_signature"],
        **asdict(candidate),
        "calibrated_dimension": "planned_supplier_lead_time_days_only",
        "changed_dimension_count": 1,
        "changes": changes,
    }
    if graph_path.is_file() or ledger_path.is_file():
        if (
            not graph_path.is_file()
            or not ledger_path.is_file()
            or coarse._read_json(graph_path) != graph
            or _read_json(ledger_path) != ledger
        ):
            raise ValueError(f"Fine candidate input is partial or changed: {candidate.candidate_id}")
    elif create:
        directory.mkdir(parents=True, exist_ok=False)
        _write_json(graph_path, graph)
        _write_json(ledger_path, ledger)
    else:
        raise FileNotFoundError(f"Fine candidate input missing: {candidate.candidate_id}")
    return {
        **asdict(candidate),
        "graph_path": graph_path.relative_to(output_dir).as_posix(),
        "graph_sha256": _sha256(graph_path),
        "change_ledger_path": ledger_path.relative_to(output_dir).as_posix(),
        "change_ledger_sha256": _sha256(ledger_path),
    }


def _adapter(
    plan: ValidatedFinePlan,
    output_dir: Path,
    candidate: coarse.Candidate,
    *,
    create_input: bool,
) -> coarse.ValidatedPlan:
    item = _candidate_input(plan, output_dir, candidate, create=create_input)
    return coarse.ValidatedPlan(
        plan_dir=output_dir,
        manifest={
            "plan_signature": plan.manifest["plan_signature"],
            "targets": [0.93, 0.80],
            "target_tolerance": TARGET_TOLERANCE,
        },
        candidates=(candidate,),
        inventory={candidate.candidate_id: item},
        lanes_by_product=plan.coarse_plan.lanes_by_product,
        source_graph=plan.coarse_plan.source_graph,
        engine=plan.coarse_plan.engine,
        profile=plan.coarse_plan.profile,
    )


def _fine_evidence_path(output_dir: Path, candidate_id: str) -> Path:
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "evidence" / f"{digest}.json"


def _coarse_evidence(
    plan: ValidatedFinePlan, candidate: coarse.Candidate, seed: int
) -> dict[str, Any] | None:
    if (
        plan.coarse_run_dir is None
        or candidate.candidate_id not in plan.coarse_plan.inventory
    ):
        return None
    path = coarse._evidence_path(plan.coarse_run_dir, candidate.candidate_id)
    if not path.is_file():
        return None
    payload = coarse._read_json(path)
    coarse._validate_evidence(payload, candidate, plan.coarse_plan, seed)
    return payload


def _wrap_evidence(
    *,
    plan: ValidatedFinePlan,
    candidate: coarse.Candidate,
    source_kind: str,
    source_evidence: Mapping[str, Any],
    seed: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        **asdict(candidate),
        "seed": int(seed),
        "source_kind": source_kind,
        "source_evidence": dict(source_evidence),
        "metrics": dict(source_evidence.get("metrics") or {}),
        "graph_sha256": str(source_evidence.get("graph_sha256") or ""),
        "engine_sha256": str(source_evidence.get("engine_sha256") or ""),
        "valid": True,
        "created_at_utc": _now(),
    }
    payload["evidence_signature"] = _stable_sha256(payload)
    return payload


def _validate_fine_evidence(
    payload: Mapping[str, Any], plan: ValidatedFinePlan, output_dir: Path, seed: int
) -> coarse.Candidate:
    unsigned = dict(payload)
    signature = str(unsigned.pop("evidence_signature", ""))
    candidate = _candidate(
        coarse.protocol.finite_float(payload.get("offset_days_268091"), math.nan),
        coarse.protocol.finite_float(payload.get("offset_days_268967"), math.nan),
    )
    if (
        payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or signature != _stable_sha256(unsigned)
        or payload.get("candidate_id") != candidate.candidate_id
        or int(payload.get("seed") or -1) != seed
        or payload.get("valid") is not True
        or payload.get("source_kind")
        not in {"coarse_signed_evidence_reuse", "fine_canonical_execution"}
    ):
        raise ValueError(f"Fine evidence contract mismatch: {candidate.candidate_id}")
    adapter = _adapter(plan, output_dir, candidate, create_input=False)
    source = payload.get("source_evidence") or {}
    coarse._validate_evidence(source, candidate, adapter, seed)
    if (
        payload.get("metrics") != source.get("metrics")
        or payload.get("graph_sha256") != source.get("graph_sha256")
        or payload.get("engine_sha256") != _sha256(plan.coarse_plan.engine)
    ):
        raise ValueError(f"Fine/source evidence mismatch: {candidate.candidate_id}")
    for field in (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
        "minimum_product_on_due_service",
    ):
        _metric(payload, field)
    for field in (
        "on_due_qty_268091",
        "demand_qty_268091",
        "on_due_qty_268967",
        "demand_qty_268967",
    ):
        _quantity(payload, field)
    _validate_service_quantities(payload)
    return candidate


def _load_evidence(
    plan: ValidatedFinePlan, output_dir: Path, seed: int
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((output_dir / "evidence").glob("*.json")):
        payload = _read_json(path)
        candidate = _validate_fine_evidence(payload, plan, output_dir, seed)
        if candidate.candidate_id in found:
            raise ValueError(f"Duplicate fine evidence: {candidate.candidate_id}")
        if path != _fine_evidence_path(output_dir, candidate.candidate_id):
            raise ValueError(f"Fine evidence filename mismatch: {path}")
        found[candidate.candidate_id] = payload
    return found


def _result_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") or {}
    return {
        "candidate_id": payload["candidate_id"],
        "offset_days_268091": payload["offset_days_268091"],
        "offset_days_268967": payload["offset_days_268967"],
        "seed": payload["seed"],
        "system_on_due_service": metrics["system_on_due_service"],
        "on_due_service_268091": metrics["on_due_service_268091"],
        "on_due_service_268967": metrics["on_due_service_268967"],
        "minimum_product_on_due_service": metrics[
            "minimum_product_on_due_service"
        ],
        "on_due_qty_268091": metrics["on_due_qty_268091"],
        "demand_qty_268091": metrics["demand_qty_268091"],
        "on_due_qty_268967": metrics["on_due_qty_268967"],
        "demand_qty_268967": metrics["demand_qty_268967"],
        "graph_sha256": payload["graph_sha256"],
        "source_kind": payload["source_kind"],
        "evidence_signature": payload["evidence_signature"],
        "valid": payload["valid"],
    }


def _decisions(evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [decide_axis(axis, evidence) for axis in AXES]


def _write_progress(
    output_dir: Path,
    *,
    plan: ValidatedFinePlan,
    evidence: Mapping[str, Mapping[str, Any]],
    status: str,
    error: str = "",
) -> None:
    rows = sorted(
        (_result_row(payload) for payload in evidence.values()),
        key=lambda row: (
            float(row["offset_days_268091"]),
            float(row["offset_days_268967"]),
        ),
    )
    _write_csv(output_dir / "fine_metrics.csv", rows, RESULT_FIELDS)
    permitted_ids = {
        str(row["candidate_id"])
        for row in plan.manifest["explicit_candidate_pairs"]
    }
    _write_json(
        output_dir / "progress.json",
        {
            "schema_version": PROGRESS_SCHEMA_VERSION,
            "plan_signature": plan.manifest["plan_signature"],
            "status": status,
            "seed": DEFAULT_SEED,
            "completed_case_count": len(evidence),
            "permitted_one_axis_pair_count": len(permitted_ids),
            "completed_permitted_one_axis_pair_count": len(
                permitted_ids & set(evidence)
            ),
            "joint_case_count": len(set(evidence) - permitted_ids),
            "coarse_reused_case_count": sum(
                payload["source_kind"] == "coarse_signed_evidence_reuse"
                for payload in evidence.values()
            ),
            "axis_decisions": _decisions(evidence),
            "error": error,
            "updated_at_utc": _now(),
        },
    )


def _obtain(
    plan: ValidatedFinePlan,
    output_dir: Path,
    candidate: coarse.Candidate,
    *,
    seed: int,
    executor: RawExecutor,
) -> dict[str, Any]:
    adapter = _adapter(plan, output_dir, candidate, create_input=True)
    reused = _coarse_evidence(plan, candidate, seed)
    if reused is None:
        source = executor(candidate, adapter, output_dir, seed)
        source_kind = "fine_canonical_execution"
    else:
        source = reused
        source_kind = "coarse_signed_evidence_reuse"
    coarse._validate_evidence(source, candidate, adapter, seed)
    payload = _wrap_evidence(
        plan=plan,
        candidate=candidate,
        source_kind=source_kind,
        source_evidence=source,
        seed=seed,
    )
    path = _fine_evidence_path(output_dir, candidate.candidate_id)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite fine evidence: {path}")
    _write_json(path, payload)
    _validate_fine_evidence(payload, plan, output_dir, seed)
    return payload


def _joint_candidates(decisions: Sequence[Mapping[str, Any]]) -> dict[str, coarse.Candidate]:
    by_search = {str(row["search_id"]): row for row in decisions}
    if set(by_search) != {axis.search_id for axis in AXES} or any(
        row.get("status") not in TERMINAL_AXIS_STATUSES
        or row.get("selected_offset_days") is None
        for row in by_search.values()
    ):
        raise ValueError("All four axis searches must be terminal before joint verification")
    return {
        "op_93": _candidate(
            float(by_search["pf268091_target_93"]["selected_offset_days"]),
            float(by_search["pf268967_target_93"]["selected_offset_days"]),
        ),
        "op_80": _candidate(
            float(by_search["pf268091_target_80"]["selected_offset_days"]),
            float(by_search["pf268967_target_80"]["selected_offset_days"]),
        ),
    }


def _joint_records(
    joints: Mapping[str, coarse.Candidate],
    evidence: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    targets = {"op_93": 0.93, "op_80": 0.80}
    for point_id in ("op_93", "op_80"):
        candidate = joints[point_id]
        payload = evidence.get(candidate.candidate_id)
        if payload is None:
            raise ValueError(f"Joint verification evidence missing: {point_id}")
        left = _metric(payload, "on_due_service_268091")
        right = _metric(payload, "on_due_service_268967")
        on_due_left = _quantity(payload, "on_due_qty_268091")
        demand_left = _quantity(payload, "demand_qty_268091")
        on_due_right = _quantity(payload, "on_due_qty_268967")
        demand_right = _quantity(payload, "demand_qty_268967")
        if demand_left <= 0.0 or demand_right <= 0.0:
            raise ValueError(f"Joint verification has zero demand: {point_id}")
        pooled_global = (on_due_left + on_due_right) / (
            demand_left + demand_right
        )
        reported_global = _metric(payload, "system_on_due_service")
        if not math.isclose(
            pooled_global, reported_global, rel_tol=1e-10, abs_tol=1e-12
        ):
            raise ValueError(
                f"Joint global service is inconsistent with quantities: {point_id}"
            )
        target = targets[point_id]
        rows.append(
            {
                "operating_point_id": point_id,
                **asdict(candidate),
                "target_service_global": target,
                "on_due_service_268091": left,
                "on_due_service_268967": right,
                "system_on_due_service": pooled_global,
                "on_due_qty_268091": on_due_left,
                "demand_qty_268091": demand_left,
                "on_due_qty_268967": on_due_right,
                "demand_qty_268967": demand_right,
                "error_268091_pp": 100.0 * (left - target),
                "error_268967_pp": 100.0 * (right - target),
                "product_service_gap_pp": 100.0 * abs(left - right),
                "global_target_within_tolerance": abs(
                    pooled_global - target
                )
                <= TARGET_TOLERANCE + 1e-12,
                "products_balanced_within_5pp": abs(left - right)
                <= PRODUCT_BALANCE_LIMIT + 1e-12,
                "no_degraded_product_saturated_at_100pct": max(left, right)
                < 1.0 - 1e-12,
                "within_operating_point_contract": (
                    abs(pooled_global - target)
                    <= TARGET_TOLERANCE + 1e-12
                    and max(left, right) < 1.0 - 1e-12
                ),
                "evidence_signature": payload["evidence_signature"],
            }
        )
    return rows


def build_final_outputs(
    plan: ValidatedFinePlan,
    output_dir: Path,
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    write: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decisions = _decisions(evidence)
    joints = _joint_candidates(decisions)
    joint_records = _joint_records(joints, evidence)
    if not all(row["within_operating_point_contract"] for row in joint_records):
        raise ValueError(
            "Joint selected pairs do not attain the global-state contract"
        )
    if (
        joints["op_80"].offset_days_268091 < joints["op_93"].offset_days_268091
        or joints["op_80"].offset_days_268967 < joints["op_93"].offset_days_268967
    ):
        raise ValueError("The 80% point must not be less severe than the 93% point")
    baseline = _candidate(0.0, 0.0)
    if baseline.candidate_id not in evidence:
        raise ValueError("The zero-delay op_100 baseline evidence is missing")
    selection: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "joint_global_targets_attained_product_gap_reported",
        "target_tolerance": TARGET_TOLERANCE,
        "target_scope": "global_demand_weighted_finished_product_service",
        "product_balance_limit_pp": 100.0 * PRODUCT_BALANCE_LIMIT,
        "product_gap_is_acceptance_criterion": False,
        "service_evaluation_window": SERVICE_EVALUATION_WINDOW,
        "axis_records": decisions,
        "joint_records": joint_records,
        "common_seed": DEFAULT_SEED,
        "interpolation_used": False,
        "local_adaptive_search_not_global_proof": True,
        "simulation_hypotheses_not_observed_performance": True,
        "adaptive_algorithm_revision": ADAPTIVE_ALGORITHM_REVISION,
        "calibration_driver_sha256": _sha256(Path(__file__).resolve()),
        "protocol_amendment": PROTOCOL_AMENDMENT,
    }
    selection["selection_signature"] = _stable_sha256(selection)

    rows_by_id = {candidate_id: payload for candidate_id, payload in evidence.items()}

    def point(
        point_id: str,
        target: float,
        candidate: coarse.Candidate,
        label: str,
    ) -> dict[str, Any]:
        payload = rows_by_id[candidate.candidate_id]
        item = _candidate_input(plan, output_dir, candidate, create=False)
        graph = (output_dir / item["graph_path"]).resolve()
        return {
            "operating_point_id": point_id,
            "operating_point_label": label,
            "target_service": target,
            "target_scope": "global_demand_weighted_finished_product_service",
            "source_candidate_id": candidate.candidate_id,
            "degradation_family": "balanced_product_supplier_planned_lead",
            "degradation_unit": "jours_ajoutes_par_chaine_produit",
            "offset_days_268091": candidate.offset_days_268091,
            "offset_days_268967": candidate.offset_days_268967,
            "screening_system_service": _metric(payload, "system_on_due_service"),
            "screening_product_268091_service": _metric(
                payload, "on_due_service_268091"
            ),
            "screening_product_268967_service": _metric(
                payload, "on_due_service_268967"
            ),
            "graph": str(graph),
            "graph_sha256": item["graph_sha256"],
            "supplier_floors": "",
            "supplier_floors_sha256": "",
            "factory_capacities": "",
            "factory_capacities_sha256": "",
        }

    metrics_path = output_dir / "fine_metrics.csv"
    run_manifest_path = output_dir / "run_manifest.json"
    campaign: dict[str, Any] = {
        "schema_version": CAMPAIGN_POINTS_SCHEMA_VERSION,
        "status": "exploratory_one_seed_fine_calibration_complete",
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "supplier_capacity_override_included": False,
        "factory_capacity_override_included": False,
        "supplier_availability_degradation_included": False,
        "simulation_hypotheses_not_observed_supplier_performance": True,
        "service_evaluation_window": SERVICE_EVALUATION_WINDOW,
        "source_fine_plan": {
            "path": str(plan.plan_dir),
            "plan_signature": plan.manifest["plan_signature"],
            "manifest_sha256": _sha256(plan.plan_dir / "fine_calibration_plan.json"),
        },
        "source_coarse_plan": plan.manifest["coarse_source"],
        "source_results": {
            "seed": DEFAULT_SEED,
            "completed_candidate_count": len(evidence),
            "metrics_csv": str(metrics_path.resolve()),
            "metrics_csv_sha256": _sha256(metrics_path) if metrics_path.is_file() else "",
            "run_manifest": str(run_manifest_path.resolve()),
            "run_manifest_sha256": (
                _sha256(run_manifest_path) if run_manifest_path.is_file() else ""
            ),
            "evidence_signature_set_sha256": _stable_sha256(
                sorted(str(row["evidence_signature"]) for row in evidence.values())
            ),
            "coarse_reused_case_count": sum(
                row["source_kind"] == "coarse_signed_evidence_reuse"
                for row in evidence.values()
            ),
            "adaptive_algorithm_revision": ADAPTIVE_ALGORITHM_REVISION,
            "calibration_driver_sha256": _sha256(Path(__file__).resolve()),
            "protocol_amendment": PROTOCOL_AMENDMENT,
        },
        "selection_signature": selection["selection_signature"],
        "engine_sha256": _sha256(plan.coarse_plan.engine),
        "profile_sha256": _sha256(plan.coarse_plan.profile),
        "operating_points": [
            point(
                "op_100",
                1.0,
                baseline,
                "Fonctionnement de référence — délais sans ajout",
            ),
            point(
                "op_93",
                0.93,
                joints["op_93"],
                "Fonctionnement simulé visant 93 % de service global",
            ),
            point(
                "op_80",
                0.80,
                joints["op_80"],
                "Fonctionnement simulé visant 80 % de service global",
            ),
        ],
    }
    campaign["artifact_signature"] = _stable_sha256(campaign)
    if write:
        _write_json(output_dir / "fine_selection.json", selection)
        _write_json(output_dir / "campaign_operating_points.json", campaign)
    return selection, campaign


@contextmanager
def _exclusive_lock(output_dir: Path):
    path = output_dir / ".fine_balanced_delay_calibration.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another fine calibration owns {path}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} utc={_now()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def _register_run(plan: ValidatedFinePlan, output_dir: Path, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    expected = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": _sha256(plan.coarse_plan.engine),
        "seed": int(seed),
        "common_random_numbers": True,
        "coarse_run_mutated": False,
        "candidate_design": "explicit_pairs_only_not_cartesian",
    }
    if path.is_file():
        if _read_json(path) != expected:
            raise ValueError("Fine result directory belongs to another run")
        return
    unmanaged = [child for child in output_dir.iterdir() if child.name != path.name]
    if unmanaged:
        raise ValueError("Refusing a non-empty unregistered fine result directory")
    _write_json(path, expected)


def _require_coarse_run_finished(plan: ValidatedFinePlan) -> None:
    """Fail closed so the fine engine cannot compete with an active coarse run."""

    directory = plan.coarse_run_dir
    if directory is None:
        return
    lock = directory / ".balanced_delay_calibration.lock"
    progress_path = directory / "progress.json"
    if lock.exists():
        raise RuntimeError(
            "Coarse 36-case calibration is still active; fine run is deferred"
        )
    if not progress_path.is_file():
        raise RuntimeError("Coarse run has no terminal progress proof")
    progress = _read_json(progress_path)
    if (
        progress.get("status") != "complete"
        or int(progress.get("completed_case_count") or -1)
        != int(progress.get("planned_case_count") or -2)
        or int(progress.get("failed_case_count") or 0) != 0
    ):
        raise RuntimeError(
            "Coarse 36-case calibration is not complete and valid; fine run is deferred"
        )


def _next_axis_candidate(
    decisions: Sequence[Mapping[str, Any]],
) -> coarse.Candidate | None:
    by_id = {axis.search_id: axis for axis in AXES}
    for decision in decisions:
        if decision["status"] == "needs_candidate":
            axis = by_id[str(decision["search_id"])]
            return _axis_candidate(axis, float(decision["next_offset_days"]))
        if decision["status"] in {
            "within_tolerance",
            "target_not_attained_after_local_search",
        }:
            continue
        if decision["status"] != "within_tolerance":
            raise ValueError(
                f"Fine axis {decision['search_id']} failed: "
                f"{decision['status']} — {decision['reason']}"
            )
    return None


def build_unattained_output(
    plan: ValidatedFinePlan,
    output_dir: Path,
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    joint_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Report observed services without publishing false global states."""

    decisions = _decisions(evidence)
    failures = [
        row
        for row in decisions
        if row["status"] == "target_not_attained_after_local_search"
    ]
    if any(row["status"] not in TERMINAL_AXIS_STATUSES for row in decisions):
        raise ValueError("Axis searches are not terminal")
    payload: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "global_balanced_target_not_attained_no_campaign_export",
        "target_tolerance": TARGET_TOLERANCE,
        "target_scope": "global_demand_weighted_finished_product_service",
        "product_balance_limit_pp": 100.0 * PRODUCT_BALANCE_LIMIT,
        "product_gap_is_acceptance_criterion": False,
        "service_evaluation_window": SERVICE_EVALUATION_WINDOW,
        "axis_records": decisions,
        "joint_records": [dict(row) for row in joint_records],
        "unattained_search_ids": [row["search_id"] for row in failures],
        "common_seed": DEFAULT_SEED,
        "interpolation_used": False,
        "local_adaptive_search_not_global_proof": True,
        "simulation_hypotheses_not_observed_performance": True,
        "adaptive_algorithm_revision": ADAPTIVE_ALGORITHM_REVISION,
        "calibration_driver_sha256": _sha256(Path(__file__).resolve()),
        "protocol_amendment": PROTOCOL_AMENDMENT,
        "business_limit": (
            "Nearest observed services are reported as obtained states. The "
            "global 80%/93% state contract was not attained, so these "
            "states cannot feed the supplier incident campaign."
        ),
    }
    payload["selection_signature"] = _stable_sha256(payload)
    _write_json(output_dir / "fine_selection.json", payload)
    return payload


def run_adaptive(
    plan_dir: Path,
    output_dir: Path,
    *,
    seed: int = DEFAULT_SEED,
    executor: RawExecutor = coarse.execute_candidate,
) -> dict[str, Any]:
    """Execute or resume the explicit adaptive search and joint verification."""

    if seed != DEFAULT_SEED:
        raise ValueError(f"Fine/coarse evidence contract requires seed {DEFAULT_SEED}")
    plan = validate_plan(plan_dir)
    _require_coarse_run_finished(plan)
    output_dir = output_dir.resolve()
    _register_run(plan, output_dir, seed)
    with _exclusive_lock(output_dir):
        evidence = _load_evidence(plan, output_dir, seed)
        try:
            baseline = _candidate(0.0, 0.0)
            if baseline.candidate_id not in evidence:
                evidence[baseline.candidate_id] = _obtain(
                    plan,
                    output_dir,
                    baseline,
                    seed=seed,
                    executor=executor,
                )
                _write_progress(
                    output_dir,
                    plan=plan,
                    evidence=evidence,
                    status="running",
                )

            # Import already-computed signed coarse boundaries without running
            # new simulations.  They prevent the adaptive search from walking
            # back into a demonstrated plateau and preserve the coarse work as
            # evidence rather than merely as narrative context.
            coarse_boundaries = (
                _candidate(0.0, 45.0),
                _candidate(0.0, 60.0),
                _candidate(0.0, 90.0),
                _candidate(0.0, 120.0),
            )
            imported_boundary = False
            for candidate in coarse_boundaries:
                if candidate.candidate_id in evidence:
                    continue
                if _coarse_evidence(plan, candidate, seed) is None:
                    continue
                evidence[candidate.candidate_id] = _obtain(
                    plan,
                    output_dir,
                    candidate,
                    seed=seed,
                    executor=executor,
                )
                imported_boundary = True
            if imported_boundary:
                _write_progress(
                    output_dir,
                    plan=plan,
                    evidence=evidence,
                    status="running",
                )

            for _iteration in range(64):
                decisions = _decisions(evidence)
                next_candidate = _next_axis_candidate(decisions)
                if next_candidate is not None:
                    if next_candidate.candidate_id in evidence:
                        raise RuntimeError("Adaptive decision requested existing evidence")
                    evidence[next_candidate.candidate_id] = _obtain(
                        plan,
                        output_dir,
                        next_candidate,
                        seed=seed,
                        executor=executor,
                    )
                    _write_progress(
                        output_dir,
                        plan=plan,
                        evidence=evidence,
                        status="running",
                    )
                    continue
                joints = _joint_candidates(decisions)
                missing_joint = next(
                    (
                        candidate
                        for candidate in joints.values()
                        if candidate.candidate_id not in evidence
                    ),
                    None,
                )
                if missing_joint is not None:
                    evidence[missing_joint.candidate_id] = _obtain(
                        plan,
                        output_dir,
                        missing_joint,
                        seed=seed,
                        executor=executor,
                    )
                    _write_progress(
                        output_dir,
                        plan=plan,
                        evidence=evidence,
                        status="running",
                    )
                    continue
                joint_records = _joint_records(joints, evidence)
                if not all(
                    row["within_operating_point_contract"]
                    for row in joint_records
                ):
                    selection = build_unattained_output(
                        plan,
                        output_dir,
                        evidence,
                        joint_records=joint_records,
                    )
                    _write_progress(
                        output_dir,
                        plan=plan,
                        evidence=evidence,
                        status="complete_global_target_not_attained",
                    )
                    return {
                        "selection": selection,
                        "campaign_operating_points": None,
                    }
                selection, campaign = build_final_outputs(
                    plan, output_dir, evidence, write=True
                )
                _write_progress(
                    output_dir,
                    plan=plan,
                    evidence=evidence,
                    status="complete",
                )
                # Rebuild after final metrics/progress writes so all recorded hashes
                # refer to their terminal files.
                selection, campaign = build_final_outputs(
                    plan, output_dir, evidence, write=True
                )
                return {
                    "selection": selection,
                    "campaign_operating_points": campaign,
                }
            raise RuntimeError("Adaptive calibration exceeded its deterministic iteration cap")
        except Exception as exc:
            _write_progress(
                output_dir,
                plan=plan,
                evidence=evidence,
                status="interrupted",
                error=str(exc),
            )
            raise


def export_completed(plan_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Validate and export an already complete fine run without simulations."""

    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    _register_run(plan, output_dir, DEFAULT_SEED)
    evidence = _load_evidence(plan, output_dir, DEFAULT_SEED)
    decisions = _decisions(evidence)
    next_candidate = _next_axis_candidate(decisions)
    if next_candidate is not None:
        raise ValueError(
            "Fine run is incomplete; next required candidate is "
            f"{next_candidate.candidate_id}"
        )
    joints = _joint_candidates(decisions)
    missing_joint = [
        candidate.candidate_id
        for candidate in joints.values()
        if candidate.candidate_id not in evidence
    ]
    if missing_joint:
        raise ValueError(
            "Fine run is missing joint verification evidence: "
            + ", ".join(missing_joint)
        )
    joint_records = _joint_records(joints, evidence)
    if not all(row["within_operating_point_contract"] for row in joint_records):
        selection = build_unattained_output(
            plan,
            output_dir,
            evidence,
            joint_records=joint_records,
        )
        _write_progress(
            output_dir,
            plan=plan,
            evidence=evidence,
            status="complete_global_target_not_attained",
        )
        return {"selection": selection, "campaign_operating_points": None}
    selection, campaign = build_final_outputs(plan, output_dir, evidence, write=True)
    _write_progress(
        output_dir,
        plan=plan,
        evidence=evidence,
        status="complete",
    )
    selection, campaign = build_final_outputs(plan, output_dir, evidence, write=True)
    return {"selection": selection, "campaign_operating_points": campaign}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("plan", "validate", "run", "export"), required=True
    )
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--coarse-plan-dir", type=Path, default=DEFAULT_COARSE_PLAN)
    parser.add_argument("--coarse-run-dir", type=Path, default=DEFAULT_COARSE_RUN)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        path = prepare_plan(
            args.plan_dir,
            coarse_plan_dir=args.coarse_plan_dir,
            coarse_run_dir=args.coarse_run_dir,
        )
        print(f"Fine explicit-pair plan prepared; no simulation executed: {path}")
    elif args.mode == "validate":
        plan = validate_plan(args.plan_dir)
        print(
            f"Valid fine plan: {plan.manifest['explicit_candidate_pair_count']} "
            "permitted explicit one-axis pairs"
        )
    elif args.mode == "run":
        result = run_adaptive(args.plan_dir, args.output_dir, seed=args.seed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = export_completed(args.plan_dir, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
