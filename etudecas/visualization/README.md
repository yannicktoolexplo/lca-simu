# Visualisation etudecas

Ce dossier contient les generateurs d'artefacts visuels.

## Structure

- `maps/` : generation des cartes HTML interactives.
- `maps/journey_scenario_delivery.py` : publication d'un explorateur de lots
  depuis les CSV d'un scénario existant.
- `maps/material_delivery.py` : actualisation du contexte matière dans une
  nouvelle copie de carte.
- `diagnostic_fusion/` : rapprochement interactif des creux hebdomadaires de
  Muret, des stocks de la chaîne et des expériences locales de 2025.
- `standalone_html.py` : conditionnement et validation d'archives HTML autonomes,
  partagé avec les outils de recherche.

Les publications et le conditionnement HTML utilisent directement les modules
de ce dossier. Les anciens relais ont été retirés ; utiliser les commandes
ci-dessous dans les scripts et les procédures.

Les commandes canoniques s'affichent avec :

```powershell
python -m etudecas.visualization.maps.journey_scenario_delivery --help
python -m etudecas.visualization.maps.material_delivery --help
python -m etudecas.visualization.standalone_html --help
```

Les anciens scripts `etudecas/testing/journey_scenario_delivery.py` et
`etudecas/testing/material_delivery.py` sont remplacés respectivement par
`python -m etudecas.visualization.maps.journey_scenario_delivery` et
`python -m etudecas.visualization.maps.material_delivery`, avec les mêmes options.
Lancer ces commandes depuis la racine du dépôt. Les deux modules de publication
ne prennent pas en charge le lancement par chemin de fichier : sans installation
du paquet, celui-ci échoue à importer `etudecas`. Aucun bootstrap supplémentaire
n'est ajouté pour maintenir cet ancien mode d'accès.

