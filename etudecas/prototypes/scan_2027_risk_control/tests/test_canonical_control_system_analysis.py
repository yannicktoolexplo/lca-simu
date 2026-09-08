from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_control_system_analysis import (
    ACTUATOR_INPUTS,
    PHYSICAL_CANDIDATE_MODEL,
    IdentificationSequence,
    controllability_matrix,
    fit_reduced_dmdc,
    observability_matrix,
    run_control_system_analysis,
    siso_state_space_zeros,
)
from etudecas.visualization.maps.control_system_dashboard_payload import (
    build_control_system_dashboard_section,
)


def _simulate(
    a_matrix: np.ndarray,
    b_matrix: np.ndarray,
    commands: np.ndarray,
    *,
    initial: np.ndarray | None = None,
) -> np.ndarray:
    states = np.zeros((len(commands) + 1, len(a_matrix)), dtype=float)
    if initial is not None:
        states[0] = initial
    for index, command in enumerate(commands):
        states[index + 1] = a_matrix @ states[index] + b_matrix @ command
    return states


def test_numpy_state_space_algebra_and_reduced_dmdc_recover_known_system() -> None:
    a_matrix = np.array([[0.78, 0.12], [-0.08, 0.62]])
    b_matrix = np.array([[0.25, 0.03], [0.05, 0.22]])
    assert np.linalg.matrix_rank(controllability_matrix(a_matrix, b_matrix)) == 2
    assert np.linalg.matrix_rank(observability_matrix(a_matrix, np.eye(2))) == 2

    rng = np.random.default_rng(421)

    def sequence(name: str, samples: int) -> IdentificationSequence:
        commands = rng.normal(size=(samples - 1, 2))
        states = _simulate(
            a_matrix,
            b_matrix,
            commands,
            initial=rng.normal(size=2),
        )
        return IdentificationSequence(name, states, commands)

    result = fit_reduced_dmdc(
        [sequence("estimate_1", 450), sequence("estimate_2", 450)],
        [sequence("independent_validation", 280)],
        state_names=["stock", "pipeline"],
        input_names=["order", "production"],
        candidate_orders=[2],
        independent_validation=True,
    )

    assert result.accepted is True
    assert result.rejection_reasons == []
    assert result.selected_order == 2
    assert result.candidate_metrics.iloc[0]["free_run_nrmse"] < 1e-10
    np.testing.assert_allclose(
        np.sort_complex(result.poles),
        np.sort_complex(np.linalg.eigvals(a_matrix)),
        atol=1e-10,
    )

    zeros = siso_state_space_zeros(
        np.diag([0.5, 0.7]),
        np.array([1.0, 1.0]),
        np.array([1.0, -5.0 / 3.0]),
    )
    np.testing.assert_allclose(zeros, [0.2], atol=1e-10)


def test_reduced_dmdc_rejects_exact_actuator_dead_zone() -> None:
    commands = np.sin(np.arange(79) / 4.0).reshape(-1, 1)
    states = np.zeros((80, 2), dtype=float)
    sequence = IdentificationSequence("dead_zone", states, commands)

    result = fit_reduced_dmdc(
        [sequence],
        [sequence],
        state_names=["stock", "pipeline"],
        input_names=["order"],
        independent_validation=False,
    )

    assert result.available is False
    assert result.accepted is False
    assert "physical_actuator_dead_zone" in result.rejection_reasons


def _write_v3_fixture(root: Path, *, days: int = 80, period: int = 20) -> None:
    root.mkdir()
    controller = {
        "schema_version": "scan.canonical_state_feedback.v3",
        "dynamics": {
            "stress_memory": 0.82,
            "nervousness_gain": 0.2,
            "pressure_gain": 0.34,
            "disruption_gain": 0.5,
        },
        "continuous_relief": {
            "enabled": True,
            "stress_span": 1.15,
            "order_relief_gain": 0.04,
            "production_relief_gain": 0.02,
        },
    }
    (root / "controller.json").write_text(json.dumps(controller), encoding="utf-8")
    protocol = {
        "schema_version": "scan.canonical_frequency_study.v1",
        "controller": {
            "schema_version": "scan.canonical_state_feedback.v3",
            "snapshot_relative_path": "controller.json",
        },
        "sampling": {
            "measured_days": days,
            "designed_period_days": period,
        },
    }
    (root / "canonical_frequency_protocol.json").write_text(
        json.dumps(protocol), encoding="utf-8"
    )
    time = np.arange(days)
    demand = 0.005 * (
        np.sin(2.0 * np.pi * time / period)
        + 0.35 * np.sin(6.0 * np.pi * time / period)
    )
    trajectories = pd.DataFrame(
        {
            "condition": "supplier_stress_capacity",
            "policy": "canonical_feedback",
            "experiment_input_signal": "demand_multiplier",
            "day": time,
            "period_index": time // period,
            "excitation_fraction__demand_multiplier": demand,
            "baseline__global_inventory_qty": 1_000_000.0 - 1_100.0 * time,
            "baseline__global_order_qty": 10_000.0 + 15.0 * time,
            "baseline__target_finished_stock_qty": 4_000.0,
            "baseline__control_order_multiplier": 0.99,
            "baseline__control_production_target_multiplier": 0.995,
            "delta__global_inventory_qty": 100.0 * np.sin(2.0 * np.pi * time / period),
            "delta__target_production_qty": 0.0,
            "delta__probe_destination_arrivals_qty": 0.0,
            "delta__target_backlog_qty": 0.0,
            "delta__target_service_level": 0.0,
        }
    )
    trajectories.to_csv(root / "canonical_frequency_trajectories.csv", index=False)
    decisions_dir = (
        root
        / "runs"
        / "supplier_stress_capacity"
        / "excited"
        / "demand_multiplier"
        / "canonical_feedback"
        / "seed_17"
        / "data"
    )
    decisions_dir.mkdir(parents=True)
    relief = 0.4 + 0.1 * np.sin(2.0 * np.pi * np.arange(days - 1) / period)
    pd.DataFrame(
        {
            "decision_day": np.arange(days - 1),
            "control_continuous_requested_order_multiplier": 1.0 - 0.04 * relief,
            "control_continuous_requested_production_target_multiplier": 1.0
            - 0.02 * relief,
        }
    ).to_csv(decisions_dir / "canonical_closed_loop_decisions.csv", index=False)


