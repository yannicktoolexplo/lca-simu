#!/usr/bin/env python3
"""Finalize V7-authorized campaign results with the frozen V4 finalizer."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as v7_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v6 as adapter_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


implementation_v4 = adapter_v6.implementation_v4
V7_CAMPAIGN_RUNNER = (
    Path(__file__).resolve().with_name("supplier_operating_point_full_campaign_v7.py")
)
V7FinalizerAdapterError = adapter_v6.V6FinalizerAdapterError
V7_RESULT_OVERLAY_SCHEMA_VERSION = (
    "etudecas.supplier_operating_point_full_campaign.v7.result_overlay.v1"
)
V7_RESULT_OVERLAY_NAME = "campaign_validation_v7.json"
EXPECTED_V6_ADAPTER_SHA256 = (
    "a4d523d0817464074ae4089b660de2db992de950cad8566e9efd2b68dd08715b"
)
_ORIGINAL_VALIDATE_PROVENANCE = (  # noqa: SLF001
    implementation_v4._validate_operating_point_provenance
)


def _v7_provenance(evidence: Any, manifest: Any) -> dict[str, Any]:
    payload = dict(_ORIGINAL_VALIDATE_PROVENANCE(evidence, manifest))
    holdout = payload.get("holdout_contract") or {}
    validation = holdout.get("validation_protocol") or {}
    baseline = holdout.get("campaign_baseline_contract") or {}
    if (
        validation.get("role") != "sole_scientific_authorization_for_fixed_triplet"
        or validation.get("accepted") is not True
        or validation.get("validation_seed_count") != 150
        or validation.get("fresh_physical_evidence_case_count") != 450
        or validation.get("prior_version_simulation_evidence_reused") is not False
        or baseline.get("role") != "campaign_initial_conditions_and_pairing_only"
        or baseline.get("seeds") != list(trace_package.CAMPAIGN_SEEDS)
        or baseline.get("physical_case_count") != 90
        or baseline.get("acceptance_gate") is not False
        or baseline.get("used_for_operating_point_retuning") is not False
    ):
        raise V7FinalizerAdapterError("Final V7 provenance separation changed")
    legacy = str(payload.get("producer") or "")
    payload.update(
        {
            "producer": "v7_fixed_triplet_confirmation_bridge",
            "legacy_v4_producer_dispatch_key": legacy,
            "legacy_v4_producer_is_compatibility_alias": True,
            "scientific_provenance_v7": {
                "scientific_authorization": (
                    "accepted_official_v7_fixed_triplet_confirmation"
                ),
                "v7_plan_signature": validation["plan_signature"],
                "v7_result_signature": validation["result_signature"],
                "validation_seed_count": 150,
                "fresh_validation_case_count": 450,
                "campaign_baseline_seed_count": 30,
                "campaign_baseline_trace_count": 90,
                "campaign_baseline_subset_is_acceptance_gate": False,
                "same_30_seeds_for_baseline_and_incidents": True,
                "prior_version_simulation_evidence_reused": False,
                "retuning_after_v7": False,
            },
        }
    )
    return payload


def validate_frozen_implementation() -> Path:
    trace_package.validate_frozen_v7_protocol()
    path = Path(adapter_v6.__file__).resolve()
    digest = adapter_v6.adapter_v5._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V6_ADAPTER_SHA256:
        raise V7FinalizerAdapterError(f"Frozen V6 finalizer adapter changed: {digest}")
    parent = adapter_v6.validate_frozen_implementation()
    if not V7_CAMPAIGN_RUNNER.is_file():
        raise V7FinalizerAdapterError(
            f"Missing V7 campaign runner: {V7_CAMPAIGN_RUNNER}"
        )
    return parent


@contextmanager
def patched_v7_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_hash: Any = implementation_v4.SOURCE_RUNNER_SHA256
    previous_seeds: Any = implementation_v4.EXPECTED_SEEDS
    previous_provenance: Any = (  # noqa: SLF001
        implementation_v4._validate_operating_point_provenance
    )
    implementation_v4.v4_bridge = v7_bridge
    implementation_v4.SOURCE_RUNNER_SHA256 = adapter_v6.adapter_v5._sha256_file(  # noqa: SLF001
        V7_CAMPAIGN_RUNNER
    )
    implementation_v4.EXPECTED_SEEDS = trace_package.CAMPAIGN_SEEDS
    implementation_v4._validate_operating_point_provenance = (  # noqa: SLF001
        _v7_provenance
    )
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.SOURCE_RUNNER_SHA256 = previous_hash
        implementation_v4.EXPECTED_SEEDS = previous_seeds
        implementation_v4._validate_operating_point_provenance = (  # noqa: SLF001
            previous_provenance
        )


def _overlay_payload(campaign_root: Path, output_dir: Path) -> dict[str, Any]:
    campaign_root = campaign_root.resolve()
    output_dir = output_dir.resolve()
    base_path = output_dir / "campaign_validation.json"
    binding_path = output_dir / "state_validation_binding.json"
    manifest_path = campaign_root / "campaign_manifest.json"
    base = implementation_v4._read_json(base_path)  # noqa: SLF001
    binding = implementation_v4._read_json(binding_path)  # noqa: SLF001
    manifest = implementation_v4._read_json(manifest_path)  # noqa: SLF001
    implementation_v4._verify_payload_signature(  # noqa: SLF001
        binding, "binding_signature", label="V7 final state binding"
    )
    implementation_v4._verify_manifest_signature(manifest)  # noqa: SLF001
    provenance = (base.get("inputs") or {}).get("operating_point_provenance") or {}
    science = binding.get("scientific_provenance_v7") or {}
    comparisons = base.get("comparability_checks") or {}
    expected = base.get("expected_contract") or {}
    source_manifest = (base.get("inputs") or {}).get("campaign_manifest")
    if (
        base.get("status") != "complete_validated"
        or Path(str(source_manifest or "")).resolve() != manifest_path
        or (base.get("inputs") or {}).get("campaign_manifest_sha256")
        != implementation_v4._sha256(manifest_path)  # noqa: SLF001
        or provenance.get("producer") != "v7_fixed_triplet_confirmation_bridge"
        or provenance.get("legacy_v4_producer_is_compatibility_alias") is not True
        or provenance.get("scientific_provenance_v7") != science
        or science.get("scientific_authorization")
        != "accepted_official_v7_fixed_triplet_confirmation"
        or not trace_package.campaign_contract.is_sha256(
            science.get("v7_plan_signature")
        )
        or not trace_package.campaign_contract.is_sha256(
            science.get("v7_result_signature")
        )
        or science.get("validation_seed_count") != 150
        or science.get("fresh_validation_case_count") != 450
        or science.get("campaign_baseline_seed_count") != 30
        or science.get("campaign_baseline_trace_count") != 90
        or science.get("campaign_baseline_subset_is_acceptance_gate") is not False
        or science.get("same_30_seeds_for_baseline_and_incidents") is not True
        or science.get("prior_version_simulation_evidence_reused") is not False
        or science.get("retuning_after_v7") is not False
        or binding.get("campaign_seeds") != list(trace_package.CAMPAIGN_SEEDS)
        or expected.get("repetition_ids") != list(trace_package.CAMPAIGN_SEEDS)
        or expected.get("baseline_row_count") != 90
        or expected.get("incident_row_count") != 3_240
        or expected.get("mechanisms")
        != ["transport_delay", "planned_delivery_shortfall"]
        or expected.get("quality_branch_included") is not False
        or expected.get("availability_incident_included") is not False
        or comparisons.get("v4_holdout_state_binding_signed_and_accepted") is not True
        or comparisons.get("v4_holdout_shipment_traces_reused_without_rerun")
        is not True
        or comparisons.get("all_3330_metrics_reconstructed_from_signed_case_evidence")
        is not True
        or comparisons.get("quality_or_availability_incident_count") != 0
        or any(
            manifest.get(flag) is not False
            for flag in (
                "quality_branch_included",
                "quality_incident_included",
                "availability_incident_included",
                "capacity_incident_included",
                "stock_incident_included",
                "supplier_state_dependent_risks_enabled",
            )
        )
    ):
        raise V7FinalizerAdapterError("Base V4 envelope cannot authorize V7 release")
    unsigned = {
        "schema_version": V7_RESULT_OVERLAY_SCHEMA_VERSION,
        "status": "complete_validated_v7_overlay",
        "base_campaign_validation": {
            "path": str(base_path),
            "sha256": implementation_v4._sha256(base_path),  # noqa: SLF001
            "schema_version": base["schema_version"],
            "status": base["status"],
        },
        "campaign_manifest": {
            "path": str(manifest_path),
            "sha256": implementation_v4._sha256(manifest_path),  # noqa: SLF001
            "campaign_signature": manifest["campaign_signature"],
        },
        "state_validation_binding": {
            "path": str(binding_path),
            "sha256": implementation_v4._sha256(binding_path),  # noqa: SLF001
            "binding_signature": binding["binding_signature"],
        },
        "scientific_provenance_v7": science,
        "v7_comparability_checks": {
            "v7_confirmation_150_seeds_450_cases_signed_and_accepted": True,
            "v7_first30_90_shipment_traces_used_for_pairing_without_rerun": True,
            "same_30_seeds_for_baseline_and_incidents": True,
            "campaign_subset_used_as_v7_acceptance_gate": False,
            "all_3330_metrics_reconstructed_from_signed_case_evidence": True,
            "quality_capacity_availability_stock_or_state_risk_incident_count": 0,
        },
        "legacy_reader_aliases": {
            "v4_holdout_state_binding_signed_and_accepted": (
                "compatibility alias; scientific source is accepted V7 confirmation"
            ),
            "v4_holdout_shipment_traces_reused_without_rerun": (
                "compatibility alias; traces are derived from first 30 V7 seed blocks"
            ),
            "legacy_keys_are_scientific_v4_evidence_claims": False,
        },
        "counts": {
            "validation_seed_count": 150,
            "validation_case_count": 450,
            "campaign_seed_count": 30,
            "baseline_row_count": 90,
            "incident_row_count": 3_240,
            "campaign_row_count": 3_330,
        },
    }
    return {
        **unsigned,
        "overlay_signature": implementation_v4._stable_sha256(unsigned),  # noqa: SLF001
    }


def validate_v7_overlay(campaign_root: Path, output_dir: Path) -> dict[str, Any]:
    expected = _overlay_payload(campaign_root, output_dir)
    path = output_dir.resolve() / V7_RESULT_OVERLAY_NAME
    actual = implementation_v4._read_json(path)  # noqa: SLF001
    implementation_v4._verify_payload_signature(  # noqa: SLF001
        actual, "overlay_signature", label="V7 result overlay"
    )
    if actual != expected:
        raise V7FinalizerAdapterError("V7 result overlay differs from signed sources")
    return actual


def write_v7_overlay(
    campaign_root: Path,
    output_dir: Path,
    *,
    validated_base: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish only beside the base result validated in this same invocation."""

    output_dir = output_dir.resolve()
    path = output_dir / V7_RESULT_OVERLAY_NAME
    if path.exists():
        return validate_v7_overlay(campaign_root, output_dir)
    base_path = output_dir / "campaign_validation.json"
    if implementation_v4._read_json(base_path) != dict(validated_base):  # noqa: SLF001
        raise V7FinalizerAdapterError(
            "V4 compatibility result differs from the just-validated in-memory result"
        )
    payload = _overlay_payload(campaign_root, output_dir)
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.building-{uuid4().hex}")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return validate_v7_overlay(campaign_root, output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    args = implementation_v4.parse_args(argv)
    try:
        base = args.output_dir.resolve() / "campaign_validation.json"
        overlay_path = args.output_dir.resolve() / V7_RESULT_OVERLAY_NAME
        if base.is_file():
            if not overlay_path.is_file():
                raise V7FinalizerAdapterError(
                    "A mature result exists without its V7 overlay; refusing to "
                    "retrofit scientific authorization. Use a new results directory."
                )
            overlay = validate_v7_overlay(args.campaign_root, args.output_dir)
        else:
            with patched_v7_context():
                validated_base = implementation_v4.finalize_campaign(
                    campaign_root=args.campaign_root,
                    manifest_path=args.campaign_manifest,
                    metrics_paths=args.metrics_csv,
                    output_dir=args.output_dir,
                )
            overlay = write_v7_overlay(
                args.campaign_root,
                args.output_dir,
                validated_base=validated_base,
            )
    except (
        implementation_v4.CampaignValidationError,
        V7FinalizerAdapterError,
        FileExistsError,
        OSError,
    ) as exc:
        print(f"CAMPAGNE V7 INVALIDE : {exc}")
        return 2
    print(json.dumps(overlay, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
