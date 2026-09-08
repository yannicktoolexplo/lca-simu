#!/usr/bin/env python3
"""Run the additive V8 supplier campaign with an exposure-stratified window.

V8 changes only how the 42-day supplier-incident window is frozen.  It reads
and revalidates the 90 signed V7 baseline shipment traces, then selects one
fixed calendar window per lane.  The selected window is the earliest start in
J180..J678 for which every one of the 30 paired seeds has positive normally
deliverable quantity in all three operating states and, within each seed, the
largest state quantity is at most 1.5 times the smallest.

No engine case and no incident outcome participates in target selection.  The
incident mechanisms, adaptive horizons, pairing, shard execution and physical
evidence remain those of the frozen V4/V7 campaign implementation.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7 as adapter_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


implementation_v4 = adapter_v7.implementation_v4
ADAPTER_PATH = Path(__file__).resolve()
V8CampaignAdapterError = adapter_v7.V7CampaignAdapterError
EXPECTED_V7_ADAPTER_SHA256 = (
    "873ec412c8ac67db5e91731f31d648cf0bd509203b328f229721adb6a3f12b12"
)

TARGET_REGISTRY_SCHEMA_VERSION = (
    f"{implementation_v4.SCHEMA_VERSION}.target_registry.v8"
)
TARGET_DISCOVERY_PROGRESS_SCHEMA_VERSION = (
    f"{implementation_v4.SCHEMA_VERSION}.target_discovery.progress.v8"
)
STATE_VALIDATION_BINDING_SCHEMA_VERSION = (
    f"{implementation_v4.SCHEMA_VERSION}.state_validation_binding.v8"
)
TARGET_SELECTION_REVISION = (
    "v8_earliest_post_j180_all_30_seed_cross_state_exposure_v1_2026_09_06"
)
REQUIRED_COMPARABLE_SEED_COUNT = 30
CAMPAIGN_SEEDS = tuple(trace_package.CAMPAIGN_SEEDS)
MIN_FIXED_WINDOW_START_DAY = 180
MAX_FIXED_WINDOW_START_DAY = (
    implementation_v4.STATE_EVALUATION_DAYS
    - implementation_v4.INCIDENT_DISRUPTION_DAYS
)
TARGET_CELL_COUNT = (
    len(implementation_v4.OPERATING_POINT_IDS)
    * REQUIRED_COMPARABLE_SEED_COUNT
    * 18
)
SOURCE_TRACE_COUNT = (
    len(implementation_v4.OPERATING_POINT_IDS) * REQUIRED_COMPARABLE_SEED_COUNT
)
EXPOSURE_QUANTITY_FIELD = "shipped_qty"
EXPOSURE_QUANTITY_MEANING = "normally_deliverable_quantity"
SELECTION_STATUS = "accepted_earliest_post_j180_all_30_seed_comparable_42d_window"
POSITIVE_TARGET_STATUSES = frozenset(
    {
        "identified_unique_reference_shipment",
        "identified_reference_lane_day_shipment_group",
        "identified_reference_lane_window_shipment_group",
    }
)
_POSITIVE_QUANTITY_EPSILON = 1e-12

# These are exactly the fields created by the signed V7 trace importer.  A
# field carrying an incident result cannot silently enter the selection input.
BASELINE_SELECTION_TRACE_FIELDS = frozenset(
    {
        "day",
        "shipment_id",
        "risk_decision_day",
        "risk_event_ids",
        "src_node_id",
        "dst_node_id",
        "item_id",
        "edge_id",
        "shipped_qty",
        "pulled_qty",
        "lead_days",
        "arrival_day",
        "reliability",
        "uom",
    }
)


def validate_frozen_implementation() -> Path:
    """Fail closed if the V7 adapter being extended has changed."""

    path = Path(adapter_v7.__file__).resolve()
    digest = implementation_v4._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V7_ADAPTER_SHA256:
        raise V8CampaignAdapterError(f"Frozen V7 campaign adapter changed: {digest}")
    return adapter_v7.validate_frozen_implementation()


def _remove_obsolete_target_design_fields(payload: dict[str, Any]) -> None:
    payload.pop("design_seed", None)
    payload.pop("design_seed_excluded", None)
    payload.pop("design_seed_in_acceptance_statistics", None)
    payload.pop("design_seed_in_campaign_statistics", None)


def _build_v8_design_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Replace the obsolete one-seed target design with the V8 contract."""

    payload = dict(adapter_v7._build_v7_design_payload(*args, **kwargs))  # noqa: SLF001
    counts = dict(payload.get("expected_counts") or {})
    counts.update(
        {
            "auxiliary_discovery_runs": 0,
            "design_window_engine_runs": 0,
            "target_selection_engine_runs": 0,
            "imported_v7_campaign_baseline_service_proofs": SOURCE_TRACE_COUNT,
            "imported_v7_campaign_baseline_shipment_traces": SOURCE_TRACE_COUNT,
        }
    )
    preflight = dict(payload.get("operating_point_preflight_contract") or {})
    _remove_obsolete_target_design_fields(preflight)
    preflight.update(
        {
            "timing": (
                "signed_V7_state_binding_then_exposure_stratification_then_incident_probes"
            ),
            "target_selection_engine_runs": 0,
            "imported_shipment_trace_count": SOURCE_TRACE_COUNT,
            "incident_outcomes_used_for_target_selection": False,
        }
    )
    payload.update(
        {
            "target_selection_revision": TARGET_SELECTION_REVISION,
            "target_selection_engine_runs": 0,
            "expected_counts": counts,
            # Keep this exact signed bridge projection for provenance.  Its
            # legacy reserved cohort is historical and is not used by V8.
            "operating_points_cohorts": payload.get("operating_points_cohorts"),
            "v8_target_selection_cohort": {
                "campaign_baselines_used_for_exposure_stratification": list(
                    CAMPAIGN_SEEDS
                ),
                "source_trace_count": SOURCE_TRACE_COUNT,
                "reserved_target_design_cohort_used": False,
                "incident_outcomes_used": False,
            },
            "operating_point_preflight_contract": preflight,
            "target_discovery_contract": {
                "target_selection_revision": TARGET_SELECTION_REVISION,
                "source": "90_signed_V7_campaign_baseline_shipment_traces",
                "source_trace_count": SOURCE_TRACE_COUNT,
                "source_seed_count": REQUIRED_COMPARABLE_SEED_COUNT,
                "states": list(implementation_v4.OPERATING_POINT_IDS),
                "campaign_seeds": list(CAMPAIGN_SEEDS),
                "target_selection_engine_runs": 0,
                "disruption_window_days": (
                    implementation_v4.INCIDENT_DISRUPTION_DAYS
                ),
                "candidate_start_day_min": MIN_FIXED_WINDOW_START_DAY,
                "candidate_start_day_max": MAX_FIXED_WINDOW_START_DAY,
                "same_lane_specific_dates_across_states_and_campaign_seeds": True,
                "exposure_quantity_field": EXPOSURE_QUANTITY_FIELD,
                "exposure_quantity_meaning": EXPOSURE_QUANTITY_MEANING,
                "quantity_ratio_limit": (
                    implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO
                ),
                "required_comparable_seed_count": (
                    REQUIRED_COMPARABLE_SEED_COUNT
                ),
                "selection": (
                    "choose_the_earliest_start_from_J180_to_J678_with_positive_"
                    "shipped_qty_in_every_state_seed_cell_and_within_seed_cross_"
                    "state_max_over_min_ratio_at_most_1.5"
                ),
                "selection_uses_incident_outcomes": False,
                "selection_uses_actions": False,
                "selection_uses_observed_supplier_probability": False,
                "campaign_exposure_gate": (
                    "all_18_lanes_must_be_comparable_for_all_30_campaign_seeds"
                ),
                "exposure_gate_failure_policy": "block_all_incident_probes",
                "zero_flow_policy": "reject_lane_and_block_all_incident_probes",
                "interpretation": (
                    "conditional_exposure_stratification_not_random_incident_timing_"
                    "and_not_observed_supplier_performance"
                ),
            },
            "target_selection": {
                "target_selection_revision": TARGET_SELECTION_REVISION,
                "reference_kind": implementation_v4.TARGET_REFERENCE_KIND,
                "group_key": "lane_id+fixed_42_day_risk_decision_window",
                "source": "signed_paired_simulated_V7_campaign_baseline_shipments",
                "selection_rule": (
                    "earliest_fully_comparable_42_day_window_on_or_after_J180"
                ),
                "candidate_start_day_window": [
                    MIN_FIXED_WINDOW_START_DAY,
                    MAX_FIXED_WINDOW_START_DAY,
                ],
                "exposure_quantity_field": EXPOSURE_QUANTITY_FIELD,
                "exposure_quantity_meaning": EXPOSURE_QUANTITY_MEANING,
                "all_30_seeds_and_all_3_states_required": True,
                "cross_state_ratio_limit_within_each_seed": (
                    implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO
                ),
                "incident_outcomes_used": False,
                "new_engine_runs": 0,
                "target_claim": (
                    "fixed_conditional_supplier_stress_window_not_observed_incident"
                ),
            },
        }
    )
    return payload


