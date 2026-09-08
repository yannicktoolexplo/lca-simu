#!/usr/bin/env python3
"""Five-seed prevalidation of fine supplier-delay operating points.

This additive stage is deliberately separate from the one-seed calibration.
It plans and can resume exactly 3 operating points x 5 campaign seeds, baseline
only.  It publishes a strict campaign input only when the pooled,
demand-weighted global service is within +/-1.5 percentage points of each state
label and degraded states do not leave either product saturated at 100%.
The gap between product services is always published; five points is a
descriptive warning threshold, not an invented rejection rule.  Otherwise the
stage reports and renames the actually obtained state.
"""

from __future__ import annotations

import argparse
import copy
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
    supplier_balanced_product_delay_fine_calibration as fine,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v2 as campaign_v2,
)


SCHEMA_VERSION = "etudecas.supplier_balanced_product_delay_prevalidation.v1"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence"
SUMMARY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.summary"
VALIDATED_POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.validated_points"
OBSERVED_POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.observed_points"
CAMPAIGN_SEEDS = tuple(range(340282, 340287))
CALIBRATION_SEED = fine.DEFAULT_SEED
TARGET_TOLERANCE = fine.TARGET_TOLERANCE
PRODUCT_BALANCE_LIMIT = fine.PRODUCT_BALANCE_LIMIT
LOW_STATE_FALLBACK_RANGE = (0.75, 0.85)
SERVICE_EVALUATION_WINDOW = fine.SERVICE_EVALUATION_WINDOW
POINT_IDS = ("op_100", "op_93", "op_80")
DEFAULT_SOURCE = fine.DEFAULT_RUN_OUTPUT / "campaign_operating_points.json"
DEFAULT_PLAN_OUTPUT = (
    coarse.protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_prevalidation_plan_20260904_v1"
)
DEFAULT_RUN_OUTPUT = (
    coarse.protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_prevalidation_run_20260904_v1"
)
RESULT_FIELDS = (
    "case_key",
    "operating_point_id",
    "target_service",
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
    "evidence_signature",
    "valid",
)


@dataclass(frozen=True)
class PrevalidationPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    source_points: dict[str, Any]
    points: tuple[dict[str, Any], ...]
    fine_plan: fine.ValidatedFinePlan


BaselineExecutor = Callable[
    [str, Mapping[str, Any], PrevalidationPlan, Path, int], dict[str, Any]
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


def _case_key(point_id: str, seed: int) -> str:
    return f"{point_id}__seed_{seed}"


def _candidate(point: Mapping[str, Any]) -> coarse.Candidate:
    left = coarse.protocol.finite_float(point.get("offset_days_268091"), math.nan)
    right = coarse.protocol.finite_float(point.get("offset_days_268967"), math.nan)
    if not all(math.isfinite(value) and value >= 0.0 for value in (left, right)):
        raise ValueError("Operating point lacks finite non-negative product delays")
    return coarse.Candidate(
        candidate_id=coarse._candidate_id(left, right),
        offset_days_268091=left,
        offset_days_268967=right,
    )


def _manifest_signature_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "source": manifest.get("source"),
        "source_hashes": manifest.get("source_hashes"),
        "seeds": manifest.get("seeds"),
        "cases": manifest.get("cases"),
        "execution_contract": manifest.get("execution_contract"),
    }


