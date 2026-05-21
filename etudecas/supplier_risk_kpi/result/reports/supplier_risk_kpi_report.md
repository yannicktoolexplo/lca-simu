# Supplier Risk KPI

## Statut

Cette brique produit un MVP de KPI fournisseur-article-site a partir des sorties de simulation `etudecas`.
Le cadre operationnel est: KPI normalises -> risque probabiliste -> incertitude -> resilience -> decision robuste.
La baseline analysee ne contient pas assez d'incidents observables pour entrainer une probabilite supervisee; les champs `*_proxy` sont donc des proxys explicites.

## Inputs

- Simulation result: `etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test`
- Sensitivity file: `C:\dev\lca-simu\etudecas\simulation\sensibility\active_supplier_parameter_result\supplier_parameter_recommendations.csv`
- Weeks: 272
- Suppliers: 30
- Supplier-item-site pairs: 40

## Qualite evenementielle

- MRP order rows: 26760
- Observable late MRP rows: 0
- Observable short MRP rows: 0

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
| jaune | 7 |
| vert | 33 |

## Top fournisseurs

| supplier_id | supplier_name | pair_count | max_risk_probability_proxy_4w | max_risk_probability_high_proxy_4w | min_resilience_score | max_action_priority_score | worst_decision_zone | top_item_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDC-1450 | Supplier of Raw Materials - D1450 | 4 | 0.209263 | 0.31612 | 0.645 | 0.122633 | jaune | item:693055 |
| SDC-VD0525412A | Supplier of Packaging - VD0525412A | 1 | 0.212209 | 0.255676 | 0.765343 | 0.113151 | jaune | item:333362 |
| SDC-VD0914360C | Supplier of Packaging - VD0914360C | 1 | 0.188177 | 0.233129 | 0.85 | 0.106689 | jaune | item:338929 |
| SDC-VD0993480A | Supplier of Packaging - VD0993480A | 1 | 0.192948 | 0.238891 | 0.789666 | 0.10301 | jaune | item:344135 |
| SDC-VD0951020A | Supplier of Raw Materials - VD0951020A | 4 | 0.185096 | 0.282762 | 0.748679 | 0.095744 | jaune | item:001757 |
| SDC-VD0901566A | Supplier of Packaging - VD0901566A | 1 | 0.18264 | 0.224126 | 0.822916 | 0.085255 | jaune | item:338928 |
| SDC-VD0508918A | Supplier of Packaging - VD0508918A | 1 | 0.150802 | 0.217379 | 0.775283 | 0.077544 | vert | item:730384 |
| SDC-VD0520132A | Supplier of Raw Materials - VD0520132A | 2 | 0.155385 | 0.228983 | 0.833077 | 0.069986 | vert | item:038005 |
| SDC-VD0520115A | Supplier of Packaging - VD0520115A | 1 | 0.140125 | 0.203177 | 0.775885 | 0.067518 | vert | item:708073 |
| SDC-VD1095770A | Supplier of Packaging - VD1095770A | 1 | 0.131169 | 0.186769 | 0.791407 | 0.060809 | vert | item:734545 |
| SDC-VD0914690A | Supplier of Raw Materials - VD0914690A | 1 | 0.122858 | 0.20242 | 0.833846 | 0.058361 | vert | item:042342 |
| SDC-VD0989480A | Supplier of Packaging - VD0989480A | 1 | 0.11511 | 0.186539 | 0.834615 | 0.046821 | vert | item:426331 |

## Top couples fournisseur-article-site

| supplier_id | dst_node_id | item_id | risk_probability_proxy_4w | risk_probability_high_proxy_4w | action_priority_score | resilience_score | early_warning_score | lead_days_q90 | decision_zone | robust_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDC-1450 | M-1810 | item:693055 | 0.209263 | 0.31612 | 0.122633 | 0.685 | 0.032143 | 73.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-1450 | M-1430 | item:773474 | 0.20383 | 0.30623 | 0.119449 | 0.645 | 0.324 | 10.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0525412A | M-1430 | item:333362 | 0.212209 | 0.255676 | 0.113151 | 0.765343 | 0.236095 | 62.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0914360C | M-1810 | item:338929 | 0.188177 | 0.233129 | 0.106689 | 0.85 | 0.009048 | 44.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0993480A | M-1430 | item:344135 | 0.192948 | 0.238891 | 0.10301 | 0.789666 | 0.010857 | 37.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0951020A | M-1810 | item:001757 | 0.185096 | 0.22881 | 0.095744 | 0.788679 | 0.006786 | 87.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0951020A | M-1810 | item:007923 | 0.169245 | 0.243912 | 0.087545 | 0.748679 | 0.363333 | 4.0 | vert | routine_monitoring |
| SDC-VD0901566A | M-1810 | item:338928 | 0.18264 | 0.224126 | 0.085255 | 0.822916 | 0.189115 | 71.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0951020A | M-1810 | item:001848 | 0.163893 | 0.282762 | 0.084777 | 0.756217 | 0.071048 | 71.2 | vert | routine_monitoring |
| SDC-1450 | SDC-1450 | item:773474 | 0.14295 | 0.30775 | 0.083772 | 0.645 | 0.048 | 0.0 | vert | routine_monitoring |
| SDC-1450 | SDC-1450 | item:693055 | 0.14295 | 0.30775 | 0.083772 | 0.645 | 0.048 | 0.0 | vert | routine_monitoring |
| SDC-VD0508918A | M-1430 | item:730384 | 0.150802 | 0.217379 | 0.077544 | 0.775283 | 0.012901 | 57.0 | vert | routine_monitoring |

## Fichiers

- Panel hebdomadaire: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\data\supplier_item_week_panel.csv`
- KPI couples: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\data\supplier_item_risk_kpi.csv`
- KPI fournisseurs: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\data\supplier_risk_kpi.csv`
- Summary JSON: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\summaries\supplier_risk_kpi_summary.json`

## Lecture correcte

Le score est utile pour prioriser une revue fournisseur, pas pour automatiser seul une decision.
Pour passer a une prediction industrielle, il faut alimenter le panel avec incidents reels ou campagnes Monte Carlo/stress tests, puis calibrer les probabilites avec un split temporel.
