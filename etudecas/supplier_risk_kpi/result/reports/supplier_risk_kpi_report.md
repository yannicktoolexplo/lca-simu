# Supplier Risk KPI

## Statut

Cette brique produit un MVP de KPI fournisseur-article-site a partir des sorties de simulation `etudecas`.
Le cadre operationnel est: KPI normalises -> risque probabiliste -> incertitude -> resilience -> decision robuste.
La baseline analysee ne contient pas assez d'incidents observables pour entrainer une probabilite supervisee; les champs `*_proxy` sont donc des proxys explicites.

## Inputs

- Simulation result: `etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test`
- Sensitivity file: `etudecas\simulation\sensibility\active_supplier_parameter_result\supplier_parameter_recommendations.csv`
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
| jaune | 6 |
| vert | 34 |

## Top fournisseurs

| supplier_id | supplier_name | pair_count | max_risk_probability_proxy_4w | max_risk_probability_high_proxy_4w | min_resilience_score | max_action_priority_score | worst_decision_zone | top_item_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDC-VD0525412A | Supplier of Packaging - VD0525412A | 1 | 0.216066 | 0.259532 | 0.765343 | 0.120382 | jaune | item:333362 |
| SDC-VD0914360C | Supplier of Packaging - VD0914360C | 1 | 0.191703 | 0.236655 | 0.85 | 0.112582 | jaune | item:338929 |
| SDC-VD0993480A | Supplier of Packaging - VD0993480A | 1 | 0.196542 | 0.242485 | 0.789666 | 0.109724 | jaune | item:344135 |
| SDC-VD0901566A | Supplier of Packaging - VD0901566A | 1 | 0.186087 | 0.227572 | 0.822916 | 0.090644 | jaune | item:338928 |
| SDC-VD0508918A | Supplier of Packaging - VD0508918A | 1 | 0.15376 | 0.220337 | 0.775283 | 0.082801 | vert | item:730384 |
| SDC-VD0520132A | Supplier of Raw Materials - VD0520132A | 2 | 0.161496 | 0.235093 | 0.833077 | 0.079299 | vert | item:038005 |
| SDC-VD0520115A | Supplier of Packaging - VD0520115A | 1 | 0.14291 | 0.205961 | 0.775885 | 0.07236 | vert | item:708073 |
| SDC-VD1095770A | Supplier of Packaging - VD1095770A | 1 | 0.133803 | 0.189403 | 0.791407 | 0.065188 | vert | item:734545 |
| SDC-VD0914690A | Supplier of Raw Materials - VD0914690A | 1 | 0.125349 | 0.204911 | 0.833846 | 0.06209 | vert | item:042342 |
| SDC-VD0951020A | Supplier of Raw Materials - VD0951020A | 4 | 0.103467 | 0.209444 | 0.898679 | 0.056051 | vert | item:001757 |
| SDC-VD0989480A | Supplier of Packaging - VD0989480A | 1 | 0.117465 | 0.188894 | 0.834615 | 0.050165 | vert | item:426331 |
| SDC-VD0505677A | Supplier of Raw Materials - VD0505677A | 1 | 0.116227 | 0.181118 | 0.834615 | 0.048058 | vert | item:099439 |

## Top couples fournisseur-article-site

| supplier_id | dst_node_id | item_id | risk_probability_proxy_4w | risk_probability_high_proxy_4w | action_priority_score | resilience_score | early_warning_score | lead_days_q90 | decision_zone | robust_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDC-VD0525412A | M-1430 | item:333362 | 0.216066 | 0.259532 | 0.120382 | 0.765343 | 0.236095 | 62.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0914360C | M-1810 | item:338929 | 0.191703 | 0.236655 | 0.112582 | 0.85 | 0.009048 | 44.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0993480A | M-1430 | item:344135 | 0.196542 | 0.242485 | 0.109724 | 0.789666 | 0.010857 | 37.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0901566A | M-1810 | item:338928 | 0.186087 | 0.227572 | 0.090644 | 0.822916 | 0.189115 | 71.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0508918A | M-1430 | item:730384 | 0.15376 | 0.220337 | 0.082801 | 0.775283 | 0.012901 | 57.0 | vert | routine_monitoring |
| SDC-VD0520132A | M-1430 | item:038005 | 0.161496 | 0.235093 | 0.079299 | 0.833846 | 0.025034 | 174.0 | vert | routine_monitoring |
| SDC-VD0520132A | M-1810 | item:049371 | 0.153069 | 0.219469 | 0.075162 | 0.833077 | 0.010154 | 147.0 | vert | routine_monitoring |
| SDC-VD0520115A | M-1430 | item:708073 | 0.14291 | 0.205961 | 0.07236 | 0.775885 | 0.014422 | 28.0 | vert | routine_monitoring |
| SDC-VD1095770A | M-1430 | item:734545 | 0.133803 | 0.189403 | 0.065188 | 0.791407 | 0.006 | 21.0 | vert | routine_monitoring |
| SDC-VD0914690A | M-1430 | item:042342 | 0.125349 | 0.204911 | 0.06209 | 0.833846 | 0.03593 | 23.9 | vert | routine_monitoring |
| SDC-VD0951020A | M-1810 | item:001757 | 0.103467 | 0.147181 | 0.056051 | 0.938679 | 0.006786 | 87.0 | vert | routine_monitoring |
| SDC-VD0951020A | M-1810 | item:007923 | 0.093802 | 0.168469 | 0.050816 | 0.898679 | 0.363333 | 4.0 | vert | routine_monitoring |

## Fichiers

- Panel hebdomadaire: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\data\supplier_item_week_panel.csv`
- KPI couples: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\data\supplier_item_risk_kpi.csv`
- KPI fournisseurs: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\data\supplier_risk_kpi.csv`
- Summary JSON: `C:\dev\lca-simu\etudecas\supplier_risk_kpi\result\summaries\supplier_risk_kpi_summary.json`

## Lecture correcte

Le score est utile pour prioriser une revue fournisseur, pas pour automatiser seul une decision.
Pour passer a une prediction industrielle, il faut alimenter le panel avec incidents reels ou campagnes Monte Carlo/stress tests, puis calibrer les probabilites avec un split temporel.
