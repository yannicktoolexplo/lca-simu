from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etudecas.simulation.run_format import export_run_package, load_run_package, validate_run_package


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_empty_csv(path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


class RunFormatIntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / "result"
        graph = self.root / "graph.json"
        _write_json(graph, {"nodes": [{"id": "S1"}, {"id": "M1"}],
                            "edges": [{"id": "E1", "from": "S1", "to": "M1"}]})
        _write_json(self.output / "summaries" / "first_simulation_summary.json",
                    {"policy": {"lot_trace_enabled": True}, "kpis": {}})
        for name in ("first_simulation_daily.csv", "production_lot_events.csv", "production_lot_genealogy.csv"):
            _write_csv(self.output / "data" / name, [{"day": 0, "qty": 1}])
        # A custom package location must still resolve artifacts against output_dir.
        self.package = export_run_package(output_dir=self.output, input_graph=graph,
                                          package_dir=self.root / "separate_package")

    def failures(self) -> list[dict[str, object]]:
        return [row for row in validate_run_package(self.package) if not row["ok"]]

    def edit(self, name: str, transform) -> None:
        path = self.package / name
        value = json.loads(path.read_text(encoding="utf-8"))
        _write_json(path, transform(value))

    def test_valid_custom_location_and_absent_optional_artifacts(self) -> None:
        self.assertEqual(self.failures(), [])

    def test_deleted_required_csv_is_rejected_despite_exists_flag(self) -> None:
        (self.output / "data" / "first_simulation_daily.csv").unlink()
        self.assertTrue(self.failures())

    def test_csv_corruption_is_rejected(self) -> None:
        path = self.output / "data" / "first_simulation_daily.csv"
        for content in ('day,qty\n0,1,2\n', 'day,qty\n0\n', 'day,qty\n0,"unterminated',
                        'day,day\n0,1\n', 'day,qty\n0,1\n1,2\n', ''):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assertTrue(self.failures())

    def test_invalid_json_and_document_types_report_failures(self) -> None:
        for name in ("run_manifest.json", "nodes.json", "flows.json", "kpis.json", "artifact_index.json", "lots_index.json"):
            path = self.package / name
            original = path.read_bytes()
            try:
                for content in ('{', 'null', '42', '"text"'):
                    with self.subTest(name=name, content=content):
                        path.write_text(content, encoding="utf-8")
                        self.assertTrue(self.failures())
            finally:
                path.write_bytes(original)

    def test_directory_entrypoint_is_rejected(self) -> None:
        path = self.package / "nodes.json"
        path.unlink()
        path.mkdir()
        self.assertTrue(self.failures())

    def test_unknown_flow_endpoint_is_rejected(self) -> None:
        self.edit("flows.json", lambda rows: [dict(rows[0], to="UNKNOWN")])
        self.assertTrue(self.failures())

    def test_duplicate_and_invalid_ids_are_rejected(self) -> None:
        for nodes in ([{"id": "S1"}, {"id": "S1"}], [{}], [{"id": []}], [42]):
            with self.subTest(nodes=nodes):
                _write_json(self.package / "nodes.json", nodes)
                self.assertTrue(self.failures())

    def test_required_entry_cannot_be_removed(self) -> None:
        self.edit("artifact_index.json", lambda rows: [row for row in rows if row["name"] != "first_simulation_daily.csv"])
        self.assertTrue(self.failures())

    def test_invalid_artifact_metadata_is_rejected(self) -> None:
        path = self.package / "artifact_index.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for field, value in (("row_count", "1"), ("row_count", True), ("exists", "true"),
                             ("required", False), ("path", []), ("format", "unknown")):
            with self.subTest(field=field, value=value):
                rows = [dict(row) for row in original]
                rows[0][field] = value
                _write_json(path, rows)
                self.assertTrue(self.failures())

    def test_stale_group_index_is_rejected(self) -> None:
        _write_json(self.package / "lots_index.json", [])
        self.assertTrue(self.failures())

    def test_corrupt_json_artifact_is_rejected(self) -> None:
        (self.output / "summaries" / "first_simulation_summary.json").write_text('{', encoding="utf-8")
        self.assertTrue(self.failures())

    def test_string_false_does_not_allow_empty_lots(self) -> None:
        self.edit("run_manifest.json", lambda value: dict(value, capabilities={"lot_trace_enabled": "false"}))
        self.assertTrue(self.failures())

    def test_assertion_reports_actionable_failures(self) -> None:
        from etudecas.simulation.run_format.validator import assert_run_package_valid
        (self.output / "data" / "first_simulation_daily.csv").unlink()
        with self.assertRaisesRegex(RuntimeError, "first_simulation_daily.csv"):
            assert_run_package_valid(self.package)

    def test_non_finite_json_is_rejected(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                (self.package / "kpis.json").write_text('{"cost": ' + value + '}', encoding="utf-8")
                self.assertTrue(self.failures())

    def test_cli_export_returns_failure_for_incomplete_results(self) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from etudecas.simulation.run_format.cli import main

        with patch("sys.argv", ["run_format", "export", "--output-dir", str(self.root / "empty")]):
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)


