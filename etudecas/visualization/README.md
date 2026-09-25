# Visualisation etudecas

Ce dossier contient les generateurs d'artefacts visuels.

## Structure

- `maps/` : generation des cartes HTML interactives.
- `maps/journey_scenario_delivery.py` : publication d'un explorateur de lots
  depuis les CSV d'un scénario existant.
- `maps/material_delivery.py` : actualisation du contexte matière dans une
  nouvelle copie de carte.
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
