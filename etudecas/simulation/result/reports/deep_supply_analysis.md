# Analyse globale supply (synthese consolidee)

Date: 2026-03-06 (UTC)

## 1) Baseline actuelle
- Fill rate: **0.787666** (1171.6524/1487.5)
- Backlog final: **315.8476**
- Cout total: **1273360.3167**
- Inventaire moyen: **1045717.0788** | inventaire final: **1035949.2243**
- Service journalier: **20** jours en sous-service, backlog max **365.8870** au jour **13**

## 2) Matieres d'entree les plus critiques
Definition pratique: criticite structurelle = consommation + mono-sourcing + delai + couverture.

| Rang | Factory | Item | Score | Conso totale | Nb fournisseurs | Couverture (jours) |
|---|---|---|---:|---:|---:|---:|
| 1 | M-1430 | item:042342 | 0.807 | 36569.439 | 1 | 35.571 |
| 2 | M-1430 | item:773474 | 0.472 | 5851.109 | 1 | 10.215 |
| 3 | M-1810 | item:007923 | 0.425 | 2307.511 | 1 | 8.674 |
| 4 | M-1810 | item:338928 | 0.423 | 710.440 | 1 | 122.375 |
| 5 | M-1810 | item:049371 | 0.422 | 1.067 | 1 | 270.570 |
| 6 | M-1810 | item:338929 | 0.421 | 710.440 | 1 | 68.156 |
| 7 | M-1810 | item:693055 | 0.419 | 288.439 | 1 | 121.686 |
| 8 | M-1810 | item:001757 | 0.417 | 1.154 | 1 | 149.199 |
| 9 | M-1430 | item:344135 | 0.414 | 606.036 | 1 | 64.938 |
| 10 | M-1810 | item:029313 | 0.414 | 0.029 | 1 | 95.300 |

## 3) Sensibilite (top drivers normalises)
- Fill rate: demand_item_scale::item:268967 (-0.368), capacity_node_scale::M-1810 (+0.295), capacity_node_scale::M-1430 (+0.269), demand_item_scale::item:268091 (-0.224), supplier_stock_scale (-0.034)
- Backlog: demand_item_scale::item:268967 (+1.899), demand_item_scale::item:268091 (+1.417), capacity_node_scale::M-1810 (-1.096), capacity_node_scale::M-1430 (-0.999), supplier_stock_scale (+0.126)
- Cout total: capacity_node_scale::SDC-1450 (+0.927), lead_time_scale (+0.723), capacity_node_scale::M-1430 (+0.063), transport_cost_scale (+0.017), supplier_stock_scale (+0.007)

## 4) Monte Carlo
- P(fill < 0.90): **1.0000**
- P(fill < 0.85): **0.9835**
- P(backlog > 100): **1.0000**
- P(backlog > 200): **0.9752**

## 5) Exploration systeme large
- Probabilites de risque: `{"p_fill_lt_0_90": 1.0, "p_fill_lt_0_85": 0.9931350114416476, "p_backlog_gt_100": 1.0, "p_backlog_gt_200": 0.9931350114416476, "p_cost_gt_24000": 1.0, "p_cost_gt_28000": 1.0, "p_fill_ge_baseline": 0.02288329519450801, "p_backlog_le_baseline": 0.036613272311212815, "p_cost_le_baseline": 0.5903890160183066}`

## 6) Campagne de chocs
- `combo_extreme_black_swan`: fill=0.081299, backlog=3086.8359, cost=1040011.8817
- `combo_systemic_stress`: fill=0.187129, backlog=2219.9840, cost=1376284.0397
- `combo_supplier_crunch`: fill=0.288266, backlog=1058.7040, cost=1399696.3380
- `review_period_scale_7d`: fill=0.315402, backlog=1018.3400, cost=1308172.0514
- `combo_logistics_strike`: fill=0.315402, backlog=1018.3400, cost=1430864.8547

## 7) Points de vigilance
1. Les intrants critiques mono-source restent prioritaires.
2. `item:007923` est bien traite comme composant special de `M-1810`.
3. Le service reste fortement sensible a la demande et au pilotage de `M-1810`.
