#!/usr/bin/env python3
"""Run the additive three-state supplier incident campaign, shard by shard.

The campaign compares the same 18 supplier lanes at three calibrated service
operating points.  For each lane, one 42-day calendar window is selected on the
independent design seed 340281, then frozen across all three states and the 30
campaign seeds.  Each paired repetition contains one baseline and two supplier
stress mechanisms applied to every dispatch actually decided in that window:

* ``transport_delay`` adds 120 transport days; and
* ``planned_delivery_shortfall`` multiplies planned delivery reliability by
  0.5 (a 50% receipt shortfall conditional on a dispatch).

No availability, capacity, stock, quality or endogenous state-risk event is
created here.  Replanning after the start of the stress may legitimately alter
shipment identifiers and quantities.  A fixed window with no positive flow in
a campaign seed remains a valid, non-exercised calendar case with zero effect.

The full design is 3 operating points x 18 lanes x 2 incidents x 30 seeds,
plus 3 x 30 paired baselines (3,330 reported rows), preceded by 93 auxiliary
J720 discovery runs.  Case horizons are adaptive.  The operating point remains
defined only on J0--J719, while incident effects use a fixed 360-day business
window and a fully observed causal window containing the latest actually
affected arrival plus the following 89 days (90 observed days inclusive).  It
is executed as 18
isolated shards: one operating point x one fixed block of five seeds.  Existing
scripts and historical outputs are never modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as campaign_core,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)

SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v2"
CASE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case.v2"
PROGRESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.progress.v1"
PREFLIGHT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.operating_point_preflight.v2"
PROBE_CHECKPOINT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.incident_probe_checkpoint.v1"
FAILED_ATTEMPT_DIAGNOSTIC_SCHEMA_VERSION = (
    f"{SCHEMA_VERSION}.failed_engine_attempt_diagnostic.v1"
)
HOLDOUT_ACCEPTED_STATUS = "holdout_validated_30_seed"
HOLDOUT_REJECTED_STATUS = "holdout_rejected_30_seed"
V1_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_calibration.v1.selected_operating_points"
)
V1_POINTS_PENDING_STATUS = "selected_on_five_seed_calibration_pending_holdout"
V2_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v2.selected_operating_points"
)
V2_POINTS_PENDING_STATUS = "selected_on_five_seed_refinement_pending_30_seed_holdout"
V3_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v3.selected_operating_points"
)
V3_POINTS_PENDING_STATUS = "selected_on_five_seed_refinement_v3_pending_30_seed_holdout"
V3_SELECTION_PASS_STATUS = "five_seed_loo_screen_v3_passed_pending_holdout"
V3_REFINEMENT_MODULE_SHA256 = (
    "707cbd79b8758b48a70665250d15e6af547fe0ad01b7bac44bad66ff14a9858e"
)
CALIBRATION_SEEDS = tuple(range(340282, 340287))
CONTRACT_REVISION = "fixed_42d_holdout_gated_adaptive_compact_probe_v5_2026_09_04"
PREFLIGHT_BOOTSTRAP_REPLICATES = 10_000
PREFLIGHT_BOOTSTRAP_SEED = 20260904

ARTIFACT_ROOT = protocol.ARTIFACT_PARENT
DEFAULT_LANE_REFERENCE = (
    ARTIFACT_ROOT
    / "supplier_network_risk_screen_20260902_v2"
    / "active_lane_reference.csv"
)
DEFAULT_ENGINE = (
    REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
)
DEFAULT_PROFILE = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)
DEFAULT_OUTPUT = ARTIFACT_ROOT / "supplier_operating_point_full_campaign_v2_20260904_v3"

OPERATING_POINT_IDS = ("op_100", "op_93", "op_80")
# 340282--340286 are reserved for multi-seed operating-point calibration.
# Campaign discovery and impact inference use a disjoint 30-seed holdout.
SEEDS = tuple(range(340287, 340317))
TARGET_DESIGN_SEED = 340281
SEED_BLOCK_SIZE = 5
SEED_BLOCKS = tuple(
    SEEDS[index : index + SEED_BLOCK_SIZE]
    for index in range(0, len(SEEDS), SEED_BLOCK_SIZE)
)
STATE_EVALUATION_DAYS = protocol.MEASURED_DAYS
DISCOVERY_DAYS = STATE_EVALUATION_DAYS
# Compatibility/default used by direct helper calls only.  Production cases
# use an adaptive, evidence-derived horizon (see ``_execute_baseline``).
SIMULATION_DAYS = 1080
MINIMUM_CASE_DAYS = STATE_EVALUATION_DAYS
DAYS = SIMULATION_DAYS
IMPACT_WINDOW_DAYS = 360
MIN_RECOVERY_OBSERVATION_DAYS = 90
MAX_WORKERS = 2
FAILED_ATTEMPT_INVENTORY_LIMIT = 64
FAILED_ATTEMPT_LOG_TAIL_BYTES = 16 * 1024
FAILED_ATTEMPT_DIAGNOSTICS_PER_CASE = 3
TARGET_PRODUCTS = protocol.PRODUCTS
PRODUCT_FACTORY = {"268091": "M-1810", "268967": "M-1430"}
TARGET_SELECTION_MAX_DELAY_DAYS = 120
TARGET_QUANTITY_TOLERANCE = 1e-6
INCIDENT_DISRUPTION_DAYS = 42
STATE_MATCH_MAX_QUANTITY_RATIO = 1.5
TARGET_REFERENCE_KIND = (
    "paired_simulated_baseline_shipment_not_observed_supplier_performance"
)


@dataclass(frozen=True)
class Lane:
    lane_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    edge_id: str
    target_product_id: str
    planned_lead_days: float

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.supplier_id, self.item_id, self.dst_node_id, self.edge_id


@dataclass(frozen=True)
class Mechanism:
    key: str
    risk_type: str
    value: float
    unit: str
    label_fr: str


MECHANISMS = (
    Mechanism(
        key="transport_delay",
        risk_type="lead_time_extra_days",
        value=120.0,
        unit="jours_ajoutes",
        label_fr="Stress fournisseur de 6 semaines : délai logistique accru de 120 jours",
    ),
    Mechanism(
        key="planned_delivery_shortfall",
        risk_type="reliability",
        value=0.5,
        unit="part_de_la_quantite_planifiee_livree",
        label_fr="Stress fournisseur de 6 semaines : 50 % de la quantité planifiée reçue",
    ),
)

FORBIDDEN_INCIDENT_RISK_TYPES = frozenset(
    {"availability", "capacity", "stock", "quality_yield", "quality_delay"}
)
ALLOWED_OPERATING_POINT_DEGRADATION_FAMILIES = frozenset(
    {
        "supplier_planned_lead",
        "supplier_nominal_delivery_reliability",
        "balanced_product_supplier_planned_lead",
    }
)

METRIC_FIELDS = (
    "schema_version",
    "campaign_signature",
    "engine_sha256",
    "shard_id",
    "shard_index",
    "shard_count",
    "operating_point_id",
    "operating_point_service_pct",
    "simulation_days",
    "state_evaluation_days",
    "stage",
    "mechanism",
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "target_product_id",
    "seed",
    "status",
    "valid",
    "case_key",
    "case_signature",
    "baseline_case_signature",
    "target_status",
    "target_selection_mode",
    "target_reference_kind",
    "target_shipment_id",
    "target_shipment_count",
    "target_shipment_ids",
    "target_decision_day",
    "target_window_start_day",
    "target_window_end_day",
    "target_window_days",
    "target_active_decision_day_count",
    "target_active_decision_days",
    "target_release_day",
    "target_arrival_day",
    "target_planned_qty",
    "target_expected_delivered_qty",
    "target_uom",
    "baseline_lane_shipped_qty_state_window",
    "target_qty_share_of_lane_state_window",
    "target_group_qty_percentile_lane_state_window",
    "target_exposure_concentration_flag",
    "target_selected_independently_by_operating_point",
    "target_selection_basis",
    "cross_state_common_day_found",
    "cross_state_common_window_found",
    "cross_state_match_status",
    "cross_state_quantity_ratio",
    "cross_state_match_threshold_ratio",
    "state_comparison_valid",
    "seed_cross_state_exposure_comparable",
    "comparable_campaign_seed_count",
    "required_comparable_seed_count",
    "state_exposure_max_window_start_day",
    "state_exposure_max_decision_day",
    "state_exposure_max_group_qty",
    "cross_state_matched_min_group_qty",
    "cross_state_matched_max_group_qty",
    "cross_state_matched_quantities_json",
    "impact_window_start_day",
    "impact_window_end_day",
    "impact_window_days",
    "impact_window_fully_observed",
    "target_latest_baseline_arrival_day",
    "target_latest_stressed_arrival_day",
    "observable_days_after_target_decision",
    "observable_days_after_first_expected_arrival",
    "recovery_observation_days_after_latest_stressed_arrival",
    "recovery_observation_days_within_impact_window",
    "recovery_fully_observed_within_360",
    "minimum_recovery_observation_days_required",
    "causal_window_start_day",
    "causal_window_end_day",
    "causal_window_days",
    "causal_window_defined",
    "causal_window_fully_observed",
    "required_simulation_days",
    "anchor_day",
    "stressed_shipment_ids",
    "stressed_pulled_qty",
    "stressed_shipped_qty",
    "incident_affected_pulled_qty",
    "incident_affected_shipped_qty",
    "incident_plan_divergence_pulled_qty",
    "incident_shipment_count",
    "quantity_shortfall_qty",
    "arrival_delay_days",
    "risk_event_ids",
    "risk_type",
    "risk_value",
    "risk_start_day",
    "risk_end_day",
    "risk_applied_row_count",
    "risk_applied_event_count",
    "baseline_pre_incident_shipment_trace_sha256",
    "incident_pre_incident_shipment_trace_sha256",
    "pre_incident_shipment_trace_match",
    "incident_physically_exercised",
    "physical_exercise_count",
    "target_day",
    "target_shipped_qty",
    "service_output_product_268091_pct",
    "service_output_product_268967_pct",
    "service_global_pct",
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
    "impact_on_due_loss_268091_qty",
    "impact_on_due_loss_268967_qty",
    "impact_on_due_loss_global_qty",
    "impact_on_due_loss_fed_product_qty",
    "impact_on_due_loss_268091_share_of_demand",
    "impact_on_due_loss_268967_share_of_demand",
    "impact_on_due_loss_global_share_of_demand",
    "impact_on_due_loss_fed_product_share_of_demand",
    "impact_backlog_qty_days_delta",
    "impact_backlog_qty_days_per_demand_unit",
    "impact_backlog_relative_load",
    "impact_backlog_qty_days_fed_product_delta",
    "impact_backlog_relative_load_fed_product",
    "impact_max_backlog_qty_delta",
    "impact_max_backlog_share_of_demand",
    "impact_production_loss_268091_qty",
    "impact_production_loss_268967_qty",
    "impact_production_loss_fed_product_qty",
    "impact_production_loss_268091_share_of_demand",
    "impact_production_loss_268967_share_of_demand",
    "impact_production_loss_fed_product_share_of_demand",
    "quantity_shortfall_share_of_target",
    "incident_reference_dose_qty",
    "incident_reference_dose_qty_days",
    "incident_effective_dose_qty",
    "incident_effective_dose_qty_days",
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
    "causal_on_due_loss_268091_qty",
    "causal_on_due_loss_268967_qty",
    "causal_on_due_loss_global_qty",
    "causal_on_due_loss_fed_product_qty",
    "causal_on_due_loss_268091_share_of_demand",
    "causal_on_due_loss_268967_share_of_demand",
    "causal_on_due_loss_global_share_of_demand",
    "causal_on_due_loss_fed_product_share_of_demand",
    "causal_backlog_qty_days_delta",
    "causal_backlog_qty_days_per_demand_unit",
    "causal_backlog_relative_load",
    "causal_backlog_qty_days_fed_product_delta",
    "causal_backlog_relative_load_fed_product",
    "causal_max_backlog_qty_delta",
    "causal_max_backlog_share_of_demand",
    "causal_production_loss_268091_qty",
    "causal_production_loss_268967_qty",
    "causal_production_loss_fed_product_qty",
    "causal_production_loss_268091_share_of_demand",
    "causal_production_loss_268967_share_of_demand",
    "causal_production_loss_fed_product_share_of_demand",
    "global_service_loss_pp",
    "service_loss_268091_pp",
    "service_loss_268967_pp",
    "late_orders",
    "backlog_day_count",
    "backlog_qty",
    "max_backlog_qty",
    "backlog_qty_days",
    "production_released_268091_qty",
    "production_released_268967_qty",
    "total_cost",
    "total_transport_cost",
    "total_purchase_cost",
    "total_unreliable_loss_qty",
    "cumulative_penalty",
    "warmup_core_state_sha256",
    "summary_sha256",
    "validation_errors",
    "error",
    "created_at_utc",
)

TARGET_FIELDS = (
    "campaign_signature",
    "shard_id",
    "shard_index",
    "shard_count",
    "operating_point_id",
    "operating_point_service_pct",
    "simulation_days",
    "state_evaluation_days",
    "seed",
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "target_product_id",
    "target_status",
    "target_shipment_id",
    "target_shipment_count",
    "target_shipment_ids",
    "target_decision_day",
    "target_window_start_day",
    "target_window_end_day",
    "target_window_days",
    "target_active_decision_day_count",
    "target_active_decision_days",
    "target_release_day",
    "target_arrival_day",
    "target_release_days",
    "target_arrival_days",
    "target_planned_qty",
    "target_expected_delivered_qty",
    "target_nominal_reliability",
    "target_lead_days",
    "target_uom",
    "baseline_lane_shipped_qty_state_window",
    "target_qty_share_of_lane_state_window",
    "target_group_qty_percentile_lane_state_window",
    "target_exposure_concentration_flag",
    "target_selection_basis",
    "cross_state_common_day_found",
    "cross_state_common_window_found",
    "cross_state_match_status",
    "cross_state_quantity_ratio",
    "cross_state_match_threshold_ratio",
    "state_comparison_valid",
    "seed_cross_state_exposure_comparable",
    "comparable_campaign_seed_count",
    "required_comparable_seed_count",
    "state_exposure_max_window_start_day",
    "state_exposure_max_decision_day",
    "state_exposure_max_group_qty",
    "cross_state_matched_min_group_qty",
    "cross_state_matched_max_group_qty",
    "cross_state_matched_quantities_json",
    "impact_window_start_day",
    "impact_window_end_day",
    "impact_window_days",
    "impact_window_fully_observed",
    "target_latest_baseline_arrival_day",
    "target_latest_stressed_arrival_day",
    "observable_days_after_target_decision",
    "observable_days_after_first_expected_arrival",
    "recovery_observation_days_after_latest_stressed_arrival",
    "recovery_observation_days_within_impact_window",
    "recovery_fully_observed_within_360",
    "minimum_recovery_observation_days_required",
    "causal_window_start_day",
    "causal_window_end_day",
    "causal_window_days",
    "causal_window_defined",
    "causal_window_fully_observed",
    "required_simulation_days",
    "baseline_pre_incident_shipment_trace_sha256",
    "target_selected_independently_by_operating_point",
    "candidate_day_count",
    "eligible_candidate_day_count",
    "ineligible_candidate_day_count",
    "unique_candidate_day_count",
    "selection_mode",
    "selection_rule",
    "reference_kind",
    "interpretation_fr",
    "reason",
)

LEDGER_FIELDS = (
    "case_key",
    "case_signature",
    "stage",
    "operating_point_id",
    "seed",
    "lane_id",
    "mechanism",
    "status",
    "valid",
    "evidence_path",
    "created_at_utc",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    campaign_core.write_json_atomic(path, payload)


def _write_csv_atomic(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> None:
    campaign_core.write_csv_atomic(path, rows, fields)


def _sha256_file(path: Path) -> str:
    return campaign_core.sha256_file(path)


def _stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _as_float(value: Any, default: float = math.nan) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    return converted if math.isfinite(converted) else default


def _as_int(value: Any, default: int = -1) -> int:
    converted = _as_float(value)
    return int(converted) if math.isfinite(converted) else default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def _event_tokens(value: Any) -> set[str]:
    return {
        token.strip()
        for token in str(value or "").replace(",", "|").split("|")
        if token.strip()
    }


def seed_block(block_number: int) -> tuple[int, ...]:
    if block_number < 1 or block_number > len(SEED_BLOCKS):
        raise ValueError(f"seed block must be in 1..{len(SEED_BLOCKS)}")
    return SEED_BLOCKS[block_number - 1]


def shard_index(point_id: str, block_number: int) -> int:
    if point_id not in OPERATING_POINT_IDS:
        raise ValueError(f"Unknown operating point: {point_id}")
    seed_block(block_number)
    return OPERATING_POINT_IDS.index(point_id) * len(SEED_BLOCKS) + block_number


def _operating_point_service_pct(point: Mapping[str, Any]) -> float:
    calibration = _as_float(point.get("calibration_pooled_service"))
    if math.isfinite(calibration):
        return 100.0 * calibration
    realized = _as_float(point.get("screening_system_service"))
    if math.isfinite(realized):
        return 100.0 * realized
    target = _as_float(point.get("target_service"))
    if not math.isfinite(target):
        raise ValueError(f"Missing service level for {point.get('operating_point_id')}")
    return 100.0 * target


def _required_campaign_holdout_contract() -> dict[str, Any]:
    expected_window = {
        "start_day": 0,
        "end_day": STATE_EVALUATION_DAYS - 1,
        "day_count": STATE_EVALUATION_DAYS,
    }
    return {
        "status_only_if_passed": HOLDOUT_ACCEPTED_STATUS,
        "fixed_point_count": len(OPERATING_POINT_IDS),
        "seed_count": len(SEEDS),
        "baseline_case_count": len(OPERATING_POINT_IDS) * len(SEEDS),
        "seeds": list(SEEDS),
        "service_window": expected_window,
        "op100_minimum_global_and_each_product": 0.985,
        "op93_global_pooled_and_median_band": [0.915, 0.945],
        "op80_global_pooled_and_median_band": [0.785, 0.815],
        "degraded_product_strictly_below": 0.995,
        "pooled_strict_order_required_for": [
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        ],
        "same_seed_joint_strict_order_required": 24,
        "bootstrap_repetitions_descriptive": PREFLIGHT_BOOTSTRAP_REPLICATES,
        "retuning_after_holdout": False,
    }


def _validate_pending_multiseed_v1_source(
    path: Path, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate the pending five-seed selection and its signed source chain.

    The 30 campaign seeds are deliberately still sealed at this point.  The
    campaign discovery is their one holdout use; accepting a stand-alone JSON
    without its signed calibration plan/selection would make that separation
    impossible to audit.
    """

    # Lazy import avoids a cycle while the additive calibration producer reuses
    # the legacy non-strict operating-point loader from this module.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_calibration as multiseed_calibration,
    )

    if (
        payload.get("schema_version") != V1_POINTS_SCHEMA_VERSION
        or payload.get("status") != V1_POINTS_PENDING_STATUS
    ):
        raise ValueError("Pending V1 operating-point schema/status mismatch")
    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, Mapping):
        raise ValueError("Multi-seed operating points have no signed plan reference")
    plan_dir_raw = str(plan_reference.get("path") or "").strip()
    if not plan_dir_raw:
        raise ValueError("Multi-seed operating points have no calibration plan path")
    plan_dir = Path(plan_dir_raw)
    if not plan_dir.is_absolute():
        plan_dir = path.parent / plan_dir
    plan = multiseed_calibration.validate_plan(plan_dir.resolve())
    plan_manifest = plan.manifest
    if (
        str(plan_reference.get("plan_signature") or "")
        != str(plan_manifest.get("plan_signature") or "")
        or payload.get("source_hashes") != plan_manifest.get("source_hashes")
        or payload.get("cohorts") != plan_manifest.get("cohorts")
    ):
        raise ValueError("Multi-seed selection does not match its signed source plan")

    expected_window = {
        "start_day": 0,
        "end_day": STATE_EVALUATION_DAYS - 1,
        "day_count": STATE_EVALUATION_DAYS,
    }
    holdout_contract = dict(plan_manifest.get("holdout_contract") or {})
    required_holdout_contract = _required_campaign_holdout_contract()
    changed_holdout_fields = [
        field
        for field, expected in required_holdout_contract.items()
        if holdout_contract.get(field) != expected
    ]
    if changed_holdout_fields:
        raise ValueError(
            "Signed calibration holdout contract is incompatible: "
            + ", ".join(changed_holdout_fields)
        )
    selection_contract = dict(plan_manifest.get("selection_contract") or {})
    if (
        selection_contract.get("no_holdout_retuning") is not True
        or selection_contract.get("global_median_must_also_be_in_target_band")
        is not True
    ):
        raise ValueError("Signed calibration does not preserve the sealed holdout")
    if payload.get("service_evaluation_window") != expected_window:
        raise ValueError("Selected operating-point service window changed")

    selection_path = path.parent / "selection.json"
    if not selection_path.is_file():
        raise FileNotFoundError(
            f"Missing signed multi-seed selection evidence: {selection_path}"
        )
    selection = _read_json(selection_path)
    unsigned_selection = dict(selection)
    selection_signature = str(unsigned_selection.pop("selection_signature", ""))
    if (
        not selection_signature
        or selection_signature != _stable_sha256(unsigned_selection)
        or selection_signature != str(payload.get("selection_signature") or "")
        or selection.get("schema_version")
        != multiseed_calibration.SELECTION_SCHEMA_VERSION
        or selection.get("status") != "calibration_selected"
        or selection.get("plan_signature") != plan_manifest.get("plan_signature")
        or selection.get("calibration_seeds")
        != list(multiseed_calibration.CALIBRATION_SEEDS)
        or selection.get("holdout_seeds_sealed_and_unread") != list(SEEDS)
        or selection.get("selection_contract")
        != plan_manifest.get("selection_contract")
        or selection.get("fallback_required") is not False
    ):
        raise ValueError("Multi-seed selection evidence/signature is invalid")
    selected_pair = selection.get("selected_pair")
    if not isinstance(selected_pair, Mapping):
        raise ValueError("Multi-seed selection has no selected operating-point pair")
    candidate_by_point = {
        str(point.get("operating_point_id") or ""): str(
            point.get("candidate_key") or ""
        )
        for point in payload.get("operating_points") or []
        if isinstance(point, Mapping)
    }
    if (
        candidate_by_point.get("op_100") != "op100_reference"
        or candidate_by_point.get("op_93")
        != str(selected_pair.get("op93_candidate_key") or "")
        or candidate_by_point.get("op_80")
        != str(selected_pair.get("op80_candidate_key") or "")
    ):
        raise ValueError("Selected operating points differ from selection evidence")
    return {
        "producer": "v1_calibration",
        "plan_path": str(plan.plan_dir.resolve()),
        "plan_manifest_path": str((plan.plan_dir / "calibration_plan.json").resolve()),
        "plan_signature": str(plan_manifest["plan_signature"]),
        "selection_path": str(selection_path.resolve()),
        "selection_signature": selection_signature,
        "holdout_contract": holdout_contract,
    }


def _validate_pending_multiseed_v2_source(
    path: Path, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Delegate V2 proof validation to its producer without a module cycle."""

    # The refinement imports the V1 producer, whose prevalidation layer imports
    # this campaign module.  Importing only at call time keeps that chain acyclic
    # during module initialization.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v2 as refinement_v2,
    )

    if (
        payload.get("schema_version") != refinement_v2.POINTS_SCHEMA_VERSION
        or payload.get("schema_version") != V2_POINTS_SCHEMA_VERSION
        or payload.get("status") != V2_POINTS_PENDING_STATUS
    ):
        raise ValueError("Pending V2 operating-point schema/status mismatch")
    validated = refinement_v2.validate_selected_operating_points(path)
    if validated != payload:
        raise ValueError("V2 producer validation returned different operating points")
    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, Mapping):
        raise ValueError("V2 operating points have no signed refinement plan")
    plan_path = Path(str(plan_reference.get("path") or ""))
    if not plan_path.is_absolute():
        plan_path = path.parent / plan_path
    plan = refinement_v2.validate_plan(plan_path.resolve())
    plan_manifest = plan.manifest
    holdout_contract = dict(plan_manifest.get("holdout_contract") or {})
    incompatible = [
        field
        for field, expected in _required_campaign_holdout_contract().items()
        if holdout_contract.get(field) != expected
    ]
    if incompatible:
        raise ValueError(
            "Signed V2 refinement holdout contract is incompatible: "
            + ", ".join(incompatible)
        )
    if (
        holdout_contract.get("status") != "sealed_unread"
        or holdout_contract.get("cases_in_this_plan") != 0
        or payload.get("holdout_cases_read") != 0
        or payload.get("holdout_contract") != holdout_contract
        or payload.get("target_labels_apply_to_global_service_only") is not True
    ):
        raise ValueError("V2 refinement does not preserve the sealed holdout")
    selection_reference = payload.get("selection")
    if not isinstance(selection_reference, Mapping):
        raise ValueError("V2 operating points have no signed selection reference")
    relative_selection = Path(str(selection_reference.get("relative_path") or ""))
    selection_path = (path.parent / relative_selection).resolve()
    plan_manifest_path = (plan.plan_dir / "refinement_plan.json").resolve()
    if not plan_manifest_path.is_file() or not selection_path.is_file():
        raise FileNotFoundError("Signed V2 refinement plan/selection disappeared")
    return {
        "producer": "v2_refinement",
        "plan_path": str(plan.plan_dir.resolve()),
        "plan_manifest_path": str(plan_manifest_path),
        "plan_signature": str(plan_manifest["plan_signature"]),
        "selection_path": str(selection_path),
        "selection_signature": str(payload["selection_signature"]),
        "holdout_contract": holdout_contract,
    }


def _validate_pending_multiseed_v3_source(
    path: Path, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate the frozen V3 producer and independently cross-check its chain."""

    # V3 imports V2, which eventually reaches this campaign module through the
    # legacy prevalidation dependency.  Keep this import local to avoid a cycle
    # while this module initializes.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v3 as refinement_v3,
    )

    producer_module = Path(refinement_v3.__file__).resolve()
    producer_module_sha256 = _sha256_file(producer_module)
    if producer_module_sha256 != V3_REFINEMENT_MODULE_SHA256:
        raise ValueError("Frozen V3 refinement producer hash changed")
    if (
        refinement_v3.POINTS_SCHEMA_VERSION != V3_POINTS_SCHEMA_VERSION
        or refinement_v3.POINTS_STATUS != V3_POINTS_PENDING_STATUS
        or refinement_v3.SELECTION_PASS_STATUS != V3_SELECTION_PASS_STATUS
        or payload.get("schema_version") != V3_POINTS_SCHEMA_VERSION
        or payload.get("status") != V3_POINTS_PENDING_STATUS
    ):
        raise ValueError("Pending V3 operating-point schema/status mismatch")

    # This call revalidates the complete 80-proof run, including the signed V2
    # 65-proof NO-GO source.  The checks below deliberately recut the provenance
    # fields consumed by the full-campaign manifest instead of trusting only the
    # producer's return value.
    validated = refinement_v3.validate_selected_operating_points(path)
    if validated != payload:
        raise ValueError("V3 producer validation returned different operating points")

    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, Mapping):
        raise ValueError("V3 operating points have no signed refinement plan")
    plan_path_raw = str(plan_reference.get("path") or "").strip()
    if not plan_path_raw:
        raise ValueError("V3 operating points have no refinement plan path")
    plan_path = Path(plan_path_raw)
    if not plan_path.is_absolute():
        plan_path = path.parent / plan_path
    plan = refinement_v3.validate_plan(plan_path.resolve())
    plan_manifest = plan.manifest
    plan_manifest_path = (plan.plan_dir / "refinement_plan.json").resolve()
    if not plan_manifest_path.is_file():
        raise FileNotFoundError("Signed V3 refinement plan disappeared")
    if (
        str(plan_reference.get("plan_signature") or "")
        != str(plan_manifest.get("plan_signature") or "")
        or payload.get("source_hashes") != plan_manifest.get("source_hashes")
        or payload.get("cohorts") != plan_manifest.get("cohorts")
        or dict(plan_manifest.get("source_hashes") or {}).get("v3_driver_sha256")
        != producer_module_sha256
    ):
        raise ValueError("V3 selected points do not match their signed source plan")

    holdout_contract = dict(plan_manifest.get("holdout_contract") or {})
    incompatible = [
        field
        for field, expected in _required_campaign_holdout_contract().items()
        if holdout_contract.get(field) != expected
    ]
    if incompatible:
        raise ValueError(
            "Signed V3 refinement holdout contract is incompatible: "
            + ", ".join(incompatible)
        )
    if (
        holdout_contract.get("status") != "sealed_unread"
        or holdout_contract.get("cases_in_this_plan") != 0
        or holdout_contract.get("selected_output_status") != V3_POINTS_PENDING_STATUS
        or payload.get("holdout_cases_read") != 0
        or payload.get("holdout_contract") != holdout_contract
        or payload.get("target_labels_apply_to_global_service_only") is not True
    ):
        raise ValueError("V3 refinement does not preserve the sealed holdout")

    selection_reference = payload.get("selection")
    if not isinstance(selection_reference, Mapping):
        raise ValueError("V3 operating points have no signed selection reference")
    if (
        selection_reference.get("relative_path") != "selection.json"
        or selection_reference.get("schema_version")
        != refinement_v3.SELECTION_SCHEMA_VERSION
    ):
        raise ValueError("V3 operating points do not reference the sibling selection")
    selection_path = (path.parent / "selection.json").resolve()
    if not selection_path.is_file():
        raise FileNotFoundError("Signed V3 refinement selection disappeared")
    selection = _read_json(selection_path)
    unsigned_selection = dict(selection)
    selection_signature = str(unsigned_selection.pop("selection_signature", ""))
    selected_pair = selection.get("selected_pair")
    eligible_pairs = selection.get("eligible_pairs")
    if (
        not selection_signature
        or selection_signature != _stable_sha256(unsigned_selection)
        or selection_signature != str(payload.get("selection_signature") or "")
        or selection_signature
        != str(selection_reference.get("selection_signature") or "")
        or selection.get("schema_version") != refinement_v3.SELECTION_SCHEMA_VERSION
        or selection.get("status") != V3_SELECTION_PASS_STATUS
        or selection.get("plan_signature") != plan_manifest.get("plan_signature")
        or selection.get("calibration_seeds") != list(CALIBRATION_SEEDS)
        or selection.get("holdout_seeds_sealed_and_unread") != list(SEEDS)
        or selection.get("holdout_cases_read") != 0
        or selection.get("selection_contract")
        != plan_manifest.get("selection_contract")
        or selection.get("holdout_contract") != holdout_contract
        or selection.get("holdout_launch_permitted") is not True
        or selection.get("fallback_required") is not False
        or not isinstance(selected_pair, Mapping)
        or not isinstance(eligible_pairs, list)
        or not eligible_pairs
        or selected_pair != eligible_pairs[0]
    ):
        raise ValueError("V3 selection evidence/status/signature is invalid")

    candidate_by_point = {
        str(point.get("operating_point_id") or ""): str(
            point.get("candidate_key") or ""
        )
        for point in payload.get("operating_points") or []
        if isinstance(point, Mapping)
    }
    if (
        candidate_by_point.get("op_100") != refinement_v3.FIXED_REFERENCE_KEY
        or candidate_by_point.get("op_93") != refinement_v3.FIXED_OP93_KEY
        or candidate_by_point.get("op_80")
        != str(selected_pair.get("op80_candidate_key") or "")
        or str(selected_pair.get("op93_candidate_key") or "")
        != refinement_v3.FIXED_OP93_KEY
    ):
        raise ValueError("V3 selected operating points differ from selection evidence")

    return {
        "producer": "v3_refinement",
        "plan_path": str(plan.plan_dir.resolve()),
        "plan_manifest_path": str(plan_manifest_path),
        "plan_signature": str(plan_manifest["plan_signature"]),
        "selection_path": str(selection_path),
        "selection_signature": selection_signature,
        "holdout_contract": holdout_contract,
    }


