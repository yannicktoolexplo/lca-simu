from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etudecas.knowledge_graph.enrichers import enrich_graph_from_excel
from etudecas.knowledge_graph.excel_io import read_xlsx
from etudecas.knowledge_graph.excel_template import write_excel_template


class ExcelEnrichmentTest(unittest.TestCase):
    def test_template_roundtrip_and_enrichment(self) -> None:
        graph = {
            "nodes": [{"id": "S-1", "type": "supplier_dc"}, {"id": "M-1", "type": "factory"}],
            "edges": [{"id": "edge:S-1_TO_M-1", "from": "S-1", "to": "M-1", "items": ["item:A"]}],
            "items": [{"id": "item:A", "uom": "KG"}],
            "scenarios": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            workbook = Path(tmp) / "enrichment.xlsx"
            write_excel_template(workbook, graph)
            rows = read_xlsx(workbook)

        self.assertIn("nodes", rows)
        self.assertEqual(rows["nodes"][0]["id"], "S-1")
        self.assertEqual(rows["edges"][0]["item_ids"], "item:A")

    def test_apply_excel_updates_graph_contract(self) -> None:
        graph = {"nodes": [], "edges": [], "items": [], "scenarios": []}
        with tempfile.TemporaryDirectory() as tmp:
            workbook = Path(tmp) / "enrichment.xlsx"
            sheets = {
                "README": [],
                "nodes": [
                    {"id": "S-1", "type": "supplier_dc", "name": "Supplier"},
                    {"id": "M-1", "type": "factory", "name": "Factory"},
                ],
                "items": [{"item_id": "A", "uom": "KG"}],
                "edges": [
                    {
                        "from": "S-1",
                        "to": "M-1",
                        "item_ids": "A",
                        "lead_time_days": 3,
                        "quantity_unit": "KG",
                        "standard_order_qty": 100,
                    }
                ],
                "bom": [
                    {
                        "node_id": "M-1",
                        "output_item_id": "PF",
                        "input_item_id": "A",
                        "batch_size": 10,
                        "ratio_per_batch": 2,
                        "ratio_unit": "KG",
                    }
                ],
                "initial_inventory": [{"node_id": "M-1", "item_id": "A", "quantity": 50, "uom": "KG"}],
                "demand": [{"scenario_id": "base", "customer_id": "C-1", "item_id": "PF", "day": 0, "quantity": 10}],
                "risks": [],
                "logistics": [{"item_id": "PF", "units_per_case": 125}],
                "case_config": [{"section": "node_aliases", "key": "D-1", "value_json": '"S-1"'}],
            }
            from etudecas.knowledge_graph.excel_io import write_xlsx
            from etudecas.knowledge_graph.excel_template import EXCEL_COLUMNS

            write_xlsx(workbook, sheets, EXCEL_COLUMNS)
            enriched, report = enrich_graph_from_excel(graph, workbook)

        self.assertFalse([issue for issue in report["issues"] if issue["level"] == "error"])
        self.assertEqual(enriched["nodes"][0]["id"], "S-1")
        self.assertEqual(enriched["edges"][0]["items"], ["item:A"])
        self.assertEqual(enriched["nodes"][1]["processes"][0]["inputs"][0]["item_id"], "item:A")
        factory = next(node for node in enriched["nodes"] if node["id"] == "M-1")
        stocks = [stock for rows in factory["inventory"].values() for stock in rows]
        stock = next(row for row in stocks if row["item_id"] == "item:A")
        self.assertEqual(stock["initial"], 50.0)
        self.assertEqual(stock["quantity"], 50.0)
        self.assertEqual(enriched["case_config"]["logistics_assumptions"]["item:PF"]["unitsPerCase"], 125.0)

    def test_excel_roundtrip_is_non_destructive_and_idempotent(self) -> None:
        graph = {
            "items": [{"id": "item:A"}, {"id": "item:PF"}],
            "nodes": [
                {"id": "S-1", "type": "supplier_dc"},
                {
                    "id": "M-1",
                    "type": "factory",
                    "inventory": {"states": [{"item_id": "item:A", "initial": 5, "uom": "KG"}]},
                    "processes": [
                        {
                            "id": "proc:MAKE_PF",
                            "outputs": [{"item_id": "item:PF", "rate_id": "Q_CUSTOM", "uom": "G/day"}],
                            "inputs": [{"item_id": "item:A", "ratio_per_batch": 2, "ratio_unit": "KG"}],
                            "batch_size": 10,
                            "batch_size_unit": "UN",
                            "wip": {"state_id": "WIP_PF", "tau_process": 2, "time_unit": "day"},
                        }
                    ],
                },
            ],
            "edges": [
                {
                    "id": "edge:S-1_TO_M-1_A",
                    "type": "transport",
                    "from": "S-1",
                    "to": "M-1",
                    "items": ["item:A"],
                    "lead_time": {"type": "erlang_pipeline", "mean": 4, "stages": 4, "time_unit": "day"},
                }
            ],
            "scenarios": [
                {
                    "id": "base",
                    "demand": {"daily": [{"customer_id": "C-1", "item_id": "item:PF", "day": 0, "quantity": 10}]},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            workbook = Path(tmp) / "enrichment.xlsx"
            write_excel_template(workbook, graph)
            enriched, report = enrich_graph_from_excel(graph, workbook)
            enriched, second_report = enrich_graph_from_excel(enriched, workbook)

        self.assertFalse([issue for issue in report["issues"] if issue["level"] == "error"])
        self.assertFalse([issue for issue in second_report["issues"] if issue["level"] == "error"])
        edge = enriched["edges"][0]
        self.assertEqual(edge["lead_time"]["type"], "erlang_pipeline")
        self.assertEqual(edge["lead_time"]["stages"], 4)
        process = next(node for node in enriched["nodes"] if node["id"] == "M-1")["processes"][0]
        self.assertEqual(process["outputs"][0]["rate_id"], "Q_CUSTOM")
        self.assertEqual(process["outputs"][0]["uom"], "G/day")
        self.assertEqual(process["wip"]["state_id"], "WIP_PF")
        self.assertEqual(len(enriched["scenarios"][0]["demand"]["daily"]), 1)


if __name__ == "__main__":
    unittest.main()
