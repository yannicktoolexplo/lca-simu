"""Assemble an offline episode explorer from preserved, explicitly dated evidence.

No simulation, source workbook mutation, network, or production helper is used.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'etudecas/resultats/audit_service_reel_2025_20261020/remontee/remontee_chaine_reelle.html'
COMPARISON = ROOT / 'etudecas/resultats/aleas_prolonges_693055_20261021/report_payload.json'
OLD_COMPARISON = COMPARISON.with_name('comparaison_arrets_693055.html')
FOCUS = ROOT / 'etudecas/resultats/aleas_boucle_20261021/source_audit/episodes_sources.json'
OUT = ROOT / 'etudecas/resultats/diagnostic_fusion_20261022/interface'
PROOF = ROOT / 'etudecas/artifacts/testing/diagnostic_fusion_20261022/ui'
PREVIOUS_SUITE = ROOT / 'etudecas/resultats/diagnostic_suite_20261022/interface'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def photo_stage(episode, comparison, key, label, site):
    """Exact-date industrial photos, with no inferred availability or causality."""
    start = episode['week_start']
    end = (date.fromisoformat(start) + timedelta(days=7)).isoformat()
    photos = comparison['source_photos'].get(key, [])
    opening = next((p for p in photos if p['date'] == start), None)
    closing = next((p for p in photos if p['date'] == end), None)
    article = key.split('_')[0]
    detail = next((p for p in episode['upstream_source']
                   if str(p['article']) == article and str(p['site']) == site
                   and p['week'] == start), None)
    refs = [f"Flow_Data_Inventory_and_Replenishment_rules.xlsx / Stocks!E{p['source_row']}:H{p['source_row']}"
            for p in (opening, closing) if p is not None]
    stage = dict(id=key, label=label, article=article, site=site, date=start, date_end=end,
                 value=opening['quantity'] if opening else None,
                 value_end=closing['quantity'] if closing else None,
                 source_row=opening['source_row'] if opening else None,
                 source_end_row=closing['source_row'] if closing else None,
                 unit=comparison['entities'][key]['unit'],
                 status='Photo source' if opening else 'Photo non chargée à cette date',
                 conclusion='La présence physique ne prouve pas la disponibilité réelle.',
                 detail='Mouvements et MRP non chargés pour cette semaine.')
    if detail:
        if detail['movement_row_missing']:
            movement = 'Ligne de mouvements absente.'
        else:
            movement = (f"Entrées H : {detail['H_observed']:g} ; I signé : {detail['I_signed']:g} ; "
                        f"Scan3 : {detail['Scan3_signed']:g} {stage['unit']}.")
            row = detail['source_movement_row']
            refs.append(f'Flow_Data_Inventory_movements.xlsx / Feuille1!G{row}:J{row}')
        current_j = detail.get('MRP_current_J')
        planned = (f"J courant prévu : {current_j:g} {stage['unit']}, version {detail['MRP_vintage']}."
                   if current_j is not None else 'Disponibilité prévue inconnue.')
        stage['detail'] = movement + ' ' + planned
        if detail.get('source_MRP_row') is not None:
            row = detail['source_MRP_row']
            refs.append(f'Flow_Data_MRP_results.xlsx / Feuille1!A{row}:K{row}')
    stage['source'] = ' ; '.join(refs) if refs else 'Aucune photo embarquée à cette date exacte.'
    return stage


def add_drilldown(data):
    """A compact reading path, not an automated industrial root-cause detector."""
    for episode in data['episodes']:
        product = episode['product']
        demand, proxy = episode['demand_UN'], episode['abs_I_proxy_UN']
        gap = demand - proxy
        if demand == 0:
            summary = 'Demande source nulle cette semaine ; aucun creux sous la demande.'
        elif gap <= 0:
            summary = 'Le mouvement atteint la demande ; cela ne certifie pas les livraisons client.'
        elif episode['I_signed_UN'] > 0:
            summary = 'I est positif : ce faible mouvement ne prouve pas un manque client. Origine non établie.'
        elif episode['stock_open_UN'] >= demand:
            summary = 'Muret a du stock : le creux ne s’explique pas par le stock total initial. Origine non établie.'
        else:
            summary = 'Le stock initial est inférieur à la demande ; les entrées et leur disponibilité restent à vérifier.'
        keys = [(product+'_Muret', 'Muret · PF '+product, '1920')]
        keys += ([('693055_Avene','Avène · matière 693055','1810'),('693055_Gaillac','Gaillac · matière 693055','1450')]
                 if product == '268091' else
                 [('773474_Gien','Gien · matière 773474','1430'),('773474_Gaillac','Gaillac · matière 773474','1450')])
        stages = [photo_stage(episode,data['comparison'],*key) for key in keys]
        muret = stages[0]
        if muret['value'] is not None:
            assert muret['value'] == episode['stock_open_UN']
        if muret['value_end'] is not None:
            assert muret['value_end'] == episode['stock_close_UN']
        j = episode['MRP_J_UN']
        planned = f"{j:g} UN" if j is not None else 'inconnu'
        muret['detail'] = f"I signé : {episode['I_signed_UN']:g} UN. J courant prévu : {planned}, version {episode['MRP_vintage'] or 'inconnue'}."
        muret['conclusion'] = ('Stock initial couvrant la demande ; libération et allocation réelles inconnues.'
                              if demand > 0 and episode['stock_open_UN'] >= demand else
                              'Comparer les dates des commandes, des disponibilités et des départs.')
        muret['source'] += ' ; ' + ' ; '.join(episode['source_cells'])
        stages[-1]['conclusion'] = 'Ce stock ne démontre pas l’origine du creux à Muret.'
        episode['drilldown'] = dict(summary=summary,gap_UN=gap,
            ratio_pct=100*proxy/demand if demand>0 else None,stages=stages,
            next_check='À vérifier : commande exigible → lot libéré/réservé → départ → réception client.')
    data['low_points'] = {}
    for product in data['products']:
        lows = [e for e in data['episodes'] if e['product']==product and e['demand_UN']>0
                and e['abs_I_proxy_UN']<e['demand_UN']]
        lows.sort(key=lambda e:(Fraction(int(e['abs_I_proxy_UN']),int(e['demand_UN'])),
                                e['abs_I_proxy_UN'],e['week_start']))
        data['low_points'][product] = [e['id'] for e in lows]
    data['conventions']['low_points'] = 'Raccourcis : abs(I)/demande croissant, puis abs(I) et date ; demande nulle exclue. Ce ratio n’est pas un taux de service.'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replays', type=Path)
    parser.add_argument('--source-notes', type=Path)
    parser.add_argument('--timeliness', type=Path)
    parser.add_argument('--output-dir', type=Path, default=OUT)
    parser.add_argument('--proof-dir', type=Path, default=PROOF)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    proof = args.proof_dir.resolve()
    out.relative_to(ROOT)
    proof.relative_to(ROOT)
    old = json.loads(re.search(r'<script[^>]*id="remontee-interactive-data"[^>]*>(.*?)</script>', OLD.read_text(encoding='utf-8'), re.S).group(1))
    comp = json.loads(COMPARISON.read_text(encoding='utf-8'))
    focused = json.loads(FOCUS.read_text(encoding='utf-8'))['episodes']
    episodes = []
    for c in old['cases'].values():
        i = c['sorties_signed_qty']
        h, g = c['movement_H_entries_qty'], c['movement_G_divers_qty']
        delta = c['stock_close_qty'] - c['stock_open_qty']
        episodes.append(dict(id=c['id'], product=c['product'], week_start=c['week_start'], week_end=c['week_end'],
            demand_UN=c['demand_qty'], I_signed_UN=i, abs_I_proxy_UN=abs(i), H_UN=h, G_UN=g,
            stock_open_UN=c['stock_open_qty'], stock_close_UN=c['stock_close_qty'], delta_photo_UN=delta,
            residual_UN=delta - (h+i+g), MRP_J_UN=c['dc_mrp_available_qty'], MRP_projected_UN=c['dc_mrp_projected_qty'],
            MRP_vintage=c['dc_mrp_vintage'], financial_lost_pct=c['ca_lost_pct'], source_cells=c['source_cells']))
    for e in episodes:
        f = next((x for x in focused if str(x['product']) == e['product'] and x['week'] == e['week_start']), None)
        e['upstream_source'] = [x for x in f['upstream_current_points'] if str(x['article']) in {'693055','773474'}] if f else []
    inputs = [OLD, COMPARISON, OLD_COMPARISON, FOCUS, Path(__file__), Path(__file__).with_name('view.html')]
    data = dict(schema_version='diagnostic_fusion.v1', period={'start':'2025-01-01','end':'2025-12-31'},
        products=old['products'], episodes=sorted(episodes,key=lambda e:(e['product'],e['week_start'])),
        focus=[{'id':'w-'+str(p['product'])+'-'+p['week'],'label':'Proxy abs(I) sous demande · bilan et réserves','historical':True} for p in focused],
        comparison=comp, episode_replays=None, source_notes=None, episode_timeliness=None,
        conventions={
            'I':'I est conservé signé. abs(I) est un proxy de comparaison, pas une livraison client mesurée.',
            'balance':'Résidu = photo finale − photo initiale − (H + I signé + G). Un résidu nul ne prouve pas la signification métier de I.',
            'stocks':'Stocks simulés physiques à l’ouverture du jour ; photos sources ponctuelles. Les points sources ne sont pas interpolés.',
            'service':'UN simulées servies / demande de la semaine. Un rattrapage de backlog peut dépasser 100 % ; ce n’est pas un taux à l’heure.',
            'finance':'CA livré / (CA livré + CA perdu), calcul financier séparé : aucune conversion en UN.',
            'scope':'A/D/E : résultats historiques 2025 conservés, qualification globale partielle. Les hypothèses de rejeu aval restent distinctes du MRP autonome.'})
    for name, path in [('episode_replays', args.replays), ('source_notes', args.source_notes), ('episode_timeliness', args.timeliness)]:
        if path:
            path = path.resolve()
            data[name] = json.loads(path.read_text(encoding='utf-8'))
            inputs.append(path)
    add_drilldown(data)
    out.mkdir(parents=True,exist_ok=True)
    proof.mkdir(parents=True,exist_ok=True)
    links = [{'label':'Ancienne navigation conservée · 102 semaines','href':str(OLD.relative_to(ROOT))},
             {'label':'Comparaison A/D/E conservée · chronologies de lots','href':str(OLD_COMPARISON.relative_to(ROOT))}] + comp['proof_links']
    previous = OUT/'diagnostic_fusion.html'
    preserved = [OLD, OLD_COMPARISON]
    if out != OUT.resolve() and previous.is_file():
        links.append({'label':'Fusion précédente conservée · livraison du 22 octobre','href':str(previous.relative_to(ROOT))})
        preserved += [previous, OUT/'payload.json', PROOF/'final_manifest.json']
    if out != PREVIOUS_SUITE.resolve() and (PREVIOUS_SUITE/'diagnostic_fusion.html').is_file():
        links.append({'label':'Vue détaillée précédente conservée','href':str((PREVIOUS_SUITE/'diagnostic_fusion.html').relative_to(ROOT))})
        preserved += [PREVIOUS_SUITE/'diagnostic_fusion.html',PREVIOUS_SUITE/'payload.json']
    data['links'] = [{'label':x['label'],'href':os.path.relpath(ROOT / x['href'],out).replace('\\','/')} for x in links]
    data['provenance'] = [{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in inputs]
    encoded = json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    html = Path(__file__).with_name('view.html').read_text(encoding='utf-8').replace('__PAYLOAD__',encoded)
    target = out / 'diagnostic_fusion.html'
    target.write_text(html,encoding='utf-8')
    (out/'payload.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest = dict(schema_version='diagnostic_fusion.build.v1', status='built_not_browser_validated',
        inputs=data['provenance'], outputs=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p),'bytes':p.stat().st_size} for p in [target,out/'payload.json']],
        preserved_originals=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in preserved],
        episodes=len(episodes), historical_focus=len(data['focus']), scenarios=[x['id'] for x in comp['cases']],
        browser='NOT_EXECUTED: previous Windows refusal; in-memory interaction checks are separate',
        qualifications='Historical global qualification remains partial; builder does not qualify engine or industrial calibration.')
    (proof/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'html':str(target),'bytes':target.stat().st_size,'episodes':len(episodes),'focus':len(data['focus'])}))


if __name__ == '__main__':
    main()
