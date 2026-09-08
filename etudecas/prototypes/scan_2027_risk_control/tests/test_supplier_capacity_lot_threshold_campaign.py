from __future__ import annotations

import math

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_capacity_lot_threshold_campaign as threshold,
)


def _minimal_graph() -> dict[str, object]:
    return {
        "edges": [
            {
                "id": "edge:target",
                "from": threshold.SUPPLIER_ID,
                "to": threshold.DESTINATION_ID,
                "items": [threshold.ITEM_ID],
                "attrs": {
                    "standard_order_qty": 120000,
                    "standard_order_uom": "UN",
                    "source_workbook": "268967.xlsx",
                },
            }
        ]
    }


def test_fixed_grid_maps_the_one_lot_gate_without_duplicate_execution() -> None:
    scenarios = threshold.build_threshold_scenarios()
    assert [scenario.value for scenario in scenarios] == list(
        threshold.CAPACITY_RATIOS
    )
    assert len(threshold.executable_scenarios(scenarios)) == 6
    assert scenarios[0].is_baseline_alias is True
    rows = threshold.scenario_design_rows(scenarios)
    assert len(rows) == 7
    by_ratio = {float(row["capacity_ratio"]): row for row in rows}
    assert by_ratio[0.41]["capacity_qty_per_day"] == 123000
    assert by_ratio[0.41]["integer_lot_slots_per_day"] == 1
    assert by_ratio[0.40]["capacity_qty_per_day"] == 120000
    assert by_ratio[0.40]["integer_lot_slots_per_day"] == 1
    assert by_ratio[0.39]["capacity_qty_per_day"] == 117000
    assert by_ratio[0.39]["integer_lot_slots_per_day"] == 0
    assert by_ratio[0.39]["capacity_regime"] == "sous_le_seuil_aucun_lot"
    assert all(row["curve_type"] == "discrete_engine_integer_lot_gate" for row in rows)
    assert not any(row["is_physical_supplier_cliff"] for row in rows)


def test_graph_audit_proves_120000_and_arithmetic_threshold() -> None:
    audit = threshold.audit_graph_standard_order(_minimal_graph())
    assert audit["validated"] is True
    assert audit["standard_order_qty"] == 120000
    assert audit["reference_capacity_qty_per_day"] == 300000
    assert audit["arithmetic_one_lot_threshold_ratio"] == pytest.approx(0.4)
    assert audit["proof"] == "120000 / 300000 = 0.40"


def test_graph_audit_fails_loudly_if_lot_input_changes() -> None:
    graph = _minimal_graph()
    graph["edges"][0]["attrs"]["standard_order_qty"] = 100000  # type: ignore[index]
    with pytest.raises(ValueError, match="standard order quantity changed"):
        threshold.audit_graph_standard_order(graph)


def test_real_engine_contains_the_audited_integer_lot_capacity_rule() -> None:
    audit = threshold.audit_engine_integer_lot_gate(threshold.landscape.DEFAULT_ENGINE)
    assert audit["validated"] is True
    assert audit["curve_is_discontinuous_by_construction"] is True
    assert len(audit["engine_sha256"]) == 64
    line_numbers = list(audit["rule_line_numbers"].values())
    assert line_numbers == sorted(line_numbers)


def test_capacity_events_only_touch_target_lane_during_j45_to_j224() -> None:
    scenario = threshold.scenario_for_ratio(
        threshold.build_threshold_scenarios(), 0.39
    )
    rows = threshold.landscape.build_risk_event_rows(
        scenario, threshold.MEASURED_DAYS
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["risk_type"] == "capacity"
    assert row["supplier_id"] == threshold.SUPPLIER_ID
    assert row["item_id"] == threshold.ITEM_ID
    assert row["dst_node_id"] == threshold.DESTINATION_ID
    assert (row["start_day"], row["end_day"]) == (45, 224)
    assert row["multiplier"] == pytest.approx(0.39)


def _baseline_metric(seed: int = threshold.SCREENING_SEED) -> dict[str, object]:
    prefix = f"baseline_chain__{threshold.CHAIN_ID}__"
    return {
        "scenario_id": "baseline_nominal",
        "seed": seed,
        "j0_state_sha256": f"j0-{seed}",
        "valid": True,
        "fill_rate_268967": 1.0,
        "on_due_volume_proxy_268967": 1.0,
        "backlog_qty_days_268967": 0.0,
        "worst_rolling_28d_on_due_proxy_268967": 1.0,
        f"{prefix}incident_shipped_qty": 240000.0,
    }


def _stress_metric(
    scenario_id: str,
    on_due: float,
    shipped: float,
    seed: int = threshold.SCREENING_SEED,
) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "seed": seed,
        "j0_state_sha256": f"j0-{seed}",
        "valid": True,
        "product_service_horizon": 1.0,
        "product_on_due_date_proxy": on_due,
        "target_backlog_qty_days": (1.0 - on_due) * 1_000_000,
        "incremental_target_backlog_qty_days": (1.0 - on_due) * 1_000_000,
        "target_worst_rolling_28d_on_due_proxy": max(0.0, on_due - 0.1),
        "supplier_incident_shipped_qty": shipped,
        "supplier_incident_flow_coverage_vs_paired_baseline": shipped / 240000,
        "supplier_incident_capacity_binding_days": 180,
        "target_on_due_date_proxy_delta_vs_paired_baseline": on_due - 1.0,
    }


