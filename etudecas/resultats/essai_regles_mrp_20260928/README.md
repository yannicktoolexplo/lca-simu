# Essai séparé des règles MRP — 28 septembre 2026

Ouvrir [comparaison.html](comparaison.html), puis **Essai règles MRP 2025**.
Le panneau compare les observations, le nominal conservé et le nouvel essai.
Les autres vues de cette copie de carte gardent leurs résultats historiques.
Aucune carte existante, source Excel ou configuration nominale n'a été remplacée.

## Ce qui a réellement été essayé

Deux simulations de 1 825 jours, sans période de chauffe, avec origine au
1er janvier 2025. Les graphiques de comparaison portent uniquement sur la
première année. Durées mesurées : 56,84 s et 57,99 s, hors qualifications.

La copie du graphe charge les 27 politiques de sécurité du nouveau classeur.
Cinq diffèrent du nominal : sécurité de 268967 au dépôt 25→60 jours,
268091 au dépôt 20→0 jours, 426331 7→10 jours, ajout de 20 jours pour
773474 à Gaillac et de 900 000 kg pour 021081 à Gaillac.
Le minimum de fabrication de 268091 passe de 14 400 à 28 800 unités ;
multiple de 14 400 et maximum de 142 485 conservés.

**Limites d'application :** les 20 jours de 773474 sont lus mais ne pilotent
pas la cible du contrôleur de fabrication actuel. Le lot source de 693055 à
Gaillac n'est pas appliqué, faute de processus de fabrication représenté.
Les besoins statiques, planchers génériques, calendrier lundi-vendredi,
délais, commandes et stocks initiaux ainsi que le calcul du transit sont
conservés. Zéro jour de sécurité source ne signifie pas zéro cible finale.
L'essai ne prétend donc pas reproduire toutes les règles du MRP industriel.

## Résultats sur 2025

Stocks moyens aux 52 relevés hebdomadaires, comparés au stock simulé sur site
en fin de journée précédente. Aucun mélange entre unités ou sites.

| Article / site | Unité | Observé | Nominal | Nouvelles valeurs sources |
|---|---|---:|---:|---:|
| 002612 / Avène | kg | 105 740 | 192 920 | 193 238 |
| 007923 / Avène | kg | 45 628 | 71 339 | 71 848 |
| 338929 / Avène | UN | 521 515 | 1 724 458 | 1 835 235 |
| 268091 / dépôt Muret | UN | 806 091 | 275 939 | 54 891 |
| 268967 / dépôt Muret | UN | 670 475 | 482 984 | 837 481 |
| 021081 / Gaillac | kg | 1 558 863 | 1 652 394 | 1 618 835 |

Les écarts ne s'améliorent pas globalement. Par exemple, l'erreur absolue
moyenne de 268091 au dépôt passe de 530 152 à 751 200 unités ; celle de
268967 passe de 187 490 à 289 628 unités. Celle de 021081 à Gaillac diminue
de 351 351 à 322 608 kg. Changer les paramètres ne suffit pas à résoudre
les différences de périmètre et de logique de planification.

Les volumes annuels servis restent identiques dans ces deux essais :
3 576 442 unités pour 268091 et 1 575 985 pour 268967. Cela ne prouve pas
l'identité des délais ou des trajectoires de service. Même graine ne garantit
pas les mêmes réalisations aléatoires après changement des décisions ;
aucune attribution causale règle par règle n'est revendiquée.

## Part indicative des matières partagées à Avène

Formule : **part = demande de notre PF × coefficient BOM / sorties MRP
totales de la matière**, sur les mêmes semaines d'une même version du plan.
Stock attribuable = stock initial observé × part. Les semaines absentes ne
sont pas mises à zéro et les versions des plans ne sont jamais additionnées.

| Matière | Stock initial site | Diviseur selon notre demande | Stock attribuable | Diviseur selon demande PF industrielle | Stock attribuable |
|---|---:|---:|---:|---:|---:|
| 002612 | 153 521,64 kg | 63,81 | 2 405,95 kg | 42,43 | 3 618,49 kg |
| 007923 | 55 018,98 kg | 18,45 | 2 982,22 kg | 12,32 | 4 465,21 kg |

Plan du 5 janvier 2025 : respectivement 39 et 37 semaines complètes communes.
La seconde méthode utilise les sorties du PF268091 dans le MRP du dépôt,
qui ne sont pas des ordres de fabrication observés à Avène. Ce sont deux
hypothèses de demande, pas un intervalle de confiance. Les douze matières
premières et la dispersion entre versions sont disponibles dans le panneau
HTML et [allocation.json](../../artifacts/testing/mrp_rules_trial_20260928/allocation.json).
Les emballages ne sont pas répartis automatiquement.

Ces stocks estimés ne sont **pas appliqués aux simulations**. Le caractère
partagé est à confirmer pour chaque article ; une part de consommation ne
prouve pas une part de stock, notamment avec des tailles minimales d'achat.
Une simulation allouée doit traiter aussi les commandes ouvertes du site,
sans diviser automatiquement les jours de sécurité ni les tailles de lots.

## Reproduction et preuves

[study.py](../../artifacts/testing/mrp_rules_trial_20260928/study.py) prépare
le graphe, exécute les deux calculs puis assemble le panneau. Les commandes
exactes et les empreintes sont dans
[plan.json](../../artifacts/testing/mrp_rules_trial_20260928/plan.json).
[allocation.py](../../artifacts/testing/mrp_rules_trial_20260928/allocation.py)
calcule séparément les parts à partir des sources et de la demande nominale
du payload de comparaison conservé. Le validateur recalcule cette demande
depuis les CSV du nouveau nominal.

Pour reproduire dans un **nouveau dossier**, depuis la racine du dépôt :

```powershell
$repriseM = 'etudecas/artifacts/testing/mrp_rules_reprise'
New-Item -ItemType Directory -Path $repriseM -ErrorAction Stop
Copy-Item -LiteralPath 'etudecas/artifacts/testing/mrp_rules_trial_20260928/allocation.py' -Destination "$repriseM/allocation.py"
python -B etudecas/artifacts/testing/mrp_rules_trial_20260928/study.py prepare --workdir $repriseM
python -B etudecas/artifacts/testing/mrp_rules_trial_20260928/study.py run --workdir $repriseM
python -B "$repriseM/allocation.py"
python -B etudecas/artifacts/testing/mrp_rules_trial_20260928/study.py render --workdir $repriseM --html etudecas/resultats/essai_regles_mrp_reprise/comparaison.html
```

Reproduction de cette étude avec ses sources figées ; toute nouvelle version
des données exige une nouvelle revue, notamment des hypothèses et du texte
de présentation. Les sorties existantes sont refusées au lieu d'être écrasées.
Le moteur et les sources de simulation ont également une capsule de reproduction.

La [contre-vérification indépendante](../../artifacts/testing/mrp_rules_trial_20260928/validation/independent-validation.json)
contrôle les cellules sources, les règles effectivement lues pendant les
1 825 jours, les quantités UN et l'allocation. Les 34 CSV du nominal sont
identiques à la référence précédente. Qualifications CSV et revue navigateur
se trouvent dans le même dossier de preuves. Aucun essai d'altération de
fichiers, de dates ou de permissions n'a été exécuté.

La donnée 002612/Gaillac du 6 janvier utilisée ici est celle du classeur
actuel : **1 250 kg**, valeur de stock **1 575**. Elle n'intervient pas dans
l'allocation à Avène. La comparaison historique reste inchangée.
