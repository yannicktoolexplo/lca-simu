# Analyse complete de coherence supply chain

Reference analysee :

- donnees source :
  - [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx)
  - [268967.xlsx](C:/dev/lca-simu/etudecas/donnees/268967.xlsx)
  - [268191.xlsx](C:/dev/lca-simu/etudecas/donnees/268191.xlsx)
  - [021081.xlsx](C:/dev/lca-simu/etudecas/donnees/021081.xlsx)
  - [Stocks_MRP.xlsx](C:/dev/lca-simu/etudecas/donnees/Stocks_MRP.xlsx)
- simulation :
  - [first_simulation_report.md](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/reports/first_simulation_report.md)
  - [first_simulation_summary.json](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/summaries/first_simulation_summary.json)
  - [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv)
  - [mrp_trace_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_trace_daily.csv)
  - [production_supplier_shipments_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_shipments_daily.csv)
  - [production_supplier_stocks_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_stocks_daily.csv)
  - [production_supplier_capacity_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_capacity_daily.csv)
  - [production_input_stocks_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_input_stocks_daily.csv)
  - [production_output_products_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_output_products_daily.csv)
  - [production_demand_service_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_demand_service_daily.csv)
  - [production_constraint_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_constraint_daily.csv)
  - [assumptions_ledger.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/assumptions_ledger.csv)

## Conclusion executive

La baseline actuelle est globalement coherente **dans sa mecanique interne** :

- les ordres de type `lane_release` correspondent aux expeditions physiques,
- les dates d'arrivee sont bien ulterieures aux dates de lancement,
- les stocks fournisseurs suivent presque parfaitement la relation :
  - stock(t) - stock(t-1) = receptions(t) - expeditions(t)

Mais elle n'est **pas encore completement coherente avec la source de verite metier** :

- la demande de `268091` colle a `demand_PF.xlsx`,
- la demande de `268967` ne colle pas encore a `demand_PF.xlsx`,
- une part importante de l'amont reste reconstruite via `estimated_source`,
- une partie de la trace MRP repose encore sur des `static_requirement`.

Donc :

- comme simulateur, l'ensemble tient,
- comme jumeau strict des donnees source, il reste des ecarts importants.

## 1. Demande source vs demande simulee

Depuis [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx), feuille `Demande` :

- `268091 = 3,576,442`
- `268967 = 1,575,986`

Depuis [production_demand_service_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_demand_service_daily.csv) :

- `268091 = 3,576,442`
- `268967 = 1,706,750`

Diagnostic :

- `268091` est aligne.
- `268967` est surestime de `130,764`, soit environ `+8.30%`.

Implication :

- toute analyse matiere derivee de `268967` est encore gonflee dans la simulation actuelle.
- la baseline n'est donc pas completement alignee a la source de verite `demand_PF.xlsx`.

## 2. Service et horizon

Depuis [first_simulation_report.md](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/reports/first_simulation_report.md) :

- horizon mesure : `365 jours`
- warm-up : `0`
- fill rate : `1.0`
- ending backlog : `0`

Ce point est coherent avec l'hypothese metier retenue :

- pas de pre-historique artificiel,
- les stocks initiaux de [Stocks_MRP.xlsx](C:/dev/lca-simu/etudecas/donnees/Stocks_MRP.xlsx) servent de photo initiale,
- les KPI sont donc interpretable comme une vraie annee simulee.

## 3. Ordres, expeditions et receptions

### 3.1 Cohérence `lane_release -> shipment`

Comparaison entre :

- [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv)
- [production_supplier_shipments_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_shipments_daily.csv)

Resultat :

- `1688` lignes `lane_release`
- `1688` lignes d'expedition fournisseur
- `1684` cles uniques `(src,dst,item,jour)` comparees
- `0` mismatch

Diagnostic :

- les expeditions physiques et les ordres de lancement sur lane sont coherents.
- quand la map montre `Flux aval`, elle montre bien le meme evenement physique que le moteur.

### 3.2 Cohérence temporelle des receptions

Sur [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv) :

- `arrival_day - release_day` min = `1`
- max = `190`
- `0` cas avec lead nul ou negatif

Diagnostic :

- les receptions planifiees sont bien posterieures aux lancements,
- donc la logique `commande -> transit -> reception` a du sens.

### 3.3 Interprétation correcte des graphes

Apres correction du rendu :

- les graphes `Ordres` utilisent `release_day` pour les lancements,
- et `arrival_day` pour les receptions.

Donc les graphes ne posent plus artificiellement les receptions au jour de commande.

## 4. Cohérence des stocks fournisseur

Test sur [production_supplier_stocks_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_stocks_daily.csv), hors `SDC-1450` :

- `12012` transitions jour-a-jour verifiees
- `11998` exactes a tolerance numerique pres
- taux de cohérence : `99.88%`

