#!/usr/bin/env python3
"""Build the signed V5 operating-point bridge used by the V4 incident engine.

The V5 calibration is additive: it follows the official V4 development no-go,
uses a cohort that V4 never opened, and may authorize the downstream campaign
only after a reproducible 3 x 30 holdout acceptance.  This bridge executes no
simulation.  It reopens all ninety V5 proofs and compact shipment traces and
projects them into the stable incident-campaign envelope.

The outer ``BRIDGE_SCHEMA_VERSION`` intentionally stays equal to the existing
V4 campaign bridge schema.  This is a compatibility envelope, not a claim that
the calibration source is V4: the signed ``source`` and ``source_hashes`` fields
identify the V5 plan, selection, holdout, driver, and run unambiguously.
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
    build_validated_operating_points_v4 as bridge_v4_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as campaign_contract,
)


BRIDGE_SCHEMA_VERSION = campaign_contract.BRIDGE_SCHEMA_VERSION
BRIDGE_ACCEPTED_STATUS = campaign_contract.BRIDGE_ACCEPTED_STATUS
BRIDGE_FIELDS = bridge_v4_contract.BRIDGE_FIELDS
SOURCE_REFERENCE_FIELDS = bridge_v4_contract.SOURCE_REFERENCE_FIELDS
POINT_FIELDS = bridge_v4_contract.POINT_FIELDS
TRACE_INDEX_FIELDS = bridge_v4_contract.TRACE_INDEX_FIELDS

INTERPRETATION = (
    "Simulation hypotheses only; the accepted V5 states come from thirty "
    "carried-forward but previously unseen seeds. They are not observed supplier "
    "performance and do not estimate incident probability."
)
ACCEPTED_HOLDOUT_STATUS = "holdout_validated_30_carried_unseen_seeds"
COMPATIBILITY_COHORT_KEY = "campaign_repetitions_reuse_v4_fresh_holdout"


class V5BridgeError(ValueError):
    """The signed V5 source cannot authorize the downstream campaign."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V5BridgeError(f"Cannot read signed JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V5BridgeError(f"Signed JSON must contain an object: {path}")
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
    if not campaign_contract.is_sha256(
        signature
    ) or signature != campaign_contract.stable_sha256(unsigned):
        raise V5BridgeError(f"Invalid {label} signature")
    return signature


def _load_official_source(
    plan_dir: Path, run_dir: Path
) -> tuple[
    Any,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[tuple[str, int], dict[str, Any]],
]:
    """Recompute the official V5 acceptance from its exact ninety proofs."""

    plan = refinement_v5.validate_plan(
        plan_dir.resolve(), verify_runtime_dependencies=True
    )
    if tuple(refinement_v5.EXPECTED_HOLDOUT_SEEDS) != tuple(
        campaign_contract.CAMPAIGN_SEEDS
    ):
        raise V5BridgeError("V5 producer/campaign seed contracts differ")
    if refinement_v5.INCIDENT_DESIGN_SEED != campaign_contract.INCIDENT_DESIGN_SEED:
        raise V5BridgeError("V5 producer/campaign design seeds differ")
    driver = Path(refinement_v5.__file__).resolve()
    if plan.manifest.get("source_hashes", {}).get(
        "v5_driver_sha256"
    ) != campaign_contract.sha256_file(driver):
        raise V5BridgeError("The V5 plan does not pin the current V5 producer")

    run_dir = run_dir.resolve()
    execution_mode = refinement_v5._registered_execution_mode(  # noqa: SLF001
        plan, run_dir
    )
    if execution_mode != refinement_v5.OFFICIAL_EXECUTION_MODE:
        raise V5BridgeError("A test-only V5 run can never authorize a full campaign")
    run_manifest = _read_json(run_dir / "run_manifest.json")
    expected_run = refinement_v5._run_manifest(  # noqa: SLF001
        plan, refinement_v5.OFFICIAL_EXECUTION_MODE
    )
    if run_manifest != expected_run or run_manifest.get("publishable") is not True:
        raise V5BridgeError("V5 official run registration changed")

    selection = refinement_v5._load_development_selection(  # noqa: SLF001
        plan, run_dir
    )
    if (
        selection.get("schema_version") != refinement_v5.SELECTION_SCHEMA_VERSION
        or selection.get("status") != "development_selected_pending_fresh_holdout"
        or selection.get("execution_mode") != refinement_v5.OFFICIAL_EXECUTION_MODE
        or selection.get("publishable") is not True
        or selection.get("holdout_cases_read") != 0
    ):
        raise V5BridgeError("V5 development selection is not publishable")

    evidence = refinement_v5._load_stage_evidence(  # noqa: SLF001
        plan, run_dir, "holdout"
    )
    if len(evidence) != 3 * len(campaign_contract.CAMPAIGN_SEEDS):
        raise V5BridgeError("The V5 bridge requires exactly 90 holdout proofs")
    holdout_path = run_dir / "holdout_result.json"
    holdout = _read_json(holdout_path)
    _verify_self_signature(holdout, "holdout_signature", "V5 holdout")
    recomputed = refinement_v5._build_holdout_result(  # noqa: SLF001
        plan,
        evidence,
        selection,
        execution_mode=refinement_v5.OFFICIAL_EXECUTION_MODE,
    )
    if holdout != recomputed:
        raise V5BridgeError("V5 holdout is not reproducible from its 90 proofs")
    if (
        holdout.get("schema_version") != refinement_v5.HOLDOUT_SCHEMA_VERSION
        or holdout.get("status") != ACCEPTED_HOLDOUT_STATUS
        or holdout.get("accepted") is not True
        or holdout.get("retuning_after_holdout") is not False
        or holdout.get("publishable") is not True
        or holdout.get("execution_mode") != refinement_v5.OFFICIAL_EXECUTION_MODE
    ):
        raise V5BridgeError("Only an accepted official unseen V5 holdout is usable")
    return plan, run_manifest, selection, holdout, evidence


