"""Assemble an offline episode explorer from preserved, explicitly dated evidence.

No simulation, source workbook mutation, network, or production helper is used.
"""
from __future__ import annotations

import argparse
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replays', type=Path)
    parser.add_argument('--source-notes', type=Path)
    args = parser.parse_args()
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
        comparison=comp, episode_replays=None, source_notes=None,
        conventions={
            'I':'I est conservé signé. abs(I) est un proxy de comparaison, pas une livraison client mesurée.',
            'balance':'Résidu = photo finale − photo initiale − (H + I signé + G). Un résidu nul ne prouve pas la signification métier de I.',
            'stocks':'Stocks simulés physiques à l’ouverture du jour ; photos sources ponctuelles. Les points sources ne sont pas interpolés.',
            'service':'UN simulées servies / demande de la semaine. Un rattrapage de backlog peut dépasser 100 % ; ce n’est pas un taux à l’heure.',
            'finance':'CA livré / (CA livré + CA perdu), calcul financier séparé : aucune conversion en UN.',
            'scope':'A/D/E : résultats historiques 2025 conservés, qualification globale partielle. Les hypothèses de rejeu aval restent distinctes du MRP autonome.'})
    for name, path in [('episode_replays', args.replays), ('source_notes', args.source_notes)]:
        if path:
            path = path.resolve()
            data[name] = json.loads(path.read_text(encoding='utf-8'))
            inputs.append(path)
    OUT.mkdir(parents=True,exist_ok=True)
    PROOF.mkdir(parents=True,exist_ok=True)
    links = [{'label':'Ancienne navigation conservée · 102 semaines','href':str(OLD.relative_to(ROOT))},
             {'label':'Comparaison A/D/E conservée · chronologies de lots','href':str(OLD_COMPARISON.relative_to(ROOT))}] + comp['proof_links']
    data['links'] = [{'label':x['label'],'href':os.path.relpath(ROOT / x['href'],OUT).replace('\\','/')} for x in links]
    data['provenance'] = [{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in inputs]
    encoded = json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    html = Path(__file__).with_name('view.html').read_text(encoding='utf-8').replace('__PAYLOAD__',encoded)
    target = OUT / 'diagnostic_fusion.html'
    target.write_text(html,encoding='utf-8')
    (OUT/'payload.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest = dict(schema_version='diagnostic_fusion.build.v1', status='built_not_browser_validated',
        inputs=data['provenance'], outputs=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p),'bytes':p.stat().st_size} for p in [target,OUT/'payload.json']],
        preserved_originals=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in [OLD,OLD_COMPARISON]],
        episodes=len(episodes), historical_focus=len(data['focus']), scenarios=[x['id'] for x in comp['cases']],
        browser='NOT_EXECUTED: previous Windows refusal; in-memory interaction checks are separate',
        qualifications='Historical global qualification remains partial; builder does not qualify engine or industrial calibration.')
    (PROOF/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'html':str(target),'bytes':target.stat().st_size,'episodes':len(episodes),'focus':len(data['focus'])}))


if __name__ == '__main__':
    main()