def _load_source(path: Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    payload = _read_json(path)
    # This is the one-seed calibration candidate that this module exists to
    # prevalidate.  The full campaign loader defaults to rejecting it.
    points = tuple(campaign_v2.load_operating_points(path, require_prevalidated=False))
    if tuple(point["operating_point_id"] for point in points) != POINT_IDS:
        raise ValueError("Prevalidation requires exact op_100/op_93/op_80 inputs")
    fine_source = payload.get("source_fine_plan") or {}
    if not str(fine_source.get("path") or ""):
        raise ValueError("Operating points do not identify their fine calibration plan")
    return payload, points


def prepare_plan(output_dir: Path, *, source_points_path: Path = DEFAULT_SOURCE) -> Path:
    """Create an immutable 15-case plan without executing the engine."""

    output_dir = output_dir.resolve()
    source_points_path = source_points_path.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite prevalidation plan: {output_dir}")
    source, points = _load_source(source_points_path)
    fine_source = source["source_fine_plan"]
    fine_plan = fine.validate_plan(Path(str(fine_source["path"])))
    if (
        fine_source.get("plan_signature") != fine_plan.manifest["plan_signature"]
        or source.get("service_evaluation_window") != SERVICE_EVALUATION_WINDOW
        or int(source.get("source_results", {}).get("seed") or -1)
        != CALIBRATION_SEED
    ):
        raise ValueError("Fine calibration provenance/window mismatch")
    cases = [
        {
            "case_key": _case_key(point_id, seed),
            "operating_point_id": point_id,
            "seed": seed,
        }
        for point_id in POINT_IDS
        for seed in CAMPAIGN_SEEDS
    ]
    manifest: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": "planned_not_executed",
        "created_at_utc": _now(),
        "source": {
            "campaign_operating_points": str(source_points_path),
            "campaign_operating_points_sha256": _sha256(source_points_path),
            "campaign_artifact_signature": source.get("artifact_signature"),
            "fine_plan": str(fine_plan.plan_dir),
            "fine_plan_signature": fine_plan.manifest["plan_signature"],
        },
        "source_hashes": {
            "engine_sha256": _sha256(fine_plan.coarse_plan.engine),
            "profile_sha256": _sha256(fine_plan.coarse_plan.profile),
            "graphs_by_point": {
                point["operating_point_id"]: point["graph_sha256"]
                for point in points
            },
        },
        "seeds": list(CAMPAIGN_SEEDS),
        "calibration_seed_excluded": CALIBRATION_SEED,
        "cases": cases,
        "expected_case_count": 15,
        "execution_contract": {
            "stage": "baseline_only",
            "scenario": "scn:BASE",
            "common_random_numbers": True,
            "service_evaluation_window": SERVICE_EVALUATION_WINDOW,
            "quality_incident": False,
            "supplier_availability_incident": False,
            "acute_incident": False,
            "state_dependent_risk": False,
            "capacity_override": False,
            "target_tolerance": TARGET_TOLERANCE,
            "acceptance_statistic": "pooled_global_ratio_of_sums",
            "product_gap_reporting_threshold_pp": 100.0 * PRODUCT_BALANCE_LIMIT,
            "product_gap_is_acceptance_criterion": False,
            "low_state_fallback_range": list(LOW_STATE_FALLBACK_RANGE),
            "low_state_fallback_label_rule": "publish_observed_global_service_not_80",
            "pooled_state_order": "op_100 > op_93 > op_80",
            "per_seed_strict_state_order_required": 4,
            "per_seed_count": len(CAMPAIGN_SEEDS),
            "dispersion_statistics": ["mean", "median", "p10", "p90", "iqr"],
        },
    }
    manifest["plan_signature"] = _stable_sha256(
        _manifest_signature_payload(manifest)
    )
    output_dir.mkdir(parents=True)
    _write_json(output_dir / "prevalidation_plan.json", manifest)
    _write_csv(
        output_dir / "case_ledger.csv",
        cases,
        ("case_key", "operating_point_id", "seed"),
    )
    return output_dir


