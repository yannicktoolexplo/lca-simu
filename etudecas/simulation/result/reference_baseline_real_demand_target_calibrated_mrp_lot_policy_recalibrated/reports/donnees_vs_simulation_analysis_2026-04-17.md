# Analyse Donnees vs Simulation

## Cadre

Cette note prend comme source de vérité métier les fichiers du dossier [donnees](C:/dev/lca-simu/etudecas/donnees):

- [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx)
- [268967.xlsx](C:/dev/lca-simu/etudecas/donnees/268967.xlsx)
- [268191.xlsx](C:/dev/lca-simu/etudecas/donnees/268191.xlsx)
- [021081.xlsx](C:/dev/lca-simu/etudecas/donnees/021081.xlsx)
- [Stocks_MRP.xlsx](C:/dev/lca-simu/etudecas/donnees/Stocks_MRP.xlsx)
- [Fournisseur.xlsx](C:/dev/lca-simu/etudecas/donnees/Fournisseur.xlsx)
- [Data_poc.xlsx](C:/dev/lca-simu/etudecas/donnees/Data_poc.xlsx)

La simulation de reference comparee ici est:

- [first_simulation_report.md](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/reports/first_simulation_report.md)
- [first_simulation_summary.json](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/summaries/first_simulation_summary.json)

## Ce qui est maintenant aligne

### Demande finale

Les totaux issus de [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx) sont maintenant alignes avec le run:

- `268967 = 1,706,750`
- `268091 = 3,576,442`

Le run final mesure:

- `Total demand = 5,283,192.0`
- `Total served = 5,283,192.0`
- `Fill rate = 1.0`
- `Ending backlog = 0`

### Warm-up et etat initial

Le run de reference est maintenant sans warm-up:

- `warmup_days = 0`
- `timeline_days = 365`

Et il n’y a pas de pipeline initial injecte:

- `total_explicit_initialization_pipeline_qty = 0.0`

Donc la baseline actuelle correspond a une lecture plus fidele d’un `jour 1` metier, avec etat initial explicite mais sans pre-historique artificiel.

### MRP sur les intrants transformes

Le cas `SDC-1450 / item:021081` a ete corrige. Le trace MRP ne part plus d’un besoin nominal aberrant derive de la capacite max du process.

Dans [mrp_trace_daily.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/mrp_trace_daily.csv):

- `gross_requirement_basis = static_requirement`
- `bb_qty = 221.208347 / jour`
- `stock_proj_qty = 1,142,100`
- `bn_qty = 0`

Ce point est maintenant beaucoup plus defensable que l’ancien signal a `6.5M/an`.

## Ce qui est coherent avec les donnees source

### Familles tres tamponnees par le stock initial

Les donnees source montrent des matieres fortement couvertes au depart, et la simulation raconte la meme histoire:

- `021081` a Gaillac
- `002612` a Avène
- `055703`
- `039668`

Conséquence logique:

- plusieurs fournisseurs restent dormants sans que ce soit un bug d’affichage
- c’est un effet de snapshot stock, pas un effet de modele pur

Le diagnostic fournisseurs dormants reste coherent avec cela dans [dormant_suppliers_diagnostic.md](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/reports/dormant_suppliers_diagnostic.md).

### Branche Gaillac

Les donnees source montrent:

- `773474` est une sortie structurante
- `021081` est un intrant reel de cette transformation
- mais `021081` est fortement tamponne par le stock initial

La simulation finale confirme cela:

- Gaillac reste critique comme noeud
- mais `021081` n’est pas un intrant en tension dans cette baseline

## Ce qui reste moins fidele aux donnees source

### 1. Amont encore trop reconstruit

Le run final utilise encore:

- `33` politiques `unmodeled_supplier_source_policy`
- `34` lignes `supplier_capacity_basis`
- `1` `assumed_supplier_node`
- `1` `assumed_supply_edge`

