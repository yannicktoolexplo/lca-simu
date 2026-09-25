"""Compare two replay exports exactly, without importing their producers.

Only data/ and summaries/ are compared; maps, execution times and run manifests
require separate checks. CSV rows are streamed, preserving their order and exact
cell text. JSON numbers use Decimal, without a floating-point tolerance.

Optional metadata rules are a JSON list. Each rule specifies file, kind, before,
after, and either pointer (JSON Pointer) or column (CSV). Example::

    {"file": "summaries/first_simulation_summary.json", "pointer": "/input_file",
     "kind": "path", "before": "before/graph.json", "after": "after/graph.json"}

Rules accept only named technical metadata, exact value pairs, and existing
fields. Every use is reported; unused rules fail. Business dates, quantities,
input hashes and physical/scenario identities cannot be normalized.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path, PurePosixPath
import stat


SCOPES = ("data", "summaries")
METADATA_FIELDS = {
    "path": {"input_file", "input_graph", "output_dir", "source_csv", "events_csv",
             "floors_csv", "capacities_csv", "profile_path", "source_path"},
    "timestamp": {"generated_at_utc", "generated_at", "created_at_utc"},
    "source_identity": {"implementation_sha256", "source_code_sha256", "source_bundle_sha256"},
}
MISSING = object()


def _hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _no_link(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
        raise ValueError(f"Linked paths are not comparison inputs: {path}")


def _root(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        _no_link(part)
    if not path.is_dir():
        raise ValueError(f"Run is not a directory: {path}")
    return path.resolve()


def _inventory(root):
    files = {}
    for scope in SCOPES:
        folder = root / scope
        _no_link(folder)
        if not folder.is_dir():
            raise ValueError(f"Missing export directory: {folder}")
        pending = [folder]
        scope_files = 0
        while pending:
            current = pending.pop()
            for child in sorted(current.iterdir()):
                _no_link(child)
                if child.is_dir():
                    pending.append(child)
                elif child.is_file():
                    files[child.relative_to(root).as_posix()] = child
                    scope_files += 1
                else:
                    raise ValueError(f"Unsupported filesystem entry: {child}")
        if not scope_files:
            raise ValueError(f"Empty export directory: {folder}")
    if not any(name.startswith("data/") and name.endswith(".csv") for name in files):
        raise ValueError("Expected at least one data CSV")
    if not any(name.startswith("summaries/") and name.endswith(".json") for name in files):
        raise ValueError("Expected at least one summary JSON")
    return files


def _pointer(parts):
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _rules(values):
    if not isinstance(values, list):
        raise ValueError("Metadata rules must be a list")
    indexed = {}
    for row in values:
        if not isinstance(row, dict):
            raise ValueError("Each metadata rule must be an object")
        selector = "pointer" if "pointer" in row else "column"
        if set(row) != {"file", "kind", "before", "after", selector}:
            raise ValueError("Rule requires file, kind, before, after and exactly one selector")
        if any(not isinstance(v, str) or not v for v in row.values()):
            raise ValueError("Metadata rule values must be nonempty strings")
        file = PurePosixPath(row["file"])
        if file.as_posix() != row["file"] or file.is_absolute() or ".." in file.parts or "\\" in row["file"] or file.parts[0] not in SCOPES:
            raise ValueError("Rule file must be a relative path inside data/ or summaries/")
        if selector == "pointer":
            if file.suffix != ".json" or not row[selector].startswith("/"):
                raise ValueError("JSON rules require a JSON file and an absolute JSON Pointer")
            field = row[selector].rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        else:
            if file.suffix != ".csv":
                raise ValueError("CSV rules require a CSV file")
            field = row[selector]
        if field not in METADATA_FIELDS.get(row["kind"], set()):
            raise ValueError(f"Not an allowed technical metadata field: {field}")
        if row["before"] == row["after"]:
            raise ValueError("Metadata rule must declare an actual difference")
        if row["kind"] == "timestamp":
            for value in (row["before"], row["after"]):
                datetime.fromisoformat(value.replace("Z", "+00:00"))
        if row["kind"] == "source_identity":
            for value in (row["before"], row["after"]):
                if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                    raise ValueError("Source identities must be explicit lowercase SHA-256 values")
        key = row["file"], selector, row[selector]
        if key in indexed:
            raise ValueError(f"Duplicate metadata rule: {key}")
        indexed[key] = {**row, "uses": 0}
    return indexed


def _allow(rules, file, selector, location, before, after):
    rule = rules.get((file, selector, location))
    if rule is not None and isinstance(before, str) and isinstance(after, str) and before == rule["before"] and after == rule["after"]:
        rule["uses"] += 1
        return True
    return False


def _display(value):
    if value is MISSING:
        return {"missing": True}
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, (dict, list)):
        return {"type": type(value).__name__, "length": len(value)}
    if isinstance(value, str) and len(value) > 300:
        return {"length": len(value), "sha256": hashlib.sha256(value.encode()).hexdigest(), "prefix": value[:160]}
    return value


def _difference(result, location, before, after):
    result["differences"] += 1
    if len(result["examples"]) < 10:
        result["examples"].append({"location": location, "before": _display(before), "after": _display(after)})


def _json(path):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_number(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream, parse_float=Decimal, parse_int=Decimal,
                         parse_constant=invalid_number, object_pairs_hook=object_pairs)


def _compare_json(before, after, parts, result, rules):
    pointer = _pointer(parts)
    if type(before) is not type(after):
        _difference(result, pointer, before, after)
    elif isinstance(before, dict):
        for key in sorted(set(before) | set(after)):
            _compare_json(before.get(key, MISSING), after.get(key, MISSING), [*parts, key], result, rules)
    elif isinstance(before, list):
        for index, (a, b) in enumerate(zip_longest(before, after, fillvalue=MISSING)):
            _compare_json(a, b, [*parts, index], result, rules)
    else:
        result["values_compared"] += 1
        if before != after and not _allow(rules, result["path"], "pointer", pointer, before, after):
            _difference(result, pointer, before, after)


def _compare_csv(before, after, result, rules):
    with before.open(encoding="utf-8-sig", newline="") as a, after.open(encoding="utf-8-sig", newline="") as b:
        left, right = csv.reader(a, strict=True), csv.reader(b, strict=True)
        header_a, header_b = next(left, None), next(right, None)
        for header in (header_a, header_b):
            if not header or len(set(header)) != len(header) or any(not field for field in header):
                raise ValueError("CSV requires a nonempty, unique header")
        if header_a != header_b:
            _difference(result, "header", header_a, header_b)
            return
        for number, (row_a, row_b) in enumerate(zip_longest(left, right, fillvalue=MISSING), 1):
            result["rows_compared"] += 1
            if row_a is MISSING or row_b is MISSING:
                _difference(result, f"row:{number}", row_a, row_b)
                continue
            if len(row_a) != len(header_a) or len(row_b) != len(header_b):
                raise ValueError(f"Malformed CSV row {number}: width differs from header")
            for column, value_a, value_b in zip(header_a, row_a, row_b):
                result["values_compared"] += 1
                if value_a != value_b and not _allow(rules, result["path"], "column", column, value_a, value_b):
                    _difference(result, f"row:{number}/column:{column}", value_a, value_b)


def compare_runs(before, after, metadata_rules=None):
    """Return evidence; no output files or simulation processes are created."""
    report = {"schema": "etudecas.replay_comparison.v1", "ok": False, "scope": list(SCOPES),
              "numeric_tolerance": 0, "csv_cell_comparison": "exact_text_and_order",
              "files": [], "errors": [], "metadata_changes": []}
    try:
        roots = _root(before), _root(after)
        report.update(before=str(roots[0]), after=str(roots[1]))
        if roots[0] == roots[1] or os.path.samefile(*roots):
            raise ValueError("Before and after must be different run directories")
        inventories = _inventory(roots[0]), _inventory(roots[1])
        rules = _rules([] if metadata_rules is None else metadata_rules)
        for file in sorted(set(inventories[0]) | set(inventories[1])):
            item = {"path": file, "differences": 0, "examples": [], "values_compared": 0, "rows_compared": 0}
            report["files"].append(item)
            a, b = inventories[0].get(file), inventories[1].get(file)
            if a is None or b is None:
                _difference(item, "file", "present" if a else MISSING, "present" if b else MISSING)
                continue
            try:
                item.update(before_sha256=_hash(a), after_sha256=_hash(b))
                if a.suffix == ".csv":
                    _compare_csv(a, b, item, rules)
                elif a.suffix == ".json":
                    _compare_json(_json(a), _json(b), [], item, rules)
                elif item["before_sha256"] != item["after_sha256"]:
                    _difference(item, "bytes_sha256", item["before_sha256"], item["after_sha256"])
            except (OSError, ValueError, csv.Error) as exc:
                item["error"] = str(exc)
        report["metadata_changes"] = list(rules.values())
        for rule in rules.values():
            if not rule["uses"]:
                report["errors"].append(f"Unused metadata rule: {rule['file']} {rule.get('pointer', rule.get('column'))}")
        if set(_inventory(roots[0])) != set(inventories[0]) or set(_inventory(roots[1])) != set(inventories[1]):
            raise ValueError("Export inventory changed during comparison")
        for item in report["files"]:
            for inventory, side in zip(inventories, ("before", "after")):
                key = side + "_sha256"
                if key in item and _hash(inventory[item["path"]]) != item[key]:
                    report["errors"].append(f"Export changed during comparison: {side} {item['path']}")
        report["ok"] = not report["errors"] and all(not f["differences"] and "error" not in f for f in report["files"])
    except (OSError, ValueError) as exc:
        report["errors"].append(str(exc))
    report["file_count"] = len(report["files"])
    report["difference_count"] = sum(f["differences"] for f in report["files"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-rules", type=Path)
    args = parser.parse_args(argv)
    try:
        rules = json.loads(args.metadata_rules.read_text(encoding="utf-8-sig")) if args.metadata_rules else []
        if args.output.exists():
            parser.error("Choose a new evidence file; previous evidence is preserved")
        target = args.output.resolve()
        if any(target.is_relative_to(root.resolve()) for root in (args.before, args.after)):
            parser.error("Evidence must be outside both compared run directories")
        report = compare_runs(args.before, args.after, rules)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"ok": report["ok"], "files": report["file_count"], "differences": report["difference_count"], "output": str(args.output)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
