# Contexte IA - Prediction du risque fournisseur

Ce document rassemble le maximum d'informations utiles pour donner du contexte a une IA qui doit tester, challenger ou ameliorer la prediction de risque fournisseur-matiere du projet `lca-simu`.

## Objectif metier

Le besoin est de passer d'un simple score de criticite fournisseur a une logique exploitable de prediction du risque supply:

- estimer une probabilite d'incident fournisseur sur un horizon court;
- combiner cette probabilite avec l'impact supply attendu;
- prioriser les couples fournisseur-article-site;
- remonter une synthese fournisseur;
- alimenter la carte supply et les panneaux KPI.

La logique actuelle couvre deux briques complementaires:

- `etudecas/prototypes/prediction`: POC de prediction supervisee sur historique synthetique.
- `etudecas/risk/supplier_criticality`: MVP KPI construit depuis les sorties de simulation reelles.

## Statut actuel

Le POC Prediction est fonctionnel, mais ce n'est pas encore un modele industriel calibre.

Points importants:

- les labels `incident_next_30d` et plusieurs variables temporelles du POC Prediction sont synthetiques;
- les impacts supply utilises par le POC viennent d'une etude proxy/simulation existante;
- les sorties `supplier_criticality` viennent des simulations locales et donnent un panel hebdomadaire plus operationnel;
- la baseline KPI actuelle ne contient pas assez d'incidents observables retard/rupture pour entrainer une probabilite supervisee fiable;
- les champs `*_proxy` doivent etre lus comme des proxys explicites, pas comme une verite terrain.

## Fichiers principaux

### Prediction POC

| fichier | role |
| --- | --- |
| `etudecas/prototypes/prediction/run_prediction_poc.py` | genere l'historique synthetique, entraine le modele, calibre les probabilites, score les couples et exporte les resultats |
| `etudecas/prototypes/prediction/data/synthetic_supplier_item_history.csv` | historique hebdomadaire synthetique fournisseur-article-site |
| `etudecas/prototypes/prediction/result/prediction_test_scored_rows.csv` | lignes du jeu de test avec probabilites predites |
| `etudecas/prototypes/prediction/result/predicted_supplier_item_risk.csv` | derniere photo par couple fournisseur-article-site |
| `etudecas/prototypes/prediction/result/predicted_supplier_risk.csv` | aggregation fournisseur |
| `etudecas/prototypes/prediction/result/evaluation_metrics.json` | metriques de validation |
| `etudecas/prototypes/prediction/result/model_feature_coefficients.csv` | coefficients du modele logistique |
| `etudecas/prototypes/prediction/result/prediction_poc_report.md` | rapport synthetique genere |

### Supplier Risk KPI

| fichier | role |
| --- | --- |
| `etudecas/risk/supplier_criticality/build_supplier_criticality.py` | construit les KPI hebdomadaires depuis les sorties simulation |
| `etudecas/risk/supplier_criticality/result/data/supplier_item_week_panel.csv` | panel hebdomadaire complet fournisseur-article-site |
| `etudecas/risk/supplier_criticality/result/data/supplier_item_risk_kpi.csv` | derniere photo KPI par couple |
| `etudecas/risk/supplier_criticality/result/data/supplier_risk_kpi.csv` | aggregation fournisseur |
| `etudecas/risk/supplier_criticality/result/summaries/supplier_risk_kpi_summary.json` | metadata, compteurs et normalisateurs |
| `etudecas/risk/supplier_criticality/result/reports/supplier_risk_kpi_report.md` | rapport metier court |

### Integration carte

La carte HTML est generee par:

`etudecas/affichage_supply_script/build_supplychain_worldmap.py`

Elle lit les sorties KPI risque fournisseur par defaut:

- `etudecas/risk/supplier_criticality/result/summaries/supplier_risk_kpi_summary.json`
- `etudecas/risk/supplier_criticality/result/data/supplier_risk_kpi.csv`
- `etudecas/risk/supplier_criticality/result/data/supplier_item_risk_kpi.csv`
- `etudecas/risk/supplier_criticality/result/data/supplier_item_week_panel.csv`

## Jeu Prediction POC

Historique:

- lignes: 3120
- fournisseurs: 23
- couples fournisseur-article-site: 30
- articles: 23
- sites/usines: 2
- semaines par couple: 104
- dates synthetiques: a partir du 2024-01-01, pas hebdomadaire
- incidents `incident_next_30d`: 306
- taux incident global: 0.098077
- incidents severes `severe_incident_next_30d`: 151
- taux incident severe global: 0.048397

Split temporel:

| split | semaines | lignes |
| --- | ---: | ---: |
| train | 1-72 | 2160 |
| calibration | 73-88 | 480 |
| test | 89-104 | 480 |

Target principale:

`incident_next_30d`: label binaire, vaut 1 si un incident fournisseur est simule dans les 30 prochains jours.

Target secondaire:

`severe_incident_next_30d`: label binaire severe, derive de l'incident et de l'impact/uncertainty.

