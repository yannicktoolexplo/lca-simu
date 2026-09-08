#!/usr/bin/env python3
"""Build the accepted V7 bridge consumed by the mature incident campaign.

V7 alone authorizes the fixed three-state model from 150 seed blocks / 450
fresh physical runs. The mature campaign keeps its 30-repetition design: its
90 compact baseline traces are derived, without engine reruns, from the first
30 V7 blocks frozen before execution. V4/V5/V6 simulation evidence is never
used; V6 remains design provenance inside the signed V7 plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import Any
from uuid import uuid4

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v4 as bridge_v4_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as campaign_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


BRIDGE_SCHEMA_VERSION = campaign_contract.BRIDGE_SCHEMA_VERSION
BRIDGE_ACCEPTED_STATUS = campaign_contract.BRIDGE_ACCEPTED_STATUS
BRIDGE_FIELDS = bridge_v4_contract.BRIDGE_FIELDS
SOURCE_REFERENCE_FIELDS = bridge_v4_contract.SOURCE_REFERENCE_FIELDS
POINT_FIELDS = bridge_v4_contract.POINT_FIELDS
TRACE_INDEX_FIELDS = bridge_v4_contract.TRACE_INDEX_FIELDS
CAMPAIGN_SEEDS = trace_package.CAMPAIGN_SEEDS
EXPECTED_CAMPAIGN_BASELINE_CASES = trace_package.EXPECTED_TRACE_COUNT
EXPECTED_V7_VALIDATION_CASES = 450
EXPECTED_V7_VALIDATION_SEEDS = 150
COMPATIBILITY_COHORT_KEY = "campaign_repetitions_reuse_v4_fresh_holdout"
DESCRIPTIVE_BOOTSTRAP_REPLICATES = 10_000
DESCRIPTIVE_BOOTSTRAP_SEED = 2_026_090_517
EXPECTED_V4_BRIDGE_CONTRACT_SHA256 = (
    "c4456f00224610c161187643892576a3ed4aa76cb9f55b471d9063a508d75da9"
)

INTERPRETATION = (
    "Hypothèses simulées uniquement. V7 autorise le triplet fixe sur 150 "
    "graines et 450 simulations physiques nouvelles. Les 90 traces utilisées "
    "par la campagne sont dérivées des 30 premières graines V7, figées avant "
    "exécution, et servent seulement à apparier situation normale et incident. "
    "V4, V5 et V6 ne fournissent aucune preuve de simulation à cette campagne."
)


class V7BridgeError(ValueError):
    """The accepted V7 source or its derived trace package is inconsistent."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V7BridgeError(f"Cannot read signed JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V7BridgeError(f"Signed JSON must contain an object: {path}")
    return payload


def _verify_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if not campaign_contract.is_sha256(
        signature
    ) or signature != campaign_contract.stable_sha256(unsigned):
        raise V7BridgeError(f"Invalid {label} signature")
    return signature


def _validate_frozen_compatibility_contract() -> None:
    path = Path(bridge_v4_contract.__file__).resolve()
    digest = campaign_contract.sha256_file(path)
    if digest != EXPECTED_V4_BRIDGE_CONTRACT_SHA256:
        raise V7BridgeError(
            f"Frozen V4 bridge compatibility contract changed: {digest}"
        )


