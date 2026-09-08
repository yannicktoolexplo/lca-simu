#!/usr/bin/env python3
"""Derive the mature campaign's 90 compact traces from accepted V7 evidence.

The first thirty V7 seed blocks are frozen as the incident-campaign cohort
before V7 execution.  This postprocessor reads their already retained complete
supplier-shipment CSV snapshots, validates every V7 evidence/bundle hash, and
writes a separate compact trace package.  It never runs the simulation engine
and never writes inside the immutable V7 plan or run.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v6 as development_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as campaign_contract,
)


SCHEMA_VERSION = "etudecas.supplier_v7_campaign_trace_package.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selection"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.trace_evidence"
CAMPAIGN_SEED_COUNT = 30
CAMPAIGN_SEEDS = tuple(protocol_v7.V7_VALIDATION_SEEDS[:CAMPAIGN_SEED_COUNT])
CAMPAIGN_SEED_BLOCK_SIZE = 5
CAMPAIGN_SEED_BLOCKS = tuple(
    CAMPAIGN_SEEDS[index : index + CAMPAIGN_SEED_BLOCK_SIZE]
    for index in range(0, len(CAMPAIGN_SEEDS), CAMPAIGN_SEED_BLOCK_SIZE)
)
EXPECTED_TRACE_COUNT = 3 * CAMPAIGN_SEED_COUNT
SHIPMENT_SOURCE = "data/production_supplier_shipments_daily.csv"
EXPECTED_V7_PROTOCOL_SHA256 = (
    "f11ba2523bd319e210e5d5d82a25beb1e88a2fc5bd17a181540f8662526a63e5"
)


class V7TracePackageError(ValueError):
    """The accepted V7 source cannot yield an exact mature-campaign package."""


def validate_frozen_v7_protocol() -> Path:
    """Fail closed if the independently reviewed V7 protocol changes."""

    path = Path(protocol_v7.__file__).resolve()
    digest = campaign_contract.sha256_file(path)
    if digest != EXPECTED_V7_PROTOCOL_SHA256:
        raise V7TracePackageError(f"Frozen V7 protocol changed: {digest}")
    if (
        len(protocol_v7.V7_VALIDATION_SEEDS) != protocol_v7.VALIDATION_SEED_COUNT
        or tuple(protocol_v7.V7_VALIDATION_SEEDS[:CAMPAIGN_SEED_COUNT])
        != CAMPAIGN_SEEDS
    ):
        raise V7TracePackageError("Frozen V7 seed order changed")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V7TracePackageError(f"Cannot read JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V7TracePackageError(f"JSON must contain an object: {path}")
    return payload


def _signed(unsigned: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**unsigned, field: campaign_contract.stable_sha256(unsigned)}


def _verify(payload: Mapping[str, Any], field: str, label: str) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(field, ""))
    if not campaign_contract.is_sha256(
        signature
    ) or signature != campaign_contract.stable_sha256(unsigned):
        raise V7TracePackageError(f"Invalid {label} signature")
    return signature


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _validate_v7(
    plan_dir: Path, run_dir: Path
) -> tuple[Any, dict[str, Any], dict[tuple[str, int], dict[str, Any]]]:
    validate_frozen_v7_protocol()
    plan = protocol_v7.validate_plan(
        plan_dir.resolve(), allow_test_source=False, verify_runtime=True
    )
    result = protocol_v7.validate_result(
        plan.plan_dir, run_dir.resolve(), test_only=False
    )
    evidence = protocol_v7.validated_evidence(
        plan.plan_dir, run_dir.resolve(), test_only=False
    )
    if (
        result.get("status") != protocol_v7.ACCEPTED_STATUS
        or result.get("accepted") is not True
        or result.get("publishable") is not True
        or result.get("execution_mode") != protocol_v7.OFFICIAL_EXECUTION_MODE
        or result.get("plan_signature") != plan.manifest["plan_signature"]
        or result.get("v5_v6_acceptance_evidence_reused") is not False
        or result.get("v6_holdout_reused_as_v7_acceptance_evidence") is not False
        or int(result.get("validation_seed_count") or -1)
        != protocol_v7.VALIDATION_SEED_COUNT
        or int(result.get("fresh_physical_evidence_case_count") or -1)
        != protocol_v7.EXPECTED_CASES
        or len(evidence) != protocol_v7.EXPECTED_CASES
        or result.get("evidence_signature_set_sha256")
        != protocol_v7.stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        )
    ):
        raise V7TracePackageError(
            "Only the accepted complete official V7 run is usable"
        )
    return plan, dict(result), evidence


def _campaign_lanes(v7_plan: Any) -> list[dict[str, Any]]:
    source = v7_plan.manifest.get("v6_design_provenance") or {}
    v6_plan_path = Path(str(source.get("plan") or "")).resolve()
    v6_plan = development_v6.validate_plan(
        v6_plan_path.parent, verify_runtime_dependencies=True
    )
    if v6_plan.manifest["plan_signature"] != source.get(
        "plan_signature"
    ) or campaign_contract.sha256_file(v6_plan_path) != source.get("plan_sha256"):
        raise V7TracePackageError("V7 design is not bound to its V6 lane source")
    campaign_path = Path(
        str(v6_plan.manifest["source"]["campaign_manifest"]["path"])
    ).resolve()
    campaign = _read_json(campaign_path)
    lanes = campaign.get("lanes")
    if not isinstance(lanes, list):
        raise V7TracePackageError("Signed design source has no lane registry")
    try:
        return campaign_contract.lane_contract_payload(lanes)
    except Exception as exc:
        raise V7TracePackageError("Signed 18-lane campaign scope changed") from exc


def _trace_adapter(v7_plan: Any, lanes: Sequence[Mapping[str, Any]]) -> tuple[Any, Any]:
    v4, adapter = protocol_v7._v4_adapter(v7_plan)  # noqa: SLF001
    manifest = dict(adapter["validated_plan"].manifest)
    manifest["source"] = {"lanes": [dict(row) for row in lanes]}
    validated = v4.ValidatedPlan(
        v7_plan.plan_dir,
        manifest,
        tuple(adapter["validated_plan"].candidates),
    )
    return v4, validated


def _bundle_source(
    *, run_dir: Path, evidence: Mapping[str, Any]
) -> tuple[bytes, dict[str, Any]]:
    bundle = evidence.get("retained_bundle") or {}
    matches = [
        dict(row)
        for row in bundle.get("files") or []
        if isinstance(row, Mapping)
        and row.get("source_relative_path") == SHIPMENT_SOURCE
    ]
    if len(matches) != 1:
        raise V7TracePackageError("V7 evidence has no unique retained shipment CSV")
    row = matches[0]
    path = (run_dir / str(row.get("relative_path") or "")).resolve()
    if not path.is_relative_to(run_dir) or not path.is_file():
        raise V7TracePackageError("Retained shipment snapshot escaped/disappeared")
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != row.get("gzip_sha256") or len(
        compressed
    ) != row.get("gzip_bytes"):
        raise V7TracePackageError("Retained shipment snapshot gzip hash changed")
    try:
        raw = gzip.decompress(compressed)
    except OSError as exc:
        raise V7TracePackageError("Retained shipment snapshot is not gzip") from exc
    if hashlib.sha256(raw).hexdigest() != row.get("source_sha256") or len(
        raw
    ) != row.get("source_bytes"):
        raise V7TracePackageError("Retained shipment CSV source hash changed")
    return raw, row


def _trace_relative(candidate: Any, seed: int) -> str:
    return f"shipment_traces/holdout/{candidate.key}/seed_{seed}.json.gz"


def _evidence_relative(candidate: Any, seed: int) -> str:
    return f"evidence/{candidate.target_group}/{candidate.key}/seed_{seed}.json"


def _case_material(
    *,
    plan: Any,
    run_dir: Path,
    candidate: Any,
    seed: int,
    result_signature: str,
    source_evidence: Mapping[str, Any],
    v4: Any,
    trace_plan: Any,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    raw_csv, bundle_row = _bundle_source(run_dir=run_dir, evidence=source_evidence)
    rows = v4._canonical_trace_rows(raw_csv, trace_plan)  # noqa: SLF001
    trace = v4._shipment_trace_payload(  # noqa: SLF001
        plan=trace_plan,
        candidate=candidate,
        seed=seed,
        rows=rows,
        source_csv_sha256=bundle_row["source_sha256"],
    )
    raw_trace = v4._trace_json_bytes(trace)  # noqa: SLF001
    compressed_trace = v4._deterministic_gzip(raw_trace)  # noqa: SLF001
    trace_reference = {
        "relative_path": _trace_relative(candidate, seed),
        "gzip_sha256": hashlib.sha256(compressed_trace).hexdigest(),
        "trace_signature": trace["trace_signature"],
        "source_csv_sha256": bundle_row["source_sha256"],
        "row_count": len(rows),
        "uncompressed_bytes": len(raw_trace),
        "compression": campaign_contract.TRACE_COMPRESSION,
    }
    unsigned_evidence = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "result_signature": result_signature,
        "target_group": candidate.target_group,
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "seed": seed,
        "source_v7_evidence_signature": source_evidence["evidence_signature"],
        "source_v7_bundle_signature": source_evidence["retained_bundle"][
            "bundle_signature"
        ],
        "source_shipment_snapshot": bundle_row,
        "shipment_trace": trace_reference,
        "engine_runs_performed": 0,
    }
    derived_evidence = _signed(unsigned_evidence, "evidence_signature")
    return compressed_trace, trace_reference, derived_evidence


def _selection_payload(plan: Any, result: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "fixed_first_30_v7_seed_blocks_for_incident_campaign",
        "plan_signature": plan.manifest["plan_signature"],
        "result_signature": result["result_signature"],
        "selected_candidate_keys": {
            candidate.target_group: candidate.key for candidate in plan.candidates
        },
        "campaign_seeds": list(CAMPAIGN_SEEDS),
        "selection_rule": "first_30_seed_blocks_in_signed_v7_plan_order",
        "selection_frozen_before_v7_execution": True,
        "selection_uses_simulated_outcomes": False,
        "validation_seed_count": protocol_v7.VALIDATION_SEED_COUNT,
        "campaign_seed_count": CAMPAIGN_SEED_COUNT,
        "retuning_or_candidate_selection": False,
    }
    return _signed(unsigned, "selection_signature")


def _build_payloads(
    plan_dir: Path,
    run_dir: Path,
    package_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[Path, bytes]]:
    plan, result, evidence = _validate_v7(plan_dir, run_dir)
    run_dir = run_dir.resolve()
    package_dir = package_dir.resolve()
    lanes = _campaign_lanes(plan)
    v4, trace_plan = _trace_adapter(plan, lanes)
    candidates = {candidate.key: candidate for candidate in trace_plan.candidates}
    file_bytes: dict[Path, bytes] = {}
    index: list[dict[str, Any]] = []
    for seed in CAMPAIGN_SEEDS:
        for spec in protocol_v7.FIXED_TRIPLET:
            candidate = candidates[spec.key]
            source_evidence = evidence[(spec.key, seed)]
            compressed, reference, derived = _case_material(
                plan=plan,
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
                result_signature=result["result_signature"],
                source_evidence=source_evidence,
                v4=v4,
                trace_plan=trace_plan,
            )
            trace_relative = Path(reference["relative_path"])
            evidence_relative = Path(_evidence_relative(candidate, seed))
            encoded_evidence = (
                json.dumps(derived, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8")
            file_bytes[trace_relative] = compressed
            file_bytes[evidence_relative] = encoded_evidence
            index.append(
                {
                    "operating_point_id": candidate.target_group,
                    "candidate_key": candidate.key,
                    "candidate_id": candidate.candidate_id,
                    "seed": seed,
                    "evidence_relative_path": evidence_relative.as_posix(),
                    "evidence_sha256": hashlib.sha256(encoded_evidence).hexdigest(),
                    "evidence_signature": derived["evidence_signature"],
                    "shipment_trace": reference,
                }
            )
    index.sort(key=lambda row: (row["operating_point_id"], row["seed"]))
    if len(index) != EXPECTED_TRACE_COUNT or {
        (row["operating_point_id"], row["seed"]) for row in index
    } != {
        (state, seed)
        for state in campaign_contract.OPERATING_POINT_IDS
        for seed in CAMPAIGN_SEEDS
    }:
        raise V7TracePackageError("Derived V7 trace matrix is not exactly 3 x 30")
    selection = _selection_payload(plan, result)
    selection_bytes = (
        json.dumps(selection, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    file_bytes[Path("campaign_trace_selection.json")] = selection_bytes
    producer = Path(__file__).resolve()
    unsigned_manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_read_only_derivation_from_accepted_v7",
        "producer": {
            "path": str(producer),
            "sha256": campaign_contract.sha256_file(producer),
        },
        "v7_source": {
            "protocol_driver_sha256": EXPECTED_V7_PROTOCOL_SHA256,
            "plan_dir": str(plan.plan_dir),
            "plan_manifest": str((plan.plan_dir / "protocol_manifest.json").resolve()),
            "plan_manifest_sha256": campaign_contract.sha256_file(
                plan.plan_dir / "protocol_manifest.json"
            ),
            "plan_signature": plan.manifest["plan_signature"],
            "run_dir": str(run_dir),
            "run_manifest": str((run_dir / "run_manifest.json").resolve()),
            "run_manifest_sha256": campaign_contract.sha256_file(
                run_dir / "run_manifest.json"
            ),
            "result": str((run_dir / "validation_result.json").resolve()),
            "result_sha256": campaign_contract.sha256_file(
                run_dir / "validation_result.json"
            ),
            "result_signature": result["result_signature"],
            "validation_seed_count": protocol_v7.VALIDATION_SEED_COUNT,
            "fresh_physical_evidence_case_count": protocol_v7.EXPECTED_CASES,
        },
        "campaign_cohort": {
            "selection_rule": "first_30_seed_blocks_in_signed_v7_plan_order",
            "seeds": list(CAMPAIGN_SEEDS),
            "seed_count": CAMPAIGN_SEED_COUNT,
            "seed_blocks": [list(block) for block in CAMPAIGN_SEED_BLOCKS],
            "state_count": len(protocol_v7.FIXED_TRIPLET),
            "trace_count": EXPECTED_TRACE_COUNT,
            "subset_of_v7_validation_seeds": True,
            "same_seeds_required_for_baseline_and_incidents": True,
            "outcome_dependent_selection": False,
        },
        "lane_contract": {
            "count": len(lanes),
            "lanes": lanes,
            "sha256": campaign_contract.lane_contract_sha256(lanes),
        },
        "trace_contract": {
            "schema_version": campaign_contract.TRACE_SCHEMA_VERSION,
            "compression": campaign_contract.TRACE_COMPRESSION,
            "fields": list(campaign_contract.TRACE_ROW_FIELDS),
            "filter_contract": campaign_contract.trace_filter_contract(lanes),
        },
        "selection": {
            "relative_path": "campaign_trace_selection.json",
            "sha256": hashlib.sha256(selection_bytes).hexdigest(),
            "signature": selection["selection_signature"],
        },
        "trace_index": index,
        "trace_index_signature": campaign_contract.stable_sha256(index),
        "file_inventory": [
            {
                "relative_path": path.as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
            for path, raw in sorted(
                file_bytes.items(), key=lambda item: item[0].as_posix()
            )
        ],
        "engine_runs_performed": 0,
        "v4_v5_v6_simulation_evidence_reused": False,
        "v6_role": "design_provenance_only",
    }
    manifest = _signed(unsigned_manifest, "run_signature")
    return manifest, selection, index, file_bytes


def validate_package(
    package_dir: Path,
    *,
    plan_dir: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest_path = package_dir / "trace_package_manifest.json"
    manifest = _read_json(manifest_path)
    _verify(manifest, "run_signature", "V7 trace package")
    source = manifest.get("v7_source") or {}
    expected_plan = Path(str(source.get("plan_dir") or "")).resolve()
    expected_run = Path(str(source.get("run_dir") or "")).resolve()
    if plan_dir is not None and plan_dir.resolve() != expected_plan:
        raise V7TracePackageError("Trace package belongs to another V7 plan")
    if run_dir is not None and run_dir.resolve() != expected_run:
        raise V7TracePackageError("Trace package belongs to another V7 run")
    expected_manifest, selection, index, file_bytes = _build_payloads(
        expected_plan, expected_run, package_dir
    )
    if manifest != expected_manifest:
        raise V7TracePackageError("V7 trace package manifest differs from source")
    actual_selection = _read_json(package_dir / "campaign_trace_selection.json")
    _verify(actual_selection, "selection_signature", "V7 campaign trace selection")
    if actual_selection != selection:
        raise V7TracePackageError("V7 campaign trace selection changed")
    expected_files = {
        "trace_package_manifest.json",
        *(path.as_posix() for path in file_bytes),
    }
    actual_files = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise V7TracePackageError("V7 trace package file inventory changed")
    for relative, raw in file_bytes.items():
        path = package_dir / relative
        if path.read_bytes() != raw:
            raise V7TracePackageError(f"Derived V7 trace file changed: {relative}")
    lanes = manifest["lane_contract"]["lanes"]
    allowed = [row["lane_id"] for row in lanes]
    validated_plan = protocol_v7.validate_plan(expected_plan, verify_runtime=True)
    engine_sha = validated_plan.manifest["execution_contract"]["engine"]["sha256"]
    for row in index:
        campaign_contract.validate_trace_reference(
            row["shipment_trace"],
            run_dir=package_dir,
            expected={
                "plan_signature": source["plan_signature"],
                "candidate_key": row["candidate_key"],
                "candidate_id": row["candidate_id"],
                "target_group": row["operating_point_id"],
                "seed": row["seed"],
                "graph_sha256": validated_plan.manifest["inventory"][
                    row["candidate_key"]
                ]["graph_sha256"],
                "engine_sha256": engine_sha,
                "simulation_days": protocol_v7.SERVICE_DAYS,
                "lane_contract_sha256": manifest["lane_contract"]["sha256"],
                "filter_contract": campaign_contract.trace_filter_contract(lanes),
            },
            allowed_lane_ids=allowed,
        )
    return manifest


def build_package(plan_dir: Path, run_dir: Path, output_dir: Path) -> Path:
    output = output_dir.resolve()
    for source in (
        plan_dir.resolve(),
        run_dir.resolve(),
        Path(__file__).resolve().parents[3],
    ):
        if _paths_overlap(output, source):
            raise V7TracePackageError(
                "Trace package output overlaps a protected source"
            )
    if output.exists():
        validate_package(output, plan_dir=plan_dir, run_dir=run_dir)
        return output / "trace_package_manifest.json"
    manifest, _selection, _index, file_bytes = _build_payloads(
        plan_dir, run_dir, output
    )
    temporary = output.with_name(f".{output.name}.building-{uuid4().hex}")
    published_by_this_call = False
    try:
        temporary.mkdir(parents=True)
        for relative, raw in file_bytes.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (temporary / "trace_package_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.rename(output)
        published_by_this_call = True
        validate_package(output, plan_dir=plan_dir, run_dir=run_dir)
    except BaseException:
        if temporary.exists() and temporary.parent == output.parent:
            shutil.rmtree(temporary)
        if published_by_this_call and output.exists():
            try:
                validate_package(output, plan_dir=plan_dir, run_dir=run_dir)
            except BaseException:
                shutil.rmtree(output)
        raise
    return output / "trace_package_manifest.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--plan-dir", type=Path, required=True)
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--path", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        result: Any = build_package(args.plan_dir, args.run_dir, args.output_dir)
    else:
        result = validate_package(args.path)["run_signature"]
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