## Colonnes Prediction POC

| colonne | type | interpretation |
| --- | --- | --- |
| `week_index` | entier | semaine de l'historique, de 1 a 104 |
| `snapshot_date` | date | date de snapshot hebdomadaire |
| `pair_key` | identifiant | cle `supplier_id|item_id|factory_id` |
| `supplier_id` | categorie | fournisseur |
| `factory_id` | categorie | usine/site destinataire |
| `item_id` | categorie | article ou matiere |
| `supplier_count_for_item` | numerique | nombre de fournisseurs pour l'article |
| `structural_proxy_score` | numerique 0-1 | risque structurel issu du proxy initial |
| `impact_proxy_score` | numerique 0-1 | impact supply normalise |
| `combined_proxy_risk_score` | numerique 0-1 | score combine structure x impact |
| `criticality_norm` | numerique 0-1 | criticite normalisee |
| `demand_exposure_norm` | numerique 0-1 | exposition a la demande |
| `volume_exposure_norm` | numerique 0-1 | exposition volume |
| `cover_risk_norm` | numerique 0-1 | risque de couverture stock |
| `lead_time_risk_norm` | numerique 0-1 | risque lie au lead time |
| `mono_source_risk` | numerique 0-1 | exposition mono-source |
| `uncertainty_penalty` | numerique 0-1 | penalite d'incertitude/data quality |
| `lead_mean_days` | numerique | lead time moyen en jours |
| `conditional_expected_backlog_if_incident` | numerique | backlog attendu conditionnellement a un incident |
| `conditional_expected_fill_loss_if_incident` | numerique | perte de fill rate attendue conditionnellement a un incident |
| `recent_otif_4w` | numerique 0-1 | OTIF recent sur 4 semaines |
| `recent_delay_ratio_4w` | numerique | ratio retard recent sur 4 semaines |
| `recent_short_ship_rate_8w` | numerique 0-1 | taux de short shipment recent sur 8 semaines |
| `recent_quality_incidents_12w` | entier | incidents qualite recents sur 12 semaines |
| `open_po_count` | entier | commandes ouvertes |
| `order_count_8w` | entier | nombre de commandes sur 8 semaines |
| `demand_pressure_norm` | numerique | pression demande normalisee |
| `supplier_latent_shock` | numerique | choc latent fournisseur synthetique |
| `season_sin` | numerique | saisonnalite sinusoide |
| `season_cos` | numerique | saisonnalite cosinus |
| `true_incident_probability_30d` | numerique 0-1 | vraie probabilite synthetique utilisee pour tirer le label |
| `incident_next_30d` | binaire | target principale |
| `severe_incident_next_30d` | binaire | target severe |

Colonnes ajoutees dans `predicted_supplier_item_risk.csv`:

| colonne | role |
| --- | --- |
| `predicted_incident_probability_30d` | probabilite calibree d'incident a 30 jours |
| `predicted_incident_probability_30d_raw` | probabilite brute avant calibration isotonic |
| `predicted_expected_backlog_risk_30d` | `predicted_incident_probability_30d * conditional_expected_backlog_if_incident` |
| `predicted_expected_fill_loss_risk_30d` | `predicted_incident_probability_30d * conditional_expected_fill_loss_if_incident` |
| `predicted_priority_score` | score de priorite mixant probabilite et impact backlog |

## Generation synthetique du POC

La fonction `generate_synthetic_history()` construit 104 semaines par couple.

Variables structurelles reprises du proxy:

- `structural_proxy_score`
- `impact_proxy_score`
- `uncertainty_penalty`
- `demand_exposure_norm`
- `lead_time_risk_norm`
- `cover_risk_norm`
- `volume_exposure_norm`
- `criticality_norm`
- `mono_source_risk`
- `lead_mean_days`
- impacts conditionnels backlog/fill loss

Variables temporelles synthetiques:

- `demand_pressure_norm`
- `recent_delay_ratio_4w`
- `recent_short_ship_rate_8w`
- `recent_otif_4w`
- `quality_issue_rate`, puis `recent_quality_incidents_12w`
- `open_po_count`
- `order_count_8w`
- `supplier_latent_shock`
- `season_sin`, `season_cos`

Logit synthetique du label incident:

```text
logit =
  -4.8
  + 1.8 * structural_proxy_score
  + 1.2 * impact_proxy_score
  + 1.0 * recent_short_ship_rate_8w
  + 0.8 * recent_delay_ratio_4w
  + 0.5 * demand_pressure_norm
  + 0.4 * uncertainty_penalty
  + 0.12 * recent_quality_incidents_12w
  + 0.35 * max(0, supplier_bias)
  + 0.45 * max(0, supplier_latent_shock)
  + 0.4 * recent_incident_memory
```

Puis:

```text
true_incident_probability_30d = clip(sigmoid(logit), 0.01, 0.97)
incident_next_30d = Bernoulli(true_incident_probability_30d)
```

