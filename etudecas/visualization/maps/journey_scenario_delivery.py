"""Publish a separate offline lot explorer from one existing scenario's CSVs.

No replay, no nominal payload reuse: occurrence IDs are local to this scenario.
"""
import argparse
import base64
import gzip
import hashlib
import html
import json
from pathlib import Path

from etudecas.simulation.lot_trace.io import read_csv_rows
from etudecas.simulation.lot_trace.indexes import build_lot_trace_indexes
from etudecas.simulation.lot_trace.materials import build_material_traceability
from etudecas.simulation.lot_trace.payload import _enrich_lot_identities
from etudecas.simulation.logistics.display import build_transport_context
from etudecas.visualization.maps.worldmap_html_template import html_template


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
    modules=[folder/name for name in ['lot_journey.js','lot_journey_operations.js','lot_journey_explorer.js','lot_journey_timeline.js','lot_journey_case.js']]
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
        Path(__file__).parents[2]/'simulation/logistics/display.py']
    if metadata_path.exists():sources.append(metadata_path)
    if manifest_path.exists():sources.append(manifest_path)
    report=dict(scenario=scenario,output=str(output),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        events=len(events),links=len(links),lots=len(lots),root=root,transport_error=trace['truck_consolidation'].get('error'),
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        limitations='Standalone scenario explorer; link quantities and network bounds, no canonical PF contribution overlay. No new physical incident.')
    evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'scenario-provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('data','graph','output','evidence'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build_scenario_explorer(args.data,args.graph,args.output,args.evidence),ensure_ascii=True))


if __name__ == '__main__':
    main()