def validate_plan(plan_dir: Path) -> PrevalidationPlan:
    plan_dir = plan_dir.resolve()
    manifest_path = plan_dir / "prevalidation_plan.json"
    ledger_path = plan_dir / "case_ledger.csv"
    if not manifest_path.is_file() or not ledger_path.is_file():
        raise FileNotFoundError(f"Incomplete prevalidation plan: {plan_dir}")
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "planned_not_executed"
        or manifest.get("plan_signature")
        != _stable_sha256(_manifest_signature_payload(manifest))
        or manifest.get("seeds") != list(CAMPAIGN_SEEDS)
        or manifest.get("calibration_seed_excluded") != CALIBRATION_SEED
        or manifest.get("expected_case_count") != 15
        or len(manifest.get("cases") or []) != 15
    ):
        raise ValueError("Prevalidation plan/signature mismatch")
    source_path = Path(
        str(manifest.get("source", {}).get("campaign_operating_points") or "")
    ).resolve()
    if (
        not source_path.is_file()
        or _sha256(source_path)
        != manifest["source"]["campaign_operating_points_sha256"]
    ):
        raise ValueError("Source operating-point file changed")
    source, points = _load_source(source_path)
    if source.get("artifact_signature") != manifest["source"].get(
        "campaign_artifact_signature"
    ):
        raise ValueError("Source operating-point signature changed")
    fine_plan = fine.validate_plan(Path(str(manifest["source"]["fine_plan"])))
    if (
        fine_plan.manifest["plan_signature"]
        != manifest["source"]["fine_plan_signature"]
        or manifest.get("source_hashes")
        != {
            "engine_sha256": _sha256(fine_plan.coarse_plan.engine),
            "profile_sha256": _sha256(fine_plan.coarse_plan.profile),
            "graphs_by_point": {
                point["operating_point_id"]: point["graph_sha256"]
                for point in points
            },
        }
    ):
        raise ValueError("Prevalidation source hashes changed")
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = [
        {key: str(value) for key, value in row.items()}
        for row in manifest["cases"]
    ]
    if rows != expected:
        raise ValueError("Prevalidation case ledger differs from signed plan")
    return PrevalidationPlan(
        plan_dir=plan_dir,
        manifest=manifest,
        source_points=source,
        points=points,
        fine_plan=fine_plan,
    )


def _point(plan: PrevalidationPlan, point_id: str) -> dict[str, Any]:
    matches = [
        point for point in plan.points if point["operating_point_id"] == point_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Unknown operating point: {point_id}")
    return matches[0]


def _adapter(
    point: Mapping[str, Any], plan: PrevalidationPlan
) -> tuple[coarse.Candidate, coarse.ValidatedPlan]:
    candidate = _candidate(point)
    graph = Path(str(point["graph"])).resolve()
    adapter = coarse.ValidatedPlan(
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
                "graph_path": str(graph),
                "graph_sha256": _sha256(graph),
            }
        },
        lanes_by_product=plan.fine_plan.coarse_plan.lanes_by_product,
        source_graph=plan.fine_plan.coarse_plan.source_graph,
        engine=plan.fine_plan.coarse_plan.engine,
        profile=plan.fine_plan.coarse_plan.profile,
    )
    return candidate, adapter


def execute_baseline(
    _point_id: str,
    point: Mapping[str, Any],
    plan: PrevalidationPlan,
    output_dir: Path,
    seed: int,
) -> dict[str, Any]:
    candidate, adapter = _adapter(point, plan)
    return coarse.execute_candidate(candidate, adapter, output_dir, seed)


def _evidence_path(output_dir: Path, case_key: str) -> Path:
    digest = hashlib.sha256(case_key.encode("utf-8")).hexdigest()[:20]
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
        raise ValueError(f"Invalid non-negative quantity metric: {field}")
    return value


def _validate_service_quantities(payload: Mapping[str, Any]) -> None:
    left_on_due = _quantity(payload, "on_due_qty_268091")
    left_demand = _quantity(payload, "demand_qty_268091")
    right_on_due = _quantity(payload, "on_due_qty_268967")
    right_demand = _quantity(payload, "demand_qty_268967")
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
            _metric(payload, field), derived, rel_tol=1e-9, abs_tol=1e-12
        ):
            raise ValueError(f"Service metric is inconsistent with quantities: {field}")


def _wrap_evidence(
    *,
    plan: PrevalidationPlan,
    point_id: str,
    point: Mapping[str, Any],
    seed: int,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "case_key": _case_key(point_id, seed),
        "operating_point_id": point_id,
        "target_service": float(point["target_service"]),
        "seed": seed,
        "metrics": dict(source.get("metrics") or {}),
        "graph_sha256": str(source.get("graph_sha256") or ""),
        "engine_sha256": str(source.get("engine_sha256") or ""),
        "source_evidence": dict(source),
        "valid": True,
        "created_at_utc": _now(),
    }
    payload["evidence_signature"] = _stable_sha256(payload)
    return payload


