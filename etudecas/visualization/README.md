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

Le générateur fusionne les épisodes de `remontee_chaine_reelle.html` et les
résultats nominal/A/D/E de `comparaison_arrets_693055.html`. Les originaux
restent conservés. Il nécessite ces preuves locales et n'exécute aucun moteur.

```powershell
python -B -m etudecas.visualization.diagnostic_fusion.build --source-notes etudecas/artifacts/testing/diagnostic_suite_20261022/source/episode_source_notes.json --replays etudecas/artifacts/testing/diagnostic_fusion_20261022/simulation/episode_replays.json --timeliness etudecas/artifacts/testing/diagnostic_suite_20261022/simulation/timeliness.json --output-dir etudecas/resultats/diagnostic_suite_20261022/interface --proof-dir etudecas/artifacts/testing/diagnostic_suite_20261022/ui
```

Livrable : `etudecas/resultats/diagnostic_suite_20261022/interface/diagnostic_fusion.html`,
accessible aussi depuis `etudecas/index.html`. Le manifeste de construction
est dans `etudecas/artifacts/testing/diagnostic_suite_20261022/ui`. La première
fusion reste dans `resultats/diagnostic_fusion_20261022` ; les options de sortie
permettent de conserver les livrables précédents.
Un clic sur une semaine aligne les stocks en KG/UN, le bilan signé de Muret,
les sources et les hypothèses. `abs(I)` reste un indicateur de rapprochement,
pas un taux de service mesuré. Les rejeux locaux conservent les arrivées
simulées et ne recalculent pas le MRP amont ; ils sont distincts des scénarios
annuels. Six fiches distinguent faits, hypothèses, données discriminantes et
verdict. Quatre épisodes ont cinq cas de rejeu avec livraisons à l'échéance
conventionnelle J+2, délais pondérés par UN, comparaison appariée au nominal et
rattrapage. Le backlog total sur 28 jours reste séparé du retard des cohortes
de la semaine ; les éventuelles observations censurées sont affichées.
Ces délais simulés ne sont pas un OTIF industriel observé.
Les détails numériques et les contrôles d'interaction ne remplacent
pas une validation industrielle ni un rendu navigateur.