def _validate_v7_acceptance(
    plan_dir: Path, run_dir: Path
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[tuple[str, int], dict[str, Any]]]:
    _validate_frozen_compatibility_contract()
    trace_package.validate_frozen_v7_protocol()
    plan = protocol_v7.validate_plan(
        plan_dir.resolve(), allow_test_source=False, verify_runtime=True
    )
    result = protocol_v7.validate_result(
        plan.plan_dir, run_dir.resolve(), test_only=False
    )
    evidence = protocol_v7.validated_evidence(
        plan.plan_dir, run_dir.resolve(), test_only=False
    )
    result_path = run_dir.resolve() / "validation_result.json"
    if not result_path.is_file() or _read_json(result_path) != result:
        raise V7BridgeError("V7 validation result is absent or not reproduced")
    _verify_signature(result, "result_signature", "V7 validation result")
    run_manifest = _read_json(run_dir.resolve() / "run_manifest.json")
    _verify_signature(run_manifest, "run_signature", "V7 run manifest")
    checks = result.get("primary_checks")
    if (
        result.get("schema_version") != protocol_v7.RESULT_SCHEMA_VERSION
        or result.get("status") != protocol_v7.ACCEPTED_STATUS
        or result.get("accepted") is not True
        or result.get("publishable") is not True
        or result.get("execution_mode") != protocol_v7.OFFICIAL_EXECUTION_MODE
        or result.get("plan_signature") != plan.manifest["plan_signature"]
        or result.get("run_signature") != run_manifest["run_signature"]
        or int(result.get("validation_seed_count") or -1)
        != EXPECTED_V7_VALIDATION_SEEDS
        or int(result.get("fresh_physical_evidence_case_count") or -1)
        != EXPECTED_V7_VALIDATION_CASES
        or len(evidence) != EXPECTED_V7_VALIDATION_CASES
        or result.get("v5_v6_acceptance_evidence_reused") is not False
        or result.get("v6_holdout_reused_as_v7_acceptance_evidence") is not False
        or result.get("retuning_after_any_v7_result") is not False
        or not isinstance(checks, Mapping)
        or not checks
        or not all(value is True for value in checks.values())
        or result.get("fixed_triplet")
        != [candidate.payload() for candidate in protocol_v7.FIXED_TRIPLET]
    ):
        raise V7BridgeError(
            "Only the accepted official 450-case V7 result may authorize"
        )
    return plan, run_manifest, dict(result), evidence


def _service(row: Mapping[str, Any], suffix: str) -> float:
    metrics = row["metrics"]
    demand_key = "demand_qty_global" if suffix == "global" else f"demand_qty_{suffix}"
    due_key = "on_due_qty_global" if suffix == "global" else f"on_due_qty_{suffix}"
    demand = float(metrics[demand_key])
    due = float(metrics[due_key])
    if (
        not math.isfinite(demand)
        or not math.isfinite(due)
        or demand <= 0
        or not 0 <= due <= demand + 1e-6
    ):
        raise V7BridgeError("Invalid V7 campaign-baseline service quantities")
    return due / demand


