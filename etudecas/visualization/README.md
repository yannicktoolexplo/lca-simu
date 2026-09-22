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

Les anciens points d'entrée `etudecas.testing.journey_scenario_delivery`,
`etudecas.testing.material_delivery` et
`etudecas.prototypes.scan_2027_risk_control.standalone_single_html` restent
des relais. Pour modifier leurs implémentations, travailler dans ce dossier.

Les commandes canoniques s'affichent avec :

```powershell
python -m etudecas.visualization.maps.journey_scenario_delivery --help
python -m etudecas.visualization.maps.material_delivery --help
python -m etudecas.visualization.standalone_html --help
```

## Compatibilite

Le generateur historique reste appelable via :

```bash
python etudecas/affichage_supply_script/build_supplychain_worldmap.py
```

Le chemin canonique est maintenant :

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py
```
