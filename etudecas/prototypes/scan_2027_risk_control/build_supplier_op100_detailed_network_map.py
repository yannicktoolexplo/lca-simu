#!/usr/bin/env python3
"""Build a standalone, detailed op_100 supplier-network HTML without simulation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping


EXPECTED_PACKAGE_SIGNATURE = (
    "0231b89f05b07d739fafac72478926bfb23d6cfd2edf8f659b786cdaa8d1367a"
)
EXPECTED_CAMPAIGN_SIGNATURE = (
    "fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598"
)
SOURCE_FILES = {
    "manifest": "manifest_paquet_op_100_30_sur_30.json",
    "summary": "bilan_provisoire_op_100_30_sur_30.json",
    "lanes": "resultats_descriptifs_par_voie_op_100_30_sur_30.csv",
    "cases": "mesures_simulees_1110_op_100_30_sur_30.csv",
}
ENTRYPOINT = "OUVRIR_CARTE_DETAILLEE_OP_100_30_SUR_30.html"


class DetailedMapError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise DetailedMapError(f"JSON hors contrat : {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def as_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def validate_source(source_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    paths = {key: source_dir / name for key, name in SOURCE_FILES.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise DetailedMapError("Sources absentes : " + ", ".join(missing))
    manifest = read_json(paths["manifest"])
    if manifest.get("package_signature") != EXPECTED_PACKAGE_SIGNATURE:
        raise DetailedMapError("Le paquet op_100 30/30 n'est pas celui validé.")
    if manifest.get("campaign_signature") != EXPECTED_CAMPAIGN_SIGNATURE:
        raise DetailedMapError("La campagne source n'est pas celle attendue.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping):
        raise DetailedMapError("Index des sorties source absent.")
    for key in ("summary", "lanes", "cases"):
        name = SOURCE_FILES[key]
        record = outputs.get(name)
        if not isinstance(record, Mapping) or sha256_file(paths[key]) != record.get(
            "sha256"
        ):
            raise DetailedMapError(f"Empreinte source invalide : {name}")
    return {"manifest": manifest, "paths": paths}


def build_payload(source_dir: Path, lane_reference: Path) -> dict[str, Any]:
    validated = validate_source(source_dir)
    if not lane_reference.is_file():
        raise DetailedMapError(f"Référence des voies absente : {lane_reference}")
    stats = read_csv(validated["paths"]["lanes"])
    cases = read_csv(validated["paths"]["cases"])
    references = read_csv(lane_reference)
    if len(stats) != 36 or len(references) != 18 or len(cases) != 1110:
        raise DetailedMapError(
            f"Comptages inattendus : voies={len(references)}, statistiques={len(stats)}, cas={len(cases)}"
        )
    reference_by_lane = {row["chain_id"]: row for row in references}
    sample_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    sample_units: dict[tuple[str, str], list[float]] = defaultdict(list)
    sample_production: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in cases:
        if row.get("stage") != "incident":
            continue
        key = (row["mechanism"], row["lane_id"])
        sample_values[key].append(as_float(row.get("impact_service_loss_fed_product_pp")))
        sample_units[key].append(as_float(row.get("impact_on_due_loss_fed_product_qty")))
        sample_production[key].append(
            as_float(row.get("impact_production_loss_fed_product_qty"))
        )
    lanes: list[dict[str, Any]] = []
    for row in stats:
        lane_id = row["lane_id"]
        reference = reference_by_lane.get(lane_id)
        if reference is None:
            raise DetailedMapError(f"Voie sans référence physique : {lane_id}")
        key = (row["mechanism"], lane_id)
        samples = sample_values[key]
        if len(samples) != 30:
            raise DetailedMapError(f"La voie {key} ne contient pas 30 répétitions.")
        lanes.append(
            {
                "mechanism": row["mechanism"],
                "lane_id": lane_id,
                "supplier": row["supplier_id"],
                "item": row["item_id"].removeprefix("item:"),
                "plant": row["dst_node_id"],
                "product": row["target_product_id"],
                "lead_days": as_float(reference.get("planned_lead_days")),
                "reference_qty": as_float(reference.get("reference_total_shipped_qty")),
                "reference_shipment_days": as_int(reference.get("reference_shipment_day_count")),
                "mean_loss": as_float(row.get("service_loss_mean_pp")),
                "median_loss": as_float(row.get("service_loss_median_pp")),
                "p10": as_float(row.get("service_loss_p10_pp")),
                "p90": as_float(row.get("service_loss_p90_pp")),
                "max_loss": as_float(row.get("service_loss_max_pp")),
                "affected_count": as_int(row.get("positive_service_effect_count")),
                "exercised_count": as_int(row.get("physical_exercise_count")),
                "late_units_mean": as_float(row.get("on_due_units_lost_mean")),
                "production_loss_mean": as_float(
                    row.get("production_not_released_mean_qty")
                ),
                "backlog_load_mean": as_float(
                    row.get("backlog_qty_days_per_demand_unit_mean")
                ),
                "samples": [round(value, 6) for value in samples],
                "late_samples": [round(value, 3) for value in sample_units[key]],
                "production_samples": [
                    round(value, 3) for value in sample_production[key]
                ],
            }
        )
    suppliers = sorted({row["supplier"] for row in lanes})
    transport = [row for row in lanes if row["mechanism"] == "transport_delay"]
    shortfall = [
        row for row in lanes if row["mechanism"] == "planned_delivery_shortfall"
    ]
    sensitive = [row for row in transport if row["mean_loss"] > 0]
    return {
        "schema_version": "etudecas.supplier_v8.op100_detailed_network_map.v1",
        "campaign_signature": EXPECTED_CAMPAIGN_SIGNATURE,
        "source_package_signature": EXPECTED_PACKAGE_SIGNATURE,
        "operating_point": "op_100",
        "simulation_count": 30,
        "case_count": 1110,
        "incident_count": 1080,
        "lane_count": len(references),
        "supplier_count": len(suppliers),
        "lanes": lanes,
        "headline": {
            "sensitive_transport_lanes": len(sensitive),
            "shortfall_absorbed_lanes": sum(row["mean_loss"] == 0 for row in shortfall),
            "top_transport": [row["lane_id"] for row in sorted(transport, key=lambda x: -x["mean_loss"])[:4]],
            "transport_mean_loss_across_lanes": mean(row["mean_loss"] for row in transport),
        },
    }


def render_html(payload: Mapping[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    return """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carte détaillée du réseau — op_100 — 30/30</title>
<style>
:root{--navy:#092b50;--blue:#1768c4;--sky:#eaf3ff;--green:#11845f;--amber:#ef9f1a;--red:#ce3e35;--ink:#14263a;--muted:#60758b;--line:#d5e1ec;--paper:#fff;--bg:#edf3f8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif}header{background:linear-gradient(125deg,#082947,#154f82);color:#fff;padding:30px max(24px,4vw)}header h1{margin:7px 0;font-size:clamp(28px,4vw,46px)}header p{max-width:1050px;margin:6px 0;color:#dbeafe}.tag{display:inline-block;padding:6px 10px;border-radius:999px;background:#ffffff20;border:1px solid #ffffff40;font-size:12px;font-weight:800;letter-spacing:.05em}.wrap{max-width:1500px;margin:auto;padding:20px}.notice{background:#fff7e6;border-left:5px solid var(--amber);padding:14px 17px;border-radius:10px;margin-bottom:16px}.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:11px;margin:15px 0}.kpi,.panel,.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:0 7px 20px #183b5b0d}.kpi{padding:15px}.kpi strong{display:block;font-size:28px;color:var(--navy)}.kpi span{font-size:12px;color:var(--muted)}.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:end;padding:14px;margin:15px 0;background:#fff;border:1px solid var(--line);border-radius:14px}.controls label{font-size:12px;font-weight:800;color:var(--muted)}select,button{display:block;margin-top:5px;border:1px solid #b9cada;border-radius:9px;padding:9px 11px;background:#fff;color:var(--ink)}button{cursor:pointer}.layout{display:grid;grid-template-columns:minmax(700px,2fr) minmax(330px,1fr);gap:14px}.panel{padding:14px;overflow:hidden}.panel h2,.card h2{margin:0 0 5px}.sub{color:var(--muted);font-size:13px;margin:0 0 10px}.map-scroll{overflow:auto;max-height:900px}svg{display:block;width:100%;min-width:900px;height:auto;background:linear-gradient(#fbfdff,#f5f9fd);border:1px solid var(--line);border-radius:12px}.lane{fill:none;cursor:pointer;transition:.15s}.lane:hover,.lane.selected{stroke:#7b3fc6!important;stroke-width:8!important;opacity:1!important}.node rect{fill:#fff;stroke:#b8cbdd;stroke-width:1.5}.node text{font-size:12px;fill:var(--ink);font-weight:700}.plant rect{fill:#e9f3ff;stroke:#1768c4}.product rect{fill:#e7f7f0;stroke:#11845f}.detail{padding:17px;position:sticky;top:10px;min-height:500px}.badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:850}.badge.sim{background:#e5efff;color:#1456a0}.badge.high{background:#fde8e6;color:#a12822}.badge.abs{background:#e6f7f0;color:#087052}.path{font-size:19px;font-weight:850;color:var(--navy);margin:10px 0}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px}.metric{border:1px solid var(--line);border-radius:10px;padding:10px}.metric strong{font-size:21px;display:block}.metric small{color:var(--muted)}.reading{padding:11px;margin:12px 0;border-radius:10px;background:#f1f6fb}.dots{display:flex;align-items:end;gap:3px;height:95px;border-bottom:1px solid #9eb4c8;margin:12px 0 5px}.dot{flex:1;min-width:3px;background:#1f70d1;border-radius:3px 3px 0 0}.legend{display:flex;gap:13px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.sw{display:inline-block;width:18px;height:4px;border-radius:3px;margin-right:5px;vertical-align:middle}.business{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:15px 0}.card{padding:17px}.card.good{border-top:5px solid var(--green)}.card.warn{border-top:5px solid var(--amber)}.card.risk{border-top:5px solid var(--red)}.table-wrap{overflow:auto}.table-wrap table{border-collapse:collapse;width:100%;min-width:1050px}.table-wrap th,.table-wrap td{padding:9px;border-bottom:1px solid var(--line);text-align:left;font-size:12px}.table-wrap th{background:#edf4fb;position:sticky;top:0}.num{text-align:right!important;font-variant-numeric:tabular-nums}.method{margin-top:15px;padding:18px}.method details{border-top:1px solid var(--line);padding:10px 0}.method summary{font-weight:800;cursor:pointer}footer{padding:24px;color:var(--muted);font-size:12px;text-align:center}@media(max-width:1050px){.kpis{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.detail{position:static}.business{grid-template-columns:1fr}}@media print{.controls{display:none}.layout{grid-template-columns:1fr}.detail{position:static}body{background:#fff}}
</style></head><body>
<header><span class="tag">RÉSULTAT SIMULÉ · ÉTAT UNIQUE · 30/30</span><h1>Où le réseau résiste — et où il décroche</h1><p>Carte physique interactive des 18 voies fournisseurs testées dans l’état de référence sans dégradation générale ajoutée. Cliquez sur une voie pour lire ses 30 simulations et ses conséquences métier.</p></header>
<main class="wrap"><div class="notice"><strong>Portée :</strong> cette carte décrit un test de résistance simulé. Elle ne mesure ni la performance historique ni la probabilité réelle de défaillance des fournisseurs. La persistance des signaux sera évaluée avec les états 93 et 80.</div>
<section class="kpis"><div class="kpi"><strong>30</strong><span>simulations comparables</span></div><div class="kpi"><strong>18</strong><span>voies physiques testées</span></div><div class="kpi"><strong>1 080</strong><span>incidents simulés</span></div><div class="kpi"><strong>4</strong><span>voies sensibles au retard</span></div><div class="kpi"><strong>18/18</strong><span>voies absorbant la baisse de quantité</span></div></section>
<section class="business"><article class="card risk"><h2>Vulnérabilité forte</h2><p><strong>SDC‑VD0514881A / 016332</strong> dégrade le service dans 24 simulations sur 30. C’est le signal le plus sévère en moyenne.</p></article><article class="card warn"><h2>Effet de seuil</h2><p><strong>SDC‑VD0519670A / 029313</strong> est souvent absorbé, mais peut provoquer une chute supérieure à 40 points. Le réseau résiste puis décroche brutalement.</p></article><article class="card good"><h2>Protection observée</h2><p>La livraison divisée par deux pendant 42 jours est absorbée dans cet état. Cela teste les protections simulées, pas l’absence de risque fournisseur.</p></article></section>
<div class="controls"><label>Incident<select id="mechanism"><option value="transport_delay">Retard de transport de 120 jours</option><option value="planned_delivery_shortfall">Livraison réduite de 50 % pendant 42 jours</option></select></label><label>Produit<select id="product"><option value="all">Tous</option><option>268091</option><option>268967</option></select></label><label>Affichage<select id="sensitivity"><option value="all">Toutes les voies</option><option value="sensitive">Voies avec effet seulement</option></select></label><button id="reset">Réinitialiser la sélection</button></div>
<section class="layout"><div class="panel"><h2>Carte du réseau</h2><p class="sub">La couleur représente la baisse moyenne du service. L’épaisseur représente également la sévérité; une voie grise a été touchée mais absorbée.</p><div class="legend"><span><i class="sw" style="background:#c7d3de"></i>absorbé</span><span><i class="sw" style="background:#ef9f1a"></i>signal modéré</span><span><i class="sw" style="background:#ce3e35"></i>signal fort</span><span><i class="sw" style="background:#7b3fc6"></i>sélection</span></div><div class="map-scroll"><svg id="network" viewBox="0 0 1200 980" aria-label="Réseau fournisseurs vers sites et produits"></svg></div></div><aside class="panel detail" id="detail"></aside></section>
<section class="panel method"><h2>Comparer toutes les voies</h2><p class="sub">Le tableau suit les filtres de la carte. Cliquez sur une ligne pour ouvrir son détail.</p><div class="table-wrap"><table><thead><tr><th>Fournisseur / article</th><th>Chaîne</th><th class="num">Délai planifié</th><th class="num">Baisse moyenne</th><th class="num">Médiane</th><th class="num">P10–P90</th><th class="num">Service dégradé</th><th class="num">Quantités à l’heure perdues</th><th>Lecture métier</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="panel method"><h2>Ce que cette carte permet — et ne permet pas encore</h2><details open><summary>Résultat exploitable maintenant</summary><p>Elle localise les voies qui transmettent un retard fournisseur jusqu’au service du produit fini, quantifie la sévérité moyenne et montre si l’effet est systématique ou dépend d’un seuil.</p></details><details><summary>Pourquoi 30 simulations ?</summary><p>Le même incident est rejoué dans 30 évolutions comparables du réseau. On observe ainsi si la conséquence est stable ou si elle dépend de l’état des stocks, commandes et encours au moment de l’incident.</p></details><details><summary>Limites</summary><p>Les incidents sont imposés, pas observés. Le retard de 120 jours est un test sévère. Aucun levier d’action ni suivi généalogique des lots n’est évalué dans ce paquet. Les états 93 et 80 sont nécessaires avant tout classement final.</p></details></section>
</main><footer>Source : paquet signé op_100 30/30 · signature 0231b89f… · HTML autonome sans ressource externe.</footer>
<script>const DATA=""" + data + """;
const svg=document.getElementById('network'),detail=document.getElementById('detail'),tbody=document.getElementById('rows');let selected=null;
const fmt=(v,d=2)=>Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
function severity(v){return v>=10?'#ce3e35':v>0?'#ef9f1a':'#c7d3de'}
function label(l){return `${l.supplier} · ${l.item}`}
function reading(l){if(l.mean_loss===0)return "Dans cet état, l'incident touche bien une livraison mais les protections simulées évitent une perte de service.";if(l.median_loss===0)return "Effet de seuil : plus de la moitié des situations sont absorbées, mais certains états du réseau provoquent une rupture sévère.";if(l.affected_count>=24)return "Signal récurrent : la majorité des états simulés transmettent l'incident jusqu'au service du produit fini.";return "Signal intermittent : la conséquence dépend fortement des stocks, encours et commandes présents au moment de l'incident."}
function filtered(){const m=document.getElementById('mechanism').value,p=document.getElementById('product').value,s=document.getElementById('sensitivity').value;return DATA.lanes.filter(x=>x.mechanism===m&&(p==='all'||x.product===p)&&(s==='all'||x.mean_loss>0));}
function draw(){const lanes=filtered(),suppliers=[...new Set(lanes.map(x=>x.supplier))].sort();svg.innerHTML='';const NS='http://www.w3.org/2000/svg';const add=(tag,a={})=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(a))e.setAttribute(k,v);svg.appendChild(e);return e};add('text',{x:35,y:28,fill:'#60758b','font-size':13}).textContent='FOURNISSEURS';add('text',{x:565,y:28,fill:'#60758b','font-size':13}).textContent='SITES';add('text',{x:1000,y:28,fill:'#60758b','font-size':13}).textContent='PRODUITS';const sy={};suppliers.forEach((s,i)=>sy[s]=55+i*(885/Math.max(1,suppliers.length-1)));const py={'M-1810':300,'M-1430':680},fy={'268091':300,'268967':680};lanes.slice().sort((a,b)=>a.mean_loss-b.mean_loss).forEach(l=>{const path=add('path',{d:`M 230 ${sy[l.supplier]} C 410 ${sy[l.supplier]},440 ${py[l.plant]},570 ${py[l.plant]}`,stroke:severity(l.mean_loss),'stroke-width':Math.max(2,2+l.mean_loss/3),opacity:l.mean_loss?0.82:0.48,class:'lane'+(selected===l.lane_id?' selected':''),'data-id':l.lane_id});path.onclick=()=>{selected=l.lane_id;show(l);draw()};const p2=add('path',{d:`M 710 ${py[l.plant]} C 850 ${py[l.plant]},900 ${fy[l.product]},990 ${fy[l.product]}`,stroke:'#7aa9d6','stroke-width':4,opacity:.45,fill:'none'});});suppliers.forEach(s=>{const g=add('g',{class:'node'}),r=document.createElementNS(NS,'rect');r.setAttribute('x',35);r.setAttribute('y',sy[s]-17);r.setAttribute('width',195);r.setAttribute('height',34);r.setAttribute('rx',8);g.appendChild(r);const t=document.createElementNS(NS,'text');t.setAttribute('x',47);t.setAttribute('y',sy[s]+4);t.textContent=s;g.appendChild(t);svg.appendChild(g)});Object.entries(py).forEach(([p,y])=>{const g=add('g',{class:'node plant'});g.innerHTML=`<rect x="570" y="${y-35}" width="140" height="70" rx="13"></rect><text x="640" y="${y+5}" text-anchor="middle">${p}</text>`;svg.appendChild(g)});Object.entries(fy).forEach(([p,y])=>{const g=add('g',{class:'node product'});g.innerHTML=`<rect x="990" y="${y-35}" width="170" height="70" rx="13"></rect><text x="1075" y="${y+5}" text-anchor="middle">Produit ${p}</text>`;svg.appendChild(g)});drawTable(lanes);if(!selected&&lanes.length)show(lanes.slice().sort((a,b)=>b.mean_loss-a.mean_loss)[0]);}
function show(l){const max=Math.max(1,...l.samples),bars=l.samples.map(v=>`<i class="dot" title="${fmt(v)} points" style="height:${Math.max(2,90*v/max)}px"></i>`).join('');detail.innerHTML=`<span class="badge sim">SIMULÉ · 30 RÉPÉTITIONS</span> <span class="badge ${l.mean_loss?'high':'abs'}">${l.mean_loss?'SIGNAL À INSTRUIRE':'INCIDENT ABSORBÉ'}</span><div class="path">${esc(l.supplier)} → article ${esc(l.item)} → ${esc(l.plant)} → produit ${esc(l.product)}</div><div class="metrics"><div class="metric"><strong>${fmt(l.mean_loss)}</strong><small>points de service perdus en moyenne</small></div><div class="metric"><strong>${l.affected_count}/30</strong><small>simulations avec service dégradé</small></div><div class="metric"><strong>${fmt(l.median_loss)}</strong><small>médiane</small></div><div class="metric"><strong>${fmt(l.p10)}–${fmt(l.p90)}</strong><small>intervalle P10–P90</small></div><div class="metric"><strong>${fmt(l.late_units_mean,0)}</strong><small>quantités à l'heure perdues, moyenne</small></div><div class="metric"><strong>${fmt(l.production_loss_mean,0)}</strong><small>production non libérée, moyenne</small></div></div><div class="reading"><strong>Lecture métier</strong><br>${reading(l)}</div><h3>Les 30 résultats</h3><div class="dots">${bars}</div><p class="sub">Chaque barre est une simulation; hauteur = baisse du service. Maximum : ${fmt(l.max_loss)} points.</p><div class="reading"><strong>Exposition physique simulée</strong><br>Délai planifié : ${fmt(l.lead_days,0)} jours · volume de référence : ${fmt(l.reference_qty,0)} · ${l.reference_shipment_days} jours d'expédition dans la référence.</div>`}
function drawTable(lanes){tbody.innerHTML=lanes.slice().sort((a,b)=>b.mean_loss-a.mean_loss).map(l=>`<tr data-id="${esc(l.lane_id)}"><td><strong>${esc(l.supplier)}</strong><br>article ${esc(l.item)}</td><td>${esc(l.plant)} → ${esc(l.product)}</td><td class="num">${fmt(l.lead_days,0)} j</td><td class="num"><strong>${fmt(l.mean_loss)}</strong></td><td class="num">${fmt(l.median_loss)}</td><td class="num">${fmt(l.p10)}–${fmt(l.p90)}</td><td class="num">${l.affected_count}/30</td><td class="num">${fmt(l.late_units_mean,0)}</td><td>${reading(l)}</td></tr>`).join('');tbody.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>{const l=lanes.find(x=>x.lane_id===tr.dataset.id);selected=l.lane_id;show(l);draw()})}
['mechanism','product','sensitivity'].forEach(id=>document.getElementById(id).onchange=()=>{selected=null;draw()});document.getElementById('reset').onclick=()=>{selected=null;draw()};draw();
</script></body></html>"""


def build(source_dir: Path, lane_reference: Path, output_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    lane_reference = lane_reference.resolve()
    output_dir = output_dir.resolve(strict=False)
    if output_dir.exists():
        raise DetailedMapError(f"Destination déjà existante : {output_dir}")
    if output_dir == source_dir or output_dir.is_relative_to(source_dir):
        raise DetailedMapError("La nouvelle carte doit rester hors du paquet source.")
    payload = build_payload(source_dir, lane_reference)
    document = render_html(payload)
    output_dir.mkdir(parents=True, exist_ok=False)
    entrypoint = output_dir / ENTRYPOINT
    entrypoint.write_text(document, encoding="utf-8")
    data_path = output_dir / "donnees_carte_op_100_30_sur_30.json"
    data_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "etudecas.supplier_v8.op100_detailed_network_map.v1.package",
        "status": "complete",
        "source_package_signature": EXPECTED_PACKAGE_SIGNATURE,
        "campaign_signature": EXPECTED_CAMPAIGN_SIGNATURE,
        "engine_runs_started": 0,
        "existing_outputs_modified": False,
        "entrypoint": str(entrypoint),
        "outputs": {
            entrypoint.name: {"sha256": sha256_file(entrypoint), "size_bytes": entrypoint.stat().st_size},
            data_path.name: {"sha256": sha256_file(data_path), "size_bytes": data_path.stat().st_size},
        },
    }
    manifest_path = output_dir / "manifest_carte_detaillee_op_100.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--lane-reference", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build(args.source_dir, args.lane_reference, args.output_dir)
    except (DetailedMapError, OSError, ValueError) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
