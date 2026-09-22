"""Refresh receipt/incident UI on a previously generated map without a replay.

The embedded event and genealogy ledgers must match the supplied CSVs. Existing
simulation payloads and historical HTML are preserved; only the material context
and the lot renderer from the current template are added to a new output.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

from etudecas.simulation.lot_trace.io import read_csv_rows
from etudecas.simulation.lot_trace.materials import build_material_traceability
from etudecas.visualization.maps.worldmap_html_template import html_template


def _signature(rows, fields, numbers):
    values = []
    for row in rows:
        values.append([float(row.get(key) or 0) if key in numbers else str(row.get(key) or "")
                       for key in fields])
    return hashlib.sha256(json.dumps(sorted(values), separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def refresh(source, data, graph, output, evidence, metadata_path=None):
    if source.resolve() == output.resolve():
        raise ValueError("Keep the historical map: output must differ from source")
    original = source.read_text(encoding="utf-8")
    marker = "const DATA_CHUNKED_GZIP_BASE64 = "
    if marker in original:
        chunks, _ = json.JSONDecoder().raw_decode(original[original.index(marker) + len(marker):])
        trace = json.loads(gzip.decompress(base64.b64decode("".join(chunks["lot_trace"]))))
        del chunks
    else:
        marker = "const DATA = "
        payload, _ = json.JSONDecoder().raw_decode(original[original.index(marker) + len(marker):])
        trace = payload["lot_trace"]
    events = read_csv_rows(data / "production_lot_events.csv")
    links = read_csv_rows(data / "production_lot_genealogy.csv")
    signatures = {}
    for name, rows, fields, numbers in [
        ("events", events, ["event_id", "lot_id", "event_type", "item_id", "node_id", "qty", "day", "shipment_id", "risk_event_ids"], {"qty", "day"}),
        ("genealogy", links, ["parent_lot_id", "child_lot_id", "link_type", "parent_qty", "child_qty", "day", "shipment_id"], {"parent_qty", "child_qty", "day"}),
    ]:
        signatures[name] = _signature(rows, fields, numbers)
        if signatures[name] != _signature(trace[name], fields, numbers):
            raise ValueError(f"Map/CSV mismatch: {name}")
    del trace
    if metadata_path is not None and not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    metadata_path = metadata_path or data / "material_traceability.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig")) if metadata_path.exists() else None
    context = build_material_traceability(events, links, json.loads(graph.read_text(encoding="utf-8-sig")), metadata)
    template = html_template("", "{}", "", 0, "")
    start, end = "    function renderLotTraceGraph(snapshot)", "    function updateLotTraceControls()"
    if original.count(start) != 1 or original.count(end) != 1:
        raise ValueError("Unexpected map renderer structure")
    updated = original[:original.index(start)] + template[template.index(start):template.index(end)] + original[original.index(end):]
    css_start, css_end = "    .lotTraceMaterials {", "    .lotTraceGraphWrap {"
    if css_start in updated:
        updated = updated[:updated.index(css_start)] + updated[updated.index(css_end):]
    updated = updated.replace(css_end, template[template.index(css_start):template.index(css_end)] + css_end, 1)
    marker = "    const LOT_TRACE = "
    previous = "    LOT_TRACE.material_traceability = "
    if previous in updated:
        beginning = updated.index(previous)
        value_start = beginning + len(previous)
        _, length = json.JSONDecoder().raw_decode(updated[value_start:])
        ending = value_start + length
        if updated[ending:ending + 2] != ";\n":
            raise ValueError("Unexpected existing material context")
        updated = updated[:beginning] + updated[ending + 2:]
    insert = updated.index("\n", updated.index(marker)) + 1
    serialized = json.dumps(context, ensure_ascii=True, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    updated = updated[:insert] + "    LOT_TRACE.material_traceability = " + serialized + ";\n" + updated[insert:]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(updated, encoding="utf-8")
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "material-context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    files = [source, data / "production_lot_events.csv", data / "production_lot_genealogy.csv", graph,
             Path(__file__), Path(__file__).parents[2] / "simulation/lot_trace/materials.py",
             Path(__file__).parents[2] / "visualization/maps/lot_material_trace.js",
             Path(__file__).parents[2] / "visualization/maps/lot_journey.js",
             Path(__file__).parents[2] / "visualization/maps/lot_journey_operations.js",
             Path(__file__).parents[2] / "visualization/maps/lot_journey_explorer.js",
             Path(__file__).parents[2] / "visualization/maps/lot_journey_timeline.js",
             Path(__file__).parents[2] / "visualization/maps/lot_journey_case.js",
             Path(__file__).parents[2] / "visualization/maps/lot_journey_explorer.css",
             Path(__file__).parents[2] / "visualization/maps/worldmap_html_template.py"]
    if metadata_path.exists():
        files.append(metadata_path)
    report = dict(output=str(output), output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  map_csv_signatures=signatures, coverage=context["coverage"],
                  scope="Material identities and conservative recall exploration; no engine replay or changes to physical results.")
    (evidence / "provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "data", "graph", "output", "evidence"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    result = refresh(args.source, args.data, args.graph, args.output, args.evidence, args.metadata)
    print(json.dumps({"output": result["output"], "coverage": result["coverage"]}))


if __name__ == "__main__":
    main()
