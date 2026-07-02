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
- test_incident_rate: **0.122917**
- roc_auc: **0.691614**
- pr_auc: **0.218471**
- brier_score: **0.106500**
- top_decile_precision: **0.223684**
- top_decile_recall: **0.576271**

## Top couples predits
| supplier_id | factory_id | item_id | predicted_incident_probability_30d | conditional_expected_backlog_if_incident | predicted_expected_backlog_risk_30d | conditional_expected_fill_loss_if_incident | predicted_expected_fill_loss_risk_30d |
|---|---|---|---|---|---|---|---|
| SDC-1450 | M-1430 | item:773474 | 0.071130 | 26.091750 | 1.855899 | 0.017541 | 0.001248 |
| SDC-1450 | M-1810 | item:007923 | 0.071130 | 24.745700 | 1.760154 | 0.016636 | 0.001183 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.071130 | 24.374175 | 1.733728 | 0.016387 | 0.001166 |
| SDC-1450 | M-1810 | item:693055 | 0.071130 | 16.640780 | 1.183654 | 0.011187 | 0.000796 |
| SDC-VD0505677A | M-1810 | item:099439 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD0514881A | M-1810 | item:016332 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD0519670A | M-1810 | item:029313 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD0951020A | M-1810 | item:001757 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD1096202A | M-1810 | item:039668 | 0.071130 | 12.500000 | 0.889121 | 0.008404 | 0.000598 |
| SDC-VD0520115A | M-1430 | item:708073 | 0.071130 | 11.335125 | 0.806264 | 0.007621 | 0.000542 |

## Top fournisseurs predits
| supplier_id | supplier_pair_count | mean_predicted_incident_probability_30d | max_predicted_incident_probability_30d | predicted_expected_backlog_risk_30d_sum | item_id |
|---|---|---|---|---|---|
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

## Variables dominantes du modele
| feature | coefficient | abs_coefficient |
|---|---|---|
| supplier_count_for_item | -1.072005 | 1.072005 |
| mono_source_risk | -0.810665 | 0.810665 |
| cover_risk_norm | 0.469422 | 0.469422 |
| uncertainty_penalty | 0.340101 | 0.340101 |
| structural_proxy_score | -0.292500 | 0.292500 |
| lead_time_risk_norm | 0.281787 | 0.281787 |
| lead_mean_days | 0.281778 | 0.281778 |
| volume_exposure_norm | 0.279555 | 0.279555 |
| impact_proxy_score | 0.262664 | 0.262664 |
| recent_otif_4w | -0.219202 | 0.219202 |
| criticality_norm | 0.205675 | 0.205675 |
| recent_quality_incidents_12w | 0.116277 | 0.116277 |

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
