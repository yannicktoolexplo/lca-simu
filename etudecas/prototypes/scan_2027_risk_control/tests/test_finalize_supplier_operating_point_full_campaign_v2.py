from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v2 as finalizer,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v2 as runner,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v2 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_multiseed_refinement_v2 import (
    _prepare_v1,
    _raw_evidence,
)


STRICT_SOURCE_VALIDATOR = runner._validate_pending_multiseed_source


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _signed(payload: dict[str, object], signature_field: str) -> dict[str, object]:
    return {**payload, signature_field: finalizer._stable_sha256(payload)}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _resign_campaign_manifest(manifest: dict[str, object]) -> None:
    manifest["campaign_signature"] = finalizer._stable_sha256(
        {
            key: value
            for key, value in manifest.items()
            if key not in finalizer.UNSIGNED_MANIFEST_RUNTIME_FIELDS
        }
    )


@pytest.fixture(autouse=True)
def _stub_strict_source_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the large finalizer fixture focused on finalization semantics.

    Dedicated tests below restore the real dispatcher against genuine V1/V2/V3
    producer evidence.  This stub only describes the already hash-checked
    synthetic fixture chain used by the pre-existing business tests.
    """

    def validate(path: Path, payload: dict[str, object]) -> dict[str, object]:
        plan_reference = dict(payload.get("plan") or {})
        plan_dir = Path(str(plan_reference["path"])).resolve()
        plan_path = plan_dir / "refinement_plan.json"
        selection_reference = dict(payload.get("selection") or {})
        selection_path = (
            path.parent
            / str(selection_reference.get("relative_path") or "selection.json")
        ).resolve()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        return {
            "producer": "v2_refinement",
            "plan_path": str(plan_dir),
            "plan_manifest_path": str(plan_path),
            "plan_signature": str(plan["plan_signature"]),
            "selection_path": str(selection_path),
            "selection_signature": str(selection["selection_signature"]),
            "holdout_contract": dict(plan["holdout_contract"]),
        }

    monkeypatch.setattr(runner, "_validate_pending_multiseed_source", validate)


def _rewrite_signed_registry(
    root: Path, manifest: dict[str, object], registry: dict[str, object]
) -> None:
    registry_path = Path(str(manifest["target_registry"]))
    unsigned = dict(registry)
    unsigned.pop("registry_signature", None)
    signed = _signed(unsigned, "registry_signature")
    _write_json(registry_path, signed)
    manifest["target_registry_sha256"] = finalizer._sha256(registry_path)
    manifest["target_registry_signature"] = signed["registry_signature"]
    _write_json(root / "campaign_manifest.json", manifest)


def _rewrite_signed_preflight(
    root: Path, manifest: dict[str, object], preflight: dict[str, object]
) -> None:
    preflight_path = Path(str(manifest["operating_point_preflight"]))
    unsigned = dict(preflight)
    unsigned.pop("preflight_signature", None)
    signed = _signed(unsigned, "preflight_signature")
    _write_json(preflight_path, signed)
    manifest["operating_point_preflight_sha256"] = finalizer._sha256(preflight_path)
    manifest["operating_point_preflight_signature"] = signed["preflight_signature"]
    _write_json(root / "campaign_manifest.json", manifest)


def _shard_id(point: str, seed: int) -> str:
    block = (seed - finalizer.EXPECTED_SEEDS[0]) // 5 + 1
    return f"{point}__seed_block_{block:02d}"


def _fixture(
    tmp_path: Path,
    *,
    no_exposure: set[tuple[str, str, int]] | None = None,
    incomparable_lane: str | None = None,
) -> tuple[Path, Path, pd.DataFrame, dict[str, object]]:
    no_exposure = no_exposure or set()
    root = tmp_path / "campaign"
    discovery = root / "target_discovery"
    discovery.mkdir(parents=True)
    campaign_signature = "a" * 64
    engine_sha256 = "b" * 64
    profile_sha256 = "c" * 64
    state_labels = {"op_100": 100.0, "op_93": 92.72, "op_80": 79.91}
    achieved = {
        "op_100": (99.82, 99.70, 99.94),
        "op_93": (92.41, 93.20, 91.62),
        "op_80": (79.77, 83.54, 76.00),
    }
    lanes = [f"lane_{index:02d}" for index in range(finalizer.EXPECTED_LANE_COUNT)]
    lane_rows = [
        {
            "lane_id": lane,
            "supplier_id": f"supplier_{index:02d}",
            "item_id": f"item:{index:06d}",
            "dst_node_id": "M-1810" if index < 9 else "M-1430",
            "edge_id": f"edge:{index:02d}",
            "target_product_id": "268091" if index < 9 else "268967",
            "planned_lead_days": 30.0,
        }
        for index, lane in enumerate(lanes)
    ]
    cohorts = {
        "design": [runner.TARGET_DESIGN_SEED],
        "calibration": list(range(340282, 340287)),
        "holdout_sealed": list(finalizer.EXPECTED_SEEDS),
    }
    holdout_contract = {
        **runner._required_campaign_holdout_contract(),
        "status": "sealed_unread",
        "cases_in_this_plan": 0,
    }
    source_hashes = {
        "engine_sha256": engine_sha256,
        "profile_sha256": profile_sha256,
    }
    selection_contract = {"fixture_preserves_signed_selection": True}
    provenance_dir = root / "operating_point_provenance"
    provenance_dir.mkdir()
    plan = _signed(
        {
            "schema_version": ("etudecas.multiseed_operating_point_refinement.v2.plan"),
            "status": "planned_not_executed",
            "source_hashes": source_hashes,
            "cohorts": cohorts,
            "selection_contract": selection_contract,
            "holdout_contract": holdout_contract,
        },
        "plan_signature",
    )
    plan_path = provenance_dir / "refinement_plan.json"
    _write_json(plan_path, plan)
    selection = _signed(
        {
            "schema_version": (
                "etudecas.multiseed_operating_point_refinement.v2.selection"
            ),
            "status": "five_seed_loo_screen_passed_pending_holdout",
            "plan_signature": plan["plan_signature"],
            "calibration_seeds": list(range(340282, 340287)),
            "holdout_seeds_sealed_and_unread": list(finalizer.EXPECTED_SEEDS),
            "holdout_cases_read": 0,
            "selection_contract": selection_contract,
            "holdout_contract": holdout_contract,
            "selected_pair": {
                "op93_candidate_key": "fixture_op93",
                "op80_candidate_key": "fixture_op80",
            },
            "holdout_launch_permitted": True,
            "fallback_required": False,
        },
        "selection_signature",
    )
    selection_path = provenance_dir / "selection.json"
    _write_json(selection_path, selection)
    selected_points = []
    for point in finalizer.OPERATING_POINTS:
        _, product_091, product_967 = achieved[point]
        selected_points.append(
            {
                "operating_point_id": point,
                "target_service": state_labels[point] / 100.0,
                "calibration_pooled_service": state_labels[point] / 100.0,
                "calibration_product_268091_service": product_091 / 100.0,
                "calibration_product_268967_service": product_967 / 100.0,
                "graph_sha256": _digest(f"graph__{point}"),
            }
        )
    selected_source = _signed(
        {
            "schema_version": runner.V2_POINTS_SCHEMA_VERSION,
            "status": runner.V2_POINTS_PENDING_STATUS,
            "plan": {
                "path": str(provenance_dir.resolve()),
                "plan_signature": plan["plan_signature"],
            },
            "selection": {
                "relative_path": selection_path.name,
                "schema_version": (
                    "etudecas.multiseed_operating_point_refinement.v2.selection"
                ),
                "selection_signature": selection["selection_signature"],
            },
            "selection_signature": selection["selection_signature"],
            "source_hashes": source_hashes,
            "cohorts": cohorts,
            "holdout_contract": holdout_contract,
            "holdout_validated": False,
            "holdout_cases_read": 0,
            "simulation_hypotheses_not_observed_performance": True,
            "target_labels_apply_to_global_service_only": True,
            "operating_points": selected_points,
        },
        "artifact_signature",
    )
    selected_source_path = provenance_dir / "selected_operating_points.json"
    _write_json(selected_source_path, selected_source)

    preflight_states = []
    for point in finalizer.OPERATING_POINTS:
        global_service, product_091, product_967 = achieved[point]
        preflight_states.append(
            {
                "operating_point_id": point,
                "target_service_pct": state_labels[point],
                "campaign_seed_count": 30,
                "service_global_ratio_of_sums_pct": global_service,
                "service_268091_ratio_of_sums_pct": product_091,
                "service_268967_ratio_of_sums_pct": product_967,
                "service_global_seed_median_pct": global_service,
                "global_service_bootstrap_ci95_low_pct": global_service,
                "global_service_bootstrap_ci95_high_pct": global_service,
                "accepted": True,
                "failures": [],
            }
        )
    preflight = _signed(
        {
            "schema_version": runner.PREFLIGHT_SCHEMA_VERSION,
            "contract_revision": runner.CONTRACT_REVISION,
            "campaign_signature": campaign_signature,
            "status": runner.HOLDOUT_ACCEPTED_STATUS,
            "campaign_seed_count": 30,
            "campaign_seeds": list(finalizer.EXPECTED_SEEDS),
            "calibration_seeds_excluded": list(range(340282, 340287)),
            "holdout_used_once_without_retuning": True,
            "operating_points_input_status": runner.V2_POINTS_PENDING_STATUS,
            "operating_points_artifact_signature": selected_source[
                "artifact_signature"
            ],
            "operating_points_calibration_plan_signature": plan["plan_signature"],
            "operating_points_selection_signature": selection["selection_signature"],
            "no_incident_probe_before_holdout_acceptance": True,
            "design_seed": runner.TARGET_DESIGN_SEED,
            "design_seed_in_acceptance_statistics": False,
            "bootstrap": {
                "method": "paired_common_seed_resampling",
                "replicates": finalizer.BOOTSTRAP_REPLICATES,
                "seed": finalizer.BOOTSTRAP_SEED,
            },
            "ordering_valid": True,
            "pooled_ordering_by_measure": {
                "global": True,
                "268091": True,
                "268967": True,
            },
            "seed_ordering_valid": True,
            "seed_order_counts": {"global": 30, "268091": 30, "268967": 30},
            "joint_seed_order_count": 30,
            "joint_seed_order_required": 24,
            "minimum_seed_order_count": 24,
            "product_seed_ordering_checks": {
                "268091": {
                    "ordered_seed_count": 30,
                    "ordering_observed_in_at_least_24_of_30_seeds": True,
                    "acceptance_gate": True,
                },
                "268967": {
                    "ordered_seed_count": 30,
                    "ordering_observed_in_at_least_24_of_30_seeds": True,
                    "acceptance_gate": True,
                },
            },
            "states": preflight_states,
        },
        "preflight_signature",
    )
    preflight_path = discovery / "operating_point_preflight.json"
    _write_json(preflight_path, preflight)

    comparable_seed_by_lane: dict[str, dict[int, bool]] = {}
    comparable_by_lane: dict[str, int] = {}
    for lane in lanes:
        flags = {
            seed: (
                seed_index < (23 if lane == incomparable_lane else 30)
                and all(
                    (point, lane, seed) not in no_exposure
                    for point in finalizer.OPERATING_POINTS
                )
            )
            for seed_index, seed in enumerate(finalizer.EXPECTED_SEEDS)
        }
        comparable_seed_by_lane[lane] = flags
        comparable_by_lane[lane] = sum(flags.values())
    target_rows: list[dict[str, object]] = []
    for point in finalizer.OPERATING_POINTS:
        for seed_index, seed in enumerate(finalizer.EXPECTED_SEEDS):
            for lane_index, lane in enumerate(lanes):
                exposed = (point, lane, seed) not in no_exposure
                comparable = comparable_seed_by_lane[lane][seed]
                quantity = (1000.0 + lane_index) if exposed else 0.0
                if lane == incomparable_lane and seed_index >= 23 and point == "op_100":
                    quantity *= 2.0
                all_states_exposed = all(
                    (state, lane, seed) not in no_exposure
                    for state in finalizer.OPERATING_POINTS
                )
                quantity_ratio: float | str = (
                    2.0
                    if all_states_exposed
                    and lane == incomparable_lane
                    and seed_index >= 23
                    else (1.0 if all_states_exposed else "")
                )
                start = 100 + lane_index
                target_rows.append(
                    {
                        "operating_point_id": point,
                        "seed": seed,
                        "lane_id": lane,
                        "target_status": (
                            "identified_aggregated_lane_window"
                            if exposed
                            else "identified_registered_window_no_positive_flow"
                        ),
                        "target_window_start_day": start,
                        "target_window_end_day": start
                        + runner.INCIDENT_DISRUPTION_DAYS
                        - 1,
                        "target_window_days": runner.INCIDENT_DISRUPTION_DAYS,
                        "target_shipment_count": 2 if exposed else 0,
                        "target_planned_qty": quantity,
                        "target_expected_delivered_qty": quantity,
                        "cross_state_match_status": (
                            f"calibration_design_comparable_"
                            f"{runner.INCIDENT_DISRUPTION_DAYS}d_window"
                        ),
                        "cross_state_quantity_ratio": quantity_ratio,
                        "cross_state_match_threshold_ratio": 1.5,
                        "seed_cross_state_exposure_comparable": comparable,
                        "state_comparison_valid": comparable_by_lane[lane] >= 24,
                        "comparable_campaign_seed_count": comparable_by_lane[lane],
                        "required_comparable_seed_count": 24,
                    }
                )
    registry = _signed(
        {
            "schema_version": f"{runner.SCHEMA_VERSION}.target_registry.v4",
            "campaign_signature": campaign_signature,
            "engine_sha256": engine_sha256,
            "design_seed": runner.TARGET_DESIGN_SEED,
            "campaign_seeds": list(finalizer.EXPECTED_SEEDS),
            "discovery_days": 720,
            "disruption_window_days": runner.INCIDENT_DISRUPTION_DAYS,
            "state_match_max_quantity_ratio": 1.5,
            "required_comparable_seed_count": 24,
            "campaign_exposure_gate_contract": (
                "all_18_lanes_require_a_common_positive_design_window_with_quantity_"
                "ratio_at_most_1.5_and_at_least_24_of_30_holdout_seeds_comparable"
            ),
            "all_lane_design_windows_comparable": True,
            "all_lane_holdout_exposures_comparable": all(
                count >= 24 for count in comparable_by_lane.values()
            ),
            "campaign_exposure_gate_passed": all(
                count >= 24 for count in comparable_by_lane.values()
            ),
            "exposure_gate_failures": (
                []
                if all(count >= 24 for count in comparable_by_lane.values())
                else [
                    {
                        "lane_id": lane,
                        "reasons": [
                            "fewer_than_24_of_30_holdout_seeds_have_comparable_exposure"
                        ],
                    }
                    for lane, count in comparable_by_lane.items()
                    if count < 24
                ]
            ),
            "states": list(finalizer.OPERATING_POINTS),
            "seeds": list(finalizer.EXPECTED_SEEDS),
            "lanes": lanes,
            "lane_contracts": [
                {
                    "lane_id": lane,
                    "design_seed": runner.TARGET_DESIGN_SEED,
                    "design_status": (
                        f"calibration_design_comparable_"
                        f"{runner.INCIDENT_DISRUPTION_DAYS}d_window"
                    ),
                    "fixed_window_start_day": 100 + index,
                    "fixed_window_end_day": 100
                    + index
                    + runner.INCIDENT_DISRUPTION_DAYS
                    - 1,
                    "design_quantities": {
                        point: 1000.0 + index for point in finalizer.OPERATING_POINTS
                    },
                    "design_quantity_ratio": 1.0,
                    "comparable_campaign_seed_count": comparable_by_lane[lane],
                    "required_comparable_seed_count": 24,
                    "state_comparison_valid": comparable_by_lane[lane] >= 24,
                }
                for index, lane in enumerate(lanes)
            ],
            "targets": target_rows,
        },
        "registry_signature",
    )
    registry_path = discovery / "target_registry.json"
    _write_json(registry_path, registry)
    _write_json(
        discovery / "progress.json",
        {
            "schema_version": f"{runner.SCHEMA_VERSION}.target_discovery.progress.v1",
            "campaign_signature": campaign_signature,
            "status": "complete",
            "planned": 93,
            "completed": 93,
            "failed": 0,
            "running": 0,
        },
    )

    shards = []
    for point in finalizer.OPERATING_POINTS:
        for block in range(1, 7):
            shard_id = f"{point}__seed_block_{block:02d}"
            block_seeds = list(finalizer.EXPECTED_SEEDS[(block - 1) * 5 : block * 5])
            shards.append(
                {
                    "shard_id": shard_id,
                    "operating_point_id": point,
                    "seed_ids": block_seeds,
                    "baseline_rows": 5,
                    "incident_rows": 180,
                    "total_rows": 185,
                }
            )
            _write_json(
                root / "shards" / shard_id / "progress.json",
                {
                    "schema_version": runner.PROGRESS_SCHEMA_VERSION,
                    "campaign_signature": campaign_signature,
                    "shard_id": shard_id,
                    "status": "complete",
                    "planned_case_count": 185,
                    "completed_case_count": 185,
                    "failed_case_count": 0,
                    "running_case_keys": [],
                    "errors": [],
                },
            )
    manifest: dict[str, object] = {
        "schema_version": runner.SCHEMA_VERSION,
        "contract_revision": runner.CONTRACT_REVISION,
        "status": "planned",
        "campaign_signature": campaign_signature,
        "engine_sha256": engine_sha256,
        "engine_profile_sha256": profile_sha256,
        "days": "adaptive_by_operating_point_seed_and_incident_target",
        "simulation_days": "adaptive_by_operating_point_seed_and_incident_target",
        "adaptive_horizon_contract": {"fixed_upper_bound_assumed": False},
        "state_evaluation_window": {"start_day": 0, "end_day": 719, "day_count": 720},
        "incident_impact_window": {
            "anchor": (
                f"first_day_of_fixed_{runner.INCIDENT_DISRUPTION_DAYS}_day_"
                "supplier_disruption_window"
            ),
            "day_count": 360,
        },
        "target_discovery_contract": {
            "design_seed": runner.TARGET_DESIGN_SEED,
            "disruption_window_days": runner.INCIDENT_DISRUPTION_DAYS,
            "same_lane_specific_dates_across_states_and_campaign_seeds": True,
            "quantity_ratio_limit": 1.5,
            "minimum_comparable_campaign_seeds": 24,
        },
        "impact_metric_contract": {
            "primary": (
                "paired_service_loss_pp_of_finished_product_fed_by_lane_on_fixed_360d_envelope"
            ),
            "full_horizon_cost_pairing_comparable": False,
        },
        "states": [
            {
                "operating_point_id": point,
                "operating_point_service_pct": state_labels[point],
                "target_service_pct": state_labels[point],
                "calibration_pooled_service_pct": state_labels[point],
                "calibration_product_268091_service_pct": achieved[point][1],
                "calibration_product_268967_service_pct": achieved[point][2],
                "graph_sha256": _digest(f"graph__{point}"),
            }
            for point in finalizer.OPERATING_POINTS
        ],
        "lanes": lane_rows,
        "mechanisms": [asdict(mechanism) for mechanism in runner.MECHANISMS],
        "seeds": list(finalizer.EXPECTED_SEEDS),
        "operating_points_source": str(selected_source_path.resolve()),
        "operating_points_source_sha256": finalizer._sha256(selected_source_path),
        "operating_points_producer": "v2_refinement",
        "operating_points_schema_version": runner.V2_POINTS_SCHEMA_VERSION,
        "operating_points_artifact_signature": selected_source["artifact_signature"],
        "operating_points_input_status": runner.V2_POINTS_PENDING_STATUS,
        "operating_points_cohorts": cohorts,
        "operating_points_calibration_plan": str(plan_path.resolve()),
        "operating_points_calibration_plan_sha256": finalizer._sha256(plan_path),
        "operating_points_calibration_plan_signature": plan["plan_signature"],
        "operating_points_selection": str(selection_path.resolve()),
        "operating_points_selection_sha256": finalizer._sha256(selection_path),
        "operating_points_selection_signature": selection["selection_signature"],
        "operating_points_holdout_contract": holdout_contract,
        "shards": shards,
        "expected_counts": {
            "auxiliary_discovery_runs": 93,
            "baseline_rows": 90,
            "incident_rows": 3240,
            "total_rows": 3330,
            "shard_count": 18,
            "rows_per_shard": 185,
        },
        "target_selection": {
            "target_claim": (
                f"fixed_{runner.INCIDENT_DISRUPTION_DAYS}_day_simulated_supplier_"
                "disruption_window_not_an_observed_incident"
            )
        },
        "quality_branch_included": False,
        "quality_incident_included": False,
        "availability_incident_included": False,
        "capacity_incident_included": False,
        "stock_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "historical_incident_probability_estimated": False,
        "all_lots_traced_claimed": False,
        "operating_point_preflight": str(preflight_path.resolve()),
        "operating_point_preflight_sha256": finalizer._sha256(preflight_path),
        "operating_point_preflight_signature": preflight["preflight_signature"],
        "operating_point_preflight_status": runner.HOLDOUT_ACCEPTED_STATUS,
        "target_registry": str(registry_path.resolve()),
        "target_registry_sha256": finalizer._sha256(registry_path),
        "target_registry_signature": registry["registry_signature"],
        "target_discovery_status": "complete",
    }

    signed_design = {
        key: value
        for key, value in manifest.items()
        if key not in finalizer.UNSIGNED_MANIFEST_RUNTIME_FIELDS
    }
    campaign_signature = finalizer._stable_sha256(signed_design)
    manifest["campaign_signature"] = campaign_signature

    unsigned_preflight = dict(preflight)
    unsigned_preflight.pop("preflight_signature")
    unsigned_preflight["campaign_signature"] = campaign_signature
    preflight = _signed(unsigned_preflight, "preflight_signature")
    _write_json(preflight_path, preflight)

    unsigned_registry = dict(registry)
    unsigned_registry.pop("registry_signature")
    unsigned_registry["campaign_signature"] = campaign_signature
    registry = _signed(unsigned_registry, "registry_signature")
    _write_json(registry_path, registry)

    manifest.update(
        {
            "operating_point_preflight_sha256": finalizer._sha256(preflight_path),
            "operating_point_preflight_signature": preflight["preflight_signature"],
            "target_registry_sha256": finalizer._sha256(registry_path),
            "target_registry_signature": registry["registry_signature"],
        }
    )
    _write_json(
        discovery / "progress.json",
        {
            "schema_version": f"{runner.SCHEMA_VERSION}.target_discovery.progress.v1",
            "campaign_signature": campaign_signature,
            "status": "complete",
            "planned": 93,
            "completed": 93,
            "failed": 0,
            "running": 0,
        },
    )
    for progress_path in root.glob("shards/*/progress.json"):
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        progress["campaign_signature"] = campaign_signature
        _write_json(progress_path, progress)

    discovery_evidence_dir = discovery / "evidence"
    for point in finalizer.OPERATING_POINTS:
        state = next(
            item for item in manifest["states"] if item["operating_point_id"] == point
        )
        _, service_091, service_967 = achieved[point]
        demand_091 = 100_000.0
        demand_967 = 100_000.0
        on_due_091 = demand_091 * service_091 / 100.0
        on_due_967 = demand_967 * service_967 / 100.0
        for seed in (finalizer.DESIGN_SEED, *finalizer.EXPECTED_SEEDS):
            discovery_signature = finalizer._stable_sha256(
                {
                    "campaign_signature": campaign_signature,
                    "engine_sha256": engine_sha256,
                    "engine_profile_sha256": manifest["engine_profile_sha256"],
                    "point_id": point,
                    "graph_sha256": state["graph_sha256"],
                    "seed": seed,
                    "simulation_days": finalizer.STATE_EVALUATION_DAYS,
                    "purpose": (
                        f"cross_state_{runner.INCIDENT_DISRUPTION_DAYS}d_"
                        "target_discovery"
                    ),
                }
            )
            unsigned_evidence: dict[str, object] = {
                "schema_version": (f"{runner.SCHEMA_VERSION}.target_discovery.case.v1"),
                "campaign_signature": campaign_signature,
                "engine_sha256": engine_sha256,
                "discovery_signature": discovery_signature,
                "operating_point_id": point,
                "seed": seed,
                "simulation_days": finalizer.STATE_EVALUATION_DAYS,
                "warmup_core_state_sha256": _digest(f"discovery-warmup-{point}-{seed}"),
                "summary_sha256": _digest(f"discovery-summary-{point}-{seed}"),
                "state_service_metrics": {
                    "demand_qty_268091": demand_091,
                    "demand_qty_268967": demand_967,
                    "demand_qty_global": demand_091 + demand_967,
                    "on_due_qty_268091": on_due_091,
                    "on_due_qty_268967": on_due_967,
                    "on_due_qty_global": on_due_091 + on_due_967,
                },
                "shipment_rows": [],
                "created_at_utc": "2026-09-04T12:00:00+00:00",
            }
            signed_evidence = _signed(unsigned_evidence, "evidence_signature")
            _write_json(
                discovery_evidence_dir / f"{point}__target_discovery__seed_{seed}.json",
                signed_evidence,
            )

    manifest_path = root / "campaign_manifest.json"
    _write_json(manifest_path, manifest)

    target_lookup = {
        (row["operating_point_id"], row["seed"], row["lane_id"]): row
        for row in target_rows
    }
    rows: list[dict[str, object]] = []
    baseline_signatures: dict[tuple[str, int], str] = {}
    warmup_signatures: dict[tuple[str, int], str] = {}
    state_factor = {"op_100": 0.8, "op_93": 1.0, "op_80": 1.2}
    for point in finalizer.OPERATING_POINTS:
        for seed in finalizer.EXPECTED_SEEDS:
            shard_id = _shard_id(point, seed)
            baseline_key = f"{point}__baseline__seed_{seed}"
            baseline_signature = _digest(baseline_key)
            warmup_signature = _digest(f"warmup__{point}__{seed}")
            baseline_signatures[(point, seed)] = baseline_signature
            warmup_signatures[(point, seed)] = warmup_signature
            baseline = {field: "" for field in runner.METRIC_FIELDS}
            baseline.update(
                {
                    "schema_version": runner.CASE_SCHEMA_VERSION,
                    "campaign_signature": campaign_signature,
                    "engine_sha256": engine_sha256,
                    "shard_id": shard_id,
                    "operating_point_id": point,
                    "operating_point_service_pct": state_labels[point],
                    "simulation_days": 820 + (seed % 3) * 20,
                    "state_evaluation_days": 720,
                    "stage": "baseline",
                    "mechanism": "baseline",
                    "seed": seed,
                    "status": "valid",
                    "valid": True,
                    "case_key": baseline_key,
                    "case_signature": baseline_signature,
                    "baseline_case_signature": baseline_signature,
                    "service_output_product_268091_pct": achieved[point][1],
                    "service_output_product_268967_pct": achieved[point][2],
                    "service_global_pct": achieved[point][0],
                    "warmup_core_state_sha256": warmup_signature,
                    "summary_sha256": _digest(f"summary__{baseline_key}"),
                    "validation_errors": "",
                }
            )
            rows.append(baseline)
            for lane_index, lane in enumerate(lanes):
                target = target_lookup[(point, seed, lane)]
                product = "268091" if lane_index < 9 else "268967"
                for mechanism in finalizer.MECHANISMS:
                    case_key = f"{point}__{lane}__{mechanism}__seed_{seed}"
                    physical = float(target["target_planned_qty"]) > 0
                    primary_loss = 0.0
                    if lane_index == 17 and physical:
                        primary_loss = (
                            0.9 * state_factor[point]
                            + (seed - finalizer.EXPECTED_SEEDS[0]) * 0.001
                        )
                    other_loss = primary_loss * 0.35
                    loss_091 = primary_loss if product == "268091" else other_loss
                    loss_967 = primary_loss if product == "268967" else other_loss
                    global_loss = 0.6 * loss_091 + 0.4 * loss_967
                    causal_factor = 0.75
                    causal_091 = loss_091 * causal_factor
                    causal_967 = loss_967 * causal_factor
                    causal_global = global_loss * causal_factor
                    base_service = {"op_100": 99.0, "op_93": 92.0, "op_80": 79.0}[point]
                    demand_091 = 100_000.0 + (seed % 4) * 100
                    demand_967 = 80_000.0 + (seed % 5) * 100
                    demand_global = demand_091 + demand_967
                    fed_demand = demand_091 if product == "268091" else demand_967
                    impact_on_due_fed = primary_loss / 100.0 * fed_demand
                    impact_on_due_global = global_loss / 100.0 * demand_global
                    causal_on_due_fed = (
                        primary_loss * causal_factor / 100.0 * fed_demand
                    )
                    causal_on_due_global = causal_global / 100.0 * demand_global
                    impact_backlog = primary_loss * 1000.0
                    causal_backlog = primary_loss * causal_factor * 1100.0
                    production_loss = primary_loss * 200.0
                    causal_production_loss = primary_loss * causal_factor * 200.0
                    start = int(target["target_window_start_day"])
                    impact_end = start + finalizer.BUSINESS_WINDOW_DAYS - 1
                    causal_start = start + 30 if physical else start
                    causal_end = causal_start + 149 if physical else impact_end
                    simulation_days = (
                        max(720, impact_end + 1, causal_end + 1) + lane_index % 3
                    )
                    target_qty = float(target["target_planned_qty"])
                    shortfall_qty = (
                        0.5 * target_qty
                        if mechanism == "planned_delivery_shortfall"
                        else 0.0
                    )
                    affected_qty = target_qty
                    contract = finalizer.MECHANISM_CONTRACT[mechanism]
                    incident = {field: "" for field in runner.METRIC_FIELDS}
                    incident.update(
                        {
                            "schema_version": runner.CASE_SCHEMA_VERSION,
                            "campaign_signature": campaign_signature,
                            "engine_sha256": engine_sha256,
                            "shard_id": shard_id,
                            "operating_point_id": point,
                            "operating_point_service_pct": state_labels[point],
                            "simulation_days": simulation_days,
                            "state_evaluation_days": 720,
                            "stage": "incident",
                            "mechanism": mechanism,
                            "lane_id": lane,
                            "supplier_id": f"supplier_{lane_index:02d}",
                            "item_id": f"item:{lane_index:06d}",
                            "dst_node_id": "M-1810" if lane_index < 9 else "M-1430",
                            "edge_id": f"edge:{lane_index:02d}",
                            "target_product_id": product,
                            "seed": seed,
                            "status": "valid" if physical else "valid_no_exposure",
                            "valid": True,
                            "case_key": case_key,
                            "case_signature": _digest(case_key),
                            "baseline_case_signature": baseline_signatures[
                                (point, seed)
                            ],
                            "target_status": target["target_status"],
                            "target_selection_mode": (
                                "aggregated_lane_window"
                                if physical
                                else "registered_cross_state_window_no_flow"
                            ),
                            "target_reference_kind": finalizer.TARGET_REFERENCE_KIND,
                            "target_shipment_count": target["target_shipment_count"],
                            "target_window_start_day": start,
                            "target_window_end_day": target["target_window_end_day"],
                            "target_window_days": target["target_window_days"],
                            "target_planned_qty": target_qty,
                            "target_expected_delivered_qty": target_qty,
                            "target_uom": "UN" if physical else "no_flow",
                            "target_selected_independently_by_operating_point": False,
                            "state_comparison_valid": target["state_comparison_valid"],
                            "seed_cross_state_exposure_comparable": target[
                                "seed_cross_state_exposure_comparable"
                            ],
                            "comparable_campaign_seed_count": target[
                                "comparable_campaign_seed_count"
                            ],
                            "required_comparable_seed_count": 24,
                            "impact_window_start_day": start,
                            "impact_window_end_day": impact_end,
                            "impact_window_days": 360,
                            "impact_window_fully_observed": True,
                            "causal_window_start_day": causal_start,
                            "causal_window_end_day": causal_end,
                            "causal_window_days": causal_end - causal_start + 1,
                            "causal_window_defined": physical,
                            "causal_window_fully_observed": True,
                            "required_simulation_days": simulation_days,
                            "risk_type": contract["risk_type"],
                            "risk_value": contract["risk_value"],
                            "risk_start_day": start,
                            "risk_end_day": target["target_window_end_day"],
                            "risk_applied_row_count": 1 if physical else 0,
                            "risk_applied_event_count": 1 if physical else 0,
                            "incident_physically_exercised": physical,
                            "incident_shipment_count": 2 if physical else 0,
                            "incident_affected_pulled_qty": affected_qty,
                            "quantity_shortfall_qty": shortfall_qty,
                            "arrival_delay_days": (
                                120.0 if mechanism == "transport_delay" else 0.0
                            ),
                            "incident_effective_dose_qty": (
                                shortfall_qty
                                if mechanism == "planned_delivery_shortfall"
                                else ""
                            ),
                            "incident_effective_dose_qty_days": (
                                120.0 * affected_qty
                                if mechanism == "transport_delay"
                                else ""
                            ),
                            "baseline_impact_service_268091_pct": base_service,
                            "baseline_impact_service_268967_pct": base_service,
                            "baseline_impact_service_global_pct": base_service,
                            "impact_service_268091_pct": base_service - loss_091,
                            "impact_service_268967_pct": base_service - loss_967,
                            "impact_service_global_pct": base_service - global_loss,
                            "impact_service_loss_268091_pp": loss_091,
                            "impact_service_loss_268967_pp": loss_967,
                            "impact_service_loss_global_pp": global_loss,
                            "impact_service_loss_fed_product_pp": primary_loss,
                            "baseline_impact_demand_268091_qty": demand_091,
                            "baseline_impact_demand_268967_qty": demand_967,
                            "baseline_impact_demand_global_qty": demand_global,
                            "impact_demand_268091_qty": demand_091,
                            "impact_demand_268967_qty": demand_967,
                            "impact_demand_global_qty": demand_global,
                            "impact_on_due_loss_fed_product_qty": impact_on_due_fed,
                            "impact_on_due_loss_global_qty": impact_on_due_global,
                            "impact_on_due_loss_fed_product_share_of_demand": (
                                impact_on_due_fed / fed_demand
                            ),
                            "impact_on_due_loss_global_share_of_demand": (
                                impact_on_due_global / demand_global
                            ),
                            "impact_backlog_qty_days_delta": impact_backlog,
                            "impact_backlog_qty_days_per_demand_unit": (
                                impact_backlog / demand_global
                            ),
                            "impact_max_backlog_qty_delta": primary_loss * 100.0,
                            "impact_production_loss_fed_product_qty": production_loss,
                            "impact_production_loss_fed_product_share_of_demand": (
                                production_loss / fed_demand
                            ),
                            "baseline_causal_service_268091_pct": base_service,
                            "baseline_causal_service_268967_pct": base_service,
                            "baseline_causal_service_global_pct": base_service,
                            "causal_service_268091_pct": base_service - causal_091,
                            "causal_service_268967_pct": base_service - causal_967,
                            "causal_service_global_pct": base_service - causal_global,
                            "causal_service_loss_268091_pp": causal_091,
                            "causal_service_loss_268967_pp": causal_967,
                            "causal_service_loss_global_pp": causal_global,
                            "causal_service_loss_fed_product_pp": primary_loss
                            * causal_factor,
                            "baseline_causal_demand_268091_qty": demand_091,
                            "baseline_causal_demand_268967_qty": demand_967,
                            "baseline_causal_demand_global_qty": demand_global,
                            "causal_demand_268091_qty": demand_091,
                            "causal_demand_268967_qty": demand_967,
                            "causal_demand_global_qty": demand_global,
                            "causal_on_due_loss_fed_product_qty": causal_on_due_fed,
                            "causal_on_due_loss_global_qty": causal_on_due_global,
                            "causal_on_due_loss_fed_product_share_of_demand": (
                                causal_on_due_fed / fed_demand
                            ),
                            "causal_on_due_loss_global_share_of_demand": (
                                causal_on_due_global / demand_global
                            ),
                            "causal_backlog_qty_days_delta": causal_backlog,
                            "causal_backlog_qty_days_per_demand_unit": (
                                causal_backlog / demand_global
                            ),
                            "causal_max_backlog_qty_delta": primary_loss * 75.0,
                            "causal_production_loss_fed_product_qty": causal_production_loss,
                            "causal_production_loss_fed_product_share_of_demand": (
                                causal_production_loss / fed_demand
                            ),
                            "warmup_core_state_sha256": warmup_signatures[
                                (point, seed)
                            ],
                            "summary_sha256": _digest(f"summary__{case_key}"),
                            "validation_errors": "",
                        }
                    )
                    rows.append(incident)
    frame = pd.DataFrame(rows)
    metrics_path = root / "campaign_metrics.csv"
    frame.to_csv(metrics_path, index=False)
    return root, metrics_path, frame, manifest


def _prepare_fragile_v1_for_v2_no_go(tmp_path: Path) -> tuple[Path, Path]:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_fine_prevalidation as previous,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_calibration as calibration_v1,
    )
    from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_fine_prevalidation import (
        _executor as previous_executor,
    )
    from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_fine_prevalidation import (
        _source_points,
    )

    source_points = _source_points(tmp_path)
    previous_plan = tmp_path / "previous_plan"
    previous_run = tmp_path / "previous_run"
    previous.prepare_plan(previous_plan, source_points_path=source_points)

    def previous_response(point_id: str, _seed: int) -> tuple[float, float]:
        return {
            "op_100": (1.0, 1.0),
            "op_93": (0.945, 1.0),
            "op_80": (0.82, 0.69),
        }[point_id]

    previous.run(
        previous_plan,
        previous_run,
        executor=previous_executor(previous_response, []),
    )
    plan_dir = tmp_path / "v1_plan"
    run_dir = tmp_path / "v1_run"
    calibration_v1.prepare_plan(
        plan_dir,
        source_plan_dir=previous_plan,
        source_run_dir=previous_run,
    )
    fragile_low_by_seed = dict(
        zip(
            calibration_v1.CALIBRATION_SEEDS,
            (0.70, 0.80, 0.80, 0.80, 0.90),
            strict=True,
        )
    )

    def execute_v1(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        offsets = (candidate.offset_days_268091, candidate.offset_days_268967)
        if offsets == (14.0, 96.0):
            value = fragile_low_by_seed[seed]
            left, right = value, value
        else:
            left, right = {
                (7.0, 90.0): (0.92, 0.94),
                (10.0, 90.0): (0.89, 0.93),
                (16.0, 95.0): (0.75, 0.75),
            }[offsets]
        return _raw_evidence(candidate, adapter, seed, left, right)

    result = calibration_v1.run(plan_dir, run_dir, executor=execute_v1)
    assert result["selected_operating_points"] is not None
    return plan_dir, run_dir


def _real_selected_source(tmp_path: Path, version: str) -> Path:
    source_plan, source_run = (
        _prepare_fragile_v1_for_v2_no_go(tmp_path / "source")
        if version == "v3"
        else _prepare_v1(tmp_path / "source")
    )
    if version == "v1":
        return source_run / "selected_operating_points.json"
    plan_dir = tmp_path / "refinement_plan"
    run_dir = tmp_path / "refinement_run"
    refinement.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )

    def execute(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        pass_values = {
            (7.0, 75.0): (0.92, 0.94),
            (7.0, 81.0): (0.93, 0.93),
            (7.0, 86.0): (0.94, 0.92),
            (17.0, 95.0): (0.79, 0.82),
            (17.0, 94.0): (0.80, 0.80),
            (18.0, 94.0): (0.81, 0.78),
        }
        no_go_values = {
            **pass_values,
            (17.0, 95.0): (0.70, 0.70),
            (17.0, 94.0): (0.70, 0.70),
            (18.0, 94.0): (0.70, 0.70),
        }
        values = pass_values if version == "v2" else no_go_values
        left, right = values[
            (candidate.offset_days_268091, candidate.offset_days_268967)
        ]
        return _raw_evidence(candidate, adapter, seed, left, right)

    v2_result = refinement.run(plan_dir, run_dir, workers=1, executor=execute)
    if version == "v2":
        assert v2_result["selected_operating_points"] is not None
        return run_dir / "selected_operating_points.json"
    if version != "v3":
        raise ValueError(f"Unsupported fixture source version: {version}")
    assert v2_result["selected_operating_points"] is None

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v3 as refinement_v3,
    )

    v3_plan_dir = tmp_path / "refinement_plan_v3"
    v3_run_dir = tmp_path / "refinement_run_v3"
    refinement_v3.prepare_plan(
        v3_plan_dir,
        v1_plan_dir=source_plan,
        v1_run_dir=source_run,
        v2_plan_dir=plan_dir,
        v2_run_dir=run_dir,
    )

    def execute_v3(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        left, right = {
            (16.5, 94.0): (0.80, 0.80),
            (16.5, 94.5): (0.75, 0.75),
            (16.5, 95.0): (0.70, 0.70),
        }[(candidate.offset_days_268091, candidate.offset_days_268967)]
        return _raw_evidence(candidate, adapter, seed, left, right)

    v3_result = refinement_v3.run(
        v3_plan_dir,
        v3_run_dir,
        max_workers=1,
        executor=execute_v3,
    )
    assert v3_result["selection"]["status"] == refinement_v3.SELECTION_PASS_STATUS
    assert v3_result["selection"]["selected_pair"]["op80_candidate_key"] == (
        "op80_refine_v3_16p5_94"
    )
    return v3_run_dir / "selected_operating_points.json"


def _provenance_manifest_for_source(
    selected_path: Path,
) -> tuple[dict[str, object], finalizer.InputEvidence]:
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    chain = STRICT_SOURCE_VALIDATOR(selected_path, selected)
    plan_path = Path(str(chain["plan_manifest_path"]))
    selection_path = Path(str(chain["selection_path"]))
    manifest: dict[str, object] = {
        "engine_sha256": selected["source_hashes"]["engine_sha256"],
        "engine_profile_sha256": selected["source_hashes"]["profile_sha256"],
        "operating_points_source": str(selected_path.resolve()),
        "operating_points_source_sha256": finalizer._sha256(selected_path),
        "operating_points_producer": chain["producer"],
        "operating_points_schema_version": selected["schema_version"],
        "operating_points_artifact_signature": selected["artifact_signature"],
        "operating_points_input_status": selected["status"],
        "operating_points_cohorts": selected["cohorts"],
        "operating_points_calibration_plan": str(plan_path.resolve()),
        "operating_points_calibration_plan_sha256": finalizer._sha256(plan_path),
        "operating_points_calibration_plan_signature": chain["plan_signature"],
        "operating_points_selection": str(selection_path.resolve()),
        "operating_points_selection_sha256": finalizer._sha256(selection_path),
        "operating_points_selection_signature": chain["selection_signature"],
        "operating_points_holdout_contract": chain["holdout_contract"],
        "states": [
            {
                "operating_point_id": point["operating_point_id"],
                "target_service_pct": 100.0 * float(point["target_service"]),
                "calibration_pooled_service_pct": 100.0
                * float(point["calibration_pooled_service"]),
                "calibration_product_268091_service_pct": 100.0
                * float(point["calibration_product_268091_service"]),
                "calibration_product_268967_service_pct": 100.0
                * float(point["calibration_product_268967_service"]),
                "graph_sha256": point["graph_sha256"],
            }
            for point in selected["operating_points"]
        ],
    }
    _resign_campaign_manifest(manifest)
    manifest_path = selected_path.parent / "fixture_campaign_manifest.json"
    _write_json(manifest_path, manifest)
    evidence = finalizer.InputEvidence(
        manifest_path=manifest_path,
        metrics_paths=(),
        manifest_sha256=finalizer._sha256(manifest_path),
        metrics_sha256={},
    )
    return manifest, evidence


def test_finalizer_contract_matches_adaptive_runner() -> None:
    runner_fields = set(runner.METRIC_FIELDS)
    assert finalizer.INPUT_CAMPAIGN_SCHEMA_VERSION == runner.SCHEMA_VERSION
    assert finalizer.INPUT_METRIC_SCHEMA_VERSION == runner.CASE_SCHEMA_VERSION
    assert finalizer.REQUIRED_COLUMNS <= runner_fields
    assert finalizer.EXPECTED_SEEDS == runner.SEEDS
    assert tuple(item.key for item in runner.MECHANISMS) == finalizer.MECHANISMS
    assert runner.INCIDENT_DISRUPTION_DAYS > 1


def test_signed_manifest_rejects_every_changed_provenance_link(
    tmp_path: Path,
) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    manifest_path = root / "campaign_manifest.json"
    evidence = finalizer.InputEvidence(
        manifest_path=manifest_path,
        metrics_paths=(),
        manifest_sha256=finalizer._sha256(manifest_path),
        metrics_sha256={},
    )
    plan_path = str(manifest["operating_points_calibration_plan"])
    plan_sha = str(manifest["operating_points_calibration_plan_sha256"])
    selection_path = str(manifest["operating_points_selection"])
    selection_sha = str(manifest["operating_points_selection_sha256"])

    changed_manifests: list[dict[str, object]] = []
    changed_hash = json.loads(json.dumps(manifest))
    changed_hash["operating_points_source_sha256"] = "0" * 64
    changed_manifests.append(changed_hash)
    changed_plan = json.loads(json.dumps(manifest))
    changed_plan["operating_points_calibration_plan"] = selection_path
    changed_plan["operating_points_calibration_plan_sha256"] = selection_sha
    changed_manifests.append(changed_plan)
    changed_selection = json.loads(json.dumps(manifest))
    changed_selection["operating_points_selection"] = plan_path
    changed_selection["operating_points_selection_sha256"] = plan_sha
    changed_manifests.append(changed_selection)
    changed_status = json.loads(json.dumps(manifest))
    changed_status["operating_points_input_status"] = "substituted"
    changed_manifests.append(changed_status)
    changed_cohorts = json.loads(json.dumps(manifest))
    changed_cohorts["operating_points_cohorts"]["calibration"] = [340282]
    changed_manifests.append(changed_cohorts)

    for changed in changed_manifests:
        _resign_campaign_manifest(changed)
        finalizer._verify_manifest_signature(changed)
        with pytest.raises(finalizer.CampaignValidationError):
            finalizer._validate_operating_point_provenance(evidence, changed)


def test_resigned_manifest_cannot_detach_source_from_signed_holdout_preflight(
    tmp_path: Path,
) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    selection_path = Path(str(manifest["operating_points_selection"]))
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection.pop("selection_signature")
    selection["replacement_note"] = "internally_resigned_substitution"
    selection["selection_signature"] = finalizer._stable_sha256(selection)
    _write_json(selection_path, selection)

    selected_path = Path(str(manifest["operating_points_source"]))
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    selected.pop("artifact_signature")
    selected["selection_signature"] = selection["selection_signature"]
    selected["selection"]["selection_signature"] = selection["selection_signature"]
    selected["artifact_signature"] = finalizer._stable_sha256(selected)
    _write_json(selected_path, selected)
    manifest["operating_points_selection_sha256"] = finalizer._sha256(selection_path)
    manifest["operating_points_selection_signature"] = selection["selection_signature"]
    manifest["operating_points_source_sha256"] = finalizer._sha256(selected_path)
    manifest["operating_points_artifact_signature"] = selected["artifact_signature"]
    _resign_campaign_manifest(manifest)

    preflight_path = Path(str(manifest["operating_point_preflight"]))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight.pop("preflight_signature")
    preflight["campaign_signature"] = manifest["campaign_signature"]
    preflight["preflight_signature"] = finalizer._stable_sha256(preflight)
    _write_json(preflight_path, preflight)
    manifest["operating_point_preflight_sha256"] = finalizer._sha256(preflight_path)
    manifest["operating_point_preflight_signature"] = preflight["preflight_signature"]
    manifest_path = root / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    evidence = finalizer.InputEvidence(
        manifest_path=manifest_path,
        metrics_paths=(),
        manifest_sha256=finalizer._sha256(manifest_path),
        metrics_sha256={},
    )

    finalizer._verify_manifest_signature(manifest)
    finalizer._validate_operating_point_provenance(evidence, manifest)
    with pytest.raises(finalizer.CampaignValidationError, match="preflight"):
        finalizer._validate_signed_context(evidence, manifest)


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_resigned_v1_v2_v3_selection_substitution_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    monkeypatch.setattr(
        runner, "_validate_pending_multiseed_source", STRICT_SOURCE_VALIDATOR
    )
    selected_path = _real_selected_source(tmp_path / version, version)
    manifest, evidence = _provenance_manifest_for_source(selected_path)

    validated = finalizer._validate_operating_point_provenance(evidence, manifest)
    assert (
        validated["producer"]
        == f"{version}_{'calibration' if version == 'v1' else 'refinement'}"
    )
    if version == "v3":
        assert validated["schema_version"] == runner.V3_POINTS_SCHEMA_VERSION
        assert validated["status"] == runner.V3_POINTS_PENDING_STATUS
        assert validated["selection_status"] == runner.V3_SELECTION_PASS_STATUS
        assert validated["calibration_proof_count"] == 80
        assert validated["upstream_v2_no_go_status"] == (
            "five_seed_loo_screen_failed_no_holdout"
        )
        assert validated["source_hashes"]["v3_driver_sha256"] == (
            runner.V3_REFINEMENT_MODULE_SHA256
        )

        mixed = json.loads(json.dumps(manifest))
        mixed["operating_points_producer"] = "v2_refinement"
        mixed["operating_points_schema_version"] = runner.V2_POINTS_SCHEMA_VERSION
        mixed["operating_points_input_status"] = runner.V2_POINTS_PENDING_STATUS
        _resign_campaign_manifest(mixed)
        finalizer._verify_manifest_signature(mixed)
        with pytest.raises(
            finalizer.CampaignValidationError,
            match="provenance differs",
        ):
            finalizer._validate_operating_point_provenance(evidence, mixed)

    selection_path = Path(str(manifest["operating_points_selection"]))
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection.pop("selection_signature")
    selection["status"] = "substituted_but_resigned"
    selection["selection_signature"] = finalizer._stable_sha256(selection)
    _write_json(selection_path, selection)

    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    selected.pop("artifact_signature")
    selected["selection_signature"] = selection["selection_signature"]
    if isinstance(selected.get("selection"), dict):
        selected["selection"]["selection_signature"] = selection["selection_signature"]
    selected["artifact_signature"] = finalizer._stable_sha256(selected)
    _write_json(selected_path, selected)
    manifest["operating_points_selection_sha256"] = finalizer._sha256(selection_path)
    manifest["operating_points_selection_signature"] = selection["selection_signature"]
    manifest["operating_points_source_sha256"] = finalizer._sha256(selected_path)
    manifest["operating_points_artifact_signature"] = selected["artifact_signature"]
    _resign_campaign_manifest(manifest)
    finalizer._verify_manifest_signature(manifest)

    with pytest.raises(
        finalizer.CampaignValidationError,
        match="Strict V1/V2/V3 operating-point source validation failed",
    ):
        finalizer._validate_operating_point_provenance(evidence, manifest)


def test_complete_adaptive_campaign_writes_global_and_product_results(
    tmp_path: Path,
) -> None:
    root, _, _, _ = _fixture(tmp_path)
    output = tmp_path / "final"

    result = finalizer.finalize_campaign(
        campaign_root=root,
        manifest_path=None,
        metrics_paths=[],
        output_dir=output,
    )

    assert result["schema_version"] == finalizer.SCHEMA_VERSION
    assert result["status"] == "complete_validated"
    assert result["adaptive_horizons_observed"] is True
    assert result["statistics"]["bootstrap_replicates"] == 10_000
    assert result["statistics"]["forced_top3"] is False
    assert result["comparability_checks"]["whole_horizon_cost_deltas_excluded"] is True
    assert (
        result["comparability_checks"]["operating_point_source_chain_revalidated"]
        is True
    )
    assert result["inputs"]["operating_point_provenance"]["producer"] == (
        "v2_refinement"
    )
    assert result["supplier_disruption_window_days"] == runner.INCIDENT_DISRUPTION_DAYS

    lane_stats = pd.read_csv(output / "lane_statistics.csv")
    supplier_stats = pd.read_csv(output / "supplier_statistics.csv")
    product_priority = pd.read_csv(
        output / "priority_suppliers_by_cause_state_and_product.csv"
    )
    global_priority = pd.read_csv(output / "priority_suppliers_by_cause_state.csv")
    assert len(lane_stats) == 108
    assert len(supplier_stats) == 108
    assert set(product_priority["ranking_scope"]) == {"within_target_product"}
    assert set(global_priority["ranking_scope"]) == {"all_target_products"}
    assert "within_target_product_rank_min" in product_priority
    assert supplier_stats.loc[
        supplier_stats["operating_point_id"] == "op_100",
        "operating_point_service_pct",
    ].iloc[0] == pytest.approx(99.82)
    assert not any("total_cost_delta" in column for column in supplier_stats.columns)
    selected = global_priority[
        global_priority["priority_status"].isin(
            ["robust_priority", "priority_contender"]
        )
    ]
    assert set(selected["supplier_id"]) == {"supplier_17"}
    assert selected.groupby(["operating_point_id", "mechanism"]).size().eq(1).all()
    assert (
        selected["representative_lane_label_fr"]
        == "voie la plus exposée parmi les voies testées"
    ).all()
    stability = pd.read_csv(output / "supplier_priority_stability_by_cause.csv")
    supplier_17 = stability[stability["supplier_id"] == "supplier_17"]
    assert supplier_17["priority_in_all_three_states"].all()
    assert supplier_17["state_comparison_valid"].all()


def test_zero_exposure_is_kept_as_an_explicit_zero_case(tmp_path: Path) -> None:
    first_seed = finalizer.EXPECTED_SEEDS[0]
    root, _, _, _ = _fixture(tmp_path, no_exposure={("op_100", "lane_17", first_seed)})
    output = tmp_path / "final"

    finalizer.finalize_campaign(
        campaign_root=root,
        manifest_path=None,
        metrics_paths=[],
        output_dir=output,
    )

    lane_stats = pd.read_csv(output / "lane_statistics.csv")
    selected = lane_stats[
        (lane_stats["operating_point_id"] == "op_100")
        & (lane_stats["mechanism"] == "transport_delay")
        & (lane_stats["lane_id"] == "lane_17")
    ].iloc[0]
    assert selected["paired_repetition_count"] == 30
    assert selected["zero_exposure_repetition_count"] == 1
    assert selected["physical_exercise_rate"] == pytest.approx(29 / 30)


def test_zero_exposure_with_nonzero_effect_is_rejected(tmp_path: Path) -> None:
    first_seed = finalizer.EXPECTED_SEEDS[0]
    root, metrics_path, frame, _ = _fixture(
        tmp_path, no_exposure={("op_100", "lane_17", first_seed)}
    )
    selected = (
        (frame["operating_point_id"] == "op_100")
        & (frame["seed"] == first_seed)
        & (frame["lane_id"] == "lane_17")
        & (frame["mechanism"] == "transport_delay")
    )
    frame.loc[selected, "impact_backlog_qty_days_delta"] = 1.0
    frame.loc[selected, "impact_backlog_qty_days_per_demand_unit"] = 1.0 / frame.loc[
        selected, "baseline_impact_demand_global_qty"
    ].astype(float)
    frame.to_csv(metrics_path, index=False)

    with pytest.raises(finalizer.CampaignValidationError, match="Zero-exposure"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_tampered_preflight_signature_is_rejected(tmp_path: Path) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    preflight_path = Path(str(manifest["operating_point_preflight"]))
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload["states"][0]["service_global_ratio_of_sums_pct"] = 91.0
    _write_json(preflight_path, payload)
    manifest["operating_point_preflight_sha256"] = finalizer._sha256(preflight_path)
    _write_json(root / "campaign_manifest.json", manifest)

    with pytest.raises(finalizer.CampaignValidationError, match="preflight signature"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_tampered_manifest_signed_design_is_rejected(tmp_path: Path) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    manifest["impact_metric_contract"]["primary"] = "tampered"
    _write_json(root / "campaign_manifest.json", manifest)

    with pytest.raises(finalizer.CampaignValidationError, match="signed design"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_unpaired_preflight_method_is_rejected_even_if_name_contains_paired(
    tmp_path: Path,
) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    preflight_path = Path(str(manifest["operating_point_preflight"]))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight["bootstrap"]["method"] = "unpaired_seed_resampling"
    _rewrite_signed_preflight(root, manifest, preflight)

    with pytest.raises(finalizer.CampaignValidationError, match="paired bootstrap"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_preflight_acceptance_is_recomputed_from_discovery_evidence(
    tmp_path: Path,
) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    for evidence_path in (root / "target_discovery" / "evidence").glob("op_93__*.json"):
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        metrics = evidence["state_service_metrics"]
        metrics["on_due_qty_268091"] = 94_500.0
        metrics["on_due_qty_268967"] = 94_500.0
        metrics["on_due_qty_global"] = 189_000.0
        unsigned = dict(evidence)
        unsigned.pop("evidence_signature")
        _write_json(evidence_path, _signed(unsigned, "evidence_signature"))

    preflight_path = Path(str(manifest["operating_point_preflight"]))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    state = next(
        row for row in preflight["states"] if row["operating_point_id"] == "op_93"
    )
    for field in (
        "service_global_ratio_of_sums_pct",
        "service_global_seed_median_pct",
        "service_268091_ratio_of_sums_pct",
        "service_268967_ratio_of_sums_pct",
        "global_service_bootstrap_ci95_low_pct",
        "global_service_bootstrap_ci95_high_pct",
    ):
        state[field] = 94.5
    _rewrite_signed_preflight(root, manifest, preflight)

    with pytest.raises(finalizer.CampaignValidationError, match="signed target"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_lane_window_dates_must_be_identical_across_states_and_seeds(
    tmp_path: Path,
) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    registry_path = Path(str(manifest["target_registry"]))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    target = next(row for row in registry["targets"] if row["lane_id"] == "lane_00")
    target["target_window_start_day"] += 1
    target["target_window_end_day"] += 1
    _rewrite_signed_registry(root, manifest, registry)

    with pytest.raises(finalizer.CampaignValidationError, match="one fixed window"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_lane_window_must_stay_inside_state_evaluation_period(tmp_path: Path) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    registry_path = Path(str(manifest["target_registry"]))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    contract = next(
        row for row in registry["lane_contracts"] if row["lane_id"] == "lane_00"
    )
    contract["fixed_window_start_day"] = 700
    contract["fixed_window_end_day"] = 700 + runner.INCIDENT_DISRUPTION_DAYS - 1
    for target in registry["targets"]:
        if target["lane_id"] == "lane_00":
            target["target_window_start_day"] = contract["fixed_window_start_day"]
            target["target_window_end_day"] = contract["fixed_window_end_day"]
    _rewrite_signed_registry(root, manifest, registry)

    with pytest.raises(finalizer.CampaignValidationError, match="J0-J719"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_version", f"{runner.SCHEMA_VERSION}.target_registry.v5"),
        ("campaign_exposure_gate_passed", False),
        ("all_lane_design_windows_comparable", False),
        ("all_lane_holdout_exposures_comparable", False),
        (
            "exposure_gate_failures",
            [{"lane_id": "lane_00", "reasons": ["synthetic_gate_failure"]}],
        ),
    ],
)
def test_registry_v4_and_global_exposure_gate_are_mandatory(
    tmp_path: Path, field: str, invalid_value: object
) -> None:
    root, _, _, manifest = _fixture(tmp_path)
    registry_path = Path(str(manifest["target_registry"]))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry[field] = invalid_value
    _rewrite_signed_registry(root, manifest, registry)

    with pytest.raises(finalizer.CampaignValidationError, match="target registry"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_one_day_or_mismatched_incident_window_is_rejected(tmp_path: Path) -> None:
    root, metrics_path, frame, _ = _fixture(tmp_path)
    selected = frame["stage"] == "incident"
    frame.loc[selected, "target_window_days"] = 1
    frame.loc[selected, "target_window_end_day"] = frame.loc[
        selected, "target_window_start_day"
    ]
    frame.loc[selected, "risk_end_day"] = frame.loc[selected, "risk_start_day"]
    frame.to_csv(metrics_path, index=False)

    with pytest.raises(finalizer.CampaignValidationError, match="uniform window"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_unknown_target_product_is_rejected_before_ranking(tmp_path: Path) -> None:
    root, metrics_path, frame, _ = _fixture(tmp_path)
    frame.loc[frame["stage"] == "incident", "target_product_id"] = "unknown_pf"
    frame.to_csv(metrics_path, index=False)

    with pytest.raises(
        finalizer.CampaignValidationError, match="exactly 268091 or 268967"
    ):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_quantity_and_demand_normalization_arithmetic_is_recomputed(
    tmp_path: Path,
) -> None:
    root, metrics_path, frame, _ = _fixture(tmp_path)
    selected = frame["stage"] == "incident"
    first_index = frame[selected].index[0]
    frame.loc[first_index, "impact_on_due_loss_fed_product_qty"] = 123.456
    frame.to_csv(metrics_path, index=False)

    with pytest.raises(finalizer.CampaignValidationError, match="arithmetic"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_missing_incident_cell_is_rejected(tmp_path: Path) -> None:
    root, metrics_path, frame, _ = _fixture(tmp_path)
    frame = frame.drop(frame[frame["stage"] == "incident"].index[0])
    frame.to_csv(metrics_path, index=False)

    with pytest.raises(finalizer.CampaignValidationError, match="3240 incidents"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_lane_below_24_comparable_seeds_rejects_the_whole_campaign(
    tmp_path: Path,
) -> None:
    root, _, _, _ = _fixture(tmp_path, incomparable_lane="lane_17")
    with pytest.raises(finalizer.CampaignValidationError, match="target registry"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
        )


def test_rank_bounds_preserve_ties_and_priority_is_not_forced() -> None:
    rank_min, rank_max = finalizer._rank_bounds(
        pd.Series([5.0, 3.0, 3.0, 0.0]).to_numpy()
    )
    assert rank_min.tolist() == [1, 2, 2, 4]
    assert rank_max.tolist() == [1, 3, 3, 4]
    assert (
        finalizer._priority_status(
            detected=False, robust_probability=1.0, possible_probability=1.0
        )
        == "no_detected_effect"
    )


def test_published_bootstrap_count_cannot_be_reduced(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)
    with pytest.raises(finalizer.CampaignValidationError, match="10,000"):
        finalizer.finalize_campaign(
            campaign_root=root,
            manifest_path=None,
            metrics_paths=[],
            output_dir=tmp_path / "final",
            bootstrap_replicates=999,
        )
