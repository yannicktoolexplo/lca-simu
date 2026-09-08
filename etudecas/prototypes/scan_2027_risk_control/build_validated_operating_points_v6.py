#!/usr/bin/env python3
"""Build the campaign-compatible bridge from an accepted V6 fresh holdout.

The stable V5 bridge serializer/validator is reused as a compatibility envelope;
the signed source paths, signatures and hashes bind it to the V6 holdout.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v5 as implementation_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_holdout_v6 as holdout_v6,
)


BRIDGE_SCHEMA_VERSION = implementation_v5.BRIDGE_SCHEMA_VERSION
BRIDGE_ACCEPTED_STATUS = implementation_v5.BRIDGE_ACCEPTED_STATUS
ACCEPTED_HOLDOUT_STATUS = holdout_v6.ACCEPTED_HOLDOUT_STATUS
campaign_contract = implementation_v5.campaign_contract

INTERPRETATION = (
    "Simulation hypotheses only; the three accepted V6 states come from thirty "
    "fresh reserved seeds after a separately frozen selection. They are not "
    "observed supplier performance and do not estimate incident probability."
)

V6BridgeError = implementation_v5.V5BridgeError
EXPECTED_V5_IMPLEMENTATION_SHA256 = (
    "41492d5b66835028b7aed9977a4e21f4214e7d6e85d98c6a5ae535a7b2cbacb2"
)


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v5.__file__).resolve()
    if campaign_contract.sha256_file(path) != EXPECTED_V5_IMPLEMENTATION_SHA256:
        raise V6BridgeError("Frozen V5 bridge implementation changed")
    return path


def _load_official_source_v6(
    plan_dir: Path, run_dir: Path
) -> tuple[
    Any,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[tuple[str, int], dict[str, Any]],
]:
    validate_frozen_implementation()
    plan = holdout_v6.validate_plan(plan_dir, verify_runtime_dependencies=True)
    if tuple(holdout_v6.EXPECTED_HOLDOUT_SEEDS) != tuple(
        campaign_contract.CAMPAIGN_SEEDS
    ):
        raise V6BridgeError("V6 holdout/campaign seed contracts differ")
    if holdout_v6.INCIDENT_DESIGN_SEED != campaign_contract.INCIDENT_DESIGN_SEED:
        raise V6BridgeError("V6 holdout/campaign design seeds differ")
    if plan.manifest["source_hashes"].get(
        "v6_holdout_driver_sha256"
    ) != campaign_contract.sha256_file(Path(holdout_v6.__file__).resolve()):
        raise V6BridgeError("The V6 holdout plan does not pin its current producer")
    run_dir = run_dir.resolve()
    mode = holdout_v6._registered_execution_mode(plan, run_dir)  # noqa: SLF001
    if mode != holdout_v6.OFFICIAL_EXECUTION_MODE:
        raise V6BridgeError("Only an official V6 holdout can authorize a campaign")
    run_manifest = implementation_v5._read_json(run_dir / "run_manifest.json")  # noqa: SLF001
    if (
        run_manifest != holdout_v6._run_manifest(plan, mode)  # noqa: SLF001
        or run_manifest.get("publishable") is not True
    ):
        raise V6BridgeError("V6 official holdout registration changed")
    selection = holdout_v6._load_development_selection(plan, run_dir)  # noqa: SLF001
    evidence = holdout_v6._load_stage_evidence(  # noqa: SLF001
        plan, run_dir, "holdout"
    )
    holdout_path = run_dir / "holdout_result.json"
    holdout = implementation_v5._read_json(holdout_path)  # noqa: SLF001
    implementation_v5._verify_self_signature(  # noqa: SLF001
        holdout, "holdout_signature", "V6 holdout"
    )
    rebuilt = holdout_v6._build_holdout_result(  # noqa: SLF001
        plan, evidence, selection, execution_mode=mode
    )
    if holdout != rebuilt:
        raise V6BridgeError("V6 holdout is not reproducible from its 90 proofs")
    if (
        holdout.get("status") != ACCEPTED_HOLDOUT_STATUS
        or holdout.get("accepted") is not True
        or holdout.get("retuning_after_holdout") is not False
        or holdout.get("publishable") is not True
    ):
        raise V6BridgeError("V6 holdout is not accepted without retuning")
    return plan, run_manifest, selection, holdout, evidence


@contextmanager
def _v6_binding() -> Iterator[None]:
    validate_frozen_implementation()
    names: dict[str, Any] = {
        "refinement_v5": holdout_v6,
        "INTERPRETATION": INTERPRETATION,
        "ACCEPTED_HOLDOUT_STATUS": ACCEPTED_HOLDOUT_STATUS,
        "_load_official_source": _load_official_source_v6,
    }
    previous = {name: getattr(implementation_v5, name) for name in names}
    try:
        for name, value in names.items():
            setattr(implementation_v5, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(implementation_v5, name, value)


def build_bridge_payload(plan_dir: Path, run_dir: Path) -> dict[str, Any]:
    with _v6_binding():
        payload = implementation_v5.build_bridge_payload(plan_dir, run_dir)
    plan = holdout_v6.validate_plan(plan_dir, verify_runtime_dependencies=True)
    unsigned = dict(payload)
    unsigned.pop("artifact_signature", None)
    producer_path = Path(__file__).resolve()
    unsigned["producer"] = {
        "path": str(producer_path),
        "sha256": campaign_contract.sha256_file(producer_path),
    }
    unsigned["source_hashes"] = {
        "v5_development_driver_sha256": plan.manifest["source_hashes"][
            "v5_driver_sha256"
        ],
        "v6_development_driver_sha256": plan.manifest["source_hashes"][
            "v6_driver_sha256"
        ],
        "v6_holdout_driver_sha256": plan.manifest["source_hashes"][
            "v6_holdout_driver_sha256"
        ],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "engine_profile_sha256": plan.manifest["source_hashes"][
            "engine_profile_sha256"
        ],
        "v5_bridge_implementation_sha256": EXPECTED_V5_IMPLEMENTATION_SHA256,
        "v6_bridge_driver_sha256": campaign_contract.sha256_file(producer_path),
    }
    return {
        **unsigned,
        "artifact_signature": campaign_contract.stable_sha256(unsigned),
    }


def validate_bridge(path: Path, *, revalidate_source: bool = True) -> dict[str, Any]:
    path = path.resolve()
    payload = implementation_v5._read_json(path)  # noqa: SLF001
    if set(payload) != implementation_v5.BRIDGE_FIELDS:
        raise V6BridgeError("Validated V6 bridge fields changed")
    implementation_v5._verify_self_signature(  # noqa: SLF001
        payload, "artifact_signature", "V6 bridge"
    )
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
        raise V6BridgeError("Validated V6 bridge status changed")
    source = payload.get("source")
    hashes = payload.get("source_hashes")
    points = payload.get("operating_points")
    traces = payload.get("trace_index")
    if (
        not isinstance(source, Mapping)
        or set(source) != implementation_v5.SOURCE_REFERENCE_FIELDS
        or not isinstance(hashes, Mapping)
        or set(hashes)
        != {
            "v5_development_driver_sha256",
            "v6_development_driver_sha256",
            "v6_holdout_driver_sha256",
            "engine_sha256",
            "engine_profile_sha256",
            "v5_bridge_implementation_sha256",
            "v6_bridge_driver_sha256",
        }
        or not isinstance(points, list)
        or len(points) != 3
        or [row.get("operating_point_id") for row in points]
        != list(campaign_contract.OPERATING_POINT_IDS)
        or not isinstance(traces, list)
        or len(traces) != 90
        or payload.get("trace_index_signature")
        != campaign_contract.stable_sha256(traces)
    ):
        raise V6BridgeError("Validated V6 bridge structure changed")
    holdout = payload.get("holdout_contract") or {}
    if (
        holdout.get("status") != ACCEPTED_HOLDOUT_STATUS
        or holdout.get("accepted") is not True
        or holdout.get("publishable") is not True
        or holdout.get("retuning_after_holdout") is not False
        or holdout.get("evidence_case_count") != 90
    ):
        raise V6BridgeError("Validated V6 holdout contract changed")
    producer = payload.get("producer") or {}
    producer_path = Path(__file__).resolve()
    if producer != {
        "path": str(producer_path),
        "sha256": campaign_contract.sha256_file(producer_path),
    }:
        raise V6BridgeError("Validated V6 bridge serializer changed")
    if revalidate_source:
        rebuilt = build_bridge_payload(Path(source["plan_dir"]), Path(source["run_dir"]))
        if rebuilt != payload:
            raise V6BridgeError("Validated V6 bridge differs from signed source")
    return payload


def write_bridge(plan_dir: Path, run_dir: Path, output: Path) -> Path:
    output = output.resolve()
    plan_dir = plan_dir.resolve()
    run_dir = run_dir.resolve()
    plan = holdout_v6.validate_plan(plan_dir, verify_runtime_dependencies=True)
    source = plan.manifest["v6_development_source"]
    development_plan = holdout_v6.development_v6.validate_plan(
        Path(source["plan_dir"]), verify_runtime_dependencies=True
    )
    protected = (
        plan.plan_dir,
        run_dir,
        *holdout_v6._protected_development_sources(  # noqa: SLF001
            development_plan, Path(source["run_dir"])
        ),
    )
    if any(holdout_v6._paths_overlap(output, root) for root in protected):  # noqa: SLF001
        raise V6BridgeError("V6 bridge output overlaps an immutable source")
    payload = build_bridge_payload(plan_dir, run_dir)
    if output.exists():
        if validate_bridge(output) != payload:
            raise V6BridgeError("Existing V6 bridge differs; refusing overwrite")
        return output
    if build_bridge_payload(plan_dir, run_dir) != payload:
        raise V6BridgeError("V6 source changed before bridge publication")
    implementation_v5._write_json_atomic(output, payload)  # noqa: SLF001
    try:
        validate_bridge(output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--plan-dir", type=Path, required=True)
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--path", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        print(write_bridge(args.plan_dir, args.run_dir, args.output))
    else:
        print(validate_bridge(args.path)["artifact_signature"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
