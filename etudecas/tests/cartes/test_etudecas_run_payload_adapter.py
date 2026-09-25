from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.run_format import export_run_package
from etudecas.visualization.maps.adapters.etudecas_run_payload import (
    map_inputs_from_run_package,
    run_contract_payload,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class EtudecasRunPayloadAdapterTest(unittest.TestCase):
    def test_map_inputs_resolve_standard_artifacts_from_run_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "result"
            graph_path = root / "graph.json"
            _write_json(graph_path, {"nodes": [{"id": "S", "type": "supplier_dc"}], "edges": []})
            _write_json(
                output_dir / "summaries" / "first_simulation_summary.json",
                {
                    "scenario_id": "scn:test",
                    "sim_days": 1,
                    "timeline_days": 1,
                    "policy": {"output_profile": "compact"},
                    "kpis": {"fill_rate": 1.0},
                },
            )
            csv_rows = [{"day": 0, "node_id": "S", "item_id": "item:A", "stock_end_of_day": 1}]
            required_files = [
                "first_simulation_daily.csv",
                "production_lot_events.csv",
                "production_lot_genealogy.csv",
                "production_input_stocks_daily.csv",
                "production_output_products_daily.csv",
                "production_demand_service_daily.csv",
                "production_supplier_shipments_daily.csv",
                "production_supplier_stocks_daily.csv",
                "production_supplier_capacity_daily.csv",
                "production_input_replenishment_arrivals_daily.csv",
                "production_constraint_daily.csv",
            ]
            for name in required_files:
                _write_csv(output_dir / "data" / name, csv_rows)

            package_dir = export_run_package(output_dir=output_dir, input_graph=graph_path)
            inputs = map_inputs_from_run_package(package_dir)
            contract = run_contract_payload(inputs)

            self.assertEqual(inputs.input_graph, graph_path.resolve(strict=False))
            self.assertEqual(inputs.daily_kpi_csv, output_dir.resolve(strict=False) / "data" / "first_simulation_daily.csv")
            self.assertEqual(contract["schema_version"], "etudecas.simulation_run.v1")
            self.assertEqual(contract["scenario_id"], "scn:test")
            self.assertGreaterEqual(len(contract["artifacts"]), len(required_files))


if __name__ == "__main__":
    unittest.main()