Le label severe est tire si `incident_next_30d = 1`, avec une probabilite augmentee par impact, incertitude et choc latent.

Attention fuite de donnees:

- `true_incident_probability_30d` ne doit pas etre utilise comme feature;
- `incident_next_30d` et `severe_incident_next_30d` ne doivent etre utilises que comme targets;
- `supplier_latent_shock` est synthetique et ne sera pas directement disponible dans une vraie implementation.

## Modele Prediction POC

Modele:

- `Pipeline(StandardScaler(), LogisticRegression())`
- `LogisticRegression(max_iter=3000, class_weight="balanced", random_state=42)`
- calibration des probabilites par `IsotonicRegression(out_of_bounds="clip")`
- entrainement sur semaines 1-72
- calibration sur semaines 73-88
- evaluation sur semaines 89-104

Features utilisees:

```text
supplier_count_for_item
structural_proxy_score
impact_proxy_score
criticality_norm
demand_exposure_norm
volume_exposure_norm
cover_risk_norm
lead_time_risk_norm
mono_source_risk
uncertainty_penalty
lead_mean_days
recent_otif_4w
recent_delay_ratio_4w
recent_short_ship_rate_8w
recent_quality_incidents_12w
open_po_count
order_count_8w
demand_pressure_norm
season_sin
season_cos
```

Metriques actuelles sur test:

| metrique | valeur |
| --- | ---: |
| `test_incident_rate` | 0.122917 |
| `roc_auc` | 0.691614 |
| `pr_auc` | 0.218471 |
| `brier_score` | 0.106500 |
| `top_decile_precision` | 0.223684 |
| `top_decile_recall` | 0.576271 |

Interpretation rapide:

- ROC AUC correct pour un POC synthetique, mais pas suffisant pour production;
- PR AUC faible/moderee car le taux d'incident est bas;
- top decile recall eleve: le top 10% capture une partie importante des incidents;
- top decile precision encore faible: beaucoup de faux positifs dans le top risque;
- calibration a verifier visuellement via `calibration_curve.png`.

## Coefficients du modele

Top coefficients absolus:

| feature | coefficient | lecture |
| --- | ---: | --- |
| `supplier_count_for_item` | -1.072005 | plus de fournisseurs associes reduit le risque estime |
| `mono_source_risk` | -0.810665 | signe negatif surprenant vu le generateur, a investiguer |
| `cover_risk_norm` | 0.469422 | couverture faible augmente le risque |
| `uncertainty_penalty` | 0.340101 | incertitude augmente le risque |
| `structural_proxy_score` | -0.292500 | signe negatif surprenant vu le generateur, possible colinearite/calibration/split |
| `lead_time_risk_norm` | 0.281787 | lead time risque augmente le risque |
| `lead_mean_days` | 0.281778 | lead moyen long augmente le risque |
| `volume_exposure_norm` | 0.279555 | exposition volume augmente le risque |
| `impact_proxy_score` | 0.262664 | impact eleve augmente le risque |
| `recent_otif_4w` | -0.219202 | meilleur OTIF reduit le risque |
| `criticality_norm` | 0.205675 | criticite augmente le risque |
| `recent_quality_incidents_12w` | 0.116277 | incidents qualite recents augmentent le risque |

Points a challenger:

- `mono_source_risk` et `structural_proxy_score` sortent avec un signe negatif alors que le generateur synthetique les pousse positivement. Cause probable: colinearites fortes, faible taille de panel, split temporel, calibration isotonic ou distribution du dernier snapshot.
- `demand_exposure_norm` a un coefficient nul dans la sortie actuelle, probablement car la variable est redondante ou sans variance utile apres standardisation/split.

## Top Prediction POC par couple

Les probabilites calibrees du dernier snapshot sont toutes a `0.071130` dans la sortie actuelle. Le classement est donc surtout porte par l'impact conditionnel backlog.

| fournisseur | site | article | p30 | impact backlog si incident | risque backlog attendu | priorite |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| SDC-1450 | M-1430 | item:773474 | 0.071130 | 26.091750 | 1.855899 | 0.510357 |
| SDC-1450 | M-1810 | item:007923 | 0.071130 | 24.745700 | 1.760154 | 0.485680 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.071130 | 24.374175 | 1.733728 | 0.478868 |
| SDC-1450 | M-1810 | item:693055 | 0.071130 | 16.640780 | 1.183654 | 0.337089 |
| SDC-VD0505677A | M-1810 | item:099439 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD0514881A | M-1810 | item:016332 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD0519670A | M-1810 | item:029313 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD0951020A | M-1810 | item:001757 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD1096202A | M-1810 | item:039668 | 0.071130 | 12.500000 | 0.889121 | 0.261175 |
| SDC-VD0520115A | M-1430 | item:708073 | 0.071130 | 11.335125 | 0.806264 | 0.239819 |
| SDC-VD0520132A | M-1430 | item:038005 | 0.071130 | 11.335125 | 0.806264 | 0.239819 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.071130 | 11.335125 | 0.806264 | 0.239819 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.071130 | 9.552725 | 0.679483 | 0.207142 |
| SDC-VD0525412A | M-1430 | item:333362 | 0.071130 | 2.614840 | 0.185993 | 0.079947 |

