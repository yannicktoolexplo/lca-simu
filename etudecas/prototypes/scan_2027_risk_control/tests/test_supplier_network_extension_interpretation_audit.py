from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_extension_interpretation_audit as audit,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_post_priority_extension_runner as runner,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_network_post_priority_extension_runner import (
    FakeExecutor,
    _runner_fixture,
)


def _csv_record(row: dict) -> dict:
    return {
        key: ("True" if value else "False") if isinstance(value, bool) else value
        for key, value in row.items()
    }


def _effect_matrix(
    *,
    kind: str,
    adverse_amplitude_by_slot: dict[int, float],
    temporal_causes: dict[int, str] | None = None,
    temporal_offset_by_window: dict[int, float] | None = None,
) -> list[audit.PairedEffect]:
    result: list[audit.PairedEffect] = []
    contexts: list[tuple[int, str]]
    if kind == "temporal":
        contexts = [(index, "") for index, _start, _end in audit.CALENDAR_WINDOWS]
    else:
        contexts = [(0, cause) for cause in audit.FOUR_CAUSES]
    for window_index, context_cause in contexts:
        for slot in range(1, audit.EXPECTED_FOLLOW_UP_LANE_COUNT + 1):
            cause = (
                (temporal_causes or {}).get(slot, "transport_delay")
                if kind == "temporal"
                else context_cause
            )
            amplitude = adverse_amplitude_by_slot[slot] + (
                (temporal_offset_by_window or {}).get(window_index, 0.0)
                if kind == "temporal"
                else 0.0
            )
            for seed in range(1001, 1031):
                result.append(
                    audit.PairedEffect(
                        extension=(
                            "temporal_robustness"
                            if kind == "temporal"
                            else "priority_four_business_causes"
                        ),
                        case_id=f"case_{kind}_{window_index}_{context_cause}_slot{slot}",
                        case_key=f"case_{kind}_{window_index}_{context_cause}_slot{slot}_{seed}",
                        chain_id=f"chain_{slot}",
                        supplier_id=f"supplier_{slot}",
                        item_id=f"item_{slot}",
                        dst_node_id="M-1810",
                        product_id="268091",
                        selection_slot=slot,
                        window_index=window_index,
                        failure_mode=cause,
                        mathematical_family=audit.CAUSE_FAMILY[cause],
                        mechanism_value=audit.SEVERE_CAUSE[cause][0],
                        mechanism_unit=audit.SEVERE_CAUSE[cause][1],
                        stress_start_day=(
                            audit.CALENDAR_WINDOWS[window_index - 1][1]
                            if kind == "temporal"
                            else 45
                        ),
                        stress_end_day=(
                            audit.CALENDAR_WINDOWS[window_index - 1][2]
                            if kind == "temporal"
                            else 224
                        ),
                        simulation_days=1063 if kind == "temporal" else 720,
                        outcome_spec_id=(
                            f"calendar_window_{window_index}_fixed_followup"
                            if kind == "temporal"
                            else "full_horizon_J0_J719"
                        ),
                        outcome_start_day=(
                            audit.CALENDAR_WINDOWS[window_index - 1][1]
                            if kind == "temporal"
                            else 0
                        ),
                        outcome_end_day=(
                            audit.CALENDAR_WINDOWS[window_index - 1][2] + 343
                            if kind == "temporal"
                            else 719
                        ),
                        outcome_day_count=523 if kind == "temporal" else 720,
                        preincident_snapshot_day=(
                            audit.CALENDAR_WINDOWS[window_index - 1][1] - 1
                            if kind == "temporal"
                            else -1
                        ),
                        seed=seed,
                        demand_qty=1000.0,
                        baseline_released_qty=900.0,
                        service_delta=-amplitude,
                        backlog_delta_per_requested_unit=amplitude,
                        outcome_end_backlog_delta_per_requested_unit=amplitude / 2.0,
                        signed_production_loss_ratio=amplitude,
                        client_effect=(
                            amplitude > audit.MINIMUM_REPORTABLE_RATIO_GAP
                            or amplitude > audit.MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP
                        ),
                        production_effect=(
                            amplitude > audit.MINIMUM_REPORTABLE_RATIO_GAP
                        ),
                    )
                )
    return result


def _product_rows(
    demand: float = 1000.0,
    *,
    outcome_spec_id: str = "full_horizon_J0_J719",
    outcome_start_day: int = 0,
    outcome_end_day: int = 719,
) -> list[dict]:
    return [
        {
            "outcome_spec_id": outcome_spec_id,
            "outcome_start_day": outcome_start_day,
            "outcome_end_day": outcome_end_day,
            "outcome_day_count": outcome_end_day - outcome_start_day + 1,
            "product_id": product,
            "uom": "UN",
            "demand_qty_denominator": demand,
            "required_qty_denominator": demand,
            "served_qty_numerator": 0.99 * demand,
            "fill_rate": 0.99,
            "served_on_due_qty_numerator": 0.98 * demand,
            "on_due_ratio": 0.98,
            "backlog_qty_days_numerator": 0.01 * demand,
            "normalized_backlog_days_per_demand_unit": (0.01 if demand else 0.0),
            "backlog_end_qty": 0.0,
            "released_qty_numerator": 0.99 * demand,
            "series_day_count": outcome_end_day - outcome_start_day + 1,
            "series_complete": True,
            "recovery_metric_status": "excluded_not_redefined",
        }
        for product in sorted(audit.EXPECTED_TARGET_PRODUCTS)
    ]


def _evidence(
    case_key: str,
    *,
    demand: float = 1000.0,
    case: audit.CaseSpec,
    baseline: bool = False,
) -> dict:
    event_ids = [
        f"{case.case_id}__lane{index}" for index, _lane in enumerate(case.lanes, 1)
    ]
    loaded_rows = [
        {
            "event_id": event_id,
            "risk_type": case.risk_type,
            "supplier_id": lane.supplier_id,
            "item_id": lane.item_id,
            "dst_node_id": lane.dst_node_id,
            "edge_id": lane.edge_id,
            "start_day": case.start_day,
            "end_day": case.end_day,
            "multiplier": case.mechanism_value,
            "notes": "",
        }
        for event_id, lane in zip(event_ids, case.lanes)
    ]
    snapshot_payload = {"state": "same"}
    snapshot_specs = (
        [
            (f"calendar_window_{index}_fixed_followup", start - 1)
            for index, start, _end in audit.CALENDAR_WINDOWS
        ]
        if baseline and case.outcome_spec_id.startswith("calendar_window_")
        else [(case.outcome_spec_id, case.preincident_snapshot_day)]
    )
    snapshots = (
        [
            {
                "outcome_spec_id": spec_id,
                "snapshot_day": snapshot_day,
                "payload": snapshot_payload,
                "preincident_state_sha256": audit._canonical_sha256(snapshot_payload),
            }
            for spec_id, snapshot_day in snapshot_specs
        ]
        if case.extension == "temporal_robustness"
        else []
    )
    return {
        "case_key": case_key,
        "seed": case.seed,
        "valid": True,
        "validation_errors": [],
        "input_sha256": "input",
        "j0_state_sha256": "j0",
        "resolved_lot_trace_enabled": case.lot_trace_required,
        "simulation_days": case.simulation_days,
        "outcome_bundle_sha256": case.outcome_bundle_sha256,
        "extended_horizon_input_support_pass": True,
        "post_J719_extrapolation_policy": (
            "explicit_annual_cycle_repeat_from_365_day_observed_demand_profile"
            if case.simulation_days > 720
            else "not_applicable_fixed_J0_J719"
        ),
        "product_metrics": [],
        "local_product_metrics": [
            row
            for row in _product_rows(
                demand,
                outcome_spec_id=case.outcome_spec_id,
                outcome_start_day=case.outcome_start_day,
                outcome_end_day=case.outcome_end_day,
            )
            if baseline or row["product_id"] in case.products
        ],
        "flow_metrics": [],
        "configured_event_ids": [] if baseline else event_ids,
        "loaded_event_rows": [] if baseline else loaded_rows,
        "applied_event_ids": [] if baseline else event_ids,
        "risk_application_rows": (
            [] if baseline else [{"event_ids": ",".join(event_ids)}]
        ),
        "risk_input_sha256": "" if baseline else "a" * 64,
        "risk_load_warnings": [],
        "preincident_state_snapshots": snapshots,
        "lot_events": [],
        "lot_genealogy": [],
    }


