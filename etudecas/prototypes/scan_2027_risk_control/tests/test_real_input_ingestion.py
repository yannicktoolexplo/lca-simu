from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.calibration import (
    build_calibration_frame,
    calibrate_regime_thresholds,
    discover_calibration_files,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    aggregate_baseline_with_metadata,
    build_input_context,
    discover_baseline_file,
    discover_prediction_file,
    load_config,
    load_risk_series_with_metadata,
)


def canonical_daily(days: int = 40) -> pd.DataFrame:
    day = np.arange(days)
    return pd.DataFrame({
        "day": day,
        "demand": np.full(days, 100.0),
        "served": np.where(day % 9 == 0, 90.0, 100.0),
        "backlog_end": np.where(day % 9 == 0, 10.0, 0.0),
        "arrivals_qty": 95.0 + 5.0 * np.sin(day / 3.0),
        "produced_qty": 92.0 + 8.0 * np.cos(day / 4.0),
        "inventory_total": 420.0 + 35.0 * np.sin(day / 5.0),
        "external_procured_ordered_qty": 80.0 + (day % 4) * 10.0,
        "estimated_source_ordered_qty": np.full(days, 5.0),
    })


def granular_prediction() -> pd.DataFrame:
    return pd.DataFrame({
        "snapshot_date": ["2026-06-01", "2026-06-01"],
        "supplier_id": ["SUP-A", "SUP-B"],
        "factory_id": ["FACTORY-A", "FACTORY-B"],
        "item_id": ["item:A", "item:B"],
        "predicted_incident_probability_30d": [0.35, 0.65],
        "uncertainty_penalty": [0.1, 0.2],
        "lead_mean_days": [8.0, 12.0],
        "predicted_priority_score": [0.4, 0.8],
    })