## Top Prediction POC par fournisseur

| fournisseur | nb couples | p moyenne | p max | somme risque backlog | articles |
| --- | ---: | ---: | ---: | ---: | --- |
| SDC-1450 | 3 | 0.071130 | 0.071130 | 4.799707 | item:007923, item:693055, item:773474 |
| SDC-VD0508918A | 1 | 0.071130 | 0.071130 | 1.733728 | item:730384 |
| SDC-VD0520132A | 2 | 0.071130 | 0.071130 | 1.695385 | item:038005, item:049371 |
| SDC-VD0519670A | 2 | 0.071130 | 0.071130 | 0.889121 | item:001848, item:029313 |
| SDC-VD0514881A | 1 | 0.071130 | 0.071130 | 0.889121 | item:016332 |
| SDC-VD1096202A | 1 | 0.071130 | 0.071130 | 0.889121 | item:039668 |
| SDC-VD0505677A | 1 | 0.071130 | 0.071130 | 0.889121 | item:099439 |
| SDC-VD0989480A | 1 | 0.071130 | 0.071130 | 0.889121 | item:426331 |
| SDC-VD0951020A | 2 | 0.071130 | 0.071130 | 0.889121 | item:001757, item:001848 |
| SDC-VD1095770A | 1 | 0.071130 | 0.071130 | 0.806264 | item:734545 |

## Supplier Risk KPI - inputs

Run analyse dans le resume actuel:

`etudecas/simulation/result/mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test`

Fichier sensibilite:

`etudecas/simulation/sensibility/active_supplier_parameter_result/supplier_parameter_recommendations.csv`

Compteurs:

| indicateur | valeur |
| --- | ---: |
| semaines | 272 |
| fournisseurs | 30 |
| couples fournisseur-article-site | 40 |
| lignes panel | 10880 |
| lignes fournisseurs | 30 |
| lignes MRP order | 26760 |
| lignes retard MRP observables | 0 |
| lignes short MRP observables | 0 |

Normalisateurs:

| normalisateur | valeur |
| --- | ---: |
| `lead_q90_max` | 244.2 |
| `weekly_qty_q95_log_max` | 13.768470 |
| `sensitivity_delta_log_max` | 13.727637 |
| `sensitivity_fill_drop_max` | 0.01 |

## Colonnes Supplier Risk KPI

### Identifiants et flux

| colonne | interpretation |
| --- | --- |
| `week_index` | semaine du panel |
| `supplier_id`, `supplier_name` | fournisseur |
| `dst_node_id` | site destinataire |
| `item_id` | article |
| `shipped_qty`, `pulled_qty`, `shipment_count` | quantites expediees/tirees et nombre d'expeditions |
| `mrp_order_count`, `mrp_release_qty`, `mrp_planned_receipt_qty` | signaux MRP |

### Lead time, capacite, stock

| colonne | interpretation |
| --- | --- |
| `lead_days_avg_week` | lead moyen observe sur la semaine |
| `lead_days_q50`, `lead_days_q90`, `lead_days_q95` | quantiles lead historiques |
| `lead_interval_width_days` | largeur d'intervalle lead |
| `reliability_avg_week` | fiabilite moyenne |
| `capacity_qty_week`, `capacity_used_qty_week` | capacite et utilisation |
| `capacity_utilization_avg_week`, `capacity_utilization_max_week` | utilisation capacite |
| `stock_end_of_week`, `stock_min_of_week` | stock fournisseur fin/min semaine |
| `stock_coverage_days` | couverture stock estimee en jours |

### Pressions et dynamique

| colonne | interpretation |
| --- | --- |
| `trailing_4w_shipped_qty` | expeditions cumulees 4 semaines |
| `trailing_12w_avg_shipped_qty` | moyenne 12 semaines |
| `flow_velocity_4w` | acceleration/ralentissement flux 4 semaines |
| `flow_cv_12w` | volatilite relative 12 semaines |
| `criticality_score`, `local_criticality_score` | criticite systeme et locale |
| `mono_source_score` | risque mono-source |
| `stock_pressure` | pression manque de couverture stock |
| `capacity_pressure` | pression capacite |
| `lead_time_pressure` | pression lead time |
| `flow_exposure_pressure` | exposition volume |
| `flow_volatility_pressure` | volatilite flux |
| `dynamic_pressure` | pression dynamique combinee |

### Scores risque et decision