Les rares ecarts constates sont du bruit d'arrondi flottant, pas de vraies anomalies physiques.

Diagnostic :

- les graphes `Stock fournisseur`, `Reappro amont` et `Flux aval` sont globalement coherents entre eux.

## 5. Ce que racontent vraiment les CSV MRP

### 5.1 Typologie des ordres

Dans [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv) :

- `lane_release = 1688`
- `estimated_source = 1010`

Diagnostic :

- une grosse partie du systeme est bien pilotee par des lanes explicites,
- mais l'amont reconstruit reste tres important.

### 5.2 Static requirement

Dans [mrp_trace_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_trace_daily.csv) :

- `66` paires `(node,item)` ont encore `gross_requirement_basis = static_requirement`
- `28` paires seulement ont `has_mrp_snapshot_policy = 1`

Diagnostic :

- le MRP n'est pas encore integralement porte par la demande reelle et la propagation aval,
- une partie de la logique reste basee sur un besoin statique de dimensionnement.

Implication :

- les graphes `MRP detaille` ont du sens comme lecture interne du moteur,
- mais ne doivent pas etre pris partout comme une verite metier pure.

## 6. Lecture fournisseur : ce qui a du sens et ce qui n'en a pas

Etat actuel des vues fournisseur dans la map :

- `Stock fournisseur`
  - source : [production_supplier_stocks_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_stocks_daily.csv)
  - sens : bon
- `Flux aval`
  - source : [production_supplier_shipments_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_shipments_daily.csv)
  - sens : bon
- `Capacite`
  - source : [production_supplier_capacity_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_capacity_daily.csv)
  - sens : bon
- `Reappro amont`
  - source : inbound `estimated_source` / receptions fournisseur de [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv)
  - sens : utile seulement si le fournisseur a un vrai amont journalise
- `Carnet`
  - source : [mrp_orders_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_orders_daily.csv)
  - sens : utile comme audit, pas comme vue principale
- `MRP detaille`
  - source : [mrp_trace_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_trace_daily.csv)
  - sens : analytique, secondaire

## 7. Pourquoi la moitié des fournisseurs sont dormants

Ce n'est pas un bug graphique.

Sur la baseline actuelle :

- `28` fournisseurs visibles
- `14` sans expedition ni ordre
- `14` actifs

Explication :

- stocks initiaux eleves pour certaines matieres,
- alternatifs jamais tires,
- horizon `1 an` qui ne force pas toujours a consommer l'amont dormant.

Exemple typique :

- `021081` reste largement couvert par le stock initial de Gaillac,
- donc des fournisseurs comme `VD0975221A` restent dormants sans que ce soit incoherent.

## 8. Ce qui est correct dans les graphes

### Correct

- `Stock fournisseur` <-> stock fin de jour
- `Flux aval` <-> expeditions physiques
- `Capacite` <-> utilisation journaliere
- `Reappro amont` <-> ordres entrants et receptions fournisseurs, aux bons jours
- `Ordres lane` sur les edges <-> ordres lances / receptions prevues, aux bons jours

### Encore discutable

- `MRP detaille` quand la paire est basee sur `static_requirement`
- la comparaison directe entre `stock reel` et `stock projete` sans rappeler cette distinction

## 9. Ce qui ne va pas encore

### 9.1 Demande `268967`

Le plus gros ecart source vs simulation reste la demande `268967`.

Tant qu'elle n'est pas recalee sur [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx), les flux et besoins lies a :

- `773474`
- `021081`
- plusieurs packs de `M-1430`

restent potentiellement surevalues.

### 9.2 Amont reconstruit

- `35` couples amont non explicitement modelises
- `1010` ordres `estimated_source`

Donc une part importante de l'amont reste une reconstruction de politique, pas une donnee source pure.

### 9.3 MRP partiellement statique

- `66` paires avec `static_requirement`

Donc le detail MRP est encore un melange de :

- besoin reelement tire par la demande,
- besoin statique de pilotage.

## 10. Jugement final

### Ce qui a du sens

- la chaine `ordre -> expedition -> reception` a du sens dans le moteur
- les stocks fournisseurs sont globalement coherents avec les flux
- les graphes principaux fournisseurs ont maintenant une semantique propre

### Ce qui a encore un statut de modele, pas de verite metier

- la demande `268967`
- l'amont `estimated_source`
- les traces MRP basees sur `static_requirement`

### Conclusion nette

Le systeme actuel est coherent **comme simulation instrumentee**.

Il n'est pas encore totalement coherent **comme reproduction stricte des donnees source**.

La priorite technique la plus importante avant de pousser plus loin les analyses reste :

1. recaler `268967` sur [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx)
2. reduire l'amont `estimated_source`
3. distinguer clairement dans la map les paires MRP :
   - `snapshot / demande reelle`
   - `static_requirement`
