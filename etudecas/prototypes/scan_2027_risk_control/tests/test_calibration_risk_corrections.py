from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.calibration import (
    apply_calibrated_regime_labels,
    build_calibration_frame,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    build_input_context,
    load_config,
)
from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_canonical_risk_events,
    build_granular_prediction_interval_envelope,
    build_prediction_interval_envelope,
    map_prediction_interval_to_physical,
    physical_mapping_coefficient_sensitivity,
)


def _canonical_daily(days: int) -> pd.DataFrame:
    return pd.DataFrame({
        "day": np.arange(days),
        "demand": np.full(days, 100.0),
        "served": np.full(days, 100.0),
        "backlog_end": np.zeros(days),
        "arrivals_qty": np.full(days, 100.0),
        "produced_qty": np.full(days, 100.0),
        "inventory_total": np.full(days, 500.0),
        "external_procured_ordered_qty": np.full(days, 100.0),
    })


class CalibrationRiskCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(None)

    def test_material_cover_is_derived_from_canonical_stock_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "baseline" / "data"
            data_dir.mkdir(parents=True)
            baseline = data_dir / "first_simulation_daily.csv"
            _canonical_daily(40).to_csv(baseline, index=False)
            pd.DataFrame({
                "day": np.arange(40),
                "node_id": "FACTORY",
                "item_id": "item:RAW",
                "stock_before_production": np.full(40, 100.0),
                "stock_end_of_day": np.full(40, 90.0),
            }).to_csv(data_dir / "production_input_stocks_daily.csv", index=False)
            pd.DataFrame({
                "day": [5, 6],
                "node_id": ["FACTORY", "FACTORY"],
                "output_item_id": ["item:FG", "item:FG"],
                "shortfall_vs_desired_qty": [0.0, 4.0],
                "binding_cause": ["input_shortage", "none"],
            }).to_csv(data_dir / "production_constraint_daily.csv", index=False)
            context = build_input_context(
                Path(tmp),
                str(baseline),
                "auto",
                40,
                9,
                False,
                mapping_config=self.config["physical_risk_mapping"],
            )
            frame, _ = build_calibration_frame(context)

        self.assertEqual(
            set(frame["material_cover_source"]),
            {"pair_level_input_stock_implied_consumption"},
        )
        self.assertAlmostEqual(float(frame["material_cover_days"].median()), 9.0)
        self.assertGreater(float(frame.loc[frame["day"] == 5, "constraint_activity"].iloc[0]), 0.0)
        self.assertGreater(float(frame.loc[frame["day"] == 6, "constraint_activity"].iloc[0]), 0.0)

    def test_overstock_requires_inventory_uplift_after_disruption(self) -> None:
        thresholds = self.config["regime_thresholds"]
        base = pd.DataFrame({
            "backlog_days": [0.0, 0.0],
            "inventory_cover_days": [100.0, 100.0],
            "material_cover_days": [10.0, 10.0],
            "production_utilization": [0.2, 0.2],
            "supplier_utilization": [0.2, 0.2],
            "base_risk": [0.0, 0.0],
            "supplier_stress_proxy": [0.0, 0.0],
            "nervousness": [0.0, 0.0],
            "service": [1.0, 1.0],
            "inventory_excess_ratio": [2.0, 2.0],
            "recent_disruption_signal": [0.0, 1.0],
        })
        labeled = apply_calibrated_regime_labels(base, thresholds)
        self.assertEqual(labeled.loc[0, "calibrated_regime"], "NOMINAL")
        self.assertEqual(
            labeled.loc[1, "calibrated_regime"], "POST_CRISIS_OVERSTOCK"
        )

    def test_granular_intervals_and_residual_coverage_are_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prediction_path = root / "predicted_supplier_item_risk.csv"
            pd.DataFrame({
                "snapshot_date": ["2026-06-01", "2026-06-01"],
                "supplier_id": ["SUP-A", "SUP-B"],
                "factory_id": ["FAC-A", "FAC-B"],
                "item_id": ["item:A", "item:B"],
                "predicted_incident_probability_30d": [0.30, 0.70],
                "uncertainty_penalty": [0.0, 0.0],
                "lead_mean_days": [8.0, 12.0],
                "predicted_priority_score": [0.4, 0.8],
            }).to_csv(prediction_path, index=False)
            pd.DataFrame({
                "predicted_incident_probability_30d": np.full(20, 0.20),
                "incident_next_30d": np.zeros(20),
            }).to_csv(root / "prediction_test_scored_rows.csv", index=False)

            portfolio, metadata = build_prediction_interval_envelope(
                prediction_path,
                70,
                mapping_config=self.config["physical_risk_mapping"],
            )
            granular = build_granular_prediction_interval_envelope(
                prediction_path,
                70,
                mapping_config=self.config["physical_risk_mapping"],
            )

        self.assertEqual(metadata.residual_quantile, 0.20)
        self.assertEqual(metadata.effective_interval_half_width, 0.20)
        self.assertEqual(metadata.empirical_calibration_coverage, 1.0)
        self.assertEqual(metadata.calibration_coverage_rows, 20)
        self.assertEqual(len(granular), 140)
        self.assertEqual(
            granular[
                ["supplier_id", "item_id", "dst_node_id"]
            ].drop_duplicates().shape[0],
            2,
        )
        self.assertEqual(set(granular["scope"]), {"supplier_item_destination"})
        for _, group in granular.groupby(
            ["supplier_id", "item_id", "dst_node_id"]
        ):
            after_validity = group.loc[group["day"] >= 30, "risk_interval_span"]
            self.assertTrue((after_validity.diff().dropna() >= -1e-12).all())
            self.assertGreater(
                float(group.loc[group["day"] == 69, "risk_interval_span"].iloc[0]),
                float(group.loc[group["day"] == 30, "risk_interval_span"].iloc[0]),
            )
        self.assertLess(
            abs(float(portfolio.loc[69, "risk_center"]) - 0.12),
            abs(float(portfolio.loc[30, "risk_center"]) - 0.12),
        )

    def test_mapping_coefficient_sensitivity_has_expected_direction(self) -> None:
        envelope = pd.DataFrame({
            "day": [0, 1],
            "risk_lower": [0.2, 0.2],
            "risk_center": [0.5, 0.5],
            "risk_upper": [0.8, 0.8],
            "conditional_backlog_if_incident": [20.0, 20.0],
            "conditional_fill_loss_if_incident": [0.02, 0.02],
            "lead_mean_days": [10.0, 10.0],
            "priority_score": [1.0, 1.0],
            "source_pairs": [1, 1],
        })
        sensitivity = physical_mapping_coefficient_sensitivity(
            envelope,
            self.config["physical_risk_mapping"],
            factors=(0.5, 1.0, 1.5),
        )
        availability = sensitivity.loc[
            (sensitivity["coefficient"] == "availability_loss_at_unit_risk")
            & (sensitivity["interval_side"] == "center")
        ].sort_values("factor")
        lead = sensitivity.loc[
            (
                sensitivity["coefficient"]
                == "lead_extra_fraction_of_nominal_at_unit_risk"
            )
            & (sensitivity["interval_side"] == "center")
        ].sort_values("factor")
        self.assertTrue(
            availability["perturbed_mean_physical_value"].is_monotonic_decreasing
        )
        self.assertTrue(
            lead["perturbed_mean_physical_value"].is_monotonic_increasing
        )
        with self.assertRaises(ValueError):
            physical_mapping_coefficient_sensitivity(
                envelope,
                self.config["physical_risk_mapping"],
                factors=(0.0,),
            )

    def test_canonical_mapping_prefers_pair_specific_physical_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prediction_path = Path(tmp) / "prediction.csv"
            pd.DataFrame({
                "snapshot_date": ["2026-06-01", "2026-06-01"],
                "supplier_id": ["SUP-A", "SUP-B"],
                "factory_id": ["FAC-A", "FAC-B"],
                "item_id": ["item:A", "item:B"],
                "predicted_incident_probability_30d": [0.8, 0.6],
                "predicted_priority_score": [0.9, 0.8],
            }).to_csv(prediction_path, index=False)
            granular = pd.DataFrame({
                "scope": ["supplier_item_destination"] * 4,
                "day": [0, 1, 0, 1],
                "supplier_id": ["SUP-A", "SUP-A", "SUP-B", "SUP-B"],
                "item_id": ["item:A", "item:A", "item:B", "item:B"],
                "dst_node_id": ["FAC-A", "FAC-A", "FAC-B", "FAC-B"],
                "risk_lower": [0.2, 0.2, 0.1, 0.1],
                "risk_center": [0.6, 0.6, 0.3, 0.3],
                "risk_upper": [0.9, 0.9, 0.4, 0.4],
                "conditional_backlog_if_incident": [20.0] * 4,
                "conditional_fill_loss_if_incident": [0.02] * 4,
                "lead_mean_days": [10.0] * 4,
                "priority_score": [1.0] * 4,
                "source_pairs": [1] * 4,
            })
            physical = map_prediction_interval_to_physical(
                granular, self.config["physical_risk_mapping"]
            )
            _, ledger = build_canonical_risk_events(
                prediction_path,
                physical,
                days=2,
                top_pairs=2,
                prediction_horizon_days=2,
            )

        self.assertFalse(ledger.empty)
        self.assertEqual(
            set(ledger["physical_envelope_scope"]),
            {"supplier_item_destination"},
        )
        availability = ledger.loc[
            ledger["risk_type"] == "availability"
        ].set_index("supplier_id")
        self.assertLess(
            float(availability.loc["SUP-A", "raw_physical_value"]),
            float(availability.loc["SUP-B", "raw_physical_value"]),
        )

    def test_canonical_mapping_filters_and_refills_graph_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prediction_path = Path(tmp) / "prediction.csv"
            suppliers = ["SUP-1", "SUP-2", "SUP-3", "SUP-4"]
            items = ["item:1", "item:2", "item:3", "item:4"]
            pd.DataFrame({
                "snapshot_date": ["2026-06-01"] * 4,
                "supplier_id": suppliers,
                "factory_id": ["FACTORY"] * 4,
                "item_id": items,
                "predicted_incident_probability_30d": [0.8] * 4,
                "predicted_priority_score": [1.0, 0.9, 0.8, 0.7],
            }).to_csv(prediction_path, index=False)
            granular = pd.DataFrame([
                {
                    "scope": "supplier_item_destination",
                    "day": day,
                    "supplier_id": supplier,
                    "item_id": item,
                    "dst_node_id": "FACTORY",
                    "risk_lower": 0.5,
                    "risk_center": 0.7,
                    "risk_upper": 0.9,
                    "conditional_backlog_if_incident": 20.0,
                    "conditional_fill_loss_if_incident": 0.02,
                    "lead_mean_days": 10.0,
                    "priority_score": 1.0,
                    "source_pairs": 1,
                }
                for supplier, item in zip(suppliers, items)
                for day in range(2)
            ])
            physical = map_prediction_interval_to_physical(
                granular, self.config["physical_risk_mapping"]
            )
            graph = {
                "edges": [
                    {
                        "id": f"edge:{supplier}",
                        "from": supplier,
                        "to": "FACTORY",
                        "items": [item],
                    }
                    for supplier, item in zip(
                        ["SUP-1", "SUP-3", "SUP-4"],
                        ["item:1", "item:3", "item:4"],
                    )
                ]
            }
            events, ledger = build_canonical_risk_events(
                prediction_path,
                physical,
                days=2,
                top_pairs=3,
                prediction_horizon_days=2,
                canonical_graph=graph,
            )

        selected = ledger.loc[
            ledger["selection_status"].eq("selected_graph_compatible")
        ]
        rejected = ledger.loc[
            ledger["selection_status"].eq("rejected_graph_unmatched")
        ]
        self.assertEqual(
            set(events["supplier_id"]),
            {"SUP-1", "SUP-3", "SUP-4"},
        )
        self.assertTrue(events["edge_id"].astype(str).str.len().gt(0).all())
        self.assertEqual(
            set(selected["graph_match_status"]),
            {"matched"},
        )
        self.assertEqual(set(rejected["supplier_id"]), {"SUP-2"})
        self.assertEqual(
            set(rejected["mapping_status"]),
            {"not_applied_graph_lane_unmatched"},
        )


if __name__ == "__main__":
    unittest.main()
