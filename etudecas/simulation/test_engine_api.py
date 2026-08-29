import json
from pathlib import Path
import threading
import tempfile
import textwrap
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
import unittest

from etudecas.simulation.engine import SimulationOverrides, SimulationRequest, simulate
from etudecas.simulation.engine.api import request_from_dict
from etudecas.simulation.engine.server import SimulationApiHandler


class SimulationEngineApiTest(unittest.TestCase):
    def write_fake_engine(self, root: Path) -> Path:
        fake_engine = root / "fake_engine.py"
        fake_engine.write_text(
            textwrap.dedent(
                """
                import argparse
                import json
                from pathlib import Path

                parser = argparse.ArgumentParser()
                parser.add_argument("--input")
                parser.add_argument("--output-dir")
                parser.add_argument("--scenario-id")
                parser.add_argument("--days", default="0")
                parser.add_argument("--skip-map", action="store_true")
                parser.add_argument("--skip-plots", action="store_true")
                parser.add_argument("--output-profile", default="")
                parser.add_argument("--lot-trace", action="store_true")
                parser.add_argument("--no-lot-trace", action="store_true")
                parser.add_argument("--skip-lot-audit", action="store_true")
                parser.add_argument("--demand-perturbation-csv", default="")
                parser.add_argument("--control-schedule-csv", default="")
                parser.add_argument("--control-policy-json", default="")
                parser.add_argument("--seed", type=int, default=None)
                parser.add_argument(
                    "--common-random-numbers",
                    action=argparse.BooleanOptionalAction,
                    default=None,
                )
                args, extra = parser.parse_known_args()

                data = json.loads(Path(args.input).read_text(encoding="utf-8"))
                edge = data["edges"][0]
                summary = {
                    "kpis": {
                        "fill_rate": 0.97,
                        "total_cost": 123.0,
                        "edge_lead_mean": edge["lead_time"]["mean"],
                        "edge_otif": edge["service_level"]["otif"],
                    },
                    "meta": {
                        "scenario_id": args.scenario_id,
                        "output_profile": args.output_profile,
                        "lot_trace": args.lot_trace,
                        "no_lot_trace": args.no_lot_trace,
                        "skip_lot_audit": args.skip_lot_audit,
                        "demand_perturbation_csv": args.demand_perturbation_csv,
                        "control_schedule_csv": args.control_schedule_csv,
                        "control_policy_json": args.control_policy_json,
                        "seed": args.seed,
                        "common_random_numbers": args.common_random_numbers,
                        "extra": extra,
                    },
                }
                out = Path(args.output_dir) / "summaries"
                out.mkdir(parents=True, exist_ok=True)
                (out / "first_simulation_summary.json").write_text(
                    json.dumps(summary),
                    encoding="utf-8",
                )
                print("fake simulation ok")
                """
            ),
            encoding="utf-8",
        )
        return fake_engine

    def graph(self):
        return {
            "scenarios": [{"id": "scn:BASE", "demand": [], "economic_policy": {}}],
            "nodes": [
                {"id": "SDC-1", "type": "supplier_dc"},
                {"id": "M-1", "type": "factory", "processes": []},
            ],
            "edges": [
                {
                    "id": "E1",
                    "from": "SDC-1",
                    "to": "M-1",
                    "items": ["item:A"],
                    "lead_time": {"mean": 10.0},
                    "service_level": {"otif": 1.0},
                }
            ],
        }

    def test_request_preserves_historical_positional_field_order(self):
        overrides = SimulationOverrides(engine_args=("--legacy-flag",))
        request = SimulationRequest(
            None,
            "legacy-input.json",
            "scn:POSITIONAL",
            42,
            "minimal",
            overrides,
            "legacy-output",
            "legacy-run",
            "legacy-engine.py",
            False,
            False,
            True,
            "legacy-controls.csv",
            1729,
            True,
        )

        self.assertEqual(request.control_schedule_csv, "legacy-controls.csv")
        self.assertEqual(request.seed, 1729)
        self.assertIs(request.common_random_numbers, True)
        self.assertIsNone(request.control_policy_json)
        self.assertIsNone(request.demand_perturbation_csv)

    def test_simulate_writes_mutated_input_and_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_engine = self.write_fake_engine(root)
            control_policy = root / "state feedback policy.json"
            control_policy.write_text("{}", encoding="utf-8")
            demand_perturbation = root / "demand excitation.csv"
            demand_perturbation.write_text(
                "day,node_id,item_id,demand_multiplier\n",
                encoding="utf-8",
            )
            result = simulate(
                SimulationRequest(
                    input_graph=self.graph(),
                    scenario_id="scn:BASE",
                    output_dir=root / "run",
                    run_script=fake_engine,
                    output_profile="lot_trace",
                    demand_perturbation_csv=demand_perturbation,
                    control_policy_json=control_policy,
                    seed=1729,
                    common_random_numbers=True,
                    overrides=SimulationOverrides(
                        edge_src_lead_time_scale={"SDC-1": 1.5},
                        edge_src_reliability_scale={"SDC-1": 0.8},
                        scenario_flags={"external_procurement_enabled": True},
                        engine_args=(
                            "--control-policy-json",
                            "shadow-policy.json",
                            "--seed",
                            "1",
                            "--no-common-random-numbers",
                        ),
                    ),
                )
            )

            self.assertEqual(result.kpis["fill_rate"], 0.97)
            self.assertEqual(result.kpis["edge_lead_mean"], 15.0)
            self.assertEqual(result.kpis["edge_otif"], 0.8)
            self.assertTrue(result.summary["meta"]["lot_trace"])
            self.assertTrue(result.summary["meta"]["skip_lot_audit"])
            self.assertEqual(
                result.summary["meta"]["demand_perturbation_csv"],
                str(demand_perturbation),
            )
            self.assertEqual(result.summary["meta"]["control_schedule_csv"], "")
            self.assertEqual(
                result.summary["meta"]["control_policy_json"],
                str(control_policy),
            )
            self.assertEqual(result.summary["meta"]["seed"], 1729)
            self.assertIs(result.summary["meta"]["common_random_numbers"], True)

            written_input = json.loads(result.input_path.read_text(encoding="utf-8"))
            self.assertEqual(written_input["edges"][0]["lead_time"]["mean"], 15.0)
            self.assertEqual(written_input["edges"][0]["service_level"]["otif"], 0.8)
            self.assertTrue(written_input["scenarios"][0]["economic_policy"]["external_procurement_enabled"])

    def test_http_server_simulate_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_engine = self.write_fake_engine(root)
            control_schedule = root / "daily controls.csv"
            control_schedule.write_text(
                "day,order_multiplier\n0,1.1\n",
                encoding="utf-8",
            )
            demand_perturbation = root / "http demand excitation.csv"
            demand_perturbation.write_text(
                "day,node_id,item_id,demand_multiplier\n",
                encoding="utf-8",
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), SimulationApiHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = {
                    "input_graph": self.graph(),
                    "scenario_id": "scn:BASE",
                    "output_dir": str(root / "http_run"),
                    "run_script": str(fake_engine),
                    "output_profile": "minimal",
                    "demand_perturbation_csv": str(demand_perturbation),
                    "control_schedule_csv": str(control_schedule),
                    "seed": 2027,
                    "common_random_numbers": False,
                    "overrides": {"edge_src_lead_time_scale": {"SDC-1": 2.0}},
                }
                req = Request(
                    f"http://127.0.0.1:{server.server_port}/simulate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                response = json.loads(urlopen(req, timeout=10).read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertTrue(response["ok"])
            self.assertEqual(response["result"]["kpis"]["edge_lead_mean"], 20.0)
            self.assertEqual(response["result"]["output_profile"], "minimal")
            summary_path = root / "http_run" / "summaries" / "first_simulation_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(
                summary["meta"]["demand_perturbation_csv"],
                str(demand_perturbation),
            )
            self.assertEqual(summary["meta"]["control_schedule_csv"], str(control_schedule))
            self.assertEqual(summary["meta"]["control_policy_json"], "")
            self.assertEqual(summary["meta"]["seed"], 2027)
            self.assertIs(summary["meta"]["common_random_numbers"], False)

    def test_simulate_rejects_schedule_and_feedback_policy_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_engine = self.write_fake_engine(root)
            schedule = root / "controls.csv"
            schedule.write_text("day,order_multiplier\n0,1.1\n", encoding="utf-8")
            policy = root / "policy.json"
            policy.write_text("{}", encoding="utf-8")
            request = request_from_dict(
                {
                    "input_graph": self.graph(),
                    "output_dir": root / "invalid_run",
                    "run_script": fake_engine,
                    "control_schedule_csv": schedule,
                    "control_policy_json": policy,
                }
            )
            self.assertEqual(request.control_schedule_csv, schedule)
            self.assertEqual(request.control_policy_json, policy)

            with self.assertRaisesRegex(
                ValueError,
                "cannot combine control_schedule_csv with control_policy_json",
            ):
                simulate(request)


if __name__ == "__main__":
    unittest.main()
