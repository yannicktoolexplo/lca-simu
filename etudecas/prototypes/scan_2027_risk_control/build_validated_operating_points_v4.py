#!/usr/bin/env python3
"""Build the signed V4 operating-point bridge consumed by the full campaign.

The bridge is deliberately additive.  It revalidates the complete official V4
fresh holdout, including all 90 compact shipment traces, and projects only the
three accepted states plus immutable provenance.  It never runs the engine and
never accepts an injected/test-only V4 run.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as refinement_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as contract,
)


BRIDGE_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "interpretation",
        "producer",
        "source",
        "source_hashes",
        "cohorts",
        "operating_points",
        "lane_contract",
        "holdout_contract",
        "trace_contract",
        "trace_index",
        "trace_index_signature",
        "quality_branch_included",
        "supplier_state_dependent_risks_enabled",
        "acute_incident_included_in_operating_point",
        "simulation_hypotheses_not_observed_performance",
        "retuning_after_holdout",
        "artifact_signature",
    }
)
SOURCE_REFERENCE_FIELDS = frozenset(
    {
        "plan_dir",
        "plan_manifest",
        "plan_manifest_sha256",
        "plan_signature",
        "run_dir",
        "run_manifest",
        "run_manifest_sha256",
        "run_signature",
        "development_selection",
        "development_selection_sha256",
        "development_selection_signature",
        "holdout_result",
        "holdout_result_sha256",
        "holdout_signature",
        "holdout_evidence_index_sha256",
    }
)
POINT_FIELDS = frozenset(
    {
        "operating_point_id",
        "operating_point_label",
        "candidate_key",
        "candidate_id",
        "target_service",
        "calibration_pooled_service",
        "calibration_product_268091_service",
        "calibration_product_268967_service",
        "offset_days_268091",
        "offset_days_268967",
        "degradation_family",
        "degradation_value",
        "degradation_unit",
        "graph",
        "graph_sha256",
        "supplier_floors",
        "supplier_floors_sha256",
        "factory_capacities",
        "factory_capacities_sha256",
        "holdout_seed_count",
        "holdout_state_summary",
    }
)
TRACE_INDEX_FIELDS = frozenset(
    {
        "operating_point_id",
        "candidate_key",
        "candidate_id",
        "seed",
        "evidence_relative_path",
        "evidence_sha256",
        "evidence_signature",
        "shipment_trace",
    }
)
INTERPRETATION = (
    "Simulation hypotheses only; the accepted V4 states are not observed supplier "
    "performance and the retained traces do not estimate incident probability."
)


class V4BridgeError(ValueError):
    """Raised when the accepted V4 source cannot authorize a campaign."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V4BridgeError(f"Cannot read signed JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V4BridgeError(f"Signed JSON must contain an object: {path}")
    return payload


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.building-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"Temporary bridge output already exists: {temporary}")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _verify_self_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if not contract.is_sha256(signature) or signature != contract.stable_sha256(unsigned):
        raise V4BridgeError(f"Invalid {label} signature")
    return signature


def _artifact_reference(path: Path, signature: str) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": contract.sha256_file(path.resolve()),
        "signature": signature,
    }


