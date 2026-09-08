from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

from etudecas.simulation.experiments.targeted_replay.discovery import (
    discover_replay_catalog,
)
from etudecas.simulation.experiments.targeted_replay.metrics import lot_trace_evidence
from etudecas.simulation.experiments.targeted_replay.ranking import rank_scenarios
from etudecas.simulation.experiments.targeted_replay.runner import (
    TargetedReplayRunner,
    build_replay_command,
)
from etudecas.simulation.experiments.targeted_replay.schema import (
    KpiSpec,
    ScenarioCandidate,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_source_run(
    run_dir: Path,
    *,
    fake_engine: Path,
    scenario_id: str,
    fill_rate: float,
    total_cost: float,
    delayed: bool,
) -> None:
    command = [
        sys.executable,
        str(fake_engine),
        "--input",
        str(run_dir / "input.json"),
        "--output-dir",
        str(run_dir),
        "--scenario-id",
        scenario_id,
        "--days",
        "30",
        "--no-lot-trace",
        "--preserved-flag",
        "yes",
    ]
    _write_json(run_dir / "input.json", {"scenario_id": scenario_id})
    _write_json(
        run_dir / "run_manifest.json",
        {
            "scenario_id": scenario_id,
            "input_graph": str(run_dir / "input.json"),
            "output_dir": str(run_dir),
            "days": 30,
            "simulator_command": command,
        },
    )
    _write_json(
        run_dir / "summaries" / "first_simulation_summary.json",
        {
            "scenario_id": scenario_id,
            "kpis": {
                "fill_rate": fill_rate,
                "ending_backlog": 0.0 if fill_rate >= 0.99 else 100.0,
                "total_cost": total_cost,
                "total_produced": 1000.0,
            },
            "production_tracking": {
                "production_campaigns": {
                    "campaign_rows": 1,
                    "delayed_campaign_rows": 1 if delayed else 0,
                },
                "lot_trace": {"enabled": True},
            },
        },
    )
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "production_campaigns.csv").write_text(
        "campaign_id,status,delay_event_count\n"
        f"CMP-1,{'completed_after_delay' if delayed else 'completed_without_delay'},"
        f"{1 if delayed else 0}\n",
        encoding="utf-8",
    )


