#!/usr/bin/env python3
"""Finalize the additive V8 exposure-stratified supplier campaign.

V8 deliberately keeps the mature V4 evidence reconstruction, paired statistics,
bootstrap and lot-replay selection.  It replaces only the obsolete target
discovery reader: the 42-day lane window is selected from the 90 signed V7
baseline traces, must be comparable for all 30 paired seeds and all three
operating states, and consumes no additional simulation run.

The V4-shaped result is retained for downstream readers.  A signed V8 overlay
states the actual scientific provenance and target-selection contract; no
``design_seed`` or 24/30 exposure-gate alias is manufactured for compatibility.
"""

from __future__ import annotations

import json
import math
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
    finalize_supplier_operating_point_full_campaign_v7 as adapter_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v8 as campaign_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


implementation_v4 = adapter_v7.implementation_v4
V8_CAMPAIGN_RUNNER = Path(__file__).resolve().with_name(
    "supplier_operating_point_full_campaign_v8.py"
)
V8FinalizerAdapterError = adapter_v7.V7FinalizerAdapterError
V8_RESULT_OVERLAY_SCHEMA_VERSION = (
    "etudecas.supplier_operating_point_full_campaign.v8.result_overlay.v1"
)
V8_RESULT_OVERLAY_NAME = "campaign_validation_v8.json"
EXPECTED_V7_FINALIZER_SHA256 = (
    "db0d5a2e96cf4af48d7303ccfe1718e7f5015ea30f03aa6c3cffb23b8f6d18a1"
)
TARGET_SELECTION_REVISION = campaign_v8.TARGET_SELECTION_REVISION
TARGET_REGISTRY_SCHEMA_VERSION = campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION
TARGET_PROGRESS_SCHEMA_VERSION = campaign_v8.TARGET_DISCOVERY_PROGRESS_SCHEMA_VERSION
REQUIRED_COMPARABLE_SEED_COUNT = campaign_v8.REQUIRED_COMPARABLE_SEED_COUNT
MIN_FIXED_WINDOW_START_DAY = campaign_v8.MIN_FIXED_WINDOW_START_DAY
MAX_FIXED_WINDOW_START_DAY = campaign_v8.MAX_FIXED_WINDOW_START_DAY
DISRUPTION_WINDOW_DAYS = 42
QUANTITY_RATIO_LIMIT = 1.5
EXPECTED_SOURCE_TRACE_COUNT = campaign_v8.SOURCE_TRACE_COUNT
EXPECTED_TARGET_COUNT = campaign_v8.TARGET_CELL_COUNT
_FORBIDDEN_SELECTION_KEYS = frozenset(
    {
        "design_seed",
        "design_seed_excluded",
        "design_seed_in_acceptance_statistics",
        "design_seed_in_campaign_statistics",
    }
)
_ORIGINAL_BUSINESS_LIMITS = implementation_v4._business_limits  # noqa: SLF001