def _recompute_holdout_result(
    plan: Any,
    run_dir: Path,
    selection: Mapping[str, Any],
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    """Recompute the V4 holdout finalization without writing into its run."""

    chosen = dict(selection.get("selected_candidate_keys") or {})
    if set(chosen) != set(contract.OPERATING_POINT_IDS):
        raise V4BridgeError("V4 development selection does not contain three states")
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    try:
        ordered_keys = [chosen[group] for group in refinement_v4.TARGETS]
    except KeyError as exc:
        raise V4BridgeError("V4 selection references an unknown state") from exc
    refinement_v4._validate_paired_demand(  # noqa: SLF001 - signed producer contract
        evidence, ordered_keys, contract.CAMPAIGN_SEEDS
    )
    rows_by_group = {
        group: [evidence[(key, seed)] for seed in contract.CAMPAIGN_SEEDS]
        for group, key in chosen.items()
    }
    summaries = {
        group: refinement_v4._candidate_summary(  # noqa: SLF001
            by_key[key], rows_by_group[group], False
        )
        for group, key in chosen.items()
    }
    bootstrap = refinement_v4._paired_bootstrap_global(rows_by_group)  # noqa: SLF001
    pooled, joint, pf967 = refinement_v4._ordered_pair(  # noqa: SLF001
        summaries["op_100"], summaries["op_93"], summaries["op_80"]
    )
    accepted = (
        all(summary["admissible_individually"] for summary in summaries.values())
        and pooled
        and joint >= refinement_v4.MIN_ORDERED_SEEDS
    )
    unsigned = {
        "schema_version": refinement_v4.HOLDOUT_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "development_selection_signature": selection["selection_signature"],
        "status": (
            "holdout_validated_30_fresh_seeds"
            if accepted
            else "holdout_rejected_no_retuning"
        ),
        "holdout_seeds": list(contract.CAMPAIGN_SEEDS),
        "holdout_evidence_case_count": len(evidence),
        "execution_mode": refinement_v4.OFFICIAL_EXECUTION_MODE,
        "publishable": True,
        "holdout_evidence_signature_set_sha256": contract.stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "selected_candidate_keys": chosen,
        "state_summaries": summaries,
        "paired_bootstrap_global_descriptive_only": {
            "contract": plan.manifest["holdout_contract"]["bootstrap"],
            "intervals": bootstrap,
        },
        "product_gap_warning_above_5pp_by_state": {
            group: summary["product_gap_warning"]
            for group, summary in summaries.items()
        },
        "pooled_strict_order": pooled,
        "same_seed_joint_strict_order_count": joint,
        "same_seed_pf268967_strict_order_count": pf967,
        "accepted": accepted,
        "retuning_after_holdout": False,
        "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
    }
    return {**unsigned, "holdout_signature": contract.stable_sha256(unsigned)}


def _load_official_source(
    plan_dir: Path, run_dir: Path
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[tuple[str, int], dict[str, Any]]]:
    plan = refinement_v4.validate_plan(plan_dir.resolve())
    if tuple(refinement_v4.EXPECTED_HOLDOUT_SEEDS) != contract.CAMPAIGN_SEEDS:
        raise V4BridgeError("V4 producer/campaign fresh seed contracts differ")
    if refinement_v4.INCIDENT_DESIGN_SEED != contract.INCIDENT_DESIGN_SEED:
        raise V4BridgeError("V4 producer/campaign incident design seeds differ")
    driver = Path(refinement_v4.__file__).resolve()
    if plan.manifest.get("source_hashes", {}).get(
        "v4_driver_sha256"
    ) != contract.sha256_file(driver):
        raise V4BridgeError("The frozen V4 plan does not pin the current V4 producer")
    run_dir = run_dir.resolve()
    execution_mode = refinement_v4._registered_execution_mode(  # noqa: SLF001
        plan, run_dir
    )
    if execution_mode != refinement_v4.OFFICIAL_EXECUTION_MODE:
        raise V4BridgeError("A test-only V4 run can never authorize a full campaign")
    run_manifest = _read_json(run_dir / "run_manifest.json")
    expected_run = refinement_v4._run_manifest(  # noqa: SLF001
        plan, refinement_v4.OFFICIAL_EXECUTION_MODE
    )
    if run_manifest != expected_run or run_manifest.get("publishable") is not True:
        raise V4BridgeError("V4 official run registration changed")
    selection = refinement_v4._load_development_selection(plan, run_dir)  # noqa: SLF001
    if (
        selection.get("execution_mode") != refinement_v4.OFFICIAL_EXECUTION_MODE
        or selection.get("publishable") is not True
    ):
        raise V4BridgeError("V4 development selection is not publishable")
    evidence = refinement_v4._load_stage_evidence(  # noqa: SLF001
        plan, run_dir, "holdout"
    )
    if len(evidence) != 3 * len(contract.CAMPAIGN_SEEDS):
        raise V4BridgeError("The V4 bridge requires exactly 90 holdout proofs")
    holdout_path = run_dir / "holdout_result.json"
    holdout = _read_json(holdout_path)
    _verify_self_signature(holdout, "holdout_signature", "V4 holdout")
    recomputed = _recompute_holdout_result(plan, run_dir, selection, evidence)
    if holdout != recomputed:
        raise V4BridgeError("V4 holdout is not reproducible from its 90 proofs")
    if (
        holdout.get("status") != "holdout_validated_30_fresh_seeds"
        or holdout.get("accepted") is not True
        or holdout.get("retuning_after_holdout") is not False
        or holdout.get("publishable") is not True
        or holdout.get("execution_mode") != refinement_v4.OFFICIAL_EXECUTION_MODE
    ):
        raise V4BridgeError("Only an accepted official fresh V4 holdout is usable")
    return plan, run_manifest, selection, evidence


def _lane_scope(plan: Any) -> list[dict[str, Any]]:
    source_manifest_path = Path(
        str(plan.manifest["source"]["campaign_manifest"]["path"])
    ).resolve()
    source_manifest = _read_json(source_manifest_path)
    raw = source_manifest.get("lanes")
    if not isinstance(raw, list):
        raise V4BridgeError("V4 source campaign has no signed lane scope")
    try:
        return contract.lane_contract_payload(raw)
    except contract.V4CampaignContractError as exc:
        raise V4BridgeError(str(exc)) from exc


def _trace_index(
    *,
    plan: Any,
    run_dir: Path,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    lanes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    lane_ids = [row["lane_id"] for row in lanes]
    lane_sha = contract.lane_contract_sha256(lanes)
    filter_contract = contract.trace_filter_contract(lanes)
    entries: list[dict[str, Any]] = []
    for candidate in sorted(plan.candidates, key=lambda item: item.target_group):
        if candidate.target_group not in contract.OPERATING_POINT_IDS:
            continue
        for seed in contract.CAMPAIGN_SEEDS:
            row = evidence.get((candidate.key, seed))
            if row is None:
                continue
            trace_reference = row.get("shipment_trace")
            if not isinstance(trace_reference, Mapping):
                raise V4BridgeError(
                    f"Missing compact shipment trace for {candidate.key}/seed={seed}"
                )
            expected = {
                "plan_signature": plan.manifest["plan_signature"],
                "candidate_key": candidate.key,
                "candidate_id": candidate.candidate_id,
                "target_group": candidate.target_group,
                "seed": seed,
                "graph_sha256": plan.manifest["inventory"][candidate.key][
                    "graph_sha256"
                ],
                "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
                "simulation_days": 720,
                "lane_contract_sha256": lane_sha,
                "filter_contract": filter_contract,
            }
            try:
                reference, _payload = contract.validate_trace_reference(
                    trace_reference,
                    run_dir=run_dir,
                    expected=expected,
                    allowed_lane_ids=lane_ids,
                )
            except contract.V4CampaignContractError as exc:
                raise V4BridgeError(
                    f"Invalid compact trace for {candidate.key}/seed={seed}: {exc}"
                ) from exc
            evidence_path = refinement_v4._evidence_path(  # noqa: SLF001
                run_dir, "holdout", candidate.key, seed
            ).resolve()
            entries.append(
                {
                    "operating_point_id": candidate.target_group,
                    "candidate_key": candidate.key,
                    "candidate_id": candidate.candidate_id,
                    "seed": seed,
                    "evidence_relative_path": evidence_path.relative_to(
                        run_dir
                    ).as_posix(),
                    "evidence_sha256": contract.sha256_file(evidence_path),
                    "evidence_signature": row["evidence_signature"],
                    "shipment_trace": reference,
                }
            )
    entries.sort(key=lambda item: (item["operating_point_id"], item["seed"]))
    expected_keys = {
        (point, seed)
        for point in contract.OPERATING_POINT_IDS
        for seed in contract.CAMPAIGN_SEEDS
    }
    actual_keys = {(row["operating_point_id"], row["seed"]) for row in entries}
    if len(entries) != 90 or actual_keys != expected_keys:
        raise V4BridgeError("The bridge requires one valid trace for every state/seed")
    return entries


def _operating_points(
    plan: Any, selection: Mapping[str, Any], holdout: Mapping[str, Any]
) -> list[dict[str, Any]]:
    candidate_by_key = {candidate.key: candidate for candidate in plan.candidates}
    selected = dict(selection["selected_candidate_keys"])
    labels = {
        "op_100": "État de référence proche de 100 %",
        "op_93": "État dégradé proche de 93 %",
        "op_80": "État dégradé proche de 80 %",
    }
    result: list[dict[str, Any]] = []
    for point_id in contract.OPERATING_POINT_IDS:
        candidate = candidate_by_key[selected[point_id]]
        summary = holdout["state_summaries"][point_id]
        inventory = plan.manifest["inventory"][candidate.key]
        graph = (plan.plan_dir / inventory["graph_path"]).resolve()
        if not graph.is_file() or contract.sha256_file(graph) != inventory["graph_sha256"]:
            raise V4BridgeError(f"Selected V4 graph changed: {candidate.key}")
        pooled = summary.get("pooled") or {}
        required_services = (
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        )
        if any(
            not isinstance(pooled.get(field), (int, float))
            or isinstance(pooled.get(field), bool)
            or not math.isfinite(float(pooled[field]))
            for field in required_services
        ):
            raise V4BridgeError(f"Invalid V4 state summary: {point_id}")
        degradation = {
            "offset_days_268091": float(candidate.offset_days_268091),
            "offset_days_268967": float(candidate.offset_days_268967),
        }
        result.append(
            {
                "operating_point_id": point_id,
                "operating_point_label": labels[point_id],
                "candidate_key": candidate.key,
                "candidate_id": candidate.candidate_id,
                "target_service": refinement_v4.TARGETS[point_id],
                "calibration_pooled_service": float(
                    pooled["system_on_due_service"]
                ),
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
                "degradation_unit": "planned_lead_days_added_by_finished_product_feed",
                "graph": str(graph),
                "graph_sha256": inventory["graph_sha256"],
                "supplier_floors": "",
                "supplier_floors_sha256": "",
                "factory_capacities": "",
                "factory_capacities_sha256": "",
                "holdout_seed_count": len(contract.CAMPAIGN_SEEDS),
                "holdout_state_summary": summary,
            }
        )
    return result


def build_bridge_payload(plan_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Revalidate V4 and return a deterministic bridge payload without writing."""

    plan, run_manifest, selection, evidence = _load_official_source(plan_dir, run_dir)
    run_dir = run_dir.resolve()
    holdout_path = run_dir / "holdout_result.json"
    holdout = _read_json(holdout_path)
    lanes = _lane_scope(plan)
    trace_index = _trace_index(
        plan=plan, run_dir=run_dir, evidence=evidence, lanes=lanes
    )
    plan_manifest_path = (plan.plan_dir / "refinement_plan.json").resolve()
    run_manifest_path = (run_dir / "run_manifest.json").resolve()
    selection_path = (run_dir / "development_selection.json").resolve()
    evidence_projection = [
        {
            "relative_path": row["evidence_relative_path"],
            "sha256": row["evidence_sha256"],
            "signature": row["evidence_signature"],
        }
        for row in trace_index
    ]
    driver_path = Path(refinement_v4.__file__).resolve()
    producer_path = Path(__file__).resolve()
    unsigned: dict[str, Any] = {
        "schema_version": contract.BRIDGE_SCHEMA_VERSION,
        "status": contract.BRIDGE_ACCEPTED_STATUS,
        "interpretation": INTERPRETATION,
        "producer": {
            "path": str(producer_path),
            "sha256": contract.sha256_file(producer_path),
        },
        "source": {
            "plan_dir": str(plan.plan_dir.resolve()),
            "plan_manifest": str(plan_manifest_path),
            "plan_manifest_sha256": contract.sha256_file(plan_manifest_path),
            "plan_signature": plan.manifest["plan_signature"],
            "run_dir": str(run_dir),
            "run_manifest": str(run_manifest_path),
            "run_manifest_sha256": contract.sha256_file(run_manifest_path),
            "run_signature": run_manifest["run_signature"],
            "development_selection": str(selection_path),
            "development_selection_sha256": contract.sha256_file(selection_path),
            "development_selection_signature": selection["selection_signature"],
            "holdout_result": str(holdout_path.resolve()),
            "holdout_result_sha256": contract.sha256_file(holdout_path),
            "holdout_signature": holdout["holdout_signature"],
            "holdout_evidence_index_sha256": contract.stable_sha256(
                evidence_projection
            ),
        },
        "source_hashes": {
            "v4_driver_sha256": contract.sha256_file(driver_path),
            "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
            "engine_profile_sha256": plan.manifest["source_hashes"][
                "engine_profile_sha256"
            ],
        },
        "cohorts": {
            "campaign_repetitions_reuse_v4_fresh_holdout": list(
                contract.CAMPAIGN_SEEDS
            ),
            "incident_window_design_reserved": [contract.INCIDENT_DESIGN_SEED],
            "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
        },
        "operating_points": _operating_points(plan, selection, holdout),
        "lane_contract": {
            "count": len(lanes),
            "lanes": lanes,
            "sha256": contract.lane_contract_sha256(lanes),
        },
        "holdout_contract": {
            "status": holdout["status"],
            "accepted": True,
            "execution_mode": refinement_v4.OFFICIAL_EXECUTION_MODE,
            "publishable": True,
            "seed_count": len(contract.CAMPAIGN_SEEDS),
            "evidence_case_count": len(evidence),
            "retuning_after_holdout": False,
            "state_summaries": holdout["state_summaries"],
            "paired_bootstrap_global_descriptive_only": holdout[
                "paired_bootstrap_global_descriptive_only"
            ],
        },
        "trace_contract": {
            "schema_version": contract.TRACE_SCHEMA_VERSION,
            "compression": contract.TRACE_COMPRESSION,
            "fields": list(contract.TRACE_ROW_FIELDS),
            "filter_contract": contract.trace_filter_contract(lanes),
            "expected_trace_count": 90,
            "raw_engine_runs_reused": 90,
            "raw_engine_reruns_required": 0,
        },
        "trace_index": trace_index,
        "trace_index_signature": contract.stable_sha256(trace_index),
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "simulation_hypotheses_not_observed_performance": True,
        "retuning_after_holdout": False,
    }
    return {**unsigned, "artifact_signature": contract.stable_sha256(unsigned)}


def validate_bridge(path: Path, *, revalidate_source: bool = True) -> dict[str, Any]:
    """Validate a bridge intrinsically and, by default, against all V4 proofs."""

    path = path.resolve()
    payload = _read_json(path)
    if set(payload) != BRIDGE_FIELDS:
        raise V4BridgeError("Validated V4 bridge fields changed")
    _verify_self_signature(payload, "artifact_signature", "V4 bridge")
    if (
        payload.get("schema_version") != contract.BRIDGE_SCHEMA_VERSION
        or payload.get("status") != contract.BRIDGE_ACCEPTED_STATUS
        or payload.get("interpretation") != INTERPRETATION
        or payload.get("quality_branch_included") is not False
        or payload.get("supplier_state_dependent_risks_enabled") is not False
        or payload.get("acute_incident_included_in_operating_point") is not False
        or payload.get("simulation_hypotheses_not_observed_performance") is not True
        or payload.get("retuning_after_holdout") is not False
    ):
        raise V4BridgeError("Validated V4 bridge status or interpretation changed")
    source = payload.get("source")
    if not isinstance(source, Mapping) or set(source) != SOURCE_REFERENCE_FIELDS:
        raise V4BridgeError("Validated V4 bridge source references changed")
    points = payload.get("operating_points")
    if not isinstance(points, list) or len(points) != 3:
        raise V4BridgeError("Validated V4 bridge must contain exactly three states")
    if any(not isinstance(point, Mapping) or set(point) != POINT_FIELDS for point in points):
        raise V4BridgeError("Validated V4 bridge operating-point fields changed")
    if [point["operating_point_id"] for point in points] != list(
        contract.OPERATING_POINT_IDS
    ):
        raise V4BridgeError("Validated V4 bridge state ordering changed")
    traces = payload.get("trace_index")
    if not isinstance(traces, list) or len(traces) != 90:
        raise V4BridgeError("Validated V4 bridge requires exactly 90 trace references")
    if any(not isinstance(row, Mapping) or set(row) != TRACE_INDEX_FIELDS for row in traces):
        raise V4BridgeError("Validated V4 bridge trace-index fields changed")
    if payload.get("trace_index_signature") != contract.stable_sha256(traces):
        raise V4BridgeError("Validated V4 bridge trace-index signature changed")
    producer = payload.get("producer") or {}
    if (
        set(producer) != {"path", "sha256"}
        or Path(str(producer.get("path") or "")).resolve() != Path(__file__).resolve()
        or producer.get("sha256") != contract.sha256_file(Path(__file__).resolve())
    ):
        raise V4BridgeError("Validated V4 bridge producer changed")
    if revalidate_source:
        rebuilt = build_bridge_payload(
            Path(str(source["plan_dir"])), Path(str(source["run_dir"]))
        )
        if rebuilt != payload:
            raise V4BridgeError("Validated V4 bridge differs from current signed source")
    return payload


def write_bridge(plan_dir: Path, run_dir: Path, output: Path) -> Path:
    output = output.resolve()
    payload = build_bridge_payload(plan_dir, run_dir)
    if output.exists():
        existing = validate_bridge(output)
        if existing != payload:
            raise V4BridgeError("Existing V4 bridge differs; refusing overwrite")
        return output
    _write_json_atomic(output, payload)
    validate_bridge(output)
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Revalidate V4 and write the bridge")
    build.add_argument("--plan-dir", type=Path, required=True)
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="Revalidate an existing bridge")
    validate.add_argument("--path", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        print(write_bridge(args.plan_dir, args.run_dir, args.output))
    else:
        payload = validate_bridge(args.path)
        print(payload["artifact_signature"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