def test_zero_effects_remain_an_unresolved_group_not_a_lexical_ranking():
    effects = _effect_matrix(
        kind="temporal",
        adverse_amplitude_by_slot={1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0},
    )
    effect_rows, pair_rows, interpretation = audit.analyze_selected_lane_effects(
        effects,
        kind="temporal",
        expected_seeds=tuple(range(1001, 1031)),
    )
    assert len(effect_rows) == 48
    assert len(pair_rows) == 72
    assert {row["effect_class"] for row in effect_rows} == {"uncertain"}
    assert {row["metric"] for row in effect_rows} == {
        "horizon_on_due_service_delta",
        "incremental_backlog_days_per_requested_unit",
        "signed_released_production_loss_ratio",
    }
    assert all(
        row["difference_exceeds_descriptive_reporting_rule"] is False
        for row in pair_rows
    )
    assert all(
        "order_class" not in row and "priority_rank" not in row for row in pair_rows
    )
    assert interpretation["follow_up_group_status"] == (
        "complete_nonseparated_service_group_nonordered"
    )
    assert interpretation["follow_up_lane_count"] == 4
    assert interpretation["global_network_priority_robustness_evaluable"] is False
    assert all(
        "simulated_effect_classes" in row and "observed_effect_classes" not in row
        for row in interpretation["effect_class_variations_by_lane_metric"]
    )


def test_temporal_within_lane_differences_are_descriptive_not_an_order():
    effects = _effect_matrix(
        kind="temporal",
        adverse_amplitude_by_slot={1: 0.01, 2: 0.02, 3: 0.03, 4: 0.04},
        temporal_offset_by_window={1: 0.00, 2: 0.02, 3: 0.04, 4: 0.06},
    )
    effect_rows, pair_rows, interpretation = audit.analyze_selected_lane_effects(
        effects,
        kind="temporal",
        expected_seeds=tuple(range(1001, 1031)),
    )
    assert any(
        row["difference_exceeds_descriptive_reporting_rule"] for row in pair_rows
    )
    assert all(
        row["outcome_end_residual_backlog_delta_per_requested_unit_mean"]
        == pytest.approx(-row["effect_mean"] / 2.0)
        for row in effect_rows
        if row["metric"] == "horizon_on_due_service_delta"
    )
    assert all(
        row["outcome_end_residual_is_loss_claimed"] is False for row in effect_rows
    )
    assert all(row["comparison_is_descriptive_only"] for row in pair_rows)
    assert all(row["comparison_used_for_selection"] is False for row in pair_rows)
    assert interpretation["within_lane_context_difference_detected"] is True
    assert interpretation["temporal_state_dependence_causally_identified"] is False
    assert interpretation["global_network_priority_robustness_evaluable"] is False


def test_ordered_improvements_are_not_promoted_as_an_adverse_priority():
    effects = _effect_matrix(
        kind="four_cause",
        adverse_amplitude_by_slot={1: -0.20, 2: -0.40, 3: -0.60, 4: -0.80},
    )
    effect_rows, pair_rows, interpretation = audit.analyze_selected_lane_effects(
        effects,
        kind="four_cause",
        expected_seeds=tuple(range(1001, 1031)),
    )
    assert {row["effect_class"] for row in effect_rows} == {"improvement"}
    assert all(row["comparison_used_for_selection"] is False for row in pair_rows)
    assert interpretation["follow_up_group_order_evaluable"] is False


def test_temporal_different_hypotheses_are_not_ranked_against_each_other():
    effects = _effect_matrix(
        kind="temporal",
        adverse_amplitude_by_slot={1: 0.03, 2: 0.02, 3: 0.01, 4: 0.04},
        temporal_causes={
            1: "transport_delay",
            2: "supply_availability",
            3: "transport_delay",
            4: "quality_hold",
        },
    )
    _effect_rows, pair_rows, interpretation = audit.analyze_selected_lane_effects(
        effects,
        kind="temporal",
        expected_seeds=tuple(range(1001, 1031)),
    )
    assert len(pair_rows) == 72
    assert all(
        row["chain_id"].endswith(str(row["selection_slot"])) for row in pair_rows
    )
    assert all(row["failure_mode"] for row in _effect_rows)
    assert all(row["mathematical_family"] for row in _effect_rows)
    assert all(row["mechanism_unit"] for row in _effect_rows)
    assert interpretation["pairwise_differences_used_for_ordering"] is False
    assert interpretation["follow_up_group_order_evaluable"] is False


def test_missing_seed_fails_the_paired_bootstrap_matrix():
    effects = _effect_matrix(
        kind="temporal",
        adverse_amplitude_by_slot={1: 0.03, 2: 0.02, 3: 0.01, 4: 0.04},
    )
    effects.pop()
    with pytest.raises(ValueError, match="graines incomplets ou dupliques"):
        audit.analyze_selected_lane_effects(
            effects,
            kind="temporal",
            expected_seeds=tuple(range(1001, 1031)),
        )


def test_numerical_dust_does_not_count_as_a_client_or_production_effect():
    effects = _effect_matrix(
        kind="four_cause",
        adverse_amplitude_by_slot={1: 1e-7, 2: 1e-7, 3: 1e-7, 4: 1e-7},
    )
    effect_rows, _pair_rows, _interpretation = audit.analyze_selected_lane_effects(
        effects,
        kind="four_cause",
        expected_seeds=tuple(range(1001, 1031)),
    )
    assert all(row["conditional_client_effect_seed_count"] == 0 for row in effect_rows)
    assert all(
        row["conditional_production_effect_seed_count"] == 0 for row in effect_rows
    )


