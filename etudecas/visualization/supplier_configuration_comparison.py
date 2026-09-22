"""Render the historical one-seed supplier/configuration screen, without simulation.

The standalone HTML carries the original CSV and manifest bytes, their hashes,
and normalized rows. Rebuilding requires only the HTML or its exported JSON.
This schema deliberately refuses a multi-seed study: it provides no inference.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "etudecas.supplier_configuration_comparison.v1"
STATES = ("op_100", "op_93", "op_80")
CAUSES = ("transport_delay", "supply_availability")
SOURCE_SCHEMA = "etudecas.supplier_operating_point_matrix_current_engine.preliminary.v1"
IDENTITY = ("supplier_id", "item_id", "factory_id", "product_id")
NUMBERS = ("realized_global_on_due", "realized_268091_on_due", "realized_268967_on_due",
           "baseline_global_service", "incident_global_service", "global_service_loss_pp",
           "baseline_service", "incident_service", "service_loss_pp", "backlog_qty_days_delta",
           "production_delta", "incident_value", "risk_applied_row_count", "risk_applied_event_count")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize_rows(raw: bytes, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Check the complete one-seed matrix and signs before any presentation."""
    if manifest.get("schema_version") != SOURCE_SCHEMA or manifest.get("status") != "complete":
        raise ValueError("Une matrice préliminaire complète et explicitement identifiée est requise.")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    required = {*IDENTITY, *NUMBERS, "chain_id", "operating_point_id", "incident_mechanism",
                "incident_physically_exercised", "engine_sha256", "seed", "status"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Colonnes requises absentes du CSV source.")
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str]] = set()
    identities: dict[str, tuple[str, ...]] = {}
    baselines: dict[str, tuple[float, ...]] = {}
    engines: set[str] = set()
    seeds: set[str] = set()
    for raw_row in reader:
        row: dict[str, Any] = dict(raw_row)
        if any(not str(row[key]).strip() for key in required):
            raise ValueError("Valeur requise absente du CSV source.")
        state, chain, cause = row["operating_point_id"], row["chain_id"], row["incident_mechanism"]
        key = (state, chain, cause)
        if state not in STATES or cause not in CAUSES or key in keys:
            raise ValueError("État, mécanisme ou unicité de cellule invalides.")
        keys.add(key)
        identity = tuple(row[k] for k in IDENTITY)
        if identities.setdefault(chain, identity) != identity:
            raise ValueError("Identité fournisseur/article/usine/produit contradictoire.")
        for column in NUMBERS:
            row[column] = float(row[column])
            if not math.isfinite(row[column]):
                raise ValueError(f"Valeur non finie : {column}.")
        for column in NUMBERS[:7]:
            if column != "global_service_loss_pp" and not 0 <= row[column] <= 1:
                raise ValueError(f"Taux hors [0, 1] : {column}.")
        for column in ("baseline_service", "incident_service"):
            if not 0 <= row[column] <= 1:
                raise ValueError(f"Taux hors [0, 1] : {column}.")
        for prefix, loss in (("global_", "global_service_loss_pp"), ("", "service_loss_pp")):
            before = row["baseline_" + prefix + "service"]
            after = row["incident_" + prefix + "service"]
            if not math.isclose(row[loss], 100 * (before - after), rel_tol=0, abs_tol=1e-8):
                raise ValueError("Perte de service incohérente avec référence moins incident.")
        baseline = tuple(row[k] for k in ("realized_global_on_due", "realized_268091_on_due", "realized_268967_on_due"))
        if baselines.setdefault(state, baseline) != baseline:
            raise ValueError("Référence de configuration variable entre les cellules.")
        if not math.isclose(row["baseline_global_service"], baseline[0], abs_tol=1e-12):
            raise ValueError("Référence globale contradictoire.")
        product_baseline = row.get("realized_" + row["product_id"] + "_on_due")
        if product_baseline is None or not math.isclose(row["baseline_service"], product_baseline, abs_tol=1e-12):
            raise ValueError("Référence produit contradictoire.")
        flag = str(row["incident_physically_exercised"]).lower()
        if flag not in ("true", "false"):
            raise ValueError("Exécution physique indéterminée.")
        row["incident_physically_exercised"] = flag == "true"
        expected_status = ("PRELIMINARY_VALID_NO_QUALITY_STATE_RISK_OFF" if flag == "true"
                           else "PRELIMINARY_NON_EXERCEE_EXCLUE_CLASSEMENT")
        if row["status"] != expected_status:
            raise ValueError("Statut et exécution physique contradictoires.")
        expected_value = 120 if cause == "transport_delay" else 0.5
        if row["incident_value"] != expected_value:
            raise ValueError("Intensité différente : la comparaison exige la même hypothèse par cause.")
        for column in ("risk_applied_event_count", "risk_applied_row_count"):
            if row[column] < 0 or not row[column].is_integer():
                raise ValueError("Nombre d'événements invalide.")
        if flag == "true" and row["risk_applied_row_count"] == 0:
            raise ValueError("Incident déclaré exercé sans ligne appliquée.")
        engines.add(row["engine_sha256"])
        seeds.add(row["seed"])
        rows.append(row)
    expected = {(s, chain, cause) for s in STATES for chain in identities for cause in CAUSES}
    if len(identities) != 18 or len(rows) != 108 or keys != expected or len(seeds) != 1:
        raise ValueError("Cette présentation exige 18 voies × 2 causes × 3 états, une seule graine commune.")
    if engines != {manifest.get("engine_sha256")} or manifest.get("detail_row_count") != len(rows):
        raise ValueError("Empreinte moteur ou nombre de lignes du manifeste contradictoire.")
    if sorted(int(s) for s in seeds) != manifest.get("seed_ids"):
        raise ValueError("Graine contradictoire avec le manifeste.")
    return sorted(rows, key=lambda r: (STATES.index(r["operating_point_id"]), r["chain_id"], r["incident_mechanism"]))


