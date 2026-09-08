from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.calibration import (
    calibrate_from_context,
    calibrate_nominal_parameters,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    DEFAULT_ACTIONS,
    build_input_context,
    load_config,
)
from etudecas.prototypes.scan_2027_risk_control.experiments import (
    forecast_confusion_experiment,
    paired_policy_experiment,
)


def _aggregate_frame(days: int = 40) -> pd.DataFrame:
    demand = np.full(days, 1.0)
    return pd.DataFrame(
        {
            "demand": demand,
            "service": np.ones(days),
            "backlog_days": np.zeros(days),
            "nervousness": np.zeros(days),
            "inventory_cover_days": np.full(days, 120.0),
            "arrivals": np.full(days, 50.0),
            "produced": np.full(days, 40.0),
        }
    )


def test_aggregate_cross_item_totals_do_not_refit_nominal_parameters_by_default() -> None:
    config = load_config(None)
    declared = dict(config["nominal"])

    retained = calibrate_nominal_parameters(_aggregate_frame(), config)
    candidate = calibrate_nominal_parameters(
        _aggregate_frame(),
        config,
        allow_aggregate_refit=True,
    )

    assert retained == declared
    assert candidate["raw_inventory_days"] == 20.0
    assert candidate["finished_inventory_days"] == 10.0
    assert candidate["supplier_capacity_ratio"] == 3.0
    assert candidate["production_capacity_ratio"] == 3.0


def test_etudecas_baseline_retains_declared_nominal_model_and_exercises_service() -> None:
    config = load_config(None)
    config["controller_scenarios"] = 2
    config["policy_comparison_scenarios"] = 2
    config["controller_horizon_days"] = 7
    synthetic = build_input_context(
        Path.cwd(),
        "auto",
        "auto",
        70,
        101,
        True,
        mapping_config=config["physical_risk_mapping"],
    )
    etudecas_context = replace(
        synthetic,
        source_mode="etudecas_baseline",
        baseline_path="simulated_case_daily.csv",
        baseline_ingestion_metadata={
            "input_status": "etudecas_baseline_consumed",
        },
    )

    calibration = calibrate_from_context(etudecas_context, config)
    nominal_audit = calibration.metadata["nominal_parameter_calibration"]

    assert calibration.config["nominal"] == config["nominal"]
    assert nominal_audit["refit_applied"] is False
    assert (
        nominal_audit["unit_comparability"]
        == "not_established_across_items_and_bom_levels"
    )
    assert nominal_audit["candidate_status"] == "diagnostic_only_not_applied"

    paired_runs, _ = paired_policy_experiment(
        etudecas_context,
        calibration.config,
        DEFAULT_ACTIONS,
        [81],
    )
    assert (paired_runs["service_loss"] > 0.0).any()
    assert (paired_runs["backlog_area"] > 0.0).any()
    mrp = paired_runs.loc[paired_runs["policy"] == "mrp_reference"].iloc[0]
    assert float(mrp["service_loss"]) > 0.0
    assert float(mrp["backlog_area"]) > 0.0

    runs, _, _ = forecast_confusion_experiment(
        etudecas_context,
        calibration.config,
        DEFAULT_ACTIONS,
        [91],
        start_day=8,
        duration_days=42,
        incident_duration_days=42,
        forecast_signal_duration_days=42,
    )
    incident_rows = runs.loc[runs["truth_event"].astype(bool)]
    assert float(incident_rows["service_loss"].max()) > 0.0
    assert float(incident_rows["backlog_area"].max()) > 0.0
    by_case = runs.set_index("case")
    assert float(by_case.loc["FN", "mrp_service_loss"]) > float(
        by_case.loc["TN", "mrp_service_loss"]
    )
    assert float(by_case.loc["FN", "mrp_backlog_area"]) > float(
        by_case.loc["TN", "mrp_backlog_area"]
    )


def test_synthetic_reduced_model_permits_normalized_internal_refit() -> None:
    config = load_config(None)
    context = build_input_context(
        Path.cwd(),
        "auto",
        "auto",
        40,
        101,
        True,
        mapping_config=config["physical_risk_mapping"],
    )

    calibration = calibrate_from_context(context, config)
    nominal_audit = calibration.metadata["nominal_parameter_calibration"]

    assert context.source_mode == "synthetic_fallback"
    assert nominal_audit["refit_applied"] is True
    assert nominal_audit["candidate_status"] == "applied"
    assert (
        nominal_audit["unit_comparability"]
        == "normalized_synthetic_reduced_model_unit"
    )
    assert (
        calibration.config["nominal"]
        == nominal_audit["aggregate_refit_candidate"]
    )