| colonne | interpretation |
| --- | --- |
| `performance_distance_score` | distance a la performance normale |
| `performance_score_current` | score de performance courant, inverse de la distance |
| `change_point_score`, `change_point_flag` | rupture de regime |
| `early_warning_score`, `early_warning_flag` | signaux faibles |
| `resilience_score` | capacite absorption/recuperation |
| `performance_drop_proxy` | drop de performance proxy |
| `time_to_recover_weeks_proxy` | temps de recuperation proxy |
| `sensitivity_*` | resultats de sensibilite fournisseur |
| `lead_uncertainty_pressure` | incertitude lead |
| `data_quality_*` | qualite de donnees |
| `uncertainty_pressure` | pression d'incertitude |
| `risk_signal` | signal de risque combine |
| `risk_probability_proxy_4w` | probabilite proxy d'incident 4 semaines |
| `risk_probability_low_proxy_4w` | borne basse probabilite proxy |
| `risk_probability_high_proxy_4w` | borne haute probabilite proxy |
| `action_priority_score` | score priorite action |
| `expected_exposure_qty_4w_proxy` | exposition attendue 4 semaines |
| `cvar_exposure_qty_4w_proxy` | exposition prudente type CVaR proxy |
| `action_level` | niveau action: green, amber, red, critical |
| `decision_zone` | zone robuste: vert, jaune, orange, rouge |
| `recommended_action` | action liee au niveau |
| `robust_decision` | decision robuste liee a la zone |

## Formules KPI principales

Data quality:

```text
data_quality_score =
  0.20 * data_quality_lead_score
  + 0.20 * data_quality_capacity_score
  + 0.20 * data_quality_stock_score
  + 0.20 * data_quality_criticality_score
  + 0.20 * data_quality_active_score
```

Incertitude:

```text
lead_uncertainty_pressure = clamp(lead_interval_width_days / max(lead_days_q50, 1))
uncertainty_pressure = clamp(0.60 * (1 - data_quality_score) + 0.40 * lead_uncertainty_pressure)
```

Dynamique:

```text
dynamic_pressure =
  0.35 * stock_trend_pressure
  + 0.25 * capacity_trend_pressure
  + 0.20 * flow_spike_pressure
  + 0.20 * flow_volatility_pressure
```

Performance:

```text
performance_distance_score =
  0.25 * lead_time_pressure
  + 0.20 * capacity_pressure
  + 0.20 * stock_pressure
  + 0.15 * flow_volatility_pressure
  + 0.10 * dynamic_pressure
  + 0.10 * (1 - reliability_avg_week)

performance_score_current = 1 - performance_distance_score
```

Change point:

```text
change_point_score =
  0.45 * abs(flow_velocity_4w) / max(stdev_12w, qty_q95 * 0.10, 1)
  + 0.25 * capacity_trend_pressure
  + 0.20 * stock_trend_pressure
  + 0.10 * flow_spike_pressure

change_point_flag = change_point_score >= 0.65
```

Early warning:

```text
early_warning_score =
  0.30 * flow_volatility_pressure
  + 0.25 * stock_trend_pressure
  + 0.20 * capacity_trend_pressure
  + 0.15 * lead_uncertainty_pressure
  + 0.10 * uncertainty_pressure

early_warning_flag = early_warning_score >= 0.45
```

Resilience:

```text
resilience_score =
  0.25 * stock_absorption_score
  + 0.20 * capacity_headroom_score
  + 0.20 * recovery_slope_score
  + 0.15 * source_flexibility_score
  + 0.10 * sensitivity_resilience_score
  + 0.10 * data_quality_score
```

Signal de risque:

```text
risk_signal =
  0.20 * criticality_score
  + 0.14 * mono_source_score
  + 0.15 * stock_pressure
  + 0.11 * capacity_pressure
  + 0.10 * lead_time_pressure
  + 0.08 * flow_exposure_pressure
  + 0.08 * sensitivity_pressure
  + 0.08 * dynamic_pressure
  + 0.06 * uncertainty_pressure
```

Probabilite proxy:

```text
risk_probability_proxy_4w = clamp(sigmoid(-3.0 + 5.0 * risk_signal), 0, 0.95)
risk_interval_half_width = 0.04 + 0.26 * uncertainty_pressure
risk_probability_low_proxy_4w = clamp(risk_probability_proxy_4w - risk_interval_half_width)
risk_probability_high_proxy_4w = clamp(risk_probability_proxy_4w + risk_interval_half_width)
```

Priorite:

```text
action_priority_score =
  risk_probability_proxy_4w
  * (0.35 + 0.65 * max(criticality_score, local_criticality_score))
  * (0.75 + 0.25 * sensitivity_pressure)
```

Exposition:

```text
exposure_qty_4w = max(
  4 * trailing_12w_avg_shipped_qty,
  weekly_shipped_qty_q95,
  4 * weekly_mrp_release_qty_mean
)

expected_exposure_qty_4w_proxy =
  risk_probability_proxy_4w
  * exposure_qty_4w
  * (0.5 + 0.5 * criticality_score)
```

Temps de recuperation:

```text
time_to_recover_weeks_proxy = 1 + 8 * (1 - resilience_score) + 4 * risk_signal
```