def build_payload(csv_path: Path, manifest_path: Path) -> dict[str, Any]:
    raw_csv, raw_manifest = csv_path.read_bytes(), manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    return {
        "schema_version": SCHEMA,
        "source_csv_b64": base64.b64encode(raw_csv).decode("ascii"),
        "source_manifest_b64": base64.b64encode(raw_manifest).decode("ascii"),
        "sources": {"csv": {"path": str(csv_path.resolve()), "sha256": sha256(raw_csv)},
                    "manifest": {"path": str(manifest_path.resolve()), "sha256": sha256(raw_manifest)}},
        "rows": normalize_rows(raw_csv, manifest),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA:
        raise ValueError("Schéma de présentation inconnu.")
    csv_bytes = base64.b64decode(payload["source_csv_b64"], validate=True)
    manifest_bytes = base64.b64decode(payload["source_manifest_b64"], validate=True)
    for name, raw in (("csv", csv_bytes), ("manifest", manifest_bytes)):
        if sha256(raw) != payload["sources"][name]["sha256"]:
            raise ValueError(f"Empreinte source incohérente : {name}.")
    manifest = json.loads(manifest_bytes)
    if payload["rows"] != normalize_rows(csv_bytes, manifest):
        raise ValueError("Données affichées différentes du CSV embarqué.")
    return manifest


def extract_payload(source_html: Path) -> dict[str, Any]:
    document = source_html.read_text(encoding="utf-8")
    marker = '<script id="supplier-comparison-data" type="application/json">'
    if document.count(marker) != 1:
        raise ValueError("Un seul bloc de données identifié est requis.")
    start = document.index(marker) + len(marker)
    payload = json.loads(document[start:document.index("</script>", start)])
    validate_payload(payload)
    return payload


HTML = r'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fournisseurs et configurations — comparaison préliminaire</title>
<style>
:root{font:15px/1.5 system-ui,sans-serif;color:#172c41;background:#f2f5f7}*{box-sizing:border-box}body{margin:0}header{background:#132f46;color:white;padding:28px max(22px,calc((100vw - 1480px)/2))}h1{font-size:30px;margin:5px 0 10px;line-height:1.2}h2{font-size:20px;margin:0 0 10px}h3{font-size:16px;margin:5px 0}p{margin:8px 0}main{max-width:1524px;margin:auto;padding:20px 22px}a{color:#164f80}header a{color:#c8eaff}.badge{display:inline-block;border:1px solid #b1c6d8;border-radius:6px;padding:3px 9px;font-size:12px;letter-spacing:.04em}.notice{border-left:5px solid #b67812;background:#fff6e3;padding:14px 18px;border-radius:6px;margin-bottom:16px}.muted{color:#506479;font-size:13px}.filters{display:flex;flex-wrap:wrap;gap:16px;padding:16px;background:#fff;border:1px solid #cdd8e1;border-radius:9px;margin:16px 0;position:sticky;top:0;z-index:3}.filters label{display:grid;gap:5px;font-weight:600}select,input,button{font:inherit;border:1px solid #9db0c1;border-radius:5px;padding:7px 10px;background:white;color:#18374f}button{cursor:pointer}button:hover{background:#e6f1f7}button:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid #dc8d0e;outline-offset:2px}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.card,.panel{background:white;border:1px solid #cdd8e1;border-radius:9px;padding:16px}.card.active{border:2px solid #246c9a}.big{font-size:29px;font-weight:750;color:#14537b}.grid{display:grid;grid-template-columns:1fr 1.25fr;gap:16px;margin-top:16px}.scroll{overflow:auto;max-height:670px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px 8px;text-align:left;border-bottom:1px solid #e0e7ed}th{position:sticky;top:0;background:#eaf0f5;z-index:1}td.number{font-variant-numeric:tabular-nums;text-align:right}.cell{width:100%;font-variant-numeric:tabular-nums;min-width:82px}.selected{outline:2px solid #317aa5;outline-offset:-2px}.status{font-size:12px;color:#526577}.loss{color:#922c20;font-weight:650}.gain{color:#14694e}.detail{margin-top:16px}.detail-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.detail-grid article{padding:12px;background:#f4f7fa;border-radius:6px}.downloads{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}details{margin-top:18px}summary{cursor:pointer;font-weight:650}pre{overflow:auto;white-space:pre-wrap;word-break:break-word;background:#edf2f6;padding:12px;font-size:12px}.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px}.count{font-size:13px;color:#526577}#empty{padding:20px;color:#526577}.small{font-size:12px}footer{padding:14px 0;color:#506479;font-size:12px}noscript{display:block;padding:20px;background:#ffedb5}@media(max-width:1050px){.grid{grid-template-columns:1fr}}@media(max-width:680px){.cards,.detail-grid{grid-template-columns:1fr}.filters{position:static}.filters label{width:100%}h1{font-size:25px}}
</style></head><body>
<header><div class="badge">ÉTUDE PRÉLIMINAIRE · UNE SEULE GRAINE · ARCHIVE DU 4 SEPTEMBRE 2026</div>
<h1>Quels fournisseurs deviennent prioritaires quand la chaîne se tend ?</h1>
<p>Comparez les conséquences du même type d'incident dans trois configurations du réseau.</p>
<p class="small">18 voies fournisseur–article–usine · 2 hypothèses d'incident · 108 cas. Les résultats proviennent du moteur historique.</p></header>
<main><section class="notice" aria-label="Limites de la comparaison"><strong>Un premier balayage, sans confirmation statistique.</strong>
<p>La même graine est utilisée dans les trois états : ce ne sont ni trois répétitions indépendantes ni une campagne à 30 répétitions. Les pourcentages ci-dessous décrivent le <strong>service client simulé avant incident</strong>, pas la disponibilité réelle des fournisseurs.</p>
<p>Les stocks, flux et calendriers diffèrent entre configurations ; les expositions aux incidents ne sont pas égalisées. À environ 80 %, les deux produits sont touchés de façon inégale. Les incidents non exercés sont exclus des priorités.</p></section>
<div class="cards" id="states" aria-label="Configurations de référence"></div>
<div class="filters"><label>Configuration à classer<select id="configuration"><option value="op_100">Proche de 100 %</option><option value="op_93">Proche de 93 %</option><option value="op_80">Proche de 80 %</option></select></label>
<label>Hypothèse d'incident<select id="cause"><option value="transport_delay">Retard de transport ajouté : 120 jours</option><option value="supply_availability">Disponibilité fournisseur réglée à 50 %</option></select></label>
<label>Effet comparé<select id="metric"><option value="global_service_loss_pp">Perte de service client global</option><option value="service_loss_pp">Perte de service du produit alimenté</option></select></label>
<label>Rechercher un fournisseur ou article<input id="search" type="search" placeholder="338929, fournisseur, usine…"></label></div>
<p class="muted" id="scope" aria-live="polite"></p>
<div class="grid"><section class="panel"><h2>Priorités dans la configuration choisie</h2><p class="muted">Tri par perte décroissante, à cause fixée. Une valeur positive signifie une dégradation ; une valeur négative, une amélioration dans ce seul essai.</p><p id="rank-summary" class="count"></p><div class="scroll"><table id="ranking"><thead><tr><th>Rang</th><th>Voie fournisseur</th><th>Perte (points)</th><th>Lecture</th></tr></thead><tbody></tbody></table></div></section>
<section class="panel"><h2>Le même fournisseur dans les trois états</h2><p class="muted">Sélectionnez une cellule pour voir la référence, le scénario perturbé et leur différence. Le rouge traduit une perte, le vert une amélioration ; la couleur ne représente aucune probabilité.</p><div class="scroll"><table id="comparison"><thead><tr><th>Article / fournisseur</th><th>~100 %</th><th>~93 %</th><th>~80 %</th></tr></thead><tbody></tbody></table></div><div class="legend muted"><span>Points = différence entre deux pourcentages</span><span>— = incident non exercé, aucune conclusion</span></div></section></div>
<section class="panel detail"><h2 id="detail-title">Détail de la comparaison</h2><div class="detail-grid" id="detail"></div><p class="muted">Source : volumes servis à échéance dans les sorties de simulation, rapportés à la demande des produits 268091 et 268967 (UN). Les rattrapages tardifs sont exclus. Le service global pondère les produits par leur demande ; ce n'est pas un OTIF fournisseur observé sur le terrain.</p></section>
<details class="panel"><summary>Provenance, méthode et reconstruction</summary>
<p>Le CSV original et son manifeste sont intégralement embarqués. Aucune simulation n'est exécutée lors de l'ouverture ou de la reconstruction de cette page.</p>
<p>Le classement est descriptif : même graine, même mécanisme imposé et même ancien moteur. Il ne prouve ni une probabilité d'incident ni un classement robuste général. Qualité et risques fournisseurs dépendants de l'état sont désactivés dans cette étude.</p>
<p id="provenance-summary"></p><pre id="provenance"></pre><p>Reconstruction depuis le JSON exporté :</p><pre>python -m etudecas.visualization.supplier_configuration_comparison build --input-json fournisseur-configurations.json --output-html nouvelle-comparaison.html</pre>
<p>Ou directement depuis cet HTML :</p><pre>python -m etudecas.visualization.supplier_configuration_comparison rebuild --source-html 04_criticite_fournisseurs_configurations.html --output-html nouvelle-comparaison.html</pre></details>
<div class="downloads"><button id="export-json">Exporter les données et la provenance (JSON)</button><button id="export-csv">Exporter le CSV source</button><button id="export-manifest">Exporter le manifeste source</button></div>
<footer>Aucune dépendance réseau. Un fichier autonome ; les données restent consultables et exportables hors ligne.</footer></main>
<noscript>Activez JavaScript pour utiliser les filtres. Le bloc supplier-comparison-data contient les données exportables.</noscript>
<script id="supplier-comparison-data" type="application/json">__PAYLOAD__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('supplier-comparison-data').textContent), ROWS=DATA.rows;
const STATES=['op_100','op_93','op_80'], LABELS={op_100:'Proche de 100 %',op_93:'Proche de 93 %',op_80:'Proche de 80 %'};
const $=id=>document.getElementById(id), number=(n,d=2)=>Number(n).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d}),pct=n=>number(100*n)+' %';
const text=(tag,value,cls)=>{const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e;};
const rowKey=r=>[r.operating_point_id,r.chain_id,r.incident_mechanism].join('|');
const INDEX=new Map(ROWS.map(r=>[rowKey(r),r])), lanes=[...new Map(ROWS.map(r=>[r.chain_id,r])).values()];
let chosen=lanes.find(r=>r.item_id==='338929')?.chain_id||lanes[0].chain_id;
function status(r,key){return !r.incident_physically_exercised?'Non exercé':r[key]>1e-9?'Perte mesurée dans cet essai':r[key]<-1e-9?'Amélioration dans cet essai':'Aucun effet mesuré';}
function loss(r,key){return r.incident_physically_exercised?number(r[key]):'—';}
function rowsForLane(chain){return STATES.map(s=>INDEX.get([s,chain,$('cause').value].join('|')));}
function choose(chain,state){chosen=chain;if(state)$('configuration').value=state;render();}
function render(){
 const state=$('configuration').value,cause=$('cause').value,key=$('metric').value,query=$('search').value.toLocaleLowerCase('fr');
 const filtered=lanes.filter(r=>[r.supplier_id,r.item_id,r.factory_id,r.product_id].join(' ').toLocaleLowerCase('fr').includes(query));
 $('states').replaceChildren();STATES.forEach(s=>{const r=ROWS.find(r=>r.operating_point_id===s),card=text('article','','card'+(s===state?' active':''));card.append(text('h3',LABELS[s]),text('div',pct(r.realized_global_on_due),'big'),text('p','Service client global simulé, avant incident','muted'),text('p','PF 268091 : '+pct(r.realized_268091_on_due)+' · PF 268967 : '+pct(r.realized_268967_on_due),'small'));$('states').append(card);});
 const selected=filtered.map(r=>INDEX.get([state,r.chain_id,cause].join('|'))).sort((a,b)=>Number(b.incident_physically_exercised)-Number(a.incident_physically_exercised)||(b[key]-a[key])||a.chain_id.localeCompare(b.chain_id));
 const positive=selected.filter(r=>r.incident_physically_exercised&&r[key]>1e-9);let rank=0,last=null;
 $('rank-summary').textContent=positive.length+' voies avec perte positive dans ce filtre ; '+selected.filter(r=>!r.incident_physically_exercised).length+' incidents non exercés.';
 $('scope').textContent='108 cas au total · une graine commune '+ROWS[0].seed+' · '+ROWS.filter(r=>!r.incident_physically_exercised).length+' cas non exercés sur l’ensemble de la matrice. Le tableau compare la même cause entre états.';
 const tbody=$('ranking').tBodies[0];tbody.replaceChildren();selected.forEach((r,i)=>{const tr=document.createElement('tr');tr.dataset.chain=r.chain_id;tr.dataset.exercised=String(r.incident_physically_exercised);if(r.chain_id===chosen)tr.className='selected';const positive=r.incident_physically_exercised&&r[key]>1e-9;if(positive){if(last===null||Math.abs(last-r[key])>1e-9)rank=i+1;last=r[key];}tr.append(text('td',positive?String(rank):'—'));const id=document.createElement('td'),b=text('button',r.item_id+' → '+r.factory_id);b.onclick=()=>choose(r.chain_id);b.setAttribute('aria-label','Détail '+r.supplier_id+', article '+r.item_id);id.append(b,text('div',r.supplier_id,'small'),text('div','Produit '+r.product_id,'small'));tr.append(id,text('td',loss(r,key),'number '+(r[key]>0?'loss':'gain')),text('td',status(r,key),'status'));tbody.append(tr);});
 const matrix=$('comparison').tBodies[0];matrix.replaceChildren();selected.forEach(r=>{const tr=document.createElement('tr');tr.dataset.chain=r.chain_id;const td=document.createElement('td');td.append(text('strong',r.item_id+' → '+r.factory_id),text('div',r.supplier_id,'small'));tr.append(td);rowsForLane(r.chain_id).forEach(cell=>{const td=document.createElement('td'),b=text('button',loss(cell,key),'cell');b.dataset.state=cell.operating_point_id;b.dataset.loss=String(cell[key]);b.dataset.exercised=String(cell.incident_physically_exercised);b.setAttribute('aria-label',r.item_id+', '+LABELS[cell.operating_point_id]+', '+status(cell,key)+(cell.incident_physically_exercised?', '+number(cell[key])+' points':''));if(cell.incident_physically_exercised&&cell[key]>0)b.style.backgroundColor='rgba(183,62,37,'+Math.min(.32,.04+cell[key]/120)+')';if(cell.incident_physically_exercised&&cell[key]<0)b.style.backgroundColor='#e3f4eb';b.onclick=()=>choose(cell.chain_id,cell.operating_point_id);td.append(b);tr.append(td);});matrix.append(tr);});
 const details=rowsForLane(chosen),first=details[0];$('detail-title').textContent=first.supplier_id+' · article '+first.item_id+' → '+first.factory_id+' · produit '+first.product_id;
 $('detail').replaceChildren();details.forEach(r=>{const a=document.createElement('article');a.dataset.state=r.operating_point_id;a.append(text('h3',LABELS[r.operating_point_id]));const global=key==='global_service_loss_pp',before=global?r.baseline_global_service:r.baseline_service,after=global?r.incident_global_service:r.incident_service;a.append(text('p','Référence : '+pct(before)),text('p','Avec incident : '+pct(after)),text('p',r.incident_physically_exercised?'Perte : '+number(r[key])+' points':'Incident non exercé : effet non interprétable',r[key]>0?'loss':''),text('p','1 réalisation · graine '+r.seed,'muted'));$('detail').append(a);});
}
for(const id of ['configuration','cause','metric'])$(id).addEventListener('change',render);$('search').addEventListener('input',render);
function download(name,bytes,type){const url=URL.createObjectURL(new Blob([bytes],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function rawBytes(s){return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
$('export-json').onclick=()=>download('fournisseur-configurations.json',JSON.stringify(DATA,null,2),'application/json;charset=utf-8');
$('export-csv').onclick=()=>download('supplier_operating_point_comparison.csv',rawBytes(DATA.source_csv_b64),'text/csv;charset=utf-8');
$('export-manifest').onclick=()=>download('campaign_manifest.json',rawBytes(DATA.source_manifest_b64),'application/json;charset=utf-8');
$('provenance-summary').textContent='Ancien moteur SHA-256 : '+ROWS[0].engine_sha256+'. Les empreintes identifient les sources ; elles ne certifient pas le modèle industriel.';
$('provenance').textContent=JSON.stringify(DATA.sources,null,2);render();
</script></body></html>'''


def render_html(payload: dict[str, Any]) -> str:
    validate_payload(payload)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    return HTML.replace("__PAYLOAD__", encoded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--csv", type=Path)
    build.add_argument("--manifest", type=Path)
    build.add_argument("--input-json", type=Path)
    build.add_argument("--output-html", type=Path, required=True)
    rebuild = commands.add_parser("rebuild")
    rebuild.add_argument("--source-html", type=Path, required=True)
    rebuild.add_argument("--output-html", type=Path, required=True)
    extract = commands.add_parser("extract")
    extract.add_argument("--source-html", type=Path, required=True)
    extract.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command in ("rebuild", "extract"):
        payload = extract_payload(args.source_html)
    elif args.input_json and not args.csv and not args.manifest:
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    elif args.csv and args.manifest and not args.input_json:
        payload = build_payload(args.csv, args.manifest)
    else:
        parser.error("Fournir soit --csv et --manifest, soit --input-json.")
    validate_payload(payload)
    output = args.output_json if args.command == "extract" else args.output_html
    if output.exists():
        raise FileExistsError(output)
    document = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) if args.command == "extract" else render_html(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as stream:
        stream.write(document)
    print(json.dumps({"output": str(output), "bytes": output.stat().st_size, "sha256": sha256(output.read_bytes()),
                      "rows": len(payload["rows"]), "simulation_started": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