def test_common_cause_aggregates_once_per_supplier_cause_seed_not_per_lane():
    effects: list[audit.PairedEffect] = []
    cases: list[audit.CaseSpec] = []
    full_bundle = audit._canonical_sha256(
        {
            "outcome_specs": [
                {
                    "outcome_spec_id": "full_horizon_J0_J719",
                    "outcome_start_day": 0,
                    "outcome_end_day": 719,
                    "outcome_day_count": 720,
                }
            ]
        }
    )
    for supplier_index, supplier in enumerate(audit.EXPECTED_MULTI_LANE_SUPPLIERS, 1):
        lanes = (
            audit.Lane(
                f"chain_{supplier_index}_a",
                supplier,
                f"item_{supplier_index}_a",
                "M-1810",
                f"edge_{supplier_index}_a",
                "268091",
            ),
            audit.Lane(
                f"chain_{supplier_index}_b",
                supplier,
                f"item_{supplier_index}_b",
                "M-1430",
                f"edge_{supplier_index}_b",
                "268967",
            ),
        )
        for cause in audit.FOUR_CAUSES:
            for seed in range(1001, 1031):
                case_id = f"common_{supplier_index}_{cause}"
                case_key = audit._case_key(
                    "multi_lane_supplier_common_cause", case_id, seed
                )
                case = audit.CaseSpec(
                    extension="multi_lane_supplier_common_cause",
                    case_id=case_id,
                    case_key=case_key,
                    seed=seed,
                    pairing_block_id=f"metrics_seed_{seed}",
                    paired_baseline_case_id=f"baseline_metrics__seed_{seed}",
                    failure_mode=cause,
                    risk_type=audit.RISK_TYPE[cause],
                    mechanism_value=audit.SEVERE_CAUSE[cause][0],
                    mechanism_unit=audit.SEVERE_CAUSE[cause][1],
                    start_day=0,
                    end_day=179,
                    lot_trace_required=False,
                    lanes=lanes,
                    products=("268091", "268967"),
                    selection_slot=-1,
                    window_index=-1,
                    mathematical_family=audit.CAUSE_FAMILY[cause],
                    simulation_days=720,
                    outcome_spec_id="full_horizon_J0_J719",
                    outcome_start_day=0,
                    outcome_end_day=719,
                    outcome_day_count=720,
                    outcome_bundle_sha256=full_bundle,
                    preincident_snapshot_day=-1,
                )
                cases.append(case)
                for product, demand, amplitude in (
                    ("268091", 100.0, 0.10),
                    ("268967", 300.0, 0.20),
                ):
                    effects.append(
                        audit.PairedEffect(
                            extension=case.extension,
                            case_id=case.case_id,
                            case_key=case.case_key,
                            chain_id=lanes[0].chain_id,
                            supplier_id=supplier,
                            item_id=lanes[0].item_id,
                            dst_node_id=lanes[0].dst_node_id,
                            product_id=product,
                            selection_slot=-1,
                            window_index=-1,
                            failure_mode=cause,
                            mathematical_family=audit.CAUSE_FAMILY[cause],
                            mechanism_value=audit.SEVERE_CAUSE[cause][0],
                            mechanism_unit=audit.SEVERE_CAUSE[cause][1],
                            stress_start_day=0,
                            stress_end_day=179,
                            simulation_days=720,
                            outcome_spec_id="full_horizon_J0_J719",
                            outcome_start_day=0,
                            outcome_end_day=719,
                            outcome_day_count=720,
                            preincident_snapshot_day=-1,
                            seed=seed,
                            demand_qty=demand,
                            baseline_released_qty=demand,
                            service_delta=-amplitude,
                            backlog_delta_per_requested_unit=amplitude,
                            outcome_end_backlog_delta_per_requested_unit=(
                                amplitude / 2.0
                            ),
                            signed_production_loss_ratio=amplitude,
                            client_effect=True,
                            production_effect=True,
                        )
                    )
    rows, interpretation = audit.analyze_common_cause_effects(
        effects,
        cases=cases,
        expected_seeds=tuple(range(1001, 1031)),
    )
    assert len(rows) == 24
    assert {row["paired_seed_count"] for row in rows} == {30}
    assert sorted({row["effect_mean"] for row in rows}) == pytest.approx(
        [-0.175, 0.175]
    )
    assert all(row["supplier_cause_seed_is_single_bootstrap_block"] for row in rows)
    assert interpretation["multi_lane_interaction_or_synergy_evaluable"] is False


def test_common_cause_exposure_requires_the_same_29_seeds_on_all_lanes():
    lanes = (
        audit.Lane(
            "chain_a", "supplier_common", "item_a", "M-1810", "edge_a", "268091"
        ),
        audit.Lane(
            "chain_b", "supplier_common", "item_b", "M-1430", "edge_b", "268967"
        ),
    )
    bundle = audit._canonical_sha256(
        {
            "outcome_specs": [
                {
                    "outcome_spec_id": "full_horizon_J0_J719",
                    "outcome_start_day": 0,
                    "outcome_end_day": 719,
                    "outcome_day_count": 720,
                }
            ]
        }
    )
    cases: list[audit.CaseSpec] = []
    evidence: dict[str, dict] = {}
    baseline_owner: dict[str, str] = {}
    flow_rows: list[dict] = []
    for seed in range(1001, 1031):
        case = audit.CaseSpec(
            extension="multi_lane_supplier_common_cause",
            case_id="common_supplier_transport_delay",
            case_key=(
                "multi_lane_supplier_common_cause::"
                f"common_supplier_transport_delay::seed_{seed}"
            ),
            seed=seed,
            pairing_block_id=f"metrics_seed_{seed}",
            paired_baseline_case_id="baseline_common_720",
            failure_mode="transport_delay",
            risk_type="lead_time_extra_days",
            mechanism_value=120.0,
            mechanism_unit="jours_ajoutes",
            start_day=0,
            end_day=179,
            lot_trace_required=False,
            lanes=lanes,
            products=("268091", "268967"),
            selection_slot=-1,
            window_index=-1,
            mathematical_family="date_shift",
            simulation_days=720,
            outcome_spec_id="full_horizon_J0_J719",
            outcome_start_day=0,
            outcome_end_day=719,
            outcome_day_count=720,
            outcome_bundle_sha256=bundle,
            preincident_snapshot_day=-1,
        )
        cases.append(case)
        baseline_key = audit._baseline_case_key(case.paired_baseline_case_id, seed)
        baseline_owner[baseline_key] = baseline_key
        baseline = _evidence(baseline_key, case=case, baseline=True)
        stress = _evidence(case.case_key, case=case)
        baseline_flows: list[dict] = []
        stress_flows: list[dict] = []
        for lane_index, lane in enumerate(lanes):
            exercised = not (
                (lane_index == 0 and seed == 1001) or (lane_index == 1 and seed == 1002)
            )
            baseline_qty = 100.0 if exercised else 0.0
            baseline_flows.append(
                {
                    "chain_id": lane.chain_id,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "uom": "KG",
                    "pulled_qty": baseline_qty,
                    "shipped_qty": baseline_qty,
                    "baseline_window_start_day": 0,
                    "baseline_window_end_day": 179,
                }
            )
            stress_flows.append(
                {
                    "chain_id": lane.chain_id,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "uom": "KG",
                    "pulled_qty": 100.0,
                    "shipped_qty": 100.0,
                }
            )
            flow_rows.append(
                {
                    "extension": case.extension,
                    "case_key": case.case_key,
                    "case_id": case.case_id,
                    "seed": seed,
                    "chain_id": lane.chain_id,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "failure_mode": case.failure_mode,
                    "stress_start_day": case.start_day,
                    "stress_end_day": case.end_day,
                    "simulation_days": case.simulation_days,
                    "outcome_spec_id": case.outcome_spec_id,
                    "outcome_bundle_sha256": case.outcome_bundle_sha256,
                    "uom": "KG",
                    "baseline_pulled_qty": baseline_qty,
                    "baseline_shipped_qty": baseline_qty,
                    "stress_pulled_qty": 100.0,
                    "stress_shipped_qty": 100.0,
                    "baseline_flow_evidence_available": True,
                    "baseline_flow_exercised": exercised,
                    "risk_configuration_loaded": True,
                    "risk_event_applied_on_lane": True,
                    "shipped_coverage_ratio": 1.0 if exercised else "",
                    "raw_cross_uom_aggregation_allowed": False,
                }
            )
        baseline["flow_metrics"] = baseline_flows
        stress["flow_metrics"] = stress_flows
        evidence[baseline_key] = baseline
        evidence[case.case_key] = stress

    controls = audit._validate_flow_rows(
        extension="multi_lane_supplier_common_cause",
        cases=cases,
        rows=flow_rows,
        evidence=evidence,
        baseline_owner_by_logical_key=baseline_owner,
    )
    assert all(
        row["active_exposure_interpretability_pass"]
        for row in controls["active_flow_gate_by_case_lane"]
    )
    joint = controls["all_lanes_joint_active_exposure_gate_by_case_supplier"]
    assert len(joint) == 1
    assert joint[0]["distinct_all_lanes_joint_active_exposure_seed_count"] == 28
    assert joint[0]["pass"] is False
    assert controls["all_lanes_joint_active_exposure_pass"] is False
    assert controls["active_exposure_interpretability_pass"] is False


