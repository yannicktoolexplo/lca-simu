from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

from etudecas.simulation.run_format import export_run_package, load_run_package, validate_run_package
from etudecas.simulation.run_format.exporter import _csv_profile
from etudecas.simulation.run_format import exporter as run_exporter
from etudecas.simulation.run_format.schema import ArtifactSpec


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


def _dictreader_csv_profile_reference(path: Path) -> dict:
    """Frozen pre-optimization oracle: read rows through the standard DictReader."""
    if not path.exists():
        return {"exists": False, "row_count": 0, "columns": []}
    row_count = 0
    min_day = max_day = None
    sample_entities = defaultdict(set)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = list(reader.fieldnames or [])
        day_field = next((field for field in ("day", "jour") if field in columns), None)
        entity_fields = [field for field in (
            "node_id", "source_node_id", "src_node_id", "from_node_id", "supplier_id",
            "item_id", "output_item_id", "parent_item_id", "child_item_id",
            "lot_id", "parent_lot_id", "child_lot_id",
        ) if field in columns]
        for row in reader:
            row_count += 1
            if day_field:
                try:
                    day = int(round(float(row.get(day_field) or 0)))
                except (TypeError, ValueError):
                    day = None
                if day is not None:
                    min_day = day if min_day is None else min(min_day, day)
                    max_day = day if max_day is None else max(max_day, day)
            if row_count <= 500:
                for field in entity_fields:
                    value = str(row.get(field) or "")
                    if value:
                        sample_entities[field].add(value)
    profile = {"exists": True, "row_count": row_count, "columns": columns}
    if min_day is not None or max_day is not None:
        profile["day_range"] = {"min": min_day, "max": max_day}
    if sample_entities:
        profile["sample_entities"] = {key: sorted(values)[:25]
                                      for key, values in sorted(sample_entities.items())}
    return profile


class CsvProfileEquivalenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "profile.csv"

    def assert_matches_reference(self) -> dict:
        expected = _dictreader_csv_profile_reference(self.path)
        actual = _csv_profile(self.path)
        self.assertEqual(actual, expected)
        self.assertEqual(json.dumps(actual, ensure_ascii=False), json.dumps(expected, ensure_ascii=False))
        return actual

    def test_missing_empty_and_atypical_csv_match_dictreader(self) -> None:
        self.assert_matches_reference()
        contents = (
            "", "\n", "\n\n", "day,node_id\r\n", '\"\"\n\"\"\n',
            "\n\nday,node_id\n1,N1\n\n",  # A blank first header stays blank.
            "day,node_id\n\n1,N1\n\n,\n2\n3,N3,extra\n",
            'day,node_id,item_id\r\n1,"node,one","item\r\nmultiline"\r\n',
            'jour,lot_id\r-1.5,"lot \"\"quoted\"\""\r2.5,L2\r',
            'node_id,child_lot_id\n"é","L\n2"\n  ,0\n',
            'day,node_id\n1,"unterminated',  # Default CSV parsing is deliberately non-strict.
            '\ufeffday,node_id\n1,N1\n',  # UTF-8 BOM is not stripped by the existing contract.
        )
        for content in contents:
            with self.subTest(content=content):
                self.path.write_bytes(content.encode("utf-8"))
                self.assert_matches_reference()

    def test_duplicate_headers_use_last_value_even_when_missing(self) -> None:
        self.path.write_text(
            "day,node_id,day,node_id,item_id,item_id\n"
            "91,old,4,new,old-item,new-item\n"
            "92,ignored\n"
            "93,old,bad,newer,old-item\n"
            "94,old,5,last,old-item,last-item,extra\n", encoding="utf-8",
        )
        actual = self.assert_matches_reference()
        self.assertEqual(actual["day_range"], {"min": 0, "max": 5})
        self.assertEqual(actual["sample_entities"], {
            "item_id": ["last-item", "new-item"], "node_id": ["last", "new", "newer"],
        })

    def test_day_priority_rounding_invalid_and_empty_values(self) -> None:
        self.path.write_text(
            "jour,day\n999,2.5\n-999,-2.5\n888,3.5\n-888,-3.5\n"
            "777,bad\n777,nan\n777, \n777,\n777\n", encoding="utf-8",
        )
        actual = self.assert_matches_reference()
        self.assertEqual(actual["day_range"], {"min": -4, "max": 4})
        self.assertEqual(actual["row_count"], 9)
        self.path.write_text("day\nbad\nnan\n", encoding="utf-8")
        self.assertNotIn("day_range", self.assert_matches_reference())

    def test_infinite_day_preserves_existing_overflow_error(self) -> None:
        for value in ("inf", "-inf", "1e9999"):
            with self.subTest(value=value):
                self.path.write_text(f"day\n{value}\n", encoding="utf-8")
                with self.assertRaises(OverflowError):
                    _dictreader_csv_profile_reference(self.path)
                with self.assertRaises(OverflowError):
                    _csv_profile(self.path)

    def test_entities_use_first_500_records_then_sorted_first_25_values(self) -> None:
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["day", "node_id", "item_id"])
            for index in range(500):
                if index % 7 == 0:
                    writer.writerow([])
                writer.writerow([index, f"N-{499-index:04d}", "I-constant"])
            writer.writerow([500, "A-only-after-500", "I-only-after-500"])
        actual = self.assert_matches_reference()
        self.assertEqual(actual["row_count"], 501)
        self.assertEqual(actual["day_range"], {"min": 0, "max": 500})
        self.assertEqual(actual["sample_entities"], {
            "item_id": ["I-constant"], "node_id": [f"N-{index:04d}" for index in range(25)],
        })

    def test_generated_ragged_duplicate_and_quoted_rows_match_dictreader(self) -> None:
        rng = random.Random(9102)
        fields = ["day", "jour", "node_id", "item_id", "lot_id", "parent_lot_id",
                  "child_lot_id", "source_node_id", "output_item_id", "unused", ""]
        values = ["", "0", "-0", "2.5", "-3.5", "1e2", "nan", "invalid", "é", "a,b", 'a"b', "a\nb"]
        for case in range(60):
            with self.subTest(case=case):
                columns = [rng.choice(fields) for _ in range(rng.randrange(12))]
                with self.path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(columns)
                    for _ in range(40):
                        writer.writerow([rng.choice(values) for _ in range(rng.randrange(15))])
                self.assert_matches_reference()


class WrittenCsvProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "lot_causal_links.csv"

    def write_rows(self, fields, rows):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            hashing_writer = run_exporter.CsvHashingWriter(stream)
            writer = csv.DictWriter(hashing_writer, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        self.written_sha256 = hashing_writer.hexdigest()
        return self.path.stat()

    def written_profile(self, fields, rows, stat):
        return run_exporter.profile_written_csv(
            self.path, fields, rows, stat, written_sha256=self.written_sha256,
        )

    def artifact(self, hint, path=None):
        return run_exporter._artifact_record(
            ArtifactSpec("lot_causal_links.csv", "lots", "lot_causal_links", "causal_relation"),
            path=self.path if path is None else path, output_dir=self.root, written_profile=hint,
        )

    def assert_physical_read(self, hint, path=None):
        target = self.path if path is None else path
        expected = _dictreader_csv_profile_reference(target)
        with patch.object(run_exporter, "_csv_profile", wraps=run_exporter._csv_profile) as physical:
            actual = self.artifact(hint, path)
        physical.assert_called_once_with(target)
        self.assertEqual({key: actual[key] for key in expected}, expected)

    def test_written_cells_match_independent_dictreader_without_changing_bytes(self) -> None:
        cases = [
            (["jour", "day", "node_id", "node_id", "item_id", "lot_id", "unused"], [
                {"jour": 999, "day": -3.5, "node_id": 0, "item_id": False, "lot_id": -0.0},
                {"day": 2.5, "node_id": 'N,"quoted"\r\nrow', "item_id": "é", "unused": "a\x00b"},
                {"day": None, "node_id": None, "item_id": 0},
                {"day": True, "node_id": False, "lot_id": True},
                {"day": float("nan"), "item_id": "nan day excluded"},
                {"day": "bad"}, {},
            ]),
            (["day", "node_id"], []),
            ([""], [{"": ""}, {"": None}]),
            ([], [{}, {}]),
            (["jour", "child_lot_id"], [{"jour": "-2.5", "child_lot_id": "L\n1"}]),
        ]
        for fields, rows in cases:
            with self.subTest(fields=fields, rows=rows):
                stat = self.write_rows(fields, rows)
                original = self.path.read_bytes()
                hint = self.written_profile(fields, rows, stat)
                self.assertIsNotNone(hint)
                self.assertEqual(hint["profile"], _dictreader_csv_profile_reference(self.path))
                self.assertEqual(self.path.read_bytes(), original)
                with patch.object(run_exporter, "_csv_profile", side_effect=AssertionError("Unexpected CSV reread")):
                    self.assertEqual(self.artifact(hint)["row_count"], hint["profile"]["row_count"])

    def test_hashing_writer_preserves_standard_csv_bytes_and_hash(self) -> None:
        fields = ["day", "node_id", "unused"]
        rows = [{"day": None, "node_id": 'é,"quoted"\r\n\x00', "unused": False},
                {"day": -0.0, "node_id": True, "unused": "x" * 131073}]
        for records in ([], rows):
            with self.subTest(empty=not records):
                self.write_rows(fields, records)
                standard_path = self.root / "standard.csv"
                with standard_path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(records)
                self.assertEqual(self.path.read_bytes(), standard_path.read_bytes())
                self.assertEqual(self.written_sha256, hashlib.sha256(standard_path.read_bytes()).hexdigest())

    def test_same_stat_rewrite_is_rejected_by_physical_content_hash(self) -> None:
        fields, rows = ["day", "lot_id"], [{"day": 1, "lot_id": "A"}]
        for rewrite_before_profile in (False, True):
            with self.subTest(rewrite_before_profile=rewrite_before_profile):
                stat = self.write_rows(fields, rows)
                signature = run_exporter._csv_file_signature(stat)
                hint = self.written_profile(fields, rows, stat)
                original_digest = self.written_sha256
                self.path.write_bytes(self.path.read_bytes().replace(b"1,A", b"9,Z"))
                self.assertEqual(self.path.stat().st_size, stat.st_size)
                self.assertNotEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), original_digest)
                # Reproduce Windows' observed unchanged-stat collision deterministically.
                with patch.object(run_exporter, "_csv_file_signature", return_value=signature):
                    if rewrite_before_profile:
                        hint = self.written_profile(fields, rows, stat)
                    self.assertIsNotNone(hint)
                    self.assert_physical_read(hint)
                    actual = self.artifact(hint)
                self.assertEqual(actual["day_range"], {"min": 9, "max": 9})
                self.assertEqual(actual["sample_entities"], {"lot_id": ["Z"]})

    def test_missing_digest_never_accepts_stat_only_hint(self) -> None:
        fields, rows = ["day"], [{"day": 1}]
        stat = self.write_rows(fields, rows)
        for digest in (None, "", "g" * 64, "a" * 63, 123):
            with self.subTest(digest=digest):
                self.assertIsNone(run_exporter.profile_written_csv(
                    self.path, fields, rows, stat, written_sha256=digest,
                ))
        hint = self.written_profile(fields, rows, stat)
        del hint["sha256"]
        self.assert_physical_read(hint)

    def test_hashing_writer_rejects_short_write(self) -> None:
        class ShortWriter:
            def write(self, text):
                return len(text) - 1

        with self.assertRaisesRegex(OSError, "complete text write"):
            run_exporter.CsvHashingWriter(ShortWriter()).write("day\r\n")

    def test_written_profile_retains_500_record_and_25_sorted_entity_limits(self) -> None:
        rows = [{"day": i, "node_id": f"N-{499-i:04d}"} for i in range(500)]
        rows.append({"day": 500, "node_id": "A-only-after-500"})
        fields = ["day", "node_id"]
        stat = self.write_rows(fields, rows)
        hint = self.written_profile(fields, rows, stat)
        self.assertEqual(hint["profile"], _dictreader_csv_profile_reference(self.path))
        self.assertEqual(hint["profile"]["sample_entities"]["node_id"], [f"N-{i:04d}" for i in range(25)])
        self.assertEqual(hint["profile"]["day_range"], {"min": 0, "max": 500})

    def test_changed_or_deleted_file_forces_physical_read(self) -> None:
        fields, rows = ["day", "node_id"], [{"day": 1, "node_id": "N"}]
        for operation in ("append", "same_size", "delete"):
            with self.subTest(operation=operation):
                stat = self.write_rows(fields, rows)
                hint = self.written_profile(fields, rows, stat)
                if operation == "append":
                    with self.path.open("a", encoding="utf-8", newline="") as stream:
                        csv.writer(stream).writerow([8, "M"])
                elif operation == "same_size":
                    self.path.write_bytes(self.path.read_bytes().replace(b"1,N", b"9,N"))
                    os.utime(self.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
                else:
                    self.path.unlink()
                self.assertIsNone(self.written_profile(fields, rows, stat))
                self.assert_physical_read(hint)

    def test_replaced_same_size_same_mtime_file_and_wrong_path_force_physical_read(self) -> None:
        fields, rows = ["day", "node_id"], [{"day": 1, "node_id": "N"}]
        stat = self.write_rows(fields, rows)
        hint = self.written_profile(fields, rows, stat)
        other = self.root / "replacement.csv"
        other.write_bytes(self.path.read_bytes().replace(b"1,N", b"9,N"))
        os.utime(other, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assert_physical_read(hint, other)
        other.replace(self.path)
        self.assertEqual(self.path.stat().st_size, stat.st_size)
        self.assertEqual(self.path.stat().st_mtime_ns, stat.st_mtime_ns)
        self.assert_physical_read(hint)

    def test_file_change_during_profile_is_rejected(self) -> None:
        fields, rows = ["day"], [{"day": 1}]
        stat = self.write_rows(fields, rows)
        original = run_exporter._profile_csv_records

        def changed(columns, records):
            result = original(columns, records)
            self.path.write_text("day\n99\n", encoding="utf-8")
            return result

        with patch.object(run_exporter, "_profile_csv_records", side_effect=changed):
            self.assertIsNone(self.written_profile(fields, rows, stat))

    def test_unsupported_cell_or_header_uses_physical_reader(self) -> None:
        class StableCell:
            def __str__(self):
                return "custom cell"

        for fields, rows in ((["day", "node_id"], [{"day": 2, "node_id": StableCell()}]),
                             ([None, "day"], [{None: "N", "day": 3}])):
            with self.subTest(fields=fields):
                stat = self.write_rows(fields, rows)
                hint = self.written_profile(fields, rows, stat)
                self.assertIsNone(hint)
                self.assert_physical_read(hint)

    def test_profile_failure_is_deferred_to_normal_physical_read(self) -> None:
        fields, rows = ["day"], [{"day": float("inf")}]
        stat = self.write_rows(fields, rows)
        self.assertIsNone(self.written_profile(fields, rows, stat))
        with self.assertRaises(OverflowError):
            self.artifact(None)
        old_limit = csv.field_size_limit()
        try:
            fields, rows = ["day", "unused"], [{"day": 1, "unused": "x" * 65}]
            stat = self.write_rows(fields, rows)
            hint = self.written_profile(fields, rows, stat)
            self.assertIsNotNone(hint)
            csv.field_size_limit(64)
            with self.assertRaises(csv.Error):
                self.artifact(hint)
            self.assertIsNone(self.written_profile(fields, rows, stat))
            with self.assertRaises(csv.Error):
                self.artifact(None)
        finally:
            csv.field_size_limit(old_limit)

    def test_export_hint_applies_only_to_declared_causal_link_file(self) -> None:
        data = self.root / "data"
        data.mkdir()
        self.path = data / "lot_causal_links.csv"
        fields, rows = ["day", "node_id"], [{"day": 1, "node_id": "N"}]
        stat = self.write_rows(fields, rows)
        hint = self.written_profile(fields, rows, stat)
        with patch.object(run_exporter, "_csv_profile", wraps=run_exporter._csv_profile) as physical:
            package = export_run_package(output_dir=self.root, lot_causal_link_profile=hint)
        physical_paths = [call.args[0].resolve() for call in physical.call_args_list]
        self.assertNotIn(self.path.resolve(), physical_paths)
        self.assertIn((data / "first_simulation_daily.csv").resolve(), physical_paths)
        index = json.loads((package / "artifact_index.json").read_text(encoding="utf-8"))
        self.assertEqual(next(row for row in index if row["name"] == "lot_causal_links.csv")["row_count"], 1)


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