def _write_fake_engine(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            import argparse
            import csv
            import json
            from pathlib import Path
            import sys

            parser = argparse.ArgumentParser()
            parser.add_argument("--output-dir", required=True)
            parser.add_argument("--scenario-id", required=True)
            parser.add_argument("--input")
            parser.add_argument("--days")
            parser.add_argument("--lot-trace", action="store_true")
            parser.add_argument("--skip-map", action="store_true")
            parser.add_argument("--skip-plots", action="store_true")
            args, unknown = parser.parse_known_args()

            output = Path(args.output_dir)
            data = output / "data"
            summaries = output / "summaries"
            run = output / "run"
            data.mkdir(parents=True, exist_ok=True)
            summaries.mkdir(parents=True, exist_ok=True)
            run.mkdir(parents=True, exist_ok=True)
            values = {
                "scn:BASE": (1.0, 100.0, False),
                "scn:S1": (0.8, 150.0, True),
                "scn:S2": (0.95, 110.0, False),
            }
            fill_rate, total_cost, delayed = values.get(args.scenario_id, (1.0, 100.0, False))
            summary = {
                "scenario_id": args.scenario_id,
                "kpis": {
                    "fill_rate": fill_rate,
                    "ending_backlog": 100.0 if fill_rate < 0.99 else 0.0,
                    "total_cost": total_cost,
                    "total_produced": 1000.0,
                },
                "production_tracking": {
                    "production_campaigns": {
                        "campaign_rows": 1,
                        "delayed_campaign_rows": 1 if delayed else 0,
                    },
                    "lot_trace": {
                        "enabled": args.lot_trace,
                        "lot_trace_contract_version": "3.0",
                    },
                },
            }
            (summaries / "first_simulation_summary.json").write_text(
                json.dumps(summary), encoding="utf-8"
            )
            (data / "production_campaigns.csv").write_text(
                "campaign_id,status,delay_event_count\\n"
                + ("CMP-1,completed_after_delay,1\\n" if delayed else "CMP-1,completed_without_delay,0\\n"),
                encoding="utf-8",
            )
            (data / "production_lot_events.csv").write_text(
                "event_id,lot_id,business_batch_id,lot_occurrence_id,shipment_id,"
                "planned_order_id,origin_production_order_ids,"
                "origin_production_contributions_json,causal_event_ids,"
                "causal_root_ids,causal_status,event_type,qty\\n"
                "E1,LOT-1,PBATCH-1,LOCC-1,,PORD-1,PORD-1,"
                "\\"{\\"\\"PORD-1\\"\\":10}\\",,,nominal,production_output,10\\n",
                encoding="utf-8",
            )
            (data / "production_lot_genealogy.csv").write_text(
                "parent_lot_id,child_lot_id,component_allocation_share,"
                "planned_order_id,replacement_transition_id,causal_root_ids,"
                "causal_status,link_type,qty\\n"
                "LOT-0,LOT-1,1,PORD-1,,,nominal,production,10\\n",
                encoding="utf-8",
            )
            (data / "lot_causal_links.csv").write_text(
                "causal_root_id,relation_type,entity_type,entity_id,basis\\n",
                encoding="utf-8",
            )
            (data / "lot_path_audit_issues.csv").write_text(
                "severity,code,message\\n", encoding="utf-8"
            )
            (run / "run_manifest.json").write_text(
                json.dumps({"capabilities": {"lot_trace_enabled": args.lot_trace}}),
                encoding="utf-8",
            )
            (output / "received_command.json").write_text(
                json.dumps(sys.argv[1:]), encoding="utf-8"
            )
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


class KpiSpecTests(unittest.TestCase):
    def test_parse_kpi_spec(self) -> None:
        spec = KpiSpec.parse("product_availability:lower:3")
        self.assertEqual(spec.name, "product_availability")
        self.assertEqual(spec.direction, "lower")
        self.assertEqual(spec.weight, 3.0)

    def test_invalid_weight_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            KpiSpec.parse("total_cost:higher:0")


class LotTraceEvidenceTests(unittest.TestCase):
    def test_old_contract_is_rejected_even_when_csv_files_are_nonempty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            _write_json(
                run_dir / "summaries" / "first_simulation_summary.json",
                {
                    "production_tracking": {
                        "lot_trace": {
                            "enabled": True,
                            "lot_trace_contract_version": "2.0",
                        }
                    }
                },
            )
            data_dir = run_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "production_lot_events.csv").write_text(
                "event_id,lot_id,event_type\nE1,L1,production_output\n",
                encoding="utf-8",
            )
            (data_dir / "production_lot_genealogy.csv").write_text(
                "parent_lot_id,child_lot_id\nL0,L1\n",
                encoding="utf-8",
            )
            evidence = lot_trace_evidence(run_dir)
            self.assertFalse(evidence["valid"])
            self.assertFalse(evidence["contract_ready"])
            self.assertTrue(evidence["missing_event_columns"])


class RankingTests(unittest.TestCase):
    @staticmethod
    def candidate(scenario_id: str, metrics: dict[str, float]) -> ScenarioCandidate:
        return ScenarioCandidate(
            scenario_id=scenario_id,
            label=scenario_id,
            source_run_dir=Path("."),
            source_manifest=Path("manifest.json"),
            simulator_command=["python", "engine.py"],
            metrics=metrics,
        )

    def test_rank_combines_adverse_kpi_directions(self) -> None:
        baseline = self.candidate(
            "base",
            {"product_availability": 1.0, "total_cost": 100.0},
        )
        availability_crisis = self.candidate(
            "availability",
            {"product_availability": 0.7, "total_cost": 105.0},
        )
        cost_crisis = self.candidate(
            "cost",
            {"product_availability": 0.99, "total_cost": 200.0},
        )
        specs = (
            KpiSpec("product_availability", "lower", 3.0),
            KpiSpec("total_cost", "higher", 1.0),
        )
        ranked = rank_scenarios(baseline, [cost_crisis, availability_crisis], specs)
        self.assertEqual(ranked[0].candidate.scenario_id, "availability")
        self.assertGreater(ranked[0].score, ranked[1].score)


class DiscoveryAndRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake_engine = self.root / "fake_engine.py"
        _write_fake_engine(self.fake_engine)
        self.source = self.root / "source"
        _write_source_run(
            self.source,
            fake_engine=self.fake_engine,
            scenario_id="scn:BASE",
            fill_rate=1.0,
            total_cost=100.0,
            delayed=False,
        )
        s1 = self.source / "scenario_runs" / "s1"
        s2 = self.source / "scenario_runs" / "s2"
        _write_source_run(
            s1,
            fake_engine=self.fake_engine,
            scenario_id="scn:S1",
            fill_rate=0.8,
            total_cost=150.0,
            delayed=True,
        )
        _write_source_run(
            s2,
            fake_engine=self.fake_engine,
            scenario_id="scn:S2",
            fill_rate=0.95,
            total_cost=110.0,
            delayed=False,
        )
        root_manifest = json.loads((self.source / "run_manifest.json").read_text(encoding="utf-8"))
        root_manifest["baseline"] = "Nominal"
        root_manifest["companion_runs"] = {
            "s1": {"output_dir": "scenario_runs/s1", "label": "Severe"},
            "s2": {"output_dir": "scenario_runs/s2", "label": "Moderate"},
        }
        _write_json(self.source / "run_manifest.json", root_manifest)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_discovery_reads_baseline_and_companions(self) -> None:
        catalog = discover_replay_catalog(self.source, repo_root=self.root)
        self.assertEqual(catalog.baseline.scenario_id, "scn:BASE")
        self.assertEqual([row.scenario_id for row in catalog.candidates], ["scn:S1", "scn:S2"])
        self.assertEqual(catalog.candidates[0].metrics["production_replanning_rate"], 1.0)

    def test_command_forces_lot_trace_and_preserves_other_flags(self) -> None:
        catalog = discover_replay_catalog(self.source, repo_root=self.root)
        command = build_replay_command(catalog.candidates[0], self.root / "target", days=7)
        self.assertIn("--lot-trace", command)
        self.assertNotIn("--no-lot-trace", command)
        self.assertIn("--skip-map", command)
        self.assertIn("--skip-plots", command)
        self.assertIn("--preserved-flag", command)
        self.assertEqual(command[command.index("--days") + 1], "7")

    def test_runner_executes_baseline_and_top_scenario(self) -> None:
        catalog = discover_replay_catalog(self.source, repo_root=self.root)
        specs = [
            KpiSpec("product_availability", "lower", 3.0),
            KpiSpec("total_cost", "higher", 1.0),
        ]
        ranking = rank_scenarios(catalog.baseline, catalog.candidates, specs)
        output = self.root / "targeted"
        runner = TargetedReplayRunner(
            catalog=catalog,
            ranking=ranking,
            specs=specs,
            output_dir=output,
            top_k=1,
            days=7,
        )
        manifest = runner.run(execute=True)
        self.assertEqual(manifest["execution_status"], "completed")
        self.assertEqual(len(manifest["replays"]), 2)
        selected = manifest["replays"][1]
        self.assertEqual(selected["scenario_id"], "scn:S1")
        self.assertTrue(selected["lot_trace"]["valid"])
        self.assertEqual(selected["lot_trace"]["audit_issue_rows"], 0)
        received = json.loads(
            (Path(selected["replay_output_dir"]) / "received_command.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("--lot-trace", received)
        self.assertNotIn("--no-lot-trace", received)
        self.assertAlmostEqual(
            selected["delta_vs_replayed_baseline"]["product_availability"],
            -0.2,
        )
        self.assertTrue((output / "selection_manifest.json").exists())
        self.assertTrue((output / "comparison_manifest.json").exists())

        rebuilt = runner.run(execute=False, reuse_existing=True)
        self.assertEqual(rebuilt["execution_status"], "completed")
        self.assertEqual(len(rebuilt["replays"]), 2)
        rebuilt_selected = rebuilt["replays"][1]
        self.assertEqual(rebuilt_selected["result_source"], "existing_replay_output")
        self.assertTrue(rebuilt_selected["lot_trace"]["valid"])
        self.assertAlmostEqual(
            rebuilt_selected["delta_vs_replayed_baseline"]["product_availability"],
            -0.2,
        )
        self.assertTrue(rebuilt_selected["lot_delta_report"]["json"])


if __name__ == "__main__":
    unittest.main()
