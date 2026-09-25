"""Export a simulation result folder to the generic run package contract."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from etudecas.simulation.run_format.schema import (
    CANONICAL_DATA_ARTIFACTS,
    DAY_FIELD_CANDIDATES,
    ITEM_FIELD_CANDIDATES,
    NODE_FIELD_CANDIDATES,
    RUN_PACKAGE_SCHEMA_VERSION,
    ArtifactSpec,
)
from etudecas.simulation.lot_trace.schema import LOT_TRACE_CONTRACT_VERSION


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(root.resolve(strict=False))).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _profile_csv_records(columns: list[str], rows: Iterable[list[str]]) -> dict[str, Any]:
    row_count = 0
    min_day: int | None = None
    max_day: int | None = None
    sample_entities: dict[str, set[str]] = defaultdict(set)

    # DictReader keeps the last occurrence of a duplicate header, including
    # when that occurrence has no value in a short row.
    column_indexes = {field: index for index, field in enumerate(columns)}
    day_field = next((field for field in DAY_FIELD_CANDIDATES if field in columns), None)
    day_index = column_indexes[day_field] if day_field is not None else None
    entity_indexes = [
        (field, column_indexes[field])
        for field in (*NODE_FIELD_CANDIDATES, *ITEM_FIELD_CANDIDATES, "lot_id", "parent_lot_id", "child_lot_id")
        if field in columns
    ]
    for row in rows:
        if not row:  # DictReader skips blank records, but counts [""] or ["", ""].
            continue
        row_count += 1
        row_length = len(row)
        if day_index is not None:
            raw_day = row[day_index] if day_index < row_length else ""
            try:
                day = int(round(float(raw_day or 0)))
            except (TypeError, ValueError):
                day = None
            if day is not None:
                min_day = day if min_day is None else min(min_day, day)
                max_day = day if max_day is None else max(max_day, day)
        if row_count <= 500:
            for field, index in entity_indexes:
                value = row[index] if index < row_length else ""
                if value:
                    sample_entities[field].add(value)

    profile: dict[str, Any] = {
        "exists": True,
        "row_count": row_count,
        "columns": columns,
    }
    if min_day is not None or max_day is not None:
        profile["day_range"] = {"min": min_day, "max": max_day}
    if sample_entities:
        profile["sample_entities"] = {
            key: sorted(values)[:25]
            for key, values in sorted(sample_entities.items())
        }
    return profile


def _csv_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "row_count": 0, "columns": []}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        return _profile_csv_records(next(reader, []), reader)


def _csv_file_signature(stat: Any) -> tuple[int, ...]:
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


class CsvHashingWriter:
    """Hash the exact text sent to a UTF-8 stream opened with newline=''."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._digest = hashlib.sha256()

    def write(self, text: str) -> int:
        written = self._stream.write(text)
        if written != len(text):
            raise OSError("CSV hashing writer requires a complete text write")
        self._digest.update(text.encode("utf-8"))
        return written

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


def profile_written_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
    written_stat: Any,
    *,
    written_sha256: str | None = None,
) -> dict[str, Any] | None:
    """Profile unchanged built-in cells just written by the default DictWriter.

    This is a transient producer hint, never a persisted file-verification
    result. The SHA must be captured by CsvHashingWriter during the original
    write, and is checked against the physical file before using this hint.
    Unsupported cells/headers, changed files or profiling errors fall back to
    the normal physical CSV read when the run package is exported.
    """
    if (written_stat is None or not all(type(field) is str for field in fieldnames)
            or not isinstance(written_sha256, str) or len(written_sha256) != 64
            or any(char not in "0123456789abcdef" for char in written_sha256)):
        return None
    try:
        field_limit = csv.field_size_limit()
        if any(len(field) > field_limit for field in fieldnames):
            return None
        signature = _csv_file_signature(written_stat)
        if _csv_file_signature(path.stat()) != signature:
            return None

        def serialized_rows() -> Iterable[list[str]]:
            for row in rows:
                cells = []
                for field in fieldnames:
                    value = row.get(field, "")
                    if value is None:
                        cell = ""
                    elif type(value) in (str, int, float, bool):
                        cell = str(value)
                    else:
                        raise TypeError("CSV producer hint requires stable built-in cells")
                    if len(cell) > field_limit:
                        raise ValueError("CSV cell exceeds the physical reader field limit")
                    cells.append(cell)
                yield cells

        profile = _profile_csv_records(list(fieldnames), serialized_rows())
        if _csv_file_signature(path.stat()) != signature:
            return None
        return {"path": str(path.resolve()), "signature": signature,
                "sha256": written_sha256, "field_size_limit": field_limit, "profile": profile}
    except (OSError, AttributeError, TypeError, ValueError, OverflowError):
        return None