## Regles de decision KPI

`action_level`:

| niveau | condition |
| --- | --- |
| `critical` | `action_priority_score >= 0.55` ou `risk_probability_proxy_4w >= 0.70` |
| `red` | `action_priority_score >= 0.35` ou `risk_probability_proxy_4w >= 0.50` |
| `amber` | `action_priority_score >= 0.18` ou `risk_probability_proxy_4w >= 0.30` ou `uncertainty_pressure >= 0.70` |
| `green` | sinon |

`decision_zone`:

| zone | condition |
| --- | --- |
| `rouge` | `priority >= 0.35` ou `probability_high >= 0.60` ou `probability >= 0.35 and resilience < 0.40 and criticality >= 0.45` |
| `orange` | `priority >= 0.18` ou `probability_high >= 0.45` ou `uncertainty_pressure >= 0.75` |
| `jaune` | `probability >= 0.18` ou `early_warning_flag` ou `change_point_flag` ou `uncertainty_pressure >= 0.55` |
| `vert` | sinon |

Actions:

| niveau/zone | action |
| --- | --- |
| `green` | `standard_monitoring` |
| `amber` | `weekly_watch_confirm_capacity_and_open_orders` |
| `red` | `confirm_supplier_commitment_and_recompute_safety_stock` |
| `critical` | `crisis_review_activate_backup_or_buffer` |
| `vert` | `routine_monitoring` |
| `jaune` | `watch_collect_data_and_confirm_supplier_status` |
| `orange` | `preventive_action_buffer_capacity_or_supplier_review` |
| `rouge` | `immediate_robust_decision_dual_source_buffer_or_escalation` |

## Repartition KPI actuelle

Derniere photo:

| type | vert/green | jaune | orange | rouge/red | critical |
| --- | ---: | ---: | ---: | ---: | ---: |
| `action_level` | 40 | 0 | 0 | 0 | 0 |
| `decision_zone` | 34 | 6 | 0 | 0 | 0 |

Toutes semaines:

| champ | repartition |
| --- | --- |
| `action_level` | green: 10849, amber: 31 |
| `decision_zone` | vert: 8857, jaune: 2008, orange: 15 |

## Top KPI par couple

| fournisseur | site | article | p4w proxy | p4w high | priorite | resilience | lead q90 | zone | decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| SDC-VD0525412A | M-1430 | item:333362 | 0.216066 | 0.259532 | 0.120382 | 0.765343 | 62.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0914360C | M-1810 | item:338929 | 0.191703 | 0.236655 | 0.112582 | 0.850000 | 44.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0993480A | M-1430 | item:344135 | 0.196542 | 0.242485 | 0.109724 | 0.789666 | 37.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0901566A | M-1810 | item:338928 | 0.186087 | 0.227572 | 0.090644 | 0.822916 | 71.0 | jaune | watch_collect_data_and_confirm_supplier_status |
| SDC-VD0508918A | M-1430 | item:730384 | 0.153760 | 0.220337 | 0.082801 | 0.775283 | 57.0 | vert | routine_monitoring |
| SDC-VD0520132A | M-1430 | item:038005 | 0.161496 | 0.235093 | 0.079299 | 0.833846 | 174.0 | vert | routine_monitoring |
| SDC-VD0520132A | M-1810 | item:049371 | 0.153069 | 0.219469 | 0.075162 | 0.833077 | 147.0 | vert | routine_monitoring |
| SDC-VD0520115A | M-1430 | item:708073 | 0.142910 | 0.205961 | 0.072360 | 0.775885 | 28.0 | vert | routine_monitoring |
| SDC-VD1095770A | M-1430 | item:734545 | 0.133803 | 0.189403 | 0.065188 | 0.791407 | 21.0 | vert | routine_monitoring |
| SDC-VD0914690A | M-1430 | item:042342 | 0.125349 | 0.204911 | 0.062090 | 0.833846 | 23.9 | vert | routine_monitoring |
| SDC-VD0951020A | M-1810 | item:001757 | 0.103467 | 0.147181 | 0.056051 | 0.938679 | 87.0 | vert | routine_monitoring |
| SDC-VD0951020A | M-1810 | item:007923 | 0.093802 | 0.168469 | 0.050816 | 0.898679 | 4.0 | vert | routine_monitoring |

## Top KPI par fournisseur

