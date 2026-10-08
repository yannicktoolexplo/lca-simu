"""Small standalone view of the local MRP bench; no engine or browser runs.

python -B -m etudecas.visualization.maps.local_mrp_view
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = ROOT / "etudecas/artifacts/testing/mrp_local_20261007"
OUTPUT = ROOT / "etudecas/resultats/mrp_local_20261007/comparaison.html"
ORIGIN = date(2025, 1, 1)
FOCUS = ("2025-01-05", "2025-03-30", "2025-06-29", "2025-09-28")
SITES = {"1810": "Avène", "1430": "Gien"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def esc(value):
    return html.escape(str(value), quote=True)


def num(value, places=3):
    return "Non renseigné" if value is None else f"{float(value):,.{places}f}".replace(",", "\u202f").replace(".", ",")


def when(day):
    return "Aucun" if day is None else (ORIGIN + timedelta(days=day)).isoformat()


def cell(value, pointer, places=3):
    attrs = f' data-path="{esc(pointer)}"'
    if value is not None:
        attrs += f' data-value="{float(value):.12g}"'
    return f'<td{attrs}>{num(value, places)}</td>'


def daycell(value, pointer):
    attrs = f' data-path="{esc(pointer)}"'
    if value is not None:
        attrs += f' data-day="{value}"'
    return f'<td{attrs}>{when(value)}</td>'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join(f'<th scope="col">{esc(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def build_view(bench, contract, output):
    cases = bench["cases"]
    indexed = {(c["article"], c["vintage"], c["current_week_assumption"], c["fixed_floor_mode"]): (i, c) for i, c in enumerate(cases)}
    inputs = {v["snapshot_id"]: (i, v) for i, v in enumerate(bench["inputs"])}
    def get(article, vintage, current="entirely_remaining", floor="additive"):
        return indexed[article, vintage, current, floor]
    def link(path, label):
        return f'<a href="{esc(Path(os.path.relpath(ROOT / path, output.parent)).as_posix())}">{esc(label)}</a>'
    parts = ['''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Banc MRP local — 049371 et trois contrôles</title>
<style>
:root{color-scheme:light;--ink:#173343;--muted:#526b78;--line:#d5e2e7;--accent:#146a70}
*{box-sizing:border-box}body{margin:0;background:#f3f7f7;color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:1370px;margin:auto;padding:28px 24px 60px}header{padding:12px 0}h1{font-size:2.25rem;line-height:1.15;margin:.4em 0}
h2{font-size:1.5rem;margin:0 0 16px}h3{font-size:1.12rem}p{max-width:105ch}a{color:#075f70;text-underline-offset:3px}
.eyebrow{font-size:.8rem;text-transform:uppercase;letter-spacing:.12em;color:var(--accent)}nav{display:flex;gap:10px 24px;flex-wrap:wrap;margin:24px 0}
section{padding:24px;border:1px solid var(--line);background:white;border-radius:12px;margin:24px 0;scroll-margin-top:16px}
.notice{padding:16px 20px;border-left:5px solid #b67332;background:#fff4e7;margin:20px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.metric{background:#e5f1f0;padding:16px;border-radius:8px}.metric strong{display:block;font-size:1.8rem;color:var(--accent)}small,.muted,footer{color:var(--muted)}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:.87rem;margin:14px 0}th,td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:right}
th{background:#edf3f5;font-size:.8rem}td:first-child,th:first-child{text-align:left}td[data-value],td[data-day]{font-variant-numeric:tabular-nums;white-space:nowrap}
tr.focus{background:#eef7f4}code{font-size:.88em;overflow-wrap:anywhere}details{margin:18px 0}summary{font-weight:600;cursor:pointer}
.label{display:inline-block;font-size:.8rem;background:#eef2f6;padding:2px 7px;border-radius:4px}.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:720px){main{padding:16px 12px}section{padding:16px}.two{grid-template-columns:1fr}h1{font-size:1.8rem}}
@media print{body{background:white}nav{display:none}section{break-inside:avoid}main{padding:0}}
</style></head><body><main><header><div class="eyebrow">Identification locale · expérience A · 7 octobre 2026</div>
<h1>049371 : le besoin industriel fait apparaître un besoin d’achat</h1>
<p>Le planificateur existant est confronté à des besoins I et des stocks J sources, avec les seuls engagements initiaux encore futurs.
Les propositions sont conditionnelles : <strong>les nouvelles commandes ERP et le périmètre Scan3 restent inconnus</strong>.</p>
<nav><a href="#focus">049371</a><a href="#dates">Quantités et dates</a><a href="#controls">Trois contrôles</a>
<a href="#rules">Règles et paramètres</a><a href="#coverage">Toutes les versions</a><a href="#proof">Preuves et suite</a></nav></header>''']
    partial = sum(v["coverage"]["present_week_count"] < 52 for v in bench["inputs"])
    parts.append(f'''<div class="grid"><div class="metric"><strong>{bench['snapshot_count']}</strong>états sources indépendants<br><small>4 couples × 52 versions ; pas un parcours annuel.</small></div>
<div class="metric"><strong>{bench['case_count']}</strong>plans sous hypothèses explicites<br><small>Deux états de I courant × deux modes de protection.</small></div>
<div class="metric"><strong>{partial} / {bench['snapshot_count']}</strong>horizons avec semaines absentes<br><small>Les absences restent inconnues.</small></div></div>
<div class="notice">Ces plans se recouvrent sur 52 semaines : <strong>ne jamais additionner leurs propositions comme des achats annuels</strong>.
Les dates futures peuvent aller en 2026 ; aucune simulation physique 2026 n'est exécutée. C8R et le moteur physique sont conservés.</div>
<section id="focus"><h2>049371 · Avène : quatre décisions locales</h2>
<p>Hypothèse affichée : I de la semaine courante entièrement restant. Protection additive, sécurité 40 jours ouvrés + 888 kg,
standard 1 600 kg traité comme minimum/multiple par convention C8R. Les achats initiaux conservent leurs quantités de 1 800 kg et leurs dates propres.</p>''')
    rows = []
    for vintage in FOCUS:
        i, c = get("049371", vintage)
        j, inp = inputs[c["source_snapshot_id"]]
        b = c["quantity_bounds"]
        row = f'<tr class="focus"><td>{vintage}</td>'
        for field in ["documented_requirements", "available_J", "later_existing_J", "initial_external_commitments", "unprotected_net_lower_bound", "net_plus_fixed_floor_lower_bound"]:
            row += cell(b[field], f"/cases/{i}/quantity_bounds/{field}")
        row += cell(c["proposed_qty"], f"/cases/{i}/proposed_qty", 0)
        row += cell(inp["coverage"]["present_week_count"], f"/inputs/{j}/coverage/present_week_count", 0)
        rows.append(row + '</tr>')
    parts.append(table(["Version", "I connu (kg)", "J disponible", "J libéré plus tard", "Encours initiaux futurs", "Déficit net", "+ plancher 888", "Propositions nouvelles", "Semaines / 52"], rows))
    parts.append('''<p>Au 30 mars : <code>26 196 − (5 221,240 + 1 800) − 10 800 = 8 374,760 kg</code>,
avant sécurité et lots. Le plan propose 9 600 kg au total sur son horizon, sans utiliser H comme couverture.
Cela ne démontre pas que 9 600 kg de commandes manquent réellement dans l'ERP.</p>
<p>Pour isoler le seul effet du volume des besoins dans l'état C8R du même jour : disponible 12 911,930 + engagements 10 800 = 23 711,930 kg.
Sur les fenêtres couvertes, les 4 388,275 kg reconstruits donnent un déficit nul, contre 2 325,499 kg avec les 26 037,429 kg industriels.
Cette substitution arithmétique à état figé n'est pas une simulation physique. Le snapshot brut ci-dessus a une autre répartition et un autre état de stock.</p>
<h3>Le statut de la semaine courante change le résultat</h3>
<p>« Exclu » suppose que I courant est déjà absorbé ; ce n'est pas une règle choisie parce qu'elle améliore un score.</p>''')
    rows = []
    for vintage in FOCUS:
        row = f'<tr><td>{vintage}</td>'
        for current, floor in [("entirely_remaining", "additive"), ("entirely_remaining", "maximum"), ("excluded", "additive"), ("excluded", "maximum")]:
            i, c = get("049371", vintage, current, floor)
            row += cell(c["proposed_qty"], f"/cases/{i}/proposed_qty", 0)
        rows.append(row + '</tr>')
    parts.append(table(["Version", "Courant restant · addition (kg)", "Courant restant · maximum", "Courant exclu · addition", "Courant exclu · maximum"], rows))
    parts.append('<p>Une quantité identique peut cacher des dates différentes. Le choix addition/maximum reste une hypothèse locale ; aucune adoption globale n’est déduite de ce tableau.</p></section>')
    parts.append('''<section id="dates"><h2>Arrivée physique, disponibilité et retard</h2>
<p>Nouvel achat 049371 : 147 jours calendaires, puis 9 jours ouvrés de réception. Les onze engagements initiaux proviennent
d'un autre fournisseur, avec leurs propres dates G/I. Une promesse tardive reste affectée ; elle ne provoque pas automatiquement un deuxième achat.</p>''')
    rows = []
    for vintage in FOCUS:
        for floor in ("additive", "maximum"):
            i, c = get("049371", vintage, floor=floor)
            row = f'<tr><td>{vintage} · {"addition" if floor == "additive" else "maximum"}</td>'
            first = c["proposals"][0] if c["proposals"] else None
            for field in ("release_day", "physical_arrival_day", "available_day", "protected_requested_day"):
                row += daycell(first[field], f"/cases/{i}/proposals/0/{field}") if first else '<td>Aucune proposition</td>'
            row += cell(c["physical_late_qty"], f"/cases/{i}/physical_late_qty")
            row += cell(c["protected_late_qty"], f"/cases/{i}/protected_late_qty")
            rows.append(row + '</tr>')
    parts.append(table(["Version / protection", "Première commande", "Arrivée physique", "Disponible", "Échéance protégée visée", "Besoin servi tard (kg)", "Protection couverte tard (kg)"], rows))
    parts.append('''<p>Les retards sont calculés dans ce plan conditionnel, avec sa convention de répartition journalière.
Ils ne sont pas des ruptures industrielles observées. Le retard de protection n'est pas nécessairement un retard de consommation physique.</p>
<h3>H comme cible : comparaison à semaine exacte</h3>
<p>Les quantités comparées à H sont les engagements initiaux retenus + les propositions nouvelles. Les libérations J sont exclues des entrées physiques.
Le rapprochement des arrivées connues du carnet initial ne constitue pas une prédiction réussie de nouveaux achats.</p>''')
    rows = []
    for vintage in FOCUS:
        i, c = get("049371", vintage)
        score = c["H_reference_comparison"]["contiguous_prefix_conditional_score"]
        pre = f"/cases/{i}/H_reference_comparison/contiguous_prefix_conditional_score"
        row = f'<tr><td>{vintage}</td>'
        for key, places in [("weeks", 0), ("reference_H", 0), ("predicted_physical", 0), ("physical_exact_matched_qty", 0), ("physical_unmatched_reference_H", 0), ("physical_unmatched_prediction", 0), ("available_exact_matched_qty", 0)]:
            row += cell(score[key], pre + '/' + key, places)
        rows.append(row + '</tr>')
    parts.append(table(["Version", "Semaines contiguës", "H source (kg)", "Arrivées prévues", "Même semaine · arrivé", "H non rapproché", "Arrivées non rapprochées", "Même semaine · disponible"], rows))
    parts.append('''<p>Volume rapproché = somme de <code>min(H source, H prévu)</code> par semaine, sans double emploi.
Les propositions restent conditionnelles aux besoins documentés sur tout l'horizon, même lorsque le score porte sur le préfixe renseigné.
La tolérance ±1 semaine n'est pas calculée dans cette phase.</p>''')
    for vintage in (FOCUS[0], FOCUS[1]):
        i, c = get("049371", vintage)
        weekly = c["H_reference_comparison"]["weekly"]
        rows = []
        for n, (marker, target, physical, available, prefix) in enumerate(weekly):
            if not (target or physical or available):
                continue
            pre = f"/cases/{i}/H_reference_comparison/weekly/{n}"
            rows.append(f'<tr><td>{marker}</td>' + cell(target, pre + '/1') + cell(physical, pre + '/2') + cell(available, pre + '/3') + f'<td>{"Oui" if prefix else "Non"}</td></tr>')
        parts.append(f'<details><summary>Flux prévus détaillés · version {vintage}</summary>' + table(["Repère dimanche", "H source", "Arrivé prévu", "Disponible prévu", "Préfixe contigu"], rows) + '</details>')
    parts.append('</section><section id="controls"><h2>Trois contrôles, mêmes contrats de besoin</h2><p>Courant entièrement restant ; colonne maximum = variante du même plan. Les unités sont séparées et les lignes ne sont pas additionnables.</p>')
    rows = []
    for article in ("338929", "333362", "773474"):
        for vintage in FOCUS:
            i, c = get(article, vintage)
            m, maximum = get(article, vintage, floor="maximum")
            j, inp = inputs[c["source_snapshot_id"]]
            rows.append(f'<tr><td>{article} · {SITES[c["division"]]} · {vintage}</td><td>{c["unit"]}</td>'
                        + cell(c["quantity_bounds"]["unprotected_net_lower_bound"], f"/cases/{i}/quantity_bounds/unprotected_net_lower_bound")
                        + cell(c["proposed_qty"], f"/cases/{i}/proposed_qty") + cell(maximum["proposed_qty"], f"/cases/{m}/proposed_qty")
                        + cell(c["physical_late_qty"], f"/cases/{i}/physical_late_qty")
                        + cell(inp["coverage"]["present_week_count"], f"/inputs/{j}/coverage/present_week_count", 0) + '</tr>')
    parts.append(table(["Article / site / version", "Unité", "Déficit net documenté", "Propositions addition", "Propositions maximum", "Besoin servi tard", "Semaines / 52"], rows))
    parts.append('''<p>338929 et 773474 ont un fixe nul : les deux opérateurs doivent coïncider. 773474 est un transfert local avec origine supposée non contraignante,
sans imposer son lot de fabrication de 3 200 kg. Ce calcul ne démontre pas que Gaillac peut physiquement expédier les quantités proposées.</p></section>
<section id="rules"><h2>Paramètres, origines et hypothèses</h2>''')
    rows = []
    for n, entry in enumerate(bench["catalogue"]):
        p = entry["parameters"]
        pre = f"/catalogue/{n}/parameters"
        rows.append(f'<tr><td>{entry["article"]} · {SITES[entry["division"]]}</td><td>{esc(p["supplier"])}</td>'
                    + cell(p["physical_lead_days"], pre + '/physical_lead_days', 0)
                    + cell(p["receipt_workdays"], pre + '/receipt_workdays', 0)
                    + cell(p["safety_workdays"], pre + '/safety_workdays', 0)
                    + cell(p["fixed_floor_qty"], pre + '/fixed_floor_qty', 0)
                    + f'<td>{entry["unit"]}</td><td>{"1 600 kg contraignant par convention" if p["standard_binding"] else "Standard non contraignant"}</td><td>{"Dimanche" if p["review_weekday"] == 6 else "Quotidienne"}</td></tr>')
    parts.append(table(["Couple", "Fournisseur / origine", "Transport / fournisseur (j)", "Réception (ouvrés)", "Sécurité (ouvrés)", "Fixe", "Unité", "Lot", "Revue"], rows))
    parts.append('''<p>Les sources ne donnent pas de date de validité pour ces offres et politiques. Pour 049371, le fournisseur et le lot du carnet initial diffèrent de la fiche achat.
L'interprétation du standard comme multiple obligatoire reste conventionnelle. Les jours ouvrés sont lundi–vendredi, sans jours fériés ajoutés.</p>
<div class="two"><div><h3>Entrées de décision</h3><ul><li>Une version MRP connue : besoins I uniquement.</li><li>J disponible et J libéré plus tard, crédités une fois.</li>
<li>Encours initiaux dont G est strictement futur, à leur date I d'origine.</li><li>Politique, lot et calendrier déclarés.</li></ul></div>
<div><h3>Données de comparaison</h3><ul><li>H courant et futur : jamais utilisé pour couvrir les besoins.</li><li>Photos postérieures : jamais état d'entrée.</li>
<li>Observations Scan3 : jamais ajoutées à I.</li><li>Versions futures : exclues de la décision.</li></ul></div></div>
<p>Un G passé ou égal à la décision est supposé déjà représenté dans J ; son exécution réelle n'est pas prouvée. Les annulations, reports et nouvelles commandes ERP intervenus depuis janvier sont absents.
Les périodes MRP utilisent une convention dimanche–samedi ; les mouvements historiques suivent leur propre contrat de semaines.</p></section>
<section id="coverage"><h2>Les 52 versions par couple</h2>
<p>Les colonnes « restant » et « exclu » sont deux états possibles de I courant. Les propositions couvrent chacune un horizon glissant, pas le mois ou l'année du libellé.</p>''')
    for entry in bench["catalogue"]:
        article = entry["article"]
        rows = []
        for vintage in sorted(c["vintage"] for c in cases if c["article"] == article and c["current_week_assumption"] == "entirely_remaining" and c["fixed_floor_mode"] == "additive"):
            i, c = get(article, vintage)
            m, maximum = get(article, vintage, floor="maximum")
            x, excluded = get(article, vintage, current="excluded")
            y, excluded_maximum = get(article, vintage, current="excluded", floor="maximum")
            j, inp = inputs[c["source_snapshot_id"]]
            row = f'<tr><td>{vintage}</td>'
            for key in ("present_week_count", "contiguous_prefix_week_count"):
                row += cell(inp["coverage"][key], f"/inputs/{j}/coverage/{key}", 0)
            for idx, value in ((i, c), (m, maximum), (x, excluded), (y, excluded_maximum)):
                row += cell(value["proposed_qty"], f"/cases/{idx}/proposed_qty", 0 if entry["unit"] == "UN" else 3)
            rows.append(row + '</tr>')
        parts.append(f'<details><summary>{article} · {SITES[entry["division"]]} · {entry["unit"]} · 52 versions</summary>'
                     + table(["Version", "Semaines présentes / 52", "Préfixe contigu", "Restant · addition", "Restant · maximum", "Exclu · addition", "Exclu · maximum"], rows) + '</details>')
    parts.append('''</section><section id="proof"><h2>Décision, contrôles et prochaine information utile</h2>
<p><strong>Banc local retenu comme outil de diagnostic ; aucune nouvelle politique de chaîne adoptée.</strong>
Le besoin d'approvisionnement apparaît quand on utilise les besoins industriels. L'état du carnet et le périmètre des consommations restent à identifier pour une simulation autonome.</p>
<p>Une correction numérique conserve désormais exactement les quantités lors du calcul de protection : un arrondi intermédiaire pouvait déclencher une unité de trop.
Elle ne change ni les paramètres industriels ni les politiques comparées. Le premier calcul et le test échoué sont conservés dans les preuves.</p>
<p>Contrôles documentés sur les fichiers stabilisés : tests en mémoire sans altération de fichiers, oracle indépendant, rapprochement statique HTML et doctor.
Les résultats effectivement exécutés et leurs éventuels échecs figurent dans les preuves liées ci-dessous. Le navigateur et le score ±1 semaine ne sont pas exécutés.</p>''')
    questions = [
        ("049371 : carnet et conditions d'achat", "Commandes engagées aux 5 janvier, 30 mars, 29 juin et 28 septembre ; reliquats, fournisseur, G/I et révisions. Date de validité des 147 jours et du standard 1 600 kg."),
        ("Sens du I courant", "Besoin entièrement restant, retard ou agrégat incluant une consommation déjà exécutée ? Préciser la frontière horaire du snapshot."),
        ("Scan3 : produit, vrac et étape", "Quelques prélèvements 049371/773474/042342 avec OF, produit fabriqué et format conditionné ; stock intermédiaire aux bornes."),
        ("Anomalies de mouvement", "Définition des 6 400 kg H hebdomadaires de Gaillac ; mouvements de Muret entre les photos du 22 et du 29 décembre."),
    ]
    parts.append(table(["Information ciblée", "Ce qu'elle permet de lever"], [f'<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>' for a, b in questions]))
    parts.append('<ul>')
    for path, label in [
        ("etudecas/docs/REFONDATION_MRP.md", "Protocole figé avant calcul et bilan local"),
        ("etudecas/docs/REGLES_MRP.md", "Registre des règles et référence C8R"),
        ("etudecas/artifacts/testing/mrp_local_20261007/manifest.json", "Manifeste consolidé des exécutions et limites"),
        ("etudecas/artifacts/testing/mrp_local_20261007/source_contract.json", "Contrat source, cellules et ambiguïtés"),
        ("etudecas/artifacts/testing/mrp_local_20261007/oracle_design.json", "Oracle indépendant établi avant calcul"),
        ("etudecas/artifacts/testing/mrp_local_20261007/independent_review.json", "Contre-vérification du banc"),
        ("etudecas/artifacts/testing/mrp_local_20261007/numeric_comparison.json", "Effet de la correction numérique et référence précédente"),
        ("etudecas/artifacts/testing/mrp_local_20261007/html_review.json", "Vérification statique de cette vue"),
        ("etudecas/resultats/scan3_scope_20261007/comparaison.html", "Audit Scan3 précédent conservé"),
        ("etudecas/resultats/mrp_packaging_solutions_20261006/comparaison_corrigee.html", "Comparaison historique B3/C8R conservée"),
    ]:
        parts.append('<li>' + link(path, label) + '</li>')
    parts.append('''</ul><p>Le fichier complet des plans reste local dans le dossier de preuves ; il n’est pas embarqué dans cette page.</p></section>
<footer>Planification locale conditionnelle, sans nouvelle simulation physique ni certification de calibration industrielle.</footer></main></body></html>''')
    return ''.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, default=FOLDER / "bench.json")
    parser.add_argument("--contract", type=Path, default=FOLDER / "source_contract.json")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "etudecas/resultats"):
        parser.error("Output must stay below etudecas/resultats")
    before = {p: sha(p) for p in (args.bench, args.contract, Path(__file__))}
    bench = json.loads(args.bench.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    content = build_view(bench, contract, output)
    if any(sha(p) != digest for p, digest in before.items()):
        raise RuntimeError("Input changed during generation")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(json.dumps({"status": "generated_not_browser_verified", "html": str(output),
                      "sha256": sha(output), "bytes": output.stat().st_size,
                      "inputs": {str(p): value for p, value in before.items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