def _lane_scope(plan: Any) -> list[dict[str, Any]]:
    source_manifest_path = Path(
        str(plan.manifest["source"]["campaign_manifest"]["path"])
    ).resolve()
    source_manifest = _read_json(source_manifest_path)
    raw = source_manifest.get("lanes")
    if not isinstance(raw, list):
        raise V5BridgeError("V5 source campaign has no signed lane scope")
    try:
        return campaign_contract.lane_contract_payload(raw)
    except campaign_contract.V4CampaignContractError as exc:
        raise V5BridgeError(str(exc)) from exc


def _trace_index(
    *,
    plan: Any,
    run_dir: Path,
    selection: Mapping[str, Any],
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    lanes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    lane_ids = [str(row["lane_id"]) for row in lanes]
    lane_sha = campaign_contract.lane_contract_sha256(lanes)
    filter_contract = campaign_contract.trace_filter_contract(lanes)
    selected = dict(selection["selected_candidate_keys"])
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    entries: list[dict[str, Any]] = []
    for point_id in campaign_contract.OPERATING_POINT_IDS:
        candidate = by_key[selected[point_id]]
        for seed in campaign_contract.CAMPAIGN_SEEDS:
            row = evidence.get((candidate.key, seed))
            if row is None:
                raise V5BridgeError(f"Missing V5 proof for {candidate.key}/seed={seed}")
            trace_reference = row.get("shipment_trace")
            if not isinstance(trace_reference, Mapping):
                raise V5BridgeError(
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
                "simulation_days": refinement_v5.SERVICE_DAYS,
                "lane_contract_sha256": lane_sha,
                "filter_contract": filter_contract,
            }
            try:
                reference, _payload = campaign_contract.validate_trace_reference(
                    trace_reference,
                    run_dir=run_dir,
                    expected=expected,
                    allowed_lane_ids=lane_ids,
                )
            except campaign_contract.V4CampaignContractError as exc:
                raise V5BridgeError(
                    f"Invalid V5 trace for {candidate.key}/seed={seed}: {exc}"
                ) from exc
            evidence_path = refinement_v5._evidence_path(  # noqa: SLF001
                run_dir, "holdout", candidate.key, seed
            ).resolve()
            entries.append(
                {
                    "operating_point_id": point_id,
                    "candidate_key": candidate.key,
                    "candidate_id": candidate.candidate_id,
                    "seed": seed,
                    "evidence_relative_path": evidence_path.relative_to(
                        run_dir
                    ).as_posix(),
                    "evidence_sha256": campaign_contract.sha256_file(evidence_path),
                    "evidence_signature": row["evidence_signature"],
                    "shipment_trace": reference,
                }
            )
    entries.sort(key=lambda item: (item["operating_point_id"], item["seed"]))
    expected_keys = {
        (point, seed)
        for point in campaign_contract.OPERATING_POINT_IDS
        for seed in campaign_contract.CAMPAIGN_SEEDS
    }
    if (
        len(entries) != 90
        or {(row["operating_point_id"], row["seed"]) for row in entries}
        != expected_keys
    ):
        raise V5BridgeError("The V5 bridge requires one trace for every state/seed")
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
    for point_id in campaign_contract.OPERATING_POINT_IDS:
        candidate = candidate_by_key[selected[point_id]]
        summary = holdout["state_summaries"][point_id]
        inventory = plan.manifest["inventory"][candidate.key]
        graph = (plan.plan_dir / inventory["graph_path"]).resolve()
        if (
            not graph.is_file()
            or campaign_contract.sha256_file(graph) != inventory["graph_sha256"]
        ):
            raise V5BridgeError(f"Selected V5 graph changed: {candidate.key}")
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
            raise V5BridgeError(f"Invalid V5 state summary: {point_id}")
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
                "target_service": refinement_v5.TARGETS[point_id],
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
                "degradation_unit": "planned_lead_days_added_by_finished_product_feed",
                "graph": str(graph),
                "graph_sha256": inventory["graph_sha256"],
                "supplier_floors": "",
                "supplier_floors_sha256": "",
                "factory_capacities": "",
                "factory_capacities_sha256": "",
                "holdout_seed_count": len(campaign_contract.CAMPAIGN_SEEDS),
                "holdout_state_summary": summary,
            }
        )
    return result


