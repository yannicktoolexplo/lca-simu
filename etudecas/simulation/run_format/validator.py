"""Validation helpers for generic etudecas run packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from etudecas.simulation.run_format.schema import RUN_PACKAGE_SCHEMA_VERSION


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(validations: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    validations.append({"name": name, "ok": bool(ok), "detail": detail})


def validate_run_package(package_dir: Path | str) -> list[dict[str, Any]]:
    """Return validation rows for a generic run package."""

    root = Path(package_dir)
    validations: list[dict[str, Any]] = []
    manifest_path = root / "run_manifest.json"
    _check(validations, "run_manifest_exists", manifest_path.exists(), str(manifest_path))
    if not manifest_path.exists():
        return validations

    try:
        manifest = _read_json(manifest_path)
    except Exception as exc:
        _check(validations, "run_manifest_json", False, str(exc))
        return validations

    _check(
        validations,
        "schema_version",
        manifest.get("schema_version") == RUN_PACKAGE_SCHEMA_VERSION,
        str(manifest.get("schema_version")),
    )
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    if "lot_trace_enabled" not in capabilities:
        policy_path = root / "policy.json"
        policy = _read_json(policy_path) if policy_path.exists() else {}
        if isinstance(policy, dict) and "lot_trace_enabled" in policy:
            capabilities["lot_trace_enabled"] = bool(policy.get("lot_trace_enabled"))
    lot_trace_enabled = capabilities.get("lot_trace_enabled")
    for key in ("nodes", "flows", "kpis", "artifact_index", "timeseries_index", "lots_index", "events_index"):
        rel = entrypoints.get(key)
        path = root / str(rel or "")
        _check(validations, f"entrypoint:{key}", bool(rel) and path.exists(), str(path))

    nodes_path = root / str(entrypoints.get("nodes") or "nodes.json")
    flows_path = root / str(entrypoints.get("flows") or "flows.json")
    artifact_index_path = root / str(entrypoints.get("artifact_index") or "artifact_index.json")
    if nodes_path.exists():
        nodes = _read_json(nodes_path)
        _check(validations, "nodes_non_empty", isinstance(nodes, list) and len(nodes) > 0, str(len(nodes) if isinstance(nodes, list) else "n/a"))
    if flows_path.exists():
        flows = _read_json(flows_path)
        _check(validations, "flows_non_empty", isinstance(flows, list) and len(flows) > 0, str(len(flows) if isinstance(flows, list) else "n/a"))
    if artifact_index_path.exists():
        artifacts = _read_json(artifact_index_path)
        present = [row for row in artifacts if isinstance(row, dict) and row.get("exists")] if isinstance(artifacts, list) else []
        required_missing = [
            row.get("name")
            for row in artifacts
            if isinstance(row, dict) and row.get("required") and not row.get("exists")
        ] if isinstance(artifacts, list) else ["artifact_index_not_list"]
        _check(validations, "artifacts_present", len(present) > 0, str(len(present)))
        _check(validations, "required_artifacts_present", not required_missing, ", ".join(map(str, required_missing)))
        lot_events = next((row for row in present if row.get("domain") == "lot_events"), None)
        lot_genealogy = next((row for row in present if row.get("domain") == "lot_genealogy"), None)
        lot_events_rows = int((lot_events or {}).get("row_count") or 0)
        lot_genealogy_rows = int((lot_genealogy or {}).get("row_count") or 0)
        _check(
            validations,
            "lot_events_indexed",
            bool(lot_events and (lot_events_rows > 0 or lot_trace_enabled is False)),
            (
                f"{lot_events_rows} rows"
                if lot_trace_enabled is not False
                else f"{lot_events_rows} rows; optional because lot_trace_enabled=false"
            ),
        )
        _check(
            validations,
            "lot_genealogy_indexed",
            bool(lot_genealogy and (lot_genealogy_rows > 0 or lot_trace_enabled is False)),
            (
                f"{lot_genealogy_rows} rows"
                if lot_trace_enabled is not False
                else f"{lot_genealogy_rows} rows; optional because lot_trace_enabled=false"
            ),
        )

    return validations


def assert_run_package_valid(package_dir: Path | str) -> None:
    validations = validate_run_package(package_dir)
    failed = [row for row in validations if not row.get("ok")]
    if not failed:
        return
    lines = ["Generic run package validation failed:"]
    lines.extend(f"- {row['name']}: {row.get('detail', '')}" for row in failed)
    raise RuntimeError("\n".join(lines))
