# Point de reprise MRP — 1er octobre 2026

Le scénario retenu parmi les essais est **`total`** : protection du stock partagé
et rapprochement des besoins MRP industriels pour 001757 et 002612 à Avène,
selon les règles déjà appliquées à 055703. Les jours de sécurité sources restent
inchangés (20, 20 et 30 jours ouvrés). Aucune réception partielle n'est ajoutée.

`checkpoint.zip` conserve les trois graphes d'entrée réellement simulés
(`nominal`, `safety`, `total`), leurs commandes exactes dans `manifest.json`,
les paramètres de présentation et les synthèses de validation. Les fichiers
CSV et HTML volumineux restent locaux. Les sources Excel restent dans
`etudecas/data/source`. Le nominal de comparaison désigne ici la référence
de cette étude, pas un remplacement de tous les scénarios du projet.

Deux nouveaux calculs de 1 825 jours ont été exécutés et qualifiés. Les
28 tests en mémoire de l'étape précédente ont été réutilisés avec vérification
des empreintes du code ; ils n'ont pas été relancés pour ce conditionnement.
Le navigateur a rapproché 4 377 valeurs de stock et 64 cellules MRP, sans erreur
JavaScript. Les preuves originales sont sous
`etudecas/artifacts/testing/mrp_year_end_20261001/manifest.json` ; leurs
synthèses sont conservées dans l'archive. Elles ne certifient pas la calibration.

L'erreur moyenne absolue de stock au quatrième trimestre passe de 4 276 à
1 276 kg pour 001757, et de 68 019 à 34 203 kg pour 002612. Il reste notamment
47 076 kg d'écart sur la dernière photo de 002612. Sur 29 comparaisons annuelles,
11 s'améliorent, 12 restent identiques et 6 se dégradent légèrement.

## Recalcul depuis la racine du dépôt

Avec les dépendances Python du projet installées, la commande suivante extrait
les vraies entrées dans un dossier neuf, vérifie leurs empreintes et relance
les trois simulations. Elle ne remplace aucun résultat existant. Les trois
calculs prennent environ 45 minutes sur la machine de validation.

```powershell
@'
from pathlib import Path
import hashlib, json, subprocess, sys, uuid, zipfile
root = Path.cwd()
work = root / 'etudecas/artifacts/testing' / ('reprise_mrp_' + uuid.uuid4().hex)
work.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(root / 'etudecas/config/mrp_shared_stock_20261001/checkpoint.zip') as bundle:
    manifest = json.loads(bundle.read('manifest.json'))
    for name, info in manifest['members'].items():
        data = bundle.read(name)
        assert hashlib.sha256(data).hexdigest() == info['sha256'], name
        destination = (work / name).resolve()
        assert destination.is_relative_to(work.resolve()), name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(data)
for source, expected in manifest['source_workbooks'].items():
    assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == expected, source
for key, variant in manifest['variants'].items():
    args = list(variant['python_args'])
    for flag in ('--input', '--output-dir'):
        index = args.index(flag) + 1
        args[index] = str(work / args[index])
    subprocess.run([sys.executable, *args], cwd=root, check=True)
print(work)
'@ | python -B -
```

Pour reconstruire la comparaison HTML, remplacer le chemin `reprise_mrp_...`
ci-dessous par celui affiché. Les courbes sont recalculées depuis les nouveaux
CSV et les deux Excel sources ; les anciens CSV ne sont pas nécessaires.

```powershell
@'
from pathlib import Path
import json
from etudecas.visualization.maps.source_comparison import build_comparison_payload
from etudecas.visualization.maps.portable_diagnostic import comparison_document
work = Path('etudecas/artifacts/testing/reprise_mrp_...')
source = Path('etudecas/data/source')
payload = build_comparison_payload(
    source / 'Flow_Data_Inventory_and_Replenishment_rules.xlsx',
    source / 'Flow_Data_MRP_results.xlsx',
    {key: work / 'runs' / key for key in ('nominal', 'safety', 'total')})
metadata = json.loads((work / 'comparison_metadata.json').read_text(encoding='utf-8'))
for key, presentation in metadata.pop('runs').items():
    payload['runs'][key].update(presentation)
payload.update(metadata)
with (work / 'comparaison_mrp.html').open('x', encoding='utf-8') as stream:
    stream.write(comparison_document(payload))
print(work / 'comparaison_mrp.html')
'@ | python -B -
```

Cette recette portable reprend les arguments et entrées des exécutions validées ;
elle n'a pas fait l'objet d'une quatrième série de simulations après archivage.
La carte complète locale `carte_mrp_securite_partagee.html` conserve des panneaux
historiques, dont les deux suivis de lots. Leur reproduction intégrale nécessite
les recettes historiques du projet ; cette archive reconstruit la comparaison
MRP, pas les autres panneaux à partir de ces trois nouveaux calculs.

## Anomalie connue : saut initial de 001893 à Avène

Le saut n'est pas introduit par cette dernière extension : les stocks des jours
0 à 80 sont strictement identiques dans la référence et le scénario `total`.
Le 2 février, 71 760 kg sont reçus ; le 4 février, 23 920 kg supplémentaires
portent le stock physique à 95 680 kg, entièrement indisponible à ces dates.
Les libérations ont lieu les 6 et 10 mars. Les sources indiquent seulement
14 623,304 kg le 3 février et 13 041,120 kg le 10 février.

Le planificateur utilise **88 jours** : le maximum des délais fournisseurs
(56 jours) plus le traitement à réception (24 jours ouvrés, ici 32 calendaires).
L'achat est exécuté chez VD0910216A avec **28 jours** de livraison, soit **60 jours**
traitement compris à la première commande. Cette incohérence anticipe trop de
besoins. Le besoin net du 5 janvier, 70 620,559290 kg, est arrondi à trois fois
23 920 kg ; celui du 7 janvier, 1 782,611278 kg, à une nouvelle tranche de
23 920 kg. L'absence d'engagement initial à Avène amplifie le démarrage.

Diagnostic confirmé, **correction non appliquée dans ce point de départ**.
Les cinq engagements 001893 de `Extract_En_cours.xlsx`, lignes 9–13, concernent
la division 1820 : ils ne doivent pas être réaffectés automatiquement à 1810.
Aligner le délai de planification sur l'offre retenue sera à tester comme règle
commune, sans promettre que cela résoudra à lui seul tout l'écart initial.

Preuves locales dans `mrp_year_end_20261001/run_total_extension/data` :
`mrp_orders_daily.csv` lignes 110 et 125 ; `mrp_dated_plan_daily.csv` lignes
143 et 209 ; `production_stock_availability_daily.csv` lignes 2163, 2297,
4307 et 4575. Sources : inventaire `Stocks!E951` et `E1223`, MRP
`Feuille1!E118` et `H118:H122`, offres `268091.xlsx`, FIA lignes 5–7.
