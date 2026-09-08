#!/usr/bin/env python3
"""Run the unchanged 3,330-row incident campaign through the V7 bridge."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as v7_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v6 as adapter_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


implementation_v4 = adapter_v6.implementation_v4
ADAPTER_PATH = Path(__file__).resolve()
V7CampaignAdapterError = adapter_v6.V6CampaignAdapterError
EXPECTED_V6_ADAPTER_SHA256 = (
    "ac251c2f7fec97d770ae43e21247e07a2d1eda09ebed5dbf0a113f035e9c8564"
)
_ORIGINAL_DESIGN_PAYLOAD = implementation_v4._design_payload  # noqa: SLF001
_ORIGINAL_STATE_VALIDATION_BINDING = (  # noqa: SLF001
    implementation_v4._build_v4_state_validation_binding
)


def _v7_source_contract(holdout: Any) -> dict[str, Any]:
    if not isinstance(holdout, dict):
        raise V7CampaignAdapterError("V7 holdout contract is missing")
    validation = holdout.get("validation_protocol")
    baseline = holdout.get("campaign_baseline_contract")
    if (
        holdout.get("accepted") is not True
        or holdout.get("publishable") is not True
        or holdout.get("status") != protocol_v7.ACCEPTED_STATUS
        or holdout.get("execution_mode") != protocol_v7.OFFICIAL_EXECUTION_MODE
        or holdout.get("retuning_after_holdout") is not False
        or not isinstance(validation, dict)
        or validation.get("role") != "sole_scientific_authorization_for_fixed_triplet"
        or validation.get("accepted") is not True
        or validation.get("status") != protocol_v7.ACCEPTED_STATUS
        or validation.get("validation_seed_count") != 150
        or validation.get("fresh_physical_evidence_case_count") != 450
        or validation.get("prior_version_simulation_evidence_reused") is not False
        or validation.get("retuning_after_any_v7_result") is not False
        or not isinstance(baseline, dict)
        or baseline.get("role") != "campaign_initial_conditions_and_pairing_only"
        or baseline.get("seeds") != list(trace_package.CAMPAIGN_SEEDS)
        or baseline.get("physical_case_count") != 90
        or baseline.get("subset_of_v7_validation") is not True
        or baseline.get("same_seeds_required_for_baseline_and_incidents") is not True
        or baseline.get("acceptance_gate") is not False
        or baseline.get("used_for_operating_point_retuning") is not False
    ):
        raise V7CampaignAdapterError("V7 scientific/campaign separation changed")
    return {
        "scientific_authorization": "accepted_official_v7_fixed_triplet_confirmation",
        "v7_plan_signature": validation["plan_signature"],
        "v7_result_signature": validation["result_signature"],
        "validation_seed_count": 150,
        "fresh_validation_case_count": 450,
        "campaign_baseline_seed_count": 30,
        "campaign_baseline_trace_count": 90,
        "campaign_baseline_subset_is_acceptance_gate": False,
        "same_30_seeds_for_baseline_and_incidents": True,
        "retuning_after_v7": False,
        "prior_version_simulation_evidence_reused": False,
    }


def _build_v7_design_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:
    payload = dict(_ORIGINAL_DESIGN_PAYLOAD(*args, **kwargs))
    provenance = _v7_source_contract(payload.get("operating_points_holdout_contract"))
    counts = dict(payload.get("expected_counts") or {})
    counts.update(
        {
            "imported_v7_campaign_baseline_service_proofs": 90,
            "imported_v7_campaign_baseline_shipment_traces": 90,
            "legacy_v4_count_field_names_are_compatibility_aliases": True,
        }
    )
    preflight = dict(payload.get("operating_point_preflight_contract") or {})
    preflight.update(
        {
            "kind": "signed_v7_confirmation_state_validation_binding",
            "aggregation": "describe_first_30_of_accepted_v7_without_retuning",
            "scientific_authorization_seed_count": 150,
            "scientific_authorization_case_count": 450,
            "campaign_baseline_seed_count": 30,
            "legacy_v4_field_names_retained_for_frozen_reader_compatibility": True,
        }
    )
    payload.update(
        {
            "expected_counts": counts,
            "operating_point_preflight_contract": preflight,
            "operating_points_scientific_producer": (
                "v7_fixed_triplet_confirmation_bridge"
            ),
            "operating_points_producer_is_legacy_dispatch_key": True,
            "scientific_provenance_v7": provenance,
        }
    )
    return payload


def _build_v7_state_validation_binding(*, manifest: Any, bridge: Any) -> dict[str, Any]:
    legacy = dict(_ORIGINAL_STATE_VALIDATION_BINDING(manifest=manifest, bridge=bridge))
    legacy.pop("binding_signature", None)
    source = dict(bridge.get("source") or {})
    provenance = _v7_source_contract(bridge.get("holdout_contract"))
    legacy.update(
        {
            "v7_plan_signature": source.get("plan_signature"),
            "v7_campaign_trace_selection_signature": source.get(
                "development_selection_signature"
            ),
            "v7_validation_result_signature": source.get("holdout_signature"),
            "v7_campaign_trace_index_signature": bridge.get("trace_index_signature"),
            "scientific_provenance_v7": provenance,
            "legacy_v4_named_signature_fields_are_compatibility_aliases": True,
            "interpretation": (
                "Exact campaign binding to an accepted official V7 confirmation "
                "over 150 seeds and 450 fresh physical cases. The first 30 V7 "
                "seeds provide 90 paired campaign baselines only; they do not "
                "retune or re-accept the operating points, and they are not "
                "observed supplier performance."
            ),
        }
    )
    return {
        **legacy,
        "binding_signature": implementation_v4._stable_sha256(legacy),  # noqa: SLF001
    }


def validate_frozen_implementation() -> Path:
    trace_package.validate_frozen_v7_protocol()
    path = Path(adapter_v6.__file__).resolve()
    digest = adapter_v6.adapter_v5._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V6_ADAPTER_SHA256:
        raise V7CampaignAdapterError(f"Frozen V6 campaign adapter changed: {digest}")
    return adapter_v6.validate_frozen_implementation()


@contextmanager
def patched_v7_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_file: Any = implementation_v4.__file__
    previous_seeds: Any = implementation_v4.SEEDS
    previous_seed_block_size: Any = implementation_v4.SEED_BLOCK_SIZE
    previous_seed_blocks: Any = implementation_v4.SEED_BLOCKS
    previous_design_payload: Any = implementation_v4._design_payload  # noqa: SLF001
    previous_binding_builder: Any = (  # noqa: SLF001
        implementation_v4._build_v4_state_validation_binding
    )
    implementation_v4.v4_bridge = v7_bridge
    implementation_v4.__file__ = str(ADAPTER_PATH)
    implementation_v4.SEEDS = trace_package.CAMPAIGN_SEEDS
    implementation_v4.SEED_BLOCK_SIZE = trace_package.CAMPAIGN_SEED_BLOCK_SIZE
    implementation_v4.SEED_BLOCKS = trace_package.CAMPAIGN_SEED_BLOCKS
    implementation_v4._design_payload = _build_v7_design_payload  # noqa: SLF001
    implementation_v4._build_v4_state_validation_binding = (  # noqa: SLF001
        _build_v7_state_validation_binding
    )
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.__file__ = previous_file
        implementation_v4.SEEDS = previous_seeds
        implementation_v4.SEED_BLOCK_SIZE = previous_seed_block_size
        implementation_v4.SEED_BLOCKS = previous_seed_blocks
        implementation_v4._design_payload = previous_design_payload  # noqa: SLF001
        implementation_v4._build_v4_state_validation_binding = (  # noqa: SLF001
            previous_binding_builder
        )


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v7_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