dans [assumptions_ledger.csv](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/assumptions_ledger.csv).

Lecture:

- le graphe couvre bien la structure principale,
- mais une partie importante de l’amont n’est pas directement issue des `xlsx`,
- elle est encore inferee, calibree ou supposee.

### 2. Capacites fournisseurs encore peu sourcées

Le moteur exploite des capacites fournisseur, mais une partie reste derivee d’heuristiques ou de calibrations.

Ca permet au run de tenir, mais ce n’est pas equivalent a:

- une capacite fournisseur observee,
- ou une contrainte industrielle directement documentee dans `donnees`.

### 3. Trop de service pour trop de stock

La baseline finale est propre en service:

- `fill_rate = 1.0`
- `ending_backlog = 0`

Mais elle reste tres lourde en inventaire:

- `avg_inventory = 425,985,696.6569`
- `ending_inventory = 399,464,952.0318`
- `total_estimated_source_ordered_qty = 45,893,398.8419`

Lecture:

- la simulation tient le service,
- mais probablement avec trop de stock et encore trop de reappro amont reconstruit.

### 4. Fournisseurs actifs encore trop reguliers

Les fournisseurs actifs trop constants ne viennent pas d’un bug de map. Ils viennent surtout de:

- familles FIA mono-source
- `standard_order_qty` fixes
- amont reconstruit
- demande aval assez lissée sur certaines branches

Le diagnostic reste valide dans [active_constant_suppliers_diagnostic.md](C:/dev/lca-simu/etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/reports/active_constant_suppliers_diagnostic.md).

## Lecture par grande zone

### DC

Le DC est maintenant bien pilote en service, et le point faible principal n’est pas lui.

### M-1810

Le site est globalement coherent, mais reste tire par:

- ses regles de lots
- ses composants packaging
- quelques intrants plus tendus structurellement

### M-1430

Le site reste la zone la plus sensible cote realisme supply:

- packaging critique
- dependance a `773474`
- profils fournisseurs parfois trop reguliers

### SDC-1450 / Gaillac

Gaillac reste un noeud tres important mais hybride:

- critique comme transformation amont
- encore partiellement appuye par un edge suppose
- et structurellement masque par certains stocks initiaux

## Ce qui va bien

1. La demande finale est maintenant alignee aux `xlsx`.
2. Le warm-up artificiel a ete retire de la baseline de reference.
3. Le cas `021081` n’est plus mal raconte par le trace MRP.
4. Les BOM/FIA importantes sont bien prises en compte dans la structure du simulateur.
5. La map est devenue utile pour l’exploration, a condition de la lire comme un outil de diagnostic et non comme une source de verite metier.

## Ce qui ne va pas encore assez bien

1. L’amont n’est pas encore assez source directement depuis les donnees.
2. Les capacites fournisseur restent trop souvent derivees.
3. `007923` reste un intrant structurellement mal ferme dans le graphe fournisseur.
4. Le systeme tient le service avec trop d’inventaire.
5. Certaines courbes fournisseur restent sur-regularisees par la politique, pas par la realite observee.

## Conclusion nette

La simulation actuelle est maintenant bien meilleure qu’avant pour servir de baseline:

- demande correcte
- pas de warm-up artificiel
- etat initial explicite
- MRP plus lisible sur les branches critiques

Mais elle n’est pas encore une traduction pure des `xlsx`.

Le coeur de l’ecart restant est ici:

- amont reconstruit
- capacites inferees
- edge suppose sur `007923`
- surstock global

## Priorites avant les prochaines simulations

1. Garder cette baseline comme nouvelle reference de travail.
2. Traiter explicitement `007923`.
3. Sourcer ou au moins classer les capacites fournisseur en `source / derivee / calibree`.
4. Prioriser les branches critiques de `M-1430` et `M-1810` pour les prochaines etudes de risque.
5. Lancer les prochaines simulations sur cette baseline, pas sur les anciennes versions avec warm-up.
