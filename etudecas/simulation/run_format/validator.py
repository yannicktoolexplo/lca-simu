"""Validation helpers for generic etudecas run packages."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from etudecas.simulation.run_format.schema import CANONICAL_DATA_ARTIFACTS, RUN_PACKAGE_SCHEMA_VERSION


def _read_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON number: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def _check(validations: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    validations.append({"name": name, "ok": bool(ok), "detail": detail})


def _load_checked(path: Path, expected: type, validations: list[dict[str, Any]], name: str) -> Any:
    try:
        value = _read_json(path)
        if not isinstance(value, expected):
            raise ValueError(f"Expected {expected.__name__}")
    except (OSError, ValueError, UnicodeError) as exc:
        _check(validations, name, False, str(exc))
        return None
    _check(validations, name, True)
    return value


def _validate_artifact(row: dict[str, Any], output: Path, validations: list[dict[str, Any]]) -> int | None:
    """Check the physical file; stream CSV data without retaining its rows."""
    name = f"artifact:{row.get('name')}"
    try:
        if not isinstance(row.get("path"), str) or not row["path"].strip():
            raise ValueError("Missing artifact path")
        path = output / row["path"]
        present = path.is_file()
        if type(row.get("exists")) is not bool or row["exists"] != present:
            raise ValueError(f"exists flag differs from physical file: {path}")
        if type(row.get("required")) is not bool:
            raise ValueError("required must be boolean")
        if not present:
            if row["required"] or path.exists():
                raise ValueError(f"Missing required file or path is not a file: {path}")
            _check(validations, name, True, "Optional artifact absent")
            return None
        count = None
        if row.get("format") == "csv":
            with path.open(encoding="utf-8", newline="") as stream:
                reader = csv.reader(stream, strict=True)
                columns = next(reader, [])
                if not columns or any(not col.strip() for col in columns) or len(set(columns)) != len(columns):
                    raise ValueError("CSV header must contain unique non-empty columns")
                if row.get("columns") != columns:
                    raise ValueError("CSV columns differ from index")
                count = 0
                for values in reader:
                    if not values:  # Match DictReader's handling of blank lines.
                        continue
                    if len(values) != len(columns):
                        raise ValueError(f"CSV row {reader.line_num} has wrong field count")
                    count += 1
            if type(row.get("row_count")) is not int or row["row_count"] != count:
                raise ValueError(f"row_count differs from physical CSV ({count})")
        elif row.get("format") == "json":
            _read_json(path)
            if "size_bytes" in row and (type(row["size_bytes"]) is not int or row["size_bytes"] != path.stat().st_size):
                raise ValueError("JSON size differs from index")
        else:
            raise ValueError("Unsupported artifact format")
        _check(validations, name, True)
        return count
    except (OSError, ValueError, UnicodeError, csv.Error) as exc:
        _check(validations, name, False, str(exc))
        return None


def validate_run_package(package_dir: Path | str) -> list[dict[str, Any]]:
    """Validate package structure and physical artifacts, not simulation accuracy."""
    root = Path(package_dir)
    validations: list[dict[str, Any]] = []
    manifest_path = root / "run_manifest.json"
    _check(validations, "run_manifest_exists", manifest_path.is_file(), str(manifest_path))
    if not manifest_path.is_file():
        return validations
    manifest = _load_checked(manifest_path, dict, validations, "run_manifest_json")
    if manifest is None:
        return validations
    _check(validations, "schema_version", manifest.get("schema_version") == RUN_PACKAGE_SCHEMA_VERSION,
           str(manifest.get("schema_version")))
    entrypoints = manifest.get("entrypoints")
    if not isinstance(entrypoints, dict):
        _check(validations, "entrypoints", False, "Expected object")
        return validations
    documents = {}
    for key in ("nodes", "flows", "kpis", "artifact_index", "timeseries_index", "lots_index", "events_index", "diagnostics_index"):
        if key == "diagnostics_index" and key not in entrypoints:
            continue
        rel = entrypoints.get(key)
        if not isinstance(rel, str) or not rel.strip():
            _check(validations, f"entrypoint:{key}", False, "Missing path")
            continue
        documents[key] = _load_checked(root / rel, dict if key == "kpis" else list,
                                       validations, f"entrypoint:{key}")
    node_ids: set[str] = set()
    for key in ("nodes", "flows"):
        rows = documents.get(key)
        _check(validations, f"{key}_non_empty", bool(rows))
        if not isinstance(rows, list):
            continue
        ids = [row.get("id") for row in rows if isinstance(row, dict)]
        valid = len(ids) == len(rows) and all(isinstance(value, str) and value.strip() for value in ids)
        valid = bool(valid and len(set(ids)) == len(ids))
        _check(validations, f"{key}_unique_ids", valid, "Non-empty unique string IDs required")
        if key == "nodes" and valid:
            node_ids = set(ids)
        if key == "flows":
            linked = all(isinstance(row, dict) and isinstance(row.get("from"), str)
                         and isinstance(row.get("to"), str) and row["from"] in node_ids
                         and row["to"] in node_ids for row in rows)
            _check(validations, "flow_node_references", linked, "Flow endpoints must reference package nodes")
    capabilities = manifest.get("capabilities", {})
    _check(validations, "capabilities_object", isinstance(capabilities, dict))
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    lot_trace_enabled = capabilities.get("lot_trace_enabled")
    if "lot_trace_enabled" not in capabilities and (root / "policy.json").exists():
        policy = _load_checked(root / "policy.json", dict, validations, "policy_json")
        lot_trace_enabled = (policy or {}).get("lot_trace_enabled")
    _check(validations, "lot_trace_enabled_boolean", lot_trace_enabled is None or type(lot_trace_enabled) is bool)
    output_value = manifest.get("output_dir")
    if output_value is not None and (not isinstance(output_value, str) or not output_value.strip()):
        _check(validations, "output_dir", False, "Expected non-empty path")
        return validations
    output = Path(output_value) if output_value else root.parent
    artifacts = documents.get("artifact_index")
    if not isinstance(artifacts, list):
        return validations
    names = [row.get("name") for row in artifacts if isinstance(row, dict)]
    valid_names = len(names) == len(artifacts) and all(isinstance(name, str) and name.strip() for name in names)
    valid_names = bool(valid_names and len(set(names)) == len(names))
    _check(validations, "artifact_unique_names", valid_names)
    if not valid_names:
        return validations
    indexed = {row["name"]: row for row in artifacts}
    actual_counts = {row["name"]: _validate_artifact(row, output, validations) for row in artifacts}
    for spec in CANONICAL_DATA_ARTIFACTS:
        if not spec.required:
            continue
        row = indexed.get(spec.filename, {})
        count = actual_counts.get(spec.filename)
        valid = (row.get("required") is True and row.get("domain") == spec.domain
                 and row.get("group") == spec.group and row.get("format") == "csv"
                 and count is not None and (count > 0 or (spec.group == "lots" and lot_trace_enabled is False)))
        _check(validations, f"required_artifact:{spec.filename}", valid,
               "Required CSV must be present and non-empty; empty lot CSV allowed only when tracing is disabled")
    _check(validations, "artifacts_present", any(row.get("exists") is True for row in artifacts))
    for group in ("timeseries", "lots", "events", "diagnostics"):
        key = f"{group}_index"
        if key in documents:
            expected = [row for row in artifacts if row.get("group") == group]
            _check(validations, f"{key}_consistent", documents[key] == expected,
                   "Group index must match artifact_index entries in order")
    return validations


def assert_run_package_valid(package_dir: Path | str) -> None:
    validations = validate_run_package(package_dir)
    failed = [row for row in validations if not row.get("ok")]
    if not failed:
        return
    lines = ["Generic run package validation failed:"]
    lines.extend(f"- {row['name']}: {row.get('detail', '')}" for row in failed)
    raise RuntimeError("\n".join(lines))
