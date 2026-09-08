#!/usr/bin/env python3
"""Build an additive, offline 021081 order-book and lot drill-down.

The page only consumes completed campaign outputs.  Multiple campaign packages
can be shown side by side, but their provenance remains explicit: rows are not
pooled into a supposedly homogeneous statistical sample.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


BASELINE_ID = "baseline_observed_order_book"
AUDIT_NAME = "opening_purchase_order_supplier_risk_audit_021081.csv"
LEDGER_NAME = "order_book_overlay_ledger.csv"
COMPARISON_NAME = "receipt_paired_causal_comparison.csv"
SUMMARY_NAME = "causal_lot_proof_summary.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_int(value: Any, default: int = -1) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def first_existing(root: Path, names: Iterable[str]) -> Path:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No completed metric file found under {root}")


def scenario_labels(root: Path) -> dict[str, dict[str, str]]:
    path = root / "scenario_design.csv"
    if not path.exists():
        return {}
    return {str(row.get("scenario_id") or ""): row for row in read_csv(path)}


def select_screening_rows(root: Path) -> list[dict[str, str]]:
    metric_path = first_existing(
        root,
        (
            "screening_metrics.csv",
            "unit_sensitivity_metrics.csv",
        ),
    )
    rows = read_csv(metric_path)
    selected: dict[tuple[str, str, int], dict[str, str]] = {}
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "")
        state = str(row.get("state_regime") or "")
        seed = as_int(row.get("seed"))
        if not scenario_id or not state or seed < 0:
            continue
        stage = str(row.get("stage") or "").lower()
        if "confirmation" in stage:
            continue
        selected.setdefault((state, scenario_id, seed), row)
    return list(selected.values())


def audit_rows(case_dir: Path, days: int) -> list[dict[str, Any]]:
    path = case_dir / "proofs" / AUDIT_NAME
    native_rows = read_csv(path) if path.exists() else []
    output: list[dict[str, Any]] = []
    for row in native_rows:
        usable_after = as_int(row.get("usable_day_after"))
        output.append(
            {
                "source_row": str(row.get("source_row") or ""),
                "shipment_id": str(row.get("shipment_id") or ""),
                "supplier_id": str(row.get("supplier_id") or ""),
                "planned_qty_before": as_float(row.get("planned_qty_before")),
                "pulled_qty_after": as_float(row.get("pulled_qty_after")),
                "physical_shipped_qty_after": as_float(
                    row.get("physical_shipped_qty_after")
                ),
                "usable_qty_after": as_float(row.get("usable_qty_after")),
                "physical_day_before": as_int(
                    row.get("physical_delivery_day_before")
                ),
                "physical_day_after": as_int(
                    row.get("physical_delivery_day_after")
                ),
                "usable_day_before": as_int(row.get("usable_day_before")),
                "usable_day_after": usable_after,
                "risk_event_ids": str(row.get("risk_event_ids") or ""),
                "risk_types": str(row.get("risk_types") or ""),
                "unsupported_risk_types": str(
                    row.get("unsupported_risk_types") or ""
                ),
                "application_layer": "moteur natif sur commandes d’ouverture",
                "horizon_status": (
                    "non disponible dans l’horizon"
                    if usable_after < 0 or usable_after > days
                    else "disponible dans l’horizon"
                ),
            }
        )
    if not output:
        ledger_path = case_dir / "proofs" / LEDGER_NAME
        for row in read_csv(ledger_path) if ledger_path.exists() else []:
            usable_after = as_int(row.get("simulated_usable_day"))
            simulated_qty = as_float(row.get("simulated_usable_quantity_kg"))
            output.append(
                {
                    "source_row": str(row.get("source_row") or ""),
                    "shipment_id": str(row.get("observed_order_id") or ""),
                    "supplier_id": str(row.get("supplier_id") or ""),
                    "planned_qty_before": as_float(
                        row.get("observed_quantity_kg")
                    ),
                    "pulled_qty_after": simulated_qty,
                    "physical_shipped_qty_after": simulated_qty,
                    "usable_qty_after": simulated_qty,
                    "physical_day_before": as_int(
                        row.get("source_planned_physical_delivery_day")
                    ),
                    "physical_day_after": as_int(
                        row.get("simulated_physical_delivery_day")
                    ),
                    "usable_day_before": as_int(
                        row.get("source_planned_usable_day")
                    ),
                    "usable_day_after": usable_after,
                    "risk_event_ids": "",
                    "risk_types": str(row.get("mechanism") or ""),
                    "unsupported_risk_types": "",
                    "application_layer": (
                        "overlay FIFO explicite avant moteur — "
                        + str(row.get("order_risk_application_layer") or "")
                    ),
                    "horizon_status": (
                        "non disponible dans l’horizon"
                        if usable_after < 0 or usable_after > days
                        else "disponible dans l’horizon"
                    ),
                }
            )
    output.sort(key=lambda row: (as_int(row["physical_day_before"]), as_int(row["source_row"])))
    return output


def package_payload(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "campaign_manifest.json"
    manifest = read_json(manifest_path)
    if str(manifest.get("status") or "") != "complete":
        raise ValueError(f"Campaign package is not complete: {root}")
    labels = scenario_labels(root)
    cases: list[dict[str, Any]] = []
    for row in select_screening_rows(root):
        state = str(row.get("state_regime") or "")
        scenario_id = str(row.get("scenario_id") or "")
        seed = as_int(row.get("seed"))
        case_dir = root / "cases" / state / scenario_id / f"seed_{seed}"
        audits = audit_rows(case_dir, as_int(row.get("days"), as_int(manifest.get("days"), 720)))
        if len(audits) != 23:
            # The page is an evidence viewer for the audited 23-line order book;
            # omit incomplete cases rather than silently showing a partial ledger.
            continue
        design = labels.get(scenario_id, {})
        cases.append(
            {
                "key": f"{root.name}::{state}::{scenario_id}::{seed}",
                "package_id": root.name,
                "state_regime": state,
                "state_evidence_class": str(
                    row.get("state_regime_evidence_class") or ""
                ),
                "target_cover_days": str(
                    row.get("state_regime_target_cover_days") or ""
                ),
                "scenario_id": scenario_id,
                "scenario_label": str(
                    design.get("label")
                    or design.get("mechanism_label")
                    or scenario_id
                ),
                "scope_id": str(row.get("scope_id") or design.get("scope_id") or ""),
                "mechanism": str(row.get("mechanism") or ""),
                "seed": seed,
                "days": as_int(row.get("days"), 720),
                "order_count": as_int(row.get("observed_order_count"), 23),
                "planned_qty_kg": as_float(row.get("observed_order_qty_kg")),
                "usable_qty_kg": as_float(
                    row.get("order_book_simulated_usable_qty_kg")
                ),
                "quantity_loss_kg": as_float(
                    row.get("order_book_simulated_quantity_loss_kg")
                    or row.get("overlay_quantity_loss_kg")
                ),
                "weighted_usable_shift_days": as_float(
                    row.get("order_book_weighted_planned_usable_date_shift_days")
                    or row.get("overlay_weighted_usable_delay_days")
                ),
                "after_horizon_qty_kg": as_float(
                    row.get("order_book_after_horizon_qty_kg")
                ),
                "product_on_due": as_float(row.get("product_on_due_volume_proxy")),
                "product_on_due_delta": as_float(
                    row.get("product_on_due_delta_vs_paired_baseline")
                ),
                "product_backlog_delta": as_float(
                    row.get("product_backlog_qty_days_delta_vs_paired_baseline")
                ),
                "component_stock_min_kg": as_float(
                    row.get("component_stock_min_qty_kg")
                ),
                "audits": audits,
            }
        )
    cases.sort(
        key=lambda row: (
            row["state_regime"],
            0 if row["scenario_id"] == BASELINE_ID else 1,
            row["scenario_id"],
            row["seed"],
        )
    )
    return {
        "package_id": root.name,
        "root_name": root.name,
        "manifest_sha256": sha256_file(manifest_path),
        "orchestrator_sha256": str(
            manifest.get("orchestrator_sha256_at_process_start")
            or manifest.get("orchestrator_sha256")
            or "non enregistré"
        ),
        "source_graph_sha256": str(manifest.get("source_graph_sha256") or ""),
        "engine_sha256": str(manifest.get("engine_sha256") or ""),
        "status": str(manifest.get("status") or ""),
        "case_count_in_page": len(cases),
        "cases": cases,
    }


def causal_payload(proof_dir: Path) -> dict[str, Any]:
    proof_dir = proof_dir.resolve()
    summary_path = proof_dir / SUMMARY_NAME
    comparison_path = proof_dir / COMPARISON_NAME
    summary = read_json(summary_path)
    comparison = read_csv(comparison_path)
    return {
        "key": (
            f"{Path(str(summary.get('campaign_root') or '')).name}::"
            f"{summary.get('state_regime')}::{summary.get('scenario_id')}::"
            f"{summary.get('seed')}"
        ),
        "summary": summary,
        "comparison": comparison,
        "summary_sha256": sha256_file(summary_path),
        "comparison_sha256": sha256_file(comparison_path),
    }


def build_payload(
    campaign_roots: Sequence[Path], causal_proof_dirs: Sequence[Path]
) -> dict[str, Any]:
    packages = [package_payload(root) for root in campaign_roots]
    cases = [case for package in packages for case in package.pop("cases")]
    if not cases:
        raise ValueError("No complete 23-line case can be displayed")
    proofs = [causal_payload(path) for path in causal_proof_dirs]
    return {
        "schema_version": "supplier-021081-standalone-drilldown.v1",
        "snapshot_date": "2025-01-01",
        "item_id": "021081",
        "intermediate_item_id": "773474",
        "finished_item_id": "268967",
        "packages": packages,
        "cases": cases,
        "causal_proofs": proofs,
        "scientific_alerts": {
            "order_book": (
                "23 lignes de commandes planifiées présentes dans le snapshot ERP; "
                "ce ne sont ni des livraisons historiques ni une mesure OTIF."
            ),
            "source_row": (
                "source_row est le numéro technique de ligne du snapshot ERP; "
                "ce n’est ni un numéro de lot industriel ni un numéro de commande fiable."
            ),
            "unit": (
                "Unité à valider avec l’industriel : le graphe exécute 8,94 kg de "
                "021081 pour 1000 g de 773474. Une sensibilité ÷1000 est une "
                "hypothèse, pas une correction acquise."
            ),
            "masking": (
                "L’absence d’effet client dans une configuration signifie que les "
                "stocks et productions amont testés masquent l’incident; elle ne "
                "démontre pas la résilience de la chaîne."
            ),
        },
        "masking_audit": {
            "released_268967_lot_count": 29,
            "approx_horizon_need_g": 30182579.4116,
            "opening_stock_total_g": 24193000,
            "horizon_773474_production_g": 28800000,
            "stock_multiple_of_horizon_need": 0.8015550848,
            "stock_plus_production_multiple_of_horizon_need": 1.7557478861,
            "021081_stock_multiple_of_horizon_intermediate_consumption": 4.4358221477,
            "021081_order_book_multiple_of_horizon_intermediate_consumption": 5.1267710664,
        },
    }


def json_for_script(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def render_html(payload: Mapping[str, Any]) -> str:
    data = json_for_script(payload)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>021081 — commandes, incident et lots</title>
<style>
:root{{--ink:#102a43;--muted:#52677d;--line:#d8e2ec;--navy:#0b3558;--blue:#1769aa;--bg:#eef3f8;--red:#a62929;--amber:#8a5b00;--green:#176447}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.48 Inter,Segoe UI,Arial,sans-serif}}main{{max-width:1500px;margin:auto;padding:24px}}h1{{font-size:29px;margin:0 0 5px}}h2{{font-size:20px;margin:0 0 12px}}h3{{font-size:16px;margin:0 0 8px}}p{{margin:5px 0}}.lede{{font-size:17px;color:var(--muted)}}.card{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;margin:15px 0;box-shadow:0 6px 22px #183b5610}}.alert{{border-left:6px solid var(--red);background:#fff7f7}}.note{{border-left:6px solid var(--blue);background:#f5faff}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:12px}}.kpi{{padding:14px;border:1px solid var(--line);border-radius:12px;background:#f8fbfd}}.kpi b{{display:block;font-size:23px;color:var(--navy)}}label{{display:block;font-weight:750;margin-bottom:7px}}select{{width:100%;padding:11px;border:1px solid #9fb3c8;border-radius:9px;background:white;color:var(--ink);font-size:14px}}.status{{display:inline-block;padding:4px 9px;border-radius:999px;font-weight:750;font-size:12px}}.in{{background:#e8f7ef;color:var(--green)}}.out{{background:#fdecec;color:var(--red)}}.none{{background:#edf2f7;color:var(--muted)}}.table-wrap{{overflow:auto;max-height:620px;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:separate;border-spacing:0;width:100%;min-width:1160px;background:#fff}}th,td{{padding:9px 10px;border-bottom:1px solid #e7edf3;text-align:left;white-space:nowrap}}th{{position:sticky;top:0;background:#eaf1f7;color:#183b56;z-index:1}}tr:hover td{{background:#f6faff}}.small{{font-size:12px;color:var(--muted)}}.term-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.term-grid div{{background:#f7fafc;border-radius:10px;padding:11px}}.term-grid b{{display:block;color:var(--navy)}}.provenance code{{font-size:11px;overflow-wrap:anywhere;white-space:normal}}.hide{{display:none}}.verdict{{font-size:16px;font-weight:650;padding:12px;border-radius:10px;background:#f0f6fb}}.trace-empty{{padding:18px;border:1px dashed #a9b8c7;border-radius:10px;color:var(--muted)}}@media(max-width:900px){{.grid,.term-grid{{grid-template-columns:1fr 1fr}}main{{padding:12px}}}}@media print{{body{{background:#fff}}.card{{box-shadow:none;break-inside:avoid}}select{{border:0}}}}
</style></head><body><main>
<header><h1>Composant 021081 : de la commande planifiée au lot client</h1><p class="lede">Une lecture traçable des 23 lignes du carnet, des incidents simulés et de leur propagation — ou de leur masquage — jusqu’à 773474 et 268967.</p></header>
<section class="card term-grid"><div><b>OBSERVÉ</b>État du snapshot industriel fourni, à valider avec vos équipes.</div><div><b>SIMULÉ</b>Conséquence calculée par le moteur, pas un fait historique.</div><div><b>SIGNAL DE PRIORITÉ</b>Dossier qui mérite une instruction métier, pas une probabilité.</div><div><b>HYPOTHÈSE</b>Incident, niveau de stock ou action à valider avant décision.</div></section>
<section class="card alert"><h2>Point bloquant à valider avant toute conclusion quantitative</h2><p id="unitAlert"></p></section>
<section class="card"><h2>Pourquoi un incident fournisseur peut ne pas apparaître chez le client</h2><div class="grid"><div class="kpi"><b>29 lots</b>de 268967 libérés sur 720 jours</div><div class="kpi"><b>80,2 %</b>du besoin 773474 déjà en stock au J0</div><div class="kpi"><b>175,6 %</b>du besoin couvert par stock + production 773474</div><div class="kpi"><b>5,13×</b>la consommation 021081 couverte par le carnet planifié</div></div><p class="small" id="maskingText"></p></section>
<section class="card"><h2>Choisir une configuration testée</h2><label for="caseSelect">Paquet · état de stock · incident · graine</label><select id="caseSelect"></select><p class="small" id="caseClass"></p></section>
<section class="card"><h2>Lecture métier du scénario</h2><div class="grid"><div class="kpi"><b id="plannedQty">—</b>quantité planifiée</div><div class="kpi"><b id="usableQty">—</b>quantité utilisable simulée</div><div class="kpi"><b id="delay">—</b>décalage moyen pondéré</div><div class="kpi"><b id="clientService">—</b>service produit simulé</div></div><p class="verdict" id="verdict"></p></section>
<section class="card"><h2>Les 23 lignes du carnet, avant et après l’incident</h2><p>La date physique indique l’arrivée sur site. La date utilisable inclut la libération qualité simulée. Une ligne hors horizon n’autorise pas à inventer une date de récupération.</p><div class="table-wrap"><table><thead><tr><th>Ligne technique</th><th>Fournisseur</th><th>Quantité planifiée</th><th>Tirée</th><th>Expédiée</th><th>Utilisable</th><th>Arrivée physique avant → après</th><th>Disponible avant → après</th><th>Risque simulé</th><th>Statut</th></tr></thead><tbody id="orderRows"></tbody></table></div><p class="small" id="sourceRowText"></p></section>
<section class="card"><h2>Preuve causale sur les lots</h2><p>Un « lot exposé » signifie qu’un lot simulé descend d’une réception touchée; sa quantité complète est une borne haute. On parle d’effet causal uniquement si la date ou la quantité diffère de la baseline de même graine.</p><div id="traceContent"></div></section>
<section class="card provenance"><h2>Provenance des paquets affichés</h2><p>Les paquets restent séparés. Cette page les juxtapose pour lecture; elle ne les fusionne pas en un échantillon statistique homogène.</p><div id="provenance"></div></section>
</main><script id="payload" type="application/json">{data}</script><script>
const DATA=JSON.parse(document.getElementById('payload').textContent);const byId=id=>document.getElementById(id);const nf=new Intl.NumberFormat('fr-FR',{{maximumFractionDigits:1}});const pct=new Intl.NumberFormat('fr-FR',{{style:'percent',maximumFractionDigits:2}});
const fmtQty=v=>nf.format(Number(v||0))+' kg';const fmtDay=v=>{{v=Number(v);if(!Number.isFinite(v)||v<0)return 'non disponible';const d=new Date(Date.UTC(2025,0,1+v));return 'J'+v+' ('+d.toLocaleDateString('fr-FR',{{timeZone:'UTC'}})+')'}};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function labelCase(c){{const base=c.scenario_id==='{BASELINE_ID}'?'Fonctionnement de référence':c.scenario_label;return `${{c.package_id}} · ${{c.state_regime}} · ${{base}} · graine ${{c.seed}}`}}
function renderCase(c){{byId('caseClass').textContent=`Statut de l’état : ${{c.state_evidence_class||'non renseigné'}}${{c.target_cover_days?' · couverture 021081 hypothétique '+c.target_cover_days+' jours':''}}.`;byId('plannedQty').textContent=fmtQty(c.planned_qty_kg);byId('usableQty').textContent=fmtQty(c.usable_qty_kg);byId('delay').textContent=nf.format(c.weighted_usable_shift_days)+' jours';byId('clientService').textContent=pct.format(c.product_on_due);
let v;if(c.scenario_id==='{BASELINE_ID}')v='Référence simulée avec les 23 commandes planifiées rejouées. Elle sert de point de comparaison; elle ne décrit pas l’OTIF historique.';else if(Math.abs(c.product_on_due_delta)<1e-12&&Math.abs(c.product_backlog_delta)<1e-9)v=`L’incident testé retire ${{fmtQty(c.quantity_loss_kg)}} et décale les disponibilités de ${{nf.format(c.weighted_usable_shift_days)}} jours en moyenne pondérée. Aucun écart client n’apparaît dans cet état : les couches de stock et de production le masquent; ce n’est pas une preuve de résilience.`;else v=`L’incident produit un effet aval dans cette configuration : variation de service ${{nf.format(100*c.product_on_due_delta)}} point(s), variation de retard cumulé ${{nf.format(c.product_backlog_delta)}} unité·jour. Il faut confirmer ce cas avec les graines appariées.`;byId('verdict').textContent=v;
byId('orderRows').innerHTML=c.audits.map(r=>`<tr><td><b>${{esc(r.source_row)}}</b><div class="small">${{esc(r.shipment_id)}}</div></td><td>${{esc(r.supplier_id)}}</td><td>${{fmtQty(r.planned_qty_before)}}</td><td>${{fmtQty(r.pulled_qty_after)}}</td><td>${{fmtQty(r.physical_shipped_qty_after)}}</td><td>${{fmtQty(r.usable_qty_after)}}</td><td>${{fmtDay(r.physical_day_before)}} → ${{fmtDay(r.physical_day_after)}}</td><td>${{fmtDay(r.usable_day_before)}} → ${{fmtDay(r.usable_day_after)}}</td><td>${{esc(r.risk_types||'aucun')}}<div class="small">${{esc(r.application_layer||'')}}</div></td><td><span class="status ${{r.horizon_status.startsWith('non')?'out':'in'}}">${{esc(r.horizon_status)}}</span></td></tr>`).join('');renderTrace(c)}}
function renderTrace(c){{const proof=DATA.causal_proofs.find(p=>p.key===c.key);if(!proof){{byId('traceContent').innerHTML='<div class="trace-empty">Aucune preuve causale appariée n’a été calculée pour cette sélection. La table des commandes reste disponible, mais aucune exposition de lot ne doit être déduite sans traversée native de la généalogie.</div>';return}}const s=proof.summary;const rows=proof.comparison;let intro=s.technical_rows_with_any_descendant>0?`${{s.technical_rows_with_any_descendant}} ligne(s) technique(s) ont des descendants simulés dans l’horizon; ${{s.technical_rows_with_paired_descendant_effect||0}} modifient la date ou la quantité d’un descendant apparié. Les ${{s.technical_rows_with_paired_receipt_effect||s.technical_rows_with_paired_causal_effect}} réceptions décalées ne doivent pas être confondues avec un effet client.`:'Les réceptions touchées ne sont pas consommées dans l’horizon testé : aucun descendant natif à attribuer.';byId('traceContent').innerHTML=`<p class="verdict">${{esc(intro)}}</p><div class="table-wrap"><table><thead><tr><th>Ligne technique</th><th>Fournisseur</th><th>Disponible avant → après</th><th>Descendants 773474</th><th>Descendants 268967</th><th>Livraisons client</th><th>Conclusion appariée</th></tr></thead><tbody>${{rows.map(r=>`<tr><td>${{esc(r.source_row)}}</td><td>${{esc(r.supplier_id)}}</td><td>J${{esc(r.planned_usable_day_before)}} → J${{esc(r.simulated_usable_day_after)}}</td><td>${{esc(r.stress_intermediate_descendant_lot_count||0)}}</td><td>${{esc(r.stress_finished_descendant_lot_count||0)}}</td><td>${{esc(r.stress_customer_delivery_link_count||0)}}</td><td>${{String(r.causal_effect_on_descendants).toLowerCase()==='true'?'effet sur descendant simulé':String(r.causal_effect_on_receipt).toLowerCase()==='true'?'réception décalée, aucun descendant modifié':'aucun écart apparié'}}</td></tr>`).join('')}}</tbody></table></div>`}}
const sel=byId('caseSelect');DATA.cases.forEach((c,i)=>{{const o=document.createElement('option');o.value=String(i);o.textContent=labelCase(c);sel.appendChild(o)}});sel.addEventListener('change',()=>renderCase(DATA.cases[Number(sel.value)]));byId('unitAlert').textContent=DATA.scientific_alerts.unit;byId('maskingText').textContent=DATA.scientific_alerts.masking;byId('sourceRowText').textContent=DATA.scientific_alerts.source_row+' '+DATA.scientific_alerts.order_book;byId('provenance').innerHTML=DATA.packages.map(p=>`<p><b>${{esc(p.package_id)}}</b> — ${{p.case_count_in_page}} cas affichables — statut ${{esc(p.status)}}<br><code>manifest ${{esc(p.manifest_sha256)}} · orchestrateur ${{esc(p.orchestrator_sha256)}} · moteur ${{esc(p.engine_sha256)}} · graphe ${{esc(p.source_graph_sha256)}}</code></p>`).join('');renderCase(DATA.cases[0]);
</script></body></html>"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", action="append", required=True)
    parser.add_argument("--causal-proof-dir", action="append", default=[])
    parser.add_argument("--output-html", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        [Path(path) for path in args.campaign_root],
        [Path(path) for path in args.causal_proof_dir],
    )
    output = Path(args.output_html).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(payload), encoding="utf-8")
    print(
        f"[OK] standalone 021081 drill-down: {output} "
        f"({len(payload['cases'])} cases, {len(payload['causal_proofs'])} causal proofs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