def test_ledger_relative_path_cannot_escape_the_runner(tmp_path: Path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    runner_root = tmp_path / "runner"
    runner_root.mkdir()
    with pytest.raises(ValueError, match="hors du paquet"):
        audit._safe_relative_file(
            runner_root,
            "../outside.json",
            context="ledger/tampered",
        )


def test_retained_checkpoint_requires_the_exact_immutable_15_seed_subset(
    tmp_path: Path,
):
    seeds = tuple(range(1001, 1031))
    prefix = seeds[:15]

    def case(extension: str, index: int, seed: int) -> audit.CaseSpec:
        return audit.CaseSpec(
            extension=extension,
            case_id=f"{extension}_{index}",
            case_key=f"{extension}::{index}::seed_{seed}",
            seed=seed,
            pairing_block_id=f"block_{seed}",
            paired_baseline_case_id=f"baseline_{seed}",
            failure_mode="transport_delay",
            risk_type="lead_time_extra_days",
            mechanism_value=120.0,
            mechanism_unit="jours_ajoutes",
            start_day=0,
            end_day=179,
            lot_trace_required=False,
            lanes=(),
            products=("268091",),
            selection_slot=1,
            window_index=1,
            mathematical_family="date_shift",
            simulation_days=720,
            outcome_spec_id="full_horizon_J0_J719",
            outcome_start_day=0,
            outcome_end_day=719,
            outcome_day_count=720,
            outcome_bundle_sha256="bundle",
            preincident_snapshot_day=-1,
        )

    cases = {
        "multi_lane_supplier_common_cause": [
            case("multi_lane_supplier_common_cause", index, seed)
            for index in range(8)
            for seed in prefix
        ],
        "temporal_robustness": [
            case("temporal_robustness", index, seed)
            for index in range(16)
            for seed in prefix
        ],
        "priority_four_business_causes": [
            case("priority_four_business_causes", index, seed)
            for index in range(16)
            for seed in prefix
        ],
        "causal_lot_attribution_subset": [
            case("causal_lot_attribution_subset", index, prefix[0])
            for index in range(4)
        ],
    }
    owner_keys = {
        f"baseline_owner_{seed}_{horizon}" for seed in prefix for horizon in (720, 1063)
    }
    evidence = {key: {"seed": int(key.split("_")[2])} for key in owner_keys}
    expected_keys = owner_keys | {
        item.case_key for group in cases.values() for item in group
    }
    ledger_files = {
        key: (
            Path("ledger_cases")
            / f"{audit.hashlib.sha256(key.encode('utf-8')).hexdigest()[:20]}.json"
        ).as_posix()
        for key in sorted(expected_keys)
    }
    ledger_hashes = {key: "a" * 64 for key in expected_keys}
    checkpoint = {
        "schema_version": audit.PRELIMINARY_CHECKPOINT_SCHEMA_VERSION,
        "status": "paused_preliminary",
        "checkpoint_at_utc": "2026-09-03T12:00:00+00:00",
        "runner_signature": "runner",
        "runner_builder_sha256": audit.EXPECTED_RUNNER_BUILDER_SHA256,
        "planner_builder_sha256": audit.EXPECTED_PLANNER_BUILDER_SHA256,
        "plan_signature": "plan",
        "plan_manifest_sha256": "b" * 64,
        "priority_selection_lineage_sha256": "lineage",
        "seed_scheduling_policy": "cumulative_signed_seed_prefix_v1",
        "signed_full_seed_count": 30,
        "signed_full_seed_ids": list(seeds),
        "completed_seed_count": 15,
        "completed_seed_ids": list(prefix),
        "logical_baseline_reference_count": 31,
        "physical_baseline_owner_count": 30,
        "logical_stress_case_count": 604,
        "logical_stress_case_count_by_extension": {
            "multi_lane_supplier_common_cause": 120,
            "temporal_robustness": 240,
            "priority_four_business_causes": 240,
            "causal_lot_attribution_subset": 4,
        },
        "reused_source_stress_case_count": 124,
        "executed_engine_physical_run_count": 510,
        "full_expected_engine_physical_run_count": 1020,
        "remaining_engine_physical_run_count": 510,
        "ledger_evidence_case_count": 634,
        "case_evidence_file_sha256": {
            key: {"relative_path": ledger_files[key], "sha256": ledger_hashes[key]}
            for key in sorted(expected_keys)
        },
        "execution_ledger_sha256_at_checkpoint": "c" * 64,
        "all_target_seed_jobs_complete": True,
        "no_future_seed_job_active": True,
        "full_universe_complete": False,
        "canonical_results_written": False,
        "consolidation_written": False,
        "preliminary_not_final": True,
        "finalization_eligible": False,
        "publishable_execution_contract_pass": False,
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "promotion_allowed": False,
        "checkpoint_signature_semantics": (
            "internal_integrity_digest_not_authenticated_signature"
        ),
    }
    checkpoint["checkpoint_signature"] = audit._canonical_sha256(checkpoint)
    checkpoint_path = tmp_path / audit.PRELIMINARY_CHECKPOINT_FILE
    audit._write_json(checkpoint_path, checkpoint)
    runner_manifest = {
        "runner_signature": "runner",
        "preliminary_checkpoint_manifest": audit.PRELIMINARY_CHECKPOINT_FILE,
        "preliminary_checkpoint_manifest_sha256": audit._sha256(checkpoint_path),
        "checkpoint_history": [
            {
                "completed_seed_count": 15,
                "completed_seed_ids": list(prefix),
                "checkpoint_manifest": audit.PRELIMINARY_CHECKPOINT_FILE,
                "checkpoint_signature": checkpoint["checkpoint_signature"],
                "checkpoint_at_utc": checkpoint["checkpoint_at_utc"],
            }
        ],
    }
    plan_manifest = {
        "plan_signature": "plan",
        "priority_selection_lineage_sha256": "lineage",
    }
    ledger = {"case_files": ledger_files, "case_file_sha256": ledger_hashes}
    assert (
        audit._validate_retained_preliminary_checkpoint(
            runner_dir=tmp_path,
            runner_manifest=runner_manifest,
            plan_manifest=plan_manifest,
            plan_manifest_sha256="b" * 64,
            seeds=seeds,
            cases=cases,
            physical_owner_keys=owner_keys,
            evidence=evidence,
            ledger=ledger,
        )["completed_seed_count"]
        == 15
    )

    tampered_hashes = dict(ledger_hashes)
    tampered_hashes[next(iter(expected_keys))] = "d" * 64
    with pytest.raises(ValueError, match="non reutilisee a l'identique"):
        audit._validate_retained_preliminary_checkpoint(
            runner_dir=tmp_path,
            runner_manifest=runner_manifest,
            plan_manifest=plan_manifest,
            plan_manifest_sha256="b" * 64,
            seeds=seeds,
            cases=cases,
            physical_owner_keys=owner_keys,
            evidence=evidence,
            ledger={"case_files": ledger_files, "case_file_sha256": tampered_hashes},
        )


def test_reviewed_planner_and_runner_builders_are_exactly_pinned():
    runner_path = (
        Path(audit.__file__)
        .resolve()
        .with_name("supplier_network_post_priority_extension_runner.py")
    )
    assert audit._sha256(Path(audit.planner.__file__).resolve()) == (
        audit.EXPECTED_PLANNER_BUILDER_SHA256
    )
    assert audit._sha256(runner_path) == audit.EXPECTED_RUNNER_BUILDER_SHA256


def test_consolidation_signature_and_exact_inventory_are_fail_closed():
    source_hashes = {
        name: "a" * 64 for name in audit.REQUIRED_CONSOLIDATED_SOURCE_FILES
    }
    extension_hashes = {
        name: f"{index:064x}"
        for index, name in enumerate(audit.CONSOLIDATED_SMALL_EXTENSION_FILES, 1)
    }
    extension_manifest_hashes = {
        extension: extension_hashes[name]
        for extension, name in audit.CONSOLIDATED_EXTENSION_MANIFEST_FILES.items()
    }
    payload = {
        "schema_version": audit.RUNNER_SCHEMA_VERSION,
        "status": "complete",
        "source_campaign_manifest_sha256": "b" * 64,
        "source_small_file_hashes": source_hashes,
        "extension_small_file_hashes": extension_hashes,
        "runner_manifest_sha256": extension_hashes[
            "post_priority_extension_runner_manifest.json"
        ],
        "extension_manifest_hashes": extension_manifest_hashes,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "source_artifacts_mutated": False,
        "large_case_directories_copied": False,
    }
    signed_fields = {
        key: payload[key]
        for key in (
            "schema_version",
            "source_campaign_manifest_sha256",
            "source_small_file_hashes",
            "extension_small_file_hashes",
            "runner_manifest_sha256",
            "extension_manifest_hashes",
        )
    }
    payload["consolidation_signature"] = audit._canonical_sha256(signed_fields)
    assert audit._validated_consolidation_manifest_payload(payload)[0] == (
        source_hashes
    )

    tampered = json.loads(json.dumps(payload))
    tampered["source_small_file_hashes"]["supplier_sensitivity_ranking.csv"] = "c" * 64
    with pytest.raises(ValueError, match="Signature ou garde"):
        audit._validated_consolidation_manifest_payload(tampered)

    excessive = json.loads(json.dumps(payload))
    excessive["source_small_file_hashes"]["undeclared_ranking.csv"] = "d" * 64
    with pytest.raises(ValueError, match="Inventaire signe"):
        audit._validated_consolidation_manifest_payload(excessive)


def test_signed_design_hash_is_recomputed_from_the_typed_csv(tmp_path: Path):
    _source, plan, _graph, _engine, _profile = _runner_fixture(tmp_path)
    design_path = plan / "temporal_robustness_design.csv"
    rows = audit._read_csv(design_path)
    rows[0]["ranking_effect"] = "tampered_but_file_hash_redeclared"
    audit._write_csv(design_path, rows)
    manifest_path = plan / "post_priority_extensions_plan_manifest.json"
    manifest = audit._read_json(manifest_path)
    manifest["plan_file_hashes"][design_path.name] = audit._sha256(design_path)
    audit._write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="design_hashes"):
        audit._validate_plan_manifest(plan)


