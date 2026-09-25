"""Regression tests grouped by business responsibility; original cases retained."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import pytest
from etudecas.testing.replay_comparison import compare_runs
import hashlib
from etudecas.testing.inventory import compare_inventory


# Replay comparison

def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerows(rows)


@pytest.fixture
def runs(tmp_path):
    roots = [tmp_path / "before", tmp_path / "after"]
    for root in roots:
        (root / "data").mkdir(parents=True)
        (root / "summaries").mkdir()
        write_csv(root / "data/events.csv", [["day", "qty", "uom"], [0, 20, "UN"], [1, 3, "UN"]])
        (root / "summaries/summary.json").write_text('{"total":23,"cost":null,"available":true,"input_file":"same.json"}', encoding="utf-8")
    return roots


def summary(root, value):
    (root / "summaries/summary.json").write_text(json.dumps(value), encoding="utf-8")


def test_equal_exports_and_declared_scope(runs):
    (runs[0] / "timing.txt").write_text("different metadata outside scope")
    result = compare_runs(*runs)
    assert result["ok"] and result["file_count"] == 2
    assert result["scope"] == ["data", "summaries"]
    assert result["files"][0]["rows_compared"] == 2
    assert result["metadata_changes"] == []


@pytest.mark.parametrize("rows", [
    [["day", "qty", "uom"], [0, "20.000000000000000001", "UN"], [1, 3, "UN"]],
    [["day", "qty", "uom"], [2, 20, "UN"], [1, 3, "UN"]],
    [["day", "qty", "uom"], [0, 20, "KG"], [1, 3, "UN"]],
    [["day", "qty", "uom"], [1, 3, "UN"], [0, 20, "UN"]],
    [["day", "qty", "uom"], [0, 20, "UN"]],
    [["day", "qty", "uom"], [0, 20, "UN"], [1, 3, "UN"], [2, 4, "UN"]],
    [["qty", "day", "uom"], [20, 0, "UN"], [3, 1, "UN"]],
    [["day", "qty", "qty"], [0, 20, "UN"], [1, 3, "UN"]],
    [["day", "qty", "uom"], [0, 20, "UN", "extra"]],
])
def test_csv_business_changes_and_malformed_rows_fail(runs, rows):
    write_csv(runs[1] / "data/events.csv", rows)
    assert not compare_runs(*runs)["ok"]


@pytest.mark.parametrize("value", [
    {"total": 24, "cost": None, "available": True, "input_file": "same.json"},
    {"total": 23, "cost": 0, "available": True, "input_file": "same.json"},
    {"total": 23, "cost": None, "available": 1, "input_file": "same.json"},
    {"total": 23, "cost": None, "available": True},
    {"total": 23, "cost": None, "available": True, "input_file": "other.json"},
])
def test_json_business_changes_missing_fields_and_unknown_paths_fail(runs, value):
    summary(runs[1], value)
    assert not compare_runs(*runs)["ok"]


@pytest.mark.parametrize("text", ['{"total":23.000000000000000001}', '{"total":NaN}', '{"total":23,"total":23}'])
def test_decimal_precision_nonfinite_and_duplicate_keys(runs, text):
    summary(runs[0], {"total": 23})
    (runs[1] / "summaries/summary.json").write_text(text)
    assert not compare_runs(*runs)["ok"]


def test_exact_json_numeric_value_not_binary_float_approximation(runs):
    (runs[0] / "summaries/summary.json").write_text('{"value":100000000000000000000001}')
    (runs[1] / "summaries/summary.json").write_text('{"value":100000000000000000000001.0}')
    assert compare_runs(*runs)["ok"]


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_same_complete_file_inventory_required(runs, change):
    if change == "missing":
        (runs[1] / "data/events.csv").unlink()
    else:
        (runs[1] / "data/extra.csv").write_text("qty\n1\n")
    assert not compare_runs(*runs)["ok"]


def rule(kind="path", field="input_file", before="old.json", after="new.json"):
    return {"file": "summaries/summary.json", "pointer": "/" + field,
            "kind": kind, "before": before, "after": after}


def test_exact_metadata_pairs_are_reported_and_other_fields_still_checked(runs):
    rules = [rule(), rule("timestamp", "generated_at_utc", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
             rule("source_identity", "implementation_sha256", "a" * 64, "b" * 64)]
    for index, root in enumerate(runs):
        summary(root, {**{r["pointer"][1:]: r[("before", "after")[index]] for r in rules}, "qty": 3})
    result = compare_runs(*runs, rules)
    assert result["ok"] and [r["uses"] for r in result["metadata_changes"]] == [1, 1, 1]
    obj = json.loads((runs[1] / "summaries/summary.json").read_text())
    obj["qty"] = 4
    summary(runs[1], obj)
    assert not compare_runs(*runs, rules)["ok"]


@pytest.mark.parametrize("bad_rule", [
    rule(field="qty"), rule(field="day"), rule(field="snapshot_date"),
    rule(field="scenario_id"), rule("source_identity", "input_sha256", "a" * 64, "b" * 64),
    {**rule(), "ignore": True}, {**rule(), "file": "../other.json"},
    {**rule(), "file": "summaries/../summary.json"}, rule(after="old.json"),
])
def test_rules_cannot_exempt_business_fields_or_unknown_options(runs, bad_rule):
    assert not compare_runs(*runs, [bad_rule])["ok"]


def test_unused_wrong_pair_and_duplicate_rules_fail(runs):
    assert not compare_runs(*runs, [rule()])["ok"]
    summary(runs[0], {"input_file": "old.json"})
    summary(runs[1], {"input_file": "unexpected.json"})
    assert not compare_runs(*runs, [rule()])["ok"]
    assert not compare_runs(*runs, [rule(), rule()])["ok"]


def test_csv_metadata_stream_is_exact_and_counted(runs):
    for root, source in zip(runs, ["old.csv", "new.csv"]):
        write_csv(root / "data/events.csv", [["day", "qty", "source_csv"], [0, 20, source], [1, 3, source]])
    rules = [{"file": "data/events.csv", "column": "source_csv", "kind": "path", "before": "old.csv", "after": "new.csv"}]
    result = compare_runs(*runs, rules)
    assert result["ok"] and result["metadata_changes"][0]["uses"] == 2


def test_empty_and_identical_roots_are_not_success(runs, tmp_path):
    assert not compare_runs(runs[0], runs[0])["ok"]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not compare_runs(empty, runs[0])["ok"]
    (empty / "data").mkdir()
    (empty / "summaries").mkdir()
    assert not compare_runs(empty, runs[0])["ok"]


def test_external_symlink_is_not_followed(runs, tmp_path):
    target = tmp_path / "external.csv"
    target.write_text("qty\n999\n")
    link = runs[0] / "data/external.csv"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("This account cannot create symbolic links")
    result = compare_runs(*runs)
    assert not result["ok"] and "Linked paths" in result["errors"][0]


def test_windows_reparse_point_is_rejected_without_following_it(runs, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    import stat

    original = Path.lstat
    def reparse(path, *args, **kwargs):
        if path == runs[0] / "data":
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=1024)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", reparse)
    result = compare_runs(*runs)
    assert not result["ok"] and "Linked paths" in result["errors"][0]


def test_export_changed_later_in_comparison_is_detected(runs, monkeypatch):
    import etudecas.testing.replay_comparison as module

    original = module._compare_json
    def change_previous_csv(*args):
        (runs[1] / "data/events.csv").write_text("day,qty,uom\n0,999,UN\n")
        return original(*args)

    monkeypatch.setattr(module, "_compare_json", change_previous_csv)
    result = compare_runs(*runs)
    assert not result["ok"] and any("changed during comparison" in error for error in result["errors"])


def test_cli_exit_status_and_preserved_evidence(runs, tmp_path):
    output = tmp_path / "proof.json"
    command = [sys.executable, "-B", "-m", "etudecas.testing.replay_comparison",
               "--before", str(runs[0]), "--after", str(runs[1]), "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    assert json.loads(original)["ok"]
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == original
    summary(runs[1], {"qty": 42})
    command[-1] = str(tmp_path / "failed.json")
    assert subprocess.run(command, capture_output=True).returncode == 1
    assert not json.loads((tmp_path / "failed.json").read_text())["ok"]


def test_csv_is_streamed_without_read_text(runs, monkeypatch):
    from pathlib import Path

    def forbidden(*args, **kwargs):
        raise AssertionError("CSV comparison must stream, not read the whole file")

    monkeypatch.setattr(Path, "read_text", forbidden)
    assert compare_runs(*runs)["ok"]


# Inventory

def reference(tmp_path, rows, repo=None):
    payload = {"entries": rows, "entry_count": len(rows), "repo": str(repo or tmp_path)}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode()).hexdigest()
    payload["inventory_signature"] = signature
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, signature


def test_inventory_distinguishes_representation_content_and_missing_without_writes(tmp_path):
    rows = []
    for name, raw in [("exact.py", b"x\n"), ("windows.py", b"x\r\n"),
                      ("changed.py", b"y\n"), ("missing.py", None)]:
        if raw is not None:
            (tmp_path / name).write_bytes(raw)
        rows.append({"relative_path": name, "sha256": hashlib.sha256(b"x\n").hexdigest(), "size_bytes": 2})
    path, signature = reference(tmp_path, rows, repo="historical-root")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = compare_inventory(tmp_path, path, signature)
    assert result["counts"] == {"exact_match": 1, "line_endings_only": 1, "content_mismatch": 1, "missing": 1}
    assert not result["repo_matches"] and not result["exact_match"]
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="signature"):
        compare_inventory(tmp_path, path, "0" * 64)


@pytest.mark.parametrize("name", ["../outside.py", "C:/outside.py", "/outside.py"])
def test_inventory_rejects_escaping_paths(tmp_path, name):
    path, signature = reference(tmp_path, [{"relative_path": name, "sha256": "0" * 64, "size_bytes": 0}])
    with pytest.raises(ValueError, match="path"):
        compare_inventory(tmp_path, path, signature)
