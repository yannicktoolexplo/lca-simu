#!/usr/bin/env python3
"""Validate and consolidate the additive V4 adaptive supplier campaign.

The signed campaign uses the accepted fresh V4 operating points and compact
holdout shipment traces: a lane-specific calendar disruption
window frozen on an independent design seed, a fixed 360-day business envelope and a
fully observed causal window.  This finalizer never executes the simulation
engine.  It validates the complete paired matrix and writes compact, offline
statistics only.

Supplier results are deliberately phrased as results for the *most exposed
tested lane*.  They are conditional simulations, not observations of supplier
quality and not estimates of historical incident probability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v4 as v4_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as v4_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4 as v4_runner,
)

SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v4.finalizer.v1"
INPUT_CAMPAIGN_SCHEMA_VERSION = v4_contract.CAMPAIGN_SCHEMA_VERSION
INPUT_METRIC_SCHEMA_VERSION = v4_contract.CASE_SCHEMA_VERSION
OPERATING_POINTS = ("op_100", "op_93", "op_80")
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
MECHANISM_CONTRACT = {
    "transport_delay": {"risk_type": "lead_time_extra_days", "risk_value": 120.0},
    "planned_delivery_shortfall": {"risk_type": "reliability", "risk_value": 0.5},
}
TARGET_REFERENCE_KIND = (
    "paired_simulated_baseline_shipment_not_observed_supplier_performance"
)
EXPECTED_SEEDS = v4_contract.CAMPAIGN_SEEDS
EXPECTED_LANE_COUNT = 18
EXPECTED_REPETITION_COUNT = 30
EXPECTED_SHARD_COUNT = 18
EXPECTED_ROWS_PER_SHARD = 185
EXPECTED_BASELINE_COUNT = len(OPERATING_POINTS) * EXPECTED_REPETITION_COUNT
EXPECTED_INCIDENT_COUNT = (
    len(OPERATING_POINTS)
    * EXPECTED_LANE_COUNT
    * len(MECHANISMS)
    * EXPECTED_REPETITION_COUNT
)
EXPECTED_TOTAL_COUNT = EXPECTED_BASELINE_COUNT + EXPECTED_INCIDENT_COUNT
STATE_EVALUATION_DAYS = 720
BUSINESS_WINDOW_DAYS = 360
DESIGN_SEED = v4_contract.INCIDENT_DESIGN_SEED
PREFLIGHT_ACCEPTED_STATUS = "accepted_v4_holdout_bound_no_rerun"
SOURCE_RUNNER_SHA256 = (
    "3bc8795490c6ef9ac1fef25d5dedb22811306ae869477df57e70d483881a5d9d"
)
MIN_COMPARABLE_SEEDS = 24
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260905
ROBUST_TOP3_PROBABILITY = 0.80
CONTENDER_TOP3_PROBABILITY = 0.20
NUMERIC_TOLERANCE = 1e-9
REGISTRY_NUMERIC_TOLERANCE = 1e-12
SUPPLEMENTARY_BACKLOG_METRIC = "impact_backlog_qty_days_per_demand_unit"
FORBIDDEN_TOKENS = ("quality", "availability", "capacity", "stock")
UNSIGNED_MANIFEST_RUNTIME_FIELDS = frozenset(
    {
        "campaign_signature",
        "status",
        "created_at_utc",
        "completed_at_utc",
        "target_discovery_status",
        "target_registry",
        "target_registry_sha256",
        "target_registry_signature",
        "target_exposure_comparability_status",
        "state_validation_binding",
        "state_validation_binding_sha256",
        "state_validation_binding_signature",
        "state_validation_binding_status",
        "target_discovery_completed_at_utc",
    }
)

PRIMARY_METRIC = "impact_service_loss_fed_product_pp"
CAUSAL_RANK_METRIC = "causal_service_loss_fed_product_pp"
STATISTIC_METRICS = (
    PRIMARY_METRIC,
    "impact_service_loss_global_pp",
    "impact_on_due_loss_fed_product_qty",
    "impact_on_due_loss_global_qty",
    "impact_on_due_loss_fed_product_share_of_demand",
    "impact_on_due_loss_global_share_of_demand",
    "impact_backlog_qty_days_delta",
    "impact_backlog_qty_days_per_demand_unit",
    "impact_max_backlog_qty_delta",
    "impact_production_loss_fed_product_qty",
    "impact_production_loss_fed_product_share_of_demand",
    CAUSAL_RANK_METRIC,
    "causal_service_loss_global_pp",
    "causal_on_due_loss_fed_product_qty",
    "causal_on_due_loss_global_qty",
    "causal_on_due_loss_fed_product_share_of_demand",
    "causal_on_due_loss_global_share_of_demand",
    "causal_backlog_qty_days_delta",
    "causal_backlog_qty_days_per_demand_unit",
    "causal_max_backlog_qty_delta",
    "causal_production_loss_fed_product_qty",
    "causal_production_loss_fed_product_share_of_demand",
)

COMMON_REQUIRED_COLUMNS = {
    "schema_version",
    "campaign_signature",
    "engine_sha256",
    "shard_id",
    "operating_point_id",
    "operating_point_service_pct",
    "simulation_days",
    "state_evaluation_days",
    "stage",
    "mechanism",
    "seed",
    "status",
    "valid",
    "case_key",
    "case_signature",
    "baseline_case_signature",
    "warmup_core_state_sha256",
    "summary_sha256",
    "validation_errors",
}
INCIDENT_REQUIRED_COLUMNS = {
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "target_product_id",
    "target_status",
    "target_selection_mode",
    "target_reference_kind",
    "target_shipment_count",
    "target_window_start_day",
    "target_window_end_day",
    "target_window_days",
    "target_planned_qty",
    "target_expected_delivered_qty",
    "target_uom",
    "target_selected_independently_by_operating_point",
    "state_comparison_valid",
    "seed_cross_state_exposure_comparable",
    "comparable_campaign_seed_count",
    "required_comparable_seed_count",
    "impact_window_start_day",
    "impact_window_end_day",
    "impact_window_days",
    "impact_window_fully_observed",
    "causal_window_start_day",
    "causal_window_end_day",
    "causal_window_days",
    "causal_window_defined",
    "causal_window_fully_observed",
    "required_simulation_days",
    "risk_type",
    "risk_value",
    "risk_start_day",
    "risk_end_day",
    "risk_applied_row_count",
    "risk_applied_event_count",
    "incident_physically_exercised",
    "incident_shipment_count",
    "incident_affected_pulled_qty",
    "incident_affected_shipped_qty",
    "quantity_shortfall_qty",
    "arrival_delay_days",
    "incident_effective_dose_qty",
    "incident_effective_dose_qty_days",
    "baseline_impact_service_268091_pct",
    "baseline_impact_service_268967_pct",
    "baseline_impact_service_global_pct",
    "impact_service_268091_pct",
    "impact_service_268967_pct",
    "impact_service_global_pct",
    "impact_service_loss_268091_pp",
    "impact_service_loss_268967_pp",
    "impact_service_loss_global_pp",
    "impact_service_loss_fed_product_pp",
    "baseline_impact_demand_268091_qty",
    "baseline_impact_demand_268967_qty",
    "baseline_impact_demand_global_qty",
    "impact_demand_268091_qty",
    "impact_demand_268967_qty",
    "impact_demand_global_qty",
    "impact_on_due_loss_fed_product_qty",
    "impact_on_due_loss_global_qty",
    "impact_on_due_loss_fed_product_share_of_demand",
    "impact_on_due_loss_global_share_of_demand",
    "impact_backlog_qty_days_delta",
    "impact_backlog_qty_days_per_demand_unit",
    "impact_max_backlog_qty_delta",
    "impact_production_loss_fed_product_qty",
    "impact_production_loss_fed_product_share_of_demand",
    "baseline_causal_service_268091_pct",
    "baseline_causal_service_268967_pct",
    "baseline_causal_service_global_pct",
    "causal_service_268091_pct",
    "causal_service_268967_pct",
    "causal_service_global_pct",
    "causal_service_loss_268091_pp",
    "causal_service_loss_268967_pp",
    "causal_service_loss_global_pp",
    "causal_service_loss_fed_product_pp",
    "baseline_causal_demand_268091_qty",
    "baseline_causal_demand_268967_qty",
    "baseline_causal_demand_global_qty",
    "causal_demand_268091_qty",
    "causal_demand_268967_qty",
    "causal_demand_global_qty",
    "causal_on_due_loss_fed_product_qty",
    "causal_on_due_loss_global_qty",
    "causal_on_due_loss_fed_product_share_of_demand",
    "causal_on_due_loss_global_share_of_demand",
    "causal_backlog_qty_days_delta",
    "causal_backlog_qty_days_per_demand_unit",
    "causal_max_backlog_qty_delta",
    "causal_production_loss_fed_product_qty",
    "causal_production_loss_fed_product_share_of_demand",
}
REQUIRED_COLUMNS = COMMON_REQUIRED_COLUMNS | INCIDENT_REQUIRED_COLUMNS

INCIDENT_NUMERIC_COLUMNS = {
    "target_shipment_count",
    "target_window_start_day",
    "target_window_end_day",
    "target_window_days",
    "target_planned_qty",
    "target_expected_delivered_qty",
    "comparable_campaign_seed_count",
    "required_comparable_seed_count",
    "impact_window_start_day",
    "impact_window_end_day",
    "impact_window_days",
    "causal_window_start_day",
    "causal_window_end_day",
    "causal_window_days",
    "required_simulation_days",
    "risk_value",
    "risk_start_day",
    "risk_end_day",
    "risk_applied_row_count",
    "risk_applied_event_count",
    "incident_shipment_count",
    "incident_affected_pulled_qty",
    "incident_affected_shipped_qty",
    "quantity_shortfall_qty",
    "arrival_delay_days",
    "baseline_impact_service_268091_pct",
    "baseline_impact_service_268967_pct",
    "baseline_impact_service_global_pct",
    "impact_service_268091_pct",
    "impact_service_268967_pct",
    "impact_service_global_pct",
    "impact_service_loss_268091_pp",
    "impact_service_loss_268967_pp",
    "impact_service_loss_global_pp",
    "impact_service_loss_fed_product_pp",
    "baseline_impact_demand_268091_qty",
    "baseline_impact_demand_268967_qty",
    "baseline_impact_demand_global_qty",
    "impact_demand_268091_qty",
    "impact_demand_268967_qty",
    "impact_demand_global_qty",
    "impact_on_due_loss_fed_product_qty",
    "impact_on_due_loss_global_qty",
    "impact_on_due_loss_fed_product_share_of_demand",
    "impact_on_due_loss_global_share_of_demand",
    "impact_backlog_qty_days_delta",
    "impact_backlog_qty_days_per_demand_unit",
    "impact_max_backlog_qty_delta",
    "impact_production_loss_fed_product_qty",
    "impact_production_loss_fed_product_share_of_demand",
    "baseline_causal_service_268091_pct",
    "baseline_causal_service_268967_pct",
    "baseline_causal_service_global_pct",
    "causal_service_268091_pct",
    "causal_service_268967_pct",
    "causal_service_global_pct",
    "causal_service_loss_268091_pp",
    "causal_service_loss_268967_pp",
    "causal_service_loss_global_pp",
    "causal_service_loss_fed_product_pp",
    "baseline_causal_demand_268091_qty",
    "baseline_causal_demand_268967_qty",
    "baseline_causal_demand_global_qty",
    "causal_demand_268091_qty",
    "causal_demand_268967_qty",
    "causal_demand_global_qty",
    "causal_on_due_loss_fed_product_qty",
    "causal_on_due_loss_global_qty",
    "causal_on_due_loss_fed_product_share_of_demand",
    "causal_on_due_loss_global_share_of_demand",
    "causal_backlog_qty_days_delta",
    "causal_backlog_qty_days_per_demand_unit",
    "causal_max_backlog_qty_delta",
    "causal_production_loss_fed_product_qty",
    "causal_production_loss_fed_product_share_of_demand",
}


class CampaignValidationError(ValueError):
    """Raised when the campaign cannot support the advertised comparison."""


@dataclass(frozen=True)
class InputEvidence:
    manifest_path: Path
    metrics_paths: tuple[Path, ...]
    manifest_sha256: str
    metrics_sha256: Mapping[str, str]


@dataclass(frozen=True)
class SignedCampaignContext:
    manifest: Mapping[str, Any]
    operating_point_provenance: Mapping[str, Any]
    preflight: Mapping[str, Any]
    registry: Mapping[str, Any]
    achieved_services: Mapping[str, Mapping[str, float]]
    lane_identity: Mapping[str, tuple[str, str, str, str, str]]
    shard_ids: frozenset[str]
    disruption_window_days: int
    preflight_path: Path
    registry_path: Path
    discovery_progress_path: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignValidationError(f"Invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise CampaignValidationError(f"JSON evidence must be an object: {path}")
    return payload


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() not in {"", "nan", "None"}


def _is_sha256(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _normalise_stage(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return {"reference": "baseline", "nominal": "baseline", "stress": "incident"}.get(
        text, text
    )


def _normalise_mechanism(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_")
    return {
        "delay": "transport_delay",
        "lead_time_delay": "transport_delay",
        "reliability": "planned_delivery_shortfall",
        "planned_shortfall": "planned_delivery_shortfall",
        "short_shipment": "planned_delivery_shortfall",
    }.get(text, text)


def _linear_quantile(values: Sequence[float] | np.ndarray, probability: float) -> float:
    array = np.asarray(values, dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return math.nan
    return float(np.quantile(finite, probability, method="linear"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def discover_inputs(
    *,
    campaign_root: Path | None,
    manifest_path: Path | None,
    metrics_paths: Sequence[Path],
) -> InputEvidence:
    root = campaign_root.resolve() if campaign_root is not None else None
    resolved_manifest = (
        manifest_path.resolve()
        if manifest_path is not None
        else (root / "campaign_manifest.json" if root is not None else None)
    )
    if resolved_manifest is None or not resolved_manifest.is_file():
        raise CampaignValidationError("A readable campaign_manifest.json is required")
    candidates = [path.resolve() for path in metrics_paths]
    if root is not None:
        consolidated = root / "campaign_metrics.csv"
        if consolidated.is_file():
            candidates.append(consolidated)
        else:
            candidates.extend(sorted(root.glob("shards/*/campaign_metrics.csv")))
    resolved_metrics = tuple(
        dict.fromkeys(path for path in candidates if path.is_file())
    )
    if not resolved_metrics:
        raise CampaignValidationError("No campaign_metrics.csv input was found")
    return InputEvidence(
        manifest_path=resolved_manifest,
        metrics_paths=resolved_metrics,
        manifest_sha256=_sha256(resolved_manifest),
        metrics_sha256={str(path): _sha256(path) for path in resolved_metrics},
    )


def _read_metrics(paths: Sequence[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        try:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        except (OSError, pd.errors.ParserError) as exc:
            raise CampaignValidationError(f"Cannot read metrics CSV: {path}") from exc
        frame["_source_csv"] = str(path)
        frame["_source_row"] = np.arange(2, len(frame) + 2)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False).fillna("")


def validate_metrics_against_signed_case_evidence(
    *,
    campaign_root: Path,
    metrics_paths: Sequence[Path],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild all 3,330 metric rows from their signed compact case proofs."""

    root = campaign_root.resolve()
    shard_root = (root / "shards").resolve()
    raw_rows: dict[str, dict[str, str]] = {}
    for metrics_path in metrics_paths:
        try:
            handle = metrics_path.open("r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CampaignValidationError(
                f"Cannot read metrics CSV: {metrics_path}"
            ) from exc
        with handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(v4_runner.METRIC_FIELDS):
                raise CampaignValidationError(
                    f"Campaign metric columns changed: {metrics_path}"
                )
            for row in reader:
                case_key = str(row.get("case_key") or "")
                if not case_key or case_key in raw_rows:
                    raise CampaignValidationError(
                        "Campaign metric case keys are empty or duplicated"
                    )
                raw_rows[case_key] = dict(row)
    if len(raw_rows) != EXPECTED_TOTAL_COUNT:
        raise CampaignValidationError(
            "The 3,330 campaign metric rows are required for evidence reconstruction"
        )

    evidence_by_case: dict[str, dict[str, Any]] = {}
    baseline_by_signature: dict[str, dict[str, Any]] = {}
    evidence_hashes: dict[str, str] = {}
    for case_key, row in raw_rows.items():
        shard_id = str(row.get("shard_id") or "")
        evidence_path = (
            shard_root / shard_id / "case_evidence" / f"{case_key}.json"
        ).resolve()
        if (
            not evidence_path.is_relative_to(shard_root)
            or evidence_path.name != f"{case_key}.json"
            or not evidence_path.is_file()
        ):
            raise CampaignValidationError(
                f"Signed campaign case evidence is missing: {case_key}"
            )
        payload = _read_json(evidence_path)
        try:
            v4_runner._validate_evidence(  # noqa: SLF001
                payload,
                manifest=manifest,
                case_key=case_key,
                case_signature=str(row.get("case_signature") or ""),
            )
        except ValueError as exc:
            raise CampaignValidationError(
                f"Signed campaign case evidence is invalid: {case_key}"
            ) from exc
        metrics = payload.get("metrics")
        if (
            payload.get("contract_revision")
            != "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
            or payload.get("shard_id") != shard_id
            or payload.get("valid") is not True
            or payload.get("status") not in {"valid", "valid_no_exposure"}
            or payload.get("validation_errors") != []
            or not isinstance(metrics, Mapping)
            or not _is_sha256(metrics.get("warmup_core_state_sha256"))
            or not _is_sha256(metrics.get("summary_sha256"))
        ):
            raise CampaignValidationError(
                f"Signed campaign case proof fails closed: {case_key}"
            )
        if payload.get("stage") == "incident":
            risk_path = (
                shard_root
                / shard_id
                / "inputs"
                / "risk_events"
                / f"{case_key}.csv"
            ).resolve()
            risk_sha = str(payload.get("risk_csv_sha256") or "")
            if (
                not risk_path.is_relative_to(shard_root)
                or not _is_sha256(risk_sha)
                or not risk_path.is_file()
                or _sha256(risk_path) != risk_sha
            ):
                raise CampaignValidationError(
                    f"Campaign risk CSV proof changed: {case_key}"
                )
        evidence_by_case[case_key] = payload
        evidence_hashes[case_key] = _sha256(evidence_path)
        if payload.get("stage") == "baseline":
            signature = str(payload.get("case_signature") or "")
            if not _is_sha256(signature) or signature in baseline_by_signature:
                raise CampaignValidationError("Baseline case signature is duplicated")
            baseline_by_signature[signature] = payload

    for case_key, row in raw_rows.items():
        rebuilt = v4_runner._flatten_metric_row(  # noqa: SLF001
            evidence_by_case[case_key],
            baseline_by_signature=baseline_by_signature,
        )
        canonical = {
            field: "" if rebuilt.get(field) is None else str(rebuilt.get(field, ""))
            for field in v4_runner.METRIC_FIELDS
        }
        if canonical != row:
            changed = [
                field
                for field in v4_runner.METRIC_FIELDS
                if canonical[field] != row[field]
            ]
            raise CampaignValidationError(
                f"Campaign metric row differs from signed evidence for {case_key}: "
                + ", ".join(changed[:10])
            )
    return {
        "status": "complete_reconstructed",
        "case_count": len(evidence_by_case),
        "baseline_case_count": len(baseline_by_signature),
        "incident_case_count": len(evidence_by_case) - len(baseline_by_signature),
        "evidence_index_sha256": _stable_sha256(evidence_hashes),
    }


def _resolve_signed_artifact(
    *,
    evidence: InputEvidence,
    manifest: Mapping[str, Any],
    path_key: str,
    sha_key: str,
    fallback_name: str,
) -> Path:
    declared = str(manifest.get(path_key) or "").strip()
    candidates: list[Path] = []
    if declared:
        candidate = Path(declared)
        candidates.append(
            candidate
            if candidate.is_absolute()
            else evidence.manifest_path.parent / candidate
        )
    candidates.append(
        evidence.manifest_path.parent / "target_discovery" / fallback_name
    )
    candidates.append(evidence.manifest_path.parent / fallback_name)
    resolved = next((path.resolve() for path in candidates if path.is_file()), None)
    if resolved is None:
        raise CampaignValidationError(
            f"Signed campaign artifact is missing: {fallback_name}"
        )
    expected_sha = str(manifest.get(sha_key) or "").casefold()
    if not _is_sha256(expected_sha) or _sha256(resolved) != expected_sha:
        raise CampaignValidationError(
            f"Signed campaign artifact changed: {fallback_name}"
        )
    return resolved


def _verify_payload_signature(
    payload: Mapping[str, Any], field: str, *, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(field, ""))
    if not _is_sha256(signature) or signature != _stable_sha256(unsigned):
        raise CampaignValidationError(f"Invalid {label} signature")
    return signature


def _verify_manifest_signature(manifest: Mapping[str, Any]) -> None:
    signed_design = {
        key: value
        for key, value in manifest.items()
        if key not in UNSIGNED_MANIFEST_RUNTIME_FIELDS
    }
    if _stable_sha256(signed_design) != manifest.get("campaign_signature"):
        raise CampaignValidationError(
            "Campaign manifest signed design does not match its signature"
        )


def _declared_provenance_path(
    evidence: InputEvidence, manifest: Mapping[str, Any], key: str
) -> Path:
    raw = str(manifest.get(key) or "").strip()
    if not raw:
        raise CampaignValidationError(f"Missing operating-point provenance: {key}")
    candidate = Path(raw)
    resolved = (
        candidate
        if candidate.is_absolute()
        else evidence.manifest_path.parent / candidate
    ).resolve()
    if not resolved.is_file():
        raise CampaignValidationError(
            f"Operating-point provenance file is missing: {key}"
        )
    return resolved


def _matching_declared_sha(manifest: Mapping[str, Any], key: str, path: Path) -> str:
    declared = str(manifest.get(key) or "").strip().casefold()
    actual = _sha256(path)
    if not _is_sha256(declared) or declared != actual:
        raise CampaignValidationError(f"Operating-point provenance hash changed: {key}")
    return actual