def _assert_no_design_seed_aliases(payload: Any, *, label: str) -> None:
    """Reject the obsolete independent-seed vocabulary in V8 selection proof."""

    if isinstance(payload, Mapping):
        forbidden = _FORBIDDEN_SELECTION_KEYS.intersection(
            str(key) for key in payload
        )
        if forbidden:
            raise V8FinalizerAdapterError(
                f"{label} contains obsolete design-seed fields: "
                + ", ".join(sorted(forbidden))
            )
        for key, value in payload.items():
            _assert_no_design_seed_aliases(value, label=f"{label}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _assert_no_design_seed_aliases(value, label=f"{label}[{index}]")


def _verify_signed_payload(
    payload: Mapping[str, Any], signature_key: str, *, label: str
) -> str:
    return implementation_v4._verify_payload_signature(  # noqa: SLF001
        payload, signature_key, label=label
    )


def _validate_v8_registry(
    registry: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    lane_identity: Mapping[str, tuple[str, str, str, str, str]],
) -> dict[str, Any]:
    """Replay V8 selection from the signed V7 traces, without any engine run."""

    _assert_no_design_seed_aliases(registry, label="V8 target registry")
    signature = _verify_signed_payload(
        registry, "registry_signature", label="V8 target registry"
    )
    if signature != manifest.get("target_registry_signature"):
        raise V8FinalizerAdapterError("V8 registry/manifest signature mismatch")

    lane_path = Path(str(manifest.get("lane_reference_source") or "")).resolve()
    if (
        not lane_path.is_file()
        or implementation_v4._sha256(lane_path)  # noqa: SLF001
        != manifest.get("lane_reference_source_sha256")
    ):
        raise V8FinalizerAdapterError("V8 signed lane reference is missing or changed")
    try:
        with campaign_v8.patched_v8_context():
            runner = campaign_v8.implementation_v4
            lanes = runner.load_lanes(lane_path)
            observed_identity = {
                lane.lane_id: (
                    lane.supplier_id,
                    lane.item_id,
                    lane.dst_node_id,
                    lane.edge_id,
                    lane.target_product_id,
                )
                for lane in lanes
            }
            if observed_identity != dict(lane_identity):
                raise V8FinalizerAdapterError(
                    "V8 lane reference differs from signed manifest"
                )
            bridge_path = Path(
                str(manifest.get("operating_points_source") or "")
            ).resolve()
            bridge = runner.v4_bridge.validate_bridge(
                bridge_path, revalidate_source=True
            )
            shipment_rows = runner._import_v4_holdout_shipment_rows(  # noqa: SLF001
                bridge_path=bridge_path,
                bridge=bridge,
                points=manifest["states"],
                lanes=lanes,
            )
            validated = campaign_v8.validate_v8_target_registry_payload(
                registry,
                manifest=manifest,
                lanes=lanes,
                shipment_rows_by_state_seed=shipment_rows,
            )
    except V8FinalizerAdapterError:
        raise
    except Exception as exc:
        raise V8FinalizerAdapterError(
            "V8 target registry does not replay from the 90 signed traces"
        ) from exc
    if (
        validated.get("target_cell_count") != EXPECTED_TARGET_COUNT
        or validated.get("required_comparable_seed_count")
        != REQUIRED_COMPARABLE_SEED_COUNT
        or validated.get("target_selection_engine_runs") != 0
        or validated.get("incident_outcomes_used") is not False
    ):
        raise V8FinalizerAdapterError("V8 target-selection guarantees changed")
    return validated


def _validate_v8_progress(
    progress: Mapping[str, Any], *, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    _assert_no_design_seed_aliases(progress, label="V8 target-selection progress")
    if (
        progress.get("schema_version") != TARGET_PROGRESS_SCHEMA_VERSION
        or progress.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or progress.get("campaign_signature") != manifest.get("campaign_signature")
        or progress.get("status") != "complete"
        or progress.get("engine_runs_planned") != 0
        or progress.get("engine_runs_completed") != 0
        or progress.get("engine_runs_failed") != 0
        or progress.get("target_selection_engine_runs") != 0
        or progress.get("signed_v7_service_proofs_imported")
        != EXPECTED_SOURCE_TRACE_COUNT
        or progress.get("signed_v7_shipment_traces_imported")
        != EXPECTED_SOURCE_TRACE_COUNT
        or progress.get("state_validation_engine_runs") != 0
        or progress.get("incident_outcomes_used") is not False
        or progress.get("incident_probes_started") is not False
        or progress.get("required_comparable_seed_count")
        != REQUIRED_COMPARABLE_SEED_COUNT
        or progress.get("state_validation_binding_status")
        != implementation_v4.PREFLIGHT_ACCEPTED_STATUS
        or manifest.get("target_discovery_status") != "complete"
        or manifest.get("target_exposure_comparability_status")
        != "accepted_30_of_30"
    ):
        raise V8FinalizerAdapterError("V8 zero-run target selection is incomplete")
    return dict(progress)


def _validate_v8_signed_context(
    evidence: Any, manifest: Mapping[str, Any]
) -> Any:
    """Build the mature V4 context from genuine V8 selection evidence."""

    if manifest.get("schema_version") != implementation_v4.INPUT_CAMPAIGN_SCHEMA_VERSION:
        raise V8FinalizerAdapterError("Unsupported V8 campaign schema")
    if not implementation_v4._is_sha256(  # noqa: SLF001
        manifest.get("campaign_signature")
    ) or not implementation_v4._is_sha256(manifest.get("engine_sha256")):  # noqa: SLF001
        raise V8FinalizerAdapterError("Campaign and engine SHA-256 are required")
    implementation_v4._verify_manifest_signature(manifest)  # noqa: SLF001
    provenance = implementation_v4._validate_operating_point_provenance(  # noqa: SLF001
        evidence, manifest
    )
    if (
        manifest.get("contract_revision") != campaign_v8.implementation_v4.CONTRACT_REVISION
        or manifest.get("target_selection_revision") != TARGET_SELECTION_REVISION
    ):
        raise V8FinalizerAdapterError("Unexpected V8 campaign/selection revision")

    adaptive = manifest.get("adaptive_horizon_contract")
    target_contract = manifest.get("target_discovery_contract")
    target_selection = manifest.get("target_selection")
    target_cohort = manifest.get("v8_target_selection_cohort")
    preflight_contract = manifest.get("operating_point_preflight_contract")
    if not isinstance(adaptive, Mapping) or adaptive.get(
        "fixed_upper_bound_assumed"
    ) is not False:
        raise V8FinalizerAdapterError("V8 adaptive-horizon contract changed")
    if not isinstance(target_contract, Mapping) or not isinstance(
        target_selection, Mapping
    ):
        raise V8FinalizerAdapterError("V8 target-selection contracts are missing")
    if not isinstance(target_cohort, Mapping) or not isinstance(
        preflight_contract, Mapping
    ):
        raise V8FinalizerAdapterError("V8 target cohort/preflight contracts are missing")
    _assert_no_design_seed_aliases(target_contract, label="manifest target contract")
    _assert_no_design_seed_aliases(target_selection, label="manifest target selection")
    _assert_no_design_seed_aliases(target_cohort, label="manifest target cohort")
    _assert_no_design_seed_aliases(preflight_contract, label="manifest preflight")
    if (
        target_contract.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or target_contract.get("campaign_seeds")
        != list(trace_package.CAMPAIGN_SEEDS)
        or target_contract.get("disruption_window_days")
        != DISRUPTION_WINDOW_DAYS
        or target_contract.get("candidate_start_day_min")
        != MIN_FIXED_WINDOW_START_DAY
        or target_contract.get("candidate_start_day_max")
        != MAX_FIXED_WINDOW_START_DAY
        or target_contract.get("required_comparable_seed_count")
        != REQUIRED_COMPARABLE_SEED_COUNT
        or target_contract.get("target_selection_engine_runs") != 0
        or target_contract.get("source_trace_count") != EXPECTED_SOURCE_TRACE_COUNT
        or target_contract.get("exposure_quantity_field")
        != campaign_v8.EXPOSURE_QUANTITY_FIELD
        or target_contract.get("selection_uses_incident_outcomes") is not False
        or target_contract.get("same_lane_specific_dates_across_states_and_campaign_seeds")
        is not True
        or not math.isclose(
            float(target_contract.get("quantity_ratio_limit", math.nan)),
            QUANTITY_RATIO_LIMIT,
            rel_tol=0.0,
            abs_tol=implementation_v4.NUMERIC_TOLERANCE,
        )
        or target_selection.get("selection_rule")
        != "earliest_fully_comparable_42_day_window_on_or_after_J180"
        or target_selection.get("incident_outcomes_used") is not False
        or target_selection.get("new_engine_runs") != 0
        or target_selection.get("reference_kind")
        != implementation_v4.TARGET_REFERENCE_KIND
        or target_selection.get("target_claim")
        != "fixed_conditional_supplier_stress_window_not_observed_incident"
        or manifest.get("target_selection_engine_runs") != 0
        or target_cohort.get("campaign_baselines_used_for_exposure_stratification")
        != list(trace_package.CAMPAIGN_SEEDS)
        or target_cohort.get("source_trace_count") != EXPECTED_SOURCE_TRACE_COUNT
        or target_cohort.get("reserved_target_design_cohort_used") is not False
        or target_cohort.get("incident_outcomes_used") is not False
        or preflight_contract.get("target_selection_engine_runs") != 0
        or preflight_contract.get("imported_shipment_trace_count")
        != EXPECTED_SOURCE_TRACE_COUNT
        or preflight_contract.get("incident_outcomes_used_for_target_selection")
        is not False
        or manifest.get("operating_points_scientific_producer")
        != "v7_fixed_triplet_confirmation_bridge"
        or manifest.get("scientific_provenance_v7")
        != provenance.get("scientific_provenance_v7")
    ):
        raise V8FinalizerAdapterError("V8 30/30 target-selection contract changed")

    for flag in (
        "quality_branch_included",
        "quality_incident_included",
        "availability_incident_included",
        "capacity_incident_included",
        "stock_incident_included",
        "supplier_state_dependent_risks_enabled",
        "historical_incident_probability_estimated",
        "all_lots_traced_claimed",
    ):
        if manifest.get(flag) is not False:
            raise V8FinalizerAdapterError(f"Manifest must declare {flag}=false")

    mechanisms = manifest.get("mechanisms")
    if not isinstance(mechanisms, list) or {
        str(row.get("key") or "") for row in mechanisms if isinstance(row, Mapping)
    } != set(implementation_v4.MECHANISMS):
        raise V8FinalizerAdapterError("V8 requires exactly the two incident mechanisms")
    for row in mechanisms:
        key = str(row["key"])
        expected = implementation_v4.MECHANISM_CONTRACT[key]
        if row.get("risk_type") != expected["risk_type"] or not math.isclose(
            float(row.get("value", math.nan)),
            expected["risk_value"],
            rel_tol=0.0,
            abs_tol=implementation_v4.NUMERIC_TOLERANCE,
        ):
            raise V8FinalizerAdapterError("V8 incident mechanism changed")

    state_rows = manifest.get("states")
    if not isinstance(state_rows, list) or [
        row.get("operating_point_id") for row in state_rows
    ] != list(implementation_v4.OPERATING_POINTS):
        raise V8FinalizerAdapterError("Three ordered V8 operating states are required")
    lane_rows = manifest.get("lanes")
    if not isinstance(lane_rows, list) or len(lane_rows) != implementation_v4.EXPECTED_LANE_COUNT:
        raise V8FinalizerAdapterError("Exactly 18 physical V8 lanes are required")
    lane_identity: dict[str, tuple[str, str, str, str, str]] = {}
    for row in lane_rows:
        lane_id = str(row.get("lane_id") or "")
        identity = tuple(
            str(row.get(field) or "")
            for field in (
                "supplier_id",
                "item_id",
                "dst_node_id",
                "edge_id",
                "target_product_id",
            )
        )
        if not lane_id or lane_id in lane_identity or not all(identity):
            raise V8FinalizerAdapterError("V8 lane identities are incomplete/duplicated")
        lane_identity[lane_id] = identity  # type: ignore[assignment]
    if tuple(manifest.get("seeds") or ()) != trace_package.CAMPAIGN_SEEDS:
        raise V8FinalizerAdapterError("The exact 30 V7 campaign seeds are required")
    # This field is a byte-for-byte projection of the signed V7 source bridge.
    # Its legacy names are historical provenance, never a V8 selection contract.
    if manifest.get("operating_points_cohorts") != provenance.get("cohorts"):
        raise V8FinalizerAdapterError("V7 source-cohort projection changed")

    counts = manifest.get("expected_counts")
    required_counts = {
        "auxiliary_discovery_runs": 0,
        "design_window_engine_runs": 0,
        "target_selection_engine_runs": 0,
        "operating_point_validation_engine_runs": 0,
        "imported_v7_campaign_baseline_service_proofs": 90,
        "imported_v7_campaign_baseline_shipment_traces": 90,
        "baseline_rows": implementation_v4.EXPECTED_BASELINE_COUNT,
        "incident_rows": implementation_v4.EXPECTED_INCIDENT_COUNT,
        "total_rows": implementation_v4.EXPECTED_TOTAL_COUNT,
        "shard_count": implementation_v4.EXPECTED_SHARD_COUNT,
        "rows_per_shard": implementation_v4.EXPECTED_ROWS_PER_SHARD,
    }
    if not isinstance(counts, Mapping) or any(
        counts.get(key) != value for key, value in required_counts.items()
    ):
        raise V8FinalizerAdapterError("V8 manifest evidence counts changed")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != implementation_v4.EXPECTED_SHARD_COUNT:
        raise V8FinalizerAdapterError("Exactly 18 V8 shard definitions are required")
    shard_ids = frozenset(str(row.get("shard_id") or "") for row in shards)
    if "" in shard_ids or len(shard_ids) != implementation_v4.EXPECTED_SHARD_COUNT:
        raise V8FinalizerAdapterError("V8 shard ids are incomplete/duplicated")

    binding_path = implementation_v4._resolve_signed_artifact(  # noqa: SLF001
        evidence=evidence,
        manifest=manifest,
        path_key="state_validation_binding",
        sha_key="state_validation_binding_sha256",
        fallback_name="state_validation_binding.json",
    )
    binding = implementation_v4._read_json(binding_path)  # noqa: SLF001
    binding_signature = _verify_signed_payload(
        binding, "binding_signature", label="V8 state-validation binding"
    )
    _assert_no_design_seed_aliases(binding, label="V8 state-validation binding")
    if (
        binding.get("schema_version")
        != campaign_v8.STATE_VALIDATION_BINDING_SCHEMA_VERSION
        or binding.get("contract_revision") != manifest.get("contract_revision")
        or binding.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or binding.get("campaign_signature") != manifest.get("campaign_signature")
        or binding.get("status") != implementation_v4.PREFLIGHT_ACCEPTED_STATUS
        or binding_signature != manifest.get("state_validation_binding_signature")
        or binding.get("operating_points_artifact_signature")
        != provenance.get("artifact_signature")
        or binding.get("v7_plan_signature") != provenance.get("plan_signature")
        or binding.get("v7_campaign_trace_selection_signature")
        != provenance.get("selection_signature")
        or binding.get("v7_validation_result_signature")
        != provenance.get("holdout_signature")
        or binding.get("v7_campaign_trace_index_signature")
        != provenance.get("trace_index_signature")
        or binding.get("scientific_provenance_v7")
        != provenance.get("scientific_provenance_v7")
        or binding.get("campaign_seeds") != list(trace_package.CAMPAIGN_SEEDS)
        or binding.get("state_validation_engine_runs_in_campaign") != 0
        or binding.get("target_selection_engine_runs") != 0
        or binding.get("target_selection_source_trace_count") != 90
        or binding.get("target_selection_source_seed_count") != 30
        or binding.get("target_selection_uses_incident_outcomes") is not False
        or binding.get("target_selection_uses_reserved_seed") is not False
        or binding.get("imported_official_service_proof_count") != 90
        or binding.get("imported_official_shipment_trace_count") != 90
        or binding.get("retuning_after_holdout") is not False
        or manifest.get("state_validation_binding_status")
        != implementation_v4.PREFLIGHT_ACCEPTED_STATUS
    ):
        raise V8FinalizerAdapterError("Accepted V8 state binding is inconsistent")
    achieved_services = implementation_v4._achieved_services_from_v4_binding(  # noqa: SLF001
        binding, manifest
    )

    registry_path = implementation_v4._resolve_signed_artifact(  # noqa: SLF001
        evidence=evidence,
        manifest=manifest,
        path_key="target_registry",
        sha_key="target_registry_sha256",
        fallback_name="target_registry.json",
    )
    registry = implementation_v4._read_json(registry_path)  # noqa: SLF001
    _validate_v8_registry(registry, manifest=manifest, lane_identity=lane_identity)
    progress_path = evidence.manifest_path.parent / "target_discovery" / "progress.json"
    if not progress_path.is_file():
        raise V8FinalizerAdapterError("V8 target-selection progress is missing")
    progress = implementation_v4._read_json(progress_path)  # noqa: SLF001
    _validate_v8_progress(progress, manifest=manifest)
    provenance = {
        **provenance,
        "target_selection_v8": {
            "target_selection_revision": TARGET_SELECTION_REVISION,
            "source_trace_count": EXPECTED_SOURCE_TRACE_COUNT,
            "target_selection_engine_runs": 0,
            "incident_outcomes_used": False,
            "required_comparable_seed_count": REQUIRED_COMPARABLE_SEED_COUNT,
            "minimum_fixed_window_start_day": MIN_FIXED_WINDOW_START_DAY,
            "disruption_window_days": DISRUPTION_WINDOW_DAYS,
            "registry_signature": registry["registry_signature"],
        },
    }
    return implementation_v4.SignedCampaignContext(
        manifest=manifest,
        operating_point_provenance=provenance,
        preflight=binding,
        registry=registry,
        achieved_services=achieved_services,
        lane_identity=lane_identity,
        shard_ids=shard_ids,
        disruption_window_days=DISRUPTION_WINDOW_DAYS,
        preflight_path=binding_path,
        registry_path=registry_path,
        discovery_progress_path=progress_path,
    )


def _v8_business_limits(disruption_window_days: int) -> list[dict[str, str]]:
    limits = _ORIGINAL_BUSINESS_LIMITS(disruption_window_days)
    replacement = {
        "fenetre_fournisseur": (
            f"HYPOTHÈSE : pour chaque voie, la fenêtre de {disruption_window_days} jours "
            "est la première fenêtre à partir de J180 où un flux normalement livrable "
            "existe dans les trois états et dans les 30 répétitions, avec un rapport de "
            "quantité entre états au plus égal à 1,5. Elle est choisie sur les 90 traces "
            "normales signées, sans résultat d'incident et sans nouvelle simulation. Ce "
            "choix conditionne les résultats : il ne représente ni une date d'incident "
            "historique, ni une fréquence, ni la période la plus pénalisante."
        ),
        "signal_fournisseur": (
            "SIGNAL DE PRIORITÉ conditionnel à la fenêtre comparable testée : le rang "
            "combine la structure du réseau, la dose physique et le contexte calendaire. "
            "Un fournisseur est représenté par la voie testée dont l'effet simulé est le "
            "plus fort; ce n'est ni une note de performance observée ni la preuve d'un "
            "problème récurrent."
        ),
    }
    return [
        {**row, "limit": replacement.get(str(row.get("topic")), str(row.get("limit")))}
        for row in limits
    ]


def validate_frozen_implementation() -> Path:
    try:
        trace_package.validate_frozen_v7_protocol()
        adapter_path = Path(adapter_v7.__file__).resolve()
        digest = adapter_v7.implementation_v4._sha256(adapter_path)  # noqa: SLF001
        if digest != EXPECTED_V7_FINALIZER_SHA256:
            raise V8FinalizerAdapterError(
                f"Frozen V7 finalizer adapter changed: {digest}"
            )
        parent = adapter_v7.validate_frozen_implementation()
        campaign_v8.validate_frozen_implementation()
    except V8FinalizerAdapterError:
        raise
    except Exception as exc:
        raise V8FinalizerAdapterError(
            "Frozen V7/V8 finalization dependency validation failed"
        ) from exc
    if not V8_CAMPAIGN_RUNNER.is_file():
        raise V8FinalizerAdapterError(f"Missing V8 campaign runner: {V8_CAMPAIGN_RUNNER}")
    return parent


@contextmanager
def patched_v8_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_hash: Any = implementation_v4.SOURCE_RUNNER_SHA256
    previous_seeds: Any = implementation_v4.EXPECTED_SEEDS
    previous_provenance: Any = implementation_v4._validate_operating_point_provenance  # noqa: SLF001
    previous_context: Any = implementation_v4._validate_signed_context  # noqa: SLF001
    previous_limits: Any = implementation_v4._business_limits  # noqa: SLF001
    implementation_v4.v4_bridge = v7_bridge
    implementation_v4.SOURCE_RUNNER_SHA256 = implementation_v4._sha256(  # noqa: SLF001
        V8_CAMPAIGN_RUNNER
    )
    implementation_v4.EXPECTED_SEEDS = trace_package.CAMPAIGN_SEEDS
    implementation_v4._validate_operating_point_provenance = adapter_v7._v7_provenance  # noqa: SLF001
    implementation_v4._validate_signed_context = _validate_v8_signed_context  # noqa: SLF001
    implementation_v4._business_limits = _v8_business_limits  # noqa: SLF001
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.SOURCE_RUNNER_SHA256 = previous_hash
        implementation_v4.EXPECTED_SEEDS = previous_seeds
        implementation_v4._validate_operating_point_provenance = previous_provenance  # noqa: SLF001
        implementation_v4._validate_signed_context = previous_context  # noqa: SLF001
        implementation_v4._business_limits = previous_limits  # noqa: SLF001


def _overlay_payload(campaign_root: Path, output_dir: Path) -> dict[str, Any]:
    campaign_root = campaign_root.resolve()
    output_dir = output_dir.resolve()
    base_path = output_dir / "campaign_validation.json"
    binding_path = output_dir / "state_validation_binding.json"
    registry_copy_path = output_dir / "cross_state_target_registry.json"
    manifest_path = campaign_root / "campaign_manifest.json"
    progress_path = campaign_root / "target_discovery" / "progress.json"
    base = implementation_v4._read_json(base_path)  # noqa: SLF001
    binding = implementation_v4._read_json(binding_path)  # noqa: SLF001
    registry = implementation_v4._read_json(registry_copy_path)  # noqa: SLF001
    manifest = implementation_v4._read_json(manifest_path)  # noqa: SLF001
    progress = implementation_v4._read_json(progress_path)  # noqa: SLF001
    _verify_signed_payload(binding, "binding_signature", label="V8 final binding")
    _verify_signed_payload(registry, "registry_signature", label="V8 final registry")
    implementation_v4._verify_manifest_signature(manifest)  # noqa: SLF001
    _assert_no_design_seed_aliases(binding, label="published V8 binding")
    _validate_v8_progress(progress, manifest=manifest)
    provenance = (base.get("inputs") or {}).get("operating_point_provenance") or {}
    science = binding.get("scientific_provenance_v7") or {}
    expected = base.get("expected_contract") or {}
    comparisons = base.get("comparability_checks") or {}
    if (
        base.get("status") != "complete_validated"
        or Path(str((base.get("inputs") or {}).get("campaign_manifest") or "")).resolve()
        != manifest_path
        or (base.get("inputs") or {}).get("campaign_manifest_sha256")
        != implementation_v4._sha256(manifest_path)  # noqa: SLF001
        or provenance.get("producer") != "v7_fixed_triplet_confirmation_bridge"
        or provenance.get("scientific_provenance_v7") != science
        or provenance.get("target_selection_v8", {}).get("registry_signature")
        != registry.get("registry_signature")
        or science.get("scientific_authorization")
        != "accepted_official_v7_fixed_triplet_confirmation"
        or science.get("validation_seed_count") != 150
        or science.get("fresh_validation_case_count") != 450
        or science.get("campaign_baseline_seed_count") != 30
        or science.get("campaign_baseline_trace_count") != 90
        or expected.get("repetition_ids") != list(trace_package.CAMPAIGN_SEEDS)
        or expected.get("baseline_row_count") != 90
        or expected.get("incident_row_count") != 3_240
        or expected.get("mechanisms")
        != ["transport_delay", "planned_delivery_shortfall"]
        or expected.get("quality_branch_included") is not False
        or expected.get("availability_incident_included") is not False
        or comparisons.get("complete_3x18x2x30_matrix") is not True
        or comparisons.get("all_3330_metrics_reconstructed_from_signed_case_evidence")
        is not True
        or comparisons.get("quality_or_availability_incident_count") != 0
        or registry.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or registry.get("required_comparable_seed_count") != 30
        or registry.get("target_selection_engine_runs") != 0
        or registry.get("incident_outcomes_used") is not False
        or progress.get("status") != "complete"
        or progress.get("engine_runs_completed") != 0
        or progress.get("incident_probes_started") is not False
    ):
        raise V8FinalizerAdapterError("Base statistical envelope cannot authorize V8 release")
    _assert_no_design_seed_aliases(registry, label="published V8 registry")
    _assert_no_design_seed_aliases(progress, label="published V8 progress")

    unsigned = {
        "schema_version": V8_RESULT_OVERLAY_SCHEMA_VERSION,
        "status": "complete_validated_v8_overlay",
        "base_campaign_validation": {
            "path": str(base_path),
            "sha256": implementation_v4._sha256(base_path),  # noqa: SLF001
            "schema_version": base["schema_version"],
            "status": base["status"],
            "role": "mature_3330_case_evidence_and_paired_statistics_engine",
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
        "target_registry": {
            "path": str(registry_copy_path),
            "sha256": implementation_v4._sha256(registry_copy_path),  # noqa: SLF001
            "registry_signature": registry["registry_signature"],
        },
        "target_selection_progress": {
            "path": str(progress_path),
            "sha256": implementation_v4._sha256(progress_path),  # noqa: SLF001
        },
        "scientific_provenance_v7": science,
        "target_selection_v8": {
            "revision": TARGET_SELECTION_REVISION,
            "source": "90_signed_v7_paired_baseline_shipment_traces",
            "source_trace_count": 90,
            "incident_outcomes_used": False,
            "additional_simulation_engine_runs": 0,
            "window_days": 42,
            "earliest_candidate_day": 180,
            "latest_candidate_day": 678,
            "required_comparable_seed_count_per_lane": 30,
            "campaign_seed_count": 30,
            "operating_state_count": 3,
            "lane_count": 18,
            "target_cell_count": 1_620,
            "maximum_within_seed_cross_state_quantity_ratio": 1.5,
            "positive_normally_deliverable_quantity_required": True,
            "same_lane_window_across_all_states_and_seeds": True,
            "historical_incident_probability_estimated": False,
        },
        "v8_comparability_checks": {
            "accepted_v7_confirmation_150_seeds_450_cases": True,
            "first30_v7_seed_baselines_used_for_pairing_and_exposure_stratification": True,
            "same_30_seeds_for_baseline_and_incidents": True,
            "all_18_lanes_comparable_on_all_30_seeds": True,
            "selection_uses_incident_outcomes": False,
            "selection_engine_run_count": 0,
            "complete_3330_case_matrix_reconstructed": True,
            "quality_capacity_availability_stock_or_state_risk_incident_count": 0,
        },
        "statistical_semantics": {
            "exposure_comparability_gate": "30_of_30_seeds_for_every_lane",
            "effect_detection_rule": (
                "separate mature statistical rule: paired CI95 lower bound > 0 and "
                "at least 24 of 30 positive paired effects"
            ),
            "the_24_of_30_rule_is_an_exposure_gate": False,
            "the_30_of_30_exposure_rule_is_an_incident_probability": False,
        },
        "legacy_reader_scope": {
            "v4_shaped_base_result_role": "reader_compatibility_and_mature_statistics_only",
            "manifest_operating_points_cohorts_role": "verbatim_signed_V7_source_provenance",
            "legacy_reserved_seed_was_used_by_v8_target_selection": False,
            "legacy_v4_names_are_v8_target_selection_evidence": False,
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


def validate_v8_overlay(campaign_root: Path, output_dir: Path) -> dict[str, Any]:
    expected = _overlay_payload(campaign_root, output_dir)
    path = output_dir.resolve() / V8_RESULT_OVERLAY_NAME
    actual = implementation_v4._read_json(path)  # noqa: SLF001
    _verify_signed_payload(actual, "overlay_signature", label="V8 result overlay")
    if actual != expected:
        raise V8FinalizerAdapterError("V8 result overlay differs from signed sources")
    return actual


def write_v8_overlay(
    campaign_root: Path,
    output_dir: Path,
    *,
    validated_base: Mapping[str, Any],
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    path = output_dir / V8_RESULT_OVERLAY_NAME
    if path.exists():
        return validate_v8_overlay(campaign_root, output_dir)
    base_path = output_dir / "campaign_validation.json"
    if implementation_v4._read_json(base_path) != dict(validated_base):  # noqa: SLF001
        raise V8FinalizerAdapterError(
            "Compatibility result differs from the just-validated in-memory result"
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
    return validate_v8_overlay(campaign_root, output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    args = implementation_v4.parse_args(argv)
    try:
        base_path = args.output_dir.resolve() / "campaign_validation.json"
        overlay_path = args.output_dir.resolve() / V8_RESULT_OVERLAY_NAME
        if base_path.is_file():
            if not overlay_path.is_file():
                raise V8FinalizerAdapterError(
                    "A mature result exists without its V8 overlay; refusing to retrofit "
                    "target-selection provenance. Use a new results directory."
                )
            overlay = validate_v8_overlay(args.campaign_root, args.output_dir)
        else:
            with patched_v8_context():
                validated_base = implementation_v4.finalize_campaign(
                    campaign_root=args.campaign_root,
                    manifest_path=args.campaign_manifest,
                    metrics_paths=args.metrics_csv,
                    output_dir=args.output_dir,
                )
            overlay = write_v8_overlay(
                args.campaign_root,
                args.output_dir,
                validated_base=validated_base,
            )
    except (
        implementation_v4.CampaignValidationError,
        V8FinalizerAdapterError,
        FileExistsError,
        OSError,
    ) as exc:
        print(f"CAMPAGNE V8 INVALIDE : {exc}")
        return 2
    print(json.dumps(overlay, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