def _write_state_exports(
    data_dir: Path,
    *,
    finished: np.ndarray,
    factory: np.ndarray,
    supplier: np.ndarray,
) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    days = len(finished)
    pd.DataFrame(
        {
            "day": np.arange(days),
            "node_id": "M-1",
            "item_id": "item:FG",
            "produced_qty": 0.0,
            "cum_produced_qty": 0.0,
            "stock_end_of_day": finished,
        }
    ).to_csv(data_dir / "production_output_products_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": np.arange(days),
            "node_id": "M-1",
            "item_id": "item:C",
            "stock_before_production": factory,
            "stock_end_of_day": factory,
        }
    ).to_csv(data_dir / "production_input_stocks_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": np.arange(days),
            "node_id": "S-1",
            "item_id": "item:C",
            "stock_end_of_day": supplier,
        }
    ).to_csv(data_dir / "production_supplier_stocks_daily.csv", index=False)
    pd.DataFrame(
        columns=[
            "day",
            "item_id",
            "src_node_id",
            "dst_node_id",
            "release_day",
            "arrival_day",
            "actual_receipt_day",
            "planned_receipt_qty",
        ]
    ).to_csv(data_dir / "mrp_orders_daily.csv", index=False)


def _write_actuator_fixture(
    root: Path,
    *,
    days: int = 80,
    period: int = 20,
    post_feedback_additive: bool = False,
) -> None:
    root.mkdir()
    actuator_probe: dict[str, object] = {"enabled": True}
    if post_feedback_additive:
        actuator_probe.update(
            {
                "application_mode": "post_feedback_additive",
                "baseline_condition": "supplier_stress_capacity",
                "baseline_policy": "canonical_feedback",
            }
        )
    protocol = {
        "schema_version": "scan.canonical_frequency_study.v1",
        "measured_days": days,
        "sampling": {"measured_days": days, "designed_period_days": period},
        "actuator_probe": actuator_probe,
        "supplier_probe": {
            "supplier_id": "S-1",
            "item_id": "item:C",
            "dst_node_id": "M-1",
            "target_finished_item_id": "item:FG",
            "nominal_lead_time_days": 5.0,
        },
    }
    (root / "canonical_frequency_protocol.json").write_text(
        json.dumps(protocol), encoding="utf-8"
    )
    condition = "supplier_stress_capacity" if post_feedback_additive else "nominal_capacity"
    policy = "canonical_feedback" if post_feedback_additive else "mrp_reference"
    baseline_data = root / "runs" / condition / "baseline" / policy / "seed_17" / "data"
    base_finished = np.full(days, 10_000.0)
    base_factory = np.full(days, 20_000.0)
    base_supplier = np.full(days, 30_000.0)
    _write_state_exports(
        baseline_data,
        finished=base_finished,
        factory=base_factory,
        supplier=base_supplier,
    )
    a_matrix = np.array([[0.72, 0.08, 0.0], [0.0, 0.61, 0.06], [0.04, 0.0, 0.55]])
    b_matrix = np.array([[80.0, 20.0, 10.0], [15.0, 60.0, 12.0], [5.0, 10.0, 75.0]])
    trajectory_rows: list[dict[str, object]] = []
    time = np.arange(days)
    for input_index, input_name in enumerate(ACTUATOR_INPUTS):
        command = 0.05 * np.sin(
            2.0 * np.pi * (input_index + 1) * time / period + input_index * 0.37
        )
        delta = np.zeros((days, 3))
        for day in range(1, days):
            delta[day] = a_matrix @ delta[day - 1] + b_matrix[:, input_index] * command[day]
        excited_data = (
            root
            / "actuator_probe"
            / "excited"
            / input_name
            / policy
            / "seed_17"
            / "data"
        )
        _write_state_exports(
            excited_data,
            finished=base_finished + delta[:, 0],
            factory=base_factory + delta[:, 1],
            supplier=base_supplier + delta[:, 2],
        )
        for day in range(days):
            trajectory_rows.append(
                {
                    "condition": condition,
                    "policy": (
                        "canonical_feedback_post_feedback_additive_probe"
                        if post_feedback_additive
                        else "mrp_reference_schedule_probe"
                    ),
                    "experiment_input_signal": input_name,
                    "day": day,
                    "period_index": day // period,
                    input_name: command[day],
                    f"excitation_fraction__{input_name}": command[day],
                }
            )
    pd.DataFrame(trajectory_rows).to_csv(
        root / "canonical_frequency_trajectories.csv", index=False
    )