def test_pairing_rejects_a_different_or_nonpositive_demand():
    case = audit.CaseSpec(
        extension="temporal_robustness",
        case_id="case",
        case_key="temporal_robustness::case::seed_1001",
        seed=1001,
        pairing_block_id="metrics_seed_1001",
        paired_baseline_case_id="baseline_metrics__seed_1001",
        failure_mode="transport_delay",
        risk_type="lead_time_extra_days",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=0,
        end_day=179,
        lot_trace_required=True,
        lanes=(
            audit.Lane("chain_1", "supplier_1", "item_1", "M-1810", "edge_1", "268091"),
        ),
        products=("268091",),
        selection_slot=1,
        window_index=1,
        mathematical_family="date_shift",
        simulation_days=720,
        outcome_spec_id="full_horizon_J0_J719",
        outcome_start_day=0,
        outcome_end_day=719,
        outcome_day_count=720,
        outcome_bundle_sha256=audit._canonical_sha256(
            {
                "outcome_specs": [
                    {
                        "outcome_spec_id": "full_horizon_J0_J719",
                        "outcome_start_day": 0,
                        "outcome_end_day": 719,
                        "outcome_day_count": 720,
                    }
                ]
            }
        ),
        preincident_snapshot_day=-1,
    )
    with pytest.raises(ValueError, match="Demande non appariee"):
        audit._validate_evidence_pair(
            case=case,
            stress=_evidence(case.case_key, demand=999.0, case=case),
            baseline=_evidence("baseline", demand=1000.0, case=case, baseline=True),
            expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
        )
    with pytest.raises(ValueError, match="strictement positive"):
        audit._validate_evidence_pair(
            case=case,
            stress=_evidence(case.case_key, demand=0.0, case=case),
            baseline=_evidence("baseline", demand=0.0, case=case, baseline=True),
            expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
        )
    bad_uom = _evidence(case.case_key, case=case)
    bad_uom["local_product_metrics"][0]["uom"] = "KG"
    with pytest.raises(ValueError, match="Unite produit attendue UN"):
        audit._validate_evidence_pair(
            case=case,
            stress=bad_uom,
            baseline=_evidence("baseline", case=case, baseline=True),
            expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
        )
    extra_product = _evidence(case.case_key, case=case)
    extra_product["local_product_metrics"].append(_product_rows()[1])
    with pytest.raises(ValueError, match="Jeu exact de produits invalide"):
        audit._validate_evidence_pair(
            case=case,
            stress=extra_product,
            baseline=_evidence("baseline", case=case, baseline=True),
            expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
        )


