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
from etudecas.simulation.experiments.sensitivity.designs import example_study_dict


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

class StudiesEntryPointTests(unittest.TestCase):
    def test_lazy_executor_forwards_arguments_unchanged(self):
        import sys
        from types import ModuleType
        from unittest.mock import patch, Mock
        from etudecas.simulation import studies
        name = 'etudecas.simulation.montecarlo.run_montecarlo_analysis'
        module = ModuleType(name)
        module.execute_run_spec = Mock(return_value={'status': 'fixture'})
        spec = {'index': 3}
        with patch.dict(sys.modules, {name: module}):
            self.assertEqual(studies.execute_run_spec(spec, days=12), {'status': 'fixture'})
        module.execute_run_spec.assert_called_once_with(spec, days=12)

    def test_dispatch_preserves_mode_arguments(self):
        from unittest.mock import patch
        from etudecas.simulation import studies
        for mode in ('sensitivity', 'targeted', 'paired', 'temporal'):
            with self.subTest(mode=mode), patch.object(studies, mode + '_main', return_value=7) as run:
                self.assertEqual(studies.main([mode, '--help']), 7)
                run.assert_called_once_with(['--help'])

    def test_help_for_each_mode_without_starting_calculations(self):
        import contextlib
        import io
        from unittest.mock import patch
        from etudecas.simulation import studies
        for mode in ('sensitivity', 'targeted', 'paired', 'temporal'):
            with self.subTest(mode=mode), contextlib.redirect_stdout(io.StringIO()), patch.object(studies, 'execute_run_spec', side_effect=AssertionError('No engine')), self.assertRaises(SystemExit) as caught:
                studies.main([mode, '--help'])
            self.assertEqual(caught.exception.code, 0)

    def test_sensitivity_materialize_keeps_queue_without_engine(self):
        from unittest.mock import patch
        from etudecas.simulation import studies
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = root / 'graph.json'
            graph.write_text(json.dumps({'nodes': [], 'edges': [], 'scenarios': [{'id': 'scn:BASE', 'days': 10, 'demand': [], 'economic_policy': {}}]}), encoding='utf-8')
            raw = example_study_dict()
            raw.update(input_graph=str(graph), horizon_days=10, parameters=[{'name': 'demand_scale', 'baseline': 1.0, 'levels': [0.5, 1.0]}])
            config = root / 'study.json'
            config.write_text(json.dumps(raw), encoding='utf-8')
            with patch.object(studies, 'execute_run_spec', side_effect=AssertionError('No engine')):
                self.assertEqual(studies.main(['sensitivity', 'materialize', '--study', str(config), '--output-dir', str(root / 'output')]), 0)
            rows = list(csv.DictReader((root / 'output/materialized_cases.csv').open(encoding='utf-8')))
            self.assertEqual(len(rows), 2)
            self.assertIn('--days 10', (root / 'output/run_commands.ps1').read_text(encoding='utf-8'))

    def test_targeted_modes_and_conflicting_flags(self):
        from types import SimpleNamespace
        from unittest.mock import patch, Mock
        from etudecas.simulation import studies
        for flags, execute, reuse in [([], False, False), (['--execute'], True, False), (['--reuse-existing'], False, True)]:
            runner = Mock()
            runner.run.return_value = {'execution_status': 'planned'}
            with patch.object(studies, 'discover_replay_catalog', return_value=SimpleNamespace(baseline={}, candidates=[])), patch.object(studies, 'rank_scenarios', return_value=[]), patch.object(studies, 'TargetedReplayRunner', return_value=runner):
                self.assertEqual(studies.main(['targeted', '--source-run', 'source', '--output-dir', 'target', *flags]), 0)
                runner.run.assert_called_once_with(execute=execute, reuse_existing=reuse)
                runner.run.reset_mock()
                with self.assertRaisesRegex(SystemExit, 'mutually exclusive'):
                    studies.main(['targeted', '--source-run', 'source', '--output-dir', 'target', '--execute', '--reuse-existing'])
                runner.run.assert_not_called()

    def test_paired_retains_order_failures_and_summary(self):
        from contextlib import ExitStack
        from unittest.mock import patch
        from etudecas.simulation import studies
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = root / 'graph.json'
            graph.write_text('{}', encoding='utf-8')
            summary = root / 'montecarlo_summary.json'
            summary.write_text(json.dumps({'input': str(graph), 'workers': 2, 'scenario_id': 'scn:X', 'days_override': 12, 'simulator_extra_args': ['--seed', '42']}), encoding='utf-8')
            (root / 'montecarlo_samples.csv').write_text('index,status\n0,ok\n', encoding='utf-8')
            specs = [{'index': i, 'run_id': str(i), 'row': {}, 'paired_metadata': {'index': i}} for i in range(3)]
            calls = []
            def execute(spec, **kwargs):
                calls.append((spec['index'], kwargs))
                if spec['index'] == 1:
                    raise ValueError('intentional fixture failure')
                return {'index': spec['index'], 'row': {'status': 'ok'}, 'trajectory_run': {'days': [0]}}
            def payload(**kwargs):
                self.assertEqual([x['paired_metadata']['index'] for x in kwargs['trajectory_runs']], [0, 2])
                return {'run_count': 2, 'factor_count': 1, 'background_count': 1}
            with ExitStack() as stack:
                replacements = {'select_supplier_item_factors': lambda *a, **k: ['demand_scale'], 'select_paired_factors': lambda *a, **k: [], 'select_background_rows': lambda *a, **k: [{'index': 0}], 'build_paired_run_specs': lambda **k: specs, 'execute_run_spec': execute, 'build_paired_propagation_payload': payload, 'build_temporal_propagation': lambda *a, **k: {'temporal': True}}
                for name, value in replacements.items():
                    stack.enter_context(patch.object(studies, name, value))
                studies.main(['paired', '--summary-json', str(summary), '--factor-count', '1'])
            self.assertEqual(len(calls), 3)
            self.assertTrue(all(k['days'] == 12 and k['simulator_extra_args'] == ['--seed', '42'] for _, k in calls))
            output = json.loads(summary.read_text(encoding='utf-8'))['paired_propagation']
            self.assertEqual(output['runs_failed'], 1)
            self.assertEqual(output['runs_successful'], 2)
            self.assertEqual(json.loads((root / 'montecarlo_paired_propagation.json').read_text())['failed_runs'], 1)

    def test_temporal_mode_publishes_algorithm_payload(self):
        from etudecas.simulation import studies
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paired, graph, output = root / 'paired.json', root / 'graph.json', root / 'output.json'
            paired.write_text('{"days": [], "metrics": {}}', encoding='utf-8')
            graph.write_text('{"nodes": [], "edges": []}', encoding='utf-8')
            expected = studies.build_temporal_propagation(json.loads(paired.read_text()), json.loads(graph.read_text()), lot_events_csv=None)
            studies.main(['temporal', '--paired-json', str(paired), '--graph-json', str(graph), '--output-json', str(output)])
            self.assertEqual(json.loads(output.read_text()), expected)


if __name__ == "__main__":
    unittest.main()