## Construire la carte

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py
```

## Diagnostic des épisodes 2025

Le rapport autonome `docs/archive/ALEAS_LOCALISES_20261104.html` compare quatre
épisodes et sept cas aval, à partir des preuves locales du 4 novembre. Trois
graphiques distinguent demande répartie/réponse client simulée, stocks de clôture
avec photos industrielles datées, puis flux et transit client sur axes distincts.
Les durées de libération sont lundi–vendredi ; départs et transit restent en
jours calendaires. Activation, volume témoin, exposition en unités-jours,
rattrapage et censure restent distincts, sans classement ni score de service réel.
Les arrivées amont sont figées : ces rejeux conditionnels ne sont pas un MRP
autonome. Le lien vers les creux précédents est conservé. Le générateur daté
et les preuves ciblées sont dans `artifacts/testing/aleas_localises_20261104/ui` ;
les CSV complets restent locaux. Aucun nouveau module générique ni calcul cinq ans.

Le générateur fusionne les épisodes de `remontee_chaine_reelle.html` et les
résultats nominal/A/D/E de `comparaison_arrets_693055.html`. Les originaux
restent conservés. Il nécessite ces preuves locales et n'exécute aucun moteur.

```powershell
python -B -m etudecas.visualization.diagnostic_fusion.build --source-notes etudecas/artifacts/testing/diagnostic_suite_20261022/source/episode_source_notes.json --replays etudecas/artifacts/testing/diagnostic_fusion_20261022/simulation/episode_replays.json --timeliness etudecas/artifacts/testing/diagnostic_suite_20261022/simulation/timeliness.json --output-dir etudecas/resultats/priorites_20261103/interface --proof-dir etudecas/artifacts/testing/priorites_20261103/ui/BUILD_UNIQUE
```

Livrable : `etudecas/resultats/priorites_20261103/interface/diagnostic_fusion.html`,
accessible aussi depuis `etudecas/index.html`. Le manifeste de construction
est dans `etudecas/artifacts/testing/priorites_20261103/ui/BUILD_UNIQUE`. Les vues
précédentes restent dans `resultats/diagnostic_fusion_20261022` et
`resultats/diagnostic_suite_20261022`.
L'écran principal montre les creux cliquables et une seule fiche courte.
Les produits sont désignés par leur référence article, y compris dans les
détails et les données embarquées. Les sources industrielles restent intactes.
Les raccourcis classent la quantité des mouvements de stock, sans leur signe, par rapport à la demande
(ratio croissant, puis quantité et date ; demande nulle exclue).
La remontée Muret → usine → Gaillac utilise les photos à la date exacte ;
une absence reste inconnue. Les analyses longues sont repliées par défaut.
« Après le creux » distingue le retour du mouvement de stock d'un rattrapage client.
Les détails comparent 1, 2 et 4 semaines : hausses et baisses par mouvements de stock,
demande et bilan de stock. Une fenêtre incomplète n'est pas extrapolée.
Deux décompositions comptables hypothétiques peuvent montrer que le même
stock final reste compatible avec des sorties différentes ; elles ne
reconstituent ni des livraisons observées ni une simulation native.
Un clic sur une semaine aligne les stocks en KG/UN, le bilan signé de Muret,
les sources et les hypothèses. Le mouvement de stock sans son signe reste un indicateur de rapprochement,
pas un taux de service mesuré. Les rejeux locaux conservent les arrivées
simulées et ne recalculent pas le MRP amont ; ils sont distincts des scénarios
annuels. Six fiches distinguent faits, hypothèses, données discriminantes et
verdict. Quatre épisodes ont cinq cas de rejeu avec livraisons à l'échéance
conventionnelle demande + 2 jours, délais pondérés par UN, comparaison appariée au nominal et
rattrapage. Le backlog total sur 28 jours reste séparé du retard des cohortes
de la semaine ; les éventuelles observations censurées sont affichées.
Ces délais simulés ne sont pas un OTIF industriel observé.
Les détails numériques et les contrôles d'interaction ne remplacent
pas une validation industrielle ni un rendu navigateur.

La couverture industrielle est de 51 semaines observées par article (6 janvier–28 décembre 2025), séparée des scénarios annuels. Les finances ne sont jamais converties en unités physiques. La carte sur cinq ans du 14 octobre reste une livraison datée ; ses comparaisons ne sont pas actualisées par le diagnostic.

L’option `--receipt-stages etudecas/artifacts/testing/disponibilites_20261103/receipt_stage_review.json`
ajoute la revue des deux attentes dans une nouvelle copie sous
`resultats/disponibilites_20261103/interface` (preuves dans un sous-dossier unique
de `artifacts/testing/disponibilites_20261103/ui`). Son encart est limité au
PF 268091, semaines des 7, 14 et 21 avril ; ses détails sont repliés.
« Retard simulé d’avril » ouvre le 7 avril sans qualifier cette semaine de
rupture réelle. L’essai synthétique et les disponibilités simulées restent
séparés du service annuel et de l’identité industrielle inconnue des étapes.
Le fichier de revue et son rapport sont inclus dans la provenance.

La copie `resultats/formats_confirmes_20261103/interface` conserve cette option
et ajoute une seule annotation documentaire sur l’audit annuel matière/emballages.
Le builder lit uniquement la clé
`user_confirmed_rules.material_packaging_ratio_due_to_formats` de
`docs/reference/source_knowledge.json`, avec son empreinte et le bilan lié.
Plusieurs formats sont confirmés, leur répartition de volumes reste inconnue.
Cette information ne modifie ni nomenclature, ni calcul physique, ni diagnostic
client. Sans fichier ou sans cette clé, l’annotation est absente et la voie
précédente reste utilisable. Aucun nouveau paramètre de commande n’est ajouté.

La copie `resultats/semaine_avril_bilan_20261103/interface` conserve les formats
confirmés et la navigation des 102 semaines-articles. Son encart d’avril utilise
le dossier de la semaine du 7 au 13 avril et le bilan des 2 et 3 novembre ;
les observations réelles restent séparées des événements et essais simulés.
Les copies précédentes sont conservées, sans modification de la vue ni du builder.

```powershell
python -B -m etudecas.visualization.diagnostic_fusion.build --source-notes etudecas/artifacts/testing/diagnostic_suite_20261022/source/episode_source_notes.json --replays etudecas/artifacts/testing/diagnostic_fusion_20261022/simulation/episode_replays.json --timeliness etudecas/artifacts/testing/diagnostic_suite_20261022/simulation/timeliness.json --receipt-stages etudecas/artifacts/testing/semaine_avril_bilan_20261103/receipt_stage_review.json --output-dir etudecas/resultats/semaine_avril_bilan_20261103/interface --proof-dir etudecas/artifacts/testing/semaine_avril_bilan_20261103/ui/BUILD_UNIQUE
```

L’arbre KPI utilise `simulation.analysis.production_daily_metrics` : flux exécutés additionnés, enveloppes restantes dédupliquées par programme, déficit calculé après la dernière passe quotidienne. Sans versions datées identifiables, les révisions sont inconnues (`null`) et exclues du score, déclaré partiel. Les enveloppes journalières ne sont pas assimilées à des nouveaux besoins.
