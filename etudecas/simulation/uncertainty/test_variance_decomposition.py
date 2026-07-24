import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from etudecas.simulation.uncertainty.variance_decomposition import (
    build_variance_decomposition,
    factor_family,
)


class VarianceDecompositionTests(unittest.TestCase):
    @staticmethod
    def _write_samples(directory: str, rows: list[dict[str, object]]) -> Path:
        path = Path(directory) / "montecarlo_samples.csv"
        columns = sorted({column for row in rows for column in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_allocates_predictive_share_by_family_and_excludes_systemic_reliability(self) -> None:
        rng = np.random.default_rng(1234)
        rows: list[dict[str, object]] = [
            {
                "run_id": "baseline",
                "status": "ok",
                "is_baseline": True,
                "factor::demand_scale": 1.0,
                "supplier_capacity_node::S1": 1.0,
                "factor::supplier_reliability_scale": 1.0,
                "kpi::total_cost": 100.0,
            },
            {
                "run_id": "failed",
                "status": "error",
                "is_baseline": False,
                "factor::demand_scale": 99.0,
                "supplier_capacity_node::S1": 99.0,
                "factor::supplier_reliability_scale": 99.0,
                "kpi::total_cost": 1e12,
            },
        ]
        for index in range(180):
            demand = float(rng.normal())
            capacity = float(rng.normal())
            noise = float(rng.normal(scale=0.3))
            rows.append(
                {
                    "run_id": f"run_{index:04d}",
                    "status": "ok",
                    "is_baseline": False,
                    "factor::demand_scale": 1.0 + 0.15 * demand,
                    "supplier_capacity_node::S1": 1.0 + 0.15 * capacity,
                    # Deliberately predictive but forbidden from attribution.
                    "factor::supplier_reliability_scale": 1.0 + 0.15 * demand,
                    "kpi::total_cost": 100.0 + 30.0 * demand + 4.0 * capacity + noise,
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_samples(tmp, rows)
            payload = build_variance_decomposition(
                path,
                kpis=["kpi::total_cost"],
                n_splits=5,
                permutation_repeats=8,
                random_seed=7,
            )

        result = payload["kpis"]["kpi::total_cost"]
        families = {row["family"]: row for row in result["families"]}
        self.assertEqual(payload["source"]["stochastic_success_count"], 180)
        self.assertEqual(payload["source"]["baseline_excluded_count"], 1)
        self.assertEqual(payload["source"]["failed_excluded_count"], 1)
        self.assertFalse(payload["method"]["is_sobol"])
        self.assertGreater(result["oos_r2"], 0.95)
        self.assertGreater(
            families["demand"]["explained_variance_share"],
            families["supplier_capacity"]["explained_variance_share"],
        )
        self.assertNotIn(
            "factor::supplier_reliability_scale",
            {factor for family in payload["factor_families"].values() for factor in family["factors"]},
        )
        allocated = sum(row["explained_variance_share"] for row in result["families"])
        allocated += result["residual_interactions_unexplained_share"]
        self.assertAlmostEqual(allocated, 1.0, places=10)
        json.dumps(payload, allow_nan=False)

    def test_interaction_only_signal_remains_in_explicit_residual(self) -> None:
        rng = np.random.default_rng(321)
        rows: list[dict[str, object]] = []
        for index in range(200):
            demand = float(rng.normal())
            capacity = float(rng.normal())
            rows.append(
                {
                    "run_id": f"run_{index:04d}",
                    "status": "ok",
                    "is_baseline": False,
                    "factor::demand_scale": demand,
                    "supplier_capacity_node::S1": capacity,
                    "kpi::ending_backlog": demand * capacity,
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_samples(tmp, rows)
            payload = build_variance_decomposition(
                path,
                kpis=["kpi::ending_backlog"],
                n_splits=5,
                permutation_repeats=5,
                random_seed=19,
            )

        result = payload["kpis"]["kpi::ending_backlog"]
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["residual_interactions_unexplained_share"], 0.8)
        self.assertIn("Interactions", payload["method"]["residual_definition"])

    def test_factor_family_keeps_local_reliability_only(self) -> None:
        self.assertIsNone(factor_family("factor::supplier_reliability_scale"))
        self.assertEqual(
            factor_family("supplier_reliability_node::SDC-1"),
            "supplier_reliability",
        )
        self.assertEqual(
            factor_family("factor::external_procurement_transport_cost_scale"),
            "external_supply_cost",
        )


if __name__ == "__main__":
    unittest.main()