def _validate_evidence(
    payload: Mapping[str, Any], plan: PrevalidationPlan
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop("evidence_signature", ""))
    point_id = str(payload.get("operating_point_id") or "")
    seed = int(payload.get("seed") or -1)
    point = _point(plan, point_id)
    candidate, adapter = _adapter(point, plan)
    source = payload.get("source_evidence") or {}
    coarse._validate_evidence(source, candidate, adapter, seed)
    if (
        payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or signature != _stable_sha256(unsigned)
        or seed not in CAMPAIGN_SEEDS
        or payload.get("case_key") != _case_key(point_id, seed)
        or payload.get("target_service") != float(point["target_service"])
        or payload.get("metrics") != source.get("metrics")
        or payload.get("graph_sha256") != point["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("valid") is not True
    ):
        raise ValueError(f"Prevalidation evidence mismatch: {point_id}/{seed}")
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
    return _case_key(point_id, seed)


def _load_evidence(
    plan: PrevalidationPlan, output_dir: Path
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((output_dir / "evidence").glob("*.json")):
        payload = _read_json(path)
        key = _validate_evidence(payload, plan)
        if key in found or path != _evidence_path(output_dir, key):
            raise ValueError(f"Duplicate/misnamed prevalidation evidence: {key}")
        found[key] = payload
    return found


def _result_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_key": payload["case_key"],
        "operating_point_id": payload["operating_point_id"],
        "target_service": payload["target_service"],
        "seed": payload["seed"],
        "system_on_due_service": _metric(payload, "system_on_due_service"),
        "on_due_service_268091": _metric(payload, "on_due_service_268091"),
        "on_due_service_268967": _metric(payload, "on_due_service_268967"),
        "minimum_product_on_due_service": _metric(
            payload, "minimum_product_on_due_service"
        ),
        "on_due_qty_268091": _quantity(payload, "on_due_qty_268091"),
        "demand_qty_268091": _quantity(payload, "demand_qty_268091"),
        "on_due_qty_268967": _quantity(payload, "on_due_qty_268967"),
        "demand_qty_268967": _quantity(payload, "demand_qty_268967"),
        "graph_sha256": payload["graph_sha256"],
        "evidence_signature": payload["evidence_signature"],
        "valid": payload["valid"],
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
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


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
        "range": max(values) - min(values),
    }


def _observed_id(left_service: float, right_service: float) -> str:
    left = f"{100.0 * left_service:.1f}".replace(".", "p")
    right = f"{100.0 * right_service:.1f}".replace(".", "p")
    return f"op_observed_pf268091_{left}pct__pf268967_{right}pct"


def finalize(
    plan: PrevalidationPlan,
    output_dir: Path,
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected_keys = {
        _case_key(point_id, seed) for point_id in POINT_IDS for seed in CAMPAIGN_SEEDS
    }
    if set(evidence) != expected_keys:
        raise ValueError(
            f"Prevalidation incomplete: {len(evidence)}/{len(expected_keys)} cases"
        )
    records: list[dict[str, Any]] = []
    for point_id in POINT_IDS:
        point = _point(plan, point_id)
        rows = [evidence[_case_key(point_id, seed)] for seed in CAMPAIGN_SEEDS]
        metrics = {
            field: _stats([_metric(row, field) for row in rows])
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
                "minimum_product_on_due_service",
            )
        }
        target = float(point["target_service"])
        on_due_left = sum(_quantity(row, "on_due_qty_268091") for row in rows)
        demand_left = sum(_quantity(row, "demand_qty_268091") for row in rows)
        on_due_right = sum(_quantity(row, "on_due_qty_268967") for row in rows)
        demand_right = sum(_quantity(row, "demand_qty_268967") for row in rows)
        if demand_left <= 0.0 or demand_right <= 0.0:
            raise ValueError(f"Prevalidation has zero finished-product demand: {point_id}")
        pooled_left = on_due_left / demand_left
        pooled_right = on_due_right / demand_right
        pooled_global = (on_due_left + on_due_right) / (demand_left + demand_right)
        global_target_within_tolerance = (
            abs(pooled_global - target) <= TARGET_TOLERANCE + 1e-12
        )
        products_balanced = (
            abs(pooled_left - pooled_right) <= PRODUCT_BALANCE_LIMIT + 1e-12
        )
        no_saturated_degraded_product = point_id == "op_100" or (
            max(pooled_left, pooled_right) < 1.0 - 1e-12
        )
        target_attained = (
            global_target_within_tolerance
            and no_saturated_degraded_product
        )
        fallback_state_eligible = (
            point_id == "op_80"
            and LOW_STATE_FALLBACK_RANGE[0]
            <= pooled_global
            <= LOW_STATE_FALLBACK_RANGE[1]
            and no_saturated_degraded_product
        )
        campaign_state_accepted = target_attained or fallback_state_eligible
        if target_attained:
            published_label = point["operating_point_label"]
        elif fallback_state_eligible:
            published_label = (
                "Etat bas obtenu; service global agrege "
                f"{100.0 * pooled_global:.1f}% "
                "(cible 80% non atteinte)"
            )
        else:
            published_label = (
                "Etat degrade obtenu; services agreges "
                f"PF268091={100.0 * pooled_left:.1f}%, "
                f"PF268967={100.0 * pooled_right:.1f}%, "
                f"global={100.0 * pooled_global:.1f}% "
                f"(cible globale {100.0 * target:.0f}% non atteinte)"
            )
        records.append(
            {
                "operating_point_id": point_id,
                "target_service": target,
                "replication_count": len(CAMPAIGN_SEEDS),
                "metrics": metrics,
                "pooled_ratio_of_sums": {
                    "system_on_due_service": pooled_global,
                    "on_due_service_268091": pooled_left,
                    "on_due_service_268967": pooled_right,
                },
                "product_service_gap_pp": 100.0 * abs(pooled_left - pooled_right),
                "global_target_within_tolerance": global_target_within_tolerance,
                "products_balanced_within_5pp": products_balanced,
                "no_degraded_product_saturated_at_100pct": (
                    no_saturated_degraded_product
                ),
                "strict_target_attained": target_attained,
                "fallback_state_eligible": fallback_state_eligible,
                "campaign_state_accepted": campaign_state_accepted,
                "target_attained": target_attained,
                "published_state_id": (
                    point_id
                    if campaign_state_accepted
                    else _observed_id(pooled_left, pooled_right)
                ),
                "published_state_label": published_label,
            }
        )
    pooled_by_id = {
        row["operating_point_id"]: row["pooled_ratio_of_sums"][
            "system_on_due_service"
        ]
        for row in records
    }
    per_seed_order_count = sum(
        _metric(evidence[_case_key("op_100", seed)], "system_on_due_service")
        > _metric(evidence[_case_key("op_93", seed)], "system_on_due_service")
        > _metric(evidence[_case_key("op_80", seed)], "system_on_due_service")
        for seed in CAMPAIGN_SEEDS
    )
    pooled_state_order_attained = (
        pooled_by_id["op_100"] > pooled_by_id["op_93"] > pooled_by_id["op_80"]
    )
    state_order_attained = pooled_state_order_attained and per_seed_order_count >= 4
    if not state_order_attained:
        for record in records:
            if record["operating_point_id"] == "op_100":
                continue
            pooled = record["pooled_ratio_of_sums"]
            record["target_attained"] = False
            record["campaign_state_accepted"] = False
            record["published_state_id"] = _observed_id(
                pooled["on_due_service_268091"],
                pooled["on_due_service_268967"],
            )
            record["published_state_label"] = (
                "Etat simule obtenu mais ordre des niveaux de service instable; "
                f"global={100.0 * pooled['system_on_due_service']:.1f}%"
            )
    all_targets_attained = (
        all(row["strict_target_attained"] for row in records)
        and state_order_attained
    )
    all_attained = (
        all(row["campaign_state_accepted"] for row in records)
        and state_order_attained
    )
    fallback_low_state_used = any(
        row["fallback_state_eligible"] and not row["strict_target_attained"]
        for row in records
    )
    summary: dict[str, Any] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": (
            "prevalidated_3_states_5_seeds"
            if all_targets_attained
            else "prevalidated_3_states_with_observed_low_state_5_seeds"
            if all_attained
            else "target_not_attained_state_renamed_or_refinement_required"
        ),
        "plan_signature": plan.manifest["plan_signature"],
        "calibration_seed": CALIBRATION_SEED,
        "campaign_prevalidation_seeds": list(CAMPAIGN_SEEDS),
        "calibration_seed_mixed_with_prevalidation": False,
        "case_count": len(evidence),
        "target_tolerance": TARGET_TOLERANCE,
        "acceptance_statistic": "pooled_global_ratio_of_sums",
        "product_gap_reporting_threshold_pp": 100.0 * PRODUCT_BALANCE_LIMIT,
        "product_gap_is_acceptance_criterion": False,
        "pooled_state_order_attained": pooled_state_order_attained,
        "per_seed_strict_state_order_count": per_seed_order_count,
        "per_seed_strict_state_order_required": 4,
        "state_order_attained": state_order_attained,
        "service_evaluation_window": SERVICE_EVALUATION_WINDOW,
        "state_records": records,
        "all_targets_attained": all_targets_attained,
        "all_campaign_states_accepted": all_attained,
        "fallback_low_state_used": fallback_low_state_used,
        "low_state_fallback_range": list(LOW_STATE_FALLBACK_RANGE),
        "quality_branch_included": False,
        "supplier_availability_incident_included": False,
        "acute_incident_included": False,
        "state_dependent_risk_included": False,
        "simulation_hypotheses_not_observed_performance": True,
        "business_limit": (
            "Five seeds provide an early stability check only. The 30-seed "
            "baseline stage must still confirm the labels and detect a possible "
            "lot-sizing transition before supplier incidents are ranked."
        ),
    }
    summary["summary_signature"] = _stable_sha256(summary)
    _write_json(output_dir / "prevalidation_summary.json", summary)

    source = copy.deepcopy(plan.source_points)
    source.pop("artifact_signature", None)
    source["prevalidation"] = {
        "summary": str((output_dir / "prevalidation_summary.json").resolve()),
        "summary_signature": summary["summary_signature"],
        "seeds": list(CAMPAIGN_SEEDS),
        "acceptance_statistic": "pooled_global_ratio_of_sums",
    }
    by_id = {row["operating_point_id"]: row for row in records}
    for point in source["operating_points"]:
        record = by_id[point["operating_point_id"]]
        point["screening_system_service"] = record["pooled_ratio_of_sums"][
            "system_on_due_service"
        ]
        point["screening_product_268091_service"] = record[
            "pooled_ratio_of_sums"
        ]["on_due_service_268091"]
        point["screening_product_268967_service"] = record[
            "pooled_ratio_of_sums"
        ]["on_due_service_268967"]
        point["prevalidation_target_attained"] = record["target_attained"]
        point["prevalidation_state_accepted"] = record["campaign_state_accepted"]
        if record["fallback_state_eligible"] and not record["strict_target_attained"]:
            point["original_target_service"] = point["target_service"]
            point["target_service"] = record["pooled_ratio_of_sums"][
                "system_on_due_service"
            ]
            point["operating_point_label"] = record["published_state_label"]
            point["state_label_is_observed_prevalidation_value"] = True
        elif not record["campaign_state_accepted"]:
            point["operating_point_id"] = record["published_state_id"]
            point["operating_point_label"] = record["published_state_label"]

    if all_attained:
        source["schema_version"] = VALIDATED_POINTS_SCHEMA_VERSION
        source["status"] = summary["status"]
        destination = output_dir / "validated_campaign_operating_points.json"
    else:
        source["schema_version"] = OBSERVED_POINTS_SCHEMA_VERSION
        source["status"] = "observed_states_not_strict_campaign_input"
        source["strict_v2_campaign_compatible"] = False
        source["local_refinement_required"] = True
        destination = output_dir / "observed_operating_points.json"
    source["artifact_signature"] = _stable_sha256(source)
    _write_json(destination, source)
    return {
        "summary": summary,
        "validated_campaign_operating_points": source if all_attained else None,
        "observed_operating_points": None if all_attained else source,
    }