def _legacy_validate_operating_point_provenance(
    evidence: InputEvidence, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Revalidate the exact V1/V2/V3 source chain frozen by the runner."""

    selected_path = _declared_provenance_path(
        evidence, manifest, "operating_points_source"
    )
    plan_path = _declared_provenance_path(
        evidence, manifest, "operating_points_calibration_plan"
    )
    selection_path = _declared_provenance_path(
        evidence, manifest, "operating_points_selection"
    )
    selected_sha = _matching_declared_sha(
        manifest, "operating_points_source_sha256", selected_path
    )
    plan_sha = _matching_declared_sha(
        manifest, "operating_points_calibration_plan_sha256", plan_path
    )
    selection_sha = _matching_declared_sha(
        manifest, "operating_points_selection_sha256", selection_path
    )
    selected = _read_json(selected_path)
    plan = _read_json(plan_path)
    selection = _read_json(selection_path)
    artifact_signature = _verify_payload_signature(
        selected, "artifact_signature", label="operating-point source artifact"
    )
    selection_signature = _verify_payload_signature(
        selection, "selection_signature", label="operating-point selection"
    )

    # Lazy import is required: the refinement producer reaches the campaign
    # runner through its prevalidation dependency.
    try:
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_operating_point_full_campaign_v2 as campaign_runner,
        )

        runner_path = Path(campaign_runner.__file__).resolve()
        if _sha256(runner_path) != SOURCE_RUNNER_SHA256:
            raise ValueError("Frozen operating-point source runner hash changed")
        source_chain = campaign_runner._validate_pending_multiseed_source(
            selected_path, selected
        )
    except Exception as exc:
        raise CampaignValidationError(
            "Strict V1/V2/V3 operating-point source validation failed"
        ) from exc
    if not isinstance(source_chain, Mapping):
        raise CampaignValidationError(
            "Operating-point validator returned no source chain"
        )

    declared_plan_signature = str(
        manifest.get("operating_points_calibration_plan_signature") or ""
    )
    declared_selection_signature = str(
        manifest.get("operating_points_selection_signature") or ""
    )
    expected_producer = str(manifest.get("operating_points_producer") or "")
    expected_schema = str(manifest.get("operating_points_schema_version") or "")
    expected_status = str(manifest.get("operating_points_input_status") or "")
    expected_cohorts = manifest.get("operating_points_cohorts")
    expected_holdout = manifest.get("operating_points_holdout_contract")
    source_hashes = selected.get("source_hashes")
    if not isinstance(source_hashes, Mapping):
        raise CampaignValidationError("Operating-point source hashes are missing")
    source_contracts = {
        campaign_runner.V1_POINTS_SCHEMA_VERSION: {
            "status": campaign_runner.V1_POINTS_PENDING_STATUS,
            "producer": "v1_calibration",
            "plan_schema": ("etudecas.multiseed_operating_point_calibration.v1.plan"),
            "plan_status": "planned_not_executed",
            "plan_filename": "calibration_plan.json",
            "selection_schema": (
                "etudecas.multiseed_operating_point_calibration.v1.selection"
            ),
            "selection_status": "calibration_selected",
            "selected_embeds_holdout": False,
        },
        campaign_runner.V2_POINTS_SCHEMA_VERSION: {
            "status": campaign_runner.V2_POINTS_PENDING_STATUS,
            "producer": "v2_refinement",
            "plan_schema": "etudecas.multiseed_operating_point_refinement.v2.plan",
            "plan_status": "planned_not_executed",
            "plan_filename": "refinement_plan.json",
            "selection_schema": (
                "etudecas.multiseed_operating_point_refinement.v2.selection"
            ),
            "selection_status": "five_seed_loo_screen_passed_pending_holdout",
            "selected_embeds_holdout": True,
        },
        campaign_runner.V3_POINTS_SCHEMA_VERSION: {
            "status": campaign_runner.V3_POINTS_PENDING_STATUS,
            "producer": "v3_refinement",
            "plan_schema": "etudecas.multiseed_operating_point_refinement.v3.plan",
            "plan_status": "frozen_before_v3_execution",
            "plan_filename": "refinement_plan.json",
            "selection_schema": (
                "etudecas.multiseed_operating_point_refinement.v3.selection"
            ),
            "selection_status": campaign_runner.V3_SELECTION_PASS_STATUS,
            "selected_embeds_holdout": True,
        },
    }
    source_contract = source_contracts.get(str(selected.get("schema_version") or ""))
    if source_contract is None:
        raise CampaignValidationError("Unsupported operating-point source contract")
    plan_source_hashes = plan.get("source_hashes")
    plan_cohorts = plan.get("cohorts")
    plan_holdout = plan.get("holdout_contract")
    selected_plan_reference = selected.get("plan")
    if not isinstance(selected_plan_reference, Mapping):
        raise CampaignValidationError("Operating-point plan reference is missing")
    selected_plan_dir = Path(str(selected_plan_reference.get("path") or ""))
    if not selected_plan_dir.is_absolute():
        selected_plan_dir = selected_path.parent / selected_plan_dir
    selected_plan_dir = selected_plan_dir.resolve()
    selection_contract = selection.get("selection_contract")
    expected_selection_contract = plan.get("selection_contract")
    selected_pair = selection.get("selected_pair")
    selected_embeds_holdout = bool(source_contract["selected_embeds_holdout"])
    is_v3_source = expected_schema == campaign_runner.V3_POINTS_SCHEMA_VERSION
    v3_upstream = plan.get("source")
    if (
        expected_schema != selected.get("schema_version")
        or expected_schema not in source_contracts
        or expected_status != source_contract["status"]
        or expected_producer != source_contract["producer"]
        or plan.get("schema_version") != source_contract["plan_schema"]
        or plan.get("status") != source_contract["plan_status"]
        or plan_path.name != source_contract["plan_filename"]
        or selected_plan_dir != plan_path.parent.resolve()
        or selected_plan_reference.get("plan_signature") != declared_plan_signature
        or selection.get("schema_version") != source_contract["selection_schema"]
        or selection.get("status") != source_contract["selection_status"]
        or selection.get("plan_signature") != declared_plan_signature
        or selection.get("calibration_seeds") != list(range(340282, 340287))
        or selection.get("holdout_seeds_sealed_and_unread") != list(EXPECTED_SEEDS)
        or selection_contract != expected_selection_contract
        or selection.get("fallback_required") is not False
        or not isinstance(selected_pair, Mapping)
        or source_hashes != plan_source_hashes
        or selected.get("cohorts") != plan_cohorts
        or expected_cohorts != plan_cohorts
        or plan_holdout != expected_holdout
        or selected.get("holdout_validated") is not False
        or selected.get("simulation_hypotheses_not_observed_performance") is not True
        or (
            selected_embeds_holdout
            and (
                selected.get("holdout_contract") != plan_holdout
                or selected.get("holdout_cases_read") != 0
                or selected.get("target_labels_apply_to_global_service_only")
                is not True
                or selection.get("holdout_contract") != plan_holdout
                or selection.get("holdout_cases_read") != 0
                or selection.get("holdout_launch_permitted") is not True
            )
        )
        or Path(str(source_chain.get("plan_manifest_path") or "")).resolve()
        != plan_path
        or Path(str(source_chain.get("selection_path") or "")).resolve()
        != selection_path
        or source_chain.get("plan_signature") != declared_plan_signature
        or plan.get("plan_signature") != declared_plan_signature
        or source_chain.get("selection_signature") != declared_selection_signature
        or selection_signature != declared_selection_signature
        or selected.get("selection_signature") != declared_selection_signature
        or artifact_signature
        != str(manifest.get("operating_points_artifact_signature") or "")
        or source_chain.get("producer") != expected_producer
        or selected.get("schema_version") != expected_schema
        or selected.get("status") != expected_status
        or selected.get("cohorts") != expected_cohorts
        or source_chain.get("holdout_contract") != expected_holdout
        or source_hashes.get("engine_sha256") != manifest.get("engine_sha256")
        or source_hashes.get("profile_sha256") != manifest.get("engine_profile_sha256")
        or (
            is_v3_source
            and source_hashes.get("v3_driver_sha256")
            != campaign_runner.V3_REFINEMENT_MODULE_SHA256
        )
        or (
            is_v3_source
            and (
                not isinstance(v3_upstream, Mapping)
                or v3_upstream.get("v2_no_go_status")
                != "five_seed_loo_screen_failed_no_holdout"
                or plan.get("expected_case_count") != 80
                or plan.get("new_case_count") != 15
                or plan.get("reused_case_count") != 65
            )
        )
    ):
        raise CampaignValidationError(
            "Operating-point source provenance differs from the signed campaign"
        )
    selected_selection_reference = selected.get("selection")
    if selected_embeds_holdout and (
        not isinstance(selected_selection_reference, Mapping)
        or selected_selection_reference.get("relative_path") != "selection.json"
        or selected_selection_reference.get("schema_version")
        != source_contract["selection_schema"]
        or selected_selection_reference.get("selection_signature")
        != declared_selection_signature
    ):
        raise CampaignValidationError("Operating-point selection reference changed")

    source_points = {
        str(row.get("operating_point_id") or ""): row
        for row in selected.get("operating_points") or []
        if isinstance(row, Mapping)
    }
    campaign_states = {
        str(row.get("operating_point_id") or ""): row
        for row in manifest.get("states") or []
        if isinstance(row, Mapping)
    }
    if set(source_points) != set(OPERATING_POINTS) or set(campaign_states) != set(
        OPERATING_POINTS
    ):
        raise CampaignValidationError(
            "Operating-point source/state identities are incomplete"
        )
    metric_pairs = (
        ("target_service", "target_service_pct"),
        ("calibration_pooled_service", "calibration_pooled_service_pct"),
        (
            "calibration_product_268091_service",
            "calibration_product_268091_service_pct",
        ),
        (
            "calibration_product_268967_service",
            "calibration_product_268967_service_pct",
        ),
    )
    graph_hashes: dict[str, str] = {}
    for point_id in OPERATING_POINTS:
        source_point = source_points[point_id]
        state = campaign_states[point_id]
        graph_hash = str(source_point.get("graph_sha256") or "").casefold()
        if (
            not _is_sha256(graph_hash)
            or graph_hash != str(state.get("graph_sha256") or "").casefold()
        ):
            raise CampaignValidationError(
                f"Operating-point graph provenance changed: {point_id}"
            )
        graph_hashes[point_id] = graph_hash
        for source_field, state_field in metric_pairs:
            try:
                source_value = 100.0 * float(source_point[source_field])
                state_value = float(state[state_field])
            except (KeyError, TypeError, ValueError) as exc:
                raise CampaignValidationError(
                    f"Missing operating-point state provenance: {point_id}/{state_field}"
                ) from exc
            if not math.isclose(
                source_value,
                state_value,
                rel_tol=1e-10,
                abs_tol=NUMERIC_TOLERANCE,
            ):
                raise CampaignValidationError(
                    f"Operating-point state projection changed: {point_id}/{state_field}"
                )
    return {
        "producer": expected_producer,
        "schema_version": expected_schema,
        "status": expected_status,
        "selected_points_path": str(selected_path),
        "selected_points_sha256": selected_sha,
        "artifact_signature": artifact_signature,
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha,
        "plan_signature": declared_plan_signature,
        "selection_path": str(selection_path),
        "selection_sha256": selection_sha,
        "selection_signature": selection_signature,
        "plan_schema_version": str(plan.get("schema_version") or ""),
        "plan_status": str(plan.get("status") or ""),
        "selection_schema_version": str(selection.get("schema_version") or ""),
        "selection_status": str(selection.get("status") or ""),
        "source_hashes": dict(source_hashes),
        "calibration_proof_count": int(plan.get("expected_case_count") or 0),
        "upstream_v2_no_go_status": (
            str(v3_upstream.get("v2_no_go_status") or "")
            if isinstance(v3_upstream, Mapping)
            else ""
        ),
        "cohorts": expected_cohorts,
        "holdout_contract": expected_holdout,
        "graph_sha256_by_operating_point": graph_hashes,
    }


# V4 uses a single accepted bridge rather than any pending V1--V3 selection.
def _validate_operating_point_provenance(
    evidence: InputEvidence, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    bridge_path = _declared_provenance_path(
        evidence, manifest, "operating_points_source"
    )
    bridge_sha = _matching_declared_sha(
        manifest, "operating_points_source_sha256", bridge_path
    )
    try:
        bridge = v4_bridge.validate_bridge(bridge_path, revalidate_source=True)
    except Exception as exc:
        raise CampaignValidationError(
            "Accepted V4 operating-point bridge validation failed"
        ) from exc
    source = dict(bridge["source"])
    plan_path = _declared_provenance_path(
        evidence, manifest, "operating_points_calibration_plan"
    )
    selection_path = _declared_provenance_path(
        evidence, manifest, "operating_points_selection"
    )
    holdout_path = _declared_provenance_path(
        evidence, manifest, "operating_points_holdout"
    )
    plan_sha = _matching_declared_sha(
        manifest, "operating_points_calibration_plan_sha256", plan_path
    )
    selection_sha = _matching_declared_sha(
        manifest, "operating_points_selection_sha256", selection_path
    )
    holdout_sha = _matching_declared_sha(
        manifest, "operating_points_holdout_sha256", holdout_path
    )
    runner_path = Path(str(manifest.get("runner") or "")).resolve()
    if (
        not runner_path.is_file()
        or _sha256(runner_path) != SOURCE_RUNNER_SHA256
        or manifest.get("runner_sha256") != SOURCE_RUNNER_SHA256
    ):
        raise CampaignValidationError("Frozen V4 campaign runner hash changed")
    if (
        bridge.get("schema_version") != v4_contract.BRIDGE_SCHEMA_VERSION
        or bridge.get("status") != v4_contract.BRIDGE_ACCEPTED_STATUS
        or bridge.get("artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or bridge.get("cohorts") != manifest.get("operating_points_cohorts")
        or bridge.get("holdout_contract")
        != manifest.get("operating_points_holdout_contract")
        or bridge.get("trace_index_signature")
        != manifest.get("operating_points_trace_index_signature")
        or len(bridge.get("trace_index") or []) != 90
        or manifest.get("operating_points_trace_count") != 90
        or source.get("plan_signature")
        != manifest.get("operating_points_calibration_plan_signature")
        or source.get("development_selection_signature")
        != manifest.get("operating_points_selection_signature")
        or source.get("holdout_signature")
        != manifest.get("operating_points_holdout_signature")
        or Path(str(source.get("plan_manifest") or "")).resolve() != plan_path
        or Path(str(source.get("development_selection") or "")).resolve()
        != selection_path
        or Path(str(source.get("holdout_result") or "")).resolve() != holdout_path
        or source.get("plan_manifest_sha256") != plan_sha
        or source.get("development_selection_sha256") != selection_sha
        or source.get("holdout_result_sha256") != holdout_sha
        or bridge.get("retuning_after_holdout") is not False
        or bridge.get("simulation_hypotheses_not_observed_performance") is not True
    ):
        raise CampaignValidationError(
            "Campaign manifest differs from its accepted V4 bridge provenance"
        )
    point_by_id = {
        str(row.get("operating_point_id") or ""): row
        for row in bridge.get("operating_points") or []
        if isinstance(row, Mapping)
    }
    if set(point_by_id) != set(OPERATING_POINTS):
        raise CampaignValidationError("V4 bridge operating-point inputs are incomplete")
    operating_point_inputs: dict[str, dict[str, Any]] = {}
    for point_id in OPERATING_POINTS:
        point = point_by_id[point_id]
        try:
            offset_091 = float(point["offset_days_268091"])
            offset_967 = float(point["offset_days_268967"])
            degradation_value = point["degradation_value"]
            value_091 = float(degradation_value["offset_days_268091"])
            value_967 = float(degradation_value["offset_days_268967"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CampaignValidationError(
                f"V4 degradation inputs are incomplete: {point_id}"
            ) from exc
        expected_family = (
            "baseline"
            if point_id == "op_100"
            else "balanced_product_supplier_planned_lead"
        )
        if (
            not all(math.isfinite(value) for value in (offset_091, offset_967))
            or not math.isclose(offset_091, value_091, abs_tol=NUMERIC_TOLERANCE)
            or not math.isclose(offset_967, value_967, abs_tol=NUMERIC_TOLERANCE)
            or point.get("degradation_family") != expected_family
            or point.get("degradation_unit")
            != "planned_lead_days_added_by_finished_product_feed"
        ):
            raise CampaignValidationError(
                f"V4 degradation family or offsets changed: {point_id}"
            )
        operating_point_inputs[point_id] = {
            "degradation_family": expected_family,
            "degradation_unit": point["degradation_unit"],
            "offset_days_268091": offset_091,
            "offset_days_268967": offset_967,
        }
    return {
        "producer": "v4_fresh_holdout_bridge",
        "schema_version": bridge["schema_version"],
        "status": bridge["status"],
        "bridge_path": str(bridge_path),
        "bridge_sha256": bridge_sha,
        "artifact_signature": bridge["artifact_signature"],
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha,
        "plan_signature": source["plan_signature"],
        "selection_path": str(selection_path),
        "selection_sha256": selection_sha,
        "selection_signature": source["development_selection_signature"],
        "holdout_path": str(holdout_path),
        "holdout_sha256": holdout_sha,
        "holdout_signature": source["holdout_signature"],
        "trace_index_signature": bridge["trace_index_signature"],
        "trace_count": len(bridge["trace_index"]),
        "source_hashes": bridge["source_hashes"],
        "cohorts": bridge["cohorts"],
        "holdout_contract": bridge["holdout_contract"],
        "graph_sha256_by_operating_point": {
            row["operating_point_id"]: row["graph_sha256"]
            for row in bridge["operating_points"]
        },
        "operating_point_inputs": operating_point_inputs,
    }


def _load_discovery_service_evidence(
    *,
    evidence: InputEvidence,
    manifest: Mapping[str, Any],
    disruption_window_days: int,
) -> dict[tuple[str, int], dict[str, float]]:
    """Verify every discovery case and retain only its service totals."""

    paths = sorted(
        (evidence.manifest_path.parent / "target_discovery" / "evidence").glob("*.json")
    )
    expected_keys = {
        (point, seed)
        for point in OPERATING_POINTS
        for seed in (DESIGN_SEED, *EXPECTED_SEEDS)
    }
    state_by_id = {
        str(row.get("operating_point_id")): row
        for row in manifest.get("states") or []
        if isinstance(row, Mapping)
    }
    if set(state_by_id) != set(OPERATING_POINTS) or len(paths) != len(expected_keys):
        raise CampaignValidationError(
            "The 93 signed target-discovery cases are required"
        )
    result: dict[tuple[str, int], dict[str, float]] = {}
    fields = (
        "demand_qty_global",
        "on_due_qty_global",
        "demand_qty_268091",
        "on_due_qty_268091",
        "demand_qty_268967",
        "on_due_qty_268967",
    )
    for path in paths:
        payload = _read_json(path)
        _verify_payload_signature(
            payload, "evidence_signature", label="target-discovery evidence"
        )
        point = str(payload.get("operating_point_id") or "")
        try:
            seed = int(payload.get("seed"))
        except (TypeError, ValueError) as exc:
            raise CampaignValidationError("Invalid target-discovery seed") from exc
        key = (point, seed)
        if key not in expected_keys or key in result:
            raise CampaignValidationError(
                "Target-discovery case is unexpected or duplicated"
            )
        state = state_by_id[point]
        expected_discovery_signature = _stable_sha256(
            {
                "campaign_signature": manifest["campaign_signature"],
                "engine_sha256": manifest["engine_sha256"],
                "engine_profile_sha256": manifest["engine_profile_sha256"],
                "point_id": point,
                "graph_sha256": state["graph_sha256"],
                "seed": seed,
                "simulation_days": STATE_EVALUATION_DAYS,
                "purpose": f"cross_state_{disruption_window_days}d_target_discovery",
            }
        )
        if (
            payload.get("schema_version")
            != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.target_discovery.case.v1"
            or payload.get("campaign_signature") != manifest.get("campaign_signature")
            or payload.get("engine_sha256") != manifest.get("engine_sha256")
            or payload.get("discovery_signature") != expected_discovery_signature
            or int(payload.get("simulation_days", -1)) != STATE_EVALUATION_DAYS
        ):
            raise CampaignValidationError(
                "Target-discovery case signature or contract differs"
            )
        raw_metrics = payload.get("state_service_metrics")
        if not isinstance(raw_metrics, Mapping):
            raise CampaignValidationError("Target-discovery service totals are missing")
        converted: dict[str, float] = {}
        for field in fields:
            try:
                value = float(raw_metrics[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise CampaignValidationError(
                    f"Invalid target-discovery service field: {field}"
                ) from exc
            if not math.isfinite(value) or value < 0:
                raise CampaignValidationError(
                    f"Invalid target-discovery service field: {field}"
                )
            converted[field] = value
        for suffix in ("global", "268091", "268967"):
            demand = converted[f"demand_qty_{suffix}"]
            on_due = converted[f"on_due_qty_{suffix}"]
            if demand <= NUMERIC_TOLERANCE or on_due > demand + NUMERIC_TOLERANCE:
                raise CampaignValidationError(
                    "Discovery demand/on-due totals are inconsistent"
                )
        result[key] = converted
    if set(result) != expected_keys:
        raise CampaignValidationError("Target-discovery case matrix is incomplete")
    return result


def _validate_preflight_from_discovery(
    *,
    preflight: Mapping[str, Any],
    manifest: Mapping[str, Any],
    discovery: Mapping[tuple[str, int], Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    """Recompute every scientific holdout gate from signed discovery totals."""

    state_inputs = {
        str(row["operating_point_id"]): row
        for row in manifest.get("states") or []
        if isinstance(row, Mapping)
    }
    reported_states = {
        str(row.get("operating_point_id")): row
        for row in preflight.get("states") or []
        if isinstance(row, Mapping)
    }
    if set(reported_states) != set(OPERATING_POINTS):
        raise CampaignValidationError("Preflight state results are missing")

    def ratio_of_sums(rows: Sequence[Mapping[str, float]], suffix: str) -> float:
        demand = sum(float(row[f"demand_qty_{suffix}"]) for row in rows)
        return 100.0 * sum(float(row[f"on_due_qty_{suffix}"]) for row in rows) / demand

    def seed_service(row: Mapping[str, float], suffix: str) -> float:
        return (
            100.0
            * float(row[f"on_due_qty_{suffix}"])
            / float(row[f"demand_qty_{suffix}"])
        )

    random_generator = random.Random(BOOTSTRAP_SEED)
    bootstrap_indices = [
        [random_generator.randrange(EXPECTED_REPETITION_COUNT) for _ in EXPECTED_SEEDS]
        for _ in range(BOOTSTRAP_REPLICATES)
    ]
    services: dict[str, dict[str, float]] = {}
    seed_services: dict[str, dict[str, list[float]]] = {}
    failures: list[str] = []
    for seed in EXPECTED_SEEDS:
        reference = discovery[("op_100", seed)]
        for point in OPERATING_POINTS[1:]:
            candidate = discovery[(point, seed)]
            for suffix in ("global", "268091", "268967"):
                if not math.isclose(
                    float(reference[f"demand_qty_{suffix}"]),
                    float(candidate[f"demand_qty_{suffix}"]),
                    rel_tol=1e-12,
                    abs_tol=NUMERIC_TOLERANCE,
                ):
                    raise CampaignValidationError(
                        "Paired holdout demand differs across operating states"
                    )
    for point in OPERATING_POINTS:
        rows = [discovery[(point, seed)] for seed in EXPECTED_SEEDS]
        by_measure = {
            suffix: ratio_of_sums(rows, suffix)
            for suffix in ("global", "268091", "268967")
        }
        by_seed = {
            suffix: [seed_service(row, suffix) for row in rows]
            for suffix in ("global", "268091", "268967")
        }
        seed_services[point] = by_seed
        median_global = float(np.median(by_seed["global"]))
        bootstrap_global = [
            ratio_of_sums([rows[index] for index in indices], "global")
            for indices in bootstrap_indices
        ]
        ci_low = _linear_quantile(bootstrap_global, 0.025)
        ci_high = _linear_quantile(bootstrap_global, 0.975)
        reported = reported_states[point]
        target_pct = float(state_inputs[point]["target_service_pct"])
        comparisons = {
            "target_service_pct": target_pct,
            "service_global_ratio_of_sums_pct": by_measure["global"],
            "service_global_seed_median_pct": median_global,
            "service_268091_ratio_of_sums_pct": by_measure["268091"],
            "service_268967_ratio_of_sums_pct": by_measure["268967"],
            "global_service_bootstrap_ci95_low_pct": ci_low,
            "global_service_bootstrap_ci95_high_pct": ci_high,
        }
        for field, expected in comparisons.items():
            try:
                actual = float(reported[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise CampaignValidationError(
                    f"Preflight field is missing: {field}"
                ) from exc
            if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
                raise CampaignValidationError(
                    f"Preflight field does not match signed discovery evidence: {field}"
                )
        if reported.get("accepted") is not True or reported.get("failures") not in (
            [],
            None,
        ):
            failures.append(f"{point}: reported state is not accepted without failures")
        if point == "op_100":
            if not (
                98.5 <= by_measure["global"] <= 100.0 + NUMERIC_TOLERANCE
                and 98.5 <= median_global <= 100.0 + NUMERIC_TOLERANCE
                and by_measure["268091"] >= 98.5 - NUMERIC_TOLERANCE
                and by_measure["268967"] >= 98.5 - NUMERIC_TOLERANCE
            ):
                failures.append(
                    "op_100 fails the healthy-state global/product holdout gate"
                )
        else:
            lower = target_pct - 1.5
            upper = target_pct + 1.5
            if not (
                lower <= by_measure["global"] <= upper
                and lower <= median_global <= upper
                and by_measure["268091"] < 99.5 - NUMERIC_TOLERANCE
                and by_measure["268967"] < 99.5 - NUMERIC_TOLERANCE
            ):
                failures.append(
                    f"{point} fails its signed target/saturation holdout gate"
                )
        services[point] = {
            "global": by_measure["global"],
            "268091": by_measure["268091"],
            "268967": by_measure["268967"],
            "ci95_low": ci_low,
            "ci95_high": ci_high,
            "median_global": median_global,
            "target": target_pct,
        }
    pooled_ordering = {
        measure: services["op_100"][measure]
        > services["op_93"][measure]
        > services["op_80"][measure]
        for measure in ("global", "268091", "268967")
    }
    order_counts = {
        measure: sum(
            seed_services["op_100"][measure][index]
            > seed_services["op_93"][measure][index]
            > seed_services["op_80"][measure][index]
            for index in range(EXPECTED_REPETITION_COUNT)
        )
        for measure in ("global", "268091", "268967")
    }
    joint_order_count = sum(
        all(
            seed_services["op_100"][measure][index]
            > seed_services["op_93"][measure][index]
            > seed_services["op_80"][measure][index]
            for measure in ("global", "268091", "268967")
        )
        for index in range(EXPECTED_REPETITION_COUNT)
    )
    product_checks = preflight.get("product_seed_ordering_checks")
    valid_product_checks = isinstance(product_checks, Mapping) and all(
        isinstance(product_checks.get(product), Mapping)
        and int(product_checks[product].get("ordered_seed_count", -1))
        == order_counts[product]
        and product_checks[product].get("ordering_observed_in_at_least_24_of_30_seeds")
        == (order_counts[product] >= MIN_COMPARABLE_SEEDS)
        and product_checks[product].get("acceptance_gate") is True
        for product in ("268091", "268967")
    )
    if not all(pooled_ordering.values()) or joint_order_count < MIN_COMPARABLE_SEEDS:
        failures.append(
            "Global and product service states are not jointly ordered on 24 seeds"
        )
    if (
        preflight.get("pooled_ordering_by_measure") != pooled_ordering
        or preflight.get("seed_order_counts") != order_counts
        or int(preflight.get("joint_seed_order_count", -1)) != joint_order_count
        or int(preflight.get("joint_seed_order_required", -1)) != MIN_COMPARABLE_SEEDS
        or int(preflight.get("minimum_seed_order_count", -1)) != MIN_COMPARABLE_SEEDS
        or not valid_product_checks
        or preflight.get("ordering_valid") is not all(pooled_ordering.values())
        or preflight.get("seed_ordering_valid")
        is not (joint_order_count >= MIN_COMPARABLE_SEEDS)
    ):
        failures.append(
            "Reported preflight ordering differs from signed discovery evidence"
        )
    if failures:
        raise CampaignValidationError("; ".join(failures))
    return services


def _legacy_validate_signed_context(
    evidence: InputEvidence, manifest: Mapping[str, Any]
) -> SignedCampaignContext:
    if manifest.get("schema_version") != INPUT_CAMPAIGN_SCHEMA_VERSION:
        raise CampaignValidationError("Unsupported campaign schema")
    if not _is_sha256(manifest.get("campaign_signature")) or not _is_sha256(
        manifest.get("engine_sha256")
    ):
        raise CampaignValidationError(
            "Campaign and engine signatures must be SHA-256 digests"
        )
    _verify_manifest_signature(manifest)
    operating_point_provenance = _validate_operating_point_provenance(
        evidence, manifest
    )
    revision = str(manifest.get("contract_revision") or "")
    if not all(token in revision for token in ("fixed_", "holdout", "adaptive", "_v")):
        raise CampaignValidationError(
            "A signed adaptive incident campaign contract is required"
        )
    if (
        str(manifest.get("simulation_days") or manifest.get("days") or "").startswith(
            "adaptive"
        )
        is False
    ):
        raise CampaignValidationError(
            "The campaign must declare adaptive case horizons"
        )
    adaptive = manifest.get("adaptive_horizon_contract")
    if (
        not isinstance(adaptive, Mapping)
        or adaptive.get("fixed_upper_bound_assumed") is not False
    ):
        raise CampaignValidationError("The adaptive-horizon contract is incomplete")
    state_window = manifest.get("state_evaluation_window")
    if not isinstance(state_window, Mapping) or (
        int(state_window.get("start_day", -1)) != 0
        or int(state_window.get("end_day", -1)) != STATE_EVALUATION_DAYS - 1
        or int(state_window.get("day_count", -1)) != STATE_EVALUATION_DAYS
    ):
        raise CampaignValidationError(
            "The operating states must be evaluated on J0-J719"
        )
    target_contract = manifest.get("target_discovery_contract")
    if not isinstance(target_contract, Mapping):
        raise CampaignValidationError(
            "The signed fixed-window target contract is missing"
        )
    try:
        disruption_window_days = int(target_contract.get("disruption_window_days"))
    except (TypeError, ValueError) as exc:
        raise CampaignValidationError(
            "Invalid supplier disruption-window duration"
        ) from exc
    if disruption_window_days <= 1:
        raise CampaignValidationError(
            "A multi-day supplier disruption window is required"
        )
    if int(target_contract.get("design_seed", -1)) != DESIGN_SEED:
        raise CampaignValidationError("The independent design seed is missing")
    if (
        target_contract.get("same_lane_specific_dates_across_states_and_campaign_seeds")
        is not True
    ):
        raise CampaignValidationError(
            "Supplier-window dates are not frozen across states"
        )
    try:
        quantity_ratio_limit = float(target_contract.get("quantity_ratio_limit"))
    except (TypeError, ValueError) as exc:
        raise CampaignValidationError(
            "Invalid cross-state exposure ratio limit"
        ) from exc
    if not math.isfinite(quantity_ratio_limit) or not math.isclose(
        quantity_ratio_limit, 1.5, rel_tol=0.0, abs_tol=NUMERIC_TOLERANCE
    ):
        raise CampaignValidationError(
            "The signed cross-state exposure ratio limit must be 1.5"
        )
    if int(target_contract.get("minimum_comparable_campaign_seeds", -1)) != (
        MIN_COMPARABLE_SEEDS
    ):
        raise CampaignValidationError("The signed comparable-seed threshold must be 24")
    business = manifest.get("incident_impact_window")
    if not isinstance(business, Mapping) or (
        int(business.get("day_count", -1)) != BUSINESS_WINDOW_DAYS
        or business.get("anchor")
        != f"first_day_of_fixed_{disruption_window_days}_day_supplier_disruption_window"
    ):
        raise CampaignValidationError(
            "The fixed 360-day business-envelope contract is missing"
        )
    impact_contract = manifest.get("impact_metric_contract")
    if not isinstance(impact_contract, Mapping) or (
        impact_contract.get("full_horizon_cost_pairing_comparable") is not False
        or "fixed_360" not in str(impact_contract.get("primary") or "")
    ):
        raise CampaignValidationError(
            "The paired fixed-window metric contract is incomplete"
        )
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
            raise CampaignValidationError(
                f"Manifest must explicitly declare {flag}=false"
            )
    if manifest.get("target_selection", {}).get("target_claim") != (
        f"fixed_{disruption_window_days}_day_simulated_supplier_disruption_window_"
        "not_an_observed_incident"
    ):
        raise CampaignValidationError(
            "The simulated fixed-window target claim is missing"
        )
    mechanisms = manifest.get("mechanisms")
    if not isinstance(mechanisms, list) or len(mechanisms) != len(MECHANISMS):
        raise CampaignValidationError(
            "Exactly two supplier incident causes are required"
        )
    observed_mechanisms: set[str] = set()
    for raw in mechanisms:
        if not isinstance(raw, Mapping):
            raise CampaignValidationError("Invalid mechanism declaration")
        key = _normalise_mechanism(raw.get("key"))
        observed_mechanisms.add(key)
        contract = MECHANISM_CONTRACT.get(key)
        if (
            contract is None
            or raw.get("risk_type") != contract["risk_type"]
            or not math.isclose(
                float(raw.get("value", math.nan)),
                contract["risk_value"],
                rel_tol=0.0,
                abs_tol=NUMERIC_TOLERANCE,
            )
        ):
            raise CampaignValidationError(f"Invalid mechanism contract: {key}")
    if observed_mechanisms != set(MECHANISMS):
        raise CampaignValidationError("Unexpected supplier incident cause")

    state_rows = manifest.get("states")
    if not isinstance(state_rows, list) or [
        row.get("operating_point_id") for row in state_rows
    ] != list(OPERATING_POINTS):
        raise CampaignValidationError("The three ordered operating states are required")
    lane_rows = manifest.get("lanes")
    if not isinstance(lane_rows, list) or len(lane_rows) != EXPECTED_LANE_COUNT:
        raise CampaignValidationError("Exactly 18 physical supplier lanes are required")
    lane_identity: dict[str, tuple[str, str, str, str, str]] = {}
    for row in lane_rows:
        if not isinstance(row, Mapping):
            raise CampaignValidationError("Invalid lane declaration")
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
            raise CampaignValidationError("Lane identities must be complete and unique")
        lane_identity[lane_id] = identity
    seeds = tuple(int(seed) for seed in manifest.get("seeds") or [])
    if seeds != EXPECTED_SEEDS:
        raise CampaignValidationError("The 30 preregistered paired seeds are required")
    cohorts = manifest.get("operating_points_cohorts")
    if not isinstance(cohorts, Mapping) or (
        tuple(cohorts.get("design") or ()) != (DESIGN_SEED,)
        or tuple(cohorts.get("calibration") or ()) != tuple(range(340282, 340287))
        or tuple(cohorts.get("holdout_sealed") or ()) != EXPECTED_SEEDS
    ):
        raise CampaignValidationError(
            "Design, five-seed calibration and 30-seed holdout cohorts must be disjoint"
        )
    expected_counts = manifest.get("expected_counts")
    expected = {
        "baseline_rows": EXPECTED_BASELINE_COUNT,
        "incident_rows": EXPECTED_INCIDENT_COUNT,
        "total_rows": EXPECTED_TOTAL_COUNT,
        "shard_count": EXPECTED_SHARD_COUNT,
        "rows_per_shard": EXPECTED_ROWS_PER_SHARD,
    }
    if not isinstance(expected_counts, Mapping) or any(
        int(expected_counts.get(key, -1)) != value for key, value in expected.items()
    ):
        raise CampaignValidationError("Manifest expected counts do not match 3x18x2x30")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != EXPECTED_SHARD_COUNT:
        raise CampaignValidationError(
            "Exactly 18 signed shard definitions are required"
        )
    shard_ids = frozenset(str(row.get("shard_id") or "") for row in shards)
    if "" in shard_ids or len(shard_ids) != EXPECTED_SHARD_COUNT:
        raise CampaignValidationError("Shard identities are incomplete or duplicated")

    preflight_path = _resolve_signed_artifact(
        evidence=evidence,
        manifest=manifest,
        path_key="operating_point_preflight",
        sha_key="operating_point_preflight_sha256",
        fallback_name="operating_point_preflight.json",
    )
    preflight = _read_json(preflight_path)
    preflight_signature = _verify_payload_signature(
        preflight, "preflight_signature", label="operating-point preflight"
    )
    if (
        preflight.get("schema_version")
        != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.operating_point_preflight.v2"
        or preflight.get("contract_revision") != manifest.get("contract_revision")
        or preflight.get("campaign_signature") != manifest.get("campaign_signature")
        or preflight.get("status") != PREFLIGHT_ACCEPTED_STATUS
        or preflight_signature != manifest.get("operating_point_preflight_signature")
        or manifest.get("operating_point_preflight_status") != PREFLIGHT_ACCEPTED_STATUS
        or int(preflight.get("campaign_seed_count", -1)) != EXPECTED_REPETITION_COUNT
        or tuple(preflight.get("campaign_seeds") or ()) != EXPECTED_SEEDS
        or tuple(preflight.get("calibration_seeds_excluded") or ())
        != tuple(range(340282, 340287))
        or preflight.get("holdout_used_once_without_retuning") is not True
        or preflight.get("operating_points_input_status")
        != manifest.get("operating_points_input_status")
        or preflight.get("operating_points_input_status")
        != operating_point_provenance["status"]
        or preflight.get("operating_points_artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or preflight.get("operating_points_artifact_signature")
        != operating_point_provenance["artifact_signature"]
        or preflight.get("operating_points_calibration_plan_signature")
        != manifest.get("operating_points_calibration_plan_signature")
        or preflight.get("operating_points_calibration_plan_signature")
        != operating_point_provenance["plan_signature"]
        or preflight.get("operating_points_selection_signature")
        != manifest.get("operating_points_selection_signature")
        or preflight.get("operating_points_selection_signature")
        != operating_point_provenance["selection_signature"]
        or preflight.get("no_incident_probe_before_holdout_acceptance") is not True
        or preflight.get("design_seed_in_acceptance_statistics") is not False
        or int(preflight.get("design_seed", -1)) != DESIGN_SEED
    ):
        raise CampaignValidationError(
            "The signed 30-seed operating-point preflight was not accepted"
        )
    bootstrap = preflight.get("bootstrap")
    if not isinstance(bootstrap, Mapping) or (
        int(bootstrap.get("replicates", -1)) != BOOTSTRAP_REPLICATES
        or int(bootstrap.get("seed", -1)) != BOOTSTRAP_SEED
        or bootstrap.get("method") != "paired_common_seed_resampling"
    ):
        raise CampaignValidationError(
            "The preflight must use the signed paired bootstrap"
        )

    registry_path = _resolve_signed_artifact(
        evidence=evidence,
        manifest=manifest,
        path_key="target_registry",
        sha_key="target_registry_sha256",
        fallback_name="target_registry.json",
    )
    registry = _read_json(registry_path)
    registry_signature = _verify_payload_signature(
        registry, "registry_signature", label="fixed-window target registry"
    )
    if (
        registry.get("schema_version")
        != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.target_registry.v4"
        or registry.get("campaign_signature") != manifest.get("campaign_signature")
        or registry.get("engine_sha256") != manifest.get("engine_sha256")
        or registry_signature != manifest.get("target_registry_signature")
        or int(registry.get("design_seed", -1)) != DESIGN_SEED
        or int(registry.get("disruption_window_days", -1)) != disruption_window_days
        or tuple(registry.get("campaign_seeds") or registry.get("seeds") or ())
        != EXPECTED_SEEDS
        or tuple(registry.get("states") or ()) != OPERATING_POINTS
        or tuple(registry.get("lanes") or ()) != tuple(lane_identity)
        or int(registry.get("required_comparable_seed_count", -1))
        != MIN_COMPARABLE_SEEDS
        or not math.isclose(
            float(registry.get("state_match_max_quantity_ratio", math.nan)),
            quantity_ratio_limit,
            rel_tol=0.0,
            abs_tol=NUMERIC_TOLERANCE,
        )
        or registry.get("all_lane_design_windows_comparable") is not True
        or registry.get("all_lane_holdout_exposures_comparable") is not True
        or registry.get("campaign_exposure_gate_passed") is not True
        or registry.get("exposure_gate_failures") != []
    ):
        raise CampaignValidationError(
            "The signed fixed-window target registry is inconsistent"
        )
    contracts = registry.get("lane_contracts")
    if not isinstance(contracts, list) or len(contracts) != EXPECTED_LANE_COUNT:
        raise CampaignValidationError(
            "The target registry must contain 18 lane contracts"
        )
    contracts_by_lane = {
        str(row.get("lane_id") or ""): row
        for row in contracts
        if isinstance(row, Mapping)
    }
    if set(contracts_by_lane) != set(lane_identity) or len(contracts_by_lane) != len(
        contracts
    ):
        raise CampaignValidationError(
            "Target-registry lane contracts are missing or duplicated"
        )
    targets = registry.get("targets")
    if not isinstance(targets, list) or len(targets) != (
        len(OPERATING_POINTS) * len(EXPECTED_SEEDS) * EXPECTED_LANE_COUNT
    ):
        raise CampaignValidationError("The target registry matrix is incomplete")
    target_keys = {
        (
            str(row.get("operating_point_id")),
            int(row.get("seed", -1)),
            str(row.get("lane_id")),
        )
        for row in targets
    }
    expected_target_keys = {
        (point, seed, lane)
        for point in OPERATING_POINTS
        for seed in EXPECTED_SEEDS
        for lane in lane_identity
    }
    if target_keys != expected_target_keys or len(target_keys) != len(targets):
        raise CampaignValidationError(
            "The target registry contains missing or duplicate cells"
        )
    for row in targets:
        if (
            int(row.get("target_window_days", -1)) != disruption_window_days
            or int(row.get("target_window_end_day", -1))
            - int(row.get("target_window_start_day", -1))
            + 1
            != disruption_window_days
        ):
            raise CampaignValidationError(
                "Target registry window duration is not uniform"
            )
    for lane_id, contract in contracts_by_lane.items():
        lane_targets = [row for row in targets if str(row.get("lane_id")) == lane_id]
        starts = {int(row["target_window_start_day"]) for row in lane_targets}
        ends = {int(row["target_window_end_day"]) for row in lane_targets}
        comparable_by_seed: dict[int, set[bool]] = {}
        targets_by_seed: dict[int, list[Mapping[str, Any]]] = {}
        for row in lane_targets:
            row_seed = int(row["seed"])
            comparable_by_seed.setdefault(row_seed, set()).add(
                _truthy(row.get("seed_cross_state_exposure_comparable"))
            )
            targets_by_seed.setdefault(row_seed, []).append(row)
        if (
            len(starts) != 1
            or len(ends) != 1
            or next(iter(ends)) - next(iter(starts)) + 1 != disruption_window_days
        ):
            raise CampaignValidationError(
                "One lane must keep one fixed window across all states and seeds"
            )
        fixed_start = next(iter(starts))
        fixed_end = next(iter(ends))
        if fixed_start < 0 or fixed_end >= STATE_EVALUATION_DAYS:
            raise CampaignValidationError(
                "Fixed supplier windows must stay within J0-J719"
            )
        if any(len(values) != 1 for values in comparable_by_seed.values()):
            raise CampaignValidationError(
                "Cross-state exposure flag differs within a paired seed"
            )
        recomputed_by_seed: dict[int, bool] = {}
        for seed, seed_rows in targets_by_seed.items():
            if len(seed_rows) != len(OPERATING_POINTS):
                raise CampaignValidationError(
                    "Each lane/seed needs all three operating states"
                )
            quantities = [
                float(row.get("target_planned_qty", math.nan)) for row in seed_rows
            ]
            if any(not math.isfinite(value) or value < 0.0 for value in quantities):
                raise CampaignValidationError(
                    "Target-registry quantities must be finite and non-negative"
                )
            positive_all = min(quantities) > NUMERIC_TOLERANCE
            ratio = max(quantities) / min(quantities) if positive_all else math.inf
            recomputed = (
                positive_all and ratio <= quantity_ratio_limit + NUMERIC_TOLERANCE
            )
            recomputed_by_seed[seed] = recomputed
            if comparable_by_seed[seed] != {recomputed}:
                raise CampaignValidationError(
                    "Cross-state exposure comparability does not match registered quantities"
                )
            for row in seed_rows:
                raw_ratio = row.get("cross_state_quantity_ratio", "")
                if positive_all:
                    try:
                        declared_ratio = float(raw_ratio)
                    except (TypeError, ValueError) as exc:
                        raise CampaignValidationError(
                            "Cross-state exposure ratio is missing for a positive lane/seed"
                        ) from exc
                    if not math.isclose(
                        declared_ratio, ratio, rel_tol=1e-10, abs_tol=NUMERIC_TOLERANCE
                    ):
                        raise CampaignValidationError(
                            "Cross-state exposure ratio differs from registered quantities"
                        )
                elif str(raw_ratio).strip():
                    raise CampaignValidationError(
                        "A zero-exposure lane/seed cannot declare a finite quantity ratio"
                    )
        comparable_count = sum(recomputed_by_seed.values())
        design_quantities = contract.get("design_quantities")
        if not isinstance(design_quantities, Mapping) or set(design_quantities) != set(
            OPERATING_POINTS
        ):
            raise CampaignValidationError(
                "Lane design exposure quantities are incomplete"
            )
        design_values = [float(design_quantities[point]) for point in OPERATING_POINTS]
        if any(
            not math.isfinite(value) or value <= NUMERIC_TOLERANCE
            for value in design_values
        ):
            raise CampaignValidationError(
                "Every lane needs a positive three-state design exposure"
            )
        design_ratio = max(design_values) / min(design_values)
        if (
            contract.get("design_status")
            != f"calibration_design_comparable_{disruption_window_days}d_window"
            or int(contract.get("design_seed", -1)) != DESIGN_SEED
            or int(contract.get("fixed_window_start_day", -1)) != fixed_start
            or int(contract.get("fixed_window_end_day", -1)) != fixed_end
            or int(contract.get("required_comparable_seed_count", -1))
            != MIN_COMPARABLE_SEEDS
            or int(contract.get("comparable_campaign_seed_count", -1))
            != comparable_count
            or _truthy(contract.get("state_comparison_valid"))
            != (comparable_count >= MIN_COMPARABLE_SEEDS)
            or design_ratio > quantity_ratio_limit + NUMERIC_TOLERANCE
            or not math.isclose(
                float(contract.get("design_quantity_ratio", math.nan)),
                design_ratio,
                rel_tol=1e-10,
                abs_tol=NUMERIC_TOLERANCE,
            )
        ):
            raise CampaignValidationError(
                "Lane exposure-comparability contract is inconsistent"
            )
        for row in lane_targets:
            if (
                int(row.get("required_comparable_seed_count", -1))
                != MIN_COMPARABLE_SEEDS
                or int(row.get("comparable_campaign_seed_count", -1))
                != comparable_count
                or _truthy(row.get("state_comparison_valid"))
                != (comparable_count >= MIN_COMPARABLE_SEEDS)
                or str(row.get("cross_state_match_status") or "")
                != contract.get("design_status")
                or not math.isclose(
                    float(row.get("cross_state_match_threshold_ratio", math.nan)),
                    quantity_ratio_limit,
                    rel_tol=0.0,
                    abs_tol=NUMERIC_TOLERANCE,
                )
            ):
                raise CampaignValidationError(
                    "Target cells do not reproduce the signed lane comparability contract"
                )
    discovery_progress_path = (
        evidence.manifest_path.parent / "target_discovery" / "progress.json"
    )
    if not discovery_progress_path.is_file():
        raise CampaignValidationError("Target-discovery progress evidence is missing")
    discovery_progress = _read_json(discovery_progress_path)
    if (
        discovery_progress.get("campaign_signature")
        != manifest.get("campaign_signature")
        or discovery_progress.get("status") != "complete"
        or int(discovery_progress.get("planned", -1)) != 93
        or int(discovery_progress.get("completed", -1)) != 93
        or int(discovery_progress.get("failed", -1)) != 0
        or int(discovery_progress.get("running", -1)) != 0
        or manifest.get("target_discovery_status") != "complete"
    ):
        raise CampaignValidationError("The 93-run target discovery is not complete")
    discovery_service = _load_discovery_service_evidence(
        evidence=evidence,
        manifest=manifest,
        disruption_window_days=disruption_window_days,
    )
    achieved_services = _validate_preflight_from_discovery(
        preflight=preflight,
        manifest=manifest,
        discovery=discovery_service,
    )
    return SignedCampaignContext(
        manifest=manifest,
        operating_point_provenance=operating_point_provenance,
        preflight=preflight,
        registry=registry,
        achieved_services=achieved_services,
        lane_identity=lane_identity,
        shard_ids=shard_ids,
        disruption_window_days=disruption_window_days,
        preflight_path=preflight_path,
        registry_path=registry_path,
        discovery_progress_path=discovery_progress_path,
    )


def _validate_v4_design_evidence(
    evidence: InputEvidence, manifest: Mapping[str, Any]
) -> dict[str, str]:
    directory = evidence.manifest_path.parent / "target_discovery" / "evidence"
    paths = sorted(directory.glob("*.json"))
    if len(paths) != 3:
        raise CampaignValidationError("Exactly three V4 design-run proofs are required")
    states = {
        str(row["operating_point_id"]): row for row in manifest.get("states") or []
    }
    seen: set[str] = set()
    hashes: dict[str, str] = {}
    for path in paths:
        payload = _read_json(path)
        _verify_payload_signature(
            payload, "evidence_signature", label="V4 design-run evidence"
        )
        point = str(payload.get("operating_point_id") or "")
        if point not in states or point in seen:
            raise CampaignValidationError("Unexpected or duplicate V4 design-run state")
        expected_signature = _stable_sha256(
            {
                "campaign_signature": manifest["campaign_signature"],
                "engine_sha256": manifest["engine_sha256"],
                "engine_profile_sha256": manifest["engine_profile_sha256"],
                "point_id": point,
                "graph_sha256": states[point]["graph_sha256"],
                "seed": DESIGN_SEED,
                "simulation_days": STATE_EVALUATION_DAYS,
                "purpose": "cross_state_42d_target_discovery",
            }
        )
        if (
            payload.get("schema_version")
            != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.target_discovery.case.v1"
            or payload.get("campaign_signature") != manifest["campaign_signature"]
            or payload.get("engine_sha256") != manifest["engine_sha256"]
            or payload.get("discovery_signature") != expected_signature
            or payload.get("seed") != DESIGN_SEED
            or payload.get("simulation_days") != STATE_EVALUATION_DAYS
            or not isinstance(payload.get("shipment_rows"), list)
        ):
            raise CampaignValidationError("V4 design-run evidence contract changed")
        seen.add(point)
        hashes[point] = _sha256(path)
    if seen != set(OPERATING_POINTS):
        raise CampaignValidationError("V4 design-run proof matrix is incomplete")
    return hashes


def _validate_v4_registry(
    registry: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    lane_identity: Mapping[str, tuple[str, str, str, str, str]],
    disruption_window_days: int,
    quantity_ratio_limit: float,
) -> None:
    registry_signature = _verify_payload_signature(
        registry, "registry_signature", label="V4 fixed-window target registry"
    )
    contracts = registry.get("lane_contracts")
    targets = registry.get("targets")
    if (
        registry.get("schema_version")
        != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.target_registry.v1"
        or registry.get("campaign_signature") != manifest["campaign_signature"]
        or registry.get("engine_sha256") != manifest["engine_sha256"]
        or registry_signature != manifest.get("target_registry_signature")
        or registry.get("design_seed") != DESIGN_SEED
        or registry.get("campaign_seeds") != list(EXPECTED_SEEDS)
        or registry.get("seeds") != list(EXPECTED_SEEDS)
        or registry.get("states") != list(OPERATING_POINTS)
        or registry.get("lanes") != list(lane_identity)
        or registry.get("disruption_window_days") != disruption_window_days
        or registry.get("required_comparable_seed_count") != MIN_COMPARABLE_SEEDS
        or not math.isclose(
            float(registry.get("state_match_max_quantity_ratio", math.nan)),
            quantity_ratio_limit,
            rel_tol=0.0,
            abs_tol=NUMERIC_TOLERANCE,
        )
        or registry.get("all_lane_design_windows_comparable") is not True
        or registry.get("all_lane_holdout_exposures_comparable") is not True
        or registry.get("campaign_exposure_gate_passed") is not True
        or registry.get("exposure_gate_failures") != []
        or not isinstance(contracts, list)
        or len(contracts) != EXPECTED_LANE_COUNT
        or not isinstance(targets, list)
        or len(targets)
        != len(OPERATING_POINTS) * len(EXPECTED_SEEDS) * EXPECTED_LANE_COUNT
    ):
        raise CampaignValidationError("V4 target registry header/gate is invalid")
    contracts_by_lane = {
        str(row.get("lane_id") or ""): row
        for row in contracts
        if isinstance(row, Mapping)
    }
    target_by_key = {
        (
            str(row.get("operating_point_id") or ""),
            int(row.get("seed", -1)),
            str(row.get("lane_id") or ""),
        ): row
        for row in targets
        if isinstance(row, Mapping)
    }
    expected_keys = {
        (point, seed, lane)
        for point in OPERATING_POINTS
        for seed in EXPECTED_SEEDS
        for lane in lane_identity
    }
    if (
        set(contracts_by_lane) != set(lane_identity)
        or len(contracts_by_lane) != len(contracts)
        or set(target_by_key) != expected_keys
        or len(target_by_key) != len(targets)
    ):
        raise CampaignValidationError("V4 target registry cells are missing or duplicated")
    for lane_id, lane_contract in contracts_by_lane.items():
        lane_targets = [row for key, row in target_by_key.items() if key[2] == lane_id]
        starts = {int(row.get("target_window_start_day", -1)) for row in lane_targets}
        ends = {int(row.get("target_window_end_day", -1)) for row in lane_targets}
        if (
            len(starts) != 1
            or len(ends) != 1
            or next(iter(ends)) - next(iter(starts)) + 1 != disruption_window_days
            or min(starts) < 0
            or max(ends) >= STATE_EVALUATION_DAYS
            or lane_contract.get("design_status")
            != f"calibration_design_comparable_{disruption_window_days}d_window"
            or lane_contract.get("design_seed") != DESIGN_SEED
            or lane_contract.get("fixed_window_start_day") != next(iter(starts))
            or lane_contract.get("fixed_window_end_day") != next(iter(ends))
        ):
            raise CampaignValidationError("A V4 lane does not preserve one fixed window")
        comparable = 0
        for seed in EXPECTED_SEEDS:
            seed_rows = [target_by_key[(point, seed, lane_id)] for point in OPERATING_POINTS]
            quantities = [float(row.get("target_planned_qty", math.nan)) for row in seed_rows]
            if any(not math.isfinite(value) or value < 0.0 for value in quantities):
                raise CampaignValidationError("Invalid V4 registered shipment quantity")
            positive = min(quantities) > REGISTRY_NUMERIC_TOLERANCE
            ratio = max(quantities) / min(quantities) if positive else math.inf
            is_comparable = (
                positive
                and ratio <= quantity_ratio_limit + REGISTRY_NUMERIC_TOLERANCE
            )
            comparable += int(is_comparable)
            for row in seed_rows:
                if (
                    _truthy(row.get("seed_cross_state_exposure_comparable"))
                    != is_comparable
                    or int(row.get("target_window_days", -1))
                    != disruption_window_days
                    or int(row.get("required_comparable_seed_count", -1))
                    != MIN_COMPARABLE_SEEDS
                    or str(row.get("cross_state_match_status") or "")
                    != lane_contract.get("design_status")
                ):
                    raise CampaignValidationError(
                        "V4 target cell differs from recomputed exposure comparability"
                    )
                raw_ratio = row.get("cross_state_quantity_ratio", "")
                if positive:
                    try:
                        declared_ratio = float(raw_ratio)
                    except (TypeError, ValueError) as exc:
                        raise CampaignValidationError(
                            "V4 positive target cell lacks its quantity ratio"
                        ) from exc
                    if not math.isclose(
                        declared_ratio,
                        ratio,
                        rel_tol=1e-10,
                        abs_tol=REGISTRY_NUMERIC_TOLERANCE,
                    ):
                        raise CampaignValidationError(
                            "V4 target-cell quantity ratio changed"
                        )
                elif str(raw_ratio).strip():
                    raise CampaignValidationError(
                        "V4 zero-exposure target declares a finite quantity ratio"
                    )
        design = lane_contract.get("design_quantities")
        if not isinstance(design, Mapping) or set(design) != set(OPERATING_POINTS):
            raise CampaignValidationError("V4 design quantities are incomplete")
        design_values = [float(design[point]) for point in OPERATING_POINTS]
        design_ratio = (
            max(design_values) / min(design_values)
            if min(design_values) > REGISTRY_NUMERIC_TOLERANCE
            else math.inf
        )
        if (
            min(design_values) <= REGISTRY_NUMERIC_TOLERANCE
            or design_ratio
            > quantity_ratio_limit + REGISTRY_NUMERIC_TOLERANCE
            or int(lane_contract.get("comparable_campaign_seed_count", -1))
            != comparable
            or comparable < MIN_COMPARABLE_SEEDS
            or lane_contract.get("state_comparison_valid") is not True
            or not math.isclose(
                float(lane_contract.get("design_quantity_ratio", math.nan)),
                design_ratio,
                rel_tol=1e-10,
                abs_tol=REGISTRY_NUMERIC_TOLERANCE,
            )
        ):
            raise CampaignValidationError("V4 lane exposure gate cannot be reproduced")
        for row in lane_targets:
            if (
                int(row.get("comparable_campaign_seed_count", -1)) != comparable
                or _truthy(row.get("state_comparison_valid"))
                != (comparable >= MIN_COMPARABLE_SEEDS)
            ):
                raise CampaignValidationError(
                    "V4 target-cell exposure summary differs from recomputation"
                )


def _achieved_services_from_v4_binding(
    binding: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, dict[str, float]]:
    summaries = binding.get("states")
    bootstrap = binding.get("paired_bootstrap_global_descriptive_only")
    intervals = bootstrap.get("intervals") if isinstance(bootstrap, Mapping) else None
    state_inputs = {
        str(row["operating_point_id"]): row for row in manifest.get("states") or []
    }
    if (
        not isinstance(summaries, Mapping)
        or set(summaries) != set(OPERATING_POINTS)
        or not isinstance(intervals, Mapping)
        or set(intervals) != set(OPERATING_POINTS)
    ):
        raise CampaignValidationError("V4 state summaries/bootstrap are incomplete")
    result: dict[str, dict[str, float]] = {}
    for point in OPERATING_POINTS:
        summary = summaries[point]
        pooled = summary.get("pooled") if isinstance(summary, Mapping) else None
        median = summary.get("median") if isinstance(summary, Mapping) else None
        interval = intervals[point]
        if not all(isinstance(item, Mapping) for item in (pooled, median, interval)):
            raise CampaignValidationError("Malformed V4 state summary")
        values = {
            "global": 100.0 * float(pooled["system_on_due_service"]),
            "268091": 100.0 * float(pooled["on_due_service_268091"]),
            "268967": 100.0 * float(pooled["on_due_service_268967"]),
            "ci95_low": 100.0 * float(interval["ci95_low"]),
            "ci95_high": 100.0 * float(interval["ci95_high"]),
            "median_global": 100.0 * float(median["system_on_due_service"]),
            "target": float(state_inputs[point]["target_service_pct"]),
        }
        if any(not math.isfinite(value) for value in values.values()):
            raise CampaignValidationError("Non-finite V4 achieved service")
        result[point] = values
    if not all(
        result["op_100"][measure]
        > result["op_93"][measure]
        > result["op_80"][measure]
        for measure in ("global", "268091", "268967")
    ):
        raise CampaignValidationError("Accepted V4 state ordering changed")
    return result


# This definition intentionally replaces the copied V2/V3 context validator.
def _validate_signed_context(
    evidence: InputEvidence, manifest: Mapping[str, Any]
) -> SignedCampaignContext:
    if manifest.get("schema_version") != INPUT_CAMPAIGN_SCHEMA_VERSION:
        raise CampaignValidationError("Unsupported V4 campaign schema")
    if not _is_sha256(manifest.get("campaign_signature")) or not _is_sha256(
        manifest.get("engine_sha256")
    ):
        raise CampaignValidationError("Campaign and engine SHA-256 are required")
    _verify_manifest_signature(manifest)
    provenance = _validate_operating_point_provenance(evidence, manifest)
    if manifest.get("contract_revision") != (
        "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
    ):
        raise CampaignValidationError("Unexpected V4 campaign contract revision")
    adaptive = manifest.get("adaptive_horizon_contract")
    target_contract = manifest.get("target_discovery_contract")
    if (
        not isinstance(adaptive, Mapping)
        or adaptive.get("fixed_upper_bound_assumed") is not False
        or not isinstance(target_contract, Mapping)
        or target_contract.get("design_seed") != DESIGN_SEED
        or target_contract.get("campaign_seeds") != list(EXPECTED_SEEDS)
        or target_contract.get("minimum_comparable_campaign_seeds")
        != MIN_COMPARABLE_SEEDS
    ):
        raise CampaignValidationError("V4 adaptive/design contract changed")
    disruption_window_days = int(target_contract.get("disruption_window_days", -1))
    quantity_ratio_limit = float(target_contract.get("quantity_ratio_limit", math.nan))
    if disruption_window_days != 42 or not math.isclose(
        quantity_ratio_limit, 1.5, rel_tol=0.0, abs_tol=NUMERIC_TOLERANCE
    ):
        raise CampaignValidationError("V4 window/quantity-ratio contract changed")
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
            raise CampaignValidationError(f"Manifest must declare {flag}=false")
    mechanisms = manifest.get("mechanisms")
    if not isinstance(mechanisms, list) or {
        str(row.get("key") or "") for row in mechanisms if isinstance(row, Mapping)
    } != set(MECHANISMS):
        raise CampaignValidationError("V4 requires exactly the two separate mechanisms")
    for raw in mechanisms:
        key = str(raw["key"])
        expected_mechanism = MECHANISM_CONTRACT[key]
        if raw.get("risk_type") != expected_mechanism["risk_type"] or not math.isclose(
            float(raw.get("value", math.nan)),
            expected_mechanism["risk_value"],
            rel_tol=0.0,
            abs_tol=NUMERIC_TOLERANCE,
        ):
            raise CampaignValidationError("V4 mechanism magnitude/type changed")
    state_rows = manifest.get("states")
    if not isinstance(state_rows, list) or [
        row.get("operating_point_id") for row in state_rows
    ] != list(OPERATING_POINTS):
        raise CampaignValidationError("Three ordered V4 operating states are required")
    lane_rows = manifest.get("lanes")
    if not isinstance(lane_rows, list) or len(lane_rows) != EXPECTED_LANE_COUNT:
        raise CampaignValidationError("Exactly 18 physical V4 lanes are required")
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
            raise CampaignValidationError("V4 lane identities are incomplete/duplicated")
        lane_identity[lane_id] = identity
    if tuple(manifest.get("seeds") or ()) != EXPECTED_SEEDS:
        raise CampaignValidationError("The exact 30 fresh V4 seeds are required")
    if manifest.get("operating_points_cohorts") != {
        "campaign_repetitions_reuse_v4_fresh_holdout": list(EXPECTED_SEEDS),
        "incident_window_design_reserved": [DESIGN_SEED],
        "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
    }:
        raise CampaignValidationError("V4 seed cohorts/no-retuning contract changed")
    expected_counts = manifest.get("expected_counts")
    expected = {
        "auxiliary_discovery_runs": 3,
        "design_window_engine_runs": 3,
        "operating_point_validation_engine_runs": 0,
        "imported_v4_holdout_service_proofs": 90,
        "imported_v4_holdout_shipment_traces": 90,
        "baseline_rows": EXPECTED_BASELINE_COUNT,
        "incident_rows": EXPECTED_INCIDENT_COUNT,
        "total_rows": EXPECTED_TOTAL_COUNT,
        "shard_count": EXPECTED_SHARD_COUNT,
        "rows_per_shard": EXPECTED_ROWS_PER_SHARD,
    }
    if not isinstance(expected_counts, Mapping) or any(
        int(expected_counts.get(key, -1)) != value for key, value in expected.items()
    ):
        raise CampaignValidationError("V4 manifest counts changed")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != EXPECTED_SHARD_COUNT:
        raise CampaignValidationError("Exactly 18 V4 shard definitions are required")
    shard_ids = frozenset(str(row.get("shard_id") or "") for row in shards)
    if "" in shard_ids or len(shard_ids) != EXPECTED_SHARD_COUNT:
        raise CampaignValidationError("V4 shard ids are incomplete/duplicated")

    binding_path = _resolve_signed_artifact(
        evidence=evidence,
        manifest=manifest,
        path_key="state_validation_binding",
        sha_key="state_validation_binding_sha256",
        fallback_name="state_validation_binding.json",
    )
    binding = _read_json(binding_path)
    binding_signature = _verify_payload_signature(
        binding, "binding_signature", label="V4 state-validation binding"
    )
    if (
        binding.get("schema_version")
        != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.state_validation_binding.v1"
        or binding.get("contract_revision") != manifest["contract_revision"]
        or binding.get("campaign_signature") != manifest["campaign_signature"]
        or binding.get("status") != PREFLIGHT_ACCEPTED_STATUS
        or binding_signature != manifest.get("state_validation_binding_signature")
        or manifest.get("state_validation_binding_status")
        != PREFLIGHT_ACCEPTED_STATUS
        or binding.get("operating_points_artifact_signature")
        != provenance["artifact_signature"]
        or binding.get("v4_plan_signature") != provenance["plan_signature"]
        or binding.get("v4_development_selection_signature")
        != provenance["selection_signature"]
        or binding.get("v4_holdout_signature") != provenance["holdout_signature"]
        or binding.get("v4_trace_index_signature")
        != provenance["trace_index_signature"]
        or binding.get("campaign_seeds") != list(EXPECTED_SEEDS)
        or binding.get("design_seed") != DESIGN_SEED
        or binding.get("design_seed_in_acceptance_statistics") is not False
        or binding.get("state_validation_engine_runs_in_campaign") != 0
        or binding.get("imported_official_service_proof_count") != 90
        or binding.get("imported_official_shipment_trace_count") != 90
        or binding.get("retuning_after_holdout") is not False
    ):
        raise CampaignValidationError("Accepted V4 state binding is inconsistent")
    achieved_services = _achieved_services_from_v4_binding(binding, manifest)

    registry_path = _resolve_signed_artifact(
        evidence=evidence,
        manifest=manifest,
        path_key="target_registry",
        sha_key="target_registry_sha256",
        fallback_name="target_registry.json",
    )
    registry = _read_json(registry_path)
    _validate_v4_registry(
        registry,
        manifest=manifest,
        lane_identity=lane_identity,
        disruption_window_days=disruption_window_days,
        quantity_ratio_limit=quantity_ratio_limit,
    )
    progress_path = evidence.manifest_path.parent / "target_discovery" / "progress.json"
    if not progress_path.is_file():
        raise CampaignValidationError("V4 target-discovery progress is missing")
    progress = _read_json(progress_path)
    if (
        progress.get("campaign_signature") != manifest["campaign_signature"]
        or progress.get("status") != "complete"
        or progress.get("engine_runs_planned") != 3
        or progress.get("engine_runs_completed") != 3
        or progress.get("engine_runs_failed") != 0
        or progress.get("running") != 0
        or progress.get("v4_service_proofs_imported") != 90
        or progress.get("v4_shipment_traces_imported") != 90
        or progress.get("v4_holdout_engine_reruns") != 0
        or manifest.get("target_discovery_status") != "complete"
    ):
        raise CampaignValidationError("V4 three-run discovery/import is incomplete")
    design_hashes = _validate_v4_design_evidence(evidence, manifest)
    provenance = {**provenance, "design_evidence_sha256_by_state": design_hashes}
    return SignedCampaignContext(
        manifest=manifest,
        operating_point_provenance=provenance,
        preflight=binding,
        registry=registry,
        achieved_services=achieved_services,
        lane_identity=lane_identity,
        shard_ids=shard_ids,
        disruption_window_days=disruption_window_days,
        preflight_path=binding_path,
        registry_path=registry_path,
        discovery_progress_path=progress_path,
    )


def validate_shard_progress(
    campaign_root: Path, *, campaign_signature: str, expected_shard_ids: frozenset[str]
) -> dict[str, Any]:
    paths = sorted(campaign_root.resolve().glob("shards/*/progress.json"))
    if len(paths) != EXPECTED_SHARD_COUNT:
        raise CampaignValidationError(
            f"Expected {EXPECTED_SHARD_COUNT} shard progress files, found {len(paths)}"
        )
    seen: set[str] = set()
    digests: dict[str, str] = {}
    for path in paths:
        payload = _read_json(path)
        shard_id = str(payload.get("shard_id") or path.parent.name)
        running = payload.get("running_case_keys") or []
        if (
            payload.get("schema_version")
            != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.progress.v1"
            or payload.get("campaign_signature") != campaign_signature
            or payload.get("status") != "complete"
            or int(payload.get("planned_case_count", -1)) != EXPECTED_ROWS_PER_SHARD
            or int(payload.get("completed_case_count", -1)) != EXPECTED_ROWS_PER_SHARD
            or int(payload.get("failed_case_count", -1)) != 0
            or bool(running)
            or bool(payload.get("errors"))
            or shard_id != path.parent.name
            or shard_id in seen
        ):
            raise CampaignValidationError(
                f"Shard is not complete and error-free: {path}"
            )
        seen.add(shard_id)
        digests[str(path)] = _sha256(path)
    if seen != set(expected_shard_ids):
        raise CampaignValidationError(
            "Shard progress IDs differ from the signed manifest"
        )
    return {
        "status": "complete",
        "shard_count": len(paths),
        "planned_case_count": EXPECTED_TOTAL_COUNT,
        "completed_case_count": EXPECTED_TOTAL_COUNT,
        "failed_case_count": 0,
        "progress_paths_sha256": digests,
    }


def _validate_case_evidence_file(
    path: Path,
    *,
    manifest: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a compact case proof against its metric-row identity."""

    payload = _read_json(path)
    _verify_payload_signature(payload, "evidence_signature", label="V4 case evidence")
    for field, value in expected.items():
        if payload.get(field) != value:
            raise CampaignValidationError(
                f"V4 case evidence {field} differs from its metric row: {path}"
            )
    metrics = payload.get("metrics")
    if (
        payload.get("schema_version") != INPUT_METRIC_SCHEMA_VERSION
        or payload.get("contract_revision")
        != "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
        or payload.get("campaign_signature") != manifest["campaign_signature"]
        or payload.get("engine_sha256") != manifest["engine_sha256"]
        or payload.get("valid") is not True
        or payload.get("status") not in {"valid", "valid_no_exposure"}
        or payload.get("validation_errors") != []
        or payload.get("quality_branch_included") is not False
        or payload.get("availability_incident_included") is not False
        or payload.get("supplier_state_dependent_risks_enabled") is not False
        or not isinstance(metrics, Mapping)
        or not _is_sha256(metrics.get("warmup_core_state_sha256"))
    ):
        raise CampaignValidationError(f"V4 case evidence fails closed: {path}")
    return payload


def _smoke_identity(
    context: SignedCampaignContext,
) -> tuple[int, str]:
    lane_order = {
        str(row["lane_id"]): index
        for index, row in enumerate(context.manifest.get("lanes") or [])
    }
    seed_order = {seed: index for index, seed in enumerate(EXPECTED_SEEDS)}
    candidates = [
        row
        for row in context.registry.get("targets") or []
        if row.get("operating_point_id") == "op_93"
        and row.get("seed_cross_state_exposure_comparable") is True
        and str(row.get("target_status") or "").startswith("identified_")
        and float(row.get("target_planned_qty") or 0.0) > NUMERIC_TOLERANCE
    ]
    if not candidates:
        raise CampaignValidationError(
            "No positive comparable op_93 cell exists for the mandatory V4 smoke"
        )
    try:
        selected = min(
            candidates,
            key=lambda row: (
                lane_order[str(row["lane_id"])],
                seed_order[int(row["seed"])],
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CampaignValidationError("Malformed V4 smoke target identity") from exc
    return int(selected["seed"]), str(selected["lane_id"])


def validate_v4_smoke(
    campaign_root: Path,
    *,
    context: SignedCampaignContext,
    campaign_case_signatures: set[str],
) -> dict[str, Any]:
    """Require one signed, non-reusable baseline + two-incident smoke proof."""

    root = campaign_root.resolve()
    seed, lane_id = _smoke_identity(context)
    shard_id = f"smoke__op_93__seed_{seed}"
    smoke_dir = root / "smoke" / shard_id
    progress_path = smoke_dir / "progress.json"
    shard_manifest_path = smoke_dir / "shard_manifest.json"
    metrics_path = smoke_dir / "campaign_metrics.csv"
    if not all(path.is_file() for path in (progress_path, shard_manifest_path, metrics_path)):
        raise CampaignValidationError("Mandatory V4 smoke outputs are missing")
    progress = _read_json(progress_path)
    shard_manifest = _read_json(shard_manifest_path)
    if (
        progress.get("schema_version")
        != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.progress.v1"
        or progress.get("campaign_signature")
        != context.manifest["campaign_signature"]
        or progress.get("shard_id") != shard_id
        or progress.get("operating_point_id") != "op_93"
        or progress.get("seed_ids") != [seed]
        or progress.get("status") != "complete"
        or int(progress.get("planned_case_count", -1)) != 3
        or int(progress.get("completed_case_count", -1)) != 3
        or int(progress.get("failed_case_count", -1)) != 0
        or progress.get("running_case_keys") != []
        or progress.get("errors") != []
    ):
        raise CampaignValidationError("Mandatory V4 smoke progress fails closed")
    immutable_shard = dict(shard_manifest)
    for field in (
        "completed_case_count",
        "valid_case_count",
        "invalid_or_not_applicable_case_count",
        "runtime_failure_count",
        "completed_at_utc",
    ):
        immutable_shard.pop(field, None)
    shard_signature = str(immutable_shard.pop("shard_signature", ""))
    immutable_shard["status"] = "planned"
    if (
        shard_manifest.get("schema_version")
        != f"{INPUT_CAMPAIGN_SCHEMA_VERSION}.shard.v1"
        or shard_manifest.get("campaign_signature")
        != context.manifest["campaign_signature"]
        or shard_manifest.get("shard_id") != shard_id
        or shard_manifest.get("operating_point_id") != "op_93"
        or shard_manifest.get("seed_ids") != [seed]
        or shard_manifest.get("lane_ids") != [lane_id]
        or shard_manifest.get("mechanisms") != list(MECHANISMS)
        or shard_manifest.get("execution_scope") != "smoke_non_reusable"
        or shard_manifest.get("status") != "complete"
        or int(shard_manifest.get("planned_case_count", -1)) != 3
        or int(shard_manifest.get("completed_case_count", -1)) != 3
        or int(shard_manifest.get("valid_case_count", -1)) != 3
        or int(shard_manifest.get("invalid_or_not_applicable_case_count", -1)) != 0
        or int(shard_manifest.get("runtime_failure_count", -1)) != 0
        or not _is_sha256(shard_signature)
        or shard_signature != _stable_sha256(immutable_shard)
    ):
        raise CampaignValidationError("Mandatory V4 smoke shard contract fails closed")
    smoke_frame = _read_metrics((metrics_path,))
    if len(smoke_frame) != 3:
        raise CampaignValidationError("Mandatory V4 smoke must contain exactly three rows")
    expected_case_keys = {
        f"op_93__baseline__seed_{seed}",
        *(
            f"op_93__{lane_id}__{mechanism}__seed_{seed}"
            for mechanism in MECHANISMS
        ),
    }
    if (
        set(smoke_frame["schema_version"]) != {INPUT_METRIC_SCHEMA_VERSION}
        or set(smoke_frame["campaign_signature"])
        != {context.manifest["campaign_signature"]}
        or set(smoke_frame["engine_sha256"])
        != {context.manifest["engine_sha256"]}
        or set(smoke_frame["shard_id"]) != {shard_id}
        or set(smoke_frame["operating_point_id"]) != {"op_93"}
        or {int(value) for value in smoke_frame["seed"]} != {seed}
        or set(smoke_frame["case_key"]) != expected_case_keys
        or set(smoke_frame["stage"]) != {"baseline", "incident"}
        or not smoke_frame["valid"].map(_truthy).all()
        or smoke_frame["validation_errors"].map(_nonempty).any()
        or not smoke_frame["case_signature"].map(_is_sha256).all()
        or smoke_frame["case_signature"].duplicated().any()
        or set(smoke_frame["case_signature"]) & campaign_case_signatures
    ):
        raise CampaignValidationError("Mandatory V4 smoke metric identity is invalid")
    baseline_row = smoke_frame.loc[smoke_frame["stage"] == "baseline"]
    incident_rows = smoke_frame.loc[smoke_frame["stage"] == "incident"]
    warmup_hashes = {
        str(value or "") for value in smoke_frame["warmup_core_state_sha256"]
    }
    if (
        len(baseline_row) != 1
        or len(incident_rows) != 2
        or set(incident_rows["lane_id"]) != {lane_id}
        or set(incident_rows["mechanism"]) != set(MECHANISMS)
        or not incident_rows["incident_physically_exercised"].map(_truthy).all()
        or set(incident_rows["baseline_case_signature"])
        != {str(baseline_row.iloc[0]["case_signature"])}
        or len(warmup_hashes) != 1
        or any(not _is_sha256(value) for value in warmup_hashes)
    ):
        raise CampaignValidationError("Mandatory V4 smoke pairing/exposure is invalid")
    proof_hashes: dict[str, str] = {}
    for row in smoke_frame.to_dict(orient="records"):
        case_key = str(row["case_key"])
        evidence_path = smoke_dir / "case_evidence" / f"{case_key}.json"
        payload = _validate_case_evidence_file(
            evidence_path,
            manifest=context.manifest,
            expected={
                "case_key": case_key,
                "case_signature": str(row["case_signature"]),
                "operating_point_id": "op_93",
                "seed": seed,
                "stage": str(row["stage"]),
                "shard_id": shard_id,
            },
        )
        if (
            payload["metrics"].get("warmup_core_state_sha256")
            != row["warmup_core_state_sha256"]
        ):
            raise CampaignValidationError(
                "Mandatory V4 smoke warmup evidence differs from its metric row"
            )
        if row["stage"] == "incident":
            mechanism = str(row["mechanism"])
            lane = payload.get("lane")
            mechanism_payload = payload.get("mechanism")
            risk_sha = str(payload.get("risk_csv_sha256") or "")
            risk_path = smoke_dir / "inputs" / "risk_events" / f"{case_key}.csv"
            if (
                not isinstance(lane, Mapping)
                or lane.get("lane_id") != lane_id
                or not isinstance(mechanism_payload, Mapping)
                or mechanism_payload.get("key") != mechanism
                or payload.get("baseline_case_signature")
                != str(baseline_row.iloc[0]["case_signature"])
                or not isinstance(payload.get("incident_proof"), Mapping)
                or payload["incident_proof"].get("incident_physically_exercised")
                is not True
                or not _is_sha256(risk_sha)
                or not risk_path.is_file()
                or _sha256(risk_path) != risk_sha
            ):
                raise CampaignValidationError(
                    "Mandatory V4 smoke incident evidence is incomplete"
                )
        proof_hashes[case_key] = _sha256(evidence_path)
    return {
        "status": "complete_validated_non_reusable",
        "operating_point_id": "op_93",
        "seed": seed,
        "lane_id": lane_id,
        "case_count": 3,
        "progress_path": str(progress_path.relative_to(root).as_posix()),
        "progress_sha256": _sha256(progress_path),
        "shard_manifest_path": str(shard_manifest_path.relative_to(root).as_posix()),
        "shard_manifest_sha256": _sha256(shard_manifest_path),
        "metrics_path": str(metrics_path.relative_to(root).as_posix()),
        "metrics_sha256": _sha256(metrics_path),
        "case_evidence_sha256": proof_hashes,
        "campaign_case_signatures_reused": False,
    }


def _require_columns(frame: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise CampaignValidationError(
            "Missing adaptive campaign columns: " + ", ".join(missing)
        )


def _deduplicate_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    payload_columns = sorted(
        column for column in frame.columns if not column.startswith("_source_")
    )
    kept: list[int] = []
    seen: dict[tuple[Any, ...], tuple[str, ...]] = {}
    discarded = 0
    for index, row in frame.iterrows():
        stage = _normalise_stage(row["stage"])
        if stage == "baseline":
            key = (stage, str(row["operating_point_id"]), str(row["seed"]))
        else:
            key = (
                stage,
                str(row["operating_point_id"]),
                str(row["lane_id"]),
                _normalise_mechanism(row["mechanism"]),
                str(row["seed"]),
            )
        payload = tuple(str(row[column]) for column in payload_columns)
        previous = seen.get(key)
        if previous is None:
            seen[key] = payload
            kept.append(index)
        elif previous == payload:
            discarded += 1
        else:
            raise CampaignValidationError(f"Divergent duplicate campaign cell: {key!r}")
    return frame.loc[kept].copy().reset_index(drop=True), discarded


def _numeric(series: pd.Series, *, field: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    invalid = values.isna() | ~np.isfinite(values)
    if invalid.any():
        raise CampaignValidationError(f"Non-finite numeric field: {field}")
    return values.astype(float)


def _assert_close(left: pd.Series, right: pd.Series, *, label: str) -> None:
    if not np.allclose(
        left.to_numpy(dtype=float),
        right.to_numpy(dtype=float),
        rtol=1e-9,
        atol=NUMERIC_TOLERANCE,
    ):
        raise CampaignValidationError(
            f"Paired metric arithmetic is inconsistent: {label}"
        )


def validate_and_pair(
    frame: pd.DataFrame, context: SignedCampaignContext
) -> tuple[pd.DataFrame, dict[str, Any]]:
    _require_columns(frame)
    frame, duplicate_count = _deduplicate_rows(frame)
    frame["stage"] = frame["stage"].map(_normalise_stage)
    frame["mechanism"] = frame["mechanism"].map(_normalise_mechanism)
    frame["status"] = frame["status"].astype(str).str.strip().str.casefold()
    if set(frame["stage"]) != {"baseline", "incident"}:
        raise CampaignValidationError(
            "Metrics must contain baseline and incident stages only"
        )
    for field in (
        "operating_point_service_pct",
        "simulation_days",
        "state_evaluation_days",
        "seed",
    ):
        frame[field] = _numeric(frame[field], field=field)
    frame["seed"] = frame["seed"].astype(int)
    if set(frame["schema_version"]) != {INPUT_METRIC_SCHEMA_VERSION}:
        raise CampaignValidationError("Unexpected case metrics schema")
    campaign_signatures = set(frame["campaign_signature"])
    engine_signatures = {value.casefold() for value in frame["engine_sha256"]}
    if campaign_signatures != {context.manifest["campaign_signature"]}:
        raise CampaignValidationError("Metrics do not use one signed campaign")
    if engine_signatures != {str(context.manifest["engine_sha256"]).casefold()}:
        raise CampaignValidationError("Metrics do not use one signed engine")
    if (
        not frame["case_signature"].map(_is_sha256).all()
        or not frame["warmup_core_state_sha256"].map(_is_sha256).all()
        or not frame["summary_sha256"].map(_is_sha256).all()
    ):
        raise CampaignValidationError("Case evidence digests are missing")
    if frame["case_signature"].duplicated().any():
        raise CampaignValidationError(
            "Case signatures must be unique after deduplication"
        )
    if (
        not frame["valid"].map(_truthy).all()
        or frame["validation_errors"].map(_nonempty).any()
    ):
        raise CampaignValidationError("Invalid simulation evidence is present")
    if set(frame["operating_point_id"]) != set(OPERATING_POINTS) or set(
        frame["seed"]
    ) != set(EXPECTED_SEEDS):
        raise CampaignValidationError(
            "Operating-state or paired-seed matrix is incomplete"
        )
    if (
        not (frame["state_evaluation_days"] == STATE_EVALUATION_DAYS).all()
        or (frame["simulation_days"] < STATE_EVALUATION_DAYS).any()
    ):
        raise CampaignValidationError(
            "Case horizons do not preserve the J0-J719 state window"
        )

    baseline = frame.loc[frame["stage"] == "baseline"].copy()
    incident = frame.loc[frame["stage"] == "incident"].copy()
    if (
        len(baseline) != EXPECTED_BASELINE_COUNT
        or len(incident) != EXPECTED_INCIDENT_COUNT
    ):
        raise CampaignValidationError(
            f"Expected {EXPECTED_BASELINE_COUNT} baselines and {EXPECTED_INCIDENT_COUNT} incidents"
        )
    if set(baseline["mechanism"]) != {"baseline"} or set(incident["mechanism"]) != set(
        MECHANISMS
    ):
        raise CampaignValidationError("Unexpected baseline or incident mechanisms")
    if set(baseline["status"]) != {"valid"}:
        raise CampaignValidationError("Every paired baseline must have valid status")
    expected_baselines = {
        (point, seed) for point in OPERATING_POINTS for seed in EXPECTED_SEEDS
    }
    actual_baselines = set(
        zip(baseline["operating_point_id"], baseline["seed"], strict=False)
    )
    if (
        actual_baselines != expected_baselines
        or baseline.duplicated(["operating_point_id", "seed"]).any()
    ):
        raise CampaignValidationError("Baseline matrix is incomplete or duplicated")
    expected_incidents = {
        (point, lane, mechanism, seed)
        for point in OPERATING_POINTS
        for lane in context.lane_identity
        for mechanism in MECHANISMS
        for seed in EXPECTED_SEEDS
    }
    actual_incidents = set(
        zip(
            incident["operating_point_id"],
            incident["lane_id"],
            incident["mechanism"],
            incident["seed"],
            strict=False,
        )
    )
    if (
        actual_incidents != expected_incidents
        or incident.duplicated(
            ["operating_point_id", "lane_id", "mechanism", "seed"]
        ).any()
    ):
        raise CampaignValidationError(
            "The complete 3x18x2x30 incident matrix is required"
        )
    if set(incident["shard_id"]) != set(context.shard_ids):
        raise CampaignValidationError(
            "Metrics shard IDs differ from the signed manifest"
        )

    identities = incident[
        [
            "lane_id",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "target_product_id",
        ]
    ].drop_duplicates()
    if len(identities) != EXPECTED_LANE_COUNT:
        raise CampaignValidationError("Lane identity changes across campaign cells")
    if set(incident["target_product_id"]) != {"268091", "268967"}:
        raise CampaignValidationError("Target product must be exactly 268091 or 268967")
    for row in identities.itertuples(index=False):
        actual = (
            row.supplier_id,
            row.item_id,
            row.dst_node_id,
            row.edge_id,
            row.target_product_id,
        )
        if context.lane_identity.get(row.lane_id) != actual:
            raise CampaignValidationError(
                f"Physical identity mismatch for lane {row.lane_id}"
            )

    for field in INCIDENT_NUMERIC_COLUMNS:
        incident[field] = _numeric(incident[field], field=field)
    bool_fields = (
        "impact_window_fully_observed",
        "causal_window_defined",
        "causal_window_fully_observed",
        "incident_physically_exercised",
        "target_selected_independently_by_operating_point",
        "state_comparison_valid",
        "seed_cross_state_exposure_comparable",
    )
    for field in bool_fields:
        incident[field] = incident[field].map(_truthy)
    if incident["target_selected_independently_by_operating_point"].any():
        raise CampaignValidationError(
            "Target dates were selected independently by operating state"
        )
    if set(incident["target_reference_kind"]) != {TARGET_REFERENCE_KIND}:
        raise CampaignValidationError(
            "Incident targets are not signed simulated baseline references"
        )
    if not incident["target_status"].str.startswith("identified_").all():
        raise CampaignValidationError("Every fixed calendar target must be identified")
    if (
        (incident["target_window_days"] != context.disruption_window_days).any()
        or (
            incident["target_window_end_day"] - incident["target_window_start_day"] + 1
            != context.disruption_window_days
        ).any()
        or (incident["risk_start_day"] != incident["target_window_start_day"]).any()
        or (incident["risk_end_day"] != incident["target_window_end_day"]).any()
    ):
        raise CampaignValidationError(
            "Incident risk windows do not match the signed uniform window"
        )
    if (
        (incident["impact_window_days"] != BUSINESS_WINDOW_DAYS).any()
        or (
            incident["impact_window_start_day"] != incident["target_window_start_day"]
        ).any()
        or (
            incident["impact_window_end_day"] - incident["impact_window_start_day"] + 1
            != BUSINESS_WINDOW_DAYS
        ).any()
        or not incident["impact_window_fully_observed"].all()
        or not incident["causal_window_fully_observed"].all()
        or (incident["impact_window_end_day"] >= incident["simulation_days"]).any()
        or (incident["causal_window_end_day"] >= incident["simulation_days"]).any()
        or (
            incident["causal_window_end_day"] - incident["causal_window_start_day"] + 1
            != incident["causal_window_days"]
        ).any()
        or (incident["required_simulation_days"] > incident["simulation_days"]).any()
    ):
        raise CampaignValidationError(
            "Adaptive horizons do not fully contain both effect windows"
        )

    for mechanism, contract in MECHANISM_CONTRACT.items():
        selected = incident["mechanism"] == mechanism
        if set(incident.loc[selected, "risk_type"]) != {
            contract["risk_type"]
        } or not np.allclose(
            incident.loc[selected, "risk_value"],
            contract["risk_value"],
            atol=NUMERIC_TOLERANCE,
        ):
            raise CampaignValidationError(
                f"Physical incident proof is invalid for {mechanism}"
            )
    if not np.allclose(
        incident.loc[incident["mechanism"] == "transport_delay", "arrival_delay_days"],
        120.0,
        atol=NUMERIC_TOLERANCE,
    ) or not np.allclose(
        incident.loc[
            incident["mechanism"] == "planned_delivery_shortfall",
            "arrival_delay_days",
        ],
        0.0,
        atol=NUMERIC_TOLERANCE,
    ):
        raise CampaignValidationError("Incident arrival-delay proof is inconsistent")
    if any(
        token in value.casefold()
        for value in incident["risk_type"].astype(str)
        for token in FORBIDDEN_TOKENS
    ):
        raise CampaignValidationError(
            "A forbidden quality/availability/capacity/stock risk is present"
        )

    baseline_lookup = baseline.set_index(["operating_point_id", "seed"])
    for row in incident.itertuples(index=False):
        paired_baseline = baseline_lookup.loc[(row.operating_point_id, row.seed)]
        if (
            row.baseline_case_signature != paired_baseline.case_signature
            or row.warmup_core_state_sha256 != paired_baseline.warmup_core_state_sha256
            or float(paired_baseline.simulation_days) + NUMERIC_TOLERANCE
            < float(row.required_simulation_days)
        ):
            raise CampaignValidationError(
                "Incident/baseline pairing, warmup state or adaptive horizon differs"
            )

    _assert_close(
        incident["impact_service_loss_268091_pp"],
        incident["baseline_impact_service_268091_pct"]
        - incident["impact_service_268091_pct"],
        label="fixed360 service 268091",
    )
    _assert_close(
        incident["impact_service_loss_268967_pp"],
        incident["baseline_impact_service_268967_pct"]
        - incident["impact_service_268967_pct"],
        label="fixed360 service 268967",
    )
    _assert_close(
        incident["impact_service_loss_global_pp"],
        incident["baseline_impact_service_global_pct"]
        - incident["impact_service_global_pct"],
        label="fixed360 global service",
    )
    _assert_close(
        incident["causal_service_loss_268091_pp"],
        incident["baseline_causal_service_268091_pct"]
        - incident["causal_service_268091_pct"],
        label="causal service 268091",
    )
    _assert_close(
        incident["causal_service_loss_268967_pp"],
        incident["baseline_causal_service_268967_pct"]
        - incident["causal_service_268967_pct"],
        label="causal service 268967",
    )
    _assert_close(
        incident["causal_service_loss_global_pp"],
        incident["baseline_causal_service_global_pct"]
        - incident["causal_service_global_pct"],
        label="causal global service",
    )
    expected_fed_impact = np.where(
        incident["target_product_id"] == "268091",
        incident["impact_service_loss_268091_pp"],
        incident["impact_service_loss_268967_pp"],
    )
    expected_fed_causal = np.where(
        incident["target_product_id"] == "268091",
        incident["causal_service_loss_268091_pp"],
        incident["causal_service_loss_268967_pp"],
    )
    _assert_close(
        incident[PRIMARY_METRIC],
        pd.Series(expected_fed_impact, index=incident.index),
        label="fed product fixed360",
    )
    _assert_close(
        incident[CAUSAL_RANK_METRIC],
        pd.Series(expected_fed_causal, index=incident.index),
        label="fed product causal",
    )
    for scope in ("impact", "causal"):
        for product in ("268091", "268967", "global"):
            _assert_close(
                incident[f"baseline_{scope}_demand_{product}_qty"],
                incident[f"{scope}_demand_{product}_qty"],
                label=f"{scope} demand {product}",
            )
    service_fields = [
        field
        for field in incident.columns
        if (
            field.startswith("baseline_impact_service_")
            or field.startswith("impact_service_")
            or field.startswith("baseline_causal_service_")
            or field.startswith("causal_service_")
        )
        and not field.endswith("_loss_pp")
    ]
    if (incident[service_fields] < -NUMERIC_TOLERANCE).any(axis=None) or (
        incident[service_fields] > 100.0 + NUMERIC_TOLERANCE
    ).any(axis=None):
        raise CampaignValidationError(
            "Window service percentages must remain in [0, 100]"
        )
    fed_impact_demand = np.where(
        incident["target_product_id"] == "268091",
        incident["baseline_impact_demand_268091_qty"],
        incident["baseline_impact_demand_268967_qty"],
    )
    fed_causal_demand = np.where(
        incident["target_product_id"] == "268091",
        incident["baseline_causal_demand_268091_qty"],
        incident["baseline_causal_demand_268967_qty"],
    )
    if (
        incident[
            [
                "baseline_impact_demand_268091_qty",
                "baseline_impact_demand_268967_qty",
                "baseline_impact_demand_global_qty",
                "baseline_causal_demand_268091_qty",
                "baseline_causal_demand_268967_qty",
                "baseline_causal_demand_global_qty",
            ]
        ]
        <= NUMERIC_TOLERANCE
    ).any(axis=None):
        raise CampaignValidationError("Paired window demand must be strictly positive")
    arithmetic_contracts = (
        (
            incident["impact_on_due_loss_fed_product_qty"],
            incident[PRIMARY_METRIC] / 100.0 * fed_impact_demand,
            "fixed360 fed-product on-due quantity",
        ),
        (
            incident["impact_on_due_loss_global_qty"],
            incident["impact_service_loss_global_pp"]
            / 100.0
            * incident["baseline_impact_demand_global_qty"],
            "fixed360 global on-due quantity",
        ),
        (
            incident["causal_on_due_loss_fed_product_qty"],
            incident[CAUSAL_RANK_METRIC] / 100.0 * fed_causal_demand,
            "causal fed-product on-due quantity",
        ),
        (
            incident["causal_on_due_loss_global_qty"],
            incident["causal_service_loss_global_pp"]
            / 100.0
            * incident["baseline_causal_demand_global_qty"],
            "causal global on-due quantity",
        ),
        (
            incident["impact_on_due_loss_fed_product_share_of_demand"],
            incident["impact_on_due_loss_fed_product_qty"] / fed_impact_demand,
            "fixed360 fed-product demand share",
        ),
        (
            incident["impact_on_due_loss_global_share_of_demand"],
            incident["impact_on_due_loss_global_qty"]
            / incident["baseline_impact_demand_global_qty"],
            "fixed360 global demand share",
        ),
        (
            incident["impact_backlog_qty_days_per_demand_unit"],
            incident["impact_backlog_qty_days_delta"]
            / incident["baseline_impact_demand_global_qty"],
            "fixed360 backlog demand normalization",
        ),
        (
            incident["impact_production_loss_fed_product_share_of_demand"],
            incident["impact_production_loss_fed_product_qty"] / fed_impact_demand,
            "fixed360 production demand normalization",
        ),
        (
            incident["causal_on_due_loss_fed_product_share_of_demand"],
            incident["causal_on_due_loss_fed_product_qty"] / fed_causal_demand,
            "causal fed-product demand share",
        ),
        (
            incident["causal_on_due_loss_global_share_of_demand"],
            incident["causal_on_due_loss_global_qty"]
            / incident["baseline_causal_demand_global_qty"],
            "causal global demand share",
        ),
        (
            incident["causal_backlog_qty_days_per_demand_unit"],
            incident["causal_backlog_qty_days_delta"]
            / incident["baseline_causal_demand_global_qty"],
            "causal backlog demand normalization",
        ),
        (
            incident["causal_production_loss_fed_product_share_of_demand"],
            incident["causal_production_loss_fed_product_qty"] / fed_causal_demand,
            "causal production demand normalization",
        ),
    )
    for actual, expected_values, label in arithmetic_contracts:
        _assert_close(
            actual, pd.Series(expected_values, index=incident.index), label=label
        )

    delay = incident["mechanism"] == "transport_delay"
    shortfall = incident["mechanism"] == "planned_delivery_shortfall"
    delay_dose = pd.to_numeric(
        incident.loc[delay, "incident_effective_dose_qty_days"], errors="coerce"
    )
    shortfall_dose = pd.to_numeric(
        incident.loc[shortfall, "incident_effective_dose_qty"], errors="coerce"
    )
    if (
        delay_dose.isna().any()
        or shortfall_dose.isna().any()
        or (delay_dose < 0).any()
        or (shortfall_dose < 0).any()
    ):
        raise CampaignValidationError("Effective incident exposure dose is missing")
    incident["effective_exposure_dose"] = 0.0
    incident.loc[delay, "effective_exposure_dose"] = delay_dose
    incident.loc[shortfall, "effective_exposure_dose"] = shortfall_dose
    incident["effective_exposure_dose_unit"] = np.where(
        delay, "unite_jour_de_retard", "unite_non_livree"
    )
    no_exposure = ~incident["incident_physically_exercised"]
    adverse_fields = [field for field in STATISTIC_METRICS if field in incident.columns]
    if (
        (
            incident.loc[no_exposure, "effective_exposure_dose"].abs()
            > NUMERIC_TOLERANCE
        ).any()
        or (incident.loc[no_exposure, adverse_fields].abs() > NUMERIC_TOLERANCE).any(
            axis=None
        )
        or (
            incident.loc[~no_exposure, "effective_exposure_dose"] <= NUMERIC_TOLERANCE
        ).any()
    ):
        raise CampaignValidationError(
            "Zero-exposure cases do not have explicit zero effects and dose"
        )
    if (
        not np.allclose(
            incident.loc[delay, "effective_exposure_dose"],
            120.0 * incident.loc[delay, "incident_affected_shipped_qty"],
            atol=NUMERIC_TOLERANCE,
        )
        or not np.allclose(
            incident.loc[shortfall, "effective_exposure_dose"],
            incident.loc[shortfall, "quantity_shortfall_qty"],
            atol=NUMERIC_TOLERANCE,
        )
        or (
            incident.loc[
                ~no_exposure, ["risk_applied_row_count", "risk_applied_event_count"]
            ]
            < 1
        ).any(axis=None)
        or (
            incident.loc[
                no_exposure, ["risk_applied_row_count", "risk_applied_event_count"]
            ]
            != 0
        ).any(axis=None)
        or (
            incident.loc[no_exposure, "target_planned_qty"].abs() > NUMERIC_TOLERANCE
        ).any()
        or (incident.loc[no_exposure, "target_shipment_count"] != 0).any()
        or (incident.loc[~no_exposure, "target_planned_qty"] <= NUMERIC_TOLERANCE).any()
        or (incident.loc[~no_exposure, "target_shipment_count"] < 1).any()
        or not (
            incident.loc[no_exposure, "target_status"]
            == "identified_registered_window_no_positive_flow"
        ).all()
    ):
        raise CampaignValidationError(
            "Physical exposure trace and effective dose are inconsistent"
        )
    invalid_causal_definition = no_exposure ^ (~incident["causal_window_defined"])
    if invalid_causal_definition.any():
        raise CampaignValidationError(
            "Causal-window definition does not match physical exposure"
        )
    allowed_status = np.where(no_exposure, "valid_no_exposure", "valid")
    if not np.array_equal(incident["status"].to_numpy(), allowed_status):
        raise CampaignValidationError(
            "Incident status does not distinguish zero exposure"
        )

    registry_by_key = {
        (str(row["operating_point_id"]), int(row["seed"]), str(row["lane_id"])): row
        for row in context.registry["targets"]
    }
    registry_fields = (
        "target_window_start_day",
        "target_window_end_day",
        "target_window_days",
        "target_shipment_count",
        "target_planned_qty",
        "target_expected_delivered_qty",
        "target_status",
        "seed_cross_state_exposure_comparable",
        "state_comparison_valid",
        "comparable_campaign_seed_count",
        "required_comparable_seed_count",
    )
    for row in incident.itertuples(index=False):
        target = registry_by_key[(row.operating_point_id, row.seed, row.lane_id)]
        for field in registry_fields:
            actual = getattr(row, field)
            expected_value = target.get(field, "")
            if field in {
                "target_window_start_day",
                "target_window_end_day",
                "target_window_days",
                "target_shipment_count",
                "target_planned_qty",
                "target_expected_delivered_qty",
                "comparable_campaign_seed_count",
                "required_comparable_seed_count",
            }:
                if not math.isclose(
                    float(actual), float(expected_value), abs_tol=NUMERIC_TOLERANCE
                ):
                    raise CampaignValidationError(f"Metrics/registry mismatch: {field}")
            elif field in {
                "seed_cross_state_exposure_comparable",
                "state_comparison_valid",
            }:
                if bool(actual) != _truthy(expected_value):
                    raise CampaignValidationError(f"Metrics/registry mismatch: {field}")
            elif str(actual) != str(expected_value):
                raise CampaignValidationError(f"Metrics/registry mismatch: {field}")

    incident["operating_point_input_label_pct"] = incident[
        "operating_point_service_pct"
    ]
    incident["operating_point_service_pct"] = incident["operating_point_id"].map(
        {point: values["global"] for point, values in context.achieved_services.items()}
    )
    incident["operating_point_service_268091_pct"] = incident["operating_point_id"].map(
        {point: values["268091"] for point, values in context.achieved_services.items()}
    )
    incident["operating_point_service_268967_pct"] = incident["operating_point_id"].map(
        {point: values["268967"] for point, values in context.achieved_services.items()}
    )
    validation = {
        "campaign_signature": context.manifest["campaign_signature"],
        "engine_sha256": context.manifest["engine_sha256"],
        "input_manifest_status": context.manifest.get("status", ""),
        "contract_revision": context.manifest.get("contract_revision", ""),
        "baseline_row_count": len(baseline),
        "incident_row_count": len(incident),
        "total_row_count": len(frame),
        "divergent_duplicate_count": 0,
        "identical_duplicate_count_discarded": duplicate_count,
        "shard_ids": sorted(set(incident["shard_id"])),
        "supplier_disruption_window_days": context.disruption_window_days,
        "case_horizon_min_days": int(frame["simulation_days"].min()),
        "case_horizon_max_days": int(frame["simulation_days"].max()),
        "adaptive_horizons_observed": frame["simulation_days"].nunique() > 1,
        "achieved_operating_point_service": context.achieved_services,
    }
    return incident.sort_values(
        ["operating_point_id", "mechanism", "target_product_id", "lane_id", "seed"]
    ).reset_index(drop=True), validation


def _bootstrap_indices(
    size: int, *, replicates: int = BOOTSTRAP_REPLICATES
) -> np.ndarray:
    if size < 1 or replicates < 1:
        raise ValueError("Positive sample and bootstrap sizes are required")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    return rng.integers(0, size, size=(replicates, size), endpoint=False)


def _bootstrap_counts(indices: np.ndarray, sample_size: int) -> np.ndarray:
    counts = np.zeros((indices.shape[0], sample_size), dtype=np.float64)
    rows = np.repeat(np.arange(indices.shape[0]), indices.shape[1])
    np.add.at(counts, (rows, indices.ravel()), 1.0)
    return counts


def _metric_summary(values: np.ndarray, bootstrap_means: np.ndarray) -> dict[str, Any]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p10": _linear_quantile(values, 0.10),
        "p90": _linear_quantile(values, 0.90),
        "ci95_low": _linear_quantile(bootstrap_means, 0.025),
        "ci95_high": _linear_quantile(bootstrap_means, 0.975),
        "positive_effect_count": int(np.count_nonzero(values > NUMERIC_TOLERANCE)),
        "positive_effect_rate": float(np.mean(values > NUMERIC_TOLERANCE)),
    }


def _add_prefixed(
    target: dict[str, Any], prefix: str, values: Mapping[str, Any]
) -> None:
    for name, value in values.items():
        target[f"{prefix}_{name}"] = value


def _ratio_of_sums_bootstrap(
    numerator: np.ndarray,
    denominator: np.ndarray,
    counts: np.ndarray,
    *,
    scale: float = 1.0,
) -> tuple[float, float, float]:
    total_denominator = float(np.sum(denominator))
    point = (
        math.nan
        if total_denominator <= NUMERIC_TOLERANCE
        else scale * float(np.sum(numerator)) / total_denominator
    )
    sampled_denominator = counts @ denominator
    sampled_numerator = counts @ numerator
    ratios = np.divide(
        scale * sampled_numerator,
        sampled_denominator,
        out=np.full_like(sampled_numerator, np.nan),
        where=sampled_denominator > NUMERIC_TOLERANCE,
    )
    return point, _linear_quantile(ratios, 0.025), _linear_quantile(ratios, 0.975)


def _rank_bounds(scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(scores, dtype=float)
    rank_min = np.empty(len(values), dtype=int)
    rank_max = np.empty(len(values), dtype=int)
    for index, value in enumerate(values):
        rank_min[index] = 1 + int(np.count_nonzero(values > value + NUMERIC_TOLERANCE))
        rank_max[index] = int(np.count_nonzero(values >= value - NUMERIC_TOLERANCE))
    return rank_min, rank_max


def _bootstrap_rank_bounds(scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rank_min = np.empty_like(scores, dtype=np.int16)
    rank_max = np.empty_like(scores, dtype=np.int16)
    for index in range(scores.shape[1]):
        selected = scores[:, [index]]
        rank_min[:, index] = 1 + np.sum(scores > selected + NUMERIC_TOLERANCE, axis=1)
        rank_max[:, index] = np.sum(scores >= selected - NUMERIC_TOLERANCE, axis=1)
    return rank_min, rank_max


def _priority_status(
    *, detected: bool, robust_probability: float, possible_probability: float
) -> str:
    if not detected:
        return "no_detected_effect"
    if robust_probability >= ROBUST_TOP3_PROBABILITY:
        return "robust_priority"
    if possible_probability >= CONTENDER_TOP3_PROBABILITY:
        return "dossier_to_investigate"
    return "detected_lower_priority"


def _preserve_product_ranking(record: dict[str, Any]) -> None:
    """Keep the within-product interpretation when an all-product rank is added."""

    record["ranking_scope"] = "within_target_product"
    record["ranking_within_target_product"] = True
    for field in (
        "position",
        "rank_min",
        "rank_max",
        "rank_median",
        "bootstrap_rank_ci95_low",
        "bootstrap_rank_ci95_high",
        "bootstrap_top3_inclusion_probability",
        "bootstrap_unambiguous_top3_probability",
        "causal_rank_min",
        "causal_rank_max",
        "horizon_dependent",
        "horizon_top3_membership_changed",
        "model_effect_detected",
        "priority_status",
    ):
        record[f"within_target_product_{field}"] = record[field]


def _decorate_rank_group(
    records: list[dict[str, Any]],
    fixed_bootstrap: Sequence[np.ndarray],
    causal_bootstrap: Sequence[np.ndarray],
) -> None:
    fixed_scores = np.asarray([record[f"{PRIMARY_METRIC}_mean"] for record in records])
    causal_scores = np.asarray(
        [
            record.get("causal_ranking_score_pp", record[f"{CAUSAL_RANK_METRIC}_mean"])
            for record in records
        ]
    )
    fixed_min, fixed_max = _rank_bounds(fixed_scores)
    causal_min, causal_max = _rank_bounds(causal_scores)
    fixed_matrix = np.column_stack(fixed_bootstrap)
    causal_matrix = np.column_stack(causal_bootstrap)
    boot_min, boot_max = _bootstrap_rank_bounds(fixed_matrix)
    causal_boot_min, causal_boot_max = _bootstrap_rank_bounds(causal_matrix)
    for index, record in enumerate(records):
        possible = float(np.mean(boot_min[:, index] <= 3))
        robust = float(np.mean(boot_max[:, index] <= 3))
        detected = bool(
            record[f"{PRIMARY_METRIC}_ci95_low"] > NUMERIC_TOLERANCE
            and record[f"{PRIMARY_METRIC}_positive_effect_count"]
            >= MIN_COMPARABLE_SEEDS
        )
        exposed_lane_changed = bool(
            record.get("causal_exposed_lane_id")
            and record.get("exposed_lane_id")
            and record["causal_exposed_lane_id"] != record["exposed_lane_id"]
        )
        priority_status = _priority_status(
            detected=detected,
            robust_probability=robust,
            possible_probability=possible,
        )
        backlog_ci_low = float(
            record.get(
                "supplementary_backlog_effect_ci95_low",
                record.get(f"{SUPPLEMENTARY_BACKLOG_METRIC}_ci95_low", math.nan),
            )
        )
        backlog_positive_count = int(
            record.get(
                "supplementary_backlog_positive_effect_count",
                record.get(
                    f"{SUPPLEMENTARY_BACKLOG_METRIC}_positive_effect_count", 0
                ),
            )
        )
        supplementary_backlog_detected = bool(
            math.isfinite(backlog_ci_low)
            and backlog_ci_low > NUMERIC_TOLERANCE
            and backlog_positive_count >= MIN_COMPARABLE_SEEDS
        )
        if priority_status == "no_detected_effect" and supplementary_backlog_detected:
            priority_status = "supplementary_backlog_signal"
        record.update(
            {
                "position": int(fixed_min[index]),
                "rank_min": int(fixed_min[index]),
                "rank_max": int(fixed_max[index]),
                "rank_median": float(
                    np.median((boot_min[:, index] + boot_max[:, index]) / 2)
                ),
                "bootstrap_rank_ci95_low": _linear_quantile(boot_min[:, index], 0.025),
                "bootstrap_rank_ci95_high": _linear_quantile(boot_max[:, index], 0.975),
                "bootstrap_top3_inclusion_probability": possible,
                "bootstrap_unambiguous_top3_probability": robust,
                "causal_rank_min": int(causal_min[index]),
                "causal_rank_max": int(causal_max[index]),
                "causal_bootstrap_rank_ci95_low": _linear_quantile(
                    causal_boot_min[:, index], 0.025
                ),
                "causal_bootstrap_rank_ci95_high": _linear_quantile(
                    causal_boot_max[:, index], 0.975
                ),
                "horizon_dependent": bool(
                    fixed_min[index] != causal_min[index]
                    or fixed_max[index] != causal_max[index]
                    or exposed_lane_changed
                ),
                "horizon_top3_membership_changed": bool(
                    (fixed_min[index] <= 3) != (causal_min[index] <= 3)
                    or (fixed_max[index] <= 3) != (causal_max[index] <= 3)
                ),
                "model_effect_detected": detected,
                "horizon_exposed_lane_changed": exposed_lane_changed,
                "priority_status": priority_status,
                "supplementary_backlog_effect_detected": (
                    supplementary_backlog_detected
                ),
                "supplementary_backlog_detection_criterion": (
                    "paired_bootstrap_ci95_low_gt_0_and_positive_effect_count_ge_24"
                ),
            }
        )


def build_lane_statistics(
    paired: pd.DataFrame, *, bootstrap_replicates: int = BOOTSTRAP_REPLICATES
) -> tuple[pd.DataFrame, dict[tuple[str, str, str, str], dict[str, np.ndarray]]]:
    indices = _bootstrap_indices(
        EXPECTED_REPETITION_COUNT, replicates=bootstrap_replicates
    )
    counts = _bootstrap_counts(indices, EXPECTED_REPETITION_COUNT)
    records: list[dict[str, Any]] = []
    bootstrap_by_key: dict[tuple[str, str, str, str], dict[str, np.ndarray]] = {}
    group_fields = [
        "operating_point_id",
        "mechanism",
        "target_product_id",
        "lane_id",
    ]
    for key, raw_group in paired.groupby(group_fields, sort=True):
        seeds = tuple(int(seed) for seed in raw_group["seed"])
        if (
            len(seeds) != EXPECTED_REPETITION_COUNT
            or len(set(seeds)) != EXPECTED_REPETITION_COUNT
            or set(seeds) != set(EXPECTED_SEEDS)
        ):
            raise CampaignValidationError(f"Lane cell lacks the 30 common seeds: {key}")
        # The fresh V4 cohort has a signed pseudo-random order and is deliberately
        # not numerically sorted.  Reindex every cell to that exact order so the
        # shared bootstrap rows remain paired seed-for-seed across all cells.
        group = raw_group.set_index("seed").loc[list(EXPECTED_SEEDS)].reset_index()
        if tuple(int(seed) for seed in group["seed"]) != EXPECTED_SEEDS:
            raise CampaignValidationError(f"Lane seed order changed: {key}")
        data = group.loc[:, STATISTIC_METRICS].to_numpy(dtype=float)
        bootstrap_means = counts @ data / EXPECTED_REPETITION_COUNT
        first = group.iloc[0]
        record: dict[str, Any] = {
            "operating_point_id": key[0],
            "operating_point_service_pct": float(first["operating_point_service_pct"]),
            "operating_point_service_268091_pct": float(
                first["operating_point_service_268091_pct"]
            ),
            "operating_point_service_268967_pct": float(
                first["operating_point_service_268967_pct"]
            ),
            "operating_point_input_label_pct": float(
                first["operating_point_input_label_pct"]
            ),
            "mechanism": key[1],
            "target_product_id": key[2],
            "lane_id": key[3],
            "supplier_id": str(first["supplier_id"]),
            "item_id": str(first["item_id"]),
            "dst_node_id": str(first["dst_node_id"]),
            "edge_id": str(first["edge_id"]),
            "target_uom": str(first["target_uom"]),
            "paired_repetition_count": len(group),
            "physical_exercise_count": int(
                group["incident_physically_exercised"].sum()
            ),
            "physical_exercise_rate": float(
                group["incident_physically_exercised"].mean()
            ),
            "zero_exposure_repetition_count": int(
                (~group["incident_physically_exercised"]).sum()
            ),
            "all_repetitions_zero_exposure": bool(
                (~group["incident_physically_exercised"]).all()
            ),
            "target_planned_qty_mean": float(group["target_planned_qty"].mean()),
            "target_shipment_count_mean": float(group["target_shipment_count"].mean()),
            "effective_exposure_dose_sum": float(
                group["effective_exposure_dose"].sum()
            ),
            "effective_exposure_dose_unit": str(first["effective_exposure_dose_unit"]),
            "state_comparison_valid": bool(group["state_comparison_valid"].all()),
            "comparable_campaign_seed_count": int(
                group["seed_cross_state_exposure_comparable"].sum()
            ),
            "required_comparable_seed_count": int(
                first["required_comparable_seed_count"]
            ),
            "impact_window_days": BUSINESS_WINDOW_DAYS,
            "causal_window_days_mean": float(group["causal_window_days"].mean()),
            "simulation_days_min": int(group["simulation_days"].min()),
            "simulation_days_max": int(group["simulation_days"].max()),
        }
        for metric_index, metric in enumerate(STATISTIC_METRICS):
            _add_prefixed(
                record,
                metric,
                _metric_summary(
                    data[:, metric_index], bootstrap_means[:, metric_index]
                ),
            )
        fed_product = str(key[2])
        ratio_contracts = {
            "impact_on_due_loss_fed_product_share_of_demand_ratio_of_sums": (
                "impact_on_due_loss_fed_product_qty",
                f"baseline_impact_demand_{fed_product}_qty",
            ),
            "impact_production_loss_fed_product_share_of_demand_ratio_of_sums": (
                "impact_production_loss_fed_product_qty",
                f"baseline_impact_demand_{fed_product}_qty",
            ),
            "impact_backlog_qty_days_per_demand_unit_ratio_of_sums": (
                "impact_backlog_qty_days_delta",
                "baseline_impact_demand_global_qty",
            ),
            "causal_on_due_loss_fed_product_share_of_demand_ratio_of_sums": (
                "causal_on_due_loss_fed_product_qty",
                f"baseline_causal_demand_{fed_product}_qty",
            ),
            "causal_production_loss_fed_product_share_of_demand_ratio_of_sums": (
                "causal_production_loss_fed_product_qty",
                f"baseline_causal_demand_{fed_product}_qty",
            ),
            "causal_backlog_qty_days_per_demand_unit_ratio_of_sums": (
                "causal_backlog_qty_days_delta",
                "baseline_causal_demand_global_qty",
            ),
        }
        for name, (numerator_field, denominator_field) in ratio_contracts.items():
            point, low, high = _ratio_of_sums_bootstrap(
                group[numerator_field].to_numpy(dtype=float),
                group[denominator_field].to_numpy(dtype=float),
                counts,
            )
            record[name] = point
            record[f"{name}_ci95_low"] = low
            record[f"{name}_ci95_high"] = high
        dose = group["effective_exposure_dose"].to_numpy(dtype=float)
        for metric in (
            PRIMARY_METRIC,
            "impact_on_due_loss_fed_product_qty",
            "impact_backlog_qty_days_delta",
            "impact_production_loss_fed_product_qty",
            CAUSAL_RANK_METRIC,
            "causal_on_due_loss_fed_product_qty",
            "causal_backlog_qty_days_delta",
            "causal_production_loss_fed_product_qty",
        ):
            point, low, high = _ratio_of_sums_bootstrap(
                group[metric].to_numpy(dtype=float), dose, counts, scale=1000.0
            )
            name = f"{metric}_per_1000_effective_dose"
            record[name] = point
            record[f"{name}_ci95_low"] = low
            record[f"{name}_ci95_high"] = high
        # Presentation aliases kept for the standalone dashboard.  "Envelope"
        # always means the fixed 360-day business window here.
        alias_map = {
            "envelope_global_service_loss_pp": "impact_service_loss_global_pp",
            "envelope_backlog_qty_days_per_demand_unit": "impact_backlog_qty_days_per_demand_unit",
            "envelope_backlog_qty_days_delta": "impact_backlog_qty_days_delta",
            "fed_product_production_loss_share_of_demand": "impact_production_loss_fed_product_share_of_demand",
            "fed_product_production_loss_qty": "impact_production_loss_fed_product_qty",
            "global_service_loss_pp": "causal_service_loss_global_pp",
            "backlog_qty_days_per_demand_unit": "causal_backlog_qty_days_per_demand_unit",
            "backlog_qty_days_delta": "causal_backlog_qty_days_delta",
        }
        for alias, source in alias_map.items():
            for suffix in (
                "mean",
                "median",
                "p10",
                "p90",
                "ci95_low",
                "ci95_high",
                "positive_effect_count",
                "positive_effect_rate",
            ):
                record[f"{alias}_{suffix}"] = record[f"{source}_{suffix}"]
        records.append(record)
        bootstrap_by_key[key] = {
            "fixed": bootstrap_means[:, STATISTIC_METRICS.index(PRIMARY_METRIC)].copy(),
            "causal": bootstrap_means[
                :, STATISTIC_METRICS.index(CAUSAL_RANK_METRIC)
            ].copy(),
        }
    grouped_records: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped_records.setdefault(
            (
                str(record["operating_point_id"]),
                str(record["mechanism"]),
                str(record["target_product_id"]),
            ),
            [],
        ).append(record)
    for group_records in grouped_records.values():
        group_records.sort(key=lambda row: str(row["lane_id"]))
        keys = [
            (
                str(row["operating_point_id"]),
                str(row["mechanism"]),
                str(row["target_product_id"]),
                str(row["lane_id"]),
            )
            for row in group_records
        ]
        _decorate_rank_group(
            group_records,
            [bootstrap_by_key[key]["fixed"] for key in keys],
            [bootstrap_by_key[key]["causal"] for key in keys],
        )
        for row in group_records:
            _preserve_product_ranking(row)
    lane_stats = pd.DataFrame(records).sort_values(
        ["operating_point_id", "mechanism", "target_product_id", "position", "lane_id"]
    )
    return lane_stats.reset_index(drop=True), bootstrap_by_key


def build_supplier_statistics(
    lane_stats: pd.DataFrame,
    lane_bootstrap: Mapping[tuple[str, str, str, str], Mapping[str, np.ndarray]],
) -> tuple[pd.DataFrame, dict[tuple[str, str, str, str], dict[str, np.ndarray]]]:
    records: list[dict[str, Any]] = []
    supplier_bootstrap: dict[tuple[str, str, str, str], dict[str, np.ndarray]] = {}
    group_fields = [
        "operating_point_id",
        "mechanism",
        "target_product_id",
        "supplier_id",
    ]
    for key, group in lane_stats.groupby(group_fields, sort=True):
        ordered = group.sort_values(
            [f"{PRIMARY_METRIC}_mean", "lane_id"], ascending=[False, True]
        )
        selected = ordered.iloc[0].to_dict()
        causal_selected = group.sort_values(
            [f"{CAUSAL_RANK_METRIC}_mean", "lane_id"], ascending=[False, True]
        ).iloc[0]
        backlog_selected = group.sort_values(
            [f"{SUPPLEMENTARY_BACKLOG_METRIC}_mean", "lane_id"],
            ascending=[False, True],
        ).iloc[0]
        lane_ids = sorted(str(value) for value in group["lane_id"])
        lane_keys = [(key[0], key[1], key[2], lane_id) for lane_id in lane_ids]
        fixed_matrix = np.column_stack(
            [lane_bootstrap[lane_key]["fixed"] for lane_key in lane_keys]
        )
        causal_matrix = np.column_stack(
            [lane_bootstrap[lane_key]["causal"] for lane_key in lane_keys]
        )
        selected.update(
            {
                "representative_lane_id": selected["lane_id"],
                "exposed_lane_id": selected["lane_id"],
                "representative_lane_label_fr": "voie la plus exposée parmi les voies testées",
                "supplier_aggregation_method": "maximum_tested_lane_fixed360_primary_effect",
                "tested_lane_count": len(lane_ids),
                "tested_lane_ids": "|".join(lane_ids),
                "causal_ranking_score_pp": float(
                    causal_selected[f"{CAUSAL_RANK_METRIC}_mean"]
                ),
                "causal_exposed_lane_id": str(causal_selected["lane_id"]),
                "supplementary_backlog_lane_id": str(backlog_selected["lane_id"]),
                "supplementary_backlog_target_product_id": str(
                    backlog_selected["target_product_id"]
                ),
                "supplementary_backlog_effect_mean": float(
                    backlog_selected[f"{SUPPLEMENTARY_BACKLOG_METRIC}_mean"]
                ),
                "supplementary_backlog_effect_ci95_low": float(
                    backlog_selected[f"{SUPPLEMENTARY_BACKLOG_METRIC}_ci95_low"]
                ),
                "supplementary_backlog_effect_ci95_high": float(
                    backlog_selected[f"{SUPPLEMENTARY_BACKLOG_METRIC}_ci95_high"]
                ),
                "supplementary_backlog_positive_effect_count": int(
                    backlog_selected[
                        f"{SUPPLEMENTARY_BACKLOG_METRIC}_positive_effect_count"
                    ]
                ),
            }
        )
        # Supplier score is the maximum tested lane in each paired bootstrap
        # repetition.  Descriptive metrics remain those of the full-sample
        # most exposed lane and are labelled as such.
        records.append(selected)
        supplier_bootstrap[key] = {
            "fixed": np.max(fixed_matrix, axis=1),
            "causal": np.max(causal_matrix, axis=1),
        }
    grouped_records: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped_records.setdefault(
            (
                str(record["operating_point_id"]),
                str(record["mechanism"]),
                str(record["target_product_id"]),
            ),
            [],
        ).append(record)
    for group_records in grouped_records.values():
        group_records.sort(key=lambda row: str(row["supplier_id"]))
        keys = [
            (
                str(row["operating_point_id"]),
                str(row["mechanism"]),
                str(row["target_product_id"]),
                str(row["supplier_id"]),
            )
            for row in group_records
        ]
        _decorate_rank_group(
            group_records,
            [supplier_bootstrap[key]["fixed"] for key in keys],
            [supplier_bootstrap[key]["causal"] for key in keys],
        )
        for row in group_records:
            _preserve_product_ranking(row)
            row["fixed360_effect_mean_pp"] = row[f"{PRIMARY_METRIC}_mean"]
            row["bootstrap_ci95_low"] = row[f"{PRIMARY_METRIC}_ci95_low"]
            row["bootstrap_ci95_high"] = row[f"{PRIMARY_METRIC}_ci95_high"]
            row["positive_mean_effect"] = (
                row[f"{PRIMARY_METRIC}_mean"] > NUMERIC_TOLERANCE
            )
            row["priority_group"] = row["priority_status"]
    supplier_stats = pd.DataFrame(records).sort_values(
        [
            "operating_point_id",
            "mechanism",
            "target_product_id",
            "position",
            "supplier_id",
        ]
    )
    return supplier_stats.reset_index(drop=True), supplier_bootstrap


def build_global_lane_priority(
    lane_stats: pd.DataFrame,
    lane_bootstrap: Mapping[tuple[str, str, str, str], Mapping[str, np.ndarray]],
) -> pd.DataFrame:
    """Rank every physical lane together while retaining its product stratum."""

    records = [row.to_dict() for _, row in lane_stats.iterrows()]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(
            (str(record["operating_point_id"]), str(record["mechanism"])), []
        ).append(record)
    for group_records in grouped.values():
        group_records.sort(key=lambda row: str(row["lane_id"]))
        keys = [
            (
                str(row["operating_point_id"]),
                str(row["mechanism"]),
                str(row["target_product_id"]),
                str(row["lane_id"]),
            )
            for row in group_records
        ]
        _decorate_rank_group(
            group_records,
            [lane_bootstrap[key]["fixed"] for key in keys],
            [lane_bootstrap[key]["causal"] for key in keys],
        )
        for row in group_records:
            row["ranking_scope"] = "all_target_products"
            row["ranking_within_target_product"] = False
            row["fixed360_effect_mean_pp"] = row[f"{PRIMARY_METRIC}_mean"]
            row["bootstrap_ci95_low"] = row[f"{PRIMARY_METRIC}_ci95_low"]
            row["bootstrap_ci95_high"] = row[f"{PRIMARY_METRIC}_ci95_high"]
            row["positive_mean_effect"] = (
                row[f"{PRIMARY_METRIC}_mean"] > NUMERIC_TOLERANCE
            )
            row["priority_group"] = row["priority_status"]
    return (
        pd.DataFrame(records)
        .sort_values(["operating_point_id", "mechanism", "position", "lane_id"])
        .reset_index(drop=True)
    )


def build_global_supplier_statistics(
    product_supplier_stats: pd.DataFrame,
    product_supplier_bootstrap: Mapping[
        tuple[str, str, str, str], Mapping[str, np.ndarray]
    ],
) -> tuple[pd.DataFrame, dict[tuple[str, str, str], dict[str, np.ndarray]]]:
    """Represent each supplier by its most exposed tested lane across products."""

    records: list[dict[str, Any]] = []
    global_bootstrap: dict[tuple[str, str, str], dict[str, np.ndarray]] = {}
    for key, group in product_supplier_stats.groupby(
        ["operating_point_id", "mechanism", "supplier_id"], sort=True
    ):
        ordered = group.sort_values(
            [f"{PRIMARY_METRIC}_mean", "target_product_id", "exposed_lane_id"],
            ascending=[False, True, True],
        )
        selected = ordered.iloc[0].to_dict()
        causal_selected = group.sort_values(
            ["causal_ranking_score_pp", "target_product_id", "causal_exposed_lane_id"],
            ascending=[False, True, True],
        ).iloc[0]
        backlog_selected = group.sort_values(
            ["supplementary_backlog_effect_mean", "target_product_id"],
            ascending=[False, True],
        ).iloc[0]
        bootstrap_keys = [
            (key[0], key[1], str(row["target_product_id"]), key[2])
            for _, row in group.iterrows()
        ]
        selected["ranking_scope"] = "all_target_products"
        selected["ranking_within_target_product"] = False
        selected["supplier_aggregation_method"] = (
            "maximum_tested_lane_across_target_products_fixed360_primary_effect"
        )
        selected["tested_target_products"] = "|".join(
            sorted(str(value) for value in group["target_product_id"].unique())
        )
        all_lane_ids = sorted(
            {
                lane_id
                for value in group["tested_lane_ids"]
                for lane_id in str(value).split("|")
                if lane_id
            }
        )
        selected["tested_lane_count"] = len(all_lane_ids)
        selected["tested_lane_ids"] = "|".join(all_lane_ids)
        selected["causal_ranking_score_pp"] = float(
            causal_selected["causal_ranking_score_pp"]
        )
        selected["causal_exposed_lane_id"] = str(
            causal_selected["causal_exposed_lane_id"]
        )
        for field in (
            "supplementary_backlog_lane_id",
            "supplementary_backlog_target_product_id",
            "supplementary_backlog_effect_mean",
            "supplementary_backlog_effect_ci95_low",
            "supplementary_backlog_effect_ci95_high",
            "supplementary_backlog_positive_effect_count",
        ):
            selected[field] = backlog_selected[field]
        records.append(selected)
        global_bootstrap[key] = {
            "fixed": np.max(
                np.column_stack(
                    [
                        product_supplier_bootstrap[item]["fixed"]
                        for item in bootstrap_keys
                    ]
                ),
                axis=1,
            ),
            "causal": np.max(
                np.column_stack(
                    [
                        product_supplier_bootstrap[item]["causal"]
                        for item in bootstrap_keys
                    ]
                ),
                axis=1,
            ),
        }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(
            (str(record["operating_point_id"]), str(record["mechanism"])), []
        ).append(record)
    for group_records in grouped.values():
        group_records.sort(key=lambda row: str(row["supplier_id"]))
        keys = [
            (
                str(row["operating_point_id"]),
                str(row["mechanism"]),
                str(row["supplier_id"]),
            )
            for row in group_records
        ]
        _decorate_rank_group(
            group_records,
            [global_bootstrap[key]["fixed"] for key in keys],
            [global_bootstrap[key]["causal"] for key in keys],
        )
        for row in group_records:
            row["fixed360_effect_mean_pp"] = row[f"{PRIMARY_METRIC}_mean"]
            row["bootstrap_ci95_low"] = row[f"{PRIMARY_METRIC}_ci95_low"]
            row["bootstrap_ci95_high"] = row[f"{PRIMARY_METRIC}_ci95_high"]
            row["positive_mean_effect"] = (
                row[f"{PRIMARY_METRIC}_mean"] > NUMERIC_TOLERANCE
            )
            row["priority_group"] = row["priority_status"]
            within_status = str(row.get("within_target_product_priority_status") or "")
            global_priority = row["priority_status"] in {
                "robust_priority",
                "dossier_to_investigate",
            }
            within_priority = within_status in {
                "robust_priority",
                "dossier_to_investigate",
            }
            row["priority_confirmed_global_and_within_target_product"] = bool(
                global_priority and within_priority
            )
            if global_priority and not within_priority:
                row["priority_status"] = (
                    "global_only_not_confirmed_within_target_product"
                )
                row["priority_group"] = row["priority_status"]
    return (
        pd.DataFrame(records)
        .sort_values(["operating_point_id", "mechanism", "position", "supplier_id"])
        .reset_index(drop=True),
        global_bootstrap,
    )


def _paired_difference_summary(values: np.ndarray) -> dict[str, Any]:
    indices = _bootstrap_indices(len(values))
    means = np.mean(values[indices], axis=1)
    return {
        "mean": float(np.mean(values)),
        "ci95_low": _linear_quantile(means, 0.025),
        "ci95_high": _linear_quantile(means, 0.975),
    }


def build_priority_stability(
    supplier_stats: pd.DataFrame, lane_stats: pd.DataFrame, paired: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    supplier_records: list[dict[str, Any]] = []
    lane_records: list[dict[str, Any]] = []
    for level, stats, identity_field, destination in (
        ("supplier", supplier_stats, "supplier_id", supplier_records),
        ("lane", lane_stats, "lane_id", lane_records),
    ):
        group_fields = ["mechanism", "target_product_id", identity_field]
        for key, state_stats in stats.groupby(group_fields, sort=True):
            states = {
                str(row["operating_point_id"]): row for _, row in state_stats.iterrows()
            }
            if set(states) != set(OPERATING_POINTS):
                raise CampaignValidationError(
                    f"Missing state in {level} stability cell: {key}"
                )
            if level == "supplier":
                candidate_lanes = lane_stats[
                    (lane_stats["mechanism"] == key[0])
                    & (lane_stats["target_product_id"] == key[1])
                    & (lane_stats["supplier_id"] == key[2])
                ]
                lane_scores = candidate_lanes.groupby("lane_id")[
                    f"{PRIMARY_METRIC}_mean"
                ].mean()
                comparison_lane = str(
                    sorted(
                        lane_scores.index, key=lambda lane: (-lane_scores[lane], lane)
                    )[0]
                )
                supplier_id = str(key[2])
            else:
                comparison_lane = str(key[2])
                supplier_id = str(state_stats.iloc[0]["supplier_id"])
            source = paired[
                (paired["mechanism"] == key[0])
                & (paired["target_product_id"] == key[1])
                & (paired["lane_id"] == comparison_lane)
            ]
            effect = source.pivot(
                index="seed", columns="operating_point_id", values=PRIMARY_METRIC
            )
            comparable = source.pivot(
                index="seed",
                columns="operating_point_id",
                values="seed_cross_state_exposure_comparable",
            )
            comparable_mask = comparable.reindex(columns=OPERATING_POINTS).all(axis=1)
            comparable_seeds = comparable_mask[comparable_mask].index
            declared_valid = bool(source["state_comparison_valid"].all())
            comparison_valid = (
                declared_valid and len(comparable_seeds) >= MIN_COMPARABLE_SEEDS
            )
            differences: dict[str, Any] = {}
            if comparison_valid:
                comparable_effect = effect.loc[comparable_seeds, list(OPERATING_POINTS)]
                for state in ("op_93", "op_80"):
                    summary = _paired_difference_summary(
                        (
                            comparable_effect[state] - comparable_effect["op_100"]
                        ).to_numpy(dtype=float)
                    )
                    for suffix, value in summary.items():
                        differences[f"fixed360_{state}_minus_op_100_pp_{suffix}"] = (
                            value
                        )
            else:
                for state in ("op_93", "op_80"):
                    for suffix in ("mean", "ci95_low", "ci95_high"):
                        differences[f"fixed360_{state}_minus_op_100_pp_{suffix}"] = (
                            math.nan
                        )
            statuses = {
                state: str(states[state]["priority_status"])
                for state in OPERATING_POINTS
            }
            priority_flags = {
                state: statuses[state]
                in {"robust_priority", "dossier_to_investigate"}
                for state in OPERATING_POINTS
            }
            robust_flags = {
                state: statuses[state] == "robust_priority"
                for state in OPERATING_POINTS
            }
            if not comparison_valid:
                stability_status = "insufficient_comparable_exposure"
            elif all(robust_flags.values()):
                stability_status = "robust_priority_all_states"
            elif all(priority_flags.values()):
                stability_status = "priority_all_states"
            elif any(priority_flags.values()):
                stability_status = "state_specific_priority"
            elif any(
                states[state]["model_effect_detected"] for state in OPERATING_POINTS
            ):
                stability_status = "detected_lower_priority"
            else:
                stability_status = "no_detected_effect"
            low = differences.get("fixed360_op_80_minus_op_100_pp_ci95_low", math.nan)
            high = differences.get("fixed360_op_80_minus_op_100_pp_ci95_high", math.nan)
            if not comparison_valid:
                interpretation = "comparaison inter-états non conclue : exposition comparable insuffisante"
            elif low > 0:
                interpretation = "effet simulé plus fort dans l'état fortement dégradé"
            elif high < 0:
                interpretation = (
                    "effet simulé plus faible dans l'état fortement dégradé"
                )
            else:
                interpretation = (
                    "variation entre états non séparée de la dispersion simulée"
                )
            record: dict[str, Any] = {
                "analysis_level": level,
                "mechanism": key[0],
                "target_product_id": key[1],
                "supplier_id": supplier_id,
                "comparison_lane_id": comparison_lane,
                "comparison_lane_label_fr": "même voie testée pour comparer les trois états",
                "comparable_seed_count": len(comparable_seeds),
                "required_comparable_seed_count": MIN_COMPARABLE_SEEDS,
                "state_comparison_valid": comparison_valid,
                "insufficient_comparable_exposure": not comparison_valid,
                "priority_status": stability_status,
                "priority_state_count": sum(priority_flags.values()),
                "robust_priority_state_count": sum(robust_flags.values()),
                "priority_in_all_three_states": all(priority_flags.values()),
                "robust_priority_in_all_three_states": all(robust_flags.values()),
                "state_sensitivity_interpretation_fr": interpretation,
                "horizon_dependent": any(
                    bool(states[state]["horizon_dependent"])
                    for state in OPERATING_POINTS
                ),
                **differences,
            }
            if level == "supplier":
                record["same_exposed_lane_across_states"] = (
                    len(
                        {
                            str(states[state]["exposed_lane_id"])
                            for state in OPERATING_POINTS
                        }
                    )
                    == 1
                )
            else:
                record["lane_id"] = comparison_lane
            for state in OPERATING_POINTS:
                record[f"priority_status_{state}"] = statuses[state]
                record[f"in_top3_{state}"] = priority_flags[state]
                record[f"rank_min_{state}"] = int(states[state]["rank_min"])
                record[f"rank_max_{state}"] = int(states[state]["rank_max"])
                record[f"fixed360_effect_mean_pp_{state}"] = float(
                    states[state][f"{PRIMARY_METRIC}_mean"]
                )
            destination.append(record)
    return pd.DataFrame(supplier_records), pd.DataFrame(lane_records)


def build_global_supplier_stability(
    supplier_stats: pd.DataFrame, lane_stats: pd.DataFrame, paired: pd.DataFrame
) -> pd.DataFrame:
    """Assess whether one supplier priority persists across all three states.

    Numeric state interactions always use one fixed physical lane and only the
    seeds whose exposure is comparable across the three states.  Global ranks
    remain a complementary view; the selected product is always disclosed.
    """

    records: list[dict[str, Any]] = []
    for key, state_stats in supplier_stats.groupby(
        ["mechanism", "supplier_id"], sort=True
    ):
        states = {
            str(row["operating_point_id"]): row for _, row in state_stats.iterrows()
        }
        if set(states) != set(OPERATING_POINTS):
            raise CampaignValidationError(
                f"Missing state in global supplier stability: {key}"
            )
        candidates = lane_stats[
            (lane_stats["mechanism"] == key[0]) & (lane_stats["supplier_id"] == key[1])
        ]
        scores = candidates.groupby("lane_id")[f"{PRIMARY_METRIC}_mean"].mean()
        comparison_lane = str(
            sorted(scores.index, key=lambda lane: (-scores[lane], lane))[0]
        )
        source = paired[
            (paired["mechanism"] == key[0])
            & (paired["supplier_id"] == key[1])
            & (paired["lane_id"] == comparison_lane)
        ]
        target_products = set(source["target_product_id"])
        if len(target_products) != 1:
            raise CampaignValidationError(
                "One physical lane must feed one target product"
            )
        effect = source.pivot(
            index="seed", columns="operating_point_id", values=PRIMARY_METRIC
        )
        comparable = source.pivot(
            index="seed",
            columns="operating_point_id",
            values="seed_cross_state_exposure_comparable",
        )
        comparable_mask = comparable.reindex(columns=OPERATING_POINTS).all(axis=1)
        comparable_seeds = comparable_mask[comparable_mask].index
        comparison_valid = (
            bool(source["state_comparison_valid"].all())
            and len(comparable_seeds) >= MIN_COMPARABLE_SEEDS
        )
        differences: dict[str, Any] = {}
        if comparison_valid:
            comparable_effect = effect.loc[comparable_seeds, list(OPERATING_POINTS)]
            for state in ("op_93", "op_80"):
                summary = _paired_difference_summary(
                    (comparable_effect[state] - comparable_effect["op_100"]).to_numpy(
                        dtype=float
                    )
                )
                for suffix, value in summary.items():
                    differences[f"fixed360_{state}_minus_op_100_pp_{suffix}"] = value
        else:
            for state in ("op_93", "op_80"):
                for suffix in ("mean", "ci95_low", "ci95_high"):
                    differences[f"fixed360_{state}_minus_op_100_pp_{suffix}"] = math.nan
        statuses = {
            state: str(states[state]["priority_status"]) for state in OPERATING_POINTS
        }
        priority = {
            state: statuses[state]
            in {"robust_priority", "dossier_to_investigate"}
            for state in OPERATING_POINTS
        }
        robust = {
            state: statuses[state] == "robust_priority" for state in OPERATING_POINTS
        }
        if not comparison_valid:
            status = "insufficient_comparable_exposure"
        elif all(robust.values()):
            status = "robust_priority_all_states"
        elif all(priority.values()):
            status = "priority_all_states"
        elif any(priority.values()):
            status = "state_specific_priority"
        elif any(states[state]["model_effect_detected"] for state in OPERATING_POINTS):
            status = "detected_lower_priority"
        else:
            status = "no_detected_effect"
        low = differences.get("fixed360_op_80_minus_op_100_pp_ci95_low", math.nan)
        high = differences.get("fixed360_op_80_minus_op_100_pp_ci95_high", math.nan)
        if not comparison_valid:
            interpretation = "comparaison inter-états non conclue : exposition comparable insuffisante"
        elif low > 0:
            interpretation = "effet simulé plus fort dans l'état fortement dégradé"
        elif high < 0:
            interpretation = "effet simulé plus faible dans l'état fortement dégradé"
        else:
            interpretation = (
                "variation entre états non séparée de la dispersion simulée"
            )
        record: dict[str, Any] = {
            "ranking_scope": "all_target_products",
            "mechanism": key[0],
            "supplier_id": key[1],
            "target_product_id_for_comparison_lane": next(iter(target_products)),
            "comparison_lane_id": comparison_lane,
            "comparison_lane_label_fr": "même voie testée pour comparer les trois états",
            "comparable_seed_count": len(comparable_seeds),
            "required_comparable_seed_count": MIN_COMPARABLE_SEEDS,
            "state_comparison_valid": comparison_valid,
            "insufficient_comparable_exposure": not comparison_valid,
            "priority_status": status,
            "priority_state_count": sum(priority.values()),
            "robust_priority_state_count": sum(robust.values()),
            "priority_in_all_three_states": all(priority.values()),
            "robust_priority_in_all_three_states": all(robust.values()),
            "same_exposed_lane_across_states": len(
                {str(states[state]["exposed_lane_id"]) for state in OPERATING_POINTS}
            )
            == 1,
            "same_target_product_for_exposed_lane_across_states": len(
                {str(states[state]["target_product_id"]) for state in OPERATING_POINTS}
            )
            == 1,
            "state_sensitivity_interpretation_fr": interpretation,
            "horizon_dependent": any(
                bool(states[state]["horizon_dependent"]) for state in OPERATING_POINTS
            ),
            **differences,
        }
        for state in OPERATING_POINTS:
            record[f"priority_status_{state}"] = statuses[state]
            record[f"in_top3_{state}"] = priority[state]
            record[f"rank_min_{state}"] = int(states[state]["rank_min"])
            record[f"rank_max_{state}"] = int(states[state]["rank_max"])
            record[f"fixed360_effect_mean_pp_{state}"] = float(
                states[state][f"{PRIMARY_METRIC}_mean"]
            )
            record[f"target_product_id_{state}"] = str(
                states[state]["target_product_id"]
            )
        records.append(record)
    return (
        pd.DataFrame(records)
        .sort_values(["mechanism", "supplier_id"])
        .reset_index(drop=True)
    )


def _lot_replay_priority_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    status_order = {"robust_priority": 0, "dossier_to_investigate": 1}
    state_order = {"op_80": 0, "op_93": 1, "op_100": 2}
    return (
        status_order.get(str(row.get("priority_status") or ""), 9),
        -float(row.get("bootstrap_unambiguous_top3_probability") or 0.0),
        -float(row.get("bootstrap_top3_inclusion_probability") or 0.0),
        int(row.get("position") or 10**9),
        -float(row.get("fixed360_effect_mean_pp") or 0.0),
        state_order.get(str(row.get("operating_point_id") or ""), 9),
        str(row.get("supplier_id") or ""),
        str(row.get("lane_id") or ""),
    )


def _select_lot_replay_priorities(priority_lanes: pd.DataFrame) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in priority_lanes.to_dict(orient="records")
        if str(row.get("priority_status") or "")
        in {"robust_priority", "dossier_to_investigate"}
    ]
    eligible.sort(key=_lot_replay_priority_key)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(row: Mapping[str, Any]) -> None:
        key = (
            str(row["operating_point_id"]),
            str(row["mechanism"]),
            str(row["lane_id"]),
        )
        if key not in seen and len(selected) < 3:
            selected.append(dict(row))
            seen.add(key)

    # Preserve the scientific separation of causes: when a cause has an
    # eligible signal it receives one dossier before any third dossier is added.
    for mechanism in MECHANISMS:
        candidate = next(
            (row for row in eligible if row.get("mechanism") == mechanism), None
        )
        if candidate is not None:
            add(candidate)
    for row in eligible:
        add(row)
    return selected


def build_lot_replay_selection(
    *,
    campaign_root: Path,
    context: SignedCampaignContext,
    paired: pd.DataFrame,
    priority_lanes: pd.DataFrame,
) -> dict[str, Any]:
    """Select at most three auditable campaign cells for later lot-ledger replay."""

    root = campaign_root.resolve()
    priorities = _select_lot_replay_priorities(priority_lanes)
    selected_dossiers: list[dict[str, Any]] = []
    for index, priority in enumerate(priorities, 1):
        point_id = str(priority["operating_point_id"])
        mechanism = str(priority["mechanism"])
        lane_id = str(priority["lane_id"])
        cell = paired.loc[
            (paired["operating_point_id"] == point_id)
            & (paired["mechanism"] == mechanism)
            & (paired["lane_id"] == lane_id)
            & paired["incident_physically_exercised"]
        ].copy()
        if cell.empty:
            raise CampaignValidationError(
                "A selected V4 lot-replay dossier has no physically exercised seed"
            )
        median_effect = float(np.median(cell[PRIMARY_METRIC].to_numpy(dtype=float)))
        cell["_median_distance"] = (
            cell[PRIMARY_METRIC].astype(float) - median_effect
        ).abs()
        representative = cell.sort_values(
            ["_median_distance", "seed"], ascending=[True, True]
        ).iloc[0]
        seed = int(representative["seed"])
        shard_id = str(representative["shard_id"])
        incident_case_key = str(representative["case_key"])
        baseline_case_key = f"{point_id}__baseline__seed_{seed}"
        incident_path = (
            root / "shards" / shard_id / "case_evidence" / f"{incident_case_key}.json"
        )
        baseline_path = (
            root / "shards" / shard_id / "case_evidence" / f"{baseline_case_key}.json"
        )
        incident_evidence = _validate_case_evidence_file(
            incident_path,
            manifest=context.manifest,
            expected={
                "case_key": incident_case_key,
                "case_signature": str(representative["case_signature"]),
                "operating_point_id": point_id,
                "seed": seed,
                "stage": "incident",
                "shard_id": shard_id,
            },
        )
        baseline_evidence = _validate_case_evidence_file(
            baseline_path,
            manifest=context.manifest,
            expected={
                "case_key": baseline_case_key,
                "case_signature": str(representative["baseline_case_signature"]),
                "operating_point_id": point_id,
                "seed": seed,
                "stage": "baseline",
                "shard_id": shard_id,
            },
        )
        lane = incident_evidence.get("lane")
        mechanism_evidence = incident_evidence.get("mechanism")
        incident_proof = incident_evidence.get("incident_proof")
        risk_sha = str(incident_evidence.get("risk_csv_sha256") or "")
        risk_path = (
            root / "shards" / shard_id / "inputs" / "risk_events" / f"{incident_case_key}.csv"
        )
        identity = context.lane_identity[lane_id]
        required_days = int(representative["required_simulation_days"])
        if (
            not isinstance(lane, Mapping)
            or tuple(
                str(lane.get(field) or "")
                for field in (
                    "supplier_id",
                    "item_id",
                    "dst_node_id",
                    "edge_id",
                    "target_product_id",
                )
            )
            != identity
            or lane.get("lane_id") != lane_id
            or not isinstance(mechanism_evidence, Mapping)
            or mechanism_evidence.get("key") != mechanism
            or not isinstance(incident_proof, Mapping)
            or incident_proof.get("incident_physically_exercised") is not True
            or incident_evidence.get("baseline_case_signature")
            != baseline_evidence.get("case_signature")
            or incident_evidence.get("simulation_days") != required_days
            or not _is_sha256(risk_sha)
            or not risk_path.is_file()
            or _sha256(risk_path) != risk_sha
        ):
            raise CampaignValidationError(
                "A selected V4 lot-replay dossier fails its signed physical proof"
            )
        warmup_sha = str(representative["warmup_core_state_sha256"])
        if (
            not _is_sha256(warmup_sha)
            or warmup_sha
            != str((incident_evidence.get("metrics") or {}).get("warmup_core_state_sha256") or "")
            or warmup_sha
            != str((baseline_evidence.get("metrics") or {}).get("warmup_core_state_sha256") or "")
        ):
            raise CampaignValidationError(
                "A selected V4 lot-replay dossier lost its paired warmup proof"
            )
        dossier_identity = {
            "operating_point_id": point_id,
            "mechanism": mechanism,
            "lane_id": lane_id,
        }
        selected_dossiers.append(
            {
                "dossier_id": f"dossier_{index:02d}_{_stable_sha256(dossier_identity)[:12]}",
                **dossier_identity,
                "supplier_id": str(priority["supplier_id"]),
                "item_id": str(priority["item_id"]),
                "dst_node_id": str(priority["dst_node_id"]),
                "edge_id": str(priority["edge_id"]),
                "target_product_id": str(priority["target_product_id"]),
                "priority_status": str(priority["priority_status"]),
                "position": int(priority["position"]),
                "representative_seed": seed,
                "representative_metric": PRIMARY_METRIC,
                "representative_effect_pp": float(representative[PRIMARY_METRIC]),
                "cell_median_effect_pp": median_effect,
                "valid_exercised_seed_count": int(len(cell)),
                "incident_case_key": incident_case_key,
                "incident_case_signature": str(representative["case_signature"]),
                "baseline_case_key": baseline_case_key,
                "baseline_case_signature": str(
                    representative["baseline_case_signature"]
                ),
                "required_simulation_days": required_days,
                "warmup_core_state_sha256": warmup_sha,
                "risk_csv_path": risk_path.relative_to(root).as_posix(),
                "risk_csv_sha256": risk_sha,
                "incident_evidence_path": incident_path.relative_to(root).as_posix(),
                "incident_evidence_sha256": _sha256(incident_path),
                "baseline_evidence_path": baseline_path.relative_to(root).as_posix(),
                "baseline_evidence_sha256": _sha256(baseline_path),
            }
        )
    available_by_cause = {
        mechanism: bool(
            (
                priority_lanes["mechanism"].eq(mechanism)
                & priority_lanes["priority_status"].isin(
                    {"robust_priority", "dossier_to_investigate"}
                )
            ).any()
        )
        for mechanism in MECHANISMS
    }
    unsigned: dict[str, Any] = {
        "schema_version": (
            "etudecas.supplier_operating_point_full_campaign.v4."
            "lot_replay_selection.v1"
        ),
        "status": "complete_selected",
        "campaign_signature": context.manifest["campaign_signature"],
        "engine_sha256": context.manifest["engine_sha256"],
        "generated_at_utc": _utc_now(),
        "selection_contract": {
            "source": "validated_priority_lanes_by_cause_state",
            "eligible_priority_statuses": [
                "robust_priority",
                "dossier_to_investigate",
            ],
            "supplementary_backlog_signal_eligible": False,
            "supplementary_backlog_signal_role": (
                "separate_operational_warning_not_service_rank_and_not_lot_replay"
            ),
            "maximum_dossiers": 3,
            "forced_top3": False,
            "one_dossier_per_cause_if_available": True,
            "eligible_signal_available_by_cause": available_by_cause,
            "mechanisms_kept_separate": True,
            "priority_order": (
                "robust status, bootstrap rank certainty, descriptive position, "
                "effect, degraded-state order, deterministic identity"
            ),
            "representative_seed": (
                "valid physically-exercised seed nearest the cell median paired "
                "fixed-360 service loss; smallest seed breaks ties"
            ),
            "evidence_paths_relative_to_campaign_root": True,
            "risk_paths_relative_to_campaign_root": True,
            "replay_executes_simulation": False,
            "quality_included": False,
            "state_dependent_supplier_risks_enabled": False,
        },
        "selected_dossiers": selected_dossiers,
    }
    return {**unsigned, "selection_signature": _stable_sha256(unsigned)}


def _business_limits(disruption_window_days: int) -> list[dict[str, str]]:
    return [
        {
            "topic": "nature_des_resultats",
            "limit": (
                "SIMULÉ : stress-test d'impact conditionnel aux hypothèses du modèle. "
                "Sans historiques PO/ASN/OTIF, il ne mesure ni performance observée ni "
                "probabilité d'occurrence d'un incident fournisseur."
            ),
        },
        {
            "topic": "fenetre_fournisseur",
            "limit": (
                f"HYPOTHÈSE : chaque voie a sa fenêtre de {disruption_window_days} jours, "
                "choisie sur le seed de conception pour maximiser l'exposition commune, puis "
                "figée avant les 30 répétitions et commune aux trois états pour cette voie. "
                "C'est une fenêtre de forte exposition, pas un incident moyen ou aléatoire; "
                "des voies différentes peuvent viser des dates et saisons différentes."
            ),
        },
        {
            "topic": "signal_fournisseur",
            "limit": (
                "SIGNAL DE PRIORITÉ conditionnel à la fenêtre de forte exposition testée : "
                "le rang mêle structure réseau, dose physique et contexte calendaire. Un "
                "fournisseur est représenté par sa voie testée la plus exposée; ce n'est ni "
                "une criticité générale ni la preuve d'un problème récurrent. Une extension "
                "multi-fenêtres et multi-saisons est nécessaire pour généraliser."
            ),
        },
        {
            "topic": "incertitude",
            "limit": (
                "Les intervalles bootstrap décrivent la dispersion conditionnelle créée par "
                "les délais logistiques Erlang du modèle; ils ne constituent pas une fréquence "
                "d'incident industrielle."
            ),
        },
        {
            "topic": "comparaison_des_mecanismes",
            "limit": (
                "Le retard d'arrivée de 120 jours et la quantité normalement livrable divisée "
                "par deux (plan × fiabilité nominale × 0,5) sont deux stress distincts, sans "
                "gravité commune calibrée. Les résultats montrent impact total et fragilité "
                "par unité de dose physique; ils ne permettent pas de conclure qu'un mécanisme "
                "est plus probable ou plus grave."
            ),
        },
        {
            "topic": "comparaison_des_etats",
            "limit": (
                "Les trois états proviennent d'une seule famille de dégradation : ajout équilibré "
                "de délais fournisseurs planifiés par produit fini. Le seuil d'exposition ≤ 1,5 "
                "rend une comparaison admissible, mais les doses ne sont pas identiques. Capacité, "
                "demande, stocks ou fiabilité pourraient changer le classement."
            ),
        },
        {
            "topic": "dynamique_et_boucle_fermee",
            "limit": (
                "Stocks, transits, MRP, production et backlog évoluent dans le temps, mais la "
                "demande MRP dynamique explicite ne couvre que trois couples site-article. Les "
                "18 voies ne sont donc pas toutes pilotées en boucle fermée par la demande, et "
                "l'observation du contrôleur reste agrégée sans clé de voie."
            ),
        },
        {
            "topic": "couts",
            "limit": (
                "Les horizons étant adaptatifs, aucun écart de coût total sur l'horizon complet "
                "n'est calculé. Une trace quotidienne sur fenêtres appariées serait nécessaire."
            ),
        },
        {
            "topic": "lots",
            "limit": (
                "Cette campagne compacte classe les voies. Le rejeu ciblé décrit la propagation "
                "d'impact aval jusqu'à des destinataires agrégés C-XXXXX; il ne nomme ni client "
                "réel ni commande réelle et ne simule pas des incidents secondaires corrélés."
            ),
        },
        {
            "topic": "actions",
            "limit": (
                "Le stock ciblé J0 est un contrefactuel de stock déjà libre; acquisition, "
                "qualification, délai et coût ne sont pas modélisés. La réduction de délai agit "
                "en boucle ouverte sur de futurs départs voie/jour, pas sur un shipment_id en "
                "transit. priority_weight réalloue les achats entre voies actives d'un même "
                "site-article; il ne priorise ni OF ni commande client et exige un multisourcing "
                "déjà actif et qualifié."
            ),
        },
    ]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        converted = float(value)
        return converted if math.isfinite(converted) else None
    return value


def finalize_campaign(
    *,
    campaign_root: Path | None,
    manifest_path: Path | None,
    metrics_paths: Sequence[Path],
    output_dir: Path,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    if bootstrap_replicates != BOOTSTRAP_REPLICATES:
        raise CampaignValidationError(
            "Published finalization requires exactly 10,000 bootstrap repetitions"
        )
    evidence = discover_inputs(
        campaign_root=campaign_root,
        manifest_path=manifest_path,
        metrics_paths=metrics_paths,
    )
    manifest = _read_json(evidence.manifest_path)
    context = _validate_signed_context(evidence, manifest)
    if campaign_root is None:
        raise CampaignValidationError(
            "Strict V4 finalization requires --campaign-root to validate all signed case evidence"
        )
    signed_case_evidence = validate_metrics_against_signed_case_evidence(
        campaign_root=campaign_root,
        metrics_paths=evidence.metrics_paths,
        manifest=manifest,
    )
    raw = _read_metrics(evidence.metrics_paths)
    paired, validation = validate_and_pair(raw, context)
    validation["signed_case_evidence"] = signed_case_evidence
    smoke_validation = validate_v4_smoke(
        campaign_root,
        context=context,
        campaign_case_signatures=set(raw["case_signature"]),
    )
    validation["mandatory_non_reusable_smoke"] = smoke_validation
    shard_progress = validate_shard_progress(
        campaign_root,
        campaign_signature=str(validation["campaign_signature"]),
        expected_shard_ids=context.shard_ids,
    )
    lane_stats, lane_bootstrap = build_lane_statistics(
        paired, bootstrap_replicates=bootstrap_replicates
    )
    product_supplier_stats, product_supplier_bootstrap = build_supplier_statistics(
        lane_stats, lane_bootstrap
    )
    global_lane_priority = build_global_lane_priority(lane_stats, lane_bootstrap)
    supplier_stats, _supplier_bootstrap = build_global_supplier_statistics(
        product_supplier_stats, product_supplier_bootstrap
    )
    product_supplier_stability, lane_sensitivity = build_priority_stability(
        product_supplier_stats, lane_stats, paired
    )
    supplier_stability = build_global_supplier_stability(
        supplier_stats, lane_stats, paired
    )
    if len(lane_stats) != len(OPERATING_POINTS) * len(MECHANISMS) * EXPECTED_LANE_COUNT:
        raise CampaignValidationError("Unexpected lane-statistics matrix size")
    priority_suppliers = supplier_stats.copy()
    priority_lanes = global_lane_priority.copy()
    lot_replay_selection = build_lot_replay_selection(
        campaign_root=campaign_root,
        context=context,
        paired=paired,
        priority_lanes=priority_lanes,
    )
    achieved_rows = [
        {
            "operating_point_id": point,
            "target_service_pct": context.achieved_services[point]["target"],
            "achieved_global_service_pct": context.achieved_services[point]["global"],
            "achieved_service_268091_pct": context.achieved_services[point]["268091"],
            "achieved_service_268967_pct": context.achieved_services[point]["268967"],
            "global_service_bootstrap_ci95_low_pct": context.achieved_services[point][
                "ci95_low"
            ],
            "global_service_bootstrap_ci95_high_pct": context.achieved_services[point][
                "ci95_high"
            ],
            "degradation_family": context.operating_point_provenance[
                "operating_point_inputs"
            ][point]["degradation_family"],
            "degradation_unit": context.operating_point_provenance[
                "operating_point_inputs"
            ][point]["degradation_unit"],
            "offset_days_268091": context.operating_point_provenance[
                "operating_point_inputs"
            ][point]["offset_days_268091"],
            "offset_days_268967": context.operating_point_provenance[
                "operating_point_inputs"
            ][point]["offset_days_268967"],
            "campaign_seed_count": EXPECTED_REPETITION_COUNT,
        }
        for point in OPERATING_POINTS
    ]
    achieved = pd.DataFrame(achieved_rows)

    destination = output_dir.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise CampaignValidationError(
            f"Refusing to overwrite non-empty output directory: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Build the complete package beside its destination.  Only the final
    # directory promotion makes it visible, so an interrupted finalizer cannot
    # leave a plausible-but-partial official result directory.
    output = destination.with_name(
        f".{destination.name}.building-{uuid.uuid4().hex}"
    )
    output.mkdir(parents=True, exist_ok=True)
    outputs = {
        "lane_statistics.csv": lane_stats,
        "supplier_statistics.csv": supplier_stats,
        "supplier_statistics_by_target_product.csv": product_supplier_stats,
        "priority_lanes_by_cause_state.csv": priority_lanes,
        "priority_suppliers_by_cause_state.csv": priority_suppliers,
        "priority_lanes_by_cause_state_and_product.csv": lane_stats,
        "priority_suppliers_by_cause_state_and_product.csv": product_supplier_stats,
        "supplier_priority_stability_by_cause.csv": supplier_stability,
        "supplier_priority_stability_by_cause_and_product.csv": product_supplier_stability,
        "lane_state_sensitivity_by_cause.csv": lane_sensitivity,
        "operating_point_achieved_services.csv": achieved,
    }
    for name, result_frame in outputs.items():
        result_frame.to_csv(output / name, index=False, encoding="utf-8-sig")
    _write_json(output / "lot_replay_plan.json", lot_replay_selection)
    _write_json(output / "cross_state_target_registry.json", context.registry)
    _write_json(output / "state_validation_binding.json", context.preflight)
    limits = _business_limits(context.disruption_window_days)
    _write_json(output / "business_limits.json", limits)
    selected = priority_suppliers[
        priority_suppliers["priority_status"].isin(
            {"robust_priority", "dossier_to_investigate"}
        )
    ]
    supplementary_backlog = priority_suppliers[
        priority_suppliers["priority_status"].eq("supplementary_backlog_signal")
    ]
    summary = {
        "schema_version": f"{SCHEMA_VERSION}.summary.v1",
        "status": "complete_validated",
        "evidence_class": "conditional_reproducible_simulation_hypothesis",
        "supplier_disruption_window_days": context.disruption_window_days,
        "operating_states": achieved_rows,
        "priority_signal_count": len(selected),
        "supplementary_backlog_signal_count": len(supplementary_backlog),
        "supplementary_backlog_replay_launched": False,
        "lot_replay_dossier_count": len(
            lot_replay_selection["selected_dossiers"]
        ),
        "lot_replay_plan": "lot_replay_plan.json",
        "priority_signals": selected[
            [
                "operating_point_id",
                "mechanism",
                "target_product_id",
                "supplier_id",
                "exposed_lane_id",
                "priority_status",
                "fixed360_effect_mean_pp",
                "bootstrap_ci95_low",
                "bootstrap_ci95_high",
                "bootstrap_unambiguous_top3_probability",
                "horizon_dependent",
            ]
        ].to_dict(orient="records"),
    }
    _write_json(output / "campaign_summary.json", _json_safe(summary))
    result_manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_validated",
        "generated_at_utc": _utc_now(),
        **validation,
        "shard_progress": shard_progress,
        "expected_contract": {
            "operating_point_count": len(OPERATING_POINTS),
            "operating_point_degradation_family": (
                "balanced_product_supplier_planned_lead"
            ),
            "operating_point_degradation_scope": (
                "planned_supplier_lead_offsets_by_finished_product_feed"
            ),
            "lane_count": EXPECTED_LANE_COUNT,
            "mechanisms": list(MECHANISMS),
            "paired_repetition_count": EXPECTED_REPETITION_COUNT,
            "repetition_ids": list(EXPECTED_SEEDS),
            "baseline_row_count": EXPECTED_BASELINE_COUNT,
            "incident_row_count": EXPECTED_INCIDENT_COUNT,
            "supplier_disruption_window_days": context.disruption_window_days,
            "business_window_days": BUSINESS_WINDOW_DAYS,
            "adaptive_horizons": True,
            "lot_replay_dossier_maximum": 3,
            "lot_replay_forced_top3": False,
            "quality_branch_included": False,
            "availability_incident_included": False,
            "all_lots_traced_claimed": False,
        },
        "comparability_checks": {
            "complete_3x18x2x30_matrix": True,
            "same_repetitions_in_every_cell": True,
            "same_engine_sha256": True,
            "same_campaign_signature": True,
            "lane_identity_invariant": True,
            "baseline_pairing_complete": True,
            "paired_warmup_state_identical": True,
            "shipment_set_and_incident_trace_proven": True,
            "fixed_supplier_window_registry_signed": True,
            "v4_holdout_state_binding_signed_and_accepted": True,
            "v4_holdout_shipment_traces_reused_without_rerun": True,
            "operating_point_validation_engine_runs_in_campaign": 0,
            "operating_point_source_chain_revalidated": True,
            "business_360_and_causal_windows_fully_observed": True,
            "adaptive_horizons_validated": True,
            "whole_horizon_cost_deltas_excluded": True,
            "all_18_shard_progress_documents_complete": True,
            "all_3330_metrics_reconstructed_from_signed_case_evidence": (
                signed_case_evidence.get("status") == "complete_reconstructed"
                and signed_case_evidence.get("case_count") == EXPECTED_TOTAL_COUNT
            ),
            "quality_or_availability_incident_count": 0,
            "all_lots_traced": False,
            "targeted_priority_lot_and_cascade_replay_required": True,
            "mandatory_non_reusable_op93_smoke_validated": True,
        },
        "statistics": {
            "primary_ranking_metric": PRIMARY_METRIC,
            "primary_window": "fixed_360_day_business_envelope",
            "causal_window_role": "physical_explanation_and_horizon_sensitivity",
            "confidence_interval": "paired non-parametric bootstrap percentile interval",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_pairing": "one common paired-seed resample for every campaign cell",
            "effect_detection": "CI95 lower bound > 0 and at least 24 of 30 paired effects > 0",
            "exposure_normalization": "ratio of summed effects to summed effective dose",
            "demand_normalization": "absolute effects and ratio-of-sums demand-normalized effects",
            "supplier_aggregation": "maximum tested lane, labelled voie la plus exposée",
            "robust_priority": "P(bootstrap rank_max <= 3) >= 0.80 after effect detection",
            "dossier_to_investigate": (
                "P(bootstrap rank_min <= 3) >= 0.20 after effect detection; "
                "descriptive review signal, not a forced top-three label"
            ),
            "supplementary_backlog_signal": (
                "separate from the service rank; paired bootstrap backlog-per-demand "
                "CI95 lower bound > 0 and at least 24 of 30 positive paired effects; "
                "not eligible for this campaign lot replay"
            ),
            "forced_top3": False,
        },
        "evidence_class": "conditional_reproducible_simulation_hypothesis",
        "historical_incident_probability_estimated": False,
        "industrial_supplier_criticality_claimed": False,
        "business_limits": limits,
        "inputs": {
            "campaign_manifest": str(evidence.manifest_path),
            "campaign_manifest_sha256": evidence.manifest_sha256,
            "metrics_csv_sha256": dict(evidence.metrics_sha256),
            "operating_point_provenance": context.operating_point_provenance,
            "state_validation_binding": str(context.preflight_path),
            "state_validation_binding_sha256": _sha256(context.preflight_path),
            "target_registry": str(context.registry_path),
            "target_registry_sha256": _sha256(context.registry_path),
        },
        "outputs": {
            **{
                name: {
                    "row_count": int(len(result_frame)),
                    "sha256": _sha256(output / name),
                }
                for name, result_frame in outputs.items()
            },
            "lot_replay_plan.json": {
                "row_count": len(lot_replay_selection["selected_dossiers"]),
                "sha256": _sha256(output / "lot_replay_plan.json"),
                "selection_signature": lot_replay_selection[
                    "selection_signature"
                ],
            },
            "cross_state_target_registry.json": {
                "row_count": len(context.registry["targets"]),
                "sha256": _sha256(output / "cross_state_target_registry.json"),
                "registry_signature": context.registry["registry_signature"],
            },
            "state_validation_binding.json": {
                "row_count": len(context.preflight["states"]),
                "sha256": _sha256(output / "state_validation_binding.json"),
                "binding_signature": context.preflight["binding_signature"],
            },
            "business_limits.json": {
                "row_count": len(limits),
                "sha256": _sha256(output / "business_limits.json"),
            },
            "campaign_summary.json": {
                "row_count": len(summary["priority_signals"]),
                "sha256": _sha256(output / "campaign_summary.json"),
            },
        },
        "priority_signal_count": int(len(selected)),
        "lot_replay_plan": {
            "path": "lot_replay_plan.json",
            "row_count": len(lot_replay_selection["selected_dossiers"]),
            "sha256": _sha256(output / "lot_replay_plan.json"),
            "selection_signature": lot_replay_selection["selection_signature"],
        },
    }
    _write_json(output / "campaign_validation.json", _json_safe(result_manifest))
    try:
        if destination.exists():
            # The only destination accepted above is an empty directory.
            destination.rmdir()
        output.replace(destination)
    except OSError as exc:
        raise CampaignValidationError(
            f"Could not atomically publish finalized V4 package: {destination}"
        ) from exc
    return _json_safe(result_manifest)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path)
    parser.add_argument("--metrics-csv", action="append", default=[], type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = finalize_campaign(
            campaign_root=args.campaign_root,
            manifest_path=args.campaign_manifest,
            metrics_paths=args.metrics_csv,
            output_dir=args.output_dir,
        )
    except CampaignValidationError as exc:
        print(f"CAMPAIGN INVALID: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