def build_bridge_payload(plan_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Revalidate V5 and return a deterministic bridge without writing."""

    plan, run_manifest, selection, holdout, evidence = _load_official_source(
        plan_dir, run_dir
    )
    run_dir = run_dir.resolve()
    lanes = _lane_scope(plan)
    trace_index = _trace_index(
        plan=plan,
        run_dir=run_dir,
        selection=selection,
        evidence=evidence,
        lanes=lanes,
    )
    plan_manifest_path = (plan.plan_dir / "refinement_plan.json").resolve()
    run_manifest_path = (run_dir / "run_manifest.json").resolve()
    selection_path = (run_dir / "development_selection.json").resolve()
    holdout_path = (run_dir / "holdout_result.json").resolve()
    evidence_projection = [
        {
            "relative_path": row["evidence_relative_path"],
            "sha256": row["evidence_sha256"],
            "signature": row["evidence_signature"],
        }
        for row in trace_index
    ]
    driver_path = Path(refinement_v5.__file__).resolve()
    producer_path = Path(__file__).resolve()
    unsigned: dict[str, Any] = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "status": BRIDGE_ACCEPTED_STATUS,
        "interpretation": INTERPRETATION,
        "producer": {
            "path": str(producer_path),
            "sha256": campaign_contract.sha256_file(producer_path),
        },
        "source": {
            "plan_dir": str(plan.plan_dir.resolve()),
            "plan_manifest": str(plan_manifest_path),
            "plan_manifest_sha256": campaign_contract.sha256_file(plan_manifest_path),
            "plan_signature": plan.manifest["plan_signature"],
            "run_dir": str(run_dir),
            "run_manifest": str(run_manifest_path),
            "run_manifest_sha256": campaign_contract.sha256_file(run_manifest_path),
            "run_signature": run_manifest["run_signature"],
            "development_selection": str(selection_path),
            "development_selection_sha256": campaign_contract.sha256_file(
                selection_path
            ),
            "development_selection_signature": selection["selection_signature"],
            "holdout_result": str(holdout_path),
            "holdout_result_sha256": campaign_contract.sha256_file(holdout_path),
            "holdout_signature": holdout["holdout_signature"],
            "holdout_evidence_index_sha256": campaign_contract.stable_sha256(
                evidence_projection
            ),
        },
        "source_hashes": {
            "v5_driver_sha256": campaign_contract.sha256_file(driver_path),
            "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
            "engine_profile_sha256": plan.manifest["source_hashes"][
                "engine_profile_sha256"
            ],
        },
        # The key name is retained solely because the unchanged 3330-row incident
        # engine consumes this compatibility envelope.  The referenced evidence
        # is the V5 holdout and was never read by V4.
        "cohorts": {
            COMPATIBILITY_COHORT_KEY: list(campaign_contract.CAMPAIGN_SEEDS),
            "incident_window_design_reserved": [campaign_contract.INCIDENT_DESIGN_SEED],
            "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
        },
        "operating_points": _operating_points(plan, selection, holdout),
        "lane_contract": {
            "count": len(lanes),
            "lanes": lanes,
            "sha256": campaign_contract.lane_contract_sha256(lanes),
        },
        "holdout_contract": {
            "status": holdout["status"],
            "accepted": True,
            "execution_mode": refinement_v5.OFFICIAL_EXECUTION_MODE,
            "publishable": True,
            "seed_count": len(campaign_contract.CAMPAIGN_SEEDS),
            "evidence_case_count": len(evidence),
            "retuning_after_holdout": False,
            "state_summaries": holdout["state_summaries"],
            "paired_bootstrap_global_descriptive_only": holdout[
                "paired_bootstrap_global_descriptive_only"
            ],
        },
        "trace_contract": {
            "schema_version": campaign_contract.TRACE_SCHEMA_VERSION,
            "compression": campaign_contract.TRACE_COMPRESSION,
            "fields": list(campaign_contract.TRACE_ROW_FIELDS),
            "filter_contract": campaign_contract.trace_filter_contract(lanes),
            "expected_trace_count": 90,
            "raw_engine_runs_reused": 90,
            "raw_engine_reruns_required": 0,
        },
        "trace_index": trace_index,
        "trace_index_signature": campaign_contract.stable_sha256(trace_index),
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
    """Validate the bridge and, by default, reopen all signed V5 evidence."""

    path = path.resolve()
    payload = _read_json(path)
    if set(payload) != BRIDGE_FIELDS:
        raise V5BridgeError("Validated V5 bridge fields changed")
    _verify_self_signature(payload, "artifact_signature", "V5 bridge")
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
        raise V5BridgeError("Validated V5 bridge status or interpretation changed")
    source = payload.get("source")
    if not isinstance(source, Mapping) or set(source) != SOURCE_REFERENCE_FIELDS:
        raise V5BridgeError("Validated V5 bridge source references changed")
    source_hashes = payload.get("source_hashes")
    if not isinstance(source_hashes, Mapping) or set(source_hashes) != {
        "v5_driver_sha256",
        "engine_sha256",
        "engine_profile_sha256",
    }:
        raise V5BridgeError("Validated V5 bridge source hashes changed")
    points = payload.get("operating_points")
    if not isinstance(points, list) or len(points) != 3:
        raise V5BridgeError("Validated V5 bridge must contain exactly three states")
    if any(
        not isinstance(point, Mapping) or set(point) != POINT_FIELDS for point in points
    ):
        raise V5BridgeError("Validated V5 bridge operating-point fields changed")
    if [point["operating_point_id"] for point in points] != list(
        campaign_contract.OPERATING_POINT_IDS
    ):
        raise V5BridgeError("Validated V5 bridge state ordering changed")
    traces = payload.get("trace_index")
    if not isinstance(traces, list) or len(traces) != 90:
        raise V5BridgeError("Validated V5 bridge requires exactly 90 traces")
    if any(
        not isinstance(row, Mapping) or set(row) != TRACE_INDEX_FIELDS for row in traces
    ):
        raise V5BridgeError("Validated V5 bridge trace-index fields changed")
    if payload.get("trace_index_signature") != campaign_contract.stable_sha256(traces):
        raise V5BridgeError("Validated V5 bridge trace-index signature changed")
    expected_cohorts = {
        COMPATIBILITY_COHORT_KEY: list(campaign_contract.CAMPAIGN_SEEDS),
        "incident_window_design_reserved": [campaign_contract.INCIDENT_DESIGN_SEED],
        "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
    }
    if payload.get("cohorts") != expected_cohorts:
        raise V5BridgeError("Validated V5 bridge cohort contract changed")
    holdout_contract = payload.get("holdout_contract")
    if (
        not isinstance(holdout_contract, Mapping)
        or holdout_contract.get("status") != ACCEPTED_HOLDOUT_STATUS
        or holdout_contract.get("accepted") is not True
        or holdout_contract.get("publishable") is not True
        or holdout_contract.get("retuning_after_holdout") is not False
        or holdout_contract.get("evidence_case_count") != 90
    ):
        raise V5BridgeError("Validated V5 holdout contract changed")
    producer = payload.get("producer") or {}
    if (
        set(producer) != {"path", "sha256"}
        or Path(str(producer.get("path") or "")).resolve() != Path(__file__).resolve()
        or producer.get("sha256")
        != campaign_contract.sha256_file(Path(__file__).resolve())
    ):
        raise V5BridgeError("Validated V5 bridge producer changed")
    if revalidate_source:
        rebuilt = build_bridge_payload(
            Path(str(source["plan_dir"])), Path(str(source["run_dir"]))
        )
        if rebuilt != payload:
            raise V5BridgeError("Validated V5 bridge differs from signed source")
    return payload


def write_bridge(plan_dir: Path, run_dir: Path, output: Path) -> Path:
    output = output.resolve()
    payload = build_bridge_payload(plan_dir, run_dir)
    if output.exists():
        existing = validate_bridge(output)
        if existing != payload:
            raise V5BridgeError("Existing V5 bridge differs; refusing overwrite")
        return output
    _write_json_atomic(output, payload)
    validate_bridge(output)
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Revalidate V5 and write bridge")
    build.add_argument("--plan-dir", type=Path, required=True)
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate", help="Revalidate bridge")
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
