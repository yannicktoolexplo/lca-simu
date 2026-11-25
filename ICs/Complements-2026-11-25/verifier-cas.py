"""Recalcule les deux cas publics. Python 3, bibliothèque standard uniquement."""
from pathlib import Path
from math import comb, isclose
from fractions import Fraction
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def lire(nom):
    return list(csv.DictReader((ROOT / 'Cas' / nom).open(encoding='utf-8-sig')))


def enveloppe(regles):
    """Intersections exactes et règle minimale pour chaque intervalle de r >= 0."""
    points = {Fraction(0)}
    for a in regles:
        for b in regles:
            if a['fn'] != b['fn']:
                x = Fraction(b['fp'] - a['fp'], a['fn'] - b['fn'])
                if x >= 0:
                    points.add(x)
    points = sorted(points)
    result = []
    for i, lo in enumerate(points):
        hi = points[i + 1] if i + 1 < len(points) else None
        x = (lo + hi) / 2 if hi is not None else lo + 1
        cout = {a['regle']: a['fp'] + x * a['fn'] for a in regles}
        gagnants = sorted(k for k, v in cout.items() if v == min(cout.values()))
        if result and result[-1]['regles'] == gagnants:
            result[-1]['borne_haute'] = str(hi) if hi is not None else None
        else:
            result.append({'borne_basse': str(lo), 'borne_haute': str(hi) if hi is not None else None,
                           'regles': gagnants})
    return result


def main():
    revues = []
    for r in lire('revues-fournisseurs.csv'):
        forte = r['definition_du_cas'] == 'baisse_au_moins_20_points'
        kmono, kautre = (3 if forte else 5), 1
        regle = r['regle']
        if regle == 'tirage_uniforme':
            n = comb(27, 5)
            sans = comb(27 - kmono - kautre, 5)
            esp = 5 * (kmono + kautre) / 27
        elif regle == 'tirage_par_groupe':
            m, a = int(r['places_mono_source']), int(r['places_autres'])
            n = comb(13, m) * comb(14, a)
            sans = comb(13 - kmono, m) * comb(14 - kautre, a)
            esp = m * kmono / 13 + a * kautre / 14
        else:
            # Le CSV donne une seule liste fixe sans détection. Sans dossiers nominatifs,
            # sa sélection n'est pas reproductible : seule la cohérence est vérifiée.
            n, sans, esp = 1, 1, 0
        assert n == int(r['listes_possibles'])
        assert sans == int(r['listes_sans_detection'])
        assert n - sans == int(r['listes_avec_detection'])
        assert isclose(esp, float(r['detections_moyennes']), abs_tol=1e-8)
        revues.append(dict(r, probabilite_sans_detection=sans/n, probabilite_detection=1-sans/n,
                           detections_moyennes_recalculees=esp,
                           statut='recalcul combinatoire' if regle.startswith('tirage') else 'cohérence seulement'))

    fret, enveloppes = [], {}
    for r in lire('alertes-fret.csv'):
        tp, fp, fn, tn, n = [int(r[k]) for k in ['alertes_justes', 'fausses_alertes', 'mois_manques',
                                               'mois_calmes_sans_alerte', 'nombre_mois_scenarios']]
        assert tp + fp + fn + tn == n
        fret.append({'perimetre': r['perimetre'], 'regle': r['regle'], 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
                     'n': n, 'rappel': tp/(tp+fn), 'precision': tp/(tp+fp) if tp+fp else None,
                     'taux_fausses_alertes_sur_mois_calmes': fp/(fp+tn),
                     'taux_ouverture_revue': (tp+fp)/n, 'prevalence': (tp+fn)/n})
    for regle in {r['regle'] for r in fret}:
        x = [r for r in fret if r['regle'] == regle]
        total = next(r for r in x if r['perimetre'] == 'tous_les_mois')
        for k in ['tp', 'fp', 'fn', 'tn', 'n']:
            assert total[k] == sum(r[k] for r in x if r['perimetre'] != 'tous_les_mois')
    for per in dict.fromkeys(r['perimetre'] for r in fret):
        x = [r for r in fret if r['perimetre'] == per]
        assert len({r['tp'] + r['fn'] for r in x}) == 1
        assert len({r['fp'] + r['tn'] for r in x}) == 1
        enveloppes[per] = {'cinq_regles_publiees': enveloppe(x)}
        toujours = {'regle': 'toujours_alerter_reference_derivee', 'tp': x[0]['tp'] + x[0]['fn'],
                    'fp': x[0]['fp'] + x[0]['tn'], 'fn': 0, 'tn': 0}
        enveloppes[per]['avec_toujours_alerter'] = enveloppe(x + [toujours])
    hashes = {f: hashlib.sha256((ROOT/'Cas'/f).read_bytes()).hexdigest()
              for f in ['revues-fournisseurs.csv', 'alertes-fret.csv']}
    resultat = {'date': '2026-11-25', 'origine': 'calcul complémentaire sur deux CSV publics simulés',
                'formule_cout': 'fausses_alertes + ratio_cout_manque_sur_fausse_alerte * mois_manques',
                'hypothese_cout_revue_justifiee': 0, 'hashes_sources_sha256': hashes,
                'revues': revues, 'fret': fret, 'enveloppes': enveloppes,
                'seuil_95_vs_persistance': str(Fraction(476, 115))}
    (OUT/'verification-cas.json').write_text(json.dumps(resultat, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('18 lignes revues vérifiées, dont 14 recalculées et 4 contrôlées en cohérence ; 15 lignes fret rapprochées.')
    print(json.dumps(enveloppes['tous_les_mois'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