def test_curve_explicitly_marks_crossing_and_same_j0() -> None:
    scenarios = threshold.build_threshold_scenarios()
    rows: list[dict[str, object]] = [_baseline_metric()]
    for scenario in threshold.executable_scenarios(scenarios):
        if threshold.values_equal(scenario.value, 0.40):
            on_due, shipped = 0.96, 120000.0
        elif threshold.values_equal(scenario.value, 0.39):
            on_due, shipped = 0.72, 0.0
        else:
            on_due, shipped = 0.98, 120000.0
        rows.append(_stress_metric(scenario.scenario_id, on_due, shipped))
    curve = threshold.build_threshold_curve_rows(rows, [], scenarios)
    assert len(curve) == 7
    by_ratio = {float(row["capacity_ratio"]): row for row in curve}
    assert by_ratio[1.0]["screening_product_on_due_date_proxy_mean"] == 1.0
    assert by_ratio[0.40]["screening_same_j0_as_paired_baseline"] is True
    assert by_ratio[0.39]["crosses_one_lot_gate_from_previous_ratio"] is True
    assert by_ratio[0.39][
        "screening_on_due_change_from_previous_higher_ratio"
    ] == pytest.approx(-0.24)
    assert by_ratio[0.39]["confirmation_n_seeds"] == 0
    observation = threshold.threshold_observation(curve)
    assert observation["whole_lot_gate_proven_from_inputs_and_engine"] is True
    assert observation["screening_zero_flow_below_gate_observed"] is True
    assert observation["screening_product_effect_step_observed"] is True


def test_j0_audit_rejects_one_drifted_stress_case() -> None:
    scenario = threshold.scenario_for_ratio(
        threshold.build_threshold_scenarios(), 0.40
    )
    baseline = _baseline_metric()
    stress = _stress_metric(scenario.scenario_id, 0.95, 120000.0)
    assert threshold.j0_audit([baseline, stress], [])["validated"] is True
    stress["j0_state_sha256"] = "drifted"
    assert threshold.j0_audit([baseline, stress], [])["validated"] is False


def test_confirmation_ratios_and_seeds_are_configurable_without_running() -> None:
    args = threshold.parse_args(
        [
            "--confirm-threshold",
            "--confirmation-ratios",
            "0.41,0.40,0.39",
            "--confirmation-seeds",
            "330282-330291",
            "--workers",
            "8",
        ]
    )
    assert args.confirm_threshold is True
    assert args.workers == 8
    assert threshold.parse_ratios(args.confirmation_ratios) == [0.41, 0.40, 0.39]
    assert threshold.landscape.parse_seeds(args.confirmation_seeds) == list(
        range(330282, 330292)
    )
    assert threshold.parse_args([]).confirm_threshold is False
    with pytest.raises(ValueError, match="outside the fixed screening grid"):
        threshold.parse_ratios("0.42")


def test_v4_protocol_constants_are_reused() -> None:
    assert threshold.MEASURED_DAYS == 720
    assert threshold.landscape.WARMUP_DAYS == 240
    assert threshold.landscape.INCIDENT_START_DAY == 45
    assert threshold.landscape.INCIDENT_DURATION_DAYS == 180
    assert threshold.SCREENING_SEED == 330281
    assert "--mrp-smoothed-cover-requirement-pair" in (
        threshold.landscape.CAMPAIGN_PROTOCOL_ARGS
    )
    assert "--no-supplier-risk-loss-gross-up" in (
        threshold.landscape.CAMPAIGN_PROTOCOL_ARGS
    )
    assert math.isclose(
        threshold.EXPECTED_STANDARD_ORDER_QTY
        / threshold.REFERENCE_CAPACITY_QTY_PER_DAY,
        0.4,
    )