def test_reused_causal_lot_material_is_reloaded_and_rehashed_from_signed_source(
    tmp_path: Path,
):
    source = tmp_path / "source_case"
    proof_dir = source / "proofs"
    receipt_path = proof_dir / "impacted_receipt_lots.csv"
    descendant_path = proof_dir / "impacted_descendant_lots.csv"
    genealogy_path = proof_dir / "impacted_genealogy.csv"
    client_path = proof_dir / "impacted_client_deliveries.csv"
    proof_dir.mkdir(parents=True)
    audit._write_csv(
        receipt_path,
        [
            {
                "lot_id": "ROOT-1",
                "item_id": "item_1",
                "node_id": "M-1810",
                "event_type": "lane_receipt",
                "day": 10,
                "qty": 100,
                "uom": "KG",
                "risk_event_ids": "event_1",
            }
        ],
    )
    audit._write_csv(
        descendant_path,
        [
            {
                "lot_id": "CHILD-1",
                "item_id": "268091",
                "node_id": "M-1810",
                "event_type": "production_release",
                "day": 20,
                "qty": 80,
                "uom": "UN",
                "risk_event_ids": "event_1",
            }
        ],
    )
    audit._write_csv(
        genealogy_path,
        [{"parent_lot_id": "ROOT-1", "child_lot_id": "CHILD-1"}],
    )
    audit._write_csv(client_path, [{"lot_id": "CHILD-1", "qty": 80, "uom": "UN"}])
    case = audit.CaseSpec(
        extension="causal_lot_attribution_subset",
        case_id="causal_case",
        case_key="causal_lot_attribution_subset::causal_case::seed_1001",
        seed=1001,
        pairing_block_id="block_1001",
        paired_baseline_case_id="baseline_1001",
        failure_mode="transport_delay",
        risk_type="lead_time_extra_days",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=45,
        end_day=224,
        lot_trace_required=True,
        lanes=(
            audit.Lane("chain_1", "supplier_1", "item_1", "M-1810", "edge_1", "268091"),
        ),
        products=("268091",),
        selection_slot=1,
        window_index=-1,
        mathematical_family="date_shift",
        simulation_days=720,
        outcome_spec_id="full_horizon_J0_J719",
        outcome_start_day=0,
        outcome_end_day=719,
        outcome_day_count=720,
        outcome_bundle_sha256="bundle",
        preincident_snapshot_day=-1,
    )
    baseline_key = audit._baseline_case_key(case.paired_baseline_case_id, case.seed)
    evidence = {
        baseline_key: {
            "lot_events": [{"lot_id": "BASE-1"}],
            "lot_genealogy": [],
        },
        case.case_key: {
            "reused_source_case": True,
            "run_dir": str(source),
            "lot_events": [],
            "lot_genealogy": [],
        },
    }
    hash_fields = {
        "source_incident_impacted_receipts_sha256": audit._sha256(receipt_path),
        "source_incident_impacted_descendants_sha256": audit._sha256(descendant_path),
        "source_incident_impacted_genealogy_sha256": audit._sha256(genealogy_path),
        "source_incident_impacted_client_deliveries_sha256": audit._sha256(client_path),
    }
    design = {
        "case_id": case.case_id,
        "seed": case.seed,
        "source_baseline_case_key": "",
        "source_baseline_lot_events_sha256": "",
        "source_baseline_lot_genealogy_sha256": "",
        "source_incident_case_key": str(source),
        "source_incident_evidence_format": "retained_genealogical_proof_exports",
        **hash_fields,
    }
    relative_by_field = {
        "source_incident_impacted_receipts_sha256": "proofs/impacted_receipt_lots.csv",
        "source_incident_impacted_descendants_sha256": (
            "proofs/impacted_descendant_lots.csv"
        ),
        "source_incident_impacted_genealogy_sha256": "proofs/impacted_genealogy.csv",
        "source_incident_impacted_client_deliveries_sha256": (
            "proofs/impacted_client_deliveries.csv"
        ),
    }
    declared = {
        f"{case.case_id}::{relative_by_field[field]}": value
        for field, value in hash_fields.items()
    }
    material = audit._validated_causal_lot_material(
        cases=[case],
        design_rows=[design],
        evidence=evidence,
        baseline_owner_by_logical_key={baseline_key: baseline_key},
        runner_manifest={"causal_source_material_hashes": declared},
    )[case.case_key]
    assert {row["lot_id"] for row in material.stress_events} == {"ROOT-1", "CHILD-1"}
    assert material.stress_events[0]["_proof_role"] == "direct_exposed_receipt"
    assert material.stress_events[1]["_proof_role"] == "exposed_descendant"

    audit._write_csv(receipt_path, [{"lot_id": "TAMPERED", "qty": 1, "uom": "KG"}])
    with pytest.raises(ValueError, match="Empreinte du materiau lot source invalide"):
        audit._validated_causal_lot_material(
            cases=[case],
            design_rows=[design],
            evidence=evidence,
            baseline_owner_by_logical_key={baseline_key: baseline_key},
            runner_manifest={"causal_source_material_hashes": declared},
        )


