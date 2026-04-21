# Critique de l'affichage fournisseur

Base analysee :
- [build_supplychain_worldmap.py](C:/dev/lca-simu/etudecas/affichage_supply_script/build_supplychain_worldmap.py)
- [production_supplier_shipments_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_shipments_daily.csv)
- [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv)
- [mrp_trace_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_trace_daily.csv)
- [production_supplier_stocks_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_stocks_daily.csv)
- [production_supplier_capacity_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_capacity_daily.csv)

## Diagnostic net

L'affichage fournisseur reste encore mal structuré pour un manager supply.

Les deux défauts principaux sont :

1. `Expeditions journalieres` et `Ordres` racontent souvent la meme chose.
2. `Stock fournisseur` et `MRP detaille` restent utiles, mais ils parlent tous deux de stock et peuvent se recouvrir si on ne les explique pas clairement.

## Constats chiffres

Sur `28` fournisseurs visibles :

- `14` fournisseurs n'ont aucune expedition et aucun ordre.
- `14` fournisseurs ont des expeditions.
- pour ces `14` fournisseurs actifs, les series `expeditions aval` et `ordres sortants` sont **exactement identiques** dans les donnees journalières.
- `28/28` fournisseurs ont a la fois :
  - une vue `Stock fournisseur` basee sur le stock reel
  - une vue `MRP detaille` basee sur le stock projete / cible / besoin net

Conclusion :

- le graphe `Ordres` au niveau fournisseur est redondant avec `Expeditions` pour tous les fournisseurs actifs de cette baseline.
- le graphe `Ordres` n'apporte une information distincte que si on veut aussi montrer les ordres entrants fournisseur, mais melanger inbound et outbound sur le meme graphe rend la lecture confuse.

## Exemple clair : `SDC-VD0514881A`

Etat actuel :

- `Stock fournisseur` : serie `016332`
- `Expeditions journalieres` : serie `016332`
- `Utilisation capacite` : serie `016332`
- `Ordres` : 
  - `Ordres amont - 016332`
  - `Receptions fournisseur - 016332`
  - `Expeditions aval - 016332`
  - `Receptions aval attendues - 016332`
- `MRP detaille` :
  - `Stock projete`
  - `Position stock`
  - `Cible stock`
  - `Besoin net`

Probleme :

- pour ce fournisseur, `Expeditions journalieres` et `Expeditions aval - 016332` sont le meme signal de sortie.
- le graphe `Ordres` surcharge donc l'ecran sans apporter une vraie information differente.

## Critique franche du design actuel

Ce qui ne va pas :

- montrer `Expeditions` et `Ordres` en meme temps pour un fournisseur actif est inutile si les courbes sont identiques.
- montrer une vue `Ordres` vide pour un fournisseur dormant est inutile.
- garder un onglet `Carnet` quand il n'y a aucun ordre est inutile.
- afficher au premier niveau des vues "techniques" avant d'avoir montre :
  - le stock reel
  - le flux reel
  - la tension capacitaire
  est une mauvaise priorite pour un manager.

Ce qui est defendable :

- `Stock fournisseur`
- `Expeditions journalieres`
- `Utilisation capacite`
- `MRP detaille` uniquement comme vue secondaire
- `Carnet` uniquement s'il y a effectivement des ordres

## Proposition meilleure

### Niveau 1 : 3 vues seulement

Pour chaque fournisseur, afficher seulement :

1. `Stock`
   - stock reel journalier par item
2. `Flux aval`
   - expeditions physiques journalieres par item
3. `Capacite`
   - utilisation capacite par item

Ces trois vues sont distinctes et lisibles manager :

- ai-je du stock ?
- est-ce que j'expedie ?
- suis-je sous tension de capacite ?

### Niveau 2 : seulement si pertinent

Afficher en sous-onglets :

- `MRP detaille`
  - stock projete
  - position stock
  - cible stock
  - besoin net
- `Carnet`
  - uniquement si au moins un ordre existe
- `Risque`

### Ce qu'il faut retirer

Retirer le graphe `Ordres` fournisseur tant qu'il duplique `Expeditions`.

Raison :

- dans cette baseline, le signal sortant de `mrp_orders_daily.csv` pour les fournisseurs actifs est le meme que le flux physique `production_supplier_shipments_daily.csv`.
- conserver les deux brouille la lecture sans ajouter d'information.

## Regle proposee pour l'UI

Pour un fournisseur :

- si `expeditions sortantes` = `ordres sortants` sur l'horizon, ne montrer que `Flux aval`
- si aucun ordre n'existe, masquer `Carnet`
- si aucune tension capacitaire n'existe mais une serie capacite est disponible, conserver `Capacite` car elle reste differente des flux
- garder `MRP detaille` uniquement en secondaire

## Recommendation pratique

La bonne version fournisseur pour cette map est :

- premier niveau :
  - `Stock`
  - `Flux aval`
  - `Capacite`
- second niveau :
  - `MRP detaille`
  - `Carnet` seulement si non vide
  - `Risque`

Il faut supprimer l'onglet `Ordres` fournisseur dans l'etat actuel de la baseline.
