# Agent map / payload

## Mission

Maintenir la carte HTML et ses payloads avec un rendu interactif utile, rapide
et comprehensible.

## Entrees

- `build_supplychain_worldmap.py` ;
- modules `etudecas/visualization/maps/*` ;
- HTML courant ;
- payloads compacts ou embarques ;
- captures Playwright/Edge si necessaire.

## A inspecter

- taille HTML et data embarquee ;
- chargement differé des blocs lourds ;
- onglets simulation, sensibilite, risques, criticite, incertitude ;
- coherence entre ce qui est selectionnable et ce qui est seulement affiche ;
- lisibilite metier des courbes et diagrammes.

## Livrables

- refactor payload/rendu sans casser l'autonomie HTML ;
- verification navigateur quand le rendu est touche ;
- tests des loaders et contrats JS consommes ;
- reduction de taille quand possible.

## Critere de done

- la carte s'ouvre ;
- les onglets critiques restent utilisables ;
- les payloads lourds sont compacts ou charges a la demande ;
- les textes affiches restent metier, pas techniques.

## Refus automatique

Refuser un prototype qui perd l'interactivite principale ou qui masque une
information metier importante pour gagner de la taille.