| fournisseur | nb couples | max p4w | max p4w high | min resilience | max priorite | pire zone | top article |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| SDC-VD0525412A | 1 | 0.216066 | 0.259532 | 0.765343 | 0.120382 | jaune | item:333362 |
| SDC-VD0914360C | 1 | 0.191703 | 0.236655 | 0.850000 | 0.112582 | jaune | item:338929 |
| SDC-VD0993480A | 1 | 0.196542 | 0.242485 | 0.789666 | 0.109724 | jaune | item:344135 |
| SDC-VD0901566A | 1 | 0.186087 | 0.227572 | 0.822916 | 0.090644 | jaune | item:338928 |
| SDC-VD0508918A | 1 | 0.153760 | 0.220337 | 0.775283 | 0.082801 | vert | item:730384 |
| SDC-VD0520132A | 2 | 0.161496 | 0.235093 | 0.833077 | 0.079299 | vert | item:038005 |
| SDC-VD0520115A | 1 | 0.142910 | 0.205961 | 0.775885 | 0.072360 | vert | item:708073 |
| SDC-VD1095770A | 1 | 0.133803 | 0.189403 | 0.791407 | 0.065188 | vert | item:734545 |
| SDC-VD0914690A | 1 | 0.125349 | 0.204911 | 0.833846 | 0.062090 | vert | item:042342 |
| SDC-VD0951020A | 4 | 0.103467 | 0.209444 | 0.898679 | 0.056051 | vert | item:001757 |
| SDC-VD0989480A | 1 | 0.117465 | 0.188894 | 0.834615 | 0.050165 | vert | item:426331 |
| SDC-VD0505677A | 1 | 0.116227 | 0.181118 | 0.834615 | 0.048058 | vert | item:099439 |

## Comparaison Prediction POC vs Supplier Risk KPI

| aspect | Prediction POC | Supplier Risk KPI |
| --- | --- | --- |
| horizon | 30 jours | 4 semaines |
| probabilite | supervisee mais sur labels synthetiques | proxy explicite non supervise |
| granularite | fournisseur-article-site-semaine | fournisseur-article-site-semaine |
| input | historique synthetique + impacts simulation | sorties simulation reelles + sensibilite |
| output risque | proba * backlog/fill loss conditionnel | proba proxy * exposition/criticite |
| force | architecture ML complete avec calibration | ancrage dans les sorties simulation et donnees operationnelles |
| faiblesse | labels non reels, petite taille, proba finale peu discriminante | pas de label incident reel, formule heuristique |
| usage actuel | tester une architecture IA/ML | prioriser monitoring et alimenter carte |

## Donnees a fournir a une IA pour tester

Minimum utile:

1. `etudecas/prototypes/prediction/data/synthetic_supplier_item_history.csv`
2. `etudecas/prototypes/prediction/result/prediction_test_scored_rows.csv`
3. `etudecas/prototypes/prediction/result/predicted_supplier_item_risk.csv`
4. `etudecas/prototypes/prediction/result/model_feature_coefficients.csv`
5. `etudecas/risk/supplier_criticality/result/data/supplier_item_week_panel.csv`
6. `etudecas/risk/supplier_criticality/result/data/supplier_item_risk_kpi.csv`
7. `etudecas/risk/supplier_criticality/result/data/supplier_risk_kpi.csv`
8. `etudecas/risk/supplier_criticality/result/summaries/supplier_risk_kpi_summary.json`
9. `etudecas/prototypes/prediction/run_prediction_poc.py`
10. `etudecas/risk/supplier_criticality/build_supplier_criticality.py`

Pour une IA externe, donner aussi ce fichier Markdown comme contexte principal.

## Tests IA recommandes

### Test 1 - Audit leakage

Demander a l'IA de verifier que les features n'utilisent pas:

- `true_incident_probability_30d`;
- `incident_next_30d`;
- `severe_incident_next_30d`;
- des colonnes calculees apres l'evenement;
- des aggregats qui regardent le futur.

### Test 2 - Reproduction du modele

Demander a l'IA de:

- charger `synthetic_supplier_item_history.csv`;
- refaire le split temporel;
- entrainer une regression logistique calibree;
- verifier que les metriques sont proches:
  - ROC AUC environ 0.692;
  - PR AUC environ 0.218;
  - Brier environ 0.1065;
  - precision top decile environ 0.224;
  - recall top decile environ 0.576.

### Test 3 - Challenger la calibration

Questions utiles:

- pourquoi toutes les probabilites finales du dernier snapshot sont-elles identiques a `0.071130`?
- est-ce lie a l'isotonic regression, a la distribution du dernier snapshot ou a un manque de variance?
- comparer calibration isotonic vs Platt scaling;
- analyser les probabilites raw vs calibrees;
- tracer reliability curve par decile temporel.

### Test 4 - Challenger les signes des coefficients

Questions utiles:

- pourquoi `mono_source_risk` est negatif?
- pourquoi `structural_proxy_score` est negatif?
- y a-t-il colinearite entre `supplier_count_for_item`, `mono_source_risk`, `structural_proxy_score`, `cover_risk_norm` et `impact_proxy_score`?
- refaire avec regularisation differente;
- tester permutation importance;
- tester SHAP ou coefficients bootstrap.

### Test 5 - Remplacer le synthetique par KPI panel

Demander a l'IA de proposer comment convertir `supplier_item_week_panel.csv` en dataset supervise:

- target possible: incident/alerte dans les 4 prochaines semaines;
- target alternative: chute de service, rupture stock, backlog, retard MRP, hausse de `decision_zone`;
- features: toutes les pressions a la semaine `t`;
- label: evenement observe entre `t+1` et `t+4`;
- split temporel strict.