class RunFormatExportTest(unittest.TestCase):
    def test_export_run_package_indexes_core_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "result"
            graph_path = root / "graph.json"
            _write_json(
                graph_path,
                {
                    "nodes": [
                        {"id": "S1", "type": "supplier_dc", "name": "Supplier", "geo": {"lat": 1, "lon": 2}},
                        {"id": "M1", "type": "factory", "name": "Factory", "geo": {"lat": 3, "lon": 4}},
                    ],
                    "edges": [
                        {
                            "id": "E1",
                            "type": "transport",
                            "from": "S1",
                            "to": "M1",
                            "items": ["item:A"],
                            "lead_time": {"mean": 2},
                            "attrs": {"standard_order_qty": 10},
                        }
                    ],
                },
            )
            _write_json(
                output_dir / "summaries" / "first_simulation_summary.json",
                {
                    "scenario_id": "scn:test",
                    "sim_days": 2,
                    "timeline_days": 2,
                    "policy": {"output_profile": "compact"},
                    "counts": {"nodes": 2, "edges": 1},
                    "kpis": {"fill_rate": 1.0, "total_cost": 12.3},
                },
            )
            _write_csv(
                output_dir / "data" / "first_simulation_daily.csv",
                [
                    {"day": 0, "demand": 1, "served": 1},
                    {"day": 1, "demand": 1, "served": 1},
                ],
            )
            _write_csv(
                output_dir / "data" / "production_lot_events.csv",
                [{"event_id": "E", "day": 0, "event_type": "opening_stock", "lot_id": "L1", "node_id": "M1"}],
            )
            _write_csv(
                output_dir / "data" / "production_lot_genealogy.csv",
                [{"day": 0, "link_type": "production", "parent_lot_id": "L1", "child_lot_id": "L2"}],
            )

            package_dir = export_run_package(output_dir=output_dir, input_graph=graph_path)
            validations = validate_run_package(package_dir)

            self.assertFalse([row for row in validations if not row["ok"]], validations)
            manifest = json.loads((package_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "etudecas.simulation_run.v1")
            self.assertEqual(manifest["scenario_id"], "scn:test")
            self.assertEqual(manifest["counts"]["nodes"], 2)
            self.assertEqual(manifest["counts"]["flows"], 1)
            artifacts = json.loads((package_dir / "artifact_index.json").read_text(encoding="utf-8"))
            daily = next(row for row in artifacts if row["name"] == "first_simulation_daily.csv")
            self.assertEqual(daily["row_count"], 2)
            self.assertEqual(daily["day_range"], {"min": 0, "max": 1})
            package = load_run_package(package_dir)
            self.assertEqual(package.output_dir, output_dir.resolve(strict=False))
            self.assertEqual(
                package.require_artifact_path(domain="global_kpi"),
                (output_dir / "data" / "first_simulation_daily.csv").resolve(strict=False),
            )

    def test_validate_run_package_allows_empty_lot_artifacts_when_lot_trace_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "result"
            graph_path = root / "graph.json"
            _write_json(
                graph_path,
                {
                    "nodes": [{"id": "S1"}, {"id": "M1"}],
                    "edges": [{"id": "E1", "from": "S1", "to": "M1", "items": ["item:A"]}],
                },
            )
            _write_json(
                output_dir / "summaries" / "first_simulation_summary.json",
                {
                    "scenario_id": "scn:no_lot_trace",
                    "sim_days": 1,
                    "timeline_days": 1,
                    "policy": {"output_profile": "compact", "lot_trace_enabled": False},
                    "counts": {"nodes": 2, "edges": 1},
                    "kpis": {},
                },
            )
            _write_csv(output_dir / "data" / "first_simulation_daily.csv", [{"day": 0, "demand": 0}])
            _write_empty_csv(output_dir / "data" / "production_lot_events.csv", ["event_id", "day", "lot_id"])
            _write_empty_csv(
                output_dir / "data" / "production_lot_genealogy.csv",
                ["day", "parent_lot_id", "child_lot_id"],
            )

            package_dir = export_run_package(output_dir=output_dir, input_graph=graph_path)
            validations = validate_run_package(package_dir)

            self.assertFalse([row for row in validations if not row["ok"]], validations)
            manifest = json.loads((package_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["capabilities"]["lot_trace_enabled"], False)

    def test_export_run_package_marks_companion_risk_artifacts_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "result"
            graph_path = root / "graph.json"
            _write_json(
                graph_path,
                {
                    "nodes": [{"id": "S1"}, {"id": "M1"}],
                    "edges": [{"id": "E1", "from": "S1", "to": "M1", "items": ["item:A"]}],
                },
            )
            _write_json(
                output_dir / "summaries" / "first_simulation_summary.json",
                {
                    "scenario_id": "scn:base",
                    "sim_days": 1,
                    "timeline_days": 1,
                    "policy": {
                        "output_profile": "compact",
                        "lot_trace_enabled": True,
                        "supplier_state_dependent_risk": {"enabled": False},
                        "supplier_risk": {"enabled": False},
                    },
                    "counts": {"nodes": 2, "edges": 1},
                    "kpis": {},
                },
            )
            _write_csv(output_dir / "data" / "first_simulation_daily.csv", [{"day": 0, "demand": 0}])
            _write_json(
                output_dir / "scenario_runs" / "state_dependent_full" / "run" / "run_manifest.json",
                {"capabilities": {"state_dependent_risk_enabled": True}},
            )
            _write_json(output_dir / "supplier_criticality" / "supplier_criticality_summary.json", {"rows": []})

            package_dir = export_run_package(output_dir=output_dir, input_graph=graph_path)

            manifest = json.loads((package_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["capabilities"]["state_dependent_risk_enabled"], True)
            self.assertEqual(manifest["capabilities"]["supplier_risk_enabled"], True)


if __name__ == "__main__":
    unittest.main()
