"""Publish material context on an existing map or a separate scenario lot explorer.

Both modes read existing event ledgers; neither starts a simulation."""

import html, argparse, base64, gzip, hashlib, json
from etudecas.simulation.lot_trace.indexes import build_lot_trace_indexes
from etudecas.simulation.lot_trace.payload import _enrich_lot_identities
from etudecas.simulation.logistics.io import build_transport_context
from pathlib import Path
from etudecas.simulation.lot_trace.schema import read_csv_rows
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


# Consolidated from journey_scenario_delivery: unchanged business definitions.

def build_scenario_explorer(data, graph, output, evidence):
    manifest_path=data.parent/'run_manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        expected=Path(manifest['input_graph'])
        if not expected.is_file() or hashlib.sha256(expected.read_bytes()).digest()!=hashlib.sha256(graph.read_bytes()).digest():
            raise ValueError('Graph must match the scenario input_graph recorded in its run manifest')
    events=read_csv_rows(data/'production_lot_events.csv')
    links=read_csv_rows(data/'production_lot_genealogy.csv')
    scenarios={row.get('scenario_id','') for row in events}
    if len(scenarios)!=1 or '' in scenarios:
        raise ValueError('Expected one explicitly identified scenario')
    scenario=next(iter(scenarios))
    raw=json.loads(graph.read_text(encoding='utf-8-sig'))
    lots={}
    for row in sorted(events,key=lambda r:float(r['day'])):
        if row['lot_id'] not in lots:
            lots[row['lot_id']]={**row,'created_day':int(float(row['day'])),
                'created_event_type':row['event_type'],'qty':float(row['qty'])}
    trace=dict(lots=lots,events=events,genealogy=links)
    index=build_lot_trace_indexes(trace)
    _enrich_lot_identities(lots=lots,trace_indexes=index,
        raw_event_by_id={r['event_id']:r for r in events},raw_genealogy_by_child=index.link_rows_by_child)
    metadata_path=data/'material_traceability.json'
    metadata=json.loads(metadata_path.read_text(encoding='utf-8-sig')) if metadata_path.exists() else None
    trace['material_traceability']=build_material_traceability(events,links,raw,metadata)
    try:
        trace['truck_consolidation']=build_transport_context(events,raw)
    except ValueError as exc:
        trace['truck_consolidation']={'groups':[],'error':str(exc)}
    root=next((r['lot_id'] for r in events if r.get('risk_event_ids') and r['event_type']=='lane_receipt'),next(iter(lots)))
    encoded=base64.b64encode(gzip.compress(json.dumps(trace,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode(),mtime=0)).decode()
    template=html_template('','{}','',0,'')
    css=template[template.index('    .lotTraceMaterials {'):template.index('    .lotTraceGraphWrap {')]
    folder=Path(__file__).parents[2]/'visualization/maps'
    modules=[folder/'lot_journey.js']
    script='\n'.join(p.read_text(encoding='utf-8') for p in modules)
    nodes=json.dumps({n['id']:n for n in raw['nodes']},ensure_ascii=True).replace('<','\\u003c')
    text='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Parcours des lots — scénario identifié</title><style>
body{font:14px system-ui;color:#183247;background:#f4f7fa;margin:20px}button{cursor:pointer}h1{font-size:22px}
.tableModal{display:none;position:fixed;inset:0;background:#18324766;z-index:10;align-items:center;justify-content:center}.tableModal.visible{display:flex}
.tableModalCard{background:#f8fafc;border-radius:10px;height:96vh;display:flex;flex-direction:column}.tableModalHeader{display:flex;justify-content:space-between;padding:12px}.tableModalTitle{font-size:18px;font-weight:700}.tableModalBody{overflow:auto;flex:1}.tableModalMeta{font-size:12px}
''' + css + '</style><h1>Scénario '+html.escape(scenario)+'</h1><p>Exploration de résultats existants. Les identifiants LOT et SHIP sont propres à ce scénario. Aucun incident nouveau appliqué.</p><p id="loading">Chargement…</p><button id="lotTraceOpenBtn" hidden></button><script>\n(async()=>{\n'
    text+=f'''const packed={json.dumps(encoded)};
const bytes=Uint8Array.from(atob(packed),c=>c.charCodeAt(0));
const LOT_TRACE=JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
const DATA={{lot_trace:LOT_TRACE}};window.DATA=DATA;
const nodeById={nodes};
function lotTraceLotInfo(id){{return LOT_TRACE.lots[id];}}
function escapeTableHtml(value){{return String(value??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function lotTraceQtyText(q){{return Number(q).toLocaleString('fr-FR',{{maximumFractionDigits:6}});}}
function lotTraceViewModelForLot(){{return null;}}
function selectedLotTraceSnapshot(){{return {{lotId:{json.dumps(root)}}};}}
'''+script+f"\ndocument.querySelector('#lotJourneyTitle').textContent+=' · '+{json.dumps(scenario)};\ndocument.getElementById('loading').textContent='Prêt : '+Object.keys(LOT_TRACE.lots).length+' occurrences.';\ndocument.getElementById('lotJourneyOpenBtn').click();\n"+"})().catch(e=>{document.getElementById('loading').textContent='Échec du chargement : '+e.message;console.error(e);});</script></html>"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(text,encoding='utf-8')
    sources=[data/'production_lot_events.csv',data/'production_lot_genealogy.csv',graph,Path(__file__),*modules,
        folder/'lot_journey_explorer.css',folder/'worldmap_html_template.py',
        Path(__file__).parents[2]/'simulation/lot_trace/payload.py',Path(__file__).parents[2]/'simulation/lot_trace/materials.py',
        Path(__file__).parents[2]/'simulation/logistics/io.py']
    if metadata_path.exists():sources.append(metadata_path)
    if manifest_path.exists():sources.append(manifest_path)
    report=dict(scenario=scenario,output=str(output),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        events=len(events),links=len(links),lots=len(lots),root=root,transport_error=trace['truck_consolidation'].get('error'),
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        limitations='Standalone scenario explorer; link quantities and network bounds, no canonical PF contribution overlay. No new physical incident.')
    evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'scenario-provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publish material context or a separate scenario lot explorer.")
    parser.add_argument("--mode", choices=("refresh", "scenario"), default="refresh")
    for name in ("data", "graph", "output", "evidence"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "refresh":
        if args.source is None:
            parser.error("--source is required in refresh mode")
        result = refresh(args.source, args.data, args.graph, args.output, args.evidence, args.metadata)
        print(json.dumps({"output": result["output"], "coverage": result["coverage"]}))
    else:
        if args.source is not None or args.metadata is not None:
            parser.error("--source and --metadata apply only to refresh mode")
        print(json.dumps(build_scenario_explorer(args.data, args.graph, args.output, args.evidence), ensure_ascii=True))


if __name__ == "__main__":
    main()