### Test 6 - Modele hybride

Demander a l'IA de combiner:

- probabilite supervisee si labels disponibles;
- `risk_probability_proxy_4w` comme prior ou feature;
- `uncertainty_pressure` pour largeur d'intervalle;
- `resilience_score` pour priorisation decisionnelle;
- `expected_exposure_qty_4w_proxy` comme impact.

Formule candidate:

```text
expected_risk_4w =
  calibrated_probability_4w
  * expected_exposure_qty_4w_proxy
  * (1 + uncertainty_pressure)
  * (1 + max(0, 0.5 - resilience_score))
```

### Test 7 - Backtesting decisionnel

Demander a l'IA de mesurer:

- precision/recall par zone `vert/jaune/orange/rouge`;
- part des incidents captee par les zones non vertes;
- cout des faux positifs;
- cout des faux negatifs;
- stabilite des decisions d'une semaine a l'autre;
- delai moyen entre early warning et incident.

## Prompts prets a copier

### Prompt audit

```text
Tu es data scientist supply chain. Analyse ce POC de prediction de risque fournisseur.
Objectif: verifier leakage, coherence des features, calibration probabiliste, robustesse temporelle et pertinence metier.
Utilise les fichiers:
- etudecas/prototypes/prediction/data/synthetic_supplier_item_history.csv
- etudecas/prototypes/prediction/result/prediction_test_scored_rows.csv
- etudecas/prototypes/prediction/result/model_feature_coefficients.csv
- etudecas/risk/supplier_criticality/result/data/supplier_item_week_panel.csv
- etudecas/risk/supplier_criticality/result/data/supplier_item_risk_kpi.csv

Ne considere pas les labels synthetiques comme une verite industrielle.
Produis:
1. les risques de leakage;
2. les incoherences statistiques;
3. les tests de validation a lancer;
4. une proposition de dataset supervise industriel;
5. une proposition de score final probabilite x impact x incertitude x resilience.
```

### Prompt amelioration modele

```text
Tu dois ameliorer le modele de prediction risque fournisseur.
Contraintes:
- split temporel obligatoire;
- pas d'utilisation de true_incident_probability_30d comme feature;
- calibration probabiliste obligatoire;
- sortie exploitable par couple fournisseur-article-site et par fournisseur;
- horizon cible 30 jours ou 4 semaines.

Compare au moins:
- LogisticRegression calibree;
- HistGradientBoosting ou RandomForest;
- modele avec risk_probability_proxy_4w comme feature;
- modele separant probabilite et impact.

Evalue:
- ROC AUC;
- PR AUC;
- Brier score;
- calibration curve;
- precision/recall top decile;
- stabilite des rankings.
```

### Prompt industrialisation

```text
Propose un plan d'industrialisation de la prediction risque fournisseur.
Entrees disponibles:
- OTIF fournisseur;
- retards commandes;
- quantites short ship;
- stocks fournisseur et usine;
- capacites;
- MRP release/planned receipts;
- criticite article;
- mono-source;
- resultats de sensibilite simulation;
- sorties supplier_criticality.

Objectif:
- construire une probabilite calibree d'incident a 4 semaines;
- calculer un risque attendu en quantite/backlog/service;
- expliquer les drivers;
- generer une decision robuste vert/jaune/orange/rouge.

Precise:
- schema de donnees;
- target;
- features;
- split temporel;
- monitoring;
- seuils decisionnels;
- limites et controles humains.
```

## Points de vigilance

- Les donnees synthetiques du POC ne prouvent pas une performance industrielle.
- Une probabilite identique sur tous les derniers couples indique un probleme de discrimination ou de calibration pour le scoring courant.
- Les proxys KPI sont utiles pour prioriser, mais ne doivent pas etre presentes comme probabilites observees.
- Les seuils de decision doivent etre calibres avec cout metier: cout d'une alerte inutile vs cout d'une rupture non anticipee.
- Les features tres correlees doivent etre auditees avant interpretation des coefficients.
- Une validation aleatoire classique serait trompeuse; il faut conserver un split temporel.
- Les decisions automatiques doivent rester accompagnees d'un controle humain fournisseur/achat/supply.

## Prochaine etape recommandee

Construire un dataset supervise a partir du panel KPI:

1. garder une ligne par `supplier_id`, `dst_node_id`, `item_id`, `week_index`;
2. utiliser uniquement les features connues a la fin de la semaine `t`;
3. definir une target sur `t+1` a `t+4`, par exemple:
   - rupture stock;
   - baisse de service;
   - retard MRP observable;
   - passage en zone orange/rouge;
   - hausse brutale de backlog ou exposition;
4. entrainer un modele probabiliste calibre;
5. comparer le modele au proxy existant;
6. remplacer progressivement `risk_probability_proxy_4w` par `calibrated_incident_probability_4w` quand les labels sont fiables.