def _validate_pending_multiseed_source(
    path: Path, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Dispatch exactly the signed V1, V2, and V3 pending-point contracts."""

    schema = str(payload.get("schema_version") or "")
    status = str(payload.get("status") or "")
    supported = {
        V1_POINTS_SCHEMA_VERSION: V1_POINTS_PENDING_STATUS,
        V2_POINTS_SCHEMA_VERSION: V2_POINTS_PENDING_STATUS,
        V3_POINTS_SCHEMA_VERSION: V3_POINTS_PENDING_STATUS,
    }
    if schema not in supported or status != supported[schema]:
        raise ValueError(
            "Full campaign requires an exact signed V1, V2, or V3 five-seed "
            "multi-seed selection reserved for one 30-seed holdout"
        )
    unsigned = dict(payload)
    artifact_signature = str(unsigned.pop("artifact_signature", ""))
    if not artifact_signature or artifact_signature != _stable_sha256(unsigned):
        raise ValueError("Multi-seed operating-point artifact signature is invalid")
    cohorts = dict(payload.get("cohorts") or {})
    if (
        list(cohorts.get("design") or []) != [TARGET_DESIGN_SEED]
        or list(cohorts.get("calibration") or []) != list(CALIBRATION_SEEDS)
        or list(cohorts.get("holdout_sealed") or []) != list(SEEDS)
        or payload.get("holdout_validated") is not False
        or payload.get("simulation_hypotheses_not_observed_performance") is not True
    ):
        raise ValueError("Multi-seed calibration/holdout cohorts fail closed")
    if schema == V1_POINTS_SCHEMA_VERSION:
        return _validate_pending_multiseed_v1_source(path, payload)
    if schema == V2_POINTS_SCHEMA_VERSION:
        return _validate_pending_multiseed_v2_source(path, payload)
    return _validate_pending_multiseed_v3_source(path, payload)


def load_operating_points(
    path: Path, *, require_prevalidated: bool = True
) -> list[dict[str, Any]]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing operating points: {path}")
    payload = _read_json(path)
    if require_prevalidated:
        _validate_pending_multiseed_source(path, payload)
    else:
        if payload.get("quality_branch_included") is not False:
            raise ValueError(
                "Operating points must explicitly exclude the quality branch"
            )
        if payload.get("supplier_state_dependent_risks_enabled") is not False:
            raise ValueError(
                "Operating points must explicitly disable state-dependent risks"
            )
        if payload.get("acute_incident_included_in_operating_point") is not False:
            raise ValueError(
                "Operating points must not already contain an acute incident"
            )
    raw_points = [dict(value) for value in payload.get("operating_points") or []]
    by_id = {str(value.get("operating_point_id") or ""): value for value in raw_points}
    if set(by_id) != set(OPERATING_POINT_IDS) or len(raw_points) != len(
        OPERATING_POINT_IDS
    ):
        raise ValueError("Exactly op_100, op_93 and op_80 are required")
    points: list[dict[str, Any]] = []
    for point_id in OPERATING_POINT_IDS:
        point = by_id[point_id]
        graph = Path(str(point.get("graph") or "")).resolve()
        floors_raw = str(point.get("supplier_floors") or "").strip()
        floors = Path(floors_raw).resolve() if floors_raw else None
        factory_raw = str(point.get("factory_capacities") or "").strip()
        factory = Path(factory_raw).resolve() if factory_raw else None
        if not graph.is_file():
            raise FileNotFoundError(f"Missing graph input for {point_id}: {graph}")
        graph_sha256 = _sha256_file(graph)
        if (
            require_prevalidated
            and str(point.get("graph_sha256") or "") != graph_sha256
        ):
            raise ValueError(f"Signed graph hash changed for {point_id}")
        for field in (
            "target_service",
            "calibration_pooled_service",
            "calibration_product_268091_service",
            "calibration_product_268967_service",
            "offset_days_268091",
            "offset_days_268967",
        ):
            if require_prevalidated and not math.isfinite(_as_float(point.get(field))):
                raise ValueError(f"Missing finite {field} for {point_id}")
        if floors is not None and not floors.is_file():
            raise FileNotFoundError(f"Missing supplier floors for {point_id}: {floors}")
        if factory is not None and not factory.is_file():
            raise FileNotFoundError(
                f"Missing factory capacities for {point_id}: {factory}"
            )
        degradation_family = str(point.get("degradation_family") or "")
        if require_prevalidated and not degradation_family:
            degradation_family = (
                "baseline"
                if point_id == "op_100"
                else "balanced_product_supplier_planned_lead"
            )
        if (
            point_id != "op_100"
            and degradation_family not in ALLOWED_OPERATING_POINT_DEGRADATION_FAMILIES
        ):
            raise ValueError(
                "The degraded points must use an allowed structural supplier "
                "family (planned lead, balanced product-specific planned lead, "
                "or nominal delivery reliability)"
            )
        normalized = dict(point)
        normalized.update(
            {
                "degradation_family": degradation_family,
                "graph": str(graph),
                "graph_sha256": graph_sha256,
                "supplier_floors": str(floors) if floors is not None else "",
                "supplier_floors_sha256": _sha256_file(floors)
                if floors is not None
                else "",
                "factory_capacities": str(factory) if factory is not None else "",
                "factory_capacities_sha256": _sha256_file(factory)
                if factory is not None
                else "",
                "operating_point_service_pct": _operating_point_service_pct(point),
            }
        )
        points.append(normalized)
    degraded_families = {
        str(point["degradation_family"])
        for point in points
        if point["operating_point_id"] != "op_100"
    }
    if len(degraded_families) != 1:
        raise ValueError("op_93 and op_80 must share one structural degradation family")
    return points


def load_lanes(path: Path) -> list[Lane]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing lane reference: {path}")
    lanes: list[Lane] = []
    for row in _read_csv(path):
        if str(row.get("scope_status") or "") != "active_simulated_reference_v10":
            continue
        lane = Lane(
            lane_id=str(row.get("chain_id") or "").strip(),
            supplier_id=str(row.get("supplier_id") or "").strip(),
            item_id=str(row.get("item_id") or "").strip(),
            dst_node_id=str(row.get("dst_node_id") or "").strip(),
            edge_id=str(row.get("edge_id") or "").strip(),
            target_product_id=str(row.get("target_product_id") or "").strip(),
            planned_lead_days=_as_float(row.get("planned_lead_days")),
        )
        if not all(
            (
                lane.lane_id,
                lane.supplier_id,
                lane.item_id,
                lane.dst_node_id,
                lane.edge_id,
                lane.target_product_id,
            )
        ) or not math.isfinite(lane.planned_lead_days):
            raise ValueError(f"Incomplete active lane: {row}")
        if not lane.item_id.startswith("item:"):
            raise ValueError(f"Lane item must be normalized: {lane.item_id}")
        lanes.append(lane)
    if len(lanes) != 18:
        raise ValueError(f"Expected exactly 18 active lanes; found {len(lanes)}")
    if (
        len({lane.lane_id for lane in lanes}) != 18
        or len({lane.key for lane in lanes}) != 18
    ):
        raise ValueError("Lane identities are not unique")
    return sorted(lanes, key=lambda lane: lane.lane_id)


def _mechanism_contract() -> list[dict[str, Any]]:
    result = [asdict(mechanism) for mechanism in MECHANISMS]
    if {row["risk_type"] for row in result} & FORBIDDEN_INCIDENT_RISK_TYPES:
        raise AssertionError("The V2 mechanism contract contains a forbidden risk type")
    if {row["key"] for row in result} != {
        "transport_delay",
        "planned_delivery_shortfall",
    }:
        raise AssertionError("The V2 mechanism contract changed")
    return result


def _design_payload(
    *,
    operating_points_path: Path,
    lane_reference_path: Path,
    engine: Path,
    profile: Path,
    points: Sequence[Mapping[str, Any]],
    lanes: Sequence[Lane],
) -> dict[str, Any]:
    engine = engine.resolve()
    profile = profile.resolve()
    for required, label in ((engine, "engine"), (profile, "engine profile")):
        if not required.is_file():
            raise FileNotFoundError(f"Missing {label}: {required}")
    operating_point_source = _read_json(operating_points_path.resolve())
    source_hashes = dict(operating_point_source.get("source_hashes") or {})
    if source_hashes.get("engine_sha256") != _sha256_file(engine) or source_hashes.get(
        "profile_sha256"
    ) != _sha256_file(profile):
        raise ValueError(
            "Campaign engine/profile differ from the signed multi-seed calibration"
        )
    source_chain = _validate_pending_multiseed_source(
        operating_points_path.resolve(), operating_point_source
    )
    source_plan_path = Path(source_chain["plan_manifest_path"])
    selection_path = Path(source_chain["selection_path"])
    if not source_plan_path.is_file() or not selection_path.is_file():
        raise FileNotFoundError(
            "Signed multi-seed plan/selection evidence disappeared after validation"
        )
    source_plan_manifest = _read_json(source_plan_path)
    state_projection = [
        {
            "operating_point_id": point["operating_point_id"],
            "operating_point_label": point.get("operating_point_label", ""),
            "operating_point_service_pct": point["operating_point_service_pct"],
            "target_service_pct": 100.0 * float(point["target_service"]),
            "calibration_pooled_service_pct": (
                100.0 * float(point["calibration_pooled_service"])
                if math.isfinite(_as_float(point.get("calibration_pooled_service")))
                else ""
            ),
            "calibration_product_268091_service_pct": (
                100.0 * float(point["calibration_product_268091_service"])
                if math.isfinite(
                    _as_float(point.get("calibration_product_268091_service"))
                )
                else ""
            ),
            "calibration_product_268967_service_pct": (
                100.0 * float(point["calibration_product_268967_service"])
                if math.isfinite(
                    _as_float(point.get("calibration_product_268967_service"))
                )
                else ""
            ),
            "original_target_service_pct": (
                100.0 * float(point["original_target_service"])
                if math.isfinite(_as_float(point.get("original_target_service")))
                else ""
            ),
            "state_label_is_observed_prevalidation_value": bool(
                point.get("state_label_is_observed_prevalidation_value", False)
            ),
            "prevalidation_target_attained": point.get(
                "prevalidation_target_attained", ""
            ),
            "prevalidation_state_accepted": point.get(
                "prevalidation_state_accepted", ""
            ),
            "degradation_family": point.get("degradation_family", ""),
            "degradation_value": point.get("degradation_value", ""),
            "degradation_unit": point.get("degradation_unit", ""),
            "graph": point["graph"],
            "graph_sha256": point["graph_sha256"],
            "supplier_floors": point["supplier_floors"],
            "supplier_floors_sha256": point["supplier_floors_sha256"],
            "factory_capacities": point["factory_capacities"],
            "factory_capacities_sha256": point["factory_capacities_sha256"],
        }
        for point in points
    ]
    lane_projection = [asdict(lane) for lane in lanes]
    shard_projection = []
    for point_id in OPERATING_POINT_IDS:
        for block_number, block in enumerate(SEED_BLOCKS, 1):
            shard_projection.append(
                {
                    "shard_id": f"{point_id}__seed_block_{block_number:02d}",
                    "shard_index": shard_index(point_id, block_number),
                    "shard_count": len(OPERATING_POINT_IDS) * len(SEED_BLOCKS),
                    "operating_point_id": point_id,
                    "seed_block": block_number,
                    "seed_ids": list(block),
                    "baseline_rows": len(block),
                    "incident_rows": len(block) * len(lanes) * len(MECHANISMS),
                    "total_rows": len(block) * (1 + len(lanes) * len(MECHANISMS)),
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "runner": str(Path(__file__).resolve()),
        "runner_sha256": _sha256_file(Path(__file__).resolve()),
        "scope": "full_3_states_18_lanes_2_incidents_30_repetitions",
        "days": "adaptive_by_operating_point_seed_and_incident_target",
        "simulation_days": "adaptive_by_operating_point_seed_and_incident_target",
        "discovery_days": DISCOVERY_DAYS,
        "minimum_case_days": MINIMUM_CASE_DAYS,
        "adaptive_horizon_contract": {
            "selection": "independent_of_horizon_observability_on_discovery_J0_J719",
            "baseline_days": "max_final_incident_required_days_across_the_18_lanes_for_state_seed",
            "incident_days": "max_720_fixed_360_end_exclusive_actual_arrival_plus_90_exclusive",
            "required_days_formula": (
                "max(720,window_start_plus_360,latest_tagged_arrival_plus_90); "
                "the_last_term_is_exclusive_and_gives_90_observed_days_including_arrival"
            ),
            "incident_two_pass": (
                "initial_run_then_extend_if_actual_tagged_arrivals_lack_90_day_followup; "
                "J0_J719_trace_must_be_invariant_on_rerun"
            ),
            "probe_compaction": (
                "extract_absolute_metrics_incident_trace_and_signed_physical_proof_"
                "then_prune_each_engine_case_before_running_the_paired_baseline"
            ),
            "resume_after_probe_prune": True,
            "resume_after_probe_prune_condition": (
                "a_signed_per_horizon_checkpoint_is_persisted_before_every_"
                "intermediate_prune_and_the_signed_final_probe_precedes_final_prune"
            ),
            "failed_attempt_retention": {
                "policy": (
                    "persist_bounded_signed_diagnostic_then_remove_failed_attempt_tree"
                ),
                "inventory_entry_limit": FAILED_ATTEMPT_INVENTORY_LIMIT,
                "log_tail_byte_limit": FAILED_ATTEMPT_LOG_TAIL_BYTES,
                "diagnostic_limit_per_case": FAILED_ATTEMPT_DIAGNOSTICS_PER_CASE,
            },
            "fixed_upper_bound_assumed": False,
            "discovery_rows_in_campaign_metrics": False,
        },
        "state_evaluation_window": {
            "start_day": 0,
            "end_day": STATE_EVALUATION_DAYS - 1,
            "day_count": STATE_EVALUATION_DAYS,
            "purpose": "preserve_calibrated_operating_point_service_definition",
        },
        "incident_impact_window": {
            "anchor": "first_day_of_fixed_42_day_supplier_disruption_window",
            "day_count": IMPACT_WINDOW_DAYS,
            "includes_anchor_day": True,
            "required_latest_delayed_arrival_offset_days": TARGET_SELECTION_MAX_DELAY_DAYS,
            "minimum_observation_days_after_latest_delayed_arrival": (
                MIN_RECOVERY_OBSERVATION_DAYS
            ),
            "eligibility": (
                "adaptive_case_horizon_contains_the_fixed_360d_business_envelope_and_"
                "at_least_90_days_after_the_latest_actually_tagged_incident_arrival"
            ),
        },
        "warmup_days": protocol.WARMUP_DAYS,
        "engine": str(engine),
        "engine_sha256": _sha256_file(engine),
        "engine_profile": str(profile),
        "engine_profile_sha256": _sha256_file(profile),
        "managed_engine_args": list(protocol.MANAGED_REFERENCE_PROTOCOL_ARGS),
        "operating_points_source": str(operating_points_path.resolve()),
        "operating_points_source_sha256": _sha256_file(operating_points_path.resolve()),
        "operating_points_producer": str(source_chain["producer"]),
        "operating_points_schema_version": str(
            operating_point_source.get("schema_version") or ""
        ),
        "operating_points_artifact_signature": str(
            operating_point_source.get("artifact_signature") or ""
        ),
        "operating_points_input_status": str(
            operating_point_source.get("status") or ""
        ),
        "operating_points_cohorts": dict(operating_point_source.get("cohorts") or {}),
        "operating_points_calibration_plan": str(source_plan_path),
        "operating_points_calibration_plan_sha256": _sha256_file(source_plan_path),
        "operating_points_calibration_plan_signature": str(
            source_plan_manifest.get("plan_signature") or ""
        ),
        "operating_points_selection": str(selection_path.resolve()),
        "operating_points_selection_sha256": _sha256_file(selection_path),
        "operating_points_selection_signature": str(
            operating_point_source.get("selection_signature") or ""
        ),
        "operating_points_holdout_contract": dict(
            source_plan_manifest.get("holdout_contract") or {}
        ),
        "lane_reference_source": str(lane_reference_path.resolve()),
        "lane_reference_source_sha256": _sha256_file(lane_reference_path.resolve()),
        "states": state_projection,
        "lanes": lane_projection,
        "mechanisms": _mechanism_contract(),
        "seeds": list(SEEDS),
        "seed_blocks": [list(block) for block in SEED_BLOCKS],
        "shards": shard_projection,
        "expected_counts": {
            "auxiliary_discovery_runs": len(points) * (len(SEEDS) + 1),
            "baseline_rows": len(points) * len(SEEDS),
            "incident_rows": len(points) * len(SEEDS) * len(lanes) * len(MECHANISMS),
            "total_rows": len(points) * len(SEEDS) * (1 + len(lanes) * len(MECHANISMS)),
            "shard_count": len(shard_projection),
            "rows_per_shard": SEED_BLOCK_SIZE * (1 + len(lanes) * len(MECHANISMS)),
            "maximum_engine_invocations_per_shard_without_reuse": (
                SEED_BLOCK_SIZE + 4 * SEED_BLOCK_SIZE * len(lanes) * len(MECHANISMS)
            ),
        },
        "pairing": "same_operating_point_same_seed_same_warmup_core_state",
        "target_discovery_contract": {
            "design_seed": TARGET_DESIGN_SEED,
            "design_seed_in_campaign_statistics": False,
            "campaign_seeds": list(SEEDS),
            "disruption_window_days": INCIDENT_DISRUPTION_DAYS,
            "same_lane_specific_dates_across_states_and_campaign_seeds": True,
            "quantity_ratio_limit": STATE_MATCH_MAX_QUANTITY_RATIO,
            "minimum_comparable_campaign_seeds": 24,
            "campaign_exposure_gate": (
                "all_18_lanes_must_have_a_design_window_with_ratio_le_1.5_and_"
                "at_least_24_of_30_comparable_holdout_exposures"
            ),
            "exposure_gate_failure_policy": "block_all_incident_probes",
            "selection": (
                "on_design_seed_only_choose_common_positive_42d_windows_with_ratio_le_1.5; "
                "maximise_minimum_quantity_then_minimise_ratio_then_earliest_start; "
                "fixed_dates_on_campaign_seeds"
            ),
            "zero_flow_campaign_seed_policy": (
                "run_incident_as_valid_zero_effect_non_exercised_and_include_in_physical_exercise_rate"
            ),
            "duration_rationale": (
                "42_calendar_days_is_a_readable_six_week_business_window_with_a_"
                "three_day_margin_above_the_39_day_empirical_minimum_that_exposes_"
                "all_18_lanes_on_the_signed_design_seed"
            ),
        },
        "operating_point_preflight_contract": {
            "timing": "after_93_discovery_runs_before_any_incident_probe",
            "campaign_seed_count": len(SEEDS),
            "design_seed_excluded": TARGET_DESIGN_SEED,
            "aggregation": "ratio_of_sums_over_30_paired_campaign_seeds",
            "bootstrap_replicates": PREFLIGHT_BOOTSTRAP_REPLICATES,
            "bootstrap_seed": PREFLIGHT_BOOTSTRAP_SEED,
            "op_100": "global and each PF 98.5-100%",
            "op_93": (
                "global target +/-1.5pp; each PF strictly below 99.5%; PF gap>5pp flagged"
            ),
            "op_80": (
                "global within 1.5pp of its signed target (which may be the "
                "selected multi-seed target); each PF strictly below 99.5%; "
                "PF gap>5pp flagged"
            ),
            "ordering": (
                "op_100>op_93>op_80 in ratio-of-sums and in at least 24/30 "
                "paired seeds for global service and each finished product"
            ),
            "central_tendency": (
                "ratio-of-sums and median seed-level global service must both be "
                "inside the signed state band"
            ),
            "failure_policy": "block_all_incident_probes",
        },
        "target_selection": {
            "reference_kind": "paired_simulated_baseline_shipment_not_observed_supplier_performance",
            "group_key": "lane_id+fixed_42_day_risk_decision_window",
            "preferred_positive_rows_in_group": "all_positive_rows_in_window",
            "selection_rule": (
                "fixed_on_independent_design_seed_340281_not_selected_on_campaign_repetitions; "
                "all_dispatches_in_the_42_day_window_are_the_exogenous_stress_scope"
            ),
            "decision_day_window": [0, STATE_EVALUATION_DAYS - 1],
            "simulation_day_window": "adaptive_case_horizon",
            "impact_window_days": IMPACT_WINDOW_DAYS,
            "maximum_incident_arrival_shift_days": TARGET_SELECTION_MAX_DELAY_DAYS,
            "minimum_recovery_observation_days": MIN_RECOVERY_OBSERVATION_DAYS,
            "no_positive_or_fully_observable_flow_policy": (
                "fixed_calendar_window_with_zero_flow_runs_as_valid_no_exposure_and_zero_"
                "effect; physical_exercise_rate_is_reported"
            ),
            "target_claim": (
                "fixed_42_day_simulated_supplier_disruption_window_not_an_observed_incident"
            ),
            "cross_operating_point_identity": (
                "same_lane_specific_42_day_dates_are_fixed_on_design_seed_340281_and_"
                "reused_across_all_states_and_30_campaign_seeds; quantities_may_differ"
            ),
        },
        "impact_metric_contract": {
            "primary": (
                "paired_service_loss_pp_of_finished_product_fed_by_lane_on_fixed_360d_envelope"
            ),
            "causal_window": (
                "physical_explanation_from_first_relevant_arrival_through_day_"
                "latest_actually_tagged_arrival_plus_89_inclusive"
            ),
            "business_envelope": "fixed_360_days_from_risk_decision_day",
            "secondary": [
                "paired_global_service_loss_pp",
                "absolute_on_due_quantity_loss",
                "incremental_backlog_quantity_days",
                "released_production_loss",
            ],
            "normalization": (
                "finished-product effects normalized only by finished-product demand; "
                "component target quantity is used only for within-lane exposure dose"
            ),
            "cross_uom_component_to_finished_product_ratio_used": False,
            "supplier_interpretation": (
                "ranking_identifies_the_most_exposed_simulated_lane_not_intrinsic_"
                "supplier_quality"
            ),
            "recovery_claim": (
                "fixed follow-up is observed; recovery time is not imputed when not demonstrated"
            ),
            "full_horizon_cost_pairing_comparable": False,
            "cost_effect_axis_status": (
                "not_available_without_daily_cost_trace_on_matched_windows"
            ),
            "cost_guard": (
                "total_cost_transport_and_purchase_totals_must_not_be_differenced_"
                "when_paired_case_horizons_differ"
            ),
        },
        "quality_branch_included": False,
        "quality_incident_included": False,
        "availability_incident_included": False,
        "capacity_incident_included": False,
        "stock_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "historical_incident_probability_estimated": False,
        "incident_interpretation": "conditional_simulation_hypotheses_not_observed_supplier_performance",
        "stochastic_scope": {
            "random_sources": [
                {
                    "source": "supplier_flow_logistics_delay",
                    "distribution": "four_stage_erlang",
                    "status": "graph_assumption_not_calibrated_on_supplier_history",
                }
            ],
            "demand": "fixed_2025_cyclic_profile",
            "capacity_outside_incident": "fixed",
            "reliability_outside_incident": "fixed",
            "quality_enabled": False,
            "state_dependent_supplier_risk_enabled": False,
            "uncertainty_interpretation": (
                "confidence_intervals_quantiles_and_bootstrap_describe_conditional_"
                "variability_under_this_simulation_assumption_not_industrial_failure_frequency"
            ),
        },
        "lot_trace_scope": "compact_network_screen_without_detailed_lot_trace",
        "detailed_lot_proof_status": "required_replay_on_final_top3_after_campaign",
        "all_lots_traced_claimed": False,
    }


def prepare_manifest(
    *,
    output_dir: Path,
    operating_points_path: Path,
    lane_reference_path: Path,
    engine: Path,
    profile: Path,
    smoke: bool = False,
    smoke_point_id: str = "op_100",
    smoke_seed: int = SEEDS[0],
    smoke_lane_id: str | None = None,
    require_existing: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Lane]]:
    points = load_operating_points(operating_points_path)
    lanes = load_lanes(lane_reference_path)
    design = _design_payload(
        operating_points_path=operating_points_path,
        lane_reference_path=lane_reference_path,
        engine=engine,
        profile=profile,
        points=points,
        lanes=lanes,
    )
    if smoke:
        lane_id = smoke_lane_id or lanes[0].lane_id
        if lane_id not in {lane.lane_id for lane in lanes}:
            raise ValueError(f"Unknown smoke lane: {lane_id}")
        if smoke_point_id not in OPERATING_POINT_IDS:
            raise ValueError(f"Unknown smoke operating point: {smoke_point_id}")
        design["scope"] = "smoke_non_reusable"
        design["smoke"] = {
            "operating_point_id": smoke_point_id,
            "seed": int(smoke_seed),
            "lane_id": lane_id,
        }
        design["expected_counts"] = {
            "auxiliary_discovery_runs": 1,
            "baseline_rows": 1,
            "incident_rows": 2,
            "total_rows": 3,
            "shard_count": 1,
            "rows_per_shard": 3,
            "maximum_engine_invocations_per_shard_without_reuse": 4,
        }
    signature = _stable_sha256(design)
    manifest = {
        **design,
        "campaign_signature": signature,
        "status": "smoke_planned" if smoke else "planned",
        "created_at_utc": utc_now(),
        "completed_at_utc": "",
    }
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "campaign_manifest.json"
    if manifest_path.is_file():
        existing = _read_json(manifest_path)
        if existing.get("campaign_signature") != signature:
            raise ValueError("Output directory belongs to another campaign signature")
        changed_design_fields = [
            key for key, expected in design.items() if existing.get(key) != expected
        ]
        if changed_design_fields:
            raise ValueError(
                "Existing campaign manifest changed signed design fields: "
                + ", ".join(changed_design_fields)
            )
        manifest = existing
    else:
        if require_existing:
            raise FileNotFoundError(
                "Run --mode plan once before launching isolated shards"
            )
        unexpected = [
            path
            for path in output_dir.iterdir()
            if path.name != "campaign_manifest.json.tmp"
        ]
        if unexpected:
            raise ValueError(
                f"Refusing unregistered non-empty output directory: {output_dir}"
            )
        _write_json_atomic(manifest_path, manifest)
    if not smoke:
        shard_plan_path = output_dir / "shard_plan.csv"
        if shard_plan_path.is_file():
            actual = _read_csv(shard_plan_path)
            if len(actual) != len(design["shards"]) or {
                str(row.get("shard_id") or "") for row in actual
            } != {str(row["shard_id"]) for row in design["shards"]}:
                raise ValueError(
                    "Existing shard plan differs from signed campaign design"
                )
        elif require_existing:
            raise FileNotFoundError("Signed campaign shard_plan.csv is missing")
        else:
            _write_csv_atomic(shard_plan_path, design["shards"])
    return manifest, points, lanes


def _point_by_id(points: Sequence[Mapping[str, Any]], point_id: str) -> dict[str, Any]:
    matches = [
        dict(point) for point in points if point["operating_point_id"] == point_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Operating point not found exactly once: {point_id}")
    return matches[0]


def _lane_matches(row: Mapping[str, Any], lane: Lane) -> bool:
    return (
        str(row.get("src_node_id") or "") == lane.supplier_id
        and str(row.get("item_id") or "") == lane.item_id
        and str(row.get("dst_node_id") or "") == lane.dst_node_id
        and str(row.get("edge_id") or "") == lane.edge_id
    )


def select_unique_reference_shipment(
    rows: Iterable[Mapping[str, Any]],
    *,
    lane: Lane,
    days: int | None = SIMULATION_DAYS,
    state_evaluation_days: int = STATE_EVALUATION_DAYS,
    impact_window_days: int = IMPACT_WINDOW_DAYS,
    max_delay_days: int = TARGET_SELECTION_MAX_DELAY_DAYS,
    minimum_recovery_observation_days: int = MIN_RECOVERY_OBSERVATION_DAYS,
    forced_decision_day: int | None = None,
    target_window_days: int = 1,
    state_match_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Select and aggregate a positive lane disruption window without horizon bias."""

    if (
        state_evaluation_days <= 0
        or target_window_days <= 0
        or target_window_days > state_evaluation_days
        or (days is not None and (days <= 0 or state_evaluation_days > days))
        or impact_window_days <= max_delay_days
        or max_delay_days < 0
        or minimum_recovery_observation_days < 1
    ):
        raise ValueError("Invalid target observability window contract")
    lane_rows: list[dict[str, Any]] = []
    for source in rows:
        if not _lane_matches(source, lane):
            continue
        pulled = _as_float(source.get("pulled_qty"), 0.0)
        shipped = _as_float(source.get("shipped_qty"), 0.0)
        decision_day = _as_int(source.get("risk_decision_day"), -1)
        arrival_day = _as_int(source.get("arrival_day"), -1)
        shipment_id = str(source.get("shipment_id") or "").strip()
        if (
            pulled > 1e-12
            and shipped > 1e-12
            and shipment_id
            and 0 <= decision_day < state_evaluation_days
            and arrival_day >= 0
        ):
            lane_rows.append(dict(source))
    by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in lane_rows:
        by_day[_as_int(row.get("risk_decision_day"))].append(row)
    lane_shipped_qty = sum(_as_float(row.get("shipped_qty"), 0.0) for row in lane_rows)
    if not by_day and forced_decision_day is None:
        return {
            "target_status": "not_applicable_no_positive_reference_flow",
            "candidate_window_count": 0,
            "candidate_day_count": 0,
            "target_shipment_count": 0,
            "target_shipment_ids": "",
            "baseline_lane_shipped_qty_state_window": lane_shipped_qty,
            "selection_mode": "not_applicable_no_positive_flow",
            "selection_rule": "positive_lane_dispatch_required_in_J0_J719",
            "reference_kind": TARGET_REFERENCE_KIND,
            "reason": "No positive baseline shipment exists in the state window.",
        }
    candidate_groups: dict[int, list[dict[str, Any]]] = {}
    for start in range(0, state_evaluation_days - target_window_days + 1):
        group = [
            row
            for day in range(start, start + target_window_days)
            for row in by_day.get(day, [])
        ]
        if group:
            candidate_groups[start] = group
    if forced_decision_day is not None and forced_decision_day not in candidate_groups:
        selected_end = forced_decision_day + target_window_days - 1
        impact_end = forced_decision_day + impact_window_days - 1
        required_days = max(state_evaluation_days, impact_end + 1)
        zero_flow = {
            "target_status": "identified_registered_window_no_positive_flow",
            "candidate_window_count": len(candidate_groups),
            "candidate_day_count": len(by_day),
            "target_shipment_id": "",
            "target_shipment_count": 0,
            "target_shipment_ids": "",
            "target_decision_day": forced_decision_day,
            "target_window_start_day": forced_decision_day,
            "target_window_end_day": selected_end,
            "target_window_days": target_window_days,
            "target_active_decision_day_count": 0,
            "target_active_decision_days": "",
            "target_release_day": "",
            "target_arrival_day": "",
            "target_release_days": "",
            "target_arrival_days": "",
            "target_planned_qty": 0.0,
            "target_expected_delivered_qty": 0.0,
            "target_nominal_reliability": 0.0,
            "target_lead_days": "",
            "target_uom": "no_flow",
            "baseline_lane_shipped_qty_state_window": lane_shipped_qty,
            "target_qty_share_of_lane_state_window": 0.0,
            "target_group_qty_percentile_lane_state_window": 0.0,
            "target_exposure_concentration_flag": "no_positive_flow_in_fixed_window",
            "impact_window_start_day": forced_decision_day,
            "impact_window_end_day": impact_end,
            "impact_window_days": impact_window_days,
            "impact_window_fully_observed": None if days is None else impact_end < days,
            "target_latest_baseline_arrival_day": -1,
            "target_latest_stressed_arrival_day": -1,
            "observable_days_after_target_decision": (
                "" if days is None else days - forced_decision_day
            ),
            "observable_days_after_first_expected_arrival": "",
            "recovery_observation_days_after_latest_stressed_arrival": 0,
            "recovery_observation_days_within_impact_window": 0,
            "recovery_fully_observed_within_360": False,
            "minimum_recovery_observation_days_required": minimum_recovery_observation_days,
            "causal_window_start_day": forced_decision_day,
            "causal_window_end_day": impact_end,
            "causal_window_days": impact_window_days,
            "causal_window_defined": False,
            "causal_window_fully_observed": None if days is None else impact_end < days,
            "required_simulation_days": required_days,
            "target_selected_independently_by_operating_point": False,
            "target_selection_basis": "fixed_independent_design_window_no_flow",
            "target_shipments": [],
            "eligible_candidate_day_count": "",
            "ineligible_candidate_day_count": "",
            "unique_candidate_day_count": 0,
            "selection_mode": "registered_cross_state_42d_window_no_flow",
            "selection_rule": "fixed_window_selected_on_independent_design_seed",
            "reference_kind": TARGET_REFERENCE_KIND,
            "reason": "No positive flow occurred in the fixed 42-day window for this repetition.",
        }
        if state_match_metadata:
            zero_flow.update(dict(state_match_metadata))
        return zero_flow
    candidate_starts = (
        [forced_decision_day]
        if forced_decision_day is not None
        else list(candidate_groups)
    )
    selected_start = min(
        candidate_starts,
        key=lambda start: (
            -sum(
                _as_float(row.get("shipped_qty"), 0.0)
                for row in candidate_groups[start]
            ),
            start,
            "|".join(
                sorted(
                    str(row.get("shipment_id") or "") for row in candidate_groups[start]
                )
            ),
        ),
    )
    selected_end = selected_start + target_window_days - 1
    selected_rows = sorted(
        candidate_groups[selected_start],
        key=lambda row: (
            _as_int(row.get("risk_decision_day"), -1),
            str(row.get("shipment_id") or ""),
        ),
    )
    shipment_ids = [str(row["shipment_id"]) for row in selected_rows]
    pulled_qty = sum(_as_float(row.get("pulled_qty"), 0.0) for row in selected_rows)
    shipped_qty = sum(_as_float(row.get("shipped_qty"), 0.0) for row in selected_rows)
    release_days = [_as_int(row.get("day")) for row in selected_rows]
    arrival_days = [_as_int(row.get("arrival_day")) for row in selected_rows]
    active_days = sorted(
        {_as_int(row.get("risk_decision_day")) for row in selected_rows}
    )
    impact_window_start = selected_start
    impact_window_end = selected_start + impact_window_days - 1
    latest_baseline_arrival = max(arrival_days)
    latest_stressed_arrival = latest_baseline_arrival + max_delay_days
    causal_window_start = min(arrival_days)
    causal_window_end = latest_stressed_arrival + minimum_recovery_observation_days - 1
    required_simulation_days = max(impact_window_end, causal_window_end) + 1
    selected_fully_observable = days is None or required_simulation_days <= days
    recovery_within_impact_window = max(
        0, impact_window_end - latest_stressed_arrival + 1
    )
    window_quantities = [
        sum(_as_float(row.get("shipped_qty"), 0.0) for row in group)
        for group in candidate_groups.values()
    ]
    target_group_percentile = sum(
        value <= shipped_qty + TARGET_QUANTITY_TOLERANCE for value in window_quantities
    ) / len(window_quantities)
    target_status = (
        "identified_unique_reference_shipment"
        if len(selected_rows) == 1
        else (
            "identified_reference_lane_day_shipment_group"
            if target_window_days == 1
            else "identified_reference_lane_window_shipment_group"
        )
    )
    selection_mode = (
        "registered_cross_state_42d_window"
        if forced_decision_day is not None
        and target_window_days == INCIDENT_DISRUPTION_DAYS
        else (
            "single_shipment_day"
            if len(selected_rows) == 1 and target_window_days == 1
            else "aggregated_lane_window"
        )
    )
    result: dict[str, Any] = {
        "target_status": (
            target_status
            if selected_fully_observable
            else "not_applicable_selected_reference_horizon_censored"
        ),
        "target_shipment_id": "|".join(shipment_ids),
        "target_shipment_count": len(selected_rows),
        "target_shipment_ids": "|".join(shipment_ids),
        "target_decision_day": selected_start,
        "target_window_start_day": selected_start,
        "target_window_end_day": selected_end,
        "target_window_days": target_window_days,
        "target_active_decision_day_count": len(active_days),
        "target_active_decision_days": "|".join(str(day) for day in active_days),
        "target_release_day": min(release_days),
        "target_arrival_day": min(arrival_days),
        "target_release_days": "|".join(str(value) for value in release_days),
        "target_arrival_days": "|".join(str(value) for value in arrival_days),
        "target_planned_qty": pulled_qty,
        "target_expected_delivered_qty": shipped_qty,
        "target_nominal_reliability": shipped_qty / pulled_qty
        if pulled_qty > 1e-12
        else 0.0,
        "target_lead_days": "|".join(
            str(_as_int(row.get("lead_days"))) for row in selected_rows
        ),
        "target_uom": str(selected_rows[0].get("uom") or ""),
        "baseline_lane_shipped_qty_state_window": lane_shipped_qty,
        "target_qty_share_of_lane_state_window": (
            shipped_qty / lane_shipped_qty if lane_shipped_qty > 1e-12 else 0.0
        ),
        "target_group_qty_percentile_lane_state_window": target_group_percentile,
        "target_exposure_concentration_flag": (
            "selected_window_carries_all_positive_lane_flow"
            if math.isclose(shipped_qty, lane_shipped_qty, rel_tol=0.0, abs_tol=1e-9)
            else "selected_window_is_part_of_lane_flow"
        ),
        "impact_window_start_day": impact_window_start,
        "impact_window_end_day": impact_window_end,
        "impact_window_days": impact_window_days,
        "impact_window_fully_observed": None
        if days is None
        else impact_window_end < days,
        "target_latest_baseline_arrival_day": latest_baseline_arrival,
        "target_latest_stressed_arrival_day": latest_stressed_arrival,
        "observable_days_after_target_decision": ""
        if days is None
        else days - selected_start,
        "observable_days_after_first_expected_arrival": ""
        if days is None
        else days - min(arrival_days),
        "recovery_observation_days_after_latest_stressed_arrival": (
            "" if days is None else max(0, days - latest_stressed_arrival)
        ),
        "recovery_observation_days_within_impact_window": recovery_within_impact_window,
        "recovery_fully_observed_within_360": (
            recovery_within_impact_window >= minimum_recovery_observation_days
        ),
        "minimum_recovery_observation_days_required": minimum_recovery_observation_days,
        "causal_window_start_day": causal_window_start,
        "causal_window_end_day": causal_window_end,
        "causal_window_days": causal_window_end - causal_window_start + 1,
        "causal_window_defined": True,
        "causal_window_fully_observed": (
            None
            if days is None
            else causal_window_start >= 0 and causal_window_end < days
        ),
        "required_simulation_days": required_simulation_days,
        "target_selected_independently_by_operating_point": forced_decision_day is None,
        "target_selection_basis": (
            "global_cross_state_discovery_registered_window"
            if forced_decision_day is not None
            else "within_state_largest_lane_window_quantity"
        ),
        "target_shipments": [
            {
                "shipment_id": str(row["shipment_id"]),
                "risk_decision_day": _as_int(row.get("risk_decision_day")),
                "release_day": _as_int(row.get("day")),
                "arrival_day": _as_int(row.get("arrival_day")),
                "pulled_qty": _as_float(row.get("pulled_qty"), 0.0),
                "expected_delivered_qty": _as_float(row.get("shipped_qty"), 0.0),
                "nominal_reliability": _as_float(row.get("reliability"), 1.0),
                "lead_days": _as_int(row.get("lead_days")),
                "uom": str(row.get("uom") or ""),
            }
            for row in selected_rows
        ],
        "candidate_window_count": len(candidate_groups),
        "candidate_day_count": len(by_day),
        "eligible_candidate_day_count": sum(
            1
            for start, group in candidate_groups.items()
            if days is None
            or max(
                start + impact_window_days - 1,
                max(_as_int(row.get("arrival_day"), -1) for row in group)
                + max_delay_days
                + minimum_recovery_observation_days
                - 1,
            )
            < days
        ),
        "ineligible_candidate_day_count": (
            0
            if days is None
            else len(candidate_groups)
            - sum(
                1
                for start, group in candidate_groups.items()
                if max(
                    start + impact_window_days - 1,
                    max(_as_int(row.get("arrival_day"), -1) for row in group)
                    + max_delay_days
                    + minimum_recovery_observation_days
                    - 1,
                )
                < days
            )
        ),
        "unique_candidate_day_count": sum(
            len(group) == 1 for group in candidate_groups.values()
        ),
        "selection_mode": (
            selection_mode
            if selected_fully_observable
            else "not_applicable_selected_target_requires_longer_horizon"
        ),
        "selection_rule": (
            "registered_cross_state_window_or_within_state_max_quantity; selection_before_"
            "adaptive_horizon; aggregate_every_positive_shipment_in_window"
        ),
        "reference_kind": TARGET_REFERENCE_KIND,
        "reason": (
            ""
            if selected_fully_observable
            else (
                "The horizon-independent selected target requires "
                f"{required_simulation_days} simulated days; configured horizon is {days}. "
                "The preflight must fail rather than substitute a faster shipment."
            )
        ),
    }
    if state_match_metadata:
        result.update(dict(state_match_metadata))
    return result


def _lane_day_quantity_map(
    rows: Iterable[Mapping[str, Any]], *, lane: Lane
) -> dict[int, float]:
    quantities: dict[int, float] = defaultdict(float)
    for row in rows:
        if not _lane_matches(row, lane):
            continue
        day = _as_int(row.get("risk_decision_day"), -1)
        pulled = _as_float(row.get("pulled_qty"), 0.0)
        shipped = _as_float(row.get("shipped_qty"), 0.0)
        if (
            0 <= day < STATE_EVALUATION_DAYS
            and pulled > 1e-12
            and shipped > 1e-12
            and str(row.get("shipment_id") or "").strip()
        ):
            quantities[day] += shipped
    return dict(quantities)


def build_cross_state_target_registry(
    *,
    manifest: Mapping[str, Any],
    points: Sequence[Mapping[str, Any]],
    lanes: Sequence[Lane],
    shipment_rows_by_state_seed: Mapping[tuple[str, int], Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Freeze 42-day lane windows on the design seed, then measure holdout seeds."""

    point_ids = [str(point["operating_point_id"]) for point in points]
    if point_ids != list(OPERATING_POINT_IDS):
        raise ValueError("Target discovery requires the three ordered operating points")
    discovery_seeds = (TARGET_DESIGN_SEED, *SEEDS)
    expected_keys = {
        (point_id, seed) for point_id in OPERATING_POINT_IDS for seed in discovery_seeds
    }
    if set(shipment_rows_by_state_seed) != expected_keys:
        raise ValueError("Target discovery state/seed matrix is incomplete")
    last_start = STATE_EVALUATION_DAYS - INCIDENT_DISRUPTION_DAYS

    def rolling_quantities(point_id: str, seed: int, lane: Lane) -> dict[int, float]:
        daily = _lane_day_quantity_map(
            shipment_rows_by_state_seed[(point_id, seed)], lane=lane
        )
        return {
            start: sum(
                daily.get(day, 0.0)
                for day in range(start, start + INCIDENT_DISRUPTION_DAYS)
            )
            for start in range(last_start + 1)
        }

    targets: list[dict[str, Any]] = []
    lane_contracts: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    for lane in lanes:
        design = {
            point_id: rolling_quantities(point_id, TARGET_DESIGN_SEED, lane)
            for point_id in OPERATING_POINT_IDS
        }
        positive_common = [
            start
            for start in range(last_start + 1)
            if all(design[point_id][start] > 1e-12 for point_id in OPERATING_POINT_IDS)
        ]
        comparable = [
            start
            for start in positive_common
            if max(design[point_id][start] for point_id in OPERATING_POINT_IDS)
            / min(design[point_id][start] for point_id in OPERATING_POINT_IDS)
            <= STATE_MATCH_MAX_QUANTITY_RATIO + 1e-12
        ]

        def preferred_key(start: int) -> tuple[float, float, int]:
            values = [design[point_id][start] for point_id in OPERATING_POINT_IDS]
            ratio = max(values) / min(values) if min(values) > 1e-12 else math.inf
            return (-min(values), ratio, start)

        if comparable:
            fixed_start = min(comparable, key=preferred_key)
            design_status = "calibration_design_comparable_42d_window"
        elif positive_common:
            fixed_start = min(
                positive_common,
                key=lambda start: (
                    max(design[point_id][start] for point_id in OPERATING_POINT_IDS)
                    / min(design[point_id][start] for point_id in OPERATING_POINT_IDS),
                    -min(design[point_id][start] for point_id in OPERATING_POINT_IDS),
                    start,
                ),
            )
            design_status = "calibration_design_best_ratio_above_limit"
        else:
            fixed_start = min(
                range(last_start + 1),
                key=lambda start: (
                    -min(design[point_id][start] for point_id in OPERATING_POINT_IDS),
                    -sum(design[point_id][start] for point_id in OPERATING_POINT_IDS),
                    start,
                ),
            )
            design_status = "calibration_design_no_common_positive_window"
        design_quantities = {
            point_id: design[point_id][fixed_start] for point_id in OPERATING_POINT_IDS
        }
        design_ratio = (
            max(design_quantities.values()) / min(design_quantities.values())
            if min(design_quantities.values()) > 1e-12
            else math.inf
        )
        per_seed: dict[int, dict[str, Any]] = {}
        comparable_seed_count = 0
        for seed in SEEDS:
            quantities = {
                point_id: rolling_quantities(point_id, seed, lane)[fixed_start]
                for point_id in OPERATING_POINT_IDS
            }
            positive_all = min(quantities.values()) > 1e-12
            ratio = (
                max(quantities.values()) / min(quantities.values())
                if positive_all
                else math.inf
            )
            comparable_seed = positive_all and ratio <= (
                STATE_MATCH_MAX_QUANTITY_RATIO + 1e-12
            )
            comparable_seed_count += int(comparable_seed)
            per_seed[seed] = {
                "quantities": quantities,
                "positive_all_states": positive_all,
                "quantity_ratio": ratio,
                "comparable": comparable_seed,
            }
        state_comparison_valid = comparable_seed_count >= 24
        lane_contracts.append(
            {
                "lane_id": lane.lane_id,
                "design_seed": TARGET_DESIGN_SEED,
                "design_status": design_status,
                "fixed_window_start_day": fixed_start,
                "fixed_window_end_day": fixed_start + INCIDENT_DISRUPTION_DAYS - 1,
                "design_quantities": design_quantities,
                "design_quantity_ratio": design_ratio
                if math.isfinite(design_ratio)
                else "",
                "comparable_campaign_seed_count": comparable_seed_count,
                "required_comparable_seed_count": 24,
                "state_comparison_valid": state_comparison_valid,
            }
        )
        for seed in SEEDS:
            seed_contract = per_seed[seed]
            for point_id in OPERATING_POINT_IDS:
                state_rolling = rolling_quantities(point_id, seed, lane)
                state_max_start = min(
                    state_rolling,
                    key=lambda start: (-state_rolling[start], start),
                )
                metadata = {
                    "cross_state_match_status": design_status,
                    "cross_state_common_day_found": min(design_quantities.values())
                    > 1e-12,
                    "cross_state_common_window_found": min(design_quantities.values())
                    > 1e-12,
                    "cross_state_quantity_ratio": (
                        seed_contract["quantity_ratio"]
                        if math.isfinite(seed_contract["quantity_ratio"])
                        else ""
                    ),
                    "cross_state_match_threshold_ratio": STATE_MATCH_MAX_QUANTITY_RATIO,
                    "state_comparison_valid": state_comparison_valid,
                    "seed_cross_state_exposure_comparable": seed_contract["comparable"],
                    "comparable_campaign_seed_count": comparable_seed_count,
                    "required_comparable_seed_count": 24,
                    "state_exposure_max_window_start_day": state_max_start,
                    # Deprecated compatibility alias; this is a window start,
                    # not the decision day of one shipment.
                    "state_exposure_max_decision_day": state_max_start,
                    "state_exposure_max_group_qty": state_rolling[state_max_start],
                    "cross_state_matched_min_group_qty": min(
                        seed_contract["quantities"].values()
                    ),
                    "cross_state_matched_max_group_qty": max(
                        seed_contract["quantities"].values()
                    ),
                    "cross_state_matched_quantities_json": json.dumps(
                        seed_contract["quantities"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "target_selected_independently_by_operating_point": False,
                }
                target = select_unique_reference_shipment(
                    shipment_rows_by_state_seed[(point_id, seed)],
                    lane=lane,
                    days=None,
                    forced_decision_day=fixed_start,
                    target_window_days=INCIDENT_DISRUPTION_DAYS,
                    state_match_metadata=metadata,
                )
                targets.append(
                    {
                        "operating_point_id": point_id,
                        "seed": seed,
                        "lane_id": lane.lane_id,
                        **target,
                    }
                )
                exposure_rows.append(
                    {
                        "operating_point_id": point_id,
                        "seed": seed,
                        "lane_id": lane.lane_id,
                        "fixed_window_start_day": fixed_start,
                        "fixed_window_end_day": fixed_start
                        + INCIDENT_DISRUPTION_DAYS
                        - 1,
                        "fixed_window_quantity": seed_contract["quantities"][point_id],
                        "state_max_window_start_day": state_max_start,
                        "state_max_window_quantity": state_rolling[state_max_start],
                        "seed_cross_state_exposure_comparable": seed_contract[
                            "comparable"
                        ],
                    }
                )
    exposure_gate_failures: list[dict[str, Any]] = []
    for contract in lane_contracts:
        reasons: list[str] = []
        if contract["design_status"] != "calibration_design_comparable_42d_window":
            reasons.append("no_common_design_window_with_quantity_ratio_at_most_1.5")
        if int(contract["comparable_campaign_seed_count"]) < 24:
            reasons.append("fewer_than_24_of_30_holdout_seeds_have_comparable_exposure")
        if reasons:
            exposure_gate_failures.append(
                {"lane_id": contract["lane_id"], "reasons": reasons}
            )
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.target_registry.v4",
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "design_seed": TARGET_DESIGN_SEED,
        "campaign_seeds": list(SEEDS),
        "discovery_days": DISCOVERY_DAYS,
        "disruption_window_days": INCIDENT_DISRUPTION_DAYS,
        "selection_contract": (
            "lane_specific_fixed_42d_window_selected_only_on_design_seed_340281; "
            "same_dates_for_all_30_campaign_seeds_and_three_states"
        ),
        "state_match_max_quantity_ratio": STATE_MATCH_MAX_QUANTITY_RATIO,
        "required_comparable_seed_count": 24,
        "campaign_exposure_gate_contract": (
            "all_18_lanes_require_a_common_positive_design_window_with_quantity_"
            "ratio_at_most_1.5_and_at_least_24_of_30_holdout_seeds_comparable"
        ),
        "all_lane_design_windows_comparable": all(
            contract["design_status"] == "calibration_design_comparable_42d_window"
            for contract in lane_contracts
        ),
        "all_lane_holdout_exposures_comparable": all(
            int(contract["comparable_campaign_seed_count"]) >= 24
            for contract in lane_contracts
        ),
        "campaign_exposure_gate_passed": not exposure_gate_failures,
        "exposure_gate_failures": exposure_gate_failures,
        "states": list(OPERATING_POINT_IDS),
        "seeds": list(SEEDS),
        "lanes": [lane.lane_id for lane in lanes],
        "lane_contracts": lane_contracts,
        "targets": targets,
        "state_exposure_descriptive": exposure_rows,
    }
    return {**unsigned, "registry_signature": _stable_sha256(unsigned)}


def _target_with_lane_fields(
    target: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    shard_id: str,
    point: Mapping[str, Any],
    seed: int,
    lane: Lane,
    simulation_days: int,
) -> dict[str, Any]:
    return {
        "campaign_signature": manifest["campaign_signature"],
        "shard_id": shard_id,
        "shard_index": manifest.get("active_shard_index", ""),
        "shard_count": manifest.get("active_shard_count", ""),
        "operating_point_id": point["operating_point_id"],
        "operating_point_service_pct": point["operating_point_service_pct"],
        "simulation_days": simulation_days,
        "state_evaluation_days": STATE_EVALUATION_DAYS,
        "seed": seed,
        "lane_id": lane.lane_id,
        "supplier_id": lane.supplier_id,
        "item_id": lane.item_id,
        "dst_node_id": lane.dst_node_id,
        "edge_id": lane.edge_id,
        "target_product_id": lane.target_product_id,
        **dict(target),
        "interpretation_fr": (
            "Fenêtre calendaire fixe de 42 jours (six semaines) choisie sur la seule graine de "
            "conception 340281, puis appliquée aux trois états et aux 30 répétitions. "
            "Le stress couvre tous les envois réellement décidés sur cette voie "
            "pendant la fenêtre; la replanification peut donc modifier ensuite les "
            "identifiants et les quantités. La fenêtre métier de 360 jours est fixe "
            "et la fenêtre causale observe 90 jours en comptant le jour de la "
            "dernière arrivée réellement affectée (puis 89 jours complets). Il "
            "s'agit d'une hypothèse simulée, pas "
            "d'un incident fournisseur observé."
        ),
    }


def build_risk_row(
    *,
    point_id: str,
    seed: int,
    lane: Lane,
    mechanism: Mechanism,
    target: Mapping[str, Any],
) -> dict[str, Any]:
    if not str(target.get("target_status") or "").startswith("identified_"):
        raise ValueError(
            "Cannot build a risk event without an identified lane/window target"
        )
    if mechanism.risk_type in FORBIDDEN_INCIDENT_RISK_TYPES:
        raise ValueError(f"Forbidden V2 risk type: {mechanism.risk_type}")
    day = int(target["target_window_start_day"])
    end_day = int(target["target_window_end_day"])
    event_id = (
        f"v2__{point_id}__seed_{seed}__{lane.lane_id}__{mechanism.key}"
        f"__window_{day}_{end_day}"
    )
    return {
        "event_id": event_id,
        "risk_type": mechanism.risk_type,
        "supplier_id": lane.supplier_id,
        "item_id": lane.item_id,
        "dst_node_id": lane.dst_node_id,
        "edge_id": lane.edge_id,
        "start_day": day,
        "end_day": end_day,
        "multiplier": mechanism.value,
        "notes": (
            f"Hypothèse conditionnelle de stress fournisseur sur la voie du jour "
            f"{day} au jour {end_day}. Tous les envois réellement décidés pendant "
            "cette fenêtre sont affectés; leurs identifiants et quantités peuvent "
            "diverger de la référence par replanification. Aucun changement de "
            "capacité, stock, disponibilité ou qualité."
        ),
    }


def _case_key(
    *,
    point_id: str,
    seed: int,
    stage: str,
    lane_id: str = "",
    mechanism: str = "",
) -> str:
    if stage == "baseline":
        return f"{point_id}__baseline__seed_{seed}"
    return f"{point_id}__{lane_id}__{mechanism}__seed_{seed}"


def _case_signature(
    *,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    seed: int,
    stage: str,
    lane: Lane | None = None,
    mechanism: Mechanism | None = None,
    target: Mapping[str, Any] | None = None,
    simulation_days: int | None = None,
    adaptive_contract_signature: str = "",
) -> str:
    payload: dict[str, Any] = {
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "operating_point_id": point["operating_point_id"],
        "graph_sha256": point["graph_sha256"],
        "supplier_floors_sha256": point["supplier_floors_sha256"],
        "factory_capacities_sha256": point["factory_capacities_sha256"],
        "seed": int(seed),
        "stage": stage,
        "simulation_days": simulation_days,
        "target_registry_signature": manifest.get("target_registry_signature", ""),
        "adaptive_contract_signature": adaptive_contract_signature,
    }
    if stage == "incident":
        if lane is None or mechanism is None or target is None:
            raise ValueError("Incident signature requires lane, mechanism and target")
        payload.update(
            {
                "lane": asdict(lane),
                "mechanism": asdict(mechanism),
                "target": {
                    key: target.get(key)
                    for key in (
                        "target_status",
                        "target_shipment_id",
                        "target_shipment_count",
                        "target_shipment_ids",
                        "target_decision_day",
                        "target_window_start_day",
                        "target_window_end_day",
                        "target_window_days",
                        "target_active_decision_day_count",
                        "target_active_decision_days",
                        "target_release_day",
                        "target_arrival_day",
                        "target_planned_qty",
                        "target_expected_delivered_qty",
                        "target_uom",
                        "baseline_lane_shipped_qty_state_window",
                        "target_qty_share_of_lane_state_window",
                        "target_group_qty_percentile_lane_state_window",
                        "target_exposure_concentration_flag",
                        "cross_state_match_status",
                        "cross_state_quantity_ratio",
                        "state_comparison_valid",
                        "impact_window_start_day",
                        "impact_window_end_day",
                        "impact_window_days",
                        "target_latest_baseline_arrival_day",
                        "target_latest_stressed_arrival_day",
                        "recovery_observation_days_after_latest_stressed_arrival",
                        "recovery_observation_days_within_impact_window",
                        "recovery_fully_observed_within_360",
                        "causal_window_start_day",
                        "causal_window_end_day",
                        "causal_window_days",
                        "required_simulation_days",
                        "baseline_pre_incident_shipment_trace_sha256",
                        "target_shipments",
                    )
                },
            }
        )
    return _stable_sha256(payload)


def _evidence_signature(evidence: Mapping[str, Any]) -> str:
    unsigned = dict(evidence)
    unsigned.pop("evidence_signature", None)
    return _stable_sha256(unsigned)


def _validate_evidence(
    evidence: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    case_key: str,
    case_signature: str,
) -> None:
    errors: list[str] = []
    if evidence.get("schema_version") != CASE_SCHEMA_VERSION:
        errors.append("schema_version")
    if evidence.get("campaign_signature") != manifest.get("campaign_signature"):
        errors.append("campaign_signature")
    if evidence.get("engine_sha256") != manifest.get("engine_sha256"):
        errors.append("engine_sha256")
    if evidence.get("case_key") != case_key:
        errors.append("case_key")
    if evidence.get("case_signature") != case_signature:
        errors.append("case_signature")
    if not evidence.get("evidence_signature") or evidence.get(
        "evidence_signature"
    ) != _evidence_signature(evidence):
        errors.append("evidence_signature")
    if evidence.get("quality_branch_included") is not False:
        errors.append("quality_branch_included")
    if evidence.get("availability_incident_included") is not False:
        errors.append("availability_incident_included")
    if evidence.get("supplier_state_dependent_risks_enabled") is not False:
        errors.append("supplier_state_dependent_risks_enabled")
    if str(evidence.get("status") or "") not in {
        "valid",
        "valid_no_exposure",
        "not_applicable",
        "invalid",
    }:
        errors.append("status")
    if errors:
        raise ValueError(f"Evidence fails closed for {case_key}: " + ", ".join(errors))


def _evidence_path(shard_dir: Path, case_key: str) -> Path:
    return shard_dir / "case_evidence" / f"{case_key}.json"


def _external_evidence_candidates(
    reuse_roots: Sequence[Path], case_key: str
) -> list[Path]:
    candidates: list[Path] = []
    filename = f"{case_key}.json"
    for root in reuse_roots:
        resolved = root.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Reuse evidence root does not exist: {resolved}")
        if resolved.is_file():
            if resolved.name == filename:
                candidates.append(resolved)
            continue
        candidates.extend(resolved.glob(f"**/case_evidence/{filename}"))
    return sorted(set(path.resolve() for path in candidates))


def _load_or_reuse_evidence(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    case_key: str,
    case_signature: str,
    reuse_roots: Sequence[Path],
) -> dict[str, Any] | None:
    local = _evidence_path(shard_dir, case_key)
    if local.is_file():
        evidence = _read_json(local)
        _validate_evidence(
            evidence,
            manifest=manifest,
            case_key=case_key,
            case_signature=case_signature,
        )
        return evidence
    accepted: list[tuple[Path, dict[str, Any]]] = []
    rejected: list[tuple[Path, str]] = []
    for candidate in _external_evidence_candidates(reuse_roots, case_key):
        try:
            evidence = _read_json(candidate)
            _validate_evidence(
                evidence,
                manifest=manifest,
                case_key=case_key,
                case_signature=case_signature,
            )
            accepted.append((candidate, evidence))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rejected.append((candidate, str(exc)))
    if len(accepted) > 1:
        signatures = {item[1].get("evidence_signature") for item in accepted}
        if len(signatures) != 1:
            raise ValueError(f"Conflicting reusable evidence for {case_key}")
    if accepted:
        source, evidence = accepted[0]
        reused = dict(evidence)
        reused["reuse_provenance"] = {
            "source_evidence_path": str(source),
            "source_evidence_sha256": _sha256_file(source),
            "validated_engine_sha256": manifest["engine_sha256"],
            "validated_campaign_signature": manifest["campaign_signature"],
            "reused_at_utc": utc_now(),
        }
        reused["evidence_signature"] = _evidence_signature(reused)
        _write_json_atomic(local, reused)
        return reused
    # Rejection is explicit in a small audit, but non-matching historical
    # evidence is never silently treated as compatible.
    if rejected:
        _write_json_atomic(
            shard_dir / "reuse_rejections" / f"{case_key}.json",
            {
                "case_key": case_key,
                "rejections": [
                    {"source": str(source), "reason": reason}
                    for source, reason in rejected
                ],
                "rejected_at_utc": utc_now(),
            },
        )
    return None


def _signed_document(
    payload: Mapping[str, Any], *, signature_field: str
) -> dict[str, Any]:
    signed = dict(payload)
    signed.pop(signature_field, None)
    signed[signature_field] = _stable_sha256(signed)
    return signed


def _attempt_inventory(attempt_dir: Path) -> dict[str, Any]:
    """Return a bounded metadata-only inventory of one failed engine attempt."""

    entries: list[dict[str, Any]] = []
    file_count = 0
    total_bytes = 0
    if attempt_dir.exists():
        paths = sorted(
            attempt_dir.rglob("*"),
            key=lambda path: path.relative_to(attempt_dir).as_posix(),
        )
        for path in paths:
            if path.is_symlink() or not path.is_file():
                continue
            try:
                size = int(path.stat().st_size)
            except OSError:
                continue
            file_count += 1
            total_bytes += size
            if len(entries) < FAILED_ATTEMPT_INVENTORY_LIMIT:
                entries.append(
                    {
                        "relative_path": path.relative_to(attempt_dir).as_posix(),
                        "bytes": size,
                    }
                )
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "entries": entries,
        "entry_limit": FAILED_ATTEMPT_INVENTORY_LIMIT,
        "truncated": file_count > len(entries),
    }


def _bounded_log_evidence(log_path: Path) -> dict[str, Any]:
    if not log_path.is_file():
        return {
            "present": False,
            "bytes": 0,
            "sha256": "",
            "tail_utf8": "",
            "tail_byte_limit": FAILED_ATTEMPT_LOG_TAIL_BYTES,
        }
    size = int(log_path.stat().st_size)
    with log_path.open("rb") as stream:
        stream.seek(max(0, size - FAILED_ATTEMPT_LOG_TAIL_BYTES))
        tail = stream.read(FAILED_ATTEMPT_LOG_TAIL_BYTES)
    return {
        "present": True,
        "bytes": size,
        "sha256": _sha256_file(log_path),
        "tail_utf8": tail.decode("utf-8", errors="replace"),
        "tail_byte_limit": FAILED_ATTEMPT_LOG_TAIL_BYTES,
    }


def _failed_attempt_diagnostic_payload(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    case_key: str,
    attempt: Path,
    seed: int,
    simulation_days: int,
    risk_csv: Path | None,
    command: Sequence[str],
    failure_kind: str,
    failure_detail: str,
    return_code: int | None,
) -> dict[str, Any]:
    attempts_root = (shard_dir / "_attempts").resolve()
    resolved_attempt = attempt.resolve()
    if resolved_attempt.parent != attempts_root or not attempt.name.startswith(
        f"{case_key}__"
    ):
        raise RuntimeError(f"Unsafe failed-attempt diagnostic target: {attempt}")
    summary_path = attempt / "summaries" / "first_simulation_summary.json"
    summary_evidence: dict[str, Any] = {
        "present": summary_path.is_file(),
        "sha256": "",
        "sim_days": "",
        "input_sha256": "",
        "read_error": "",
    }
    if summary_path.is_file():
        summary_evidence["sha256"] = _sha256_file(summary_path)
        try:
            summary = _read_json(summary_path)
            summary_evidence["sim_days"] = summary.get("sim_days", "")
            summary_evidence["input_sha256"] = summary.get("input_sha256", "")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            summary_evidence["read_error"] = f"{type(exc).__name__}: {exc}"
    inventory = _attempt_inventory(attempt)
    return {
        "schema_version": FAILED_ATTEMPT_DIAGNOSTIC_SCHEMA_VERSION,
        "campaign_signature": manifest.get("campaign_signature", ""),
        "engine_sha256": manifest.get("engine_sha256", ""),
        "operating_point_id": point.get("operating_point_id", ""),
        "case_key": case_key,
        "attempt_name": attempt.name,
        "attempt_dir": str(resolved_attempt),
        "seed": int(seed),
        "simulation_days": int(simulation_days),
        "risk_csv_sha256": (
            _sha256_file(risk_csv)
            if risk_csv is not None and risk_csv.is_file()
            else ""
        ),
        "command_sha256": _stable_sha256(list(command)),
        "failure_kind": failure_kind,
        "failure_detail": failure_detail,
        "return_code": "" if return_code is None else int(return_code),
        "inventory_before_cleanup": inventory,
        "engine_log": _bounded_log_evidence(attempt / "campaign_engine.log"),
        "summary": summary_evidence,
        "attempt_directory_removed": False,
        "removed_at_utc": "",
        "diagnostic_retention_max_per_case": FAILED_ATTEMPT_DIAGNOSTICS_PER_CASE,
        "created_at_utc": utc_now(),
    }


def _validate_failed_attempt_diagnostic(
    payload: Mapping[str, Any], *, manifest: Mapping[str, Any], case_key: str
) -> None:
    unsigned = dict(payload)
    signature = str(unsigned.pop("diagnostic_signature", ""))
    if (
        payload.get("schema_version") != FAILED_ATTEMPT_DIAGNOSTIC_SCHEMA_VERSION
        or payload.get("campaign_signature") != manifest.get("campaign_signature")
        or payload.get("engine_sha256") != manifest.get("engine_sha256")
        or payload.get("case_key") != case_key
        or not signature
        or signature != _stable_sha256(unsigned)
    ):
        raise ValueError(f"Failed-attempt diagnostic is invalid for {case_key}")


def _enforce_failed_attempt_diagnostic_retention(
    *, diagnostic_dir: Path, manifest: Mapping[str, Any], case_key: str, keep: Path
) -> None:
    """Keep only a bounded number of valid compact diagnostics for one case."""

    candidates: list[Path] = []
    if not diagnostic_dir.is_dir():
        return
    for path in diagnostic_dir.glob("*.json"):
        try:
            payload = _read_json(path)
            _validate_failed_attempt_diagnostic(
                payload, manifest=manifest, case_key=case_key
            )
        except (OSError, ValueError, json.JSONDecodeError):
            # Never delete an unreadable or foreign diagnostic automatically.
            continue
        candidates.append(path)
    ordered = sorted(
        candidates,
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    retained = [keep.resolve()]
    retained.extend(
        path.resolve() for path in ordered if path.resolve() != keep.resolve()
    )
    for path in retained[FAILED_ATTEMPT_DIAGNOSTICS_PER_CASE:]:
        resolved = path.resolve()
        if resolved.parent != diagnostic_dir.resolve() or resolved.suffix != ".json":
            raise RuntimeError(
                f"Unsafe failed-attempt diagnostic retention path: {path}"
            )
        resolved.unlink()


def _cleanup_failed_attempt_after_diagnostic(
    *,
    diagnostic_path: Path,
    payload: Mapping[str, Any],
    shard_dir: Path,
    manifest: Mapping[str, Any],
    case_key: str,
) -> dict[str, Any]:
    _validate_failed_attempt_diagnostic(payload, manifest=manifest, case_key=case_key)
    attempts_root = (shard_dir / "_attempts").resolve()
    attempt = Path(str(payload.get("attempt_dir") or "")).resolve()
    if attempt.parent != attempts_root or not attempt.name.startswith(f"{case_key}__"):
        raise RuntimeError(f"Unsafe failed-attempt cleanup target: {attempt}")
    if attempt.exists():
        shutil.rmtree(attempt)
    updated = dict(payload)
    updated["attempt_directory_removed"] = True
    updated["removed_at_utc"] = utc_now()
    updated = _signed_document(updated, signature_field="diagnostic_signature")
    _write_json_atomic(diagnostic_path, updated)
    _enforce_failed_attempt_diagnostic_retention(
        diagnostic_dir=diagnostic_path.parent,
        manifest=manifest,
        case_key=case_key,
        keep=diagnostic_path,
    )
    return updated


def _recover_pending_failed_attempt_cleanup(
    *, shard_dir: Path, manifest: Mapping[str, Any], case_key: str
) -> None:
    diagnostic_dir = shard_dir / "attempt_diagnostics"
    if not diagnostic_dir.is_dir():
        return
    for path in sorted(diagnostic_dir.glob("*.json")):
        if not path.is_file():
            continue
        payload = _read_json(path)
        if payload.get("case_key") != case_key:
            continue
        _validate_failed_attempt_diagnostic(
            payload, manifest=manifest, case_key=case_key
        )
        if payload.get("attempt_directory_removed") is not True:
            _cleanup_failed_attempt_after_diagnostic(
                diagnostic_path=path,
                payload=payload,
                shard_dir=shard_dir,
                manifest=manifest,
                case_key=case_key,
            )


def _record_and_cleanup_failed_attempt(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    case_key: str,
    attempt: Path,
    seed: int,
    simulation_days: int,
    risk_csv: Path | None,
    command: Sequence[str],
    failure_kind: str,
    failure_detail: str,
    return_code: int | None,
) -> Path:
    payload = _failed_attempt_diagnostic_payload(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        case_key=case_key,
        attempt=attempt,
        seed=seed,
        simulation_days=simulation_days,
        risk_csv=risk_csv,
        command=command,
        failure_kind=failure_kind,
        failure_detail=failure_detail,
        return_code=return_code,
    )
    payload = _signed_document(payload, signature_field="diagnostic_signature")
    diagnostic_path = shard_dir / "attempt_diagnostics" / f"{attempt.name}.json"
    _write_json_atomic(diagnostic_path, payload)
    _cleanup_failed_attempt_after_diagnostic(
        diagnostic_path=diagnostic_path,
        payload=payload,
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=case_key,
    )
    return diagnostic_path


def _build_engine_command(
    *,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    case_dir: Path,
    seed: int,
    risk_csv: Path | None,
    simulation_days: int = SIMULATION_DAYS,
) -> list[str]:
    if simulation_days < STATE_EVALUATION_DAYS:
        raise ValueError("Engine horizon cannot be shorter than the state window")
    command = [
        sys.executable,
        str(Path(str(manifest["engine"])).resolve()),
        "--input",
        str(point["graph"]),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(simulation_days),
        "--seed",
        str(seed),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--common-random-numbers",
    ]
    if point.get("supplier_floors"):
        command.extend(["--supplier-neutral-floors-csv", str(point["supplier_floors"])])
    if point.get("factory_capacities"):
        command.extend(
            ["--factory-nominal-capacities-csv", str(point["factory_capacities"])]
        )
    command.extend(
        campaign_core.engine_profile_args(Path(str(manifest["engine_profile"])))
    )
    command.extend(protocol.MANAGED_REFERENCE_PROTOCOL_ARGS)
    if risk_csv is not None:
        command.extend(["--supplier-risk-events-csv", str(risk_csv.resolve())])
    return command


def _run_engine(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    case_key: str,
    seed: int,
    risk_csv: Path | None,
    simulation_days: int,
) -> Path:
    case_dir = shard_dir / "cases" / case_key
    required = (
        case_dir / "summaries" / "first_simulation_summary.json",
        case_dir / "data" / "production_demand_service_daily.csv",
        case_dir / "data" / "production_supplier_shipments_daily.csv",
    )
    if case_dir.exists():
        if all(path.is_file() for path in required):
            summary = _read_json(required[0])
            if int(summary.get("sim_days") or -1) != simulation_days:
                raise RuntimeError(
                    f"Promoted case horizon differs for {case_key}: "
                    f"{summary.get('sim_days')} != {simulation_days}"
                )
            return case_dir
        raise RuntimeError(f"Incomplete promoted case requires review: {case_dir}")
    _recover_pending_failed_attempt_cleanup(
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=case_key,
    )
    attempt = shard_dir / "_attempts" / f"{case_key}__{uuid.uuid4().hex}"
    attempt.mkdir(parents=True, exist_ok=False)
    command = _build_engine_command(
        manifest=manifest,
        point=point,
        case_dir=attempt,
        seed=seed,
        risk_csv=risk_csv,
        simulation_days=simulation_days,
    )
    log_path = attempt / "campaign_engine.log"
    try:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(
                f"[{utc_now()}] COMMAND {json.dumps(command, ensure_ascii=False)}\n"
            )
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
    except Exception as exc:
        diagnostic = _record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_launch_or_runtime_exception",
            failure_detail=f"{type(exc).__name__}: {exc}",
            return_code=None,
        )
        raise RuntimeError(
            f"Engine raised for {case_key}; compact diagnostic: {diagnostic}"
        ) from exc
    if completed.returncode != 0:
        diagnostic = _record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_nonzero_exit",
            failure_detail=f"engine return code {completed.returncode}",
            return_code=int(completed.returncode),
        )
        raise RuntimeError(
            f"Engine failed for {case_key}; compact diagnostic: {diagnostic}"
        )
    attempt_required = (
        attempt / "summaries" / "first_simulation_summary.json",
        attempt / "data" / "production_demand_service_daily.csv",
        attempt / "data" / "production_supplier_shipments_daily.csv",
    )
    if not all(path.is_file() for path in attempt_required):
        missing = [
            path.relative_to(attempt).as_posix()
            for path in attempt_required
            if not path.is_file()
        ]
        diagnostic = _record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_output_incomplete",
            failure_detail="missing required outputs: " + ", ".join(missing),
            return_code=int(completed.returncode),
        )
        raise RuntimeError(
            f"Engine output incomplete for {case_key}; compact diagnostic: {diagnostic}"
        )
    case_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        attempt.replace(case_dir)
    except Exception as exc:
        diagnostic = _record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_output_promotion_failed",
            failure_detail=f"{type(exc).__name__}: {exc}",
            return_code=int(completed.returncode),
        )
        raise RuntimeError(
            f"Engine output promotion failed for {case_key}; compact diagnostic: "
            f"{diagnostic}"
        ) from exc
    return case_dir


def _validate_client_service_horizon(
    rows: Sequence[Mapping[str, Any]], *, days: int
) -> None:
    indexed: set[tuple[str, int]] = set()
    for row in rows:
        if str(row.get("node_id") or "") != protocol.CLIENT_NODE_ID:
            continue
        product = str(row.get("item_id") or "").replace("item:", "")
        if product not in TARGET_PRODUCTS:
            continue
        day = _as_int(row.get("day"), -1)
        key = (product, day)
        if key in indexed:
            raise ValueError(f"Duplicate product/day service row: {key}")
        indexed.add(key)
        for field in (
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
        ):
            value = _as_float(row.get(field))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"Invalid {field} in product/day service row: {key}")
        if _as_float(row.get("required_with_backlog_qty")) + 1e-9 < _as_float(
            row.get("demand_qty")
        ):
            raise ValueError(f"Required quantity below current demand: {key}")
    expected = {(product, day) for product in TARGET_PRODUCTS for day in range(days)}
    if indexed != expected:
        raise ValueError(f"Product/day service matrix is not exactly 2 x {days}")


def _validate_production_horizon(
    rows: Sequence[Mapping[str, Any]], *, days: int
) -> None:
    for product, factory in PRODUCT_FACTORY.items():
        selected_days = [
            _as_int(row.get("day"), -1)
            for row in rows
            if str(row.get("node_id") or "") == factory
            and str(row.get("item_id") or "") == f"item:{product}"
        ]
        if len(selected_days) != days or set(selected_days) != set(range(days)):
            raise ValueError(
                f"Incomplete production horizon for {factory}/item:{product}"
            )


def _window_metrics(
    *,
    service_rows: Sequence[Mapping[str, Any]],
    production_rows: Sequence[Mapping[str, Any]],
    start_day: int,
    end_day: int,
) -> dict[str, Any]:
    if start_day < 0 or end_day < start_day:
        raise ValueError("Impact window is outside the simulated horizon")
    expected_days = set(range(start_day, end_day + 1))
    product_metrics: dict[str, dict[str, Any]] = {}
    total_demand = 0.0
    total_on_due = 0.0
    total_backlog_by_day: dict[int, float] = defaultdict(float)
    for product in TARGET_PRODUCTS:
        selected = [
            row
            for row in service_rows
            if str(row.get("node_id") or "") == protocol.CLIENT_NODE_ID
            and str(row.get("item_id") or "").replace("item:", "") == product
            and start_day <= _as_int(row.get("day"), -1) <= end_day
        ]
        if {_as_int(row.get("day"), -1) for row in selected} != expected_days or len(
            selected
        ) != len(expected_days):
            raise ValueError(f"Incomplete service impact window for product {product}")
        demand = 0.0
        on_due = 0.0
        backlog_qty_days = 0.0
        backlog_by_day: dict[int, float] = {}
        for row in selected:
            day = _as_int(row.get("day"))
            daily_demand = max(0.0, _as_float(row.get("demand_qty"), 0.0))
            served = max(0.0, _as_float(row.get("served_qty"), 0.0))
            required = max(
                daily_demand,
                _as_float(row.get("required_with_backlog_qty"), daily_demand),
            )
            starting_backlog = max(0.0, required - daily_demand)
            daily_on_due = min(daily_demand, max(0.0, served - starting_backlog))
            ending_backlog = max(0.0, _as_float(row.get("backlog_end_qty"), 0.0))
            demand += daily_demand
            on_due += daily_on_due
            backlog_qty_days += ending_backlog
            backlog_by_day[day] = ending_backlog
            total_backlog_by_day[day] += ending_backlog
        production_selected = [
            row
            for row in production_rows
            if str(row.get("node_id") or "") == PRODUCT_FACTORY[product]
            and str(row.get("item_id") or "") == f"item:{product}"
            and start_day <= _as_int(row.get("day"), -1) <= end_day
        ]
        if {
            _as_int(row.get("day"), -1) for row in production_selected
        } != expected_days or len(production_selected) != len(expected_days):
            raise ValueError(
                f"Incomplete production impact window for product {product}"
            )
        product_metrics[product] = {
            "demand_qty": demand,
            "on_due_qty": on_due,
            "service_pct": 100.0 * on_due / demand if demand > 1e-12 else 100.0,
            "backlog_qty_days": backlog_qty_days,
            "max_backlog_qty": max(backlog_by_day.values(), default=0.0),
            "ending_backlog_qty": backlog_by_day.get(end_day, 0.0),
            "production_released_qty": sum(
                max(0.0, _as_float(row.get("released_qty"), 0.0))
                for row in production_selected
            ),
        }
        total_demand += demand
        total_on_due += on_due
    return {
        "start_day": start_day,
        "end_day": end_day,
        "day_count": end_day - start_day + 1,
        "fully_observed": True,
        "demand_qty_268091": product_metrics["268091"]["demand_qty"],
        "demand_qty_268967": product_metrics["268967"]["demand_qty"],
        "demand_qty_global": total_demand,
        "on_due_qty_268091": product_metrics["268091"]["on_due_qty"],
        "on_due_qty_268967": product_metrics["268967"]["on_due_qty"],
        "on_due_qty_global": total_on_due,
        "service_268091_pct": product_metrics["268091"]["service_pct"],
        "service_268967_pct": product_metrics["268967"]["service_pct"],
        "service_global_pct": (
            100.0 * total_on_due / total_demand if total_demand > 1e-12 else 100.0
        ),
        "backlog_qty_days_268091": product_metrics["268091"]["backlog_qty_days"],
        "backlog_qty_days_268967": product_metrics["268967"]["backlog_qty_days"],
        "max_backlog_qty_268091": product_metrics["268091"]["max_backlog_qty"],
        "max_backlog_qty_268967": product_metrics["268967"]["max_backlog_qty"],
        "backlog_qty_days_global": sum(total_backlog_by_day.values()),
        "backlog_day_count_global": sum(
            value > 1e-9 for value in total_backlog_by_day.values()
        ),
        "max_backlog_qty_global": max(total_backlog_by_day.values(), default=0.0),
        "ending_backlog_qty_global": total_backlog_by_day.get(end_day, 0.0),
        "production_released_268091_qty": product_metrics["268091"][
            "production_released_qty"
        ],
        "production_released_268967_qty": product_metrics["268967"][
            "production_released_qty"
        ],
    }


def _extract_metrics(
    *,
    case_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    risk_csv: Path | None,
    expected_event_id: str | None,
    simulation_days: int = SIMULATION_DAYS,
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    list[str],
    dict[str, list[dict[str, str]]],
]:
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    production_path = case_dir / "data" / "production_output_products_daily.csv"
    shipment_path = case_dir / "data" / "production_supplier_shipments_daily.csv"
    required = (summary_path, service_path, production_path, shipment_path)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Missing engine evidence: {path}")
    summary = _read_json(summary_path)
    service_rows = protocol.read_csv_rows(service_path)
    production_rows = protocol.read_csv_rows(production_path)
    shipment_rows = protocol.read_csv_rows(shipment_path)
    if simulation_days < STATE_EVALUATION_DAYS:
        raise ValueError("Measured engine horizon is shorter than the state window")
    _validate_client_service_horizon(service_rows, days=simulation_days)
    _validate_production_horizon(production_rows, days=simulation_days)
    state_service_rows = [
        row
        for row in service_rows
        if 0 <= _as_int(row.get("day"), -1) < STATE_EVALUATION_DAYS
    ]
    service = protocol.service_from_daily_rows(
        state_service_rows, days=STATE_EVALUATION_DAYS
    )
    state_window = _window_metrics(
        service_rows=service_rows,
        production_rows=production_rows,
        start_day=0,
        end_day=STATE_EVALUATION_DAYS - 1,
    )
    policy = summary.get("policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    economic = policy.get("economic_policy") or {}
    initialization = policy.get("initialization_policy") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    kpis = summary.get("kpis") or {}
    errors: list[str] = []
    if str(summary.get("input_sha256") or "") != str(point["graph_sha256"]):
        errors.append("engine input graph SHA-256 mismatch")
    if int(summary.get("sim_days") or -1) != simulation_days:
        errors.append("engine measured horizon mismatch")
    if int(policy.get("warmup_days") or -1) != protocol.WARMUP_DAYS:
        errors.append("engine warmup mismatch")
    if not str(warmup.get("core_state_sha256") or ""):
        errors.append("missing warmup core-state SHA-256")
    if _truthy(state_risk.get("enabled")):
        errors.append("state-dependent supplier risks unexpectedly enabled")
    if _truthy(economic.get("supplier_risk_loss_gross_up")):
        errors.append("temporary supplier loss was grossed up in planning")
    if _truthy(initialization.get("seed_open_orders_from_january_snapshot")):
        errors.append("January opening orders unexpectedly enabled")
    expected_event_count = 1 if expected_event_id else 0
    if int(supplier_risk.get("event_count") or 0) != expected_event_count:
        errors.append("acute supplier-risk event count mismatch")
    if supplier_risk.get("warnings"):
        errors.append("supplier-risk loader warnings present")
    if risk_csv is None:
        if _truthy(supplier_risk.get("enabled")):
            errors.append("supplier-risk layer unexpectedly enabled in baseline")
    else:
        if not _truthy(supplier_risk.get("enabled")):
            errors.append("supplier-risk layer is not enabled in incident")
        if str(supplier_risk.get("events_csv_sha256") or "") != _sha256_file(risk_csv):
            errors.append("supplier-risk CSV SHA-256 mismatch")
    applied_rows: list[dict[str, str]] = []
    if expected_event_id:
        applied_path = case_dir / "data" / "supplier_risk_events_applied_daily.csv"
        if not applied_path.is_file():
            errors.append("missing supplier-risk application trace")
        else:
            applied_rows = [
                row
                for row in protocol.read_csv_rows(applied_path)
                if expected_event_id in _event_tokens(row.get("event_ids"))
            ]
    metrics = {
        **service,
        "state_window_metrics": state_window,
        "simulation_days": simulation_days,
        "state_evaluation_days": STATE_EVALUATION_DAYS,
        "state_evaluation_start_day": 0,
        "state_evaluation_end_day": STATE_EVALUATION_DAYS - 1,
        "service_global_pct": 100.0 * float(service["system_on_due_service"]),
        "service_output_product_268091_pct": 100.0
        * float(service["on_due_service_268091"]),
        "service_output_product_268967_pct": 100.0
        * float(service["on_due_service_268967"]),
        "backlog_day_count": state_window["backlog_day_count_global"],
        "backlog_qty": state_window["ending_backlog_qty_global"],
        "max_backlog_qty": state_window["max_backlog_qty_global"],
        "backlog_qty_days": state_window["backlog_qty_days_global"],
        "production_released_268091_qty": state_window[
            "production_released_268091_qty"
        ],
        "production_released_268967_qty": state_window[
            "production_released_268967_qty"
        ],
        "total_cost": _as_float(kpis.get("total_cost"), 0.0),
        "total_transport_cost": _as_float(kpis.get("total_transport_cost"), 0.0),
        "total_purchase_cost": _as_float(kpis.get("total_purchase_cost"), 0.0),
        "total_unreliable_loss_qty": _as_float(
            kpis.get("total_unreliable_loss_qty"), 0.0
        ),
        "warmup_core_state_sha256": str(warmup.get("core_state_sha256") or ""),
        "summary_sha256": _sha256_file(summary_path),
        "risk_applied_row_count": len(applied_rows),
        "risk_applied_event_count": len(
            {
                token
                for row in applied_rows
                for token in _event_tokens(row.get("event_ids"))
                if token == expected_event_id
            }
        ),
    }
    return (
        metrics,
        shipment_rows,
        applied_rows,
        errors,
        {"service_rows": service_rows, "production_rows": production_rows},
    )


def validate_incident_trace(
    *,
    mechanism: Mechanism,
    lane: Lane,
    target: Mapping[str, Any],
    risk_row: Mapping[str, Any],
    shipment_rows: Sequence[Mapping[str, Any]],
    applied_rows: Sequence[Mapping[str, Any]],
    simulation_days: int = SIMULATION_DAYS,
) -> tuple[dict[str, Any], list[str]]:
    event_id = str(risk_row["event_id"])
    tagged = [
        row
        for row in shipment_rows
        if _lane_matches(row, lane)
        and event_id in _event_tokens(row.get("risk_event_ids"))
        and (
            _as_float(row.get("pulled_qty"), 0.0) > 1e-12
            or _as_float(row.get("shipped_qty"), 0.0) > 1e-12
        )
    ]
    target_window_start = int(target["target_window_start_day"])
    target_window_end = int(target["target_window_end_day"])
    incident_window_rows = [
        row
        for row in shipment_rows
        if _lane_matches(row, lane)
        and target_window_start
        <= _as_int(row.get("risk_decision_day"), -1)
        <= target_window_end
        and (
            _as_float(row.get("pulled_qty"), 0.0) > 1e-12
            or _as_float(row.get("shipped_qty"), 0.0) > 1e-12
        )
    ]
    errors: list[str] = []
    zero_flow_target = (
        str(target.get("target_status") or "")
        == "identified_registered_window_no_positive_flow"
    )
    if not applied_rows and not zero_flow_target:
        errors.append("expected at least one risk-application row")
    baseline_rows = [dict(row) for row in target.get("target_shipments") or []]
    if not baseline_rows and not zero_flow_target:
        errors.append("target does not contain its baseline shipment-row ledger")
    baseline_by_id = {str(row.get("shipment_id") or ""): row for row in baseline_rows}
    tagged_by_id = {str(row.get("shipment_id") or ""): row for row in tagged}
    incident_by_id = {
        str(row.get("shipment_id") or ""): row for row in incident_window_rows
    }
    if "" in baseline_by_id or len(baseline_by_id) != len(baseline_rows):
        errors.append("baseline target shipment ids are empty or duplicated")
    if "" in tagged_by_id or len(tagged_by_id) != len(tagged):
        errors.append("tagged shipment ids are empty or duplicated")
    if "" in incident_by_id or len(incident_by_id) != len(incident_window_rows):
        errors.append("incident-window shipment ids are empty or duplicated")
    if set(tagged_by_id) != set(incident_by_id):
        errors.append(
            "not every incident-window shipment is tagged, or a tagged row is outside"
        )
    expected_shortfall_factor = (
        0.5 if mechanism.key == "planned_delivery_shortfall" else 1.0
    )
    expected_arrival_delta = 120 if mechanism.key == "transport_delay" else 0
    impact_start = _as_int(target.get("impact_window_start_day"), -1)
    impact_end = _as_int(target.get("impact_window_end_day"), -1)
    causal_start = _as_int(target.get("causal_window_start_day"), -1)
    causal_end = _as_int(target.get("causal_window_end_day"), -1)
    if (
        target.get("impact_window_fully_observed") is not True
        or impact_end - impact_start + 1 != IMPACT_WINDOW_DAYS
        or impact_start < 0
        or impact_end >= simulation_days
    ):
        errors.append("target impact window is not a complete 360-day simulated window")
    if (
        target.get("causal_window_fully_observed") is not True
        or causal_start < 0
        or causal_end >= simulation_days
    ):
        errors.append("target causal window is not fully observed in the simulation")
    if (
        _as_int(
            target.get("recovery_observation_days_after_latest_stressed_arrival"), 0
        )
        < MIN_RECOVERY_OBSERVATION_DAYS
        and not zero_flow_target
    ):
        errors.append(
            "target leaves fewer than 90 observed days including the latest affected arrival"
        )
    if mechanism.key == "planned_delivery_shortfall":
        if str(risk_row.get("risk_type")) != "reliability" or not math.isclose(
            float(risk_row["multiplier"]), 0.5
        ):
            errors.append("delivery-shortfall risk is not reliability x0.5")
    elif mechanism.key == "transport_delay":
        if str(risk_row.get("risk_type")) != "lead_time_extra_days" or not math.isclose(
            float(risk_row["multiplier"]), 120.0
        ):
            errors.append("transport-delay risk is not +120 days")
    else:
        errors.append(f"unsupported V2 mechanism: {mechanism.key}")
    for shipment_id, actual in sorted(tagged_by_id.items()):
        decision_day = _as_int(actual.get("risk_decision_day"), -1)
        if not target_window_start <= decision_day <= target_window_end:
            errors.append(
                f"{shipment_id}: tagged decision day falls outside target window"
            )
        pulled = _as_float(actual.get("pulled_qty"), 0.0)
        shipped = _as_float(actual.get("shipped_qty"), 0.0)
        effective_reliability = _as_float(actual.get("reliability"), 0.0)
        if not math.isclose(
            shipped,
            pulled * effective_reliability,
            rel_tol=1e-9,
            abs_tol=TARGET_QUANTITY_TOLERANCE,
        ):
            errors.append(
                f"{shipment_id}: shipped quantity contradicts effective reliability"
            )
        if (
            mechanism.key == "planned_delivery_shortfall"
            and effective_reliability > 0.5 + 1e-9
        ):
            errors.append(
                f"{shipment_id}: reliability does not prove the x0.5 disruption"
            )
        if (
            mechanism.key == "transport_delay"
            and _as_int(actual.get("lead_days"), 0) < 120
        ):
            errors.append(
                f"{shipment_id}: lead time does not contain the +120-day disruption"
            )
        if _as_int(actual.get("arrival_day"), simulation_days) >= simulation_days:
            errors.append(f"{shipment_id}: stressed arrival falls outside simulation")
    aggregate_pulled = sum(_as_float(row.get("pulled_qty"), 0.0) for row in tagged)
    aggregate_shipped = sum(_as_float(row.get("shipped_qty"), 0.0) for row in tagged)
    baseline_pulled = float(target["target_planned_qty"])
    baseline_shipped = float(target["target_expected_delivered_qty"])
    attributable_shortfall = (
        sum(
            max(
                0.0,
                _as_float(row.get("pulled_qty"), 0.0)
                * min(
                    1.0,
                    _as_float(row.get("reliability"), 0.0) / expected_shortfall_factor,
                )
                - _as_float(row.get("shipped_qty"), 0.0),
            )
            for row in tagged
        )
        if mechanism.key == "planned_delivery_shortfall"
        else 0.0
    )
    if applied_rows:
        expected_active_days = {
            _as_int(row.get("risk_decision_day"), -1) for row in tagged
        }
        actual_application_days = {_as_int(row.get("day"), -1) for row in applied_rows}
        if not expected_active_days.issubset(actual_application_days):
            errors.append("a tagged shipment day lacks an application-trace row")
        if any(
            not target_window_start <= day <= target_window_end
            for day in actual_application_days
        ):
            errors.append(
                "an application-trace row falls outside the disruption window"
            )
        for applied in applied_rows:
            if mechanism.key == "planned_delivery_shortfall":
                if not math.isclose(
                    _as_float(applied.get("reliability_multiplier")), 0.5
                ):
                    errors.append("application trace does not prove reliability x0.5")
            elif not math.isclose(
                _as_float(applied.get("lead_time_extra_days")), 120.0
            ):
                errors.append("application trace does not prove +120 days")
            if not math.isclose(_as_float(applied.get("availability_multiplier")), 1.0):
                errors.append("availability multiplier is not neutral")
            if not math.isclose(_as_float(applied.get("capacity_multiplier")), 1.0):
                errors.append("capacity multiplier is not neutral")
            if not math.isclose(
                _as_float(applied.get("quality_yield_multiplier")), 1.0
            ):
                errors.append("quality-yield multiplier is not neutral")
            if not math.isclose(_as_float(applied.get("quality_delay_days")), 0.0):
                errors.append("quality delay is not neutral")
    proof = {
        "incident_physically_exercised": bool(tagged) and not errors,
        "anchor_day": int(target["target_decision_day"]),
        "baseline_shipment_count": len(baseline_rows),
        "baseline_shipment_ids": sorted(baseline_by_id),
        "baseline_pulled_qty": baseline_pulled,
        "baseline_expected_delivered_qty": baseline_shipped,
        "baseline_arrival_days_by_shipment": {
            shipment_id: int(row["arrival_day"])
            for shipment_id, row in sorted(baseline_by_id.items())
        },
        "tagged_shipment_row_count": len(tagged),
        "stressed_shipment_ids": sorted(tagged_by_id),
        "stressed_pulled_qty": aggregate_pulled,
        "stressed_shipped_qty": aggregate_shipped,
        "quantity_shortfall_qty": attributable_shortfall,
        "incident_affected_pulled_qty": aggregate_pulled,
        "incident_affected_shipped_qty": aggregate_shipped,
        "incident_plan_divergence_pulled_qty": aggregate_pulled - baseline_pulled,
        "incident_shipment_count": len(tagged),
        "arrival_delay_days": expected_arrival_delta,
        "impact_window_start_day": impact_start,
        "impact_window_end_day": impact_end,
        "impact_window_days": impact_end - impact_start + 1,
        "impact_window_fully_observed": (
            impact_start >= 0 and impact_end < simulation_days
        ),
        "recovery_observation_days_within_impact_window": max(
            0,
            impact_end
            - _as_int(target.get("target_latest_stressed_arrival_day"), impact_end + 1)
            + 1,
        ),
        "recovery_fully_observed_within_360": bool(
            target.get("recovery_fully_observed_within_360")
        ),
        "causal_window_start_day": causal_start,
        "causal_window_end_day": causal_end,
        "causal_window_days": causal_end - causal_start + 1,
        "causal_window_fully_observed": causal_start >= 0
        and causal_end < simulation_days,
        "arrival_delay_days_by_shipment": {
            shipment_id: _as_int(tagged_by_id[shipment_id].get("arrival_day"))
            - int(baseline_by_id[shipment_id]["arrival_day"])
            for shipment_id in sorted(set(baseline_by_id) & set(tagged_by_id))
        },
        "risk_event_ids": sorted(
            {
                token
                for row in tagged
                for token in _event_tokens(row.get("risk_event_ids"))
            }
        ),
        "tagged_shipments": [dict(row) for row in tagged],
        "applied_rows": [dict(row) for row in applied_rows],
    }
    return proof, errors


def _base_evidence(
    *,
    manifest: Mapping[str, Any],
    shard_id: str,
    point: Mapping[str, Any],
    seed: int,
    stage: str,
    case_key: str,
    case_signature: str,
    simulation_days: int,
) -> dict[str, Any]:
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "shard_id": shard_id,
        "shard_index": manifest.get("active_shard_index", ""),
        "shard_count": manifest.get("active_shard_count", ""),
        "operating_point_id": point["operating_point_id"],
        "operating_point_service_pct": point["operating_point_service_pct"],
        "simulation_days": simulation_days,
        "state_evaluation_days": STATE_EVALUATION_DAYS,
        "seed": int(seed),
        "stage": stage,
        "case_key": case_key,
        "case_signature": case_signature,
        "quality_branch_included": False,
        "availability_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "created_at_utc": utc_now(),
    }


def _persist_evidence(path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    evidence["evidence_signature"] = _evidence_signature(evidence)
    _write_json_atomic(path, evidence)
    return evidence


def _discovery_case_key(point_id: str, seed: int) -> str:
    return f"{point_id}__target_discovery__seed_{seed}"


def _discovery_signature(
    manifest: Mapping[str, Any], point: Mapping[str, Any], seed: int
) -> str:
    return _stable_sha256(
        {
            "campaign_signature": manifest["campaign_signature"],
            "engine_sha256": manifest["engine_sha256"],
            "engine_profile_sha256": manifest["engine_profile_sha256"],
            "point_id": point["operating_point_id"],
            "graph_sha256": point["graph_sha256"],
            "seed": seed,
            "simulation_days": DISCOVERY_DAYS,
            "purpose": "cross_state_42d_target_discovery",
        }
    )


def _execute_target_discovery_case(
    *,
    discovery_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lanes: Sequence[Lane],
    seed: int,
) -> dict[str, Any]:
    key = _discovery_case_key(str(point["operating_point_id"]), seed)
    signature = _discovery_signature(manifest, point, seed)
    evidence_path = discovery_dir / "evidence" / f"{key}.json"
    if evidence_path.is_file():
        evidence = _read_json(evidence_path)
        unsigned = dict(evidence)
        actual_signature = unsigned.pop("evidence_signature", "")
        if (
            evidence.get("schema_version")
            != f"{SCHEMA_VERSION}.target_discovery.case.v1"
            or evidence.get("discovery_signature") != signature
            or evidence.get("campaign_signature") != manifest["campaign_signature"]
            or actual_signature != _stable_sha256(unsigned)
        ):
            raise ValueError(
                f"Invalid reusable target discovery evidence: {evidence_path}"
            )
        return evidence
    case_dir = _run_engine(
        shard_dir=discovery_dir,
        manifest=manifest,
        point=point,
        case_key=key,
        seed=seed,
        risk_csv=None,
        simulation_days=DISCOVERY_DAYS,
    )
    metrics, shipment_rows, _applied, errors, _daily = _extract_metrics(
        case_dir=case_dir,
        manifest=manifest,
        point=point,
        risk_csv=None,
        expected_event_id=None,
        simulation_days=DISCOVERY_DAYS,
    )
    relevant = [
        dict(row)
        for row in shipment_rows
        if any(_lane_matches(row, lane) for lane in lanes)
        and 0 <= _as_int(row.get("risk_decision_day"), -1) < STATE_EVALUATION_DAYS
        and _as_float(row.get("shipped_qty"), 0.0) > 1e-12
    ]
    if errors:
        raise RuntimeError(f"Invalid target discovery {key}: " + "; ".join(errors))
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.target_discovery.case.v1",
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "discovery_signature": signature,
        "operating_point_id": point["operating_point_id"],
        "seed": seed,
        "simulation_days": DISCOVERY_DAYS,
        "warmup_core_state_sha256": metrics["warmup_core_state_sha256"],
        "summary_sha256": metrics["summary_sha256"],
        "state_service_metrics": {
            key: value
            for key, value in dict(metrics["state_window_metrics"]).items()
            if key
            in {
                "start_day",
                "end_day",
                "day_count",
                "demand_qty_268091",
                "demand_qty_268967",
                "demand_qty_global",
                "on_due_qty_268091",
                "on_due_qty_268967",
                "on_due_qty_global",
                "service_268091_pct",
                "service_268967_pct",
                "service_global_pct",
            }
        },
        "shipment_rows": relevant,
        "created_at_utc": utc_now(),
    }
    evidence = {**unsigned, "evidence_signature": _stable_sha256(unsigned)}
    _write_json_atomic(evidence_path, evidence)
    campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _linear_quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0.0 <= probability <= 1.0:
        raise ValueError("A non-empty sample and a probability in [0, 1] are required")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def build_operating_point_preflight(
    *,
    manifest: Mapping[str, Any],
    points: Sequence[Mapping[str, Any]],
    discovery_evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    bootstrap_replicates: int = PREFLIGHT_BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    """Validate the three achieved service states before any incident probe.

    The 30 campaign runs are paired by common seed.  Seed 340281 is reported as design
    evidence only and is never included in the acceptance statistics.
    """

    if bootstrap_replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")
    expected = {
        (point_id, seed)
        for point_id in OPERATING_POINT_IDS
        for seed in (TARGET_DESIGN_SEED, *SEEDS)
    }
    if set(discovery_evidence) != expected:
        raise ValueError("Operating-point preflight discovery matrix is incomplete")
    point_by_id = {str(point["operating_point_id"]): dict(point) for point in points}
    if set(point_by_id) != set(OPERATING_POINT_IDS):
        raise ValueError("Operating-point preflight requires exactly three states")

    metric_names = (
        "demand_qty_global",
        "on_due_qty_global",
        "demand_qty_268091",
        "on_due_qty_268091",
        "demand_qty_268967",
        "on_due_qty_268967",
    )
    rows_by_point: dict[str, list[dict[str, float]]] = {}
    design_rows: dict[str, dict[str, Any]] = {}
    for point_id in OPERATING_POINT_IDS:
        rows: list[dict[str, float]] = []
        for seed in (TARGET_DESIGN_SEED, *SEEDS):
            raw = dict(
                discovery_evidence[(point_id, seed)].get("state_service_metrics") or {}
            )
            converted = {name: _as_float(raw.get(name)) for name in metric_names}
            if any(
                not math.isfinite(value) or value < 0.0 for value in converted.values()
            ):
                raise ValueError(
                    f"Missing or invalid state-service totals for {point_id}/seed {seed}"
                )
            for demand_field in (
                "demand_qty_268091",
                "demand_qty_268967",
                "demand_qty_global",
            ):
                if converted[demand_field] <= 1e-12:
                    raise ValueError(
                        f"Zero seed-level demand for {point_id}/seed {seed}: "
                        f"{demand_field}"
                    )
            for product in TARGET_PRODUCTS:
                if converted[f"on_due_qty_{product}"] > (
                    converted[f"demand_qty_{product}"] + TARGET_QUANTITY_TOLERANCE
                ):
                    raise ValueError(
                        f"On-due quantity exceeds demand for {point_id}/seed {seed}/{product}"
                    )
            if converted["on_due_qty_global"] > (
                converted["demand_qty_global"] + TARGET_QUANTITY_TOLERANCE
            ):
                raise ValueError(
                    f"Global on-due quantity exceeds demand for {point_id}/seed {seed}"
                )
            converted["seed"] = float(seed)
            if seed == TARGET_DESIGN_SEED:
                design_rows[point_id] = {
                    "seed": seed,
                    **converted,
                    "service_global_pct": 100.0
                    * converted["on_due_qty_global"]
                    / converted["demand_qty_global"],
                }
            else:
                rows.append(converted)
        if len(rows) != len(SEEDS):
            raise AssertionError("Campaign-seed state preflight count changed")
        rows_by_point[point_id] = rows

    for index, seed in enumerate(SEEDS):
        reference = rows_by_point["op_100"][index]
        for point_id in OPERATING_POINT_IDS[1:]:
            candidate = rows_by_point[point_id][index]
            for demand_field in (
                "demand_qty_268091",
                "demand_qty_268967",
                "demand_qty_global",
            ):
                if not math.isclose(
                    float(reference[demand_field]),
                    float(candidate[demand_field]),
                    rel_tol=1e-12,
                    abs_tol=TARGET_QUANTITY_TOLERANCE,
                ):
                    raise ValueError(
                        f"Paired holdout demand changed across states for seed {seed}: "
                        f"{demand_field}"
                    )

    rng = random.Random(PREFLIGHT_BOOTSTRAP_SEED)
    bootstrap_indices = [
        [rng.randrange(len(SEEDS)) for _ in SEEDS] for _ in range(bootstrap_replicates)
    ]

    def ratio_of_sums(
        rows: Sequence[Mapping[str, float]], demand_field: str, on_due_field: str
    ) -> float:
        demand = sum(float(row[demand_field]) for row in rows)
        if demand <= 1e-12:
            raise ValueError(
                f"Zero total demand in operating-point preflight: {demand_field}"
            )
        return 100.0 * sum(float(row[on_due_field]) for row in rows) / demand

    def seed_service(
        row: Mapping[str, float], demand_field: str, on_due_field: str
    ) -> float:
        demand = float(row[demand_field])
        if demand <= 1e-12:
            raise ValueError(f"Zero seed-level demand in preflight: {demand_field}")
        return 100.0 * float(row[on_due_field]) / demand

    def dispersion(values: Sequence[float]) -> dict[str, float]:
        return {
            "min": min(values),
            "p10": _linear_quantile(values, 0.10),
            "p25": _linear_quantile(values, 0.25),
            "median": _linear_quantile(values, 0.50),
            "p75": _linear_quantile(values, 0.75),
            "p90": _linear_quantile(values, 0.90),
            "max": max(values),
            "iqr": _linear_quantile(values, 0.75) - _linear_quantile(values, 0.25),
        }

    state_rows: list[dict[str, Any]] = []
    for point_id in OPERATING_POINT_IDS:
        rows = rows_by_point[point_id]
        global_pct = ratio_of_sums(rows, "demand_qty_global", "on_due_qty_global")
        product_pct = {
            product: ratio_of_sums(
                rows, f"demand_qty_{product}", f"on_due_qty_{product}"
            )
            for product in TARGET_PRODUCTS
        }
        seed_level = {
            "global": [
                seed_service(row, "demand_qty_global", "on_due_qty_global")
                for row in rows
            ],
            **{
                product: [
                    seed_service(
                        row,
                        f"demand_qty_{product}",
                        f"on_due_qty_{product}",
                    )
                    for row in rows
                ]
                for product in TARGET_PRODUCTS
            },
        }
        bootstrap_global = [
            ratio_of_sums(
                [rows[index] for index in indices],
                "demand_qty_global",
                "on_due_qty_global",
            )
            for indices in bootstrap_indices
        ]
        saturated_seed_count = {
            product: sum(value >= 100.0 - 1e-9 for value in seed_level[product])
            for product in TARGET_PRODUCTS
        }
        non_saturation_limit_seed_count = {
            product: sum(value >= 99.5 - 1e-9 for value in seed_level[product])
            for product in TARGET_PRODUCTS
        }
        transition_zone_by_product = {
            product: 0 < count < len(SEEDS)
            for product, count in saturated_seed_count.items()
        }
        failures: list[str] = []
        target_pct = 100.0 * float(point_by_id[point_id]["target_service"])
        global_median_pct = dispersion(seed_level["global"])["median"]
        if point_id == "op_100":
            if not 98.5 <= global_pct <= 100.0 + 1e-9:
                failures.append("healthy global service is outside the 98.5-100% band")
            if not 98.5 <= global_median_pct <= 100.0 + 1e-9:
                failures.append(
                    "healthy median seed-level global service is outside the 98.5-100% band"
                )
            if any(value < 98.5 - 1e-9 for value in product_pct.values()):
                failures.append("a healthy finished product is below 98.5% service")
            contract = "global and each product 98.5-100%; product gap descriptive"
        elif point_id == "op_93":
            lower = target_pct - 1.5
            upper = target_pct + 1.5
            if not lower <= global_pct <= upper:
                failures.append(
                    f"global service is outside the signed {lower:.3f}-{upper:.3f}% band"
                )
            if not lower <= global_median_pct <= upper:
                failures.append(
                    f"median seed-level global service is outside the signed "
                    f"{lower:.3f}-{upper:.3f}% band"
                )
            if max(product_pct.values()) >= 99.5 - 1e-9:
                failures.append(
                    "a degraded finished product reaches the 99.5% saturation limit"
                )
            contract = (
                f"global {lower:.3f}-{upper:.3f}%; each product below 99.5%; "
                "product gap>5pp flagged"
            )
        else:
            lower = target_pct - 1.5
            upper = target_pct + 1.5
            if not lower <= global_pct <= upper:
                failures.append(
                    f"global service is outside the signed {lower:.3f}-{upper:.3f}% band"
                )
            if not lower <= global_median_pct <= upper:
                failures.append(
                    f"median seed-level global service is outside the signed "
                    f"{lower:.3f}-{upper:.3f}% band"
                )
            if max(product_pct.values()) >= 99.5 - 1e-9:
                failures.append(
                    "a degraded finished product reaches the 99.5% saturation limit"
                )
            contract = (
                f"global {lower:.3f}-{upper:.3f}%; each product below 99.5%; "
                "product gap>5pp flagged"
            )
        state_rows.append(
            {
                "operating_point_id": point_id,
                "target_service_pct": target_pct,
                "campaign_seed_count": len(rows),
                "service_global_ratio_of_sums_pct": global_pct,
                "service_global_seed_median_pct": global_median_pct,
                "service_268091_ratio_of_sums_pct": product_pct["268091"],
                "service_268967_ratio_of_sums_pct": product_pct["268967"],
                "product_service_gap_pp": abs(
                    product_pct["268091"] - product_pct["268967"]
                ),
                "product_service_gap_above_5pp": abs(
                    product_pct["268091"] - product_pct["268967"]
                )
                > 5.0,
                "seed_level_service_dispersion_pct": {
                    name: dispersion(values) for name, values in seed_level.items()
                },
                "saturated_seed_count_by_product": saturated_seed_count,
                "non_saturation_limit_seed_count_by_product": (
                    non_saturation_limit_seed_count
                ),
                "transition_zone_by_product": transition_zone_by_product,
                "transition_zone_observed": any(transition_zone_by_product.values()),
                "global_service_bootstrap_ci95_low_pct": _linear_quantile(
                    bootstrap_global, 0.025
                ),
                "global_service_bootstrap_ci95_high_pct": _linear_quantile(
                    bootstrap_global, 0.975
                ),
                "acceptance_contract": contract,
                "accepted": not failures,
                "failures": failures,
                "design_seed_descriptive_only": design_rows[point_id],
            }
        )
    pooled_ordering_by_measure = {
        "global": (
            float(state_rows[0]["service_global_ratio_of_sums_pct"])
            > float(state_rows[1]["service_global_ratio_of_sums_pct"])
            > float(state_rows[2]["service_global_ratio_of_sums_pct"])
        ),
        "268091": (
            float(state_rows[0]["service_268091_ratio_of_sums_pct"])
            > float(state_rows[1]["service_268091_ratio_of_sums_pct"])
            > float(state_rows[2]["service_268091_ratio_of_sums_pct"])
        ),
        "268967": (
            float(state_rows[0]["service_268967_ratio_of_sums_pct"])
            > float(state_rows[1]["service_268967_ratio_of_sums_pct"])
            > float(state_rows[2]["service_268967_ratio_of_sums_pct"])
        ),
    }
    ordering_valid = all(pooled_ordering_by_measure.values())
    seed_order_counts = {
        name: sum(
            seed_service(
                rows_by_point["op_100"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_93"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_80"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            for index in range(len(SEEDS))
        )
        for name in ("global", *TARGET_PRODUCTS)
    }
    joint_seed_order_count = sum(
        all(
            seed_service(
                rows_by_point["op_100"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_93"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_80"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            for name in ("global", *TARGET_PRODUCTS)
        )
        for index in range(len(SEEDS))
    )
    seed_ordering_valid = joint_seed_order_count >= 24
    product_seed_ordering_checks = {
        product: {
            "ordered_seed_count": seed_order_counts[product],
            "ordering_observed_in_at_least_24_of_30_seeds": (
                seed_order_counts[product] >= 24
            ),
            "acceptance_gate": True,
        }
        for product in TARGET_PRODUCTS
    }
    if not ordering_valid or not seed_ordering_valid:
        for row in state_rows:
            row["failures"].append(
                "service-state ordering op_100>op_93>op_80 is not preserved "
                "in pooled ratio-of-sums and jointly for global service plus "
                "both finished products on at least the same 24/30 paired seeds"
            )
            row["accepted"] = False
    unsigned = {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "campaign_signature": manifest["campaign_signature"],
        "status": (
            HOLDOUT_ACCEPTED_STATUS
            if all(row["accepted"] for row in state_rows)
            else HOLDOUT_REJECTED_STATUS
        ),
        "campaign_seed_count": len(SEEDS),
        "campaign_seeds": list(SEEDS),
        "calibration_seeds_excluded": list(range(340282, 340287)),
        "holdout_used_once_without_retuning": True,
        "operating_points_input_status": manifest.get(
            "operating_points_input_status", ""
        ),
        "operating_points_artifact_signature": manifest.get(
            "operating_points_artifact_signature", ""
        ),
        "operating_points_calibration_plan_signature": manifest.get(
            "operating_points_calibration_plan_signature", ""
        ),
        "operating_points_selection_signature": manifest.get(
            "operating_points_selection_signature", ""
        ),
        "no_incident_probe_before_holdout_acceptance": True,
        "design_seed": TARGET_DESIGN_SEED,
        "design_seed_in_acceptance_statistics": False,
        "bootstrap": {
            "method": "paired_common_seed_resampling",
            "replicates": bootstrap_replicates,
            "seed": PREFLIGHT_BOOTSTRAP_SEED,
        },
        "ordering_valid": ordering_valid,
        "pooled_ordering_by_measure": pooled_ordering_by_measure,
        "seed_ordering_valid": seed_ordering_valid,
        "seed_order_counts": seed_order_counts,
        "joint_seed_order_count": joint_seed_order_count,
        "joint_seed_order_required": 24,
        "product_seed_ordering_checks": product_seed_ordering_checks,
        "minimum_seed_order_count": 24,
        "states": state_rows,
    }
    return {**unsigned, "preflight_signature": _stable_sha256(unsigned)}


def run_target_discovery(
    *,
    output_dir: Path,
    manifest: Mapping[str, Any],
    points: Sequence[Mapping[str, Any]],
    lanes: Sequence[Lane],
    workers: int,
) -> dict[str, Any]:
    """Execute/reuse 93 J720 runs, validate states, and freeze target windows."""

    discovery_dir = output_dir.resolve() / "target_discovery"
    discovery_dir.mkdir(parents=True, exist_ok=True)
    progress_path = discovery_dir / "progress.json"
    jobs = [(point, seed) for point in points for seed in (TARGET_DESIGN_SEED, *SEEDS)]
    completed: dict[tuple[str, int], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []

    def write_progress(status: str) -> None:
        _write_json_atomic(
            progress_path,
            {
                "schema_version": f"{SCHEMA_VERSION}.target_discovery.progress.v1",
                "campaign_signature": manifest["campaign_signature"],
                "status": status,
                "planned": len(jobs),
                "completed": len(completed),
                "failed": len(failures),
                "running": max(
                    0, min(workers, len(jobs) - len(completed) - len(failures))
                ),
                "design_baselines_planned": len(OPERATING_POINT_IDS),
                "design_baselines_completed": sum(
                    seed == TARGET_DESIGN_SEED for _point_id, seed in completed
                ),
                "holdout_baselines_planned": len(OPERATING_POINT_IDS) * len(SEEDS),
                "holdout_baselines_completed": sum(
                    seed in SEEDS for _point_id, seed in completed
                ),
                "incident_probes_started": False,
                "updated_at": utc_now(),
            },
        )

    write_progress("running")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _execute_target_discovery_case,
                discovery_dir=discovery_dir,
                manifest=manifest,
                point=point,
                lanes=lanes,
                seed=seed,
            ): (str(point["operating_point_id"]), seed)
            for point, seed in jobs
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                completed[key] = future.result()
            except Exception as exc:  # pragma: no cover - exercised through mocks
                failures.append(
                    {"operating_point_id": key[0], "seed": key[1], "error": str(exc)}
                )
            write_progress("running")
    if failures:
        write_progress("failed")
        raise RuntimeError("Target discovery failed closed: " + json.dumps(failures))
    preflight = build_operating_point_preflight(
        manifest=manifest,
        points=points,
        discovery_evidence=completed,
    )
    preflight_path = discovery_dir / "operating_point_preflight.json"
    if preflight_path.is_file():
        existing_preflight = _read_json(preflight_path)
        if (
            existing_preflight.get("preflight_signature")
            != preflight["preflight_signature"]
        ):
            raise ValueError(
                "Existing operating-point preflight differs from deterministic discovery"
            )
    else:
        _write_json_atomic(preflight_path, preflight)
    manifest_path = output_dir.resolve() / "campaign_manifest.json"
    current_manifest = _read_json(manifest_path)
    preflight_manifest_fields = {
        "operating_point_preflight": str(preflight_path.resolve()),
        "operating_point_preflight_sha256": _sha256_file(preflight_path),
        "operating_point_preflight_signature": preflight["preflight_signature"],
        "operating_point_preflight_status": preflight["status"],
        "target_discovery_completed_at_utc": utc_now(),
    }
    if preflight["status"] != HOLDOUT_ACCEPTED_STATUS:
        # The 30-seed holdout is a hard gate.  Do not even construct the target
        # registry after rejection, and leave no signed path that a shard could
        # mistake for permission to start incident probes.
        current_manifest.update(
            {
                **preflight_manifest_fields,
                "target_discovery_status": "rejected",
                "target_registry": "",
                "target_registry_sha256": "",
                "target_registry_signature": "",
            }
        )
        _write_json_atomic(manifest_path, current_manifest)
        write_progress("failed_operating_point_preflight")
        raise RuntimeError(
            "Operating-point holdout rejected the calibrated states; no 42-day "
            f"target registry or incident probe was created. See {preflight_path}"
        )

    registry = build_cross_state_target_registry(
        manifest=manifest,
        points=points,
        lanes=lanes,
        shipment_rows_by_state_seed={
            key: value["shipment_rows"] for key, value in completed.items()
        },
    )
    registry_path = discovery_dir / "target_registry.json"
    if registry_path.is_file():
        existing = _read_json(registry_path)
        if existing.get("registry_signature") != registry["registry_signature"]:
            raise ValueError(
                "Existing target registry differs from deterministic discovery"
            )
    else:
        _write_json_atomic(registry_path, registry)
    registry_manifest_fields = {
        "target_registry": str(registry_path.resolve()),
        "target_registry_sha256": _sha256_file(registry_path),
        "target_registry_signature": registry["registry_signature"],
    }
    if registry.get("campaign_exposure_gate_passed") is not True:
        current_manifest.update(
            {
                **preflight_manifest_fields,
                **registry_manifest_fields,
                "target_discovery_status": "rejected",
                "target_exposure_comparability_status": "rejected",
            }
        )
        _write_json_atomic(manifest_path, current_manifest)
        write_progress("failed_target_exposure_comparability")
        raise RuntimeError(
            "The signed six-week target registry does not provide comparable "
            "exposure for every lane; no incident probe was started. See "
            f"{registry_path}"
        )
    current_manifest.update(
        {
            **preflight_manifest_fields,
            **registry_manifest_fields,
            "target_discovery_status": "complete",
            "target_exposure_comparability_status": "accepted",
        }
    )
    _write_json_atomic(manifest_path, current_manifest)
    write_progress("complete")
    return registry


def load_target_registry(
    *, output_dir: Path, manifest: Mapping[str, Any], lanes: Sequence[Lane]
) -> dict[str, Any]:
    if (
        manifest.get("target_discovery_status") != "complete"
        or manifest.get("operating_point_preflight_status") != HOLDOUT_ACCEPTED_STATUS
    ):
        raise ValueError(
            "Target discovery requires a signed 30-seed holdout validation"
        )
    preflight_path = Path(
        str(manifest.get("operating_point_preflight") or "")
    ).resolve()
    if not preflight_path.is_file() or _sha256_file(preflight_path) != str(
        manifest.get("operating_point_preflight_sha256") or ""
    ):
        raise ValueError(
            "Signed operating-point preflight evidence is missing or changed"
        )
    preflight = _read_json(preflight_path)
    unsigned_preflight = dict(preflight)
    preflight_signature = str(unsigned_preflight.pop("preflight_signature", ""))
    if (
        preflight.get("schema_version") != PREFLIGHT_SCHEMA_VERSION
        or preflight.get("contract_revision") != CONTRACT_REVISION
        or preflight.get("status") != HOLDOUT_ACCEPTED_STATUS
        or preflight.get("campaign_signature") != manifest.get("campaign_signature")
        or preflight.get("operating_points_input_status")
        != manifest.get("operating_points_input_status")
        or preflight.get("operating_points_artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or preflight.get("operating_points_calibration_plan_signature")
        != manifest.get("operating_points_calibration_plan_signature")
        or preflight.get("operating_points_selection_signature")
        != manifest.get("operating_points_selection_signature")
        or preflight.get("no_incident_probe_before_holdout_acceptance") is not True
        or preflight_signature != _stable_sha256(unsigned_preflight)
        or preflight_signature
        != str(manifest.get("operating_point_preflight_signature") or "")
    ):
        raise ValueError("Operating-point preflight evidence fails its signed contract")
    path = output_dir.resolve() / "target_discovery" / "target_registry.json"
    if not path.is_file():
        raise FileNotFoundError(
            "Cross-state target registry is missing; run --mode discover-targets first"
        )
    registry = _read_json(path)
    unsigned = dict(registry)
    signature = str(unsigned.pop("registry_signature", ""))
    lane_contracts = registry.get("lane_contracts") or []
    if (
        registry.get("schema_version") != f"{SCHEMA_VERSION}.target_registry.v4"
        or registry.get("campaign_signature") != manifest.get("campaign_signature")
        or registry.get("engine_sha256") != manifest.get("engine_sha256")
        or signature != _stable_sha256(unsigned)
        or registry.get("states") != list(OPERATING_POINT_IDS)
        or registry.get("seeds") != list(SEEDS)
        or registry.get("lanes") != [lane.lane_id for lane in lanes]
        or len(lane_contracts) != len(lanes)
        or {str(row.get("lane_id") or "") for row in lane_contracts}
        != {lane.lane_id for lane in lanes}
        or any(
            row.get("design_status") != "calibration_design_comparable_42d_window"
            or int(row.get("comparable_campaign_seed_count") or 0) < 24
            for row in lane_contracts
        )
        or registry.get("all_lane_design_windows_comparable") is not True
        or registry.get("all_lane_holdout_exposures_comparable") is not True
        or registry.get("campaign_exposure_gate_passed") is not True
        or registry.get("exposure_gate_failures") != []
    ):
        raise ValueError("Cross-state target registry fails its signed contract")
    expected = len(OPERATING_POINT_IDS) * len(SEEDS) * len(lanes)
    if len(registry.get("targets") or []) != expected:
        raise ValueError("Cross-state target registry target matrix is incomplete")
    return registry


def _tagged_incident_shipments(
    rows: Sequence[Mapping[str, Any]], *, lane: Lane, event_id: str
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if _lane_matches(row, lane)
        and event_id in _event_tokens(row.get("risk_event_ids"))
        and _as_float(row.get("pulled_qty"), 0.0) > 1e-12
    ]


def _incident_horizon_from_trace(
    *, target: Mapping[str, Any], tagged_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    impact_start = int(target["impact_window_start_day"])
    impact_end = int(target["impact_window_end_day"])
    if tagged_rows:
        arrivals = [_as_int(row.get("arrival_day"), -1) for row in tagged_rows]
        if min(arrivals) < 0:
            raise ValueError("Tagged incident shipment lacks an arrival day")
        baseline_first_arrival = _as_int(
            target.get("target_arrival_day"), min(arrivals)
        )
        causal_start = min(baseline_first_arrival, min(arrivals))
        latest = max(arrivals)
        causal_end = latest + MIN_RECOVERY_OBSERVATION_DAYS - 1
        causal_defined = True
    else:
        causal_start = impact_start
        causal_end = impact_end
        latest = -1
        causal_defined = False
    required_days = max(
        MINIMUM_CASE_DAYS,
        impact_end + 1,
        causal_end + 1,
    )
    recovery_in_envelope = max(0, impact_end - latest + 1) if latest >= 0 else 0
    return {
        "impact_window_start_day": impact_start,
        "impact_window_end_day": impact_end,
        "impact_window_days": impact_end - impact_start + 1,
        "impact_window_fully_observed": True,
        "causal_window_start_day": causal_start,
        "causal_window_end_day": causal_end,
        "causal_window_days": causal_end - causal_start + 1,
        "causal_window_defined": causal_defined,
        "causal_window_fully_observed": True,
        "target_latest_stressed_arrival_day": latest,
        "required_simulation_days": required_days,
        "recovery_observation_days_after_latest_stressed_arrival": (
            required_days - latest if latest >= 0 else 0
        ),
        "recovery_observation_days_within_impact_window": recovery_in_envelope,
        "recovery_fully_observed_within_360": (
            latest >= 0 and recovery_in_envelope >= MIN_RECOVERY_OBSERVATION_DAYS
        ),
    }


def _shipment_trace_signature(
    rows: Sequence[Mapping[str, Any]],
    *,
    end_day_exclusive: int = STATE_EVALUATION_DAYS,
) -> str:
    fields = (
        "shipment_id",
        "risk_decision_day",
        "risk_event_ids",
        "src_node_id",
        "dst_node_id",
        "item_id",
        "edge_id",
        "pulled_qty",
        "shipped_qty",
        "lead_days",
        "arrival_day",
        "reliability",
    )
    projection = [
        {field: row.get(field, "") for field in fields}
        for row in rows
        if 0 <= _as_int(row.get("risk_decision_day"), -1) < end_day_exclusive
    ]
    projection.sort(
        key=lambda row: (
            _as_int(row.get("risk_decision_day"), -1),
            str(row.get("src_node_id") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("edge_id") or ""),
            str(row.get("shipment_id") or ""),
        )
    )
    return _stable_sha256(projection)


def _probe_checkpoint_path(shard_dir: Path, key: str, horizon: int) -> Path:
    return shard_dir / "incident_probe_checkpoints" / f"{key}__h{horizon}.json"


def _validate_probe_checkpoint(
    payload: Mapping[str, Any],
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    key: str,
    probe_contract_signature: str,
) -> None:
    unsigned = dict(payload)
    signature = str(unsigned.pop("checkpoint_signature", ""))
    attempted = payload.get("attempted_horizons")
    try:
        horizon = int(payload.get("simulation_days"))
        next_horizon = int(payload.get("next_required_simulation_days"))
        attempted_horizons = [int(value) for value in attempted]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid incident-probe checkpoint counters: {key}") from exc
    case_dir = Path(str(payload.get("case_dir") or "")).resolve()
    expected_case_dir = (shard_dir / "cases" / f"probe__{key}__h{horizon}").resolve()
    if (
        payload.get("schema_version") != PROBE_CHECKPOINT_SCHEMA_VERSION
        or payload.get("campaign_signature") != manifest.get("campaign_signature")
        or payload.get("probe_contract_signature") != probe_contract_signature
        or payload.get("operating_point_id") != point.get("operating_point_id")
        or int(payload.get("seed", -1)) != seed
        or payload.get("lane_id") != lane.lane_id
        or payload.get("mechanism") != mechanism.key
        or payload.get("case_key") != key
        or case_dir != expected_case_dir
        or not attempted_horizons
        or attempted_horizons[-1] != horizon
        or attempted_horizons != sorted(set(attempted_horizons))
        or next_horizon <= horizon
        or not str(payload.get("J0_J719_shipment_trace_signature") or "")
        or not isinstance(payload.get("incident_window"), Mapping)
        or not signature
        or signature != _stable_sha256(unsigned)
    ):
        raise ValueError(f"Incident-probe checkpoint fails closed: {key}/h{horizon}")


def _prune_checkpoint_case(
    *, checkpoint_path: Path, payload: Mapping[str, Any], shard_dir: Path
) -> dict[str, Any]:
    case_dir = Path(str(payload.get("case_dir") or "")).resolve()
    cases_root = (shard_dir / "cases").resolve()
    if case_dir.parent != cases_root or not case_dir.name.startswith("probe__"):
        raise RuntimeError(f"Unsafe checkpoint case-prune target: {case_dir}")
    removed = (
        campaign_core.prune_case_artifacts(case_dir) or [] if case_dir.exists() else []
    )
    remaining = campaign_core.retention_targets(case_dir)
    if remaining:
        raise RuntimeError(
            "Checkpoint case still contains bulky generated directories: "
            + ", ".join(path.name for path in remaining)
        )
    updated = dict(payload)
    updated["case_artifacts_pruned"] = True
    updated["case_artifacts_removed"] = sorted(
        set(str(value) for value in updated.get("case_artifacts_removed") or [])
        | set(removed)
    )
    updated["case_artifacts_pruned_at_utc"] = utc_now()
    updated = _signed_document(updated, signature_field="checkpoint_signature")
    _write_json_atomic(checkpoint_path, updated)
    return updated


def _resume_probe_checkpoint(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    key: str,
    probe_contract_signature: str,
) -> dict[str, Any] | None:
    checkpoint_dir = shard_dir / "incident_probe_checkpoints"
    if not checkpoint_dir.is_dir():
        return None
    checkpoints: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(checkpoint_dir.glob(f"{key}__h*.json")):
        payload = _read_json(path)
        _validate_probe_checkpoint(
            payload,
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            lane=lane,
            mechanism=mechanism,
            seed=seed,
            key=key,
            probe_contract_signature=probe_contract_signature,
        )
        expected_path = _probe_checkpoint_path(
            shard_dir, key, int(payload["simulation_days"])
        ).resolve()
        if path.resolve() != expected_path:
            raise ValueError(f"Incident-probe checkpoint path differs: {path}")
        if payload.get("case_artifacts_pruned") is not True:
            payload = _prune_checkpoint_case(
                checkpoint_path=path,
                payload=payload,
                shard_dir=shard_dir,
            )
        checkpoints.append((path, payload))
    if not checkpoints:
        return None
    checkpoints.sort(key=lambda item: len(item[1]["attempted_horizons"]))
    previous: list[int] = []
    for _path, payload in checkpoints:
        attempted = [int(value) for value in payload["attempted_horizons"]]
        if previous and attempted[:-1] != previous:
            raise ValueError(f"Incident-probe checkpoint chain branches: {key}")
        previous = attempted
    return checkpoints[-1][1]


def _persist_probe_extension_checkpoint(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    key: str,
    probe_contract_signature: str,
    case_dir: Path,
    horizon: int,
    horizons: Sequence[int],
    trace_signature: str,
    horizon_contract: Mapping[str, Any],
    required_days: int,
) -> dict[str, Any]:
    checkpoint_path = _probe_checkpoint_path(shard_dir, key, horizon)
    unsigned = {
        "schema_version": PROBE_CHECKPOINT_SCHEMA_VERSION,
        "campaign_signature": manifest["campaign_signature"],
        "probe_contract_signature": probe_contract_signature,
        "operating_point_id": point["operating_point_id"],
        "seed": int(seed),
        "lane_id": lane.lane_id,
        "mechanism": mechanism.key,
        "case_key": key,
        "case_dir": str(case_dir.resolve()),
        "simulation_days": int(horizon),
        "attempted_horizons": [int(value) for value in horizons],
        "J0_J719_shipment_trace_signature": trace_signature,
        "next_required_simulation_days": int(required_days),
        "incident_window": dict(horizon_contract),
        "case_artifacts_pruned": False,
        "case_artifacts_removed": [],
        "case_artifacts_pruned_at_utc": "",
        "created_at_utc": utc_now(),
    }
    checkpoint = _signed_document(unsigned, signature_field="checkpoint_signature")
    if checkpoint_path.is_file():
        existing = _read_json(checkpoint_path)
        _validate_probe_checkpoint(
            existing,
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            lane=lane,
            mechanism=mechanism,
            seed=seed,
            key=key,
            probe_contract_signature=probe_contract_signature,
        )
        invariant_fields = (
            "simulation_days",
            "attempted_horizons",
            "J0_J719_shipment_trace_signature",
            "next_required_simulation_days",
            "incident_window",
        )
        if any(
            existing.get(field) != checkpoint.get(field) for field in invariant_fields
        ):
            raise ValueError(f"Incident-probe checkpoint changed: {checkpoint_path}")
        checkpoint = existing
    else:
        _write_json_atomic(checkpoint_path, checkpoint)
    if checkpoint.get("case_artifacts_pruned") is not True:
        checkpoint = _prune_checkpoint_case(
            checkpoint_path=checkpoint_path,
            payload=checkpoint,
            shard_dir=shard_dir,
        )
    return checkpoint


def _prepare_incident_probe(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    registered_target: Mapping[str, Any],
) -> dict[str, Any]:
    key = _case_key(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        stage="incident",
        lane_id=lane.lane_id,
        mechanism=mechanism.key,
    )
    probe_path = shard_dir / "incident_probes" / f"{key}.json"
    risk_row = build_risk_row(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        lane=lane,
        mechanism=mechanism,
        target=registered_target,
    )
    risk_csv = shard_dir / "inputs" / "risk_events" / f"{key}.csv"
    campaign_core.write_risk_csv(risk_csv, [risk_row])
    probe_contract_signature = _stable_sha256(
        {
            "campaign_signature": manifest["campaign_signature"],
            "target_registry_signature": manifest["target_registry_signature"],
            "point_id": point["operating_point_id"],
            "seed": seed,
            "lane": asdict(lane),
            "mechanism": asdict(mechanism),
            "target_window_start_day": registered_target["target_window_start_day"],
            "target_window_end_day": registered_target["target_window_end_day"],
            "risk_csv_sha256": _sha256_file(risk_csv),
        }
    )
    if probe_path.is_file():
        payload = _read_json(probe_path)
        unsigned = dict(payload)
        evidence_signature = unsigned.pop("probe_evidence_signature", "")
        if (
            payload.get("probe_contract_signature") != probe_contract_signature
            or evidence_signature != _stable_sha256(unsigned)
            or not isinstance(payload.get("metrics"), Mapping)
            or not isinstance(payload.get("incident_proof"), Mapping)
            or not isinstance(payload.get("validation_errors"), list)
        ):
            raise ValueError(f"Incident probe evidence fails closed: {probe_path}")
        if payload.get("case_artifacts_pruned") is not True:
            case_dir = Path(str(payload.get("case_dir") or "")).resolve()
            cases_root = (shard_dir / "cases").resolve()
            if not case_dir.is_relative_to(cases_root):
                raise ValueError(f"Incident probe case path escapes shard: {case_dir}")
            if case_dir.exists():
                campaign_core.prune_case_artifacts(case_dir)
            payload["case_artifacts_pruned"] = True
            payload["case_artifacts_pruned_at_utc"] = utc_now()
            payload["probe_evidence_signature"] = _stable_sha256(
                {
                    field: value
                    for field, value in payload.items()
                    if field != "probe_evidence_signature"
                }
            )
            _write_json_atomic(probe_path, payload)
        return payload
    initial_days = max(
        MINIMUM_CASE_DAYS,
        int(registered_target.get("required_simulation_days") or MINIMUM_CASE_DAYS),
    )
    checkpoint = _resume_probe_checkpoint(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        lane=lane,
        mechanism=mechanism,
        seed=seed,
        key=key,
        probe_contract_signature=probe_contract_signature,
    )
    if checkpoint is None:
        previous_trace_signature = ""
        horizons: list[int] = []
        horizon = initial_days
    else:
        previous_trace_signature = str(checkpoint["J0_J719_shipment_trace_signature"])
        horizons = [int(value) for value in checkpoint["attempted_horizons"]]
        horizon = int(checkpoint["next_required_simulation_days"])
    final_case_dir: Path | None = None
    final_rows: list[dict[str, str]] = []
    for _iteration in range(len(horizons) + 1, 5):
        probe_key = f"probe__{key}__h{horizon}"
        case_dir = _run_engine(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=probe_key,
            seed=seed,
            risk_csv=risk_csv,
            simulation_days=horizon,
        )
        shipment_rows = protocol.read_csv_rows(
            case_dir / "data" / "production_supplier_shipments_daily.csv"
        )
        trace_signature = _shipment_trace_signature(shipment_rows)
        if previous_trace_signature and trace_signature != previous_trace_signature:
            raise RuntimeError(
                f"J0-J719 shipment trace changed after horizon extension for {key}"
            )
        tagged = _tagged_incident_shipments(
            shipment_rows, lane=lane, event_id=str(risk_row["event_id"])
        )
        horizon_contract = _incident_horizon_from_trace(
            target=registered_target, tagged_rows=tagged
        )
        required_days = int(horizon_contract["required_simulation_days"])
        horizons.append(horizon)
        if required_days <= horizon:
            final_case_dir = case_dir
            final_rows = shipment_rows
            break
        _persist_probe_extension_checkpoint(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            lane=lane,
            mechanism=mechanism,
            seed=seed,
            key=key,
            probe_contract_signature=probe_contract_signature,
            case_dir=case_dir,
            horizon=horizon,
            horizons=horizons,
            trace_signature=trace_signature,
            horizon_contract=horizon_contract,
            required_days=required_days,
        )
        previous_trace_signature = trace_signature
        horizon = required_days
    if final_case_dir is None:
        raise RuntimeError(f"Adaptive incident horizon did not converge for {key}")
    tagged = _tagged_incident_shipments(
        final_rows, lane=lane, event_id=str(risk_row["event_id"])
    )
    horizon_contract = _incident_horizon_from_trace(
        target=registered_target, tagged_rows=tagged
    )
    minimum_required_days = int(horizon_contract["required_simulation_days"])
    horizon_contract["minimum_required_simulation_days"] = minimum_required_days
    horizon_contract["required_simulation_days"] = horizon
    horizon_contract["impact_window_fully_observed"] = (
        int(horizon_contract["impact_window_end_day"]) < horizon
    )
    horizon_contract["causal_window_fully_observed"] = (
        int(horizon_contract["causal_window_end_day"]) < horizon
    )
    horizon_contract["observable_days_after_target_decision"] = horizon - int(
        registered_target["target_window_start_day"]
    )
    causal_start = int(horizon_contract["causal_window_start_day"])
    horizon_contract["observable_days_after_first_expected_arrival"] = (
        horizon - causal_start if horizon_contract["causal_window_defined"] else ""
    )
    latest_stressed = int(horizon_contract["target_latest_stressed_arrival_day"])
    horizon_contract["recovery_observation_days_after_latest_stressed_arrival"] = (
        horizon - latest_stressed if latest_stressed >= 0 else 0
    )
    final_target = {**dict(registered_target), **horizon_contract}
    metrics, shipment_rows, applied_rows, extraction_errors, daily_context = (
        _extract_metrics(
            case_dir=final_case_dir,
            manifest=manifest,
            point=point,
            risk_csv=risk_csv,
            expected_event_id=str(risk_row["event_id"]),
            simulation_days=horizon,
        )
    )
    metrics["impact_window_metrics"] = _window_metrics(
        service_rows=daily_context["service_rows"],
        production_rows=daily_context["production_rows"],
        start_day=int(final_target["impact_window_start_day"]),
        end_day=int(final_target["impact_window_end_day"]),
    )
    metrics["causal_window_metrics"] = _window_metrics(
        service_rows=daily_context["service_rows"],
        production_rows=daily_context["production_rows"],
        start_day=int(final_target["causal_window_start_day"]),
        end_day=int(final_target["causal_window_end_day"]),
    )
    proof, trace_errors = validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=final_target,
        risk_row=risk_row,
        shipment_rows=shipment_rows,
        applied_rows=applied_rows,
        simulation_days=horizon,
    )
    incident_pre_trace = _shipment_trace_signature(
        shipment_rows,
        end_day_exclusive=int(final_target["target_window_start_day"]),
    )
    proof["incident_pre_incident_shipment_trace_sha256"] = incident_pre_trace
    validation_errors = [*extraction_errors, *trace_errors]
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.incident_probe.v1",
        "campaign_signature": manifest["campaign_signature"],
        "probe_contract_signature": probe_contract_signature,
        "operating_point_id": point["operating_point_id"],
        "seed": seed,
        "lane_id": lane.lane_id,
        "mechanism": mechanism.key,
        "case_dir": str(final_case_dir.resolve()),
        "risk_csv": str(risk_csv.resolve()),
        "risk_csv_sha256": _sha256_file(risk_csv),
        "attempted_horizons": horizons,
        "final_simulation_days": horizon,
        "J0_J719_shipment_trace_signature": _shipment_trace_signature(final_rows),
        "tagged_shipment_count": len(tagged),
        "incident_window": horizon_contract,
        "metrics": metrics,
        "incident_proof": proof,
        "incident_pre_incident_shipment_trace_sha256": incident_pre_trace,
        "validation_errors": validation_errors,
        "risk_row": risk_row,
        "case_artifacts_pruned": False,
        "case_artifacts_pruned_at_utc": "",
        "created_at_utc": utc_now(),
    }
    payload = {**unsigned, "probe_evidence_signature": _stable_sha256(unsigned)}
    _write_json_atomic(probe_path, payload)
    campaign_core.prune_case_artifacts(final_case_dir)
    payload["case_artifacts_pruned"] = True
    payload["case_artifacts_pruned_at_utc"] = utc_now()
    payload["probe_evidence_signature"] = _stable_sha256(
        {
            field: value
            for field, value in payload.items()
            if field != "probe_evidence_signature"
        }
    )
    _write_json_atomic(probe_path, payload)
    return payload


def _execute_baseline(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lanes: Sequence[Lane],
    seed: int,
    reuse_roots: Sequence[Path],
    registered_targets: Sequence[Mapping[str, Any]],
    simulation_days: int,
) -> dict[str, Any]:
    key = _case_key(
        point_id=str(point["operating_point_id"]), seed=seed, stage="baseline"
    )
    adaptive_contract_signature = _stable_sha256(
        [
            {
                "lane_id": target["lane_id"],
                "incident_windows": target.get("incident_windows") or {},
            }
            for target in registered_targets
        ]
    )
    signature = _case_signature(
        manifest=manifest,
        point=point,
        seed=seed,
        stage="baseline",
        simulation_days=simulation_days,
        adaptive_contract_signature=adaptive_contract_signature,
    )
    existing = _load_or_reuse_evidence(
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=key,
        case_signature=signature,
        reuse_roots=reuse_roots,
    )
    if existing is not None:
        return existing
    case_dir = _run_engine(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        case_key=key,
        seed=seed,
        risk_csv=None,
        simulation_days=simulation_days,
    )
    metrics, shipment_rows, _applied, errors, daily_context = _extract_metrics(
        case_dir=case_dir,
        manifest=manifest,
        point=point,
        risk_csv=None,
        expected_event_id=None,
        simulation_days=simulation_days,
    )
    registered_by_lane = {
        str(target.get("lane_id") or ""): dict(target) for target in registered_targets
    }
    if set(registered_by_lane) != {lane.lane_id for lane in lanes}:
        raise ValueError("Registered baseline target matrix is incomplete")
    targets: list[dict[str, Any]] = []
    invariant_fields = (
        "target_window_start_day",
        "target_window_end_day",
        "target_window_days",
        "target_active_decision_days",
        "target_shipment_count",
        "target_shipment_ids",
        "target_planned_qty",
        "target_expected_delivered_qty",
        "target_latest_baseline_arrival_day",
        "target_latest_stressed_arrival_day",
        "required_simulation_days",
    )
    metadata_fields = (
        "cross_state_match_status",
        "cross_state_common_day_found",
        "cross_state_quantity_ratio",
        "cross_state_match_threshold_ratio",
        "state_comparison_valid",
        "state_exposure_max_decision_day",
        "state_exposure_max_window_start_day",
        "state_exposure_max_group_qty",
        "cross_state_matched_min_group_qty",
        "cross_state_matched_max_group_qty",
        "cross_state_matched_quantities_json",
        "target_selected_independently_by_operating_point",
    )
    for lane in lanes:
        registered = registered_by_lane[lane.lane_id]
        selected = select_unique_reference_shipment(
            shipment_rows,
            lane=lane,
            days=simulation_days,
            forced_decision_day=int(registered["target_window_start_day"]),
            target_window_days=INCIDENT_DISRUPTION_DAYS,
            state_match_metadata={
                key: registered.get(key, "") for key in metadata_fields
            },
        )
        mismatches = [
            field
            for field in invariant_fields
            if selected.get(field) != registered.get(field)
        ]
        if mismatches:
            selected["target_status"] = (
                "not_applicable_discovery_extended_trace_mismatch"
            )
            selected["reason"] = (
                "J0-J719 target trace differs between discovery and extended baseline: "
                + ", ".join(mismatches)
            )
            errors.append(f"{lane.lane_id}: {selected['reason']}")
        selected["incident_windows"] = dict(registered.get("incident_windows") or {})
        selected["baseline_pre_incident_shipment_trace_sha256"] = (
            _shipment_trace_signature(
                shipment_rows,
                end_day_exclusive=int(selected["target_window_start_day"]),
            )
        )
        targets.append(
            _target_with_lane_fields(
                selected,
                manifest=manifest,
                shard_id=str(manifest.get("active_shard_id") or ""),
                point=point,
                seed=seed,
                lane=lane,
                simulation_days=simulation_days,
            )
        )
    for target in targets:
        if str(target.get("target_status") or "").startswith("identified_"):
            target["baseline_impact_metrics"] = _window_metrics(
                service_rows=daily_context["service_rows"],
                production_rows=daily_context["production_rows"],
                start_day=int(target["impact_window_start_day"]),
                end_day=int(target["impact_window_end_day"]),
            )
            target["baseline_causal_metrics"] = _window_metrics(
                service_rows=daily_context["service_rows"],
                production_rows=daily_context["production_rows"],
                start_day=int(target["causal_window_start_day"]),
                end_day=int(target["causal_window_end_day"]),
            )
            target["baseline_causal_metrics_by_mechanism"] = {
                mechanism_key: _window_metrics(
                    service_rows=daily_context["service_rows"],
                    production_rows=daily_context["production_rows"],
                    start_day=int(window["causal_window_start_day"]),
                    end_day=int(window["causal_window_end_day"]),
                )
                for mechanism_key, window in (
                    target.get("incident_windows") or {}
                ).items()
            }
    evidence = _base_evidence(
        manifest=manifest,
        shard_id=str(manifest.get("active_shard_id") or ""),
        point=point,
        seed=seed,
        stage="baseline",
        case_key=key,
        case_signature=signature,
        simulation_days=simulation_days,
    )
    evidence.update(
        {
            "status": "valid" if not errors else "invalid",
            "valid": not errors,
            "validation_errors": errors,
            "metrics": metrics,
            "shipment_targets": targets,
            "baseline_case_signature": signature,
            "run_dir": str(case_dir),
        }
    )
    _persist_evidence(_evidence_path(shard_dir, key), evidence)
    if evidence["valid"]:
        campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _execute_incident(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    target: Mapping[str, Any],
    baseline_evidence: Mapping[str, Any],
    reuse_roots: Sequence[Path],
    prepared_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    simulation_days = max(
        MINIMUM_CASE_DAYS,
        int(target.get("required_simulation_days") or MINIMUM_CASE_DAYS),
    )
    key = _case_key(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        stage="incident",
        lane_id=lane.lane_id,
        mechanism=mechanism.key,
    )
    signature = _case_signature(
        manifest=manifest,
        point=point,
        seed=seed,
        stage="incident",
        lane=lane,
        mechanism=mechanism,
        target=target,
        simulation_days=simulation_days,
    )
    existing = _load_or_reuse_evidence(
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=key,
        case_signature=signature,
        reuse_roots=reuse_roots,
    )
    if existing is not None:
        return existing
    base = _base_evidence(
        manifest=manifest,
        shard_id=str(manifest.get("active_shard_id") or ""),
        point=point,
        seed=seed,
        stage="incident",
        case_key=key,
        case_signature=signature,
        simulation_days=simulation_days,
    )
    base.update(
        {
            "lane": asdict(lane),
            "mechanism": asdict(mechanism),
            "target": dict(target),
            "baseline_case_signature": baseline_evidence["case_signature"],
        }
    )
    if not str(target.get("target_status") or "").startswith("identified_"):
        evidence = {
            **base,
            "status": "not_applicable",
            "valid": False,
            "validation_errors": [str(target.get("reason") or "unique target absent")],
            "metrics": {},
            "incident_proof": {"incident_physically_exercised": False},
            "run_dir": "",
        }
        return _persist_evidence(_evidence_path(shard_dir, key), evidence)
    risk_row = build_risk_row(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    risk_csv = shard_dir / "inputs" / "risk_events" / f"{key}.csv"
    campaign_core.write_risk_csv(risk_csv, [risk_row])
    if prepared_probe is not None:
        if (
            int(prepared_probe.get("final_simulation_days") or -1) != simulation_days
            or str(prepared_probe.get("risk_csv_sha256") or "")
            != _sha256_file(risk_csv)
            or prepared_probe.get("case_artifacts_pruned") is not True
            or prepared_probe.get("risk_row") != risk_row
            or prepared_probe.get("campaign_signature")
            != manifest.get("campaign_signature")
            or prepared_probe.get("operating_point_id")
            != point.get("operating_point_id")
            or int(prepared_probe.get("seed") or -1) != seed
            or prepared_probe.get("lane_id") != lane.lane_id
            or prepared_probe.get("mechanism") != mechanism.key
        ):
            raise ValueError(f"Prepared incident probe contract differs for {key}")
        case_dir: Path | None = None
        metrics = dict(prepared_probe.get("metrics") or {})
        errors = [str(value) for value in prepared_probe.get("validation_errors") or []]
        proof = dict(prepared_probe.get("incident_proof") or {})
        incident_pre_incident_trace = str(
            prepared_probe.get("incident_pre_incident_shipment_trace_sha256") or ""
        )
        if not metrics or not proof or not incident_pre_incident_trace:
            raise ValueError(f"Prepared incident probe payload is incomplete for {key}")
        if int(metrics.get("simulation_days") or -1) != simulation_days:
            errors.append(
                "prepared incident metrics horizon differs from probe horizon"
            )
    else:
        case_dir = _run_engine(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=key,
            seed=seed,
            risk_csv=risk_csv,
            simulation_days=simulation_days,
        )
        metrics, shipment_rows, applied_rows, errors, daily_context = _extract_metrics(
            case_dir=case_dir,
            manifest=manifest,
            point=point,
            risk_csv=risk_csv,
            expected_event_id=str(risk_row["event_id"]),
            simulation_days=simulation_days,
        )
        metrics["impact_window_metrics"] = _window_metrics(
            service_rows=daily_context["service_rows"],
            production_rows=daily_context["production_rows"],
            start_day=int(target["impact_window_start_day"]),
            end_day=int(target["impact_window_end_day"]),
        )
        metrics["causal_window_metrics"] = _window_metrics(
            service_rows=daily_context["service_rows"],
            production_rows=daily_context["production_rows"],
            start_day=int(target["causal_window_start_day"]),
            end_day=int(target["causal_window_end_day"]),
        )
        proof, trace_errors = validate_incident_trace(
            mechanism=mechanism,
            lane=lane,
            target=target,
            risk_row=risk_row,
            shipment_rows=shipment_rows,
            applied_rows=applied_rows,
            simulation_days=simulation_days,
        )
        errors.extend(trace_errors)
        incident_pre_incident_trace = _shipment_trace_signature(
            shipment_rows,
            end_day_exclusive=int(target["target_window_start_day"]),
        )
    expected_pre_incident_trace = str(
        target.get("baseline_pre_incident_shipment_trace_sha256") or ""
    )
    pre_incident_trace_match = bool(expected_pre_incident_trace) and (
        expected_pre_incident_trace == incident_pre_incident_trace
    )
    if not expected_pre_incident_trace:
        errors.append("paired baseline pre-incident shipment trace is missing")
    elif not pre_incident_trace_match:
        errors.append("incident shipment trace diverges before the disruption window")
    baseline_impact = target.get("baseline_impact_metrics") or {}
    incident_impact = metrics["impact_window_metrics"]
    if not baseline_impact:
        errors.append("paired baseline impact-window metrics are missing")
    else:
        for field in ("start_day", "end_day", "day_count"):
            if baseline_impact.get(field) != incident_impact.get(field):
                errors.append(f"paired impact-window {field} mismatch")
        for field in (
            "demand_qty_268091",
            "demand_qty_268967",
            "demand_qty_global",
        ):
            if not math.isclose(
                _as_float(baseline_impact.get(field)),
                _as_float(incident_impact.get(field)),
                rel_tol=1e-12,
                abs_tol=TARGET_QUANTITY_TOLERANCE,
            ):
                errors.append(f"paired impact-window {field} changed")
    baseline_causal = target.get("baseline_causal_metrics") or {}
    incident_causal = metrics["causal_window_metrics"]
    if not baseline_causal:
        errors.append("paired baseline causal-window metrics are missing")
    else:
        for field in ("start_day", "end_day", "day_count"):
            if baseline_causal.get(field) != incident_causal.get(field):
                errors.append(f"paired causal-window {field} mismatch")
        for field in (
            "demand_qty_268091",
            "demand_qty_268967",
            "demand_qty_global",
        ):
            if not math.isclose(
                _as_float(baseline_causal.get(field)),
                _as_float(incident_causal.get(field)),
                rel_tol=1e-12,
                abs_tol=TARGET_QUANTITY_TOLERANCE,
            ):
                errors.append(f"paired causal-window {field} changed")
    proof["baseline_pre_incident_shipment_trace_sha256"] = expected_pre_incident_trace
    proof["incident_pre_incident_shipment_trace_sha256"] = incident_pre_incident_trace
    proof["pre_incident_shipment_trace_match"] = pre_incident_trace_match
    zero_exposure = (
        str(target.get("target_status") or "")
        == "identified_registered_window_no_positive_flow"
    )
    if zero_exposure:
        for baseline_window, incident_window, label in (
            (baseline_impact, incident_impact, "impact"),
            (baseline_causal, incident_causal, "causal"),
        ):
            for field in (
                "service_268091_pct",
                "service_268967_pct",
                "service_global_pct",
                "backlog_qty_days_global",
                "max_backlog_qty_global",
                "production_released_268091_qty",
                "production_released_268967_qty",
            ):
                if not math.isclose(
                    _as_float(baseline_window.get(field)),
                    _as_float(incident_window.get(field)),
                    rel_tol=0.0,
                    abs_tol=TARGET_QUANTITY_TOLERANCE,
                ):
                    errors.append(f"zero-exposure {label} metric changed: {field}")
    if metrics.get("warmup_core_state_sha256") != (
        baseline_evidence.get("metrics") or {}
    ).get("warmup_core_state_sha256"):
        errors.append("incident and baseline warmup core-state hashes differ")
    proof["incident_physically_exercised"] = (
        bool(proof.get("incident_physically_exercised")) and not errors
    )
    evidence = {
        **base,
        "status": (
            "valid_no_exposure"
            if zero_exposure and not errors
            else ("valid" if not errors else "invalid")
        ),
        "valid": not errors,
        "validation_errors": errors,
        "metrics": metrics,
        "incident_proof": proof,
        "risk_row": risk_row,
        "risk_csv_sha256": _sha256_file(risk_csv),
        "prepared_probe_evidence_signature": (
            str(prepared_probe.get("probe_evidence_signature") or "")
            if prepared_probe is not None
            else ""
        ),
        "run_dir": str(case_dir) if case_dir is not None else "",
    }
    _persist_evidence(_evidence_path(shard_dir, key), evidence)
    if evidence["valid"] and case_dir is not None:
        campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _target_by_lane(baseline: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    targets = [dict(row) for row in baseline.get("shipment_targets") or []]
    by_lane = {str(row.get("lane_id") or ""): row for row in targets}
    if len(by_lane) != len(targets):
        raise ValueError("Duplicate lane target in baseline evidence")
    return by_lane


def _target_for_mechanism(
    target: Mapping[str, Any], mechanism_key: str
) -> dict[str, Any]:
    result = dict(target)
    incident_windows = target.get("incident_windows") or {}
    if mechanism_key not in incident_windows:
        raise ValueError(f"Missing adaptive incident window for {mechanism_key}")
    result.update(dict(incident_windows[mechanism_key]))
    baseline_by_mechanism = target.get("baseline_causal_metrics_by_mechanism") or {}
    if mechanism_key not in baseline_by_mechanism:
        raise ValueError(f"Missing baseline causal metrics for {mechanism_key}")
    result["baseline_causal_metrics"] = dict(baseline_by_mechanism[mechanism_key])
    return result


def _flatten_metric_row(
    evidence: Mapping[str, Any],
    *,
    baseline_by_signature: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    metrics = evidence.get("metrics") or {}
    lane = evidence.get("lane") or {}
    mechanism = evidence.get("mechanism") or {}
    target = evidence.get("target") or {}
    proof = evidence.get("incident_proof") or {}
    baseline_signature = str(
        evidence.get("baseline_case_signature") or evidence.get("case_signature") or ""
    )
    is_incident = evidence.get("stage") == "incident"
    baseline_impact = target.get("baseline_impact_metrics") or {}
    impact = metrics.get("impact_window_metrics") or {}
    baseline_causal = target.get("baseline_causal_metrics") or {}
    causal = metrics.get("causal_window_metrics") or {}
    fed_product = str(
        lane.get("target_product_id") or target.get("target_product_id") or ""
    )

    def loss(before: Mapping[str, Any], after: Mapping[str, Any], field: str) -> Any:
        first = _as_float(before.get(field))
        second = _as_float(after.get(field))
        return first - second if math.isfinite(first) and math.isfinite(second) else ""

    def increase(
        before: Mapping[str, Any], after: Mapping[str, Any], field: str
    ) -> Any:
        first = _as_float(before.get(field))
        second = _as_float(after.get(field))
        return second - first if math.isfinite(first) and math.isfinite(second) else ""

    def share(numerator: Any, denominator: Any) -> Any:
        top = _as_float(numerator)
        bottom = _as_float(denominator)
        if not math.isfinite(top) or not math.isfinite(bottom):
            return ""
        if bottom <= 1e-12:
            return 0.0 if abs(top) <= TARGET_QUANTITY_TOLERANCE else ""
        return top / bottom

    def relative_load(numerator: Any, denominator: Any, day_count: Any) -> Any:
        demand = _as_float(denominator)
        days = _as_float(day_count)
        if not math.isfinite(demand) or not math.isfinite(days):
            return ""
        return share(numerator, demand * days)

    impact_service_losses = {
        product: loss(baseline_impact, impact, f"service_{product}_pct")
        for product in TARGET_PRODUCTS
    }
    impact_global_service_loss = loss(baseline_impact, impact, "service_global_pct")
    causal_service_losses = {
        product: loss(baseline_causal, causal, f"service_{product}_pct")
        for product in TARGET_PRODUCTS
    }
    causal_global_service_loss = loss(baseline_causal, causal, "service_global_pct")
    mechanism_key = str(mechanism.get("key") or "baseline")
    target_quantity = _as_float(target.get("target_expected_delivered_qty"), 0.0)
    affected_pulled = _as_float(proof.get("incident_affected_pulled_qty"), 0.0)
    if is_incident and mechanism_key == "planned_delivery_shortfall":
        reference_dose_qty: Any = 0.5 * target_quantity
        reference_dose_qty_days: Any = ""
        effective_dose_qty: Any = _as_float(proof.get("quantity_shortfall_qty"), 0.0)
        effective_dose_qty_days: Any = ""
    elif is_incident and mechanism_key == "transport_delay":
        reference_dose_qty = ""
        reference_dose_qty_days = 120.0 * target_quantity
        effective_dose_qty = ""
        effective_dose_qty_days = 120.0 * affected_pulled
    else:
        reference_dose_qty = 0.0
        reference_dose_qty_days = 0.0
        effective_dose_qty = 0.0
        effective_dose_qty_days = 0.0

    return {
        "schema_version": evidence.get("schema_version", ""),
        "campaign_signature": evidence.get("campaign_signature", ""),
        "engine_sha256": evidence.get("engine_sha256", ""),
        "shard_id": evidence.get("shard_id", ""),
        "shard_index": evidence.get("shard_index", ""),
        "shard_count": evidence.get("shard_count", ""),
        "operating_point_id": evidence.get("operating_point_id", ""),
        "operating_point_service_pct": evidence.get("operating_point_service_pct", ""),
        "simulation_days": evidence.get("simulation_days", SIMULATION_DAYS),
        "state_evaluation_days": evidence.get(
            "state_evaluation_days", STATE_EVALUATION_DAYS
        ),
        "stage": evidence.get("stage", ""),
        "mechanism": mechanism.get("key", "baseline"),
        "lane_id": lane.get("lane_id", ""),
        "supplier_id": lane.get("supplier_id", ""),
        "item_id": lane.get("item_id", ""),
        "dst_node_id": lane.get("dst_node_id", ""),
        "edge_id": lane.get("edge_id", ""),
        "target_product_id": fed_product,
        "seed": evidence.get("seed", ""),
        "status": evidence.get("status", ""),
        "valid": evidence.get("valid", False),
        "case_key": evidence.get("case_key", ""),
        "case_signature": evidence.get("case_signature", ""),
        "baseline_case_signature": baseline_signature,
        "target_status": target.get("target_status", ""),
        "target_selection_mode": target.get("selection_mode", ""),
        "target_reference_kind": target.get("reference_kind", ""),
        "target_shipment_id": target.get("target_shipment_id", ""),
        "target_shipment_count": target.get("target_shipment_count", ""),
        "target_shipment_ids": target.get("target_shipment_ids", ""),
        "target_decision_day": target.get("target_decision_day", ""),
        "target_window_start_day": target.get("target_window_start_day", ""),
        "target_window_end_day": target.get("target_window_end_day", ""),
        "target_window_days": target.get("target_window_days", ""),
        "target_active_decision_day_count": target.get(
            "target_active_decision_day_count", ""
        ),
        "target_active_decision_days": target.get("target_active_decision_days", ""),
        "target_release_day": target.get("target_release_day", ""),
        "target_arrival_day": target.get("target_arrival_day", ""),
        "target_planned_qty": target.get("target_planned_qty", ""),
        "target_expected_delivered_qty": target.get(
            "target_expected_delivered_qty", ""
        ),
        "target_uom": target.get("target_uom", ""),
        "baseline_lane_shipped_qty_state_window": target.get(
            "baseline_lane_shipped_qty_state_window", ""
        ),
        "target_qty_share_of_lane_state_window": target.get(
            "target_qty_share_of_lane_state_window", ""
        ),
        "target_group_qty_percentile_lane_state_window": target.get(
            "target_group_qty_percentile_lane_state_window", ""
        ),
        "target_exposure_concentration_flag": target.get(
            "target_exposure_concentration_flag", ""
        ),
        "target_selection_basis": target.get("target_selection_basis", ""),
        "cross_state_common_day_found": target.get("cross_state_common_day_found", ""),
        "cross_state_common_window_found": target.get(
            "cross_state_common_window_found", ""
        ),
        "cross_state_match_status": target.get("cross_state_match_status", ""),
        "cross_state_quantity_ratio": target.get("cross_state_quantity_ratio", ""),
        "cross_state_match_threshold_ratio": target.get(
            "cross_state_match_threshold_ratio", ""
        ),
        "state_comparison_valid": target.get("state_comparison_valid", ""),
        "seed_cross_state_exposure_comparable": target.get(
            "seed_cross_state_exposure_comparable", ""
        ),
        "comparable_campaign_seed_count": target.get(
            "comparable_campaign_seed_count", ""
        ),
        "required_comparable_seed_count": target.get(
            "required_comparable_seed_count", ""
        ),
        "state_exposure_max_decision_day": target.get(
            "state_exposure_max_decision_day", ""
        ),
        "state_exposure_max_window_start_day": target.get(
            "state_exposure_max_window_start_day", ""
        ),
        "state_exposure_max_group_qty": target.get("state_exposure_max_group_qty", ""),
        "cross_state_matched_min_group_qty": target.get(
            "cross_state_matched_min_group_qty", ""
        ),
        "cross_state_matched_max_group_qty": target.get(
            "cross_state_matched_max_group_qty", ""
        ),
        "cross_state_matched_quantities_json": target.get(
            "cross_state_matched_quantities_json", ""
        ),
        "target_selected_independently_by_operating_point": target.get(
            "target_selected_independently_by_operating_point", ""
        ),
        "impact_window_start_day": target.get("impact_window_start_day", ""),
        "impact_window_end_day": target.get("impact_window_end_day", ""),
        "impact_window_days": target.get("impact_window_days", ""),
        "impact_window_fully_observed": target.get("impact_window_fully_observed", ""),
        "target_latest_baseline_arrival_day": target.get(
            "target_latest_baseline_arrival_day", ""
        ),
        "target_latest_stressed_arrival_day": target.get(
            "target_latest_stressed_arrival_day", ""
        ),
        "observable_days_after_target_decision": target.get(
            "observable_days_after_target_decision", ""
        ),
        "observable_days_after_first_expected_arrival": target.get(
            "observable_days_after_first_expected_arrival", ""
        ),
        "recovery_observation_days_after_latest_stressed_arrival": target.get(
            "recovery_observation_days_after_latest_stressed_arrival", ""
        ),
        "recovery_observation_days_within_impact_window": target.get(
            "recovery_observation_days_within_impact_window", ""
        ),
        "recovery_fully_observed_within_360": target.get(
            "recovery_fully_observed_within_360", ""
        ),
        "minimum_recovery_observation_days_required": target.get(
            "minimum_recovery_observation_days_required", ""
        ),
        "causal_window_start_day": target.get("causal_window_start_day", ""),
        "causal_window_end_day": target.get("causal_window_end_day", ""),
        "causal_window_days": target.get("causal_window_days", ""),
        "causal_window_defined": target.get("causal_window_defined", ""),
        "causal_window_fully_observed": target.get("causal_window_fully_observed", ""),
        "required_simulation_days": target.get("required_simulation_days", ""),
        "anchor_day": proof.get("anchor_day", target.get("target_decision_day", "")),
        "stressed_shipment_ids": "|".join(
            str(value) for value in proof.get("stressed_shipment_ids") or []
        ),
        "stressed_pulled_qty": proof.get("stressed_pulled_qty", ""),
        "stressed_shipped_qty": proof.get("stressed_shipped_qty", ""),
        "incident_affected_pulled_qty": proof.get("incident_affected_pulled_qty", ""),
        "incident_affected_shipped_qty": proof.get("incident_affected_shipped_qty", ""),
        "incident_plan_divergence_pulled_qty": proof.get(
            "incident_plan_divergence_pulled_qty", ""
        ),
        "incident_shipment_count": proof.get("incident_shipment_count", ""),
        "quantity_shortfall_qty": proof.get("quantity_shortfall_qty", ""),
        "arrival_delay_days": proof.get("arrival_delay_days", ""),
        "risk_event_ids": "|".join(
            str(value) for value in proof.get("risk_event_ids") or []
        ),
        "risk_type": mechanism.get("risk_type", ""),
        "risk_value": mechanism.get("value", ""),
        "risk_start_day": target.get("target_decision_day", ""),
        "risk_end_day": target.get("target_window_end_day", ""),
        "risk_applied_row_count": metrics.get("risk_applied_row_count", 0),
        "risk_applied_event_count": metrics.get("risk_applied_event_count", 0),
        "baseline_pre_incident_shipment_trace_sha256": proof.get(
            "baseline_pre_incident_shipment_trace_sha256",
            target.get("baseline_pre_incident_shipment_trace_sha256", ""),
        ),
        "incident_pre_incident_shipment_trace_sha256": proof.get(
            "incident_pre_incident_shipment_trace_sha256", ""
        ),
        "pre_incident_shipment_trace_match": proof.get(
            "pre_incident_shipment_trace_match", ""
        ),
        "incident_physically_exercised": proof.get(
            "incident_physically_exercised", evidence.get("stage") == "baseline"
        ),
        "physical_exercise_count": int(bool(proof.get("incident_physically_exercised")))
        if evidence.get("stage") == "incident"
        else 0,
        "target_day": target.get("target_decision_day", ""),
        "target_shipped_qty": target.get("target_expected_delivered_qty", ""),
        "service_output_product_268091_pct": metrics.get(
            "service_output_product_268091_pct", ""
        ),
        "service_output_product_268967_pct": metrics.get(
            "service_output_product_268967_pct", ""
        ),
        "service_global_pct": metrics.get("service_global_pct", ""),
        "baseline_impact_service_268091_pct": baseline_impact.get(
            "service_268091_pct", ""
        ),
        "baseline_impact_service_268967_pct": baseline_impact.get(
            "service_268967_pct", ""
        ),
        "baseline_impact_service_global_pct": baseline_impact.get(
            "service_global_pct", ""
        ),
        "impact_service_268091_pct": impact.get("service_268091_pct", ""),
        "impact_service_268967_pct": impact.get("service_268967_pct", ""),
        "impact_service_global_pct": impact.get("service_global_pct", ""),
        "impact_service_loss_268091_pp": (
            impact_service_losses["268091"] if is_incident else 0.0
        ),
        "impact_service_loss_268967_pp": (
            impact_service_losses["268967"] if is_incident else 0.0
        ),
        "impact_service_loss_global_pp": (
            impact_global_service_loss if is_incident else 0.0
        ),
        "impact_service_loss_fed_product_pp": (
            impact_service_losses.get(fed_product, "") if is_incident else 0.0
        ),
        "baseline_impact_demand_268091_qty": baseline_impact.get(
            "demand_qty_268091", ""
        ),
        "baseline_impact_demand_268967_qty": baseline_impact.get(
            "demand_qty_268967", ""
        ),
        "baseline_impact_demand_global_qty": baseline_impact.get(
            "demand_qty_global", ""
        ),
        "impact_demand_268091_qty": impact.get("demand_qty_268091", ""),
        "impact_demand_268967_qty": impact.get("demand_qty_268967", ""),
        "impact_demand_global_qty": impact.get("demand_qty_global", ""),
        "impact_on_due_loss_268091_qty": (
            loss(baseline_impact, impact, "on_due_qty_268091") if is_incident else 0.0
        ),
        "impact_on_due_loss_268967_qty": (
            loss(baseline_impact, impact, "on_due_qty_268967") if is_incident else 0.0
        ),
        "impact_on_due_loss_global_qty": (
            loss(baseline_impact, impact, "on_due_qty_global") if is_incident else 0.0
        ),
        "impact_on_due_loss_fed_product_qty": (
            loss(baseline_impact, impact, f"on_due_qty_{fed_product}")
            if is_incident
            else 0.0
        ),
        "impact_on_due_loss_268091_share_of_demand": (
            share(
                loss(baseline_impact, impact, "on_due_qty_268091"),
                baseline_impact.get("demand_qty_268091"),
            )
            if is_incident
            else 0.0
        ),
        "impact_on_due_loss_268967_share_of_demand": (
            share(
                loss(baseline_impact, impact, "on_due_qty_268967"),
                baseline_impact.get("demand_qty_268967"),
            )
            if is_incident
            else 0.0
        ),
        "impact_on_due_loss_global_share_of_demand": (
            share(
                loss(baseline_impact, impact, "on_due_qty_global"),
                baseline_impact.get("demand_qty_global"),
            )
            if is_incident
            else 0.0
        ),
        "impact_on_due_loss_fed_product_share_of_demand": (
            share(
                loss(baseline_impact, impact, f"on_due_qty_{fed_product}"),
                baseline_impact.get(f"demand_qty_{fed_product}"),
            )
            if is_incident
            else 0.0
        ),
        "impact_backlog_qty_days_delta": (
            increase(baseline_impact, impact, "backlog_qty_days_global")
            if is_incident
            else 0.0
        ),
        "impact_backlog_qty_days_per_demand_unit": (
            share(
                increase(baseline_impact, impact, "backlog_qty_days_global"),
                baseline_impact.get("demand_qty_global"),
            )
            if is_incident
            else 0.0
        ),
        "impact_backlog_relative_load": (
            relative_load(
                increase(baseline_impact, impact, "backlog_qty_days_global"),
                baseline_impact.get("demand_qty_global"),
                baseline_impact.get("day_count"),
            )
            if is_incident
            else 0.0
        ),
        "impact_backlog_qty_days_fed_product_delta": (
            increase(
                baseline_impact,
                impact,
                f"backlog_qty_days_{fed_product}",
            )
            if is_incident
            else 0.0
        ),
        "impact_backlog_relative_load_fed_product": (
            relative_load(
                increase(
                    baseline_impact,
                    impact,
                    f"backlog_qty_days_{fed_product}",
                ),
                baseline_impact.get(f"demand_qty_{fed_product}"),
                baseline_impact.get("day_count"),
            )
            if is_incident
            else 0.0
        ),
        "impact_max_backlog_qty_delta": (
            increase(baseline_impact, impact, "max_backlog_qty_global")
            if is_incident
            else 0.0
        ),
        "impact_max_backlog_share_of_demand": (
            share(
                increase(baseline_impact, impact, "max_backlog_qty_global"),
                baseline_impact.get("demand_qty_global"),
            )
            if is_incident
            else 0.0
        ),
        "impact_production_loss_268091_qty": (
            loss(baseline_impact, impact, "production_released_268091_qty")
            if is_incident
            else 0.0
        ),
        "impact_production_loss_268967_qty": (
            loss(baseline_impact, impact, "production_released_268967_qty")
            if is_incident
            else 0.0
        ),
        "impact_production_loss_fed_product_qty": (
            loss(
                baseline_impact,
                impact,
                f"production_released_{fed_product}_qty",
            )
            if is_incident
            else 0.0
        ),
        "impact_production_loss_268091_share_of_demand": (
            share(
                loss(baseline_impact, impact, "production_released_268091_qty"),
                baseline_impact.get("demand_qty_268091"),
            )
            if is_incident
            else 0.0
        ),
        "impact_production_loss_268967_share_of_demand": (
            share(
                loss(baseline_impact, impact, "production_released_268967_qty"),
                baseline_impact.get("demand_qty_268967"),
            )
            if is_incident
            else 0.0
        ),
        "impact_production_loss_fed_product_share_of_demand": (
            share(
                loss(
                    baseline_impact,
                    impact,
                    f"production_released_{fed_product}_qty",
                ),
                baseline_impact.get(f"demand_qty_{fed_product}"),
            )
            if is_incident
            else 0.0
        ),
        "quantity_shortfall_share_of_target": (
            share(
                proof.get("quantity_shortfall_qty"),
                target.get("target_expected_delivered_qty"),
            )
            if is_incident
            else 0.0
        ),
        "incident_reference_dose_qty": reference_dose_qty,
        "incident_reference_dose_qty_days": reference_dose_qty_days,
        "incident_effective_dose_qty": effective_dose_qty,
        "incident_effective_dose_qty_days": effective_dose_qty_days,
        "baseline_causal_service_268091_pct": baseline_causal.get(
            "service_268091_pct", ""
        ),
        "baseline_causal_service_268967_pct": baseline_causal.get(
            "service_268967_pct", ""
        ),
        "baseline_causal_service_global_pct": baseline_causal.get(
            "service_global_pct", ""
        ),
        "causal_service_268091_pct": causal.get("service_268091_pct", ""),
        "causal_service_268967_pct": causal.get("service_268967_pct", ""),
        "causal_service_global_pct": causal.get("service_global_pct", ""),
        "causal_service_loss_268091_pp": (
            causal_service_losses["268091"] if is_incident else 0.0
        ),
        "causal_service_loss_268967_pp": (
            causal_service_losses["268967"] if is_incident else 0.0
        ),
        "causal_service_loss_global_pp": (
            causal_global_service_loss if is_incident else 0.0
        ),
        "causal_service_loss_fed_product_pp": (
            causal_service_losses.get(fed_product, "") if is_incident else 0.0
        ),
        "baseline_causal_demand_268091_qty": baseline_causal.get(
            "demand_qty_268091", ""
        ),
        "baseline_causal_demand_268967_qty": baseline_causal.get(
            "demand_qty_268967", ""
        ),
        "baseline_causal_demand_global_qty": baseline_causal.get(
            "demand_qty_global", ""
        ),
        "causal_demand_268091_qty": causal.get("demand_qty_268091", ""),
        "causal_demand_268967_qty": causal.get("demand_qty_268967", ""),
        "causal_demand_global_qty": causal.get("demand_qty_global", ""),
        "causal_on_due_loss_268091_qty": (
            loss(baseline_causal, causal, "on_due_qty_268091") if is_incident else 0.0
        ),
        "causal_on_due_loss_268967_qty": (
            loss(baseline_causal, causal, "on_due_qty_268967") if is_incident else 0.0
        ),
        "causal_on_due_loss_global_qty": (
            loss(baseline_causal, causal, "on_due_qty_global") if is_incident else 0.0
        ),
        "causal_on_due_loss_fed_product_qty": (
            loss(baseline_causal, causal, f"on_due_qty_{fed_product}")
            if is_incident
            else 0.0
        ),
        "causal_on_due_loss_268091_share_of_demand": (
            share(
                loss(baseline_causal, causal, "on_due_qty_268091"),
                baseline_causal.get("demand_qty_268091"),
            )
            if is_incident
            else 0.0
        ),
        "causal_on_due_loss_268967_share_of_demand": (
            share(
                loss(baseline_causal, causal, "on_due_qty_268967"),
                baseline_causal.get("demand_qty_268967"),
            )
            if is_incident
            else 0.0
        ),
        "causal_on_due_loss_global_share_of_demand": (
            share(
                loss(baseline_causal, causal, "on_due_qty_global"),
                baseline_causal.get("demand_qty_global"),
            )
            if is_incident
            else 0.0
        ),
        "causal_on_due_loss_fed_product_share_of_demand": (
            share(
                loss(baseline_causal, causal, f"on_due_qty_{fed_product}"),
                baseline_causal.get(f"demand_qty_{fed_product}"),
            )
            if is_incident
            else 0.0
        ),
        "causal_backlog_qty_days_delta": (
            increase(baseline_causal, causal, "backlog_qty_days_global")
            if is_incident
            else 0.0
        ),
        "causal_backlog_qty_days_per_demand_unit": (
            share(
                increase(baseline_causal, causal, "backlog_qty_days_global"),
                baseline_causal.get("demand_qty_global"),
            )
            if is_incident
            else 0.0
        ),
        "causal_backlog_relative_load": (
            relative_load(
                increase(baseline_causal, causal, "backlog_qty_days_global"),
                baseline_causal.get("demand_qty_global"),
                baseline_causal.get("day_count"),
            )
            if is_incident
            else 0.0
        ),
        "causal_backlog_qty_days_fed_product_delta": (
            increase(
                baseline_causal,
                causal,
                f"backlog_qty_days_{fed_product}",
            )
            if is_incident
            else 0.0
        ),
        "causal_backlog_relative_load_fed_product": (
            relative_load(
                increase(
                    baseline_causal,
                    causal,
                    f"backlog_qty_days_{fed_product}",
                ),
                baseline_causal.get(f"demand_qty_{fed_product}"),
                baseline_causal.get("day_count"),
            )
            if is_incident
            else 0.0
        ),
        "causal_max_backlog_qty_delta": (
            increase(baseline_causal, causal, "max_backlog_qty_global")
            if is_incident
            else 0.0
        ),
        "causal_max_backlog_share_of_demand": (
            share(
                increase(baseline_causal, causal, "max_backlog_qty_global"),
                baseline_causal.get("demand_qty_global"),
            )
            if is_incident
            else 0.0
        ),
        "causal_production_loss_268091_qty": (
            loss(baseline_causal, causal, "production_released_268091_qty")
            if is_incident
            else 0.0
        ),
        "causal_production_loss_268967_qty": (
            loss(baseline_causal, causal, "production_released_268967_qty")
            if is_incident
            else 0.0
        ),
        "causal_production_loss_fed_product_qty": (
            loss(
                baseline_causal,
                causal,
                f"production_released_{fed_product}_qty",
            )
            if is_incident
            else 0.0
        ),
        "causal_production_loss_268091_share_of_demand": (
            share(
                loss(baseline_causal, causal, "production_released_268091_qty"),
                baseline_causal.get("demand_qty_268091"),
            )
            if is_incident
            else 0.0
        ),
        "causal_production_loss_268967_share_of_demand": (
            share(
                loss(baseline_causal, causal, "production_released_268967_qty"),
                baseline_causal.get("demand_qty_268967"),
            )
            if is_incident
            else 0.0
        ),
        "causal_production_loss_fed_product_share_of_demand": (
            share(
                loss(
                    baseline_causal,
                    causal,
                    f"production_released_{fed_product}_qty",
                ),
                baseline_causal.get(f"demand_qty_{fed_product}"),
            )
            if is_incident
            else 0.0
        ),
        "global_service_loss_pp": (causal_global_service_loss if is_incident else 0.0),
        "service_loss_268091_pp": (
            causal_service_losses["268091"] if is_incident else 0.0
        ),
        "service_loss_268967_pp": (
            causal_service_losses["268967"] if is_incident else 0.0
        ),
        "late_orders": "",
        "backlog_day_count": metrics.get("backlog_day_count", ""),
        "backlog_qty": metrics.get("backlog_qty", ""),
        "max_backlog_qty": metrics.get("max_backlog_qty", ""),
        "backlog_qty_days": metrics.get("backlog_qty_days", ""),
        "production_released_268091_qty": metrics.get(
            "production_released_268091_qty", ""
        ),
        "production_released_268967_qty": metrics.get(
            "production_released_268967_qty", ""
        ),
        "total_cost": metrics.get("total_cost", ""),
        "total_transport_cost": metrics.get("total_transport_cost", ""),
        "total_purchase_cost": metrics.get("total_purchase_cost", ""),
        "total_unreliable_loss_qty": metrics.get("total_unreliable_loss_qty", ""),
        "cumulative_penalty": "",
        "warmup_core_state_sha256": metrics.get("warmup_core_state_sha256", ""),
        "summary_sha256": metrics.get("summary_sha256", ""),
        "validation_errors": " | ".join(
            str(value) for value in evidence.get("validation_errors") or []
        ),
        "error": " | ".join(
            str(value) for value in evidence.get("validation_errors") or []
        ),
        "created_at_utc": evidence.get("created_at_utc", ""),
    }


def refresh_shard_outputs(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_rows: list[dict[str, Any]] = []
    for path in sorted((shard_dir / "case_evidence").glob("*.json")):
        evidence = _read_json(path)
        key = str(evidence.get("case_key") or "")
        signature = str(evidence.get("case_signature") or "")
        _validate_evidence(
            evidence,
            manifest=manifest,
            case_key=key,
            case_signature=signature,
        )
        evidence["_path"] = str(path)
        evidence_rows.append(evidence)
    baselines = {
        str(row["case_signature"]): row
        for row in evidence_rows
        if row.get("stage") == "baseline"
    }
    metric_rows = [
        _flatten_metric_row(row, baseline_by_signature=baselines)
        for row in evidence_rows
    ]
    metric_rows.sort(
        key=lambda row: (
            str(row["operating_point_id"]),
            int(row["seed"]),
            0 if row["stage"] == "baseline" else 1,
            str(row["lane_id"]),
            str(row["mechanism"]),
        )
    )
    _write_csv_atomic(shard_dir / "campaign_metrics.csv", metric_rows, METRIC_FIELDS)
    target_rows = [
        dict(target)
        for baseline in baselines.values()
        for target in baseline.get("shipment_targets") or []
    ]
    target_rows.sort(
        key=lambda row: (
            str(row.get("operating_point_id") or ""),
            int(row.get("seed") or -1),
            str(row.get("lane_id") or ""),
        )
    )
    _write_csv_atomic(shard_dir / "shipment_targets.csv", target_rows, TARGET_FIELDS)
    ledger_rows = [
        {
            "case_key": row.get("case_key", ""),
            "case_signature": row.get("case_signature", ""),
            "stage": row.get("stage", ""),
            "operating_point_id": row.get("operating_point_id", ""),
            "seed": row.get("seed", ""),
            "lane_id": (row.get("lane") or {}).get("lane_id", ""),
            "mechanism": (row.get("mechanism") or {}).get("key", "baseline"),
            "status": row.get("status", ""),
            "valid": row.get("valid", False),
            "evidence_path": row.get("_path", ""),
            "created_at_utc": row.get("created_at_utc", ""),
        }
        for row in evidence_rows
    ]
    _write_csv_atomic(shard_dir / "case_ledger.csv", ledger_rows, LEDGER_FIELDS)
    return evidence_rows, metric_rows


class ProgressTracker:
    def __init__(
        self,
        *,
        shard_dir: Path,
        manifest: Mapping[str, Any],
        shard_id: str,
        point_id: str,
        block_number: int,
        seeds: Sequence[int],
        planned_count: int,
        shard_index_value: int | None = None,
        shard_count_value: int | None = None,
    ) -> None:
        self.path = shard_dir / "progress.json"
        self.manifest = manifest
        self.shard_id = shard_id
        self.point_id = point_id
        self.block_number = block_number
        self.seeds = list(seeds)
        self.planned_count = planned_count
        self.shard_index_value = shard_index_value or shard_index(
            point_id, block_number
        )
        self.shard_count_value = shard_count_value or len(OPERATING_POINT_IDS) * len(
            SEED_BLOCKS
        )
        self.started = time.monotonic()
        self.started_at = utc_now()
        self.completed_keys: set[str] = set()
        self.initial_completed_count = 0
        self.failed_keys: set[str] = set()
        self.running_keys: set[str] = set()
        self.errors: list[dict[str, str]] = []
        self.last_completed = ""
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)

    def initialize(self, evidence_rows: Sequence[Mapping[str, Any]]) -> None:
        with self.lock:
            self.completed_keys = {str(row["case_key"]) for row in evidence_rows}
            self.initial_completed_count = len(self.completed_keys)
            self.failed_keys = {
                str(row["case_key"])
                for row in evidence_rows
                if not _truthy(row.get("valid"))
            }
            self._write_locked("running")
        self.thread.start()

    def _heartbeat(self) -> None:
        while not self.stop_event.wait(30.0):
            with self.lock:
                self._write_locked("running")

    def start_case(self, key: str) -> None:
        with self.lock:
            self.running_keys.add(key)
            self._write_locked("running")

    def sync_evidence(self, evidence_rows: Sequence[Mapping[str, Any]]) -> None:
        """Synchronize counters after local or external evidence was discovered."""

        with self.lock:
            for row in evidence_rows:
                key = str(row.get("case_key") or "")
                if not key:
                    continue
                self.completed_keys.add(key)
                if _truthy(row.get("valid")):
                    self.failed_keys.discard(key)
                else:
                    self.failed_keys.add(key)
            self._write_locked("running")

    def finish_case(self, key: str, *, valid: bool, error: str = "") -> None:
        with self.lock:
            self.running_keys.discard(key)
            self.completed_keys.add(key)
            if not valid:
                self.failed_keys.add(key)
            else:
                self.failed_keys.discard(key)
            if error:
                self.errors.append({"case_key": key, "error": error})
                self.errors = self.errors[-20:]
            self.last_completed = key
            self._write_locked("running")

    def runtime_failure(self, key: str, error: str) -> None:
        with self.lock:
            self.running_keys.discard(key)
            self.failed_keys.add(key)
            self.errors.append({"case_key": key, "error": error})
            self.errors = self.errors[-20:]
            self._write_locked("running")

    def close(self, status: str) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)
        with self.lock:
            self.running_keys.clear()
            self._write_locked(status)

    def _write_locked(self, status: str) -> None:
        elapsed = max(0.0, time.monotonic() - self.started)
        completed_count = len(self.completed_keys)
        newly_completed = max(0, completed_count - self.initial_completed_count)
        mean_seconds = elapsed / newly_completed if newly_completed else 0.0
        remaining = max(0, self.planned_count - completed_count)
        eta = mean_seconds * remaining if newly_completed else None
        _write_json_atomic(
            self.path,
            {
                "schema_version": PROGRESS_SCHEMA_VERSION,
                "campaign_signature": self.manifest["campaign_signature"],
                "shard_id": self.shard_id,
                "shard_index": self.shard_index_value,
                "shard_count": self.shard_count_value,
                "operating_point_id": self.point_id,
                "seed_block": self.block_number,
                "seed_ids": self.seeds,
                "status": status,
                "planned_case_count": self.planned_count,
                "completed_case_count": completed_count,
                "failed_case_count": len(self.failed_keys),
                "running_case_keys": sorted(self.running_keys),
                "updated_at_utc": utc_now(),
                "started_at_utc": self.started_at,
                "elapsed_seconds": elapsed,
                "mean_completed_case_seconds": mean_seconds,
                "eta_seconds": eta,
                "last_completed_case_key": self.last_completed,
                "errors": self.errors,
            },
        )


def _run_jobs(
    jobs: Sequence[tuple[str, Any]],
    *,
    workers: int,
    tracker: ProgressTracker,
    refresh: callable,
) -> tuple[list[dict[str, Any]], list[tuple[str, Exception]]]:
    results: list[dict[str, Any]] = []
    failures: list[tuple[str, Exception]] = []

    def wrapped(key: str, function: Any) -> dict[str, Any]:
        tracker.start_case(key)
        return function()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(wrapped, key, function): key for key, function in jobs}
        for future in as_completed(futures):
            key = futures[future]
            try:
                evidence = future.result()
                results.append(evidence)
                tracker.finish_case(
                    key,
                    valid=_truthy(evidence.get("valid")),
                    error=" | ".join(
                        str(value) for value in evidence.get("validation_errors") or []
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - preserve each failed engine attempt
                failures.append((key, exc))
                tracker.runtime_failure(key, str(exc))
            refresh()
    return results, failures


def _planned_case_count(seed_count: int, lane_count: int) -> int:
    return seed_count * (1 + lane_count * len(MECHANISMS))


def run_shard(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    points: Sequence[Mapping[str, Any]],
    lanes: Sequence[Lane],
    point_id: str,
    block_number: int,
    workers: int,
    reuse_roots: Sequence[Path] = (),
    smoke_seed: int | None = None,
    smoke_lane_id: str | None = None,
    stop_after_baselines: bool = False,
) -> dict[str, Any]:
    if workers < 1 or workers > MAX_WORKERS:
        raise ValueError(f"workers must be in 1..{MAX_WORKERS}")
    current_engine_sha = _sha256_file(Path(str(manifest["engine"])))
    if current_engine_sha != manifest["engine_sha256"]:
        raise ValueError("Canonical engine changed after campaign planning")
    current_profile_sha = _sha256_file(Path(str(manifest["engine_profile"])))
    if current_profile_sha != manifest["engine_profile_sha256"]:
        raise ValueError("Engine profile changed after campaign planning")
    point = _point_by_id(points, point_id)
    seeds = (int(smoke_seed),) if smoke_seed is not None else seed_block(block_number)
    selected_lanes = list(lanes)
    if smoke_lane_id is not None:
        selected_lanes = [lane for lane in lanes if lane.lane_id == smoke_lane_id]
        if len(selected_lanes) != 1:
            raise ValueError(f"Smoke lane not found exactly once: {smoke_lane_id}")
    registry = load_target_registry(
        output_dir=output_dir,
        manifest=manifest,
        lanes=lanes,
    )
    shard_id = (
        f"smoke__{point_id}__seed_{seeds[0]}"
        if smoke_seed is not None
        else f"{point_id}__seed_block_{block_number:02d}"
    )
    shard_dir = (
        output_dir.resolve() / "smoke" / shard_id
        if smoke_seed is not None
        else output_dir.resolve() / "shards" / shard_id
    )
    shard_dir.mkdir(parents=True, exist_ok=True)
    local_manifest = dict(manifest)
    local_manifest["target_registry_signature"] = registry["registry_signature"]
    local_manifest["active_shard_id"] = shard_id
    local_manifest["active_shard_index"] = (
        1 if smoke_seed is not None else shard_index(point_id, block_number)
    )
    local_manifest["active_shard_count"] = (
        1 if smoke_seed is not None else len(OPERATING_POINT_IDS) * len(SEED_BLOCKS)
    )
    shard_contract = {
        "schema_version": f"{SCHEMA_VERSION}.shard.v1",
        "campaign_signature": manifest["campaign_signature"],
        "shard_id": shard_id,
        "shard_index": local_manifest["active_shard_index"],
        "shard_count": local_manifest["active_shard_count"],
        "operating_point_id": point_id,
        "operating_point_service_pct": point["operating_point_service_pct"],
        "seed_block": block_number,
        "seed_ids": list(seeds),
        "lane_ids": [lane.lane_id for lane in selected_lanes],
        "mechanisms": [mechanism.key for mechanism in MECHANISMS],
        "target_registry_signature": registry["registry_signature"],
        "adaptive_horizon": True,
        "planned_case_count": _planned_case_count(len(seeds), len(selected_lanes)),
        "status": "planned",
    }
    shard_contract["shard_signature"] = _stable_sha256(shard_contract)
    shard_manifest_path = shard_dir / "shard_manifest.json"
    if shard_manifest_path.is_file():
        existing = _read_json(shard_manifest_path)
        if existing.get("shard_signature") != shard_contract["shard_signature"]:
            raise ValueError("Shard directory belongs to another shard contract")
        changed = [
            key
            for key, value in shard_contract.items()
            if key not in {"status", "shard_signature"} and existing.get(key) != value
        ]
        if changed:
            raise ValueError(
                "Existing shard manifest changed contract fields: " + ", ".join(changed)
            )
    else:
        _write_json_atomic(shard_manifest_path, shard_contract)
    existing_rows, _ = refresh_shard_outputs(shard_dir=shard_dir, manifest=manifest)
    tracker = ProgressTracker(
        shard_dir=shard_dir,
        manifest=manifest,
        shard_id=shard_id,
        point_id=point_id,
        block_number=block_number,
        seeds=seeds,
        planned_count=shard_contract["planned_case_count"],
        shard_index_value=local_manifest["active_shard_index"],
        shard_count_value=local_manifest["active_shard_count"],
    )
    tracker.initialize(existing_rows)

    def refresh() -> None:
        refreshed, _metrics = refresh_shard_outputs(
            shard_dir=shard_dir, manifest=manifest
        )
        tracker.sync_evidence(refreshed)

    try:
        registered_targets_by_seed: dict[int, list[dict[str, Any]]] = {}
        selected_lane_ids = {lane.lane_id for lane in selected_lanes}
        raw_registry_by_key = {
            (int(row["seed"]), str(row["lane_id"])): dict(row)
            for row in registry["targets"]
            if str(row["operating_point_id"]) == point_id
            and int(row["seed"]) in seeds
            and str(row["lane_id"]) in selected_lane_ids
        }
        expected_registry_keys = {
            (seed, lane.lane_id) for seed in seeds for lane in selected_lanes
        }
        if set(raw_registry_by_key) != expected_registry_keys:
            raise RuntimeError("Shard target-registry projection is incomplete")
        probe_jobs = [
            (seed, lane, mechanism, raw_registry_by_key[(seed, lane.lane_id)])
            for seed in seeds
            for lane in selected_lanes
            for mechanism in MECHANISMS
        ]
        prepared_probes: dict[tuple[int, str, str], dict[str, Any]] = {}
        probe_failures: list[dict[str, Any]] = []

        def write_probe_progress(status: str) -> None:
            _write_json_atomic(
                shard_dir / "incident_probe_progress.json",
                {
                    "schema_version": f"{SCHEMA_VERSION}.incident_probe.progress.v1",
                    "campaign_signature": manifest["campaign_signature"],
                    "shard_id": shard_id,
                    "status": status,
                    "planned": len(probe_jobs),
                    "completed": len(prepared_probes),
                    "failed": len(probe_failures),
                    "running": max(
                        0,
                        min(
                            workers,
                            len(probe_jobs)
                            - len(prepared_probes)
                            - len(probe_failures),
                        ),
                    ),
                    "updated_at": utc_now(),
                },
            )

        write_probe_progress("running")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _prepare_incident_probe,
                    shard_dir=shard_dir,
                    manifest=local_manifest,
                    point=point,
                    lane=lane,
                    mechanism=mechanism,
                    seed=seed,
                    registered_target=target,
                ): (seed, lane.lane_id, mechanism.key)
                for seed, lane, mechanism, target in probe_jobs
            }
            for future in as_completed(futures):
                probe_key = futures[future]
                try:
                    prepared_probes[probe_key] = future.result()
                except Exception as exc:
                    probe_failures.append(
                        {
                            "seed": probe_key[0],
                            "lane_id": probe_key[1],
                            "mechanism": probe_key[2],
                            "error": str(exc),
                        }
                    )
                write_probe_progress("running")
        if probe_failures:
            write_probe_progress("failed")
            raise RuntimeError(
                "Adaptive incident probes failed closed: "
                + json.dumps(probe_failures, ensure_ascii=False)
            )
        write_probe_progress("complete")
        for seed in seeds:
            enriched: list[dict[str, Any]] = []
            for lane in selected_lanes:
                target = dict(raw_registry_by_key[(seed, lane.lane_id)])
                target["incident_windows"] = {
                    mechanism.key: dict(
                        prepared_probes[(seed, lane.lane_id, mechanism.key)][
                            "incident_window"
                        ]
                    )
                    for mechanism in MECHANISMS
                }
                enriched.append(target)
            registered_targets_by_seed[seed] = enriched

        baselines: dict[int, dict[str, Any]] = {}
        baseline_jobs: list[tuple[str, Any]] = []
        for seed in seeds:
            registered_targets = registered_targets_by_seed[seed]
            baseline_days = max(
                MINIMUM_CASE_DAYS,
                max(
                    int(window["required_simulation_days"])
                    for target in registered_targets
                    for window in target["incident_windows"].values()
                ),
            )
            key = _case_key(point_id=point_id, seed=seed, stage="baseline")
            adaptive_contract_signature = _stable_sha256(
                [
                    {
                        "lane_id": target["lane_id"],
                        "incident_windows": target["incident_windows"],
                    }
                    for target in registered_targets
                ]
            )
            signature = _case_signature(
                manifest=local_manifest,
                point=point,
                seed=seed,
                stage="baseline",
                simulation_days=baseline_days,
                adaptive_contract_signature=adaptive_contract_signature,
            )
            existing = _load_or_reuse_evidence(
                shard_dir=shard_dir,
                manifest=local_manifest,
                case_key=key,
                case_signature=signature,
                reuse_roots=reuse_roots,
            )
            if existing is not None:
                baselines[seed] = existing
                continue
            baseline_jobs.append(
                (
                    key,
                    lambda seed=seed, registered_targets=registered_targets, baseline_days=baseline_days: (
                        _execute_baseline(
                            shard_dir=shard_dir,
                            manifest=local_manifest,
                            point=point,
                            lanes=selected_lanes,
                            seed=seed,
                            reuse_roots=reuse_roots,
                            registered_targets=registered_targets,
                            simulation_days=baseline_days,
                        )
                    ),
                )
            )
        baseline_results, baseline_failures = _run_jobs(
            baseline_jobs,
            workers=workers,
            tracker=tracker,
            refresh=refresh,
        )
        for evidence in baseline_results:
            baselines[int(evidence["seed"])] = evidence
        if baseline_failures:
            raise RuntimeError(
                "Baseline failures block paired incidents: "
                + "; ".join(f"{key}: {error}" for key, error in baseline_failures)
            )
        if set(baselines) != set(seeds):
            raise RuntimeError("Baseline matrix incomplete after baseline stage")
        invalid_baselines = [
            evidence["case_key"]
            for evidence in baselines.values()
            if not _truthy(evidence.get("valid"))
        ]
        if invalid_baselines:
            raise RuntimeError(
                "Invalid baselines block paired incidents: "
                + ", ".join(invalid_baselines)
            )

        missing_targets: list[tuple[int, Lane, dict[str, Any], dict[str, Any]]] = []
        for seed in seeds:
            baseline = baselines[seed]
            targets = _target_by_lane(baseline)
            if set(targets) != {lane.lane_id for lane in selected_lanes}:
                raise RuntimeError(f"Baseline target matrix incomplete for seed {seed}")
            for lane in selected_lanes:
                target = targets[lane.lane_id]
                if not str(target.get("target_status") or "").startswith("identified_"):
                    missing_targets.append((seed, lane, target, baseline))
        if missing_targets:
            # Materialize the two non-applicable cells for every failed window.
            nonapp_jobs: list[tuple[str, Any]] = []
            for seed, lane, target, baseline in missing_targets:
                for mechanism in MECHANISMS:
                    key = _case_key(
                        point_id=point_id,
                        seed=seed,
                        stage="incident",
                        lane_id=lane.lane_id,
                        mechanism=mechanism.key,
                    )
                    nonapp_jobs.append(
                        (
                            key,
                            lambda lane=lane, mechanism=mechanism, seed=seed, target=target, baseline=baseline: (
                                _execute_incident(
                                    shard_dir=shard_dir,
                                    manifest=local_manifest,
                                    point=point,
                                    lane=lane,
                                    mechanism=mechanism,
                                    seed=seed,
                                    target=target,
                                    baseline_evidence=baseline,
                                    reuse_roots=reuse_roots,
                                )
                            ),
                        )
                    )
            _nonapp_results, nonapp_failures = _run_jobs(
                nonapp_jobs,
                workers=workers,
                tracker=tracker,
                refresh=refresh,
            )
            details = ", ".join(
                f"seed={seed}/{lane.lane_id}"
                for seed, lane, _target, _baseline in missing_targets
            )
            if nonapp_failures:
                details += "; evidence failures=" + ", ".join(
                    key for key, _error in nonapp_failures
                )
            raise RuntimeError(
                "Fixed supplier-window target validation failed after adaptive probes: "
                f"{details}"
            )

        if stop_after_baselines:
            evidence_rows, metric_rows = refresh_shard_outputs(
                shard_dir=shard_dir, manifest=manifest
            )
            tracker.sync_evidence(evidence_rows)
            preflight_manifest = {
                **shard_contract,
                "status": "preflight_complete",
                "completed_case_count": len(metric_rows),
                "valid_case_count": sum(
                    _truthy(row.get("valid")) for row in evidence_rows
                ),
                "invalid_or_not_applicable_case_count": 0,
                "runtime_failure_count": 0,
                "diagnostic_identified_lane_window_target_count": len(seeds)
                * len(selected_lanes),
                "diagnostic_note": (
                    "All adaptive incident probes have already run; this option stops "
                    "after the paired extended baselines and is not a low-cost state gate."
                ),
                "completed_at_utc": utc_now(),
            }
            _write_json_atomic(shard_manifest_path, preflight_manifest)
            tracker.close("preflight_complete")
            return preflight_manifest

        incident_jobs: list[tuple[str, Any]] = []
        for seed in seeds:
            baseline = baselines[seed]
            targets = _target_by_lane(baseline)
            if set(targets) != {lane.lane_id for lane in selected_lanes}:
                raise RuntimeError(f"Baseline target matrix incomplete for seed {seed}")
            for lane in selected_lanes:
                baseline_target = targets[lane.lane_id]
                for mechanism in MECHANISMS:
                    target = _target_for_mechanism(baseline_target, mechanism.key)
                    incident_days = max(
                        MINIMUM_CASE_DAYS,
                        int(target["required_simulation_days"]),
                    )
                    key = _case_key(
                        point_id=point_id,
                        seed=seed,
                        stage="incident",
                        lane_id=lane.lane_id,
                        mechanism=mechanism.key,
                    )
                    signature = _case_signature(
                        manifest=local_manifest,
                        point=point,
                        seed=seed,
                        stage="incident",
                        lane=lane,
                        mechanism=mechanism,
                        target=target,
                        simulation_days=incident_days,
                    )
                    existing = _load_or_reuse_evidence(
                        shard_dir=shard_dir,
                        manifest=local_manifest,
                        case_key=key,
                        case_signature=signature,
                        reuse_roots=reuse_roots,
                    )
                    if existing is not None:
                        continue
                    incident_jobs.append(
                        (
                            key,
                            lambda lane=lane, mechanism=mechanism, seed=seed, target=target, baseline=baseline: (
                                _execute_incident(
                                    shard_dir=shard_dir,
                                    manifest=local_manifest,
                                    point=point,
                                    lane=lane,
                                    mechanism=mechanism,
                                    seed=seed,
                                    target=target,
                                    baseline_evidence=baseline,
                                    reuse_roots=reuse_roots,
                                    prepared_probe=prepared_probes[
                                        (seed, lane.lane_id, mechanism.key)
                                    ],
                                )
                            ),
                        )
                    )
        _incident_results, incident_failures = _run_jobs(
            incident_jobs,
            workers=workers,
            tracker=tracker,
            refresh=refresh,
        )
        evidence_rows, metric_rows = refresh_shard_outputs(
            shard_dir=shard_dir, manifest=manifest
        )
        tracker.sync_evidence(evidence_rows)
        expected = shard_contract["planned_case_count"]
        invalid = [row for row in evidence_rows if not _truthy(row.get("valid"))]
        complete = (
            len(metric_rows) == expected and not incident_failures and not invalid
        )
        status = "complete" if complete else "failed"
        shard_manifest = {
            **shard_contract,
            "status": status,
            "completed_case_count": len(metric_rows),
            "valid_case_count": sum(_truthy(row.get("valid")) for row in evidence_rows),
            "invalid_or_not_applicable_case_count": len(invalid),
            "runtime_failure_count": len(incident_failures),
            "completed_at_utc": utc_now(),
        }
        # Keep the immutable shard signature as the contract signature; status
        # and counters are deliberately outside its signed design payload.
        _write_json_atomic(shard_manifest_path, shard_manifest)
        tracker.close(status)
        if not complete:
            raise RuntimeError(
                f"Shard {shard_id} failed closed: rows={len(metric_rows)}/{expected}, "
                f"invalid={len(invalid)}, runtime_failures={len(incident_failures)}"
            )
        return shard_manifest
    except Exception:
        tracker.close("failed")
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("plan", "discover-targets", "run-shard", "smoke"),
        default="plan",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--operating-points",
        type=Path,
        required=True,
        help=(
            "Signed five-seed multi-seed calibration selection with the 30 campaign "
            "seeds still sealed as holdout. No default is used so an obsolete "
            "calibration cannot be planned accidentally."
        ),
    )
    parser.add_argument("--lane-reference", type=Path, default=DEFAULT_LANE_REFERENCE)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--engine-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--operating-point-id", choices=OPERATING_POINT_IDS, default=None
    )
    parser.add_argument(
        "--seed-block", type=int, choices=range(1, len(SEED_BLOCKS) + 1), default=None
    )
    parser.add_argument(
        "--workers", type=int, choices=range(1, MAX_WORKERS + 1), default=2
    )
    parser.add_argument("--reuse-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument(
        "--stop-after-baselines",
        action="store_true",
        help=(
            "Diagnostic mode: after all adaptive incident probes, execute/reuse the "
            "five extended baselines and stop before final incident materialization. "
            "Use discover-targets for the low-cost operating-point go/no-go."
        ),
    )
    parser.add_argument("--smoke-seed", type=int, default=SEEDS[0])
    parser.add_argument("--smoke-lane-id", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    smoke = args.mode == "smoke"
    if args.mode == "run-shard" and (
        args.operating_point_id is None or args.seed_block is None
    ):
        raise ValueError("run-shard requires --operating-point-id and --seed-block")
    if args.stop_after_baselines and args.mode != "run-shard":
        raise ValueError("--stop-after-baselines is valid only with --mode run-shard")
    smoke_point = args.operating_point_id or "op_100"
    manifest, points, lanes = prepare_manifest(
        output_dir=args.output_dir,
        operating_points_path=args.operating_points,
        lane_reference_path=args.lane_reference,
        engine=args.engine,
        profile=args.engine_profile,
        # A smoke run deliberately reuses the signed full-campaign plan and its
        # completed 93-run discovery registry.  It writes under ``smoke/`` and
        # is never counted in campaign shards.
        smoke=False,
        smoke_point_id=smoke_point,
        smoke_seed=args.smoke_seed,
        smoke_lane_id=args.smoke_lane_id,
        require_existing=args.mode in {"run-shard", "smoke"},
    )
    if args.mode == "plan":
        print(
            json.dumps(
                {
                    "status": "planned",
                    "campaign_signature": manifest["campaign_signature"],
                    "output_dir": str(args.output_dir.resolve()),
                    "expected_counts": manifest["expected_counts"],
                    "shard_count": len(manifest["shards"]),
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0
    if args.mode == "discover-targets":
        registry = run_target_discovery(
            output_dir=args.output_dir,
            manifest=manifest,
            points=points,
            lanes=lanes,
            workers=args.workers,
        )
        print(
            json.dumps(
                {
                    "status": "complete",
                    "registry_signature": registry["registry_signature"],
                    "target_count": len(registry["targets"]),
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0
    result = run_shard(
        output_dir=args.output_dir,
        manifest=manifest,
        points=points,
        lanes=lanes,
        point_id=smoke_point if smoke else args.operating_point_id,
        block_number=1 if smoke else args.seed_block,
        workers=1 if smoke else args.workers,
        reuse_roots=args.reuse_evidence_dir,
        smoke_seed=args.smoke_seed if smoke else None,
        smoke_lane_id=(args.smoke_lane_id or lanes[0].lane_id) if smoke else None,
        stop_after_baselines=args.stop_after_baselines,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
