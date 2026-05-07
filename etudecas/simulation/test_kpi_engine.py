from __future__ import annotations

import math
import unittest

from etudecas.simulation.kpi_engine import (
    DEFAULT_PHYSICS_KPI_DEFINITIONS,
    KpiDefinition,
    compute_kpi_rows,
    normalized_distance,
    weighted_euclidean_score,
    build_observations,
)


class KpiEngineTest(unittest.TestCase):
    def test_normalized_distance_higher_is_better(self) -> None:
        distance = normalized_distance(0.84, 0.98, 0.70, "higher_is_better")
        self.assertAlmostEqual(distance, 0.5)
        self.assertEqual(normalized_distance(1.0, 0.98, 0.70, "higher_is_better"), 0.0)
        self.assertEqual(normalized_distance(0.60, 0.98, 0.70, "higher_is_better"), 1.0)

    def test_normalized_distance_lower_is_better(self) -> None:
        distance = normalized_distance(22.5, 5.0, 40.0, "lower_is_better")
        self.assertAlmostEqual(distance, 0.5)
        self.assertEqual(normalized_distance(1.0, 5.0, 40.0, "lower_is_better"), 0.0)
        self.assertEqual(normalized_distance(50.0, 5.0, 40.0, "lower_is_better"), 1.0)

    def test_weighted_euclidean_score(self) -> None:
        definitions = [
            KpiDefinition("product_availability", 0.98, 0.70, "higher_is_better"),
            KpiDefinition("line_nervousness", 5.0, 40.0, "lower_is_better"),
        ]
        observations = build_observations(
            definitions,
            {
                "product_availability": 0.84,
                "line_nervousness": 22.5,
            },
        )
        self.assertAlmostEqual(weighted_euclidean_score(observations), 0.5)

    def test_default_physics_kpis_compute_rows(self) -> None:
        names = {definition.name for definition in DEFAULT_PHYSICS_KPI_DEFINITIONS}
        self.assertEqual(
            names,
            {
                "product_availability",
                "line_adherence",
                "line_nervousness",
                "production_replanning_count",
                "raw_material_stockout_days",
                "material_delay_days",
                "inventory_cost",
            },
        )
        rows = compute_kpi_rows(
            [0],
            {
                "product_availability": {0: 0.98},
                "line_adherence": {0: 0.95},
                "line_nervousness": {0: 5.0},
                "production_replanning_count": {0: 2.0},
                "raw_material_stockout_days": {0: 0.0},
                "material_delay_days": {0: 0.0},
                "inventory_cost": {0: 1.0},
            },
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(math.isclose(rows[0]["global_score"], 0.0))
        self.assertTrue(math.isclose(rows[0]["health_score"], 1.0))
        self.assertNotIn("performance_score", rows[0])


if __name__ == "__main__":
    unittest.main()