def _build_v8_state_validation_binding(
    *, manifest: Mapping[str, Any], bridge: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind V7 authorization while keeping target selection semantically separate."""

    legacy = dict(
        adapter_v7._build_v7_state_validation_binding(  # noqa: SLF001
            manifest=manifest,
            bridge=bridge,
        )
    )
    legacy.pop("binding_signature", None)
    _remove_obsolete_target_design_fields(legacy)
    legacy.update(
        {
            "schema_version": STATE_VALIDATION_BINDING_SCHEMA_VERSION,
            "target_selection_revision": TARGET_SELECTION_REVISION,
            "target_selection_engine_runs": 0,
            "target_selection_source_trace_count": SOURCE_TRACE_COUNT,
            "target_selection_source_seed_count": (
                REQUIRED_COMPARABLE_SEED_COUNT
            ),
            "target_selection_uses_incident_outcomes": False,
            "target_selection_uses_reserved_seed": False,
            "interpretation": (
                "The accepted official V7 validation authorizes the three fixed "
                "operating states. The first 30 paired V7 baselines supply only "
                "initial conditions and shipment exposure for the outcome-blind "
                "V8 window selection; no incident result, retuning or new engine "
                "case is used here."
            ),
        }
    )
    return {
        **legacy,
        "binding_signature": implementation_v4._stable_sha256(legacy),  # noqa: SLF001
    }


def _assert_baseline_only_trace_matrix(
    shipment_rows_by_state_seed: Mapping[
        tuple[str, int], Sequence[Mapping[str, Any]]
    ],
) -> None:
    expected_keys = {
        (point_id, seed)
        for point_id in implementation_v4.OPERATING_POINT_IDS
        for seed in CAMPAIGN_SEEDS
    }
    if set(shipment_rows_by_state_seed) != expected_keys:
        raise ValueError("V8 target selection requires exactly 90 state/seed traces")
    for key, rows in shipment_rows_by_state_seed.items():
        if not isinstance(rows, Sequence):
            raise ValueError(f"V8 shipment trace is not a sequence: {key}")
        for row in rows:
            unexpected = set(row) - BASELINE_SELECTION_TRACE_FIELDS
            if unexpected:
                raise ValueError(
                    "Incident/outcome or unknown fields are forbidden in V8 target "
                    f"selection: {key}: {sorted(unexpected)}"
                )
            if str(row.get("risk_event_ids") or "").strip():
                raise ValueError(
                    "V8 target selection accepts baseline shipment traces only"
                )


def _rolling_shipped_quantities(
    rows: Sequence[Mapping[str, Any]], *, lane: Any
) -> dict[int, float]:
    daily = implementation_v4._lane_day_quantity_map(rows, lane=lane)  # noqa: SLF001
    prefix = [0.0] * (implementation_v4.STATE_EVALUATION_DAYS + 1)
    for day in range(implementation_v4.STATE_EVALUATION_DAYS):
        prefix[day + 1] = prefix[day] + float(daily.get(day, 0.0))
    window = implementation_v4.INCIDENT_DISRUPTION_DAYS
    return {
        start: prefix[start + window] - prefix[start]
        for start in range(
            MIN_FIXED_WINDOW_START_DAY,
            MAX_FIXED_WINDOW_START_DAY + 1,
        )
    }


def _rolling_shipped_matrix(
    shipment_rows_by_state_seed: Mapping[
        tuple[str, int], Sequence[Mapping[str, Any]]
    ],
    *,
    lanes: Sequence[Any],
) -> dict[str, dict[tuple[str, int], dict[int, float]]]:
    """Scan each compact trace once rather than once for every one of 18 lanes."""

    lane_by_edge = {lane.edge_id: lane for lane in lanes}
    if len(lane_by_edge) != len(lanes):
        raise ValueError("V8 lane edge identities are not unique")
    result: dict[str, dict[tuple[str, int], dict[int, float]]] = {
        lane.lane_id: {} for lane in lanes
    }
    day_count = implementation_v4.STATE_EVALUATION_DAYS
    window = implementation_v4.INCIDENT_DISRUPTION_DAYS
    for key, rows in shipment_rows_by_state_seed.items():
        daily = {lane.lane_id: [0.0] * day_count for lane in lanes}
        for row in rows:
            lane = lane_by_edge.get(str(row.get("edge_id") or ""))
            if lane is None or not implementation_v4._lane_matches(row, lane):  # noqa: SLF001
                continue
            day = implementation_v4._as_int(  # noqa: SLF001
                row.get("risk_decision_day"), -1
            )
            pulled = implementation_v4._as_float(  # noqa: SLF001
                row.get("pulled_qty"), 0.0
            )
            shipped = implementation_v4._as_float(  # noqa: SLF001
                row.get("shipped_qty"), 0.0
            )
            if (
                0 <= day < day_count
                and pulled > _POSITIVE_QUANTITY_EPSILON
                and shipped > _POSITIVE_QUANTITY_EPSILON
                and str(row.get("shipment_id") or "").strip()
            ):
                daily[lane.lane_id][day] += shipped
        for lane in lanes:
            prefix = [0.0] * (day_count + 1)
            lane_daily = daily[lane.lane_id]
            for day, value in enumerate(lane_daily):
                prefix[day + 1] = prefix[day] + value
            result[lane.lane_id][key] = {
                start: prefix[start + window] - prefix[start]
                for start in range(
                    MIN_FIXED_WINDOW_START_DAY,
                    MAX_FIXED_WINDOW_START_DAY + 1,
                )
            }
    return result


def _quantity_ratio(values: Sequence[float]) -> float:
    smallest = min(values)
    if smallest <= _POSITIVE_QUANTITY_EPSILON:
        return math.inf
    return max(values) / smallest


def _finite_or_empty(value: float) -> float | str:
    return value if math.isfinite(value) else ""


def _quantity_summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "median": float(statistics.median(values)),
        "maximum": max(values),
        "sum": sum(values),
    }


def _eligible_starts(
    quantities: Mapping[tuple[str, int], Mapping[int, float]],
) -> list[int]:
    eligible: list[int] = []
    limit = implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO
    for start in range(
        MIN_FIXED_WINDOW_START_DAY,
        MAX_FIXED_WINDOW_START_DAY + 1,
    ):
        valid = True
        for seed in CAMPAIGN_SEEDS:
            values = [
                quantities[(point_id, seed)][start]
                for point_id in implementation_v4.OPERATING_POINT_IDS
            ]
            if (
                min(values) <= _POSITIVE_QUANTITY_EPSILON
                or _quantity_ratio(values) > limit + 1e-12
            ):
                valid = False
                break
        if valid:
            eligible.append(start)
    return eligible


def build_cross_state_target_registry(
    *,
    manifest: Mapping[str, Any],
    points: Sequence[Mapping[str, Any]],
    lanes: Sequence[Any],
    shipment_rows_by_state_seed: Mapping[
        tuple[str, int], Sequence[Mapping[str, Any]]
    ],
) -> dict[str, Any]:
    """Build the signed V8 matrix from the 90 baseline shipment traces only."""

    point_ids = [str(point["operating_point_id"]) for point in points]
    if point_ids != list(implementation_v4.OPERATING_POINT_IDS):
        raise ValueError("V8 target selection requires the three ordered states")
    if len(lanes) != 18 or len({lane.lane_id for lane in lanes}) != 18:
        raise ValueError("V8 target selection requires exactly 18 unique lanes")
    if len(CAMPAIGN_SEEDS) != REQUIRED_COMPARABLE_SEED_COUNT:
        raise ValueError("V8 target selection requires the frozen 30 campaign seeds")
    _assert_baseline_only_trace_matrix(shipment_rows_by_state_seed)

    quantities_by_lane = _rolling_shipped_matrix(
        shipment_rows_by_state_seed,
        lanes=lanes,
    )

    targets: list[dict[str, Any]] = []
    lane_contracts: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    exposure_gate_failures: list[dict[str, Any]] = []
    for lane in lanes:
        quantities = quantities_by_lane[lane.lane_id]
        eligible = _eligible_starts(quantities)
        if not eligible:
            lane_contracts.append(
                {
                    "lane_id": lane.lane_id,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "target_product_id": lane.target_product_id,
                    "selection_status": "rejected_no_fully_comparable_42d_window",
                    "eligible_candidate_window_count": 0,
                    "eligible_window_start_days": [],
                    "comparable_campaign_seed_count": 0,
                    "required_comparable_seed_count": (
                        REQUIRED_COMPARABLE_SEED_COUNT
                    ),
                    "state_comparison_valid": False,
                    "target_selection_engine_runs": 0,
                    "incident_outcomes_used": False,
                }
            )
            exposure_gate_failures.append(
                {
                    "lane_id": lane.lane_id,
                    "reason": (
                        "no_J180_J678_window_is_positive_and_ratio_comparable_"
                        "for_all_30_seeds"
                    ),
                }
            )
            continue

        fixed_start = eligible[0]
        fixed_end = (
            fixed_start + implementation_v4.INCIDENT_DISRUPTION_DAYS - 1
        )
        per_seed_targets: dict[int, dict[str, dict[str, Any]]] = {}
        shipped_by_state: dict[str, list[float]] = {
            point_id: [] for point_id in implementation_v4.OPERATING_POINT_IDS
        }
        pulled_by_state: dict[str, list[float]] = {
            point_id: [] for point_id in implementation_v4.OPERATING_POINT_IDS
        }
        seed_exposures: list[dict[str, Any]] = []
        for seed in CAMPAIGN_SEEDS:
            shipped_quantities = {
                point_id: quantities[(point_id, seed)][fixed_start]
                for point_id in implementation_v4.OPERATING_POINT_IDS
            }
            shipped_ratio = _quantity_ratio(list(shipped_quantities.values()))
            state_targets: dict[str, dict[str, Any]] = {}
            for point_id in implementation_v4.OPERATING_POINT_IDS:
                target = implementation_v4.select_unique_reference_shipment(
                    shipment_rows_by_state_seed[(point_id, seed)],
                    lane=lane,
                    days=None,
                    forced_decision_day=fixed_start,
                    target_window_days=(
                        implementation_v4.INCIDENT_DISRUPTION_DAYS
                    ),
                    state_match_metadata={
                        "cross_state_match_status": SELECTION_STATUS,
                        "cross_state_common_day_found": True,
                        "cross_state_common_window_found": True,
                        # Compatibility field consumed by the mature case writer;
                        # V8 explicitly declares that its basis is shipped_qty.
                        "cross_state_quantity_ratio": shipped_ratio,
                        "cross_state_shipped_quantity_ratio": shipped_ratio,
                        "cross_state_quantity_basis": EXPOSURE_QUANTITY_FIELD,
                        "cross_state_match_threshold_ratio": (
                            implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO
                        ),
                        "state_comparison_valid": True,
                        "seed_cross_state_exposure_comparable": True,
                        "comparable_campaign_seed_count": (
                            REQUIRED_COMPARABLE_SEED_COUNT
                        ),
                        "required_comparable_seed_count": (
                            REQUIRED_COMPARABLE_SEED_COUNT
                        ),
                        "cross_state_matched_min_group_qty": min(
                            shipped_quantities.values()
                        ),
                        "cross_state_matched_max_group_qty": max(
                            shipped_quantities.values()
                        ),
                        "cross_state_matched_quantities_json": json.dumps(
                            shipped_quantities,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "target_selected_independently_by_operating_point": False,
                        "target_selection_basis": TARGET_SELECTION_REVISION,
                        "selection_rule": (
                            "earliest_J180_J678_window_comparable_on_shipped_qty_"
                            "for_all_30_seeds_and_3_states"
                        ),
                    },
                )
                if (
                    target.get("target_status") not in POSITIVE_TARGET_STATUSES
                    or float(target.get("target_expected_delivered_qty") or 0.0)
                    <= _POSITIVE_QUANTITY_EPSILON
                ):
                    raise ValueError(
                        "V8 selected an eligible window but did not recover its "
                        f"positive baseline shipments: {lane.lane_id}/{point_id}/{seed}"
                    )
                expected = shipped_quantities[point_id]
                actual = float(target["target_expected_delivered_qty"])
                if not math.isclose(
                    actual,
                    expected,
                    rel_tol=1e-10,
                    abs_tol=1e-8,
                ):
                    raise ValueError(
                        "V8 shipped-quantity exposure differs from selected target"
                    )
                state_targets[point_id] = target
                shipped_by_state[point_id].append(actual)
                pulled_by_state[point_id].append(float(target["target_planned_qty"]))
            pulled_quantities = {
                point_id: float(state_targets[point_id]["target_planned_qty"])
                for point_id in implementation_v4.OPERATING_POINT_IDS
            }
            pulled_ratio = _quantity_ratio(list(pulled_quantities.values()))
            for target in state_targets.values():
                target["cross_state_pulled_quantity_ratio_descriptive"] = (
                    _finite_or_empty(pulled_ratio)
                )
                target["cross_state_pulled_quantities_json_descriptive"] = json.dumps(
                    pulled_quantities,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            per_seed_targets[seed] = state_targets
            seed_exposures.append(
                {
                    "seed": seed,
                    "shipped_quantities": shipped_quantities,
                    "shipped_quantity_ratio": shipped_ratio,
                    "pulled_quantities_descriptive": pulled_quantities,
                    "pulled_quantity_ratio_descriptive": (
                        _finite_or_empty(pulled_ratio)
                    ),
                    "comparable_on_shipped_qty": True,
                }
            )

        lane_contracts.append(
            {
                "lane_id": lane.lane_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "target_product_id": lane.target_product_id,
                "selection_status": SELECTION_STATUS,
                "fixed_window_start_day": fixed_start,
                "fixed_window_end_day": fixed_end,
                "disruption_window_days": (
                    implementation_v4.INCIDENT_DISRUPTION_DAYS
                ),
                "candidate_start_day_min": MIN_FIXED_WINDOW_START_DAY,
                "candidate_start_day_max": MAX_FIXED_WINDOW_START_DAY,
                "eligible_candidate_window_count": len(eligible),
                "eligible_window_start_days": eligible,
                "selected_start_is_earliest_eligible": True,
                "exposure_quantity_field": EXPOSURE_QUANTITY_FIELD,
                "exposure_quantity_meaning": EXPOSURE_QUANTITY_MEANING,
                "selected_window_shipped_qty_summary_by_state": {
                    point_id: _quantity_summary(shipped_by_state[point_id])
                    for point_id in implementation_v4.OPERATING_POINT_IDS
                },
                "selected_window_pulled_qty_summary_by_state_descriptive": {
                    point_id: _quantity_summary(pulled_by_state[point_id])
                    for point_id in implementation_v4.OPERATING_POINT_IDS
                },
                "seed_exposures": seed_exposures,
                "comparable_campaign_seed_count": (
                    REQUIRED_COMPARABLE_SEED_COUNT
                ),
                "required_comparable_seed_count": (
                    REQUIRED_COMPARABLE_SEED_COUNT
                ),
                "state_comparison_valid": True,
                "target_selection_engine_runs": 0,
                "incident_outcomes_used": False,
            }
        )
        for seed in CAMPAIGN_SEEDS:
            for point_id in implementation_v4.OPERATING_POINT_IDS:
                target = per_seed_targets[seed][point_id]
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
                        "fixed_window_end_day": fixed_end,
                        "fixed_window_shipped_qty": float(
                            target["target_expected_delivered_qty"]
                        ),
                        "fixed_window_pulled_qty_descriptive": float(
                            target["target_planned_qty"]
                        ),
                        "seed_cross_state_shipped_exposure_comparable": True,
                    }
                )

    gate_passed = not exposure_gate_failures
    unsigned = {
        "schema_version": TARGET_REGISTRY_SCHEMA_VERSION,
        "target_selection_revision": TARGET_SELECTION_REVISION,
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "source_operating_points_artifact_signature": manifest[
            "operating_points_artifact_signature"
        ],
        "source_shipment_trace_index_signature": manifest[
            "operating_points_trace_index_signature"
        ],
        "source_trace_count": SOURCE_TRACE_COUNT,
        "source_trace_cell_count": SOURCE_TRACE_COUNT,
        "target_cell_count": len(targets),
        "target_selection_engine_runs": 0,
        "incident_outcomes_used": False,
        "incident_probes_started": False,
        "states": list(implementation_v4.OPERATING_POINT_IDS),
        "seeds": list(CAMPAIGN_SEEDS),
        "campaign_seeds": list(CAMPAIGN_SEEDS),
        "lanes": [lane.lane_id for lane in lanes],
        "discovery_days": implementation_v4.DISCOVERY_DAYS,
        "disruption_window_days": implementation_v4.INCIDENT_DISRUPTION_DAYS,
        "candidate_start_day_min": MIN_FIXED_WINDOW_START_DAY,
        "candidate_start_day_max": MAX_FIXED_WINDOW_START_DAY,
        "exposure_quantity_field": EXPOSURE_QUANTITY_FIELD,
        "exposure_quantity_meaning": EXPOSURE_QUANTITY_MEANING,
        "state_match_max_quantity_ratio": (
            implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO
        ),
        "required_comparable_seed_count": REQUIRED_COMPARABLE_SEED_COUNT,
        "selection_contract": (
            "earliest_lane_specific_fixed_42d_window_in_J180_J678_positive_"
            "and_cross_state_ratio_le_1.5_for_each_of_all_30_campaign_seeds"
        ),
        "campaign_exposure_gate_contract": (
            "all_18_lanes_require_30_of_30_seed_comparability_on_shipped_qty"
        ),
        "all_lane_windows_comparable": gate_passed,
        "campaign_exposure_gate_passed": gate_passed,
        "exposure_gate_failures": exposure_gate_failures,
        "lane_contracts": lane_contracts,
        "targets": targets,
        "state_exposure_descriptive": exposure_rows,
    }
    registry = {
        **unsigned,
        "registry_signature": implementation_v4._stable_sha256(unsigned),  # noqa: SLF001
    }
    if gate_passed:
        validate_v8_target_registry_payload(
            registry,
            manifest=manifest,
            lanes=lanes,
            shipment_rows_by_state_seed=shipment_rows_by_state_seed,
        )
    return registry


def _target_matrix(
    registry: Mapping[str, Any],
) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    result: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for raw in registry.get("targets") or []:
        if not isinstance(raw, Mapping):
            raise ValueError("V8 target registry contains a non-object target")
        key = (
            str(raw.get("operating_point_id") or ""),
            implementation_v4._as_int(raw.get("seed"), -1),  # noqa: SLF001
            str(raw.get("lane_id") or ""),
        )
        if key in result:
            raise ValueError(f"Duplicate V8 target cell: {key}")
        result[key] = raw
    return result


def validate_v8_target_registry_payload(
    registry: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    lanes: Sequence[Any],
    shipment_rows_by_state_seed: Mapping[
        tuple[str, int], Sequence[Mapping[str, Any]]
    ]
    | None = None,
) -> dict[str, Any]:
    """Validate signature, 30x3x18 matrix and optional source-trace replay."""

    unsigned = dict(registry)
    signature = str(unsigned.pop("registry_signature", ""))
    if not signature or signature != implementation_v4._stable_sha256(unsigned):  # noqa: SLF001
        raise ValueError("V8 target registry signature is invalid")
    expected_lane_ids = [lane.lane_id for lane in lanes]
    expected_keys = {
        (point_id, seed, lane_id)
        for point_id in implementation_v4.OPERATING_POINT_IDS
        for seed in CAMPAIGN_SEEDS
        for lane_id in expected_lane_ids
    }
    lane_contracts = registry.get("lane_contracts") or []
    contract_by_lane = {
        str(row.get("lane_id") or ""): row
        for row in lane_contracts
        if isinstance(row, Mapping)
    }
    targets = _target_matrix(registry)
    if (
        registry.get("schema_version") != TARGET_REGISTRY_SCHEMA_VERSION
        or registry.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or registry.get("campaign_signature") != manifest.get("campaign_signature")
        or registry.get("engine_sha256") != manifest.get("engine_sha256")
        or registry.get("source_operating_points_artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or registry.get("source_shipment_trace_index_signature")
        != manifest.get("operating_points_trace_index_signature")
        or registry.get("source_trace_count") != SOURCE_TRACE_COUNT
        or registry.get("source_trace_cell_count") != SOURCE_TRACE_COUNT
        or registry.get("target_cell_count") != TARGET_CELL_COUNT
        or registry.get("target_selection_engine_runs") != 0
        or registry.get("incident_outcomes_used") is not False
        or registry.get("incident_probes_started") is not False
        or registry.get("states") != list(implementation_v4.OPERATING_POINT_IDS)
        or registry.get("seeds") != list(CAMPAIGN_SEEDS)
        or registry.get("campaign_seeds") != list(CAMPAIGN_SEEDS)
        or registry.get("lanes") != expected_lane_ids
        or registry.get("disruption_window_days")
        != implementation_v4.INCIDENT_DISRUPTION_DAYS
        or registry.get("candidate_start_day_min") != MIN_FIXED_WINDOW_START_DAY
        or registry.get("candidate_start_day_max") != MAX_FIXED_WINDOW_START_DAY
        or registry.get("exposure_quantity_field") != EXPOSURE_QUANTITY_FIELD
        or registry.get("exposure_quantity_meaning") != EXPOSURE_QUANTITY_MEANING
        or not math.isclose(
            float(registry.get("state_match_max_quantity_ratio") or math.nan),
            implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or registry.get("required_comparable_seed_count")
        != REQUIRED_COMPARABLE_SEED_COUNT
        or registry.get("all_lane_windows_comparable") is not True
        or registry.get("campaign_exposure_gate_passed") is not True
        or registry.get("exposure_gate_failures") != []
        or len(lane_contracts) != 18
        or set(contract_by_lane) != set(expected_lane_ids)
        or len(targets) != TARGET_CELL_COUNT
        or set(targets) != expected_keys
    ):
        raise ValueError("V8 target registry header or matrix contract is invalid")
    if "design_seed" in json.dumps(registry, sort_keys=True):
        raise ValueError("Obsolete design-seed semantics are forbidden in V8 registry")
    declared_signature = str(manifest.get("target_registry_signature") or "")
    if declared_signature and signature != declared_signature:
        raise ValueError("V8 registry differs from the campaign manifest signature")

    replay_quantities: dict[str, dict[tuple[str, int], dict[int, float]]] = {}
    if shipment_rows_by_state_seed is not None:
        _assert_baseline_only_trace_matrix(shipment_rows_by_state_seed)
        replay_quantities = _rolling_shipped_matrix(
            shipment_rows_by_state_seed,
            lanes=lanes,
        )

    exposure_rows = registry.get("state_exposure_descriptive") or []
    exposure_by_key = {
        (
            str(row.get("operating_point_id") or ""),
            implementation_v4._as_int(row.get("seed"), -1),  # noqa: SLF001
            str(row.get("lane_id") or ""),
        ): row
        for row in exposure_rows
        if isinstance(row, Mapping)
    }
    if len(exposure_rows) != TARGET_CELL_COUNT or set(exposure_by_key) != expected_keys:
        raise ValueError("V8 descriptive exposure matrix is incomplete")

    for lane_id in expected_lane_ids:
        contract = contract_by_lane[lane_id]
        eligible = contract.get("eligible_window_start_days")
        fixed_start = implementation_v4._as_int(  # noqa: SLF001
            contract.get("fixed_window_start_day"), -1
        )
        fixed_end = implementation_v4._as_int(  # noqa: SLF001
            contract.get("fixed_window_end_day"), -1
        )
        if (
            contract.get("selection_status") != SELECTION_STATUS
            or not isinstance(eligible, list)
            or not eligible
            or eligible != sorted(set(eligible))
            or any(
                not isinstance(start, int)
                or not MIN_FIXED_WINDOW_START_DAY
                <= start
                <= MAX_FIXED_WINDOW_START_DAY
                for start in eligible
            )
            or fixed_start != eligible[0]
            or fixed_end
            != fixed_start + implementation_v4.INCIDENT_DISRUPTION_DAYS - 1
            or contract.get("eligible_candidate_window_count") != len(eligible)
            or contract.get("selected_start_is_earliest_eligible") is not True
            or contract.get("exposure_quantity_field") != EXPOSURE_QUANTITY_FIELD
            or contract.get("exposure_quantity_meaning")
            != EXPOSURE_QUANTITY_MEANING
            or contract.get("comparable_campaign_seed_count")
            != REQUIRED_COMPARABLE_SEED_COUNT
            or contract.get("required_comparable_seed_count")
            != REQUIRED_COMPARABLE_SEED_COUNT
            or contract.get("state_comparison_valid") is not True
            or contract.get("target_selection_engine_runs") != 0
            or contract.get("incident_outcomes_used") is not False
        ):
            raise ValueError(f"Malformed V8 lane contract: {lane_id}")
        if replay_quantities:
            replay_eligible = _eligible_starts(replay_quantities[lane_id])
            if eligible != replay_eligible or fixed_start != replay_eligible[0]:
                raise ValueError(
                    f"V8 earliest-window selection differs from source traces: {lane_id}"
                )

        comparable_count = 0
        for seed in CAMPAIGN_SEEDS:
            state_rows = [
                targets[(point_id, seed, lane_id)]
                for point_id in implementation_v4.OPERATING_POINT_IDS
            ]
            shipped = [
                float(row.get("target_expected_delivered_qty") or math.nan)
                for row in state_rows
            ]
            pulled = [
                float(row.get("target_planned_qty") or math.nan)
                for row in state_rows
            ]
            if any(not math.isfinite(value) or value <= 0.0 for value in shipped):
                raise ValueError("V8 shipped-quantity exposure must be positive")
            if any(not math.isfinite(value) or value <= 0.0 for value in pulled):
                raise ValueError("V8 pulled quantity must be positive")
            shipped_ratio = _quantity_ratio(shipped)
            pulled_ratio = _quantity_ratio(pulled)
            comparable = shipped_ratio <= (
                implementation_v4.STATE_MATCH_MAX_QUANTITY_RATIO + 1e-12
            )
            comparable_count += int(comparable)
            for point_id, row, shipped_qty, pulled_qty in zip(
                implementation_v4.OPERATING_POINT_IDS,
                state_rows,
                shipped,
                pulled,
                strict=True,
            ):
                key = (point_id, seed, lane_id)
                exposure = exposure_by_key[key]
                shipments = row.get("target_shipments")
                if not isinstance(shipments, list) or not shipments:
                    raise ValueError("V8 target lacks baseline shipment details")
                shipment_shipped = sum(
                    float(item.get("expected_delivered_qty") or 0.0)
                    for item in shipments
                    if isinstance(item, Mapping)
                )
                shipment_pulled = sum(
                    float(item.get("pulled_qty") or 0.0)
                    for item in shipments
                    if isinstance(item, Mapping)
                )
                if (
                    row.get("target_status") not in POSITIVE_TARGET_STATUSES
                    or implementation_v4._as_int(  # noqa: SLF001
                        row.get("target_window_start_day"), -1
                    )
                    != fixed_start
                    or implementation_v4._as_int(  # noqa: SLF001
                        row.get("target_window_end_day"), -1
                    )
                    != fixed_end
                    or implementation_v4._as_int(  # noqa: SLF001
                        row.get("target_window_days"), -1
                    )
                    != implementation_v4.INCIDENT_DISRUPTION_DAYS
                    or row.get("cross_state_match_status") != SELECTION_STATUS
                    or row.get("cross_state_quantity_basis")
                    != EXPOSURE_QUANTITY_FIELD
                    or row.get("state_comparison_valid") is not True
                    or row.get("seed_cross_state_exposure_comparable") is not True
                    or row.get("comparable_campaign_seed_count")
                    != REQUIRED_COMPARABLE_SEED_COUNT
                    or row.get("required_comparable_seed_count")
                    != REQUIRED_COMPARABLE_SEED_COUNT
                    or row.get("target_selected_independently_by_operating_point")
                    is not False
                    or row.get("target_selection_basis")
                    != TARGET_SELECTION_REVISION
                    or not math.isclose(
                        float(row.get("cross_state_shipped_quantity_ratio") or math.nan),
                        shipped_ratio,
                        rel_tol=1e-10,
                        abs_tol=1e-12,
                    )
                    or not math.isclose(
                        float(row.get("cross_state_quantity_ratio") or math.nan),
                        shipped_ratio,
                        rel_tol=1e-10,
                        abs_tol=1e-12,
                    )
                    or not math.isclose(
                        float(
                            row.get(
                                "cross_state_pulled_quantity_ratio_descriptive"
                            )
                            or math.nan
                        ),
                        pulled_ratio,
                        rel_tol=1e-10,
                        abs_tol=1e-12,
                    )
                    or not math.isclose(
                        shipment_shipped, shipped_qty, rel_tol=1e-10, abs_tol=1e-8
                    )
                    or not math.isclose(
                        shipment_pulled, pulled_qty, rel_tol=1e-10, abs_tol=1e-8
                    )
                    or not math.isclose(
                        float(exposure.get("fixed_window_shipped_qty") or math.nan),
                        shipped_qty,
                        rel_tol=1e-10,
                        abs_tol=1e-8,
                    )
                    or not math.isclose(
                        float(
                            exposure.get("fixed_window_pulled_qty_descriptive")
                            or math.nan
                        ),
                        pulled_qty,
                        rel_tol=1e-10,
                        abs_tol=1e-8,
                    )
                ):
                    raise ValueError(f"V8 target cell is inconsistent: {key}")
                if replay_quantities:
                    replay = replay_quantities[lane_id][(point_id, seed)][fixed_start]
                    if not math.isclose(
                        replay,
                        shipped_qty,
                        rel_tol=1e-10,
                        abs_tol=1e-8,
                    ):
                        raise ValueError(
                            f"V8 target shipped exposure differs from trace: {key}"
                        )
        if comparable_count != REQUIRED_COMPARABLE_SEED_COUNT:
            raise ValueError(f"V8 lane is not comparable on all 30 seeds: {lane_id}")
    return dict(registry)


def _validate_v8_state_binding(
    binding: Mapping[str, Any], *, manifest: Mapping[str, Any]
) -> None:
    unsigned = dict(binding)
    signature = str(unsigned.pop("binding_signature", ""))
    if (
        binding.get("schema_version") != STATE_VALIDATION_BINDING_SCHEMA_VERSION
        or binding.get("status") != implementation_v4.HOLDOUT_ACCEPTED_STATUS
        or binding.get("campaign_signature") != manifest.get("campaign_signature")
        or binding.get("operating_points_artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or binding.get("v7_campaign_trace_index_signature")
        != manifest.get("operating_points_trace_index_signature")
        or binding.get("campaign_seeds") != list(CAMPAIGN_SEEDS)
        or binding.get("campaign_seed_count")
        != REQUIRED_COMPARABLE_SEED_COUNT
        or binding.get("state_validation_engine_runs_in_campaign") != 0
        or binding.get("imported_official_service_proof_count")
        != SOURCE_TRACE_COUNT
        or binding.get("imported_official_shipment_trace_count")
        != SOURCE_TRACE_COUNT
        or binding.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or binding.get("target_selection_engine_runs") != 0
        or binding.get("target_selection_source_trace_count") != SOURCE_TRACE_COUNT
        or binding.get("target_selection_source_seed_count")
        != REQUIRED_COMPARABLE_SEED_COUNT
        or binding.get("target_selection_uses_incident_outcomes") is not False
        or binding.get("target_selection_uses_reserved_seed") is not False
        or binding.get("retuning_after_holdout") is not False
        or signature != implementation_v4._stable_sha256(unsigned)  # noqa: SLF001
        or signature
        != str(manifest.get("state_validation_binding_signature") or "")
        or "design_seed" in json.dumps(binding, sort_keys=True)
    ):
        raise ValueError("V8 state-validation binding fails its signed contract")


def run_target_discovery(
    *,
    output_dir: Path,
    manifest: Mapping[str, Any],
    points: Sequence[Mapping[str, Any]],
    lanes: Sequence[Any],
    workers: int,
) -> dict[str, Any]:
    """Revalidate 90 signed traces and freeze targets without an engine run."""

    del workers  # target selection is deterministic and purely trace based
    bridge_path = Path(str(manifest["operating_points_source"])).resolve()
    bridge = implementation_v4.v4_bridge.validate_bridge(
        bridge_path,
        revalidate_source=True,
    )
    if (
        bridge["artifact_signature"]
        != manifest["operating_points_artifact_signature"]
        or bridge["trace_index_signature"]
        != manifest["operating_points_trace_index_signature"]
    ):
        raise ValueError("V7 bridge differs from the signed V8 campaign manifest")
    binding = _build_v8_state_validation_binding(manifest=manifest, bridge=bridge)
    discovery_dir = output_dir.resolve() / "target_discovery"
    discovery_dir.mkdir(parents=True, exist_ok=True)
    binding_path = discovery_dir / "state_validation_binding.json"
    if binding_path.is_file():
        if implementation_v4._read_json(binding_path) != binding:  # noqa: SLF001
            raise ValueError("Existing V8 state-validation binding changed")
    else:
        implementation_v4._write_json_atomic(binding_path, binding)  # noqa: SLF001
    progress_path = discovery_dir / "progress.json"

    def write_progress(status: str, imported_trace_count: int) -> None:
        implementation_v4._write_json_atomic(  # noqa: SLF001
            progress_path,
            {
                "schema_version": TARGET_DISCOVERY_PROGRESS_SCHEMA_VERSION,
                "target_selection_revision": TARGET_SELECTION_REVISION,
                "campaign_signature": manifest["campaign_signature"],
                "status": status,
                "engine_runs_planned": 0,
                "engine_runs_completed": 0,
                "engine_runs_failed": 0,
                "target_selection_engine_runs": 0,
                "signed_v7_service_proofs_imported": imported_trace_count,
                "signed_v7_shipment_traces_imported": imported_trace_count,
                "state_validation_engine_runs": 0,
                "state_validation_binding_status": binding["status"],
                "required_comparable_seed_count": (
                    REQUIRED_COMPARABLE_SEED_COUNT
                ),
                "incident_outcomes_used": False,
                "incident_probes_started": False,
                "updated_at": implementation_v4.utc_now(),
            },
        )

    write_progress("revalidating_signed_v7_traces", 0)
    shipment_rows = implementation_v4._import_v4_holdout_shipment_rows(  # noqa: SLF001
        bridge_path=bridge_path,
        bridge=bridge,
        points=points,
        lanes=lanes,
    )
    write_progress("selecting_earliest_comparable_windows", SOURCE_TRACE_COUNT)
    registry = build_cross_state_target_registry(
        manifest=manifest,
        points=points,
        lanes=lanes,
        shipment_rows_by_state_seed=shipment_rows,
    )
    registry_path = discovery_dir / "target_registry.json"
    if registry_path.is_file():
        if implementation_v4._read_json(registry_path) != registry:  # noqa: SLF001
            raise ValueError("Existing target registry differs from V8 discovery")
    else:
        implementation_v4._write_json_atomic(registry_path, registry)  # noqa: SLF001

    manifest_path = output_dir.resolve() / "campaign_manifest.json"
    current_manifest = implementation_v4._read_json(manifest_path)  # noqa: SLF001
    shared_fields = {
        "state_validation_binding": str(binding_path.resolve()),
        "state_validation_binding_sha256": implementation_v4._sha256_file(  # noqa: SLF001
            binding_path
        ),
        "state_validation_binding_signature": binding["binding_signature"],
        "state_validation_binding_status": binding["status"],
        "target_registry": str(registry_path.resolve()),
        "target_registry_sha256": implementation_v4._sha256_file(  # noqa: SLF001
            registry_path
        ),
        "target_registry_signature": registry["registry_signature"],
        "target_selection_revision": TARGET_SELECTION_REVISION,
        "target_selection_engine_runs": 0,
    }
    if registry.get("campaign_exposure_gate_passed") is not True:
        current_manifest.update(
            {
                **shared_fields,
                "target_discovery_status": "rejected",
                "target_exposure_comparability_status": "rejected",
            }
        )
        implementation_v4._write_json_atomic(manifest_path, current_manifest)  # noqa: SLF001
        write_progress("failed_target_exposure_comparability", SOURCE_TRACE_COUNT)
        raise RuntimeError(
            "V8 could not find a fully comparable 42-day window for every lane; "
            "no incident probe was started"
        )
    current_manifest.update(
        {
            **shared_fields,
            "target_discovery_completed_at_utc": implementation_v4.utc_now(),
            "target_discovery_status": "complete",
            "target_exposure_comparability_status": "accepted_30_of_30",
        }
    )
    implementation_v4._write_json_atomic(manifest_path, current_manifest)  # noqa: SLF001
    write_progress("complete", SOURCE_TRACE_COUNT)
    return registry


def load_target_registry(
    *, output_dir: Path, manifest: Mapping[str, Any], lanes: Sequence[Any]
) -> dict[str, Any]:
    """Load and validate the native V8 target registry before any shard runs."""

    if (
        manifest.get("target_discovery_status") != "complete"
        or manifest.get("target_exposure_comparability_status")
        != "accepted_30_of_30"
        or manifest.get("state_validation_binding_status")
        != implementation_v4.HOLDOUT_ACCEPTED_STATUS
        or manifest.get("target_selection_revision") != TARGET_SELECTION_REVISION
        or manifest.get("target_selection_engine_runs") != 0
    ):
        raise ValueError("V8 target discovery is not fully accepted")
    binding_path = Path(
        str(manifest.get("state_validation_binding") or "")
    ).resolve()
    if (
        not binding_path.is_file()
        or implementation_v4._sha256_file(binding_path)  # noqa: SLF001
        != str(manifest.get("state_validation_binding_sha256") or "")
    ):
        raise ValueError("Signed V8 state-validation binding is missing or changed")
    binding = implementation_v4._read_json(binding_path)  # noqa: SLF001
    _validate_v8_state_binding(binding, manifest=manifest)
    path = output_dir.resolve() / "target_discovery" / "target_registry.json"
    declared_path = Path(str(manifest.get("target_registry") or "")).resolve()
    if path != declared_path or not path.is_file():
        raise FileNotFoundError("V8 target registry is missing or misbound")
    if implementation_v4._sha256_file(path) != str(  # noqa: SLF001
        manifest.get("target_registry_sha256") or ""
    ):
        raise ValueError("V8 target registry file changed after discovery")
    registry = implementation_v4._read_json(path)  # noqa: SLF001
    return validate_v8_target_registry_payload(
        registry,
        manifest=manifest,
        lanes=lanes,
    )


def _parse_v8_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Expose the native V8 trace-selection contract in command-line help."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("plan", "discover-targets", "run-shard", "smoke"),
        default="plan",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=implementation_v4.DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--operating-points",
        type=Path,
        required=True,
        help=(
            "Accepted signed V7 bridge containing the first 30 paired campaign "
            "baselines and their 90 compact shipment traces. Target selection "
            "runs no simulation and reads no incident outcome."
        ),
    )
    parser.add_argument(
        "--lane-reference",
        type=Path,
        default=implementation_v4.DEFAULT_LANE_REFERENCE,
    )
    parser.add_argument(
        "--engine",
        type=Path,
        default=implementation_v4.DEFAULT_ENGINE,
    )
    parser.add_argument(
        "--engine-profile",
        type=Path,
        default=implementation_v4.DEFAULT_PROFILE,
    )
    parser.add_argument(
        "--operating-point-id",
        choices=implementation_v4.OPERATING_POINT_IDS,
        default=None,
    )
    parser.add_argument(
        "--seed-block",
        type=int,
        choices=range(1, len(implementation_v4.SEED_BLOCKS) + 1),
        default=None,
    )
    parser.add_argument(
        "--workers",
        type=int,
        choices=range(1, implementation_v4.MAX_WORKERS + 1),
        default=2,
    )
    parser.add_argument(
        "--reuse-evidence-dir",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument(
        "--stop-after-baselines",
        action="store_true",
        help=(
            "Diagnostic mode: finish adaptive incident probes and paired "
            "baselines, then stop before final incident materialization."
        ),
    )
    parser.add_argument(
        "--smoke-seed",
        type=int,
        default=None,
        help="Optional frozen V7 campaign seed override.",
    )
    parser.add_argument("--smoke-lane-id", default=None)
    return parser.parse_args(argv)


@contextmanager
def patched_v8_context() -> Iterator[None]:
    """Patch only target discovery while inheriting the frozen V7 bridge."""

    validate_frozen_implementation()
    with adapter_v7.patched_v7_context():
        previous_file: Any = implementation_v4.__file__
        previous_design_payload: Any = implementation_v4._design_payload  # noqa: SLF001
        previous_binding_builder: Any = (  # noqa: SLF001
            implementation_v4._build_v4_state_validation_binding
        )
        previous_registry_builder: Any = (
            implementation_v4.build_cross_state_target_registry
        )
        previous_discovery_runner: Any = implementation_v4.run_target_discovery
        previous_registry_loader: Any = implementation_v4.load_target_registry
        previous_parse_args: Any = implementation_v4.parse_args
        implementation_v4.__file__ = str(ADAPTER_PATH)
        implementation_v4._design_payload = _build_v8_design_payload  # noqa: SLF001
        implementation_v4._build_v4_state_validation_binding = (  # noqa: SLF001
            _build_v8_state_validation_binding
        )
        implementation_v4.build_cross_state_target_registry = (
            build_cross_state_target_registry
        )
        implementation_v4.run_target_discovery = run_target_discovery
        implementation_v4.load_target_registry = load_target_registry
        implementation_v4.parse_args = _parse_v8_args
        try:
            yield
        finally:
            implementation_v4.__file__ = previous_file
            implementation_v4._design_payload = previous_design_payload  # noqa: SLF001
            implementation_v4._build_v4_state_validation_binding = (  # noqa: SLF001
                previous_binding_builder
            )
            implementation_v4.build_cross_state_target_registry = (
                previous_registry_builder
            )
            implementation_v4.run_target_discovery = previous_discovery_runner
            implementation_v4.load_target_registry = previous_registry_loader
            implementation_v4.parse_args = previous_parse_args


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v8_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
