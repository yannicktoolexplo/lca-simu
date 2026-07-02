from __future__ import annotations

import unittest

from etudecas.visualization.maps.supplier_risk_formatting import (
    risk_pct,
    risk_ratio,
    supplier_risk_action_label,
    supplier_risk_worst_zone,
    supplier_risk_zone_color,
    supplier_risk_zone_counts_text,
    supplier_risk_zone_label,
    supplier_risk_zone_rank,
)


class SupplierRiskFormattingTest(unittest.TestCase):
    def test_ratio_and_percent_are_clamped(self) -> None:
        self.assertEqual(risk_ratio(None), 0.0)
        self.assertEqual(risk_ratio("-1"), 0.0)
        self.assertEqual(risk_ratio("1.7"), 1.0)
        self.assertEqual(risk_pct("0.123", digits=1), "12.3%")

    def test_zone_rank_label_and_color(self) -> None:
        self.assertEqual(supplier_risk_zone_rank("vert"), 0)
        self.assertEqual(supplier_risk_zone_rank("orange"), 2)
        self.assertEqual(supplier_risk_zone_rank("critical"), 4)
        self.assertEqual(supplier_risk_zone_label("rouge"), "Critique")
        self.assertEqual(supplier_risk_zone_label("jaune"), "Modere")
        self.assertEqual(supplier_risk_zone_color("orange"), "#d97706")

    def test_worst_zone_and_counts_text(self) -> None:
        rows = [{"decision_zone": "vert"}, {"decision_zone": "orange"}, {"decision_zone": "jaune"}]
        self.assertEqual(supplier_risk_worst_zone(rows), "orange")
        self.assertEqual(
            supplier_risk_zone_counts_text({"vert": 2, "orange": 1, "custom": 3}),
            "orange=1, vert=2, custom=3",
        )

    def test_action_label(self) -> None:
        self.assertEqual(supplier_risk_action_label("routine_monitoring"), "surveillance de routine")
        self.assertEqual(supplier_risk_action_label("manual_review"), "manual_review")


if __name__ == "__main__":
    unittest.main()