class RealInputIngestionTests(unittest.TestCase):
    def test_canonical_daily_aliases_and_procurement_orders_are_consumed(self) -> None:
        daily, scale, metadata = aggregate_baseline_with_metadata(canonical_daily(12), 12)

        self.assertEqual(scale, 100.0)
        self.assertGreater(float(daily["backlog"].max()), 0.0)
        self.assertGreater(float(daily["arrivals"].min()), 0.0)
        self.assertGreater(float(daily["produced"].min()), 0.0)
        self.assertGreater(float(daily["inventory"].min()), 0.0)
        self.assertAlmostEqual(float(daily.loc[0, "orders"]), 0.85)
        self.assertEqual(metadata["signal_columns"]["backlog"], ["backlog_end"])
        self.assertEqual(metadata["signal_columns"]["arrivals"], ["arrivals_qty"])
        self.assertEqual(metadata["signal_columns"]["produced"], ["produced_qty"])
        self.assertEqual(metadata["signal_columns"]["inventory"], ["inventory_total"])
        self.assertEqual(
            metadata["signal_columns"]["orders"],
            ["external_procured_ordered_qty", "estimated_source_ordered_qty"],
        )
        self.assertEqual(
            metadata["orders_source"],
            "baseline_canonical_procurement_components",
        )
        self.assertNotIn("inventory", metadata["all_zero_signals"])

    def test_auto_discovery_prefers_baseline_and_supplier_item_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            risk_run = (
                root
                / "etudecas"
                / "simulation"
                / "result"
                / "scenario_runs"
                / "state_dependent_risk_test"
                / "data"
            )
            baseline_run = (
                root
                / "etudecas"
                / "simulation"
                / "result"
                / "campaign"
                / "replays"
                / "baseline"
                / "data"
            )
            risk_run.mkdir(parents=True)
            baseline_run.mkdir(parents=True)
            canonical_daily().to_csv(risk_run / "first_simulation_daily.csv", index=False)
            canonical_daily().to_csv(baseline_run / "first_simulation_daily.csv", index=False)

            prediction_root = root / "etudecas" / "prototypes" / "prediction" / "result"
            prediction_root.mkdir(parents=True)
            aggregate_path = prediction_root / "predicted_supplier_risk.csv"
            pd.DataFrame({
                "supplier_id": ["SUP-A"],
                "mean_predicted_incident_probability_30d": [0.42],
            }).to_csv(aggregate_path, index=False)
            granular_path = prediction_root / "predicted_supplier_item_risk.csv"
            granular_prediction().to_csv(granular_path, index=False)

            self.assertEqual(discover_baseline_file(root), baseline_run / "first_simulation_daily.csv")
            self.assertEqual(discover_prediction_file(root), granular_path)

            context = build_input_context(
                root,
                "auto",
                "auto",
                40,
                101,
                False,
                mapping_config=load_config(None)["physical_risk_mapping"],
            )
            self.assertEqual(Path(context.baseline_path or ""), baseline_run / "first_simulation_daily.csv")
            self.assertEqual(Path(context.risk_path or ""), granular_path)
            self.assertGreater(float(context.input_series["inventory"].min()), 0.0)
            self.assertGreater(float(context.input_series["orders"].min()), 0.0)
            self.assertEqual(
                context.prediction_interval_metadata["input_status"],
                "prediction_rows_consumed",
            )
            self.assertFalse(context.prediction_interval_metadata["fallback_used"])
            self.assertEqual(
                context.prediction_interval_metadata["probability_column"],
                "predicted_incident_probability_30d",
            )
            self.assertEqual(
                context.prediction_interval_metadata["prediction_granularity"],
                "supplier_item_destination",
            )
            self.assertEqual(
                context.prediction_interval_metadata["prediction_rows_used"],
                2,
            )
            self.assertEqual(
                context.baseline_ingestion_metadata["signal_columns"]["inventory"],
                ["inventory_total"],
            )

            _, _, aggregate_metadata = load_risk_series_with_metadata(
                aggregate_path, 10, 22
            )
            self.assertEqual(
                aggregate_metadata["probability_column"],
                "mean_predicted_incident_probability_30d",
            )
            self.assertEqual(aggregate_metadata["granularity"], "supplier_aggregate")
            self.assertFalse(aggregate_metadata["fallback_used"])

    def test_synthetic_risk_fallback_is_explicit_in_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = build_input_context(
                Path(tmp),
                "auto",
                "auto",
                28,
                17,
                True,
                mapping_config=load_config(None)["physical_risk_mapping"],
            )
        metadata = context.prediction_interval_metadata
        self.assertEqual(metadata["input_status"], "fallback_consumed")
        self.assertTrue(metadata["fallback_used"])
        self.assertEqual(metadata["fallback_reason"], "prediction_file_not_found")
        self.assertIsNone(metadata["probability_column"])
        self.assertEqual(
            metadata["risk_series_ingestion"]["input_status"],
            "synthetic_risk_fallback",
        )
        self.assertEqual(
            context.baseline_ingestion_metadata["input_status"],
            "synthetic_baseline_fallback",
        )

    def test_real_artifact_names_feed_calibration_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = (
                root
                / "etudecas"
                / "simulation"
                / "result"
                / "reference"
                / "replays"
                / "baseline"
                / "data"
            )
            data_dir.mkdir(parents=True)
            canonical_daily().to_csv(data_dir / "first_simulation_daily.csv", index=False)
            days = np.arange(40)
            pd.DataFrame({
                "day": days,
                "node_id": "FACTORY-A",
                "output_item_id": "item:FG",
                "shortfall_vs_desired_qty": np.where(days % 8 == 0, 5.0, 0.0),
            }).to_csv(data_dir / "production_constraint_daily.csv", index=False)
            pd.DataFrame({
                "day": days,
                "node_id": "SUP-A",
                "item_id": "item:A",
                "utilization": 0.70 + 0.25 * (days % 10 == 0),
            }).to_csv(data_dir / "production_supplier_capacity_daily.csv", index=False)
            pd.DataFrame({
                "event_id": ["EV-1"],
                "trigger_day": [4],
                "start_day": [5],
                "end_day": [10],
                "supplier_id": ["SUP-A"],
                "item_id": ["item:A"],
                "risk_type": ["capacity"],
                "multiplier": [0.8],
            }).to_csv(data_dir / "supplier_state_dependent_risk_events.csv", index=False)
            pd.DataFrame({
                "day": [5],
                "supplier_id": ["SUP-A"],
                "item_id": ["item:A"],
                "capacity_multiplier": [0.75],
            }).to_csv(data_dir / "supplier_risk_events_applied_daily.csv", index=False)
            pd.DataFrame({
                "node_id": ["FACTORY-A"],
                "output_item_id": ["item:FG"],
                "actual_churn_ratio": [0.35],
                "nervousness_level": ["medium"],
            }).to_csv(data_dir / "production_factory_nervousness.csv", index=False)
            pd.DataFrame({
                "day": days,
                "node_id": "FACTORY-A",
                "item_id": "item:A",
                "stock_end_of_day": 200.0 - 2.0 * days,
            }).to_csv(data_dir / "production_input_stocks_daily.csv", index=False)
            pd.DataFrame({
                "day": days,
                "node_id": "FACTORY-A",
                "item_id": "item:A",
                "consumed_qty": np.full(40, 10.0),
            }).to_csv(data_dir / "production_input_consumption_daily.csv", index=False)
            pd.DataFrame({
                "day": days,
                "node_id": "CUSTOMER",
                "item_id": "item:FG",
                "demand_qty": 100.0,
                "served_qty": 100.0,
                "backlog_end_qty": 0.0,
            }).to_csv(data_dir / "production_demand_service_daily.csv", index=False)

            prediction_root = root / "etudecas" / "prototypes" / "prediction" / "result"
            prediction_root.mkdir(parents=True)
            granular_prediction().to_csv(
                prediction_root / "predicted_supplier_item_risk.csv", index=False
            )
            context = build_input_context(
                root,
                "auto",
                "auto",
                40,
                101,
                False,
                mapping_config=load_config(None)["physical_risk_mapping"],
            )
            discovered = discover_calibration_files(context)
            self.assertEqual(
                set(discovered),
                {
                    "constraints",
                    "supplier_capacity",
                    "state_risk_events",
                    "factory_nervousness",
                    "supplier_risk_applied",
                    "input_stocks",
                    "input_consumption",
                    "demand_service",
                },
            )
            frame, _ = build_calibration_frame(context)
            self.assertGreater(float(frame["supplier_utilization"].max()), 0.9)
            self.assertGreater(float(frame["state_risk_event_count"].max()), 0.0)
            self.assertGreater(float(frame["applied_risk_severity"].max()), 0.0)
            self.assertEqual(
                set(frame["material_cover_source"]),
                {"pair_level_input_stock_and_consumption"},
            )

    def test_missing_signals_keep_threshold_defaults(self) -> None:
        config = load_config(None)
        days = 30
        frame = pd.DataFrame({
            "service": np.ones(days),
            "backlog_days": np.zeros(days),
            "backlog_delta": np.zeros(days),
            "inventory_cover_days": np.zeros(days),
            "material_cover_days": np.zeros(days),
            "production_utilization": np.zeros(days),
            "supplier_utilization": np.zeros(days),
            "constraint_activity": np.zeros(days),
            "base_risk": np.full(days, 0.1),
            "calibration_risk_signal": np.full(days, 0.1),
            "forecast_risk_is_dynamic": np.zeros(days),
            "state_risk_event_count": np.zeros(days),
            "nervousness": np.zeros(days),
            "oscillation_index": np.zeros(days),
        })
        calibrated, evidence = calibrate_regime_thresholds(frame, config)

        for threshold in (
            "material_tension_days",
            "capacity_saturation",
            "oscillation_nervousness",
            "crisis_backlog_days",
            "recovery_backlog_days",
            "overstock_days",
        ):
            self.assertEqual(
                calibrated[threshold],
                config["regime_thresholds"][threshold],
            )
            row = evidence.loc[evidence["threshold"] == threshold].iloc[0]
            self.assertEqual(row["signal_status"], "insufficient_signal")
        self.assertEqual(
            int(
                evidence.loc[
                    evidence["threshold"] == "capacity_saturation", "anchor_days"
                ].iloc[0]
            ),
            0,
        )
        self.assertEqual(
            int(
                evidence.loc[
                    evidence["threshold"] == "oscillation_nervousness",
                    "anchor_days",
                ].iloc[0]
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
