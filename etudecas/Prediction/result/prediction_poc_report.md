# Prediction POC de risque fournisseur-matiere

## Statut
Ce dossier contient un **proof of concept** complet.

Important:
- les **labels** et une partie des variables temporelles sont **synthetiques**
- les **impacts supply** reuses viennent de l'etude de simulation existante
- donc ce POC montre **comment** faire de la prediction, pas une calibration industrielle finale

## Pipeline implemente
1. Chargement des couples fournisseur-matiere depuis l'etude proxy existante.
2. Generation d'un historique synthetique hebdomadaire sur **104 semaines** par couple.
3. Creation d'un label `incident_next_30d`.
4. Split temporel:
   - train: semaines 1-72
   - calibration: semaines 73-88
   - test: semaines 89-104
5. Entrainement d'un modele probabiliste:
   - `LogisticRegression`
   - `StandardScaler`
   - calibration isotonic sur jeu intermediaire
6. Calcul du risque final:
   - `probabilite predite d'incident`
   - x `impact conditionnel si incident`

## Metriques de validation
- train_rows: **2160**
- calibration_rows: **480**
- test_rows: **480**
- test_incident_rate: **0.100000**
- roc_auc: **0.695095**
- pr_auc: **0.225218**
- brier_score: **0.085046**
- top_decile_precision: **0.307692**
- top_decile_recall: **0.333333**

## Top couples predits
| supplier_id | factory_id | item_id | predicted_incident_probability_30d | conditional_expected_backlog_if_incident | predicted_expected_backlog_risk_30d | conditional_expected_fill_loss_if_incident | predicted_expected_fill_loss_risk_30d |
|---|---|---|---|---|---|---|---|
| SDC-1450 | M-1810 | item:693710 | 0.333333 | 28.942725 | 9.647575 | 0.019295 | 0.006432 |
| SDC-VD0914360C | M-1810 | item:338929 | 0.222222 | 18.809790 | 4.179953 | 0.012540 | 0.002787 |
| SDC-VD0901566A | M-1810 | item:338928 | 0.166667 | 18.809790 | 3.134965 | 0.012540 | 0.002090 |
| SDC-1450 | M-1430 | item:773474 | 0.166667 | 12.274400 | 2.045733 | 0.008183 | 0.001364 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.052632 | 9.287925 | 0.488838 | 0.006192 | 0.000326 |
| SDC-1450 | M-1810 | item:693055 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0505677A | M-1810 | item:099439 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0518684A | M-1810 | item:001893 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0520115A | M-1430 | item:708073 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0520132A | M-1430 | item:038005 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.222222 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

## Top fournisseurs predits
| supplier_id | supplier_pair_count | mean_predicted_incident_probability_30d | max_predicted_incident_probability_30d | predicted_expected_backlog_risk_30d_sum | item_id |
|---|---|---|---|---|---|
| SDC-1450 | 3 | 0.240741 | 0.333333 | 11.693308 | item:693055, item:693710, item:773474 |
| SDC-VD0914360C | 1 | 0.222222 | 0.222222 | 4.179953 | item:338929 |
| SDC-VD0901566A | 1 | 0.166667 | 0.166667 | 3.134965 | item:338928 |
| SDC-VD0914690A | 1 | 0.052632 | 0.052632 | 0.488838 | item:042342 |
| SDC-VD0508918A | 1 | 0.222222 | 0.222222 | 0.000000 | item:730384 |
| SDC-VD0500655A | 1 | 0.166667 | 0.166667 | 0.000000 | item:002612 |
| SDC-VD0505677A | 1 | 0.222222 | 0.222222 | 0.000000 | item:099439 |
| SDC-VD0519670A | 2 | 0.166667 | 0.166667 | 0.000000 | item:001848, item:029313 |
| SDC-VD0518684A | 1 | 0.222222 | 0.222222 | 0.000000 | item:001893 |
| SDC-VD0514881A | 1 | 0.166667 | 0.166667 | 0.000000 | item:016332 |

## Variables dominantes du modele
| feature | coefficient | abs_coefficient |
|---|---|---|
| supplier_count_for_item | -0.836954 | 0.836954 |
| mono_source_risk | -0.534378 | 0.534378 |
| impact_proxy_score | 0.385209 | 0.385209 |
| season_sin | 0.301000 | 0.301000 |
| recent_quality_incidents_12w | 0.288711 | 0.288711 |
| structural_proxy_score | -0.281571 | 0.281571 |
| demand_pressure_norm | -0.277348 | 0.277348 |
| volume_exposure_norm | 0.236883 | 0.236883 |
| recent_short_ship_rate_8w | 0.207046 | 0.207046 |
| criticality_norm | 0.199565 | 0.199565 |
| order_count_8w | -0.161601 | 0.161601 |
| open_po_count | 0.152772 | 0.152772 |

## Fichiers utiles
- `data/synthetic_supplier_item_history.csv`
- `result/predicted_supplier_item_risk.csv`
- `result/predicted_supplier_risk.csv`
- `result/evaluation_metrics.json`
- `result/prediction_poc_report.md`
- `result/calibration_curve.png`
- `result/top_pair_predicted_risk.png`
- `result/predicted_probability_vs_conditional_impact.png`
- `result/top_supplier_predicted_risk.png`
- `result/model_feature_coefficients.png`

## Lecture correcte
- Ce POC valide l'architecture:
  - **proba predite**
  - **impact supply**
  - **risque attendu**
- Pour passer en vrai industriel, il suffit de remplacer:
  - l'historique synthetique
  - par des donnees reelles ERP / OTIF / qualite / retard
