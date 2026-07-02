# Supplier Risk KPI

## Statut

Cette brique produit un MVP de KPI fournisseur-article-site a partir des sorties de simulation `etudecas`.
Le cadre operationnel est: KPI normalises -> risque probabiliste -> incertitude -> resilience -> decision robuste.
La baseline analysee ne contient pas assez d'incidents observables pour entrainer une probabilite supervisee; les champs `*_proxy` sont donc des proxys explicites.

## Inputs

- Simulation result: `C:\dev\lca-simu\etudecas\simulation\result\_codex_lot_trace_5y_risk_portfolio`
- Sensitivity file: `C:\dev\lca-simu\etudecas\simulation\sensibility\active_supplier_parameter_result\supplier_parameter_recommendations.csv`
- Weeks: 273
- Suppliers: 30
- Supplier-item-site pairs: 40

## Qualite evenementielle

- MRP order rows: 24902
- Observable late MRP rows: 0
- Observable short MRP rows: 2395

## Architecture KPI

| bloc | colonnes | role |
| --- | --- | --- |
| Performance | performance_score_current, performance_distance_score | etat actuel normalise |
| Risque | risk_probability_proxy_4w, action_priority_score | probabilite x impact x criticite |
| Incertitude | risk_probability_low/high_proxy_4w, uncertainty_pressure | intervalle de prudence |
| Resilience | resilience_score, time_to_recover_weeks_proxy | capacite absorption/recuperation |
| Dynamique | change_point_score, early_warning_score | rupture de regime et signaux faibles |
| Decision | decision_zone, robust_decision | action robuste |

## Repartition actions

| action_level | count |
| --- | --- |
| critical | 0 |
| red | 0 |
| amber | 0 |
| green | 40 |

## Zones decisionnelles

| decision_zone | count |
| --- | --- |
| rouge | 0 |
| orange | 0 |
| jaune | 5 |
| vert | 35 |

## Top fournisseurs

| supplier_id | supplier_name | pair_count | max_risk_probability_proxy_4w | max_risk_probability_high_proxy_4w | min_resilience_score | max_action_priority_score | worst_decision_zone | top_item_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDC-VD0525412A | Supplier of Packaging - VD0525412A | 1 | 0.202203 | 0.253403 | 0.792463 | 0.100348 | jaune | item:333362 |
| SDC-VD0993480A | Supplier of Packaging - VD0993480A | 1 | 0.183397 | 0.254111 | 0.780435 | 0.071247 | jaune | item:344135 |
| SDC-VD0508918A | Supplier of Packaging - VD0508918A | 1 | 0.148166 | 0.208942 | 0.778821 | 0.070767 | vert | item:730384 |
| SDC-VD0520132A | Supplier of Raw Materials - VD0520132A | 2 | 0.1453 | 0.213946 | 0.833077 | 0.05585 | vert | item:038005 |
| SDC-VD0901566A | Supplier of Packaging - VD0901566A | 1 | 0.164599 | 0.213216 | 0.81883 | 0.053237 | vert | item:338928 |
| SDC-VD0520115A | Supplier of Packaging - VD0520115A | 1 | 0.130559 | 0.193588 | 0.778192 | 0.050928 | vert | item:708073 |
| SDC-VD0914360C | Supplier of Packaging - VD0914360C | 1 | 0.149268 | 0.191745 | 0.85 | 0.048279 | vert | item:338929 |
| SDC-VD1095770A | Supplier of Packaging - VD1095770A | 1 | 0.123626 | 0.191245 | 0.789099 | 0.046462 | vert | item:734545 |
| SDC-VD0989480A | Supplier of Packaging - VD0989480A | 1 | 0.116212 | 0.246138 | 0.834615 | 0.037587 | vert | item:426331 |
| SDC-VD0951020A | Supplier of Raw Materials - VD0951020A | 4 | 0.09213 | 0.227781 | 0.901448 | 0.035889 | vert | item:001757 |
| SDC-VD1096202A | Supplier of Raw Materials - VD1096202A | 1 | 0.109335 | 0.203095 | 0.815538 | 0.035363 | vert | item:039668 |
| SDC-VD0914690A | Supplier of Raw Materials - VD0914690A | 1 | 0.109175 | 0.179691 | 0.833846 | 0.035311 | vert | item:042342 |

## Top couples fournisseur-article-site

| supplier_id | dst_node_id | item_id | risk_probability_proxy_4w | risk_probability_high_proxy_4w | action_priority_score | resilience_score | early_warning_score | lead_days_q90 | decision_zone | robust_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDC-VD0525412A | M-1430 | item:333362 | 0.202203 | 0.253403 | 0.100348 | 0.792463 | 0.011808 | 63.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0993480A | M-1430 | item:344135 | 0.183397 | 0.254111 | 0.071247 | 0.780435 | 0.035342 | 59.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0508918A | M-1430 | item:730384 | 0.148166 | 0.208942 | 0.070767 | 0.778821 | 0.010263 | 67.0 | vert | routine_monitoring |
| SDC-VD0520132A | M-1430 | item:038005 | 0.1453 | 0.213946 | 0.05585 | 0.833846 | 0.015988 | 174.6 | vert | routine_monitoring |
| SDC-VD0901566A | M-1810 | item:338928 | 0.164599 | 0.213216 | 0.053237 | 0.81883 | 0.108892 | 75.8 | vert | routine_monitoring |
| SDC-VD0520132A | M-1810 | item:049371 | 0.138351 | 0.205247 | 0.053179 | 0.833077 | 0.011059 | 147.7 | vert | routine_monitoring |
| SDC-VD0520115A | M-1430 | item:708073 | 0.130559 | 0.193588 | 0.050928 | 0.778192 | 0.019571 | 30.0 | vert | routine_monitoring |
| SDC-VD0914360C | M-1810 | item:338929 | 0.149268 | 0.191745 | 0.048279 | 0.85 | 0.004524 | 43.0 | vert | routine_monitoring |
| SDC-VD1095770A | M-1430 | item:734545 | 0.123626 | 0.191245 | 0.046462 | 0.789099 | 0.022766 | 22.7 | vert | routine_monitoring |
| SDC-VD0989480A | M-1810 | item:426331 | 0.116212 | 0.246138 | 0.037587 | 0.834615 | 0.129671 | 48.2 | vert | routine_monitoring |
| SDC-VD0951020A | M-1810 | item:001757 | 0.09213 | 0.137083 | 0.035889 | 0.938679 | 0.009048 | 88.0 | vert | routine_monitoring |
| SDC-VD1096202A | M-1810 | item:039668 | 0.109335 | 0.203095 | 0.035363 | 0.815538 | 0.020677 | 35.0 | vert | routine_monitoring |

## Fichiers

- Panel hebdomadaire: `C:\dev\lca-simu\etudecas\risk\supplier_criticality\result\data\supplier_item_week_panel.csv`
- KPI couples: `C:\dev\lca-simu\etudecas\risk\supplier_criticality\result\data\supplier_item_risk_kpi.csv`
- KPI fournisseurs: `C:\dev\lca-simu\etudecas\risk\supplier_criticality\result\data\supplier_risk_kpi.csv`
- Summary JSON: `C:\dev\lca-simu\etudecas\risk\supplier_criticality\result\summaries\supplier_risk_kpi_summary.json`

## Lecture correcte

Le score est utile pour prioriser une revue fournisseur, pas pour automatiser seul une decision.
Pour passer a une prediction industrielle, il faut alimenter le panel avec incidents reels ou campagnes Monte Carlo/stress tests, puis calibrer les probabilites avec un split temporel.