def test_causal_pair_can_be_valid_without_claiming_an_attributed_effect():
    case = audit.CaseSpec(
        extension="causal_lot_attribution_subset",
        case_id="causal_case",
        case_key="causal_lot_attribution_subset::causal_case::seed_1001",
        seed=1001,
        pairing_block_id="metrics_seed_1001",
        paired_baseline_case_id="baseline_metrics__seed_1001",
        failure_mode="transport_delay",
        risk_type="lead_time_extra_days",
        mechanism_value=120.0,
        mechanism_unit="jours_ajoutes",
        start_day=45,
        end_day=224,
        lot_trace_required=True,
        lanes=(
            audit.Lane("chain_1", "supplier_1", "item_1", "M-1810", "edge_1", "268091"),
        ),
        products=("268091",),
        selection_slot=1,
        window_index=-1,
        mathematical_family="date_shift",
        simulation_days=720,
        outcome_spec_id="full_horizon_J0_J719",
        outcome_start_day=0,
        outcome_end_day=719,
        outcome_day_count=720,
        outcome_bundle_sha256=audit._canonical_sha256(
            {
                "outcome_specs": [
                    {
                        "outcome_spec_id": "full_horizon_J0_J719",
                        "outcome_start_day": 0,
                        "outcome_end_day": 719,
                        "outcome_day_count": 720,
                    }
                ]
            }
        ),
        preincident_snapshot_day=-1,
    )
    detail = {
        "case_key": case.case_key,
        "case_id": case.case_id,
        "seed": case.seed,
        "failure_mode": case.failure_mode,
        "technical_key_type": "shipment",
        "technical_key_id": "SHIP-1",
        "node_id": "M-1810",
        "item_id": "item_1",
        "event_type": "lane_receipt",
        "uom": "KG",
        "baseline_day": 10,
        "stress_day": 10,
        "day_delta": 0,
        "baseline_qty": 100,
        "stress_qty": 100,
        "qty_delta": 0,
        "actual_difference_measured": False,
        "baseline_evidence_format": "runner_case_raw_exports",
        "pairing_input_sha256_pass": True,
        "pairing_j0_state_sha256_pass": True,
        "genealogical_exposure_only": False,
        "causal_scope": "technical_event_heuristic_not_causal_lot_identity",
        "counterfactual_entity_identity_validated": False,
        "pairing_method": (
            "heuristic_global_engine_counter_or_campaign_identifier; may shift "
            "between counterfactual runs"
        ),
    }
    summary = {
        "case_key": case.case_key,
        "case_id": case.case_id,
        "seed": case.seed,
        "failure_mode": case.failure_mode,
        "root_gate_pass": True,
        "genealogy_integrity_pass": True,
        "unique_matched_technical_key_count": 1,
        "actual_difference_row_count": 0,
        "heuristic_technical_event_comparison_evaluated": True,
        "paired_counterfactual_evaluated": False,
        "eligible_baseline_technical_key_count": 1,
        "eligible_stress_technical_key_count": 1,
        "matched_unique_technical_key_count": 1,
        "ambiguous_technical_key_count": 0,
        "baseline_only_unique_technical_key_count": 0,
        "stress_only_unique_technical_key_count": 0,
        "technical_event_heuristic_pairing_integrity_pass": True,
        "heuristic_comparison_display_allowed": True,
        "counterfactual_entity_identity_validated": False,
        "causal_lot_attribution_available": False,
        "genealogical_exposure_is_upper_bound": True,
        "industrial_lot_number_claimed": False,
    }
    exposure = {
        "case_key": case.case_key,
        "case_id": case.case_id,
        "seed": case.seed,
        "failure_mode": case.failure_mode,
        "root_lot_count": 1,
        "exposed_descendant_lot_count": 0,
        "exposed_row_count": 1,
        "exposed_quantity_upper_bound_by_uom_json": json.dumps(
            {"KG": 100.0}, sort_keys=True
        ),
        "descendant_quantity_is_upper_bound": True,
        "causal_delay_or_loss_claimed_from_genealogy": False,
        "root_gate_pass": True,
        "duplicate_root_lot_id_count": 0,
        "genealogy_integrity_pass": True,
        "missing_genealogy_lot_count": 0,
        "unreachable_declared_proof_lot_count": 0,
        "genealogy_cycle_detected": False,
        "published_exposure_is_exact_bfs_closure": True,
        "expected_risk_event_ids": f"{case.case_id}__lane1",
        "applied_expected_risk_event_ids": f"{case.case_id}__lane1",
        "root_eligibility_requires_effective_risk_application": True,
    }
    baseline_key = audit._baseline_case_key(case.paired_baseline_case_id, case.seed)
    baseline_evidence = _evidence(baseline_key, case=case, baseline=True)
    stress_evidence = _evidence(case.case_key, case=case)
    baseline_evidence["lot_events"] = [
        {
            "lot_id": "BASE-1",
            "shipment_id": "SHIP-1",
            "node_id": "M-1810",
            "item_id": "item_1",
            "event_type": "lane_receipt",
            "uom": "KG",
            "day": 10,
            "qty": 100,
        }
    ]
    stress_evidence["lot_events"] = [
        {
            "lot_id": "STRESS-1",
            "shipment_id": "SHIP-1",
            "node_id": "M-1810",
            "item_id": "item_1",
            "event_type": "lane_receipt",
            "uom": "KG",
            "day": 10,
            "qty": 100,
            "risk_event_ids": f"{case.case_id}__lane1",
        }
    ]
    exposure_detail = {
        "extension": case.extension,
        "case_key": case.case_key,
        "case_id": case.case_id,
        "seed": case.seed,
        "failure_mode": case.failure_mode,
        "stress_start_day": case.start_day,
        "stress_end_day": case.end_day,
        "chain_ids": "chain_1",
        "supplier_ids": "supplier_1",
        "lot_id": "STRESS-1",
        "exposure_role": "risk_tagged_usable_receipt_root",
        "genealogy_depth": "",
        "node_id": "M-1810",
        "item_id": "item_1",
        "event_id": "",
        "event_type": "lane_receipt",
        "day": 10,
        "qty": 100,
        "uom": "KG",
        "risk_event_ids": f"{case.case_id}__lane1",
        "shipment_id": "SHIP-1",
        "production_campaign_id": "",
        "source_type": "",
        "source_id": "",
        "descendant_quantity_is_exposure_upper_bound": True,
        "causal_delay_or_loss_claimed": False,
        "counterfactual_entity_identity_validated": False,
        "industrial_lot_number_claimed": False,
        "lot_identifier_semantics": (
            "identifiant_technique_simule_pas_numero_lot_industriel"
        ),
    }
    evidence = {
        case.case_key: stress_evidence,
        baseline_key: baseline_evidence,
    }
    lot_material = {
        case.case_key: audit.CausalLotMaterial(
            baseline_events=baseline_evidence["lot_events"],
            stress_events=stress_evidence["lot_events"],
            stress_genealogy=[],
            baseline_evidence_format="runner_case_raw_exports",
        )
    }
    result = audit._validate_causal_outputs(
        cases=[case],
        summary_rows=[_csv_record(summary)],
        detail_rows=[_csv_record(detail)],
        exposure_rows=[_csv_record(exposure)],
        exposure_detail_rows=[_csv_record(exposure_detail)],
        evidence=evidence,
        baseline_owner_by_logical_key={baseline_key: baseline_key},
        expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
        lot_material_by_case=lot_material,
    )
    assert result["causal_lot_execution_integrity_pass"] is True
    assert result["technical_event_heuristic_pairing_integrity_pass"] is True
    assert result["heuristic_comparison_evaluable_pass"] is True
    assert result["causal_comparison_evaluable_pass"] is False
    assert result["causal_lot_attribution_available"] is False
    assert result["any_heuristic_difference_detected"] is False
    assert result["genealogical_exposure_is_upper_bound"] is True

    tampered_exposure_detail = {
        **exposure_detail,
        "causal_delay_or_loss_claimed": True,
    }
    with pytest.raises(ValueError, match="Detail d'exposition lot non recomposable"):
        audit._validate_causal_outputs(
            cases=[case],
            summary_rows=[_csv_record(summary)],
            detail_rows=[_csv_record(detail)],
            exposure_rows=[_csv_record(exposure)],
            exposure_detail_rows=[_csv_record(tampered_exposure_detail)],
            evidence=evidence,
            baseline_owner_by_logical_key={baseline_key: baseline_key},
            expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
            lot_material_by_case=lot_material,
        )

    # A duplicated heuristic key is faithfully reported as ambiguous.  It
    # blocks comparison/attribution, but must not turn a valid engine/ledger
    # execution into an execution-integrity failure.
    ambiguous_summary = dict(summary)
    ambiguous_summary.update(
        {
            "unique_matched_technical_key_count": 0,
            "heuristic_technical_event_comparison_evaluated": False,
            "paired_counterfactual_evaluated": False,
            "eligible_baseline_technical_key_count": 1,
            "eligible_stress_technical_key_count": 1,
            "matched_unique_technical_key_count": 0,
            "ambiguous_technical_key_count": 1,
            "baseline_only_unique_technical_key_count": 1,
            "stress_only_unique_technical_key_count": 0,
            "technical_event_heuristic_pairing_integrity_pass": False,
            "heuristic_comparison_display_allowed": False,
        }
    )
    ambiguous_exposure = dict(exposure)
    ambiguous_exposure.update(
        {
            "root_lot_count": 2,
            "exposed_row_count": 2,
            "exposed_quantity_upper_bound_by_uom_json": json.dumps(
                {"KG": 200.0}, sort_keys=True
            ),
        }
    )
    ambiguous_stress = json.loads(json.dumps(stress_evidence))
    ambiguous_stress["lot_events"].append(
        {
            **ambiguous_stress["lot_events"][0],
            "lot_id": "STRESS-2",
        }
    )
    ambiguous_result = audit._validate_causal_outputs(
        cases=[case],
        summary_rows=[_csv_record(ambiguous_summary)],
        detail_rows=[],
        exposure_rows=[_csv_record(ambiguous_exposure)],
        exposure_detail_rows=[
            _csv_record(exposure_detail),
            _csv_record({**exposure_detail, "lot_id": "STRESS-2"}),
        ],
        evidence={
            case.case_key: ambiguous_stress,
            baseline_key: baseline_evidence,
        },
        baseline_owner_by_logical_key={baseline_key: baseline_key},
        expected_products=set(audit.EXPECTED_TARGET_PRODUCTS),
        lot_material_by_case={
            case.case_key: audit.CausalLotMaterial(
                baseline_events=baseline_evidence["lot_events"],
                stress_events=ambiguous_stress["lot_events"],
                stress_genealogy=[],
                baseline_evidence_format="runner_case_raw_exports",
            )
        },
    )
    assert ambiguous_result["causal_lot_execution_integrity_pass"] is True
    assert ambiguous_result["technical_event_heuristic_pairing_integrity_pass"] is False
    assert ambiguous_result["heuristic_comparison_evaluable_pass"] is False
    assert ambiguous_result["causal_comparison_evaluable_pass"] is False


