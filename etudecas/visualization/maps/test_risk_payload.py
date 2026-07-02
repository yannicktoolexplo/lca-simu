from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
import unittest

from etudecas.visualization.maps.risk_payload import (
    build_supplier_risk_campaign_payload,
    supplier_risk_campaign_status,
)


class RiskPayloadTest(unittest.TestCase):
    def test_supplier_risk_campaign_payload_builds_node_assets_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_json = root / "summary.json"
            summary_csv = root / "summary.csv"
            cases_csv = root / "cases.csv"
            summary_json.write_text(
                json.dumps({"metadata": {"days": 60, "case_count": 2, "families": ["stock"]}}),
                encoding="utf-8",
            )
            with summary_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "supplier_id",
                        "worst_score_decisionnel_modele",
                        "worst_impact_metier_score",
                        "worst_risk_family",
                        "worst_risk_family_label",
                        "worst_impact_metier_kpi",
                        "worst_impact_metier_delta",
                        "tested_family_count",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "supplier_id": "S-1",
                        "worst_score_decisionnel_modele": "0.08",
                        "worst_impact_metier_score": "0.12",
                        "worst_risk_family": "stock",
                        "worst_risk_family_label": "Stock",
                        "worst_impact_metier_kpi": "backlog",
                        "worst_impact_metier_delta": "+10",
                        "tested_family_count": "1",
                    }
                )
            with cases_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "supplier_id",
                        "risk_family",
                        "risk_family_label",
                        "score_decisionnel_modele",
                        "impact_metier_score",
                        "fill_rate",
                        "product_availability",
                        "line_adherence",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "supplier_id": "S-1",
                        "risk_family": "stock",
                        "risk_family_label": "Stock",
                        "score_decisionnel_modele": "0.08",
                        "impact_metier_score": "0.12",
                        "fill_rate": "0.91",
                        "product_availability": "0.90",
                        "line_adherence": "0.89",
                    }
                )

            payload = build_supplier_risk_campaign_payload(summary_json, summary_csv, cases_csv)

        self.assertTrue(payload["available"])
        self.assertEqual(payload["global"]["supplier_count"], 1)
        self.assertEqual(payload["nodes"]["S-1"]["status"], "sensitive")
        self.assertIn("stress tests fournisseurs", payload["nodes"]["S-1"]["asset"]["html"])

    def test_supplier_risk_campaign_status_thresholds(self) -> None:
        self.assertEqual(supplier_risk_campaign_status(0.0)[0], "not_local")
        self.assertEqual(supplier_risk_campaign_status(0.01)[0], "robust")
        self.assertEqual(supplier_risk_campaign_status(0.03)[0], "watch")
        self.assertEqual(supplier_risk_campaign_status(0.06)[0], "sensitive")


if __name__ == "__main__":
    unittest.main()