def test_end_to_end_lightweight_packages_export_rejected_model_and_figures(
    tmp_path: Path,
) -> None:
    v3_root = tmp_path / "v3"
    actuator_root = tmp_path / "actuator"
    output = tmp_path / "analysis"
    _write_v3_fixture(v3_root)
    _write_actuator_fixture(actuator_root)

    result = run_control_system_analysis(v3_root, actuator_root, output)

    manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
    assert manifest["status"] == "exploratory_complete"
    assert manifest["controller_exact_analysis"]["memory_pole"] == 0.82
    assert manifest["controller_exact_analysis"]["actuator_space_rank"] == 1
    assert manifest["physical_identification"]["accepted"] is False
    assert (
        "validation_repeats_the_same_periodic_phase"
        in manifest["physical_identification"]["rejection_reasons"]
    )
    assert manifest["claims"]["supply_chain_physical_poles_identified"] is False
    assert manifest["claims"]["closed_loop_stability_margin_established"] is False

    poles = pd.read_csv(output / "canonical_control_system_poles.csv")
    controller = poles.loc[poles["model"].eq("controller_v3_internal_memory")].iloc[0]
    assert controller["real"] == pytest.approx(0.82)
    assert bool(controller["publishable_as_physical_supply_chain_pole"]) is False
    physical = poles.loc[poles["model"].eq(PHYSICAL_CANDIDATE_MODEL)]
    assert not physical.empty
    assert physical["claim_status"].eq("rejected_exploratory_model").all()
    assert not physical["publishable_as_physical_supply_chain_pole"].astype(bool).any()

    zeros = pd.read_csv(output / "canonical_control_system_zeros.csv")
    assert zeros.iloc[0]["status"] == "not_computed_because_physical_model_is_rejected"
    report = (output / "canonical_control_system_report.md").read_text(
        encoding="utf-8"
    )
    assert "mémoire interne du régulateur V3" in report
    assert "REJETÉE" in report
    assert "ne sont pas utilisables pour conclure" in report
    assert "validation_repeats_the_same_periodic_phase" not in report
    assert "ce n'est pas un nouvel essai indépendant" in report
    pngs = sorted(output.glob("*.png"))
    assert len(pngs) == 11
    assert all(path.stat().st_size > 1_000 for path in pngs)

    dashboard = build_control_system_dashboard_section(output)
    assert dashboard["available"] is True
    assert dashboard["figure_count"] == 11
    assert dashboard["metrics"]["local_model_validated"] is False
    assert dashboard["metrics"]["validated_pole_count"] == 0
    assert dashboard["metrics"]["rejected_pole_count"] >= 1
    assert dashboard["metrics"]["exact_controller_pole_count"] == 1
    assert dashboard["metrics"]["local_stability_demonstrated"] is False
    assert "Exact pour le régulateur; pas un pôle physique" in dashboard["html"]
    assert "data:image/png;base64," in dashboard["html"]


def test_end_to_end_reads_post_feedback_additive_actuator_package(
    tmp_path: Path,
) -> None:
    v3_root = tmp_path / "v3"
    actuator_root = tmp_path / "actuator"
    output = tmp_path / "analysis"
    _write_v3_fixture(v3_root)
    _write_actuator_fixture(actuator_root, post_feedback_additive=True)

    result = run_control_system_analysis(v3_root, actuator_root, output)

    manifest = result["manifest"]
    excitation = manifest["experimental_actuator_excitation"]
    assert excitation["application_mode"] == "post_feedback_additive"
    assert excitation["closed_loop_probe"] is True
    assert excitation["rank"] == 3
    assert (
        manifest["physical_identification"]["source_campaign"]
        == "closed_loop_post_feedback_additive_actuator_probe"
    )
    assert manifest["physical_identification"]["accepted"] is False
    report = result["report_path"].read_text(encoding="utf-8")
    assert "actionneurs en boucle fermée" in report
    assert "rang des trois variations expérimentales séparées : 3" in report


def test_end_to_end_refuses_non_empty_output(tmp_path: Path) -> None:
    v3_root = tmp_path / "v3"
    actuator_root = tmp_path / "actuator"
    output = tmp_path / "analysis"
    _write_v3_fixture(v3_root)
    _write_actuator_fixture(actuator_root)
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")

    with pytest.raises(FileExistsError, match="non-empty"):
        run_control_system_analysis(v3_root, actuator_root, output)

    assert (output / "keep.txt").read_text(encoding="utf-8") == "user data"