def _ratio_of_sums(rows: Sequence[Mapping[str, Any]], suffix: str) -> float:
    demand_key = "demand_qty_global" if suffix == "global" else f"demand_qty_{suffix}"
    due_key = "on_due_qty_global" if suffix == "global" else f"on_due_qty_{suffix}"
    demand = sum(float(row["metrics"][demand_key]) for row in rows)
    due = sum(float(row["metrics"][due_key]) for row in rows)
    if demand <= 0:
        raise V7BridgeError("Zero pooled V7 campaign-baseline demand")
    return due / demand


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered or not 0 <= probability <= 1:
        raise V7BridgeError("Invalid descriptive quantile input")
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _campaign_baseline_statistics(
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Describe the fixed 30-block campaign subset; never re-decide V7."""

    rows: dict[str, list[Mapping[str, Any]]] = {
        candidate.target_group: [
            evidence[(candidate.key, seed)] for seed in CAMPAIGN_SEEDS
        ]
        for candidate in protocol_v7.FIXED_TRIPLET
    }
    summaries: dict[str, Any] = {}
    for group in campaign_contract.OPERATING_POINT_IDS:
        by_measure = {
            suffix: [_service(row, suffix) for row in rows[group]]
            for suffix in ("global", "268091", "268967")
        }
        summaries[group] = {
            "pooled": {
                "system_on_due_service": _ratio_of_sums(rows[group], "global"),
                "on_due_service_268091": _ratio_of_sums(rows[group], "268091"),
                "on_due_service_268967": _ratio_of_sums(rows[group], "268967"),
            },
            "median": {
                "system_on_due_service": median(by_measure["global"]),
                "on_due_service_268091": median(by_measure["268091"]),
                "on_due_service_268967": median(by_measure["268967"]),
            },
            "minimum": {
                "system_on_due_service": min(by_measure["global"]),
                "on_due_service_268091": min(by_measure["268091"]),
                "on_due_service_268967": min(by_measure["268967"]),
            },
            "maximum": {
                "system_on_due_service": max(by_measure["global"]),
                "on_due_service_268091": max(by_measure["268091"]),
                "on_due_service_268967": max(by_measure["268967"]),
            },
            "campaign_seed_count": len(CAMPAIGN_SEEDS),
            "acceptance_gate": False,
            "interpretation": (
                "Sous-ensemble descriptif apparié de campagne; décision V7 "
                "sur 150 graines."
            ),
        }
    generator = random.Random(DESCRIPTIVE_BOOTSTRAP_SEED)
    draws = {group: [] for group in campaign_contract.OPERATING_POINT_IDS}
    for _replicate in range(DESCRIPTIVE_BOOTSTRAP_REPLICATES):
        indexes = [generator.randrange(len(CAMPAIGN_SEEDS)) for _seed in CAMPAIGN_SEEDS]
        for group in campaign_contract.OPERATING_POINT_IDS:
            selected = [rows[group][index] for index in indexes]
            draws[group].append(_ratio_of_sums(selected, "global"))
    bootstrap = {
        "contract": {
            "method": "paired_whole_seed_block_percentile_bootstrap",
            "replicates": DESCRIPTIVE_BOOTSTRAP_REPLICATES,
            "seed": DESCRIPTIVE_BOOTSTRAP_SEED,
            "confidence": 0.95,
            "acceptance_gate": False,
            "subset": ("first_30_v7_validation_seed_blocks_frozen_before_execution"),
        },
        "intervals": {
            group: {
                "ci95_low": _quantile(values, 0.025),
                "ci95_high": _quantile(values, 0.975),
            }
            for group, values in draws.items()
        },
    }
    return summaries, bootstrap


def _operating_points(plan: Any, summaries: Mapping[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "op_100": "État de référence proche de 100 %",
        "op_93": "État dégradé proche de 93 %",
        "op_80": "État dégradé proche de 80 %",
    }
    by_group = {candidate.target_group: candidate for candidate in plan.candidates}
    points: list[dict[str, Any]] = []
    for point_id in campaign_contract.OPERATING_POINT_IDS:
        candidate = by_group[point_id]
        summary = summaries[point_id]
        pooled = summary["pooled"]
        inventory = plan.manifest["inventory"][candidate.key]
        graph = (plan.plan_dir / inventory["graph_path"]).resolve()
        if (
            not graph.is_file()
            or campaign_contract.sha256_file(graph) != inventory["graph_sha256"]
        ):
            raise V7BridgeError(f"V7 graph changed: {candidate.key}")
        degradation = {
            "offset_days_268091": float(candidate.offset_days_268091),
            "offset_days_268967": float(candidate.offset_days_268967),
        }
        points.append(
            {
                "operating_point_id": point_id,
                "operating_point_label": labels[point_id],
                "candidate_key": candidate.key,
                "candidate_id": candidate.candidate_id,
                "target_service": protocol_v7.TARGETS[point_id],
                "calibration_pooled_service": float(pooled["system_on_due_service"]),
                "calibration_product_268091_service": float(
                    pooled["on_due_service_268091"]
                ),
                "calibration_product_268967_service": float(
                    pooled["on_due_service_268967"]
                ),
                "offset_days_268091": degradation["offset_days_268091"],
                "offset_days_268967": degradation["offset_days_268967"],
                "degradation_family": (
                    "baseline"
                    if point_id == "op_100"
                    else "balanced_product_supplier_planned_lead"
                ),
                "degradation_value": degradation,
                "degradation_unit": (
                    "planned_lead_days_added_by_finished_product_feed"
                ),
                "graph": str(graph),
                "graph_sha256": inventory["graph_sha256"],
                "supplier_floors": "",
                "supplier_floors_sha256": "",
                "factory_capacities": "",
                "factory_capacities_sha256": "",
                "holdout_seed_count": len(CAMPAIGN_SEEDS),
                "holdout_state_summary": summary,
            }
        )
    return points


def build_bridge_payload(
    v7_plan_dir: Path, v7_run_dir: Path, trace_package_dir: Path
) -> dict[str, Any]:
    plan, run_manifest, result, evidence = _validate_v7_acceptance(
        v7_plan_dir, v7_run_dir
    )
    package = trace_package.validate_package(
        trace_package_dir.resolve(),
        plan_dir=plan.plan_dir,
        run_dir=v7_run_dir.resolve(),
    )
    if (
        package.get("v4_v5_v6_simulation_evidence_reused") is not False
        or package.get("campaign_cohort", {}).get("seeds") != list(CAMPAIGN_SEEDS)
        or package.get("campaign_cohort", {}).get(
            "same_seeds_required_for_baseline_and_incidents"
        )
        is not True
        or package.get("v7_source", {}).get("result_signature")
        != result["result_signature"]
    ):
        raise V7BridgeError("V7 trace package source/cohort changed")
    package_dir = trace_package_dir.resolve()
    selection_path = package_dir / "campaign_trace_selection.json"
    selection = _read_json(selection_path)
    _verify_signature(selection, "selection_signature", "V7 trace selection")
    traces = [dict(row) for row in package["trace_index"]]
    if len(traces) != EXPECTED_CAMPAIGN_BASELINE_CASES:
        raise V7BridgeError("V7 bridge requires exactly 90 derived traces")
    summaries, descriptive_bootstrap = _campaign_baseline_statistics(evidence)
    lanes = package["lane_contract"]["lanes"]
    plan_path = plan.plan_dir / "protocol_manifest.json"
    package_manifest_path = package_dir / "trace_package_manifest.json"
    result_path = v7_run_dir.resolve() / "validation_result.json"
    producer = Path(__file__).resolve()
    validation_protocol = {
        "role": "sole_scientific_authorization_for_fixed_triplet",
        "plan_dir": str(plan.plan_dir),
        "plan_manifest": str(plan_path.resolve()),
        "plan_manifest_sha256": campaign_contract.sha256_file(plan_path),
        "plan_signature": plan.manifest["plan_signature"],
        "run_dir": str(v7_run_dir.resolve()),
        "run_manifest": str(v7_run_dir.resolve() / "run_manifest.json"),
        "run_manifest_sha256": campaign_contract.sha256_file(
            v7_run_dir.resolve() / "run_manifest.json"
        ),
        "run_signature": run_manifest["run_signature"],
        "result": str(result_path),
        "result_sha256": campaign_contract.sha256_file(result_path),
        "result_signature": result["result_signature"],
        "status": result["status"],
        "accepted": True,
        "validation_seed_count": EXPECTED_V7_VALIDATION_SEEDS,
        "fresh_physical_evidence_case_count": EXPECTED_V7_VALIDATION_CASES,
        "evidence_signature_set_sha256": result["evidence_signature_set_sha256"],
        "prior_version_simulation_evidence_reused": False,
        "retuning_after_any_v7_result": False,
    }
    baseline_contract = {
        "role": "campaign_initial_conditions_and_pairing_only",
        "selection_rule": "first_30_seed_blocks_in_signed_v7_plan_order",
        "selection_frozen_before_v7_execution": True,
        "seeds": list(CAMPAIGN_SEEDS),
        "seed_count": len(CAMPAIGN_SEEDS),
        "physical_case_count": EXPECTED_CAMPAIGN_BASELINE_CASES,
        "shipment_trace_count": EXPECTED_CAMPAIGN_BASELINE_CASES,
        "subset_of_v7_validation": True,
        "same_seeds_required_for_baseline_and_incidents": True,
        "used_for_operating_point_retuning": False,
        "acceptance_gate": False,
        "trace_package_signature": package["run_signature"],
    }
    unsigned: dict[str, Any] = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "status": BRIDGE_ACCEPTED_STATUS,
        "interpretation": INTERPRETATION,
        "producer": {
            "path": str(producer),
            "sha256": campaign_contract.sha256_file(producer),
        },
        "source": {
            "plan_dir": str(plan.plan_dir),
            "plan_manifest": str(plan_path.resolve()),
            "plan_manifest_sha256": campaign_contract.sha256_file(plan_path),
            "plan_signature": plan.manifest["plan_signature"],
            "run_dir": str(package_dir),
            "run_manifest": str(package_manifest_path),
            "run_manifest_sha256": campaign_contract.sha256_file(package_manifest_path),
            "run_signature": package["run_signature"],
            "development_selection": str(selection_path.resolve()),
            "development_selection_sha256": campaign_contract.sha256_file(
                selection_path
            ),
            "development_selection_signature": selection["selection_signature"],
            "holdout_result": str(result_path),
            "holdout_result_sha256": campaign_contract.sha256_file(result_path),
            "holdout_signature": result["result_signature"],
            "holdout_evidence_index_sha256": result["evidence_signature_set_sha256"],
        },
        "source_hashes": {
            "v7_protocol_driver_sha256": campaign_contract.sha256_file(
                Path(protocol_v7.__file__).resolve()
            ),
            "v7_trace_package_driver_sha256": campaign_contract.sha256_file(
                Path(trace_package.__file__).resolve()
            ),
            "engine_sha256": plan.manifest["execution_contract"]["engine"]["sha256"],
            "engine_profile_sha256": plan.manifest["execution_contract"][
                "engine_profile"
            ]["sha256"],
            "v7_bridge_driver_sha256": campaign_contract.sha256_file(producer),
        },
        # Exact three-key legacy envelope required by the mature finalizer.
        "cohorts": {
            COMPATIBILITY_COHORT_KEY: list(CAMPAIGN_SEEDS),
            "incident_window_design_reserved": [campaign_contract.INCIDENT_DESIGN_SEED],
            "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
        },
        "operating_points": _operating_points(plan, summaries),
        "lane_contract": {
            "count": len(lanes),
            "lanes": lanes,
            "sha256": campaign_contract.lane_contract_sha256(lanes),
        },
        "holdout_contract": {
            "status": protocol_v7.ACCEPTED_STATUS,
            "accepted": True,
            "execution_mode": protocol_v7.OFFICIAL_EXECUTION_MODE,
            "publishable": True,
            # Compatibility counts consumed by the 3x30 campaign binding.
            "seed_count": len(CAMPAIGN_SEEDS),
            "evidence_case_count": EXPECTED_CAMPAIGN_BASELINE_CASES,
            "retuning_after_holdout": False,
            "state_summaries": summaries,
            "paired_bootstrap_global_descriptive_only": descriptive_bootstrap,
            "legacy_evidence_case_count_semantics": (
                "derived campaign-baseline traces; V7 acceptance uses 450 cases"
            ),
            "validation_protocol": validation_protocol,
            "campaign_baseline_contract": baseline_contract,
        },
        "trace_contract": {
            "schema_version": campaign_contract.TRACE_SCHEMA_VERSION,
            "compression": campaign_contract.TRACE_COMPRESSION,
            "fields": list(campaign_contract.TRACE_ROW_FIELDS),
            "filter_contract": campaign_contract.trace_filter_contract(lanes),
            "expected_trace_count": EXPECTED_CAMPAIGN_BASELINE_CASES,
            "raw_engine_runs_reused": EXPECTED_CAMPAIGN_BASELINE_CASES,
            "raw_engine_reruns_required": 0,
            "source": "accepted_v7_retained_shipment_snapshots",
        },
        "trace_index": traces,
        "trace_index_signature": campaign_contract.stable_sha256(traces),
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "simulation_hypotheses_not_observed_performance": True,
        "retuning_after_holdout": False,
    }
    return {
        **unsigned,
        "artifact_signature": campaign_contract.stable_sha256(unsigned),
    }


def validate_bridge(path: Path, *, revalidate_source: bool = True) -> dict[str, Any]:
    _validate_frozen_compatibility_contract()
    path = path.resolve()
    payload = _read_json(path)
    if set(payload) != BRIDGE_FIELDS:
        raise V7BridgeError("Validated V7 bridge fields changed")
    _verify_signature(payload, "artifact_signature", "V7 campaign bridge")
    if (
        payload.get("schema_version") != BRIDGE_SCHEMA_VERSION
        or payload.get("status") != BRIDGE_ACCEPTED_STATUS
        or payload.get("interpretation") != INTERPRETATION
        or payload.get("quality_branch_included") is not False
        or payload.get("supplier_state_dependent_risks_enabled") is not False
        or payload.get("acute_incident_included_in_operating_point") is not False
        or payload.get("simulation_hypotheses_not_observed_performance") is not True
        or payload.get("retuning_after_holdout") is not False
    ):
        raise V7BridgeError("V7 bridge status or scientific limits changed")
    source = payload.get("source")
    hashes = payload.get("source_hashes")
    points = payload.get("operating_points")
    traces = payload.get("trace_index")
    expected_hash_fields = {
        "v7_protocol_driver_sha256",
        "v7_trace_package_driver_sha256",
        "engine_sha256",
        "engine_profile_sha256",
        "v7_bridge_driver_sha256",
    }
    if (
        not isinstance(source, Mapping)
        or set(source) != SOURCE_REFERENCE_FIELDS
        or not isinstance(hashes, Mapping)
        or set(hashes) != expected_hash_fields
        or hashes.get("v7_protocol_driver_sha256")
        != trace_package.EXPECTED_V7_PROTOCOL_SHA256
        or not isinstance(points, list)
        or len(points) != 3
        or any(
            not isinstance(point, Mapping) or set(point) != POINT_FIELDS
            for point in points
        )
        or [point.get("operating_point_id") for point in points]
        != list(campaign_contract.OPERATING_POINT_IDS)
        or not isinstance(traces, list)
        or len(traces) != EXPECTED_CAMPAIGN_BASELINE_CASES
        or any(
            not isinstance(row, Mapping) or set(row) != TRACE_INDEX_FIELDS
            for row in traces
        )
        or payload.get("trace_index_signature")
        != campaign_contract.stable_sha256(traces)
    ):
        raise V7BridgeError("V7 bridge compatibility structure changed")
    if payload.get("cohorts") != {
        COMPATIBILITY_COHORT_KEY: list(CAMPAIGN_SEEDS),
        "incident_window_design_reserved": [campaign_contract.INCIDENT_DESIGN_SEED],
        "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
    }:
        raise V7BridgeError("V7 campaign cohort changed")
    holdout = payload.get("holdout_contract") or {}
    validation = holdout.get("validation_protocol") or {}
    baseline = holdout.get("campaign_baseline_contract") or {}
    if (
        holdout.get("status") != protocol_v7.ACCEPTED_STATUS
        or holdout.get("accepted") is not True
        or holdout.get("publishable") is not True
        or holdout.get("retuning_after_holdout") is not False
        or holdout.get("evidence_case_count") != EXPECTED_CAMPAIGN_BASELINE_CASES
        or validation.get("role") != "sole_scientific_authorization_for_fixed_triplet"
        or validation.get("accepted") is not True
        or validation.get("validation_seed_count") != EXPECTED_V7_VALIDATION_SEEDS
        or validation.get("fresh_physical_evidence_case_count")
        != EXPECTED_V7_VALIDATION_CASES
        or validation.get("prior_version_simulation_evidence_reused") is not False
        or baseline.get("role") != "campaign_initial_conditions_and_pairing_only"
        or baseline.get("seeds") != list(CAMPAIGN_SEEDS)
        or baseline.get("subset_of_v7_validation") is not True
        or baseline.get("same_seeds_required_for_baseline_and_incidents") is not True
        or baseline.get("used_for_operating_point_retuning") is not False
        or baseline.get("acceptance_gate") is not False
    ):
        raise V7BridgeError("V7 authorization / campaign-baseline separation changed")
    producer_path = Path(__file__).resolve()
    if payload.get("producer") != {
        "path": str(producer_path),
        "sha256": campaign_contract.sha256_file(producer_path),
    }:
        raise V7BridgeError("V7 bridge producer provenance changed")
    if revalidate_source:
        rebuilt = build_bridge_payload(
            Path(str(validation["plan_dir"])),
            Path(str(validation["run_dir"])),
            Path(str(source["run_dir"])),
        )
        if rebuilt != payload:
            raise V7BridgeError("V7 bridge differs from its signed sources")
    return payload


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _publish_bridge_exclusive(path: Path, payload: Mapping[str, Any]) -> str:
    """Publish complete bytes atomically without replacing a concurrent result."""

    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.building-{uuid4().hex}")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def write_bridge(
    v7_plan_dir: Path, v7_run_dir: Path, trace_package_dir: Path, output: Path
) -> Path:
    output = output.resolve()
    protected = (
        Path(__file__).resolve().parents[3],
        v7_plan_dir.resolve(),
        v7_run_dir.resolve(),
        trace_package_dir.resolve(),
    )
    if any(_paths_overlap(output, root) for root in protected):
        raise V7BridgeError("V7 bridge output overlaps a protected source")
    payload = build_bridge_payload(v7_plan_dir, v7_run_dir, trace_package_dir)
    if output.exists():
        if validate_bridge(output) != payload:
            raise V7BridgeError("Existing V7 bridge differs; refusing overwrite")
        return output
    published_digest = ""
    try:
        published_digest = _publish_bridge_exclusive(output, payload)
    except FileExistsError:
        if validate_bridge(output) != payload:
            raise V7BridgeError("A concurrent V7 bridge differs; refusing overwrite")
        return output
    try:
        validate_bridge(output)
    except BaseException:
        if (
            output.is_file()
            and campaign_contract.sha256_file(output) == published_digest
        ):
            output.unlink()
        raise
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--v7-plan-dir", type=Path, required=True)
    build.add_argument("--v7-run-dir", type=Path, required=True)
    build.add_argument("--trace-package-dir", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--path", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        result: Any = write_bridge(
            args.v7_plan_dir,
            args.v7_run_dir,
            args.trace_package_dir,
            args.output,
        )
    else:
        result = validate_bridge(args.path)["artifact_signature"]
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