def _write_progress(
    output_dir: Path,
    plan: PrevalidationPlan,
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    status: str,
    error: str = "",
) -> None:
    rows = sorted(
        (_result_row(row) for row in evidence.values()),
        key=lambda row: (POINT_IDS.index(row["operating_point_id"]), row["seed"]),
    )
    _write_csv(output_dir / "prevalidation_metrics.csv", rows, RESULT_FIELDS)
    _write_json(
        output_dir / "progress.json",
        {
            "schema_version": f"{SCHEMA_VERSION}.progress",
            "plan_signature": plan.manifest["plan_signature"],
            "status": status,
            "completed_case_count": len(evidence),
            "expected_case_count": 15,
            "error": error,
            "updated_at_utc": _now(),
        },
    )


def _register_run(plan: PrevalidationPlan, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    expected = {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "seeds": list(CAMPAIGN_SEEDS),
        "expected_case_count": 15,
        "stage": "baseline_only",
    }
    if path.is_file():
        if _read_json(path) != expected:
            raise ValueError("Prevalidation output belongs to another run")
        return
    if any(output_dir.iterdir()):
        raise ValueError("Refusing a non-empty unregistered output directory")
    _write_json(path, expected)


@contextmanager
def _exclusive_lock(output_dir: Path):
    path = output_dir / ".prevalidation.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another prevalidation owns {path}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} utc={_now()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def run(
    plan_dir: Path,
    output_dir: Path,
    *,
    workers: int = 1,
    executor: BaselineExecutor = execute_baseline,
) -> dict[str, Any]:
    """Execute or resume the exact 15-case baseline prevalidation."""

    if workers not in (1, 2):
        raise ValueError("Use one or two workers to bound memory use")
    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    _register_run(plan, output_dir)
    with _exclusive_lock(output_dir):
        evidence = _load_evidence(plan, output_dir)
        try:
            missing = [
                case
                for case in plan.manifest["cases"]
                if str(case["case_key"]) not in evidence
            ]

            def execute_one(case: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
                key = str(case["case_key"])
                point_id = str(case["operating_point_id"])
                seed = int(case["seed"])
                point = _point(plan, point_id)
                source = executor(point_id, point, plan, output_dir, seed)
                candidate, adapter = _adapter(point, plan)
                coarse._validate_evidence(source, candidate, adapter, seed)
                payload = _wrap_evidence(
                    plan=plan,
                    point_id=point_id,
                    point=point,
                    seed=seed,
                    source=source,
                )
                _validate_evidence(payload, plan)
                return key, payload

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(execute_one, case): case for case in missing}
                for future in as_completed(futures):
                    key, payload = future.result()
                    path = _evidence_path(output_dir, key)
                    if path.exists():
                        raise FileExistsError(
                            f"Refusing to overwrite evidence: {path}"
                        )
                    _write_json(path, payload)
                    evidence[key] = payload
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
    parser.add_argument("--source-points", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        path = prepare_plan(args.plan_dir, source_points_path=args.source_points)
        print(f"15-case prevalidation plan prepared; no simulation executed: {path}")
    elif args.mode == "validate":
        plan = validate_plan(args.plan_dir)
        print(
            f"Valid prevalidation plan: {plan.manifest['expected_case_count']} "
            f"baselines, seeds={plan.manifest['seeds']}"
        )
    elif args.mode == "run":
        print(
            json.dumps(
                run(args.plan_dir, args.output_dir, workers=args.workers), indent=2
            )
        )
    else:
        print(
            json.dumps(
                finalize_existing(args.plan_dir, args.output_dir), indent=2
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