def _canonical_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    out: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        geo = node.get("geo") if isinstance(node.get("geo"), dict) else {}
        attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}
        out.append(
            {
                "id": node.get("id"),
                "type": node.get("type", "unknown"),
                "name": node.get("name", ""),
                "location_id": node.get("location_ID") or attrs.get("location_ID"),
                "country": geo.get("country") or attrs.get("country"),
                "lat": node.get("lat", geo.get("lat")),
                "lon": node.get("lon", geo.get("lon")),
            }
        )
    return out


def _canonical_flows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    out: list[dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        lead_time = edge.get("lead_time") if isinstance(edge.get("lead_time"), dict) else {}
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        out.append(
            {
                "id": edge.get("id"),
                "type": edge.get("type", "unknown"),
                "from": edge.get("from"),
                "to": edge.get("to"),
                "items": edge.get("items") if isinstance(edge.get("items"), list) else [],
                "planned_lead_days": lead_time.get("mean"),
                "distance_km": edge.get("distance_km"),
                "standard_order_qty": attrs.get("standard_order_qty"),
            }
        )
    return out


def _artifact_record(
    spec: ArtifactSpec,
    *,
    path: Path,
    output_dir: Path,
    written_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = None
    if written_profile is not None:
        try:
            if (written_profile["path"] == str(path.resolve())
                    and written_profile["field_size_limit"] == csv.field_size_limit()
                    and written_profile["signature"] == _csv_file_signature(path.stat())):
                # Windows may retain all stat fields after a same-size rewrite.
                # Stat is only a cheap rejection filter, never content evidence.
                with path.open("rb") as stream:
                    current_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
                if (current_sha256 == written_profile["sha256"]
                        and written_profile["signature"] == _csv_file_signature(path.stat())):
                    profile = written_profile["profile"]
        except (OSError, KeyError, TypeError, ValueError):
            pass
    if profile is None:
        profile = _csv_profile(path)
    return {
        "name": spec.filename,
        "group": spec.group,
        "domain": spec.domain,
        "grain": spec.grain,
        "required": spec.required,
        "path": _rel(path, output_dir),
        "format": "csv",
        **profile,
    }


def _summary_artifacts(output_dir: Path) -> list[dict[str, Any]]:
    summaries_dir = output_dir / "summaries"
    records: list[dict[str, Any]] = []
    for path in sorted(summaries_dir.glob("*.json")) if summaries_dir.exists() else []:
        records.append(
            {
                "name": path.name,
                "group": "summaries",
                "domain": path.stem,
                "grain": "run",
                "required": path.name == "first_simulation_summary.json",
                "path": _rel(path, output_dir),
                "format": "json",
                "exists": True,
                "size_bytes": path.stat().st_size,
            }
        )
    return records


def _has_metadata_value(metadata: dict[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return bool(str(value).strip())


def _has_state_dependent_companion(output_root: Path) -> bool:
    scenario_root = output_root / "scenario_runs"
    if not scenario_root.exists():
        return False
    for manifest_path in scenario_root.glob("*/run/run_manifest.json"):
        manifest = _read_json(manifest_path)
        capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
        if capabilities.get("state_dependent_risk_enabled"):
            return True
        policy = _read_json(manifest_path.parent / "policy.json")
        supplier_state = policy.get("supplier_state_dependent_risk") if isinstance(policy, dict) else {}
        if isinstance(supplier_state, dict) and supplier_state.get("enabled"):
            return True
    return False


def _has_supplier_criticality_artifacts(output_root: Path) -> bool:
    criticality_dir = output_root / "supplier_criticality"
    return criticality_dir.exists() and any(criticality_dir.glob("*"))


def export_run_package(
    *,
    output_dir: Path | str,
    input_graph: Path | str | None = None,
    package_dir: Path | str | None = None,
    map_html: Path | str | None = None,
    extra_metadata: dict[str, Any] | None = None,
    lot_causal_link_profile: dict[str, Any] | None = None,
) -> Path:
    """Create a generic run package for an existing simulation result folder.

    Heavy CSV files remain in `output_dir/data`.  The package stores indexes and
    normalized small JSON files so downstream tools can discover the run without
    hard-coding legacy filenames.
    """

    output_root = Path(output_dir).resolve(strict=False)
    target = Path(package_dir).resolve(strict=False) if package_dir else output_root / "run"
    target.mkdir(parents=True, exist_ok=True)

    summary_path = output_root / "summaries" / "first_simulation_summary.json"
    summary = _read_json(summary_path)
    kpis = summary.get("kpis") if isinstance(summary.get("kpis"), dict) else {}
    policy = summary.get("policy") if isinstance(summary.get("policy"), dict) else {}
    counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}

    graph_path = Path(input_graph).resolve(strict=False) if input_graph else None
    graph = _read_json(graph_path) if graph_path else {}
    nodes = _canonical_nodes(graph)
    flows = _canonical_flows(graph)

    artifact_records = [
        _artifact_record(
            spec, path=output_root / "data" / spec.filename, output_dir=output_root,
            written_profile=(lot_causal_link_profile if spec.filename == "lot_causal_links.csv" else None),
        )
        for spec in CANONICAL_DATA_ARTIFACTS
    ]
    artifact_records.extend(_summary_artifacts(output_root))

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in artifact_records:
        by_group[str(record["group"])].append(record)

    map_path = Path(map_html).resolve(strict=False) if map_html else None
    if map_path and not map_path.exists():
        map_path = None

    metadata = extra_metadata or {}
    supplier_state_policy = (
        (policy.get("supplier_state_dependent_risk") or {}) if isinstance(policy, dict) else {}
    )
    supplier_risk_policy = (policy.get("supplier_risk") or {}) if isinstance(policy, dict) else {}
    state_dependent_available = bool(supplier_state_policy.get("enabled")) or _has_metadata_value(
        metadata, "simulated_risk_output_dir"
    ) or _has_metadata_value(metadata, "state_dependent_scenarios") or _has_state_dependent_companion(output_root)
    supplier_risk_available = bool(supplier_risk_policy.get("enabled")) or _has_metadata_value(
        metadata, "supplier_criticality_dir"
    ) or _has_supplier_criticality_artifacts(output_root)

    manifest = {
        "schema_version": RUN_PACKAGE_SCHEMA_VERSION,
        "lot_trace_contract_version": LOT_TRACE_CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_root),
        "source_graph": str(graph_path) if graph_path else None,
        "scenario_id": summary.get("scenario_id"),
        "sim_days": summary.get("sim_days"),
        "timeline_days": summary.get("timeline_days"),
        "output_profile": policy.get("output_profile"),
        "counts": {
            "nodes": len(nodes) or counts.get("nodes"),
            "flows": len(flows) or counts.get("edges"),
            "artifacts": len(artifact_records),
            "present_artifacts": sum(1 for row in artifact_records if row.get("exists")),
        },
        "entrypoints": {
            "nodes": "nodes.json",
            "flows": "flows.json",
            "kpis": "kpis.json",
            "artifact_index": "artifact_index.json",
            "timeseries_index": "timeseries_index.json",
            "lots_index": "lots_index.json",
            "events_index": "events_index.json",
            "diagnostics_index": "diagnostics_index.json",
        },
        "map_html": str(map_path) if map_path else None,
        "capabilities": {
            "lot_trace_enabled": bool(policy.get("lot_trace_enabled")),
            "state_dependent_risk_enabled": state_dependent_available,
            "supplier_risk_enabled": supplier_risk_available,
        },
        "metadata": metadata,
    }

    _write_json(target / "run_manifest.json", manifest)
    _write_json(target / "nodes.json", nodes)
    _write_json(target / "flows.json", flows)
    _write_json(target / "kpis.json", kpis)
    _write_json(target / "policy.json", policy)
    _write_json(target / "artifact_index.json", artifact_records)
    _write_json(target / "timeseries_index.json", by_group.get("timeseries", []))
    _write_json(target / "lots_index.json", by_group.get("lots", []))
    _write_json(target / "events_index.json", by_group.get("events", []))
    _write_json(target / "diagnostics_index.json", by_group.get("diagnostics", []))

    return target
