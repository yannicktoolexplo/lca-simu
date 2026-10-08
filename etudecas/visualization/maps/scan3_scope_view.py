"""Render a small, offline Scan3 source audit; never invokes a browser or engine.

Inputs are the source audit and an independently calculated review. Run from the
repository root: python -B -m etudecas.visualization.maps.scan3_scope_view
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "etudecas/artifacts/testing/scan3_scope_20261007"
DEFAULT_HTML = ROOT / "etudecas/resultats/scan3_scope_20261007/comparaison.html"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def number(value, precision=3):
    if value is None:
        return "Non renseigné"
    return f"{float(value):,.{precision}f}".replace(",", "\u202f").replace(".", ",")


def e(value):
    return html.escape(str(value), quote=True)


def cell(value, key, precision=3):
    """Numeric values are both visible and individually identifiable for review."""
    attrs = f' data-key="{e(key)}"'
    if value is not None:
        attrs += f' data-value="{float(value):.12g}"'
    return f'<td{attrs}>{number(value, precision)}</td>'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join(
        f'<th scope="col">{e(h)}</th>' for h in headers
    ) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def render(audit, oracle, output):
    def link(path, label):
        relative = Path(os.path.relpath(ROOT / path, output.parent)).as_posix()
        return f'<a href="{e(relative)}">{e(label)}</a>'

    parts = ['''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scan3 — matières, conditionnement et bilans sources</title>
<style>
:root{color-scheme:light;--ink:#183144;--muted:#516778;--accent:#146b70;--line:#d7e2e5}
*{box-sizing:border-box}body{margin:0;background:#f4f7f7;color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:1320px;margin:auto;padding:32px 24px 64px}h1{font-size:2.3rem;line-height:1.15;margin:.4em 0}
h2{margin:0 0 16px;font-size:1.55rem}h3{font-size:1.15rem}p{max-width:100ch}
header{padding:12px 0 24px}.eyebrow{font-size:.85rem;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
nav{display:flex;gap:8px 20px;flex-wrap:wrap;margin:24px 0}a{color:#0b626e;text-underline-offset:3px}
section{background:white;padding:24px;margin:24px 0;border:1px solid var(--line);border-radius:12px;scroll-margin-top:16px}
.notice{border-left:5px solid #b96a28;background:#fff5e9;padding:12px 18px;margin:20px 0}.muted,small{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.metric{background:#eaf2f2;padding:16px;border-radius:8px}
.metric strong{display:block;font-size:1.7rem;color:var(--accent)}.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:12px 0}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}
th{background:#ecf2f3;font-size:.8rem}th:first-child,td:first-child{text-align:left}td[data-value]{font-variant-numeric:tabular-nums;white-space:nowrap}
tr.warn{background:#fff3e7}tr.pack{background:#eef7f4}code{font-size:.9em;overflow-wrap:anywhere}
.barrow{display:grid;grid-template-columns:180px minmax(80px,1fr) 110px;gap:12px;align-items:center;margin:10px 0;font-size:.9rem}
.track{height:20px;background:#e9eeee;border-radius:3px}.bar{height:100%;background:#377e8a;border-radius:3px}.packbar{background:#9b603c}
details{margin:16px 0}summary{cursor:pointer;font-weight:600}footer{font-size:.9rem;color:var(--muted)}
@media(max-width:650px){main{padding:18px 12px}section{padding:16px}h1{font-size:1.85rem}.barrow{grid-template-columns:100px 1fr 88px;font-size:.75rem}}
@media print{body{background:white}main{padding:0}section{break-inside:avoid}nav{display:none}details{display:block}}
</style></head><body><main><header><div class="eyebrow">Reprise industrielle · 7 octobre 2026</div>
<h1>Scan3 : deux échelles à rapprocher</h1>
<p>Les matières et le conditionnement ne décrivent pas encore un périmètre de fabrication commun démontré.
Les données sont conservées telles quelles. <strong>C8R reste la référence de comparaison ; le moteur n'a pas été modifié.</strong></p>
<nav><a href="#equivalents">BOM et conditionnement</a><a href="#case">049371 et C8R</a><a href="#balances">Bilans article/site</a>
<a href="#hypotheses">Hypothèses</a><a href="#proof">Preuves et règles</a></nav></header>''']
    summary = audit["summary"]
    parts.append(f'''<div class="grid"><div class="metric"><strong>{summary['annual_balances_closed_at_1e_6']} / {summary['annual_balances_with_both_photos']}</strong>
bilans cumulés calculables fermés<br><small>Les écarts hebdomadaires restent visibles.</small></div>
<div class="metric"><strong>24,38 M / 5,02 M</strong>Avène : matières / étuis<br><small>Équivalents théoriques selon la BOM.</small></div>
<div class="metric"><strong>5,80 M / 1,26 M</strong>Gien : 773474 / étuis<br><small>Équivalents théoriques selon la BOM.</small></div></div>
<div class="notice"><strong>Période :</strong> semaines représentées du 30 décembre 2024 au 28 décembre 2025.
La première semaine chevauche 2024 ; la photo initiale est datée du 1er janvier.
Le marqueur du 28 décembre, couvrant le 29 décembre au 4 janvier 2026, est exclu.
Une semaine absente reste inconnue. Les quantités hebdomadaires n'ont pas de date journalière observée.</div>
<section id="equivalents"><h2>BOM, matières et conditionnement</h2>
<p><code>Équivalent PF = −J signé / coefficient BOM normalisé par PF</code>.
G est converti une seule fois en kg. Ces équivalents ne sont pas des productions directement mesurées.
Les barres utilisent une échelle propre à chaque usine ; les tableaux donnent la couverture et les cellules.</p>''')
    for product in audit["bom_products"][:2]:
        pf = product["product"]
        site = "Avène" if pf == "268091" else "Gien"
        parts.append(f'<h3>{site} · PF {pf}</h3>')
        selected = {"049371", "338928", "338929"} if pf == "268091" else {"773474", "042342", "333362"}
        ceiling = max(c["J_consumption_equivalent"] for c in product["components"])
        for c in product["components"]:
            if c["article"] in selected:
                v = c["J_consumption_equivalent"]
                cls = " packbar" if c["type"] == "Pack" else ""
                parts.append(f'<div class="barrow"><span>{c["article"]} · {e(c["type"])}</span><div class="track"><div class="bar{cls}" style="width:{v/ceiling*100:.3f}%"></div></div><span>{number(v/1e6,3)} M PF éq.</span></div>')
        rows = []
        for c in product["components"]:
            prefix = f'bom.{pf}.{c["article"]}'
            rows.append(f'<tr class="{"pack" if c["type"] == "Pack" else ""}"><td>{c["article"]} · {e(c["type"])}</td>'
                        + cell(-c["J_signed"], prefix + ".J") + f'<td>{e(c["unit"])}</td>'
                        + cell(c["coefficient_per_output_unit"], prefix + ".coefficient", 7)
                        + cell(c["J_consumption_equivalent"], prefix + ".equivalent", 0)
                        + f'<td>{c["present_weeks"]} / 52</td><td><small>{e(c["source"].split("/source/")[-1])}</small></td></tr>')
        parts.append(table(["Composant / étape source", "−J source", "Unité", "Coefficient / PF", "PF équivalents", "Semaines présentes", "BOM source"], rows))
    parts.append('''<p>À Avène, les douze matières concordent aussi sur les semaines communes : dispersion maximale
0,278 % sur les 41 semaines actives, parmi 46 semaines toutes renseignées. Tubes et étuis ont un ratio cumulé de 1,00417.
À Gien, 038005 atteint 6,080 millions d'équivalents, soit environ 4,8 % de plus que 773474 : toutes les matières n'ont pas une concordance aussi étroite.</p>
<p>Les mêmes quantités BOM figurent dans <code>Data_poc.xlsx</code>. Une divergence de référence subsiste :
693710 dans ce fichier, 007923 dans la BOM détaillée d'Avène, au même coefficient. Aucune substitution nouvelle n'est effectuée.</p></section>''')
    case = oracle["case_049371"]
    sim = case["c8r_through_source_week_end"]
    real = case["movement_totals_kg"]
    rows = []
    values = [("Stock initial", case["initial_stock"]["quantity"], sim["initial_stock_kg"]),
              ("Réceptions", real["receipts"], sim["arrivals_kg"]),
              ("J source / consommation BOM nouvelles fabrications", -real["J_scan3"], sim["new_production_consumption_kg"]),
              ("−I source / autres usages simulés", -real["I_sorties"], sim["external_consumption_kg"]),
              ("Divers signés source / représentés dans le bilan C8R", real["divers"], 0),
              ("Stock final : photo 29 décembre / clôture 28 décembre", case["final_stock"]["quantity"], sim["final_stock_kg"])]
    for i, (label, observed, modeled) in enumerate(values):
        rows.append(f'<tr><td>{e(label)}</td>' + cell(observed, f"case.{i}.source") + cell(modeled, f"case.{i}.C8R") + '</tr>')
    parts.append('<section id="case"><h2>049371 · Avène : le stock se ferme, le périmètre ne se ferme pas</h2>'
                 + table(["Quantité (kg)", "Sources hebdomadaires", "C8R jusqu'au 28 décembre"], rows))
    parts.append(f'''<p><code>4 138,930 + 47 975 − 36 629,748 − 691,050 − 17,522 = 14 775,610 kg</code>.</p>
<p>C8R reçoit seulement les onze engagements initiaux de 1 800 kg, sans nouvelle commande.
Les 805,500 kg d'autres usages simulés incluent environ 114,450 kg estimés sur les jours sans mouvement renseigné.
J source et consommation BOM sont comparés pour diagnostiquer leur différence, sans supposer leurs périmètres identiques.</p>
<p>Les matières des OF initiaux sont supposées déjà incorporées : {number(case['c8r_opening_material_assumed_wip_kg'])} kg de 049371.
Même ajoutées aux nouvelles fabrications, elles ne représentent que {number(case['c8r_new_plus_assumed_wip_through_dec28_kg'])} kg.
Il reste {number(case['observed_J_minus_c8r_new_and_assumed_wip_through_dec28_kg'])} kg d'écart avec J ; ce n'est pas un besoin d'achat à injecter.</p>
<p>Au <strong>31 décembre</strong>, C8R a consommé {number(case['c8r_year']['new_production_consumption_kg'])} kg pour ses nouvelles fabrications
et conserve {number(case['c8r_year']['final_stock_kg'])} kg. Ces valeurs n'ont pas la même borne que le tableau.</p>''')
    trace = case["trace_2025_03_30"][0]
    trace_fields = [("Industriel sur les fenêtres couvertes", "industrial_source_requirement_qty"),
                    ("BOM sur ces fenêtres", "industrial_own_requirement_qty"),
                    ("Autres usages prévus sur ces fenêtres", "industrial_reconstructed_external_qty"),
                    ("Retenu sur ces fenêtres", "industrial_planning_requirement_qty"),
                    ("Tous besoins de la projection", "dated_requirement_qty"),
                    ("Disponible de décision", "dated_stock_qty"),
                    ("Engagements attendus", "dated_firm_transit_qty")]
    parts.append('<h3>Décision du 30 mars : pourquoi aucun achat supplémentaire</h3>' + table(
        ["Périmètre", "kg"], [f'<tr><td>{label}</td>' + cell(float(trace[key]), f"trace.{key}") + '</tr>' for label, key in trace_fields]))
    parts.append('''<p>La règle <code>separate_own_and_other_v1</code> conserve ici le MRP industriel comme comparaison.
Le recours prioritaire aux besoins industriels concerne les deux étuis, pas 049371. Acheter davantage sans comprendre la consommation pourrait accroître le stock.</p></section>''')
    parts.append('''<section id="balances"><h2>Bilans par article et site</h2>
<p><code>Résidu = stock initial + G (Divers) + H (Entrées) + I + J − stock final</code>.
Les flux gardent leurs signes. Les sommes portent sur les lignes disponibles ; leur fermeture ne prouve pas l'exhaustivité des flux bruts.
Photos du 1er janvier et du 29 décembre. Une fermeture cumulée peut masquer un décalage entre semaines.</p>''')
    rows, anomalies = [], []
    for b in audit["article_site_balances"]:
        p = f'balance.{b["article"]}.{b["site"]}'
        a = b["annual_boundary_balance"]
        residual = a["residual_computed_minus_snapshot"]
        cls = "warn" if residual is None or abs(residual) > 1e-6 else ""
        row = f'<tr class="{cls}"><td>{b["article"]} · {e(b["site_name"])}</td><td>{e(b["unit"])}</td>'
        row += cell(a["opening"]["quantity"] if a["opening"] else None, p + ".opening")
        for col in "GHIJ":
            row += cell(a["signed_flows"][col], p + "." + col)
        row += cell(a["closing"]["quantity"] if a["closing"] else None, p + ".closing") + cell(residual, p + ".residual")
        row += f'<td>{a["present_rows"]}/52</td><td>{len(b["weekly_check"]["anomalies"])}</td></tr>'
        rows.append(row)
        for w in b["weekly_check"]["anomalies"]:
            anomalies.append(f'<tr><td>{b["article"]} · {e(b["site_name"])}</td><td>{w["start"]} → {w["end"]}</td>'
                             + cell(w["residual"], p + ".weekly." + w["end"]) + f'<td>{e(b["unit"])}</td><td><small>{e(w["movement_source"].split("/source/")[-1])}</small></td></tr>')
    parts.append(table(["Article · site", "Unité", "Initial", "G", "H", "I", "J", "Final", "Résidu", "Semaines", "Écarts hebdo"], rows))
    parts.append('<details><summary>Écarts hebdomadaires non nuls</summary>' + table(["Article · site", "Photos", "Résidu calculé − photo", "Unité", "Mouvement source"], anomalies) + '</details>')
    parts.append('''<p><strong>049371 :</strong> deux résidus de +222 puis −222 kg se compensent aux photos des 23 et 30 juin.
<strong>268967/Muret :</strong> +13 608 UN non expliquées entre les photos des 22 et 29 décembre.
<strong>773474/Gaillac :</strong> +92 800 kg, répartis en 29 excédents hebdomadaires de 3 200 kg.
H/2 fermerait ce dernier bilan, mais aucune correction du fichier n'est appliquée et un doublon n'est pas démontré.</p>
<p>Pour 773474, les sorties I de Gaillac égalent les entrées H de Gien dans chacune des 18 semaines concernées :
67 200 kg au total. Cette concordance soutient le transfert, sans fournir l'identité des expéditions ni leur délai journalier.</p></section>''')
    delay = oracle["delay_only_hypothesis_requirements"]
    parts.append(f'''<section id="hypotheses"><h2>Ce qui reste à départager</h2>
<p>Une inversion générale I/J est contredite par les étuis : I ne donnerait que 2 400 UN à Avène et zéro à Gien.
I contient aussi des entrées nettes positives pour certaines matières ; son libellé n'est pas « autres produits ».</p>
<div class="notice"><strong>Hypothèse d'un décalage entre étapes uniquement :</strong> à périmètre exclusif, BOM exacte,
flux complets et sans pertes/autres sorties, il faudrait une variation de stock intermédiaire de
{number(delay['avene_extra_pf_equivalent_via_049371'],0)} PF équivalents à Avène,
soit {number(delay['avene_extra_049371_kg'])} kg de 049371 incorporés, et environ
{number(delay['avene_extra_total_formulation_kg_from_all_12_matter_totals']/1000,2)} tonnes de formulation selon les douze matières.
À Gien : {number(delay['gien_extra_pf_equivalent_via_773474'],0)} PF équivalents, dont
{number(delay['gien_extra_773474_kg'])} kg de 773474. <strong>Ce sont des conséquences conditionnelles, pas des stocks mesurés.</strong></div>
<p>Les décalages simples de −26 à +26 semaines, comparés uniquement sur les lignes présentes des deux séries,
ne ramènent pas les ratios matières/étuis à 1 parmi les cas ayant au moins 20 semaines appariées.
Ce constat ne réfute pas un encours inconnu, un changement de format ou des sorties hors périmètre.</p>
<p>À Gien, la BOM porte 60,342 capsules et 9,654718 g de 773474 par PF, face au libellé 60 × 160 mg :
la base du conditionnement est arithmétiquement cohérente. Multiplier toute la BOM par environ 4,59 conduirait à environ 277 capsules par étui.
À Avène, les matières totalisent 20,4218 g/PF pour le libellé 40 mL ; sans densité ni exhaustivité de formulation confirmées,
ce rapprochement ne détermine pas un coefficient de correction.</p>''')
    parts.append(table(["Hypothèse", "Indice", "Information discriminante absente"], [
        '<tr><td>Formulation/vrac commun à plusieurs formats</td><td>Douze matières cohérentes ; emballages à une autre échelle</td><td>Code vrac, OF et PF destinataires des prélèvements J</td></tr>',
        '<tr><td>Base ou étape de nomenclature différente</td><td>Bases 1 000 UN répétées dans les classeurs ; Gien cohérent avec 60 capsules</td><td>Recette de vrac, conversion vers PF, rendement et unité de base attestés</td></tr>',
        '<tr><td>Stock intermédiaire et décalage fabrication/conditionnement</td><td>Variations nécessaires chiffrées ci-dessus</td><td>Stock de vrac/capsules non conditionnées à ouverture et clôture</td></tr>',
        '<tr><td>Périmètre d’extraction Scan3</td><td>I/J sans dictionnaire métier ni identité OF dans les mouvements</td><td>Filtre de l’extraction, retours/annulations et produit de chaque OF</td></tr>']))
    parts.append('''<p><strong>Question métier :</strong> à quel code de vrac ou produit fabriqué sont rattachés les prélèvements
de 049371 à Avène et de 773474/042342 à Gien ? Un numéro d'OF et son produit fabriqué permettraient de tester l'exclusivité des deux PF.</p>
<p><strong>Décision :</strong> correction documentaire retenue ; pas de modification de BOM, de consommation ou de règle d'achat.
Le partage de matière et la convention d'étape restent hypothétiques. A : identifier le planificateur local avec les besoins industriels connus.
B : expliquer la chaîne depuis la demande et les BOM. Un rejeu des observations ne valide pas une simulation autonome.</p></section>''')
    mrp = audit["mrp_stock_identity"]
    parts.append(f'''<section id="proof"><h2>Règles, provenance et contrôles</h2>
<p>MRP : {number(mrp['rows'],0)} lignes / {number(mrp['groups'],0)} groupes relus ;
<code>K = K précédent + H + J − I</code>, résidu maximal {e(mrp['max_absolute_error_native_unit'])} dans l'unité native.
{mrp['nonzero_J_after_first_row']} contributions J apparaissent après la première ligne ; elles ne sont pas automatiquement des livraisons.
{number(mrp['gaps_longer_than_7_days'],0)} sauts entre semaines renseignées ne sont pas des zéros observés.</p>
<p>Oracle indépendant : {oracle['assertion_count']} assertions, {oracle['assertion_pass_count']} satisfaites et
{oracle['assertion_count']-oracle['assertion_pass_count']} non-conformités signalées. La réconciliation globale reste non validée.
Aucun pytest, nouvelle simulation ou navigateur exécuté dans cette passe. Contrôle HTML statique uniquement ; rendu et interactions non certifiés.</p><ul>''')
    for path, label in [
        ("etudecas/docs/REGLES_MRP.md", "Registre consolidé, formules et matrice C8R"),
        ("etudecas/artifacts/testing/audit_perimetre_scan3_20261007.md", "Diagnostic consolidé et décisions"),
        ("etudecas/resultats/mrp_packaging_solutions_20261006/comparaison_corrigee.html", "Comparaison historique B3/C8R conservée"),
        ("etudecas/resultats/mrp_production_programme_20261006/comparaison_PGA.html", "Comparaison PGA — essai non retenu"),
        ("etudecas/artifacts/testing/scan3_scope_20261007/source_audit.json", "Audit des sources et cellules"),
        ("etudecas/artifacts/testing/scan3_scope_20261007/independent_review.json", "Contre-calcul indépendant et anomalies"),
        ("etudecas/artifacts/testing/scan3_scope_20261007/scenario_audit.json", "Configuration C8R effectivement exécutée"),
    ]:
        parts.append('<li>' + link(path, label) + '</li>')
    parts.append('</ul><details><summary>Classeurs lus par l’audit</summary><ul>')
    for source in audit["sources"]:
        parts.append('<li>' + link(source["path"], Path(source["path"]).name) + '</li>')
    parts.append('</ul></details></section><footer>Analyse rétrospective, sans calibration artificielle des stocks. Les références historiques et les deux suivis de lots restent conservés.</footer></main></body></html>')
    return ''.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=EVIDENCE / "source_audit.json")
    parser.add_argument("--oracle", type=Path, default=EVIDENCE / "independent_review.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "etudecas/resultats"):
        parser.error("Output must be below etudecas/resultats")
    inputs = {args.audit: digest(args.audit), args.oracle: digest(args.oracle)}
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    content = render(audit, oracle, output)
    if any(digest(p) != value for p, value in inputs.items()):
        raise RuntimeError("Input changed during rendering")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(json.dumps({"status": "generated_not_browser_verified", "html": str(output),
                      "sha256": digest(output), "bytes": output.stat().st_size,
                      "inputs": {str(p): value for p, value in inputs.items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
