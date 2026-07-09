"""Export a simulation result folder to the generic run package contract."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.simulation.run_format.schema import (
    CANONICAL_DATA_ARTIFACTS,
    DAY_FIELD_CANDIDATES,
    ITEM_FIELD_CANDIDATES,
    NODE_FIELD_CANDIDATES,
    RUN_PACKAGE_SCHEMA_VERSION,
    ArtifactSpec,
)


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


def _csv_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "row_count": 0, "columns": []}

    row_count = 0
    columns: list[str] = []
    min_day: int | None = None
    max_day: int | None = None
    sample_entities: dict[str, set[str]] = defaultdict(set)

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        day_field = next((field for field in DAY_FIELD_CANDIDATES if field in columns), None)
        entity_fields = [
            field
            for field in (*NODE_FIELD_CANDIDATES, *ITEM_FIELD_CANDIDATES, "lot_id", "parent_lot_id", "child_lot_id")
            if field in columns
        ]
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
) -> dict[str, Any]:
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


def export_run_package(
    *,
    output_dir: Path | str,
    input_graph: Path | str | None = None,
    package_dir: Path | str | None = None,
    map_html: Path | str | None = None,
    extra_metadata: dict[str, Any] | None = None,
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
        _artifact_record(spec, path=output_root / "data" / spec.filename, output_dir=output_root)
        for spec in CANONICAL_DATA_ARTIFACTS
    ]
    artifact_records.extend(_summary_artifacts(output_root))

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in artifact_records:
        by_group[str(record["group"])].append(record)

    map_path = Path(map_html).resolve(strict=False) if map_html else None
    if map_path and not map_path.exists():
        map_path = None

    manifest = {
        "schema_version": RUN_PACKAGE_SCHEMA_VERSION,
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
            "state_dependent_risk_enabled": bool(
                ((policy.get("supplier_state_dependent_risk") or {}) if isinstance(policy, dict) else {}).get("enabled")
            ),
            "supplier_risk_enabled": bool(
                ((policy.get("supplier_risk") or {}) if isinstance(policy, dict) else {}).get("enabled")
            ),
        },
        "metadata": extra_metadata or {},
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
