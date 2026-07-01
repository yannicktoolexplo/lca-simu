import csv
import json
from pathlib import Path
import tempfile
import unittest

from etudecas.simulation.experiments.sensitivity import (
    StudySpec,
    build_scenario_designs,
    consolidate_case_csvs,
    discover_case_csvs,
    ingest_case_csvs,
    materialize_cases,
    normalize_metric_row,
    summarize_metrics,
    write_scenario_design_csv,
)
from etudecas.simulation.experiments.sensitivity.results import registry_rows, write_csv
from etudecas.simulation.experiments.sensitivity.schema import example_study_dict


class SensitivityExperimentsTest(unittest.TestCase):
    def test_one_at_a_time_design_is_stable_and_compact(self):
        study = StudySpec.from_dict(example_study_dict())

        designs = build_scenario_designs(study)

        self.assertEqual(designs[0].kind, "baseline")
        self.assertEqual(designs[0].changed_parameters, ())
        self.assertGreater(len(designs), 1)
        self.assertTrue(all("supplier_lead_capacity_example" in d.scenario_id for d in designs))
        non_baseline = [d for d in designs if d.kind != "baseline"]
        self.assertTrue(all(len(d.changed_parameters) == 1 for d in non_baseline))

    def test_design_csv_writes_parameter_columns(self):
        study = StudySpec.from_dict(example_study_dict())
        designs = build_scenario_designs(study)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario_design.csv"

            write_scenario_design_csv(path, designs)

            with path.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), len(designs))
            self.assertIn("parameter_values_json", rows[0])
            self.assertIn("param::supplier_capacity_scale", rows[0])

    def test_ingest_normalizes_prefixed_and_flat_kpis(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cases.csv"
            with source.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "case_id",
                        "status",
                        "parameter_group",
                        "kpi::fill_rate",
                        "total_cost",
                        "delta::kpi::fill_rate",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "case_id": "case_a",
                        "status": "ok",
                        "parameter_group": "capacity",
                        "kpi::fill_rate": "0.99",
                        "total_cost": "123.4",
                        "delta::kpi::fill_rate": "-0.01",
                    }
                )

            rows = ingest_case_csvs([source], study_id="study_a")

            self.assertEqual(rows[0]["case_id"], "case_a")
            self.assertEqual(rows[0]["study_id"], "study_a")
            self.assertEqual(rows[0]["parameter_group"], "capacity")
            self.assertAlmostEqual(rows[0]["kpi::fill_rate"], 0.99)
            self.assertAlmostEqual(rows[0]["kpi::total_cost"], 123.4)
            self.assertAlmostEqual(rows[0]["delta::fill_rate"], -0.01)

    def test_ingest_normalizes_supplier_risk_campaign_flat_schema(self):
        row = {
            "case_id": "supplier_a__lead",
            "supplier_id": "SUP-A",
            "risk_family": "lead",
            "risk_type": "lead_time_extra_days",
            "multiplier": "30",
            "fill_rate": "0.95",
            "fill_rate_delta_pts": "-5.0",
            "total_cost": "1000",
            "total_cost_delta": "50",
            "total_cost_delta_pct": "0.05",
            "impact_score": "0.7",
            "case_dir": "cases/supplier_a__lead",
        }

        self.assertEqual(ingest_case_csvs([]), [])
        normalized = [
            normalize_metric_row(
                row,
                study_id="risk_study",
                source_file="risk/supplier_risk_campaign_cases.csv",
            )
        ]

        self.assertEqual(normalized[0]["supplier_id"], "SUP-A")
        self.assertEqual(normalized[0]["case_output_dir"], "cases/supplier_a__lead")
        self.assertAlmostEqual(normalized[0]["kpi::fill_rate"], 0.95)
        self.assertAlmostEqual(normalized[0]["delta::fill_rate_pts"], -5.0)
        self.assertAlmostEqual(normalized[0]["delta::total_cost"], 50.0)
        self.assertAlmostEqual(normalized[0]["delta_pct::total_cost"], 0.05)
        self.assertAlmostEqual(normalized[0]["kpi::impact_score"], 0.7)

    def test_summary_and_registry_are_compact(self):
        rows = [
            {"case_id": "a", "scenario_id": "a", "status": "ok", "kpi::fill_rate": 1.0},
            {"case_id": "b", "scenario_id": "b", "status": "error", "kpi::fill_rate": 0.5},
        ]

        summary = summarize_metrics(rows)
        registry = registry_rows(rows)

        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["ok_count"], 1)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["kpis"]["kpi::fill_rate"]["min"], 1.0)
        self.assertEqual(registry[0]["case_id"], "a")
        self.assertNotIn("kpi::fill_rate", registry[0])

    def test_write_csv_handles_dynamic_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.csv"
            rows = [{"case_id": "a", "kpi::fill_rate": 1.0}, {"case_id": "b", "kpi::cost": 2.0}]

            write_csv(path, rows)

            with path.open("r", encoding="utf-8", newline="") as f:
                loaded = list(csv.DictReader(f))
            self.assertEqual(len(loaded), 2)
            self.assertIn("kpi::cost", loaded[0])

    def test_example_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "study.json"
            path.write_text(json.dumps(example_study_dict(), ensure_ascii=False), encoding="utf-8")

            study = StudySpec.from_path(path)

            self.assertEqual(study.study_id, "supplier_lead_capacity_example")
            self.assertEqual(study.retention, "summary")

    def test_materialize_cases_writes_inputs_and_run_queue_without_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_graph = root / "graph.json"
            input_graph.write_text(
                json.dumps(
                    {
                        "nodes": [],
                        "edges": [],
                        "scenarios": [
                            {
                                "id": "scn:BASE",
                                "days": 10,
                                "demand": [],
                                "economic_policy": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            raw = example_study_dict()
            raw["input_graph"] = str(input_graph)
            raw["horizon_days"] = 10
            raw["parameters"] = [
                {
                    "name": "demand_scale",
                    "baseline": 1.0,
                    "levels": [0.5, 1.0],
                }
            ]
            study = StudySpec.from_dict(raw)

            rows = materialize_cases(study, root / "study_out")

            self.assertEqual(len(rows), 2)
            self.assertTrue((root / "study_out" / "materialized_cases.csv").exists())
            self.assertTrue((root / "study_out" / "run_commands.ps1").exists())
            self.assertTrue((root / "study_out" / "cases" / rows[0]["scenario_id"] / "input_case.json").exists())

    def test_discovery_skips_heavy_case_outputs_and_consolidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir = root / "result_a"
            result_dir.mkdir()
            case_csv = result_dir / "scenario_results.csv"
            with case_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["scenario_id", "status", "kpi::fill_rate"])
                writer.writeheader()
                writer.writerow({"scenario_id": "baseline", "status": "ok", "kpi::fill_rate": "1.0"})
            skipped_dir = result_dir / "cases" / "case_a"
            skipped_dir.mkdir(parents=True)
            (skipped_dir / "scenario_results.csv").write_text("scenario_id,status\nbad,ok\n", encoding="utf-8")

            discovered = discover_case_csvs(root)
            consolidated = consolidate_case_csvs(root, root / "out")

            self.assertEqual(discovered, [case_csv])
            self.assertEqual(len(consolidated["metrics_rows"]), 1)
            self.assertTrue((root / "out" / "source_files.csv").exists())
            self.assertTrue((root / "out" / "metrics.csv").exists())

if __name__ == "__main__":
    unittest.main()