@pytest.fixture(scope="module")
def closed_full_package(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    pytest.skip(
        "ancien fixture full a trois voies et executeur injecte; le contrat publiable "
        "groupe-4 exige le runner moteur builtin et sera teste sur le paquet V3 clos"
    )
    root = tmp_path_factory.mktemp("extension_interpretation_full")
    _source, plan, graph, engine, profile = _runner_fixture(root)
    runner_dir = root / "runner_full"
    monkeypatch = pytest.MonkeyPatch()

    def _windows_test_json_writer(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        runner.network.campaign_core,
        "write_json_atomic",
        _windows_test_json_writer,
    )

    def _compact_test_consolidation(
        *, source_dir: Path, runner_dir: Path, output_dir: Path | None = None
    ) -> Path:
        del source_dir
        target = output_dir or runner_dir / "consolidated_dashboard_network_artifact"
        target.mkdir(parents=True, exist_ok=False)
        extensions = {
            "multi_lane_supplier_common_cause": {"pass": True, "status": "complete"},
            "temporal_robustness": {"pass": True, "status": "complete"},
            "four_business_cause_confirmation": {"pass": True, "status": "complete"},
            "causal_lot_attribution": {"pass": True, "status": "complete"},
        }
        _windows_test_json_writer(
            target / "campaign_manifest.json",
            {
                "status": "complete",
                "mode": "full",
                "extensions_required": extensions,
                "promotion_allowed": True,
            },
        )
        _windows_test_json_writer(
            target / "consolidation_manifest.json",
            {"status": "complete", "legacy_test_fixture": True},
        )
        for name in (
            "multi_lane_supplier_common_cause_manifest.json",
            "temporal_robustness_manifest.json",
            "priority_four_business_causes_manifest.json",
            "causal_lot_attribution_manifest.json",
            "post_priority_extension_runner_manifest.json",
        ):
            shutil.copy2(runner_dir / name, target / name)
        return target

    monkeypatch.setattr(
        runner,
        "consolidate_dashboard_network_artifact",
        _compact_test_consolidation,
    )
    try:
        runner.run_extensions(
            plan_dir=plan,
            mode="full",
            output_dir=runner_dir,
            graph_path=graph,
            engine_path=engine,
            profile_path=profile,
            workers=1,
            case_executor=FakeExecutor(),
        )
    finally:
        monkeypatch.undo()
    audit_dir = audit.build_audit_package(
        runner_dir=runner_dir,
        output_dir=root / "extension_audit",
    )
    return {"root": root, "runner": runner_dir, "audit": audit_dir}


def test_full_closed_runner_builds_a_signed_fail_closed_audit(closed_full_package):
    runner_dir = closed_full_package["runner"]
    audit_dir = closed_full_package["audit"]
    runner_hash_before = audit._sha256(
        runner_dir / "post_priority_extension_runner_manifest.json"
    )
    result = audit.validate_audit_package(audit_dir)
    assert result["valid"] is True
    assert result["promotion_allowed"] is False
    controls = json.loads(
        (audit_dir / "scientific_promotion_controls.json").read_text(encoding="utf-8")
    )
    assert controls["global_priority_temporal_robustness_evaluable"] is False
    assert controls["global_four_cause_priority_robustness_evaluable"] is False
    assert controls["network_recovery_metric_status"] == (
        "excluded_invalid_common_window"
    )
    assert (
        audit._sha256(runner_dir / "post_priority_extension_runner_manifest.json")
        == runner_hash_before
    )
    with pytest.raises(FileExistsError):
        audit.build_audit_package(runner_dir=runner_dir, output_dir=audit_dir)


def test_duplicate_physical_baseline_owner_is_rejected(closed_full_package):
    manifest_path = (
        closed_full_package["runner"] / "post_priority_extension_runner_manifest.json"
    )
    original = manifest_path.read_bytes()
    try:
        payload = json.loads(original.decode("utf-8"))
        owners = payload["baseline_materialization"]["physical_owner_case_keys"]
        owners.append(owners[0])
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="vide ou dupliquee"):
            audit.load_closed_runner(closed_full_package["runner"])
    finally:
        manifest_path.write_bytes(original)


def test_overlay_neutralizes_old_release_gate_aliases_without_mutating_sources(
    closed_full_package,
):
    root = closed_full_package["root"]
    runner_dir = closed_full_package["runner"]
    audit_dir = closed_full_package["audit"]
    consolidated = runner_dir / "consolidated_dashboard_network_artifact"
    source_hash = audit._sha256(consolidated / "campaign_manifest.json")
    overlay = audit.build_scientific_overlay(
        consolidated_dir=consolidated,
        audit_dir=audit_dir,
        output_dir=root / "scientific_overlay",
    )
    result = audit.validate_scientific_overlay(overlay)
    assert result["promotion_allowed"] is False
    campaign = json.loads(
        (overlay / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    assert campaign["legacy_runner_promotion_aliases_neutralized"] is True
    assert campaign["promotion_allowed"] is False
    assert all(
        state["pass"] is False
        for state in campaign.get("extensions_required", {}).values()
    )
    for name in (
        "multi_lane_supplier_common_cause_manifest.json",
        "temporal_robustness_manifest.json",
        "priority_four_business_causes_manifest.json",
        "causal_lot_attribution_manifest.json",
    ):
        extension_manifest = json.loads((overlay / name).read_text(encoding="utf-8"))
        assert extension_manifest["release_gate_pass"] is False
        assert "legacy_runner_release_gate_value" in extension_manifest
    assert audit._sha256(consolidated / "campaign_manifest.json") == source_hash
    unsigned_alias = overlay / "promotion_controls.json"
    unsigned_alias.write_text(json.dumps({"promotion_allowed": True}), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="Inventaire disque de la surcouche"):
            audit.validate_scientific_overlay(overlay)
    finally:
        unsigned_alias.unlink()
    omitted_path = overlay / "causal_lot_attribution_manifest.json"
    omitted_bytes = omitted_path.read_bytes()
    omitted_path.unlink()
    try:
        with pytest.raises(ValueError, match="Inventaire disque de la surcouche"):
            audit.validate_scientific_overlay(overlay)
    finally:
        omitted_path.write_bytes(omitted_bytes)


def test_package_validator_rejects_a_tampered_output(
    closed_full_package, tmp_path: Path
):
    source = closed_full_package["audit"]
    copy = tmp_path / "tampered_audit"
    shutil.copytree(source, copy)
    unsigned_alias = copy / "promotion_controls.json"
    unsigned_alias.write_text(json.dumps({"promotion_allowed": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="Inventaire disque du paquet"):
        audit.validate_audit_package(copy)
    unsigned_alias.unlink()
    omitted_path = copy / "temporal_pairwise_difference_audit.csv"
    omitted_bytes = omitted_path.read_bytes()
    omitted_path.unlink()
    with pytest.raises(ValueError, match="Inventaire disque du paquet"):
        audit.validate_audit_package(copy)
    omitted_path.write_bytes(omitted_bytes)
    controls_path = copy / "scientific_promotion_controls.json"
    controls_path.write_text(
        controls_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Empreinte de sortie invalide"):
        audit.validate_audit_package(copy)
