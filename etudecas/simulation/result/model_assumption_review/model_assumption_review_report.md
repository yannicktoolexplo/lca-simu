# Revue approfondie des hypotheses et de la robustesse du modele supply

## Perimetre
- Base de travail: input prepare avec hypothese conservee `item:007923 -> SDC-1450 / Gaillac`
- Objectif: distinguer ce qui est robuste, tester les hypotheses de completion, construire un mode strict, comparer des politiques de pilotage, decomposer les causes du backlog, cartographier la fragilite matiere, tracer des frontieres cout/service et tester des ruptures ciblees.

## 1) Baseline conservee
- Fill rate: **0.787666**
- Ending backlog: **315.8476**
- Total cost: **1273360.3167**
- External procured ordered qty: **42871.1216**
- Opening stock bootstrap qty: **1060029.4897**

## 2) Ce qui est robuste vs ce qui depend des hypotheses
| conclusion | confidence | hypothesis_dependency | observed_vs_assumed | evidence |
|---|---|---|---|---|
| Mono-sourcing de item:042342 sur M-1430 | high | low | Observed directly in Data_poc.xlsx relations and criticality table; no inferred supplier. | Supplier count = 1, highest criticality score. |
| Criticité élevée de item:007923 sur M-1810 | medium | high | Observed in BOM, but supplier mapping is assumed to SDC-1450/Gaillac. | No-supplier mapping fill 0.527; 5-day outage fill 0.761. |
| M-1810 agit comme goulot service/backlog | high | medium | Observed in sensitivity, policy tests and targeted capacity drop. | M-1810 capacity-down case fill 0.653. |
| M-1430 est le principal driver de coût | high | medium | Observed in OAT sensitivity on cost; absolute level still depends on cost assumptions. | capacity_node_scale::M-1430 remains top cost driver. |
| La baseline à 78.8% repose fortement sur stock bootstrap + appro externe | high | high | Observed via strict mode and external-off cases; both are model assumptions, not source data. | Strict mode fill 0.000; external off fill 0.748. |
| La fréquence de revue/pilotage est un levier majeur | high | medium | Observed across shocks, full exploration and policy cases. | Review 7d fill 0.315 vs baseline 0.788. |
| Le niveau absolu de coût reste moins robuste que les tendances relatives | medium | high | Transport/purchase/holding were calibrated and external procurement is stylized. | Baseline total cost 1273360.3; external-expensive rises to 1281823.1. |

## 3) Sensibilite des hypotheses de modelisation
| case_id | description | fill_rate | ending_backlog | total_cost | total_external_procured_ordered_qty | total_opening_stock_bootstrap_qty |
|---|---|---|---|---|---|---|
| hyp_007923_no_supplier_mapping | Remove assumed supplier mapping for 007923 but keep other baseline assumptions. | 0.527124 | 703.402400 | 1271769.591600 | 41664.252000 | 1060029.489700 |
| hyp_bootstrap_50pct | Reduce opening stock bootstrap by 50%. | 0.612828 | 575.918000 | 27279614.151800 | 688746.861300 | 529924.744900 |
| hyp_730384_tight_flow | Treat 730384 (unit M) as a tighter flow: lower supplier and factory opening stocks. | 0.732125 | 398.463900 | 1273224.003500 | 43004.865800 | 1060029.489700 |
| hyp_external_off | Disable external procurement. | 0.747671 | 375.339400 | 1246133.852300 | 0.000000 | 1060029.489700 |
| hyp_external_limited | Keep external procurement but with tighter cap and slower lead. | 0.787665 | 315.849000 | 1257870.890200 | 23814.415600 | 1060029.489700 |
| hyp_007923_vd0519670a | Re-route 007923 to existing supplier SDC-VD0519670A instead of Gaillac. | 0.787666 | 315.847600 | 1273360.489200 | 42871.121600 | 1060628.689700 |
| hyp_007923_dedicated_local | Assign 007923 to a dedicated local assumed supplier near Avene. | 0.787666 | 315.847600 | 1273314.067900 | 42871.121600 | 1060029.489700 |
| hyp_external_expensive | Keep external procurement but make it much more expensive. | 0.787666 | 315.847600 | 1281823.063200 | 42871.121600 | 1060029.489700 |
| hyp_bootstrap_150pct | Increase opening stock bootstrap by 50%. | 0.798091 | 300.339400 | 1906503.924500 | 46512.022000 | 1590484.234600 |

Lecture:
- Les hypotheses qui changent le plus la lecture sont celles sur `007923`, l'appro externe et le bootstrap de stock initial.
- `730384` en unite `M` reste un point de vigilance de semantique/metier, mais sous les buffers actuels ce n'est pas un driver majeur de degradation.

## 4) Mode strict "sans hypotheses fortes"
- Cas strict: `strict_raw_supported_only`
- Fill rate: **0.000000**
- Ending backlog: **1487.5000**
- Total cost: **22614.6118**

Lecture:
- Cette vue montre ce que la donnee brute supporte reellement sans artifice fort.
- L'ecart avec la baseline mesure a quel point la performance actuelle depend des completions de preparation.

## 5) Comparaison des politiques de pilotage
| case_id | description | fill_rate | ending_backlog | total_cost | review_period_days | safety_stock_days | production_gap_gain | production_smoothing |
|---|---|---|---|---|---|---|---|---|
| policy_review_7d | Periodic review every 7 days. | 0.315402 | 1018.340000 | 1308172.051400 | 7.000000 | 7.000000 | 0.250000 | 0.200000 |
| policy_review_2d | Periodic review every 2 days. | 0.633753 | 544.792800 | 1278270.948700 | 2.000000 | 7.000000 | 0.250000 | 0.200000 |
| policy_stock_buffered | More buffered policy: higher safety stock and FG target. | 0.764235 | 350.700300 | 1273103.165000 | 1.000000 | 10.000000 | 0.200000 | 0.300000 |
| policy_reactive_mrp | More reactive policy: daily review, higher gap gain, lower smoothing. | 0.823529 | 262.500000 | 1275146.914700 | 1.000000 | 6.000000 | 0.600000 | 0.050000 |

Lecture:
- La revue 7 jours degrade tres fortement le service.
- Une politique plus reactive de type MRP quotidien ameliorant le recalcul frequemment preserve mieux le service qu'une revue lente.
- Une politique plus bufferisee peut proteger le service, mais en poussant les couts et les stocks.

## 6) Decomposition fine des causes de backlog (baseline)
- Jours avec sous-service identifies: **20**
- Repartition dominante des causes: **{"downstream_stockout_or_distribution": 6, "capacity": 10, "input_shortage": 4}**
- Inputs dominants en contrainte: **{"item:773474": 4}**

### Jours principaux de sous-service
| day | demand | served | ending_backlog | dominant_factory | dominant_output_item | dominant_cause | dominant_binding_input | dominant_shortfall_vs_desired_qty |
|---|---|---|---|---|---|---|---|---|
| 0 | 40.000000 | 0.000000 | 40.000000 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 1 | 47.500000 | 0.000000 | 87.500000 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 2 | 52.500000 | 0.000000 | 140.000000 | M-1430 | item:268967 | capacity |  | 0.600000 |
| 3 | 60.000000 | 0.000000 | 200.000000 | M-1430 | item:268967 | capacity |  | 4.120000 |
| 4 | 55.000000 | 0.000000 | 255.000000 | M-1430 | item:268967 | capacity |  | 2.824000 |
| 5 | 50.000000 | 43.000000 | 262.000000 | M-1430 | item:268967 | capacity |  | 0.564800 |
| 6 | 45.000000 | 43.000000 | 264.000000 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 7 | 40.000000 | 0.000000 | 304.000000 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 9 | 52.500000 | 25.000000 | 304.000000 | M-1430 | item:268967 | capacity |  | 0.624900 |
| 10 | 60.000000 | 48.113000 | 315.887000 | M-1430 | item:268967 | capacity |  | 4.125000 |
| 12 | 50.000000 | 25.000000 | 320.887000 | M-1430 | item:268967 | capacity |  | 0.565000 |
| 13 | 45.000000 | 0.000000 | 365.887000 |  |  | downstream_stockout_or_distribution |  | 0.000000 |

Lecture:
- Cette decomposition est maintenant basee sur un diagnostic journalier de contrainte de production, pas seulement sur l'evolution du backlog.
- Elle reste une inference de modele, mais elle est beaucoup plus defensable qu'une lecture purement qualitative.

## 7) Carte de fragilite par matiere
| node | item_id | supplier_count | criticality_score | cover_days | total_consumed | structural_class | model_dependency | targeted_disruption_fill_delta | targeted_disruption_backlog_delta |
|---|---|---|---|---|---|---|---|---|---|
| M-1430 | item:042342 | 1 | 0.807193 | 35.571352 | 36569.438823 | mono_source | low | -0.009281 | 13.804100 |
| M-1430 | item:773474 | 1 | 0.472112 | 10.214765 | 5851.108999 | mono_source | low | -0.038672 | 57.523800 |
| M-1810 | item:007923 | 1 | 0.425239 | 8.674297 | 2307.510518 | mono_source | high_assumed_supplier | -0.026207 | 38.982800 |
| M-1810 | item:338928 | 1 | 0.422936 | 122.375470 | 710.440430 | mono_source | low | None | None |
| M-1810 | item:049371 | 1 | 0.422265 | 270.569613 | 1.067223 | mono_source | low | None | None |
| M-1810 | item:338929 | 1 | 0.420512 | 68.155583 | 710.440430 | mono_source | low | None | None |
| M-1810 | item:693055 | 1 | 0.418639 | 121.685757 | 288.438815 | mono_source | low | None | None |
| M-1810 | item:001757 | 1 | 0.416523 | 149.198651 | 1.153755 | mono_source | low | None | None |
| M-1430 | item:344135 | 1 | 0.413992 | 64.937738 | 606.036241 | mono_source | low | None | None |
| M-1810 | item:029313 | 1 | 0.413938 | 95.299945 | 0.028842 | mono_source | low | None | None |
| M-1810 | item:016332 | 1 | 0.413186 | 82.067629 | 0.346126 | mono_source | low | None | None |
| M-1430 | item:333362 | 1 | 0.412721 | 120.792483 | 606.036241 | mono_source | low | -0.003135 | 4.662400 |
| M-1810 | item:039668 | 1 | 0.411634 | 55.686083 | 0.028842 | mono_source | low | None | None |
| M-1810 | item:099439 | 1 | 0.411511 | 55.986938 | 1.442194 | mono_source | low | None | None |
| M-1810 | item:426331 | 1 | 0.410571 | 43.305578 | 7.814848 | mono_source | low | None | None |

Lecture:
- `item:042342` reste la fragilite structurelle majeure.
- `item:007923` est un cas particulier: criticite operationnelle visible, mais dependance forte a l'hypothese Gaillac.
- `item:730384` et `item:333362` ressortent davantage comme points de vigilance de donnees / semantique que comme fragilites operationnelles dominantes dans la baseline.

## 8) Frontiere cout / service

### Frontiere Pareto sur les cas cibles de cette revue
| case_id | category | fill_rate | ending_backlog | total_cost | total_external_procured_ordered_qty |
|---|---|---|---|---|---|
| policy_reactive_mrp | policy | 0.823529 | 262.500000 | 1275146.914700 | 48166.126600 |
| hyp_007923_dedicated_local | hypothesis | 0.787666 | 315.847600 | 1273314.067900 | 42871.121600 |
| hyp_external_limited | hypothesis | 0.787665 | 315.849000 | 1257870.890200 | 23814.415600 |
| hyp_external_off | hypothesis | 0.747671 | 375.339400 | 1246133.852300 | 0.000000 |
| strict_raw_supported_only | strict_mode | 0.000000 | 1487.500000 | 22614.611800 | 0.000000 |

### Extrait de frontiere globale cout / service (full exploration)
| run_id | kpi::fill_rate | kpi::ending_backlog | kpi::total_cost |
|---|---|---|---|
| full_run_0202 | 0.855975 | 182.1019 | 1229460.4726 |
| full_run_0070 | 0.838748 | 203.883 | 1229445.5352 |
| full_run_0066 | 0.836395 | 206.8581 | 1228180.34 |
| full_run_0085 | 0.750614 | 315.3177 | 1186294.1324 |
| full_run_0205 | 0.749868 | 316.2611 | 879661.1453 |
| full_run_0073 | 0.747806 | 318.8674 | 867465.2272 |
| full_run_0354 | 0.600856 | 573.1207 | 794055.833 |
| full_run_0257 | 0.590255 | 611.9815 | 723085.2929 |
| full_run_0409 | 0.4172 | 931.3372 | 704691.5005 |
| full_run_0301 | 0.377405 | 862.832 | 634351.1339 |

### Extrait de frontiere service / inventaire (full exploration)
| run_id | kpi::fill_rate | kpi::avg_inventory | kpi::total_cost |
|---|---|---|---|
| full_run_0202 | 0.855975 | 1010007.023 | 1229460.4726 |
| full_run_0066 | 0.836395 | 1009318.2245 | 1228180.34 |
| full_run_0085 | 0.750614 | 974391.2263 | 1186294.1324 |
| full_run_0205 | 0.749868 | 720856.6898 | 879661.1453 |
| full_run_0073 | 0.747806 | 711374.5964 | 867465.2272 |
| full_run_0267 | 0.584182 | 643659.7744 | 853697.6706 |
| full_run_0379 | 0.463692 | 623161.1642 | 781899.8398 |
| full_run_0409 | 0.4172 | 553939.4475 | 704691.5005 |

Lecture:
- La baseline est performante, mais elle est surtout protectrice.
- Certaines politiques ou hypotheses peuvent battre la baseline sur un axe, rarement sur service + cout simultanement.
- La frontiere montre bien que le service est souvent achete par du stock, pas seulement par une meilleure reactivite.

## 9) Ruptures ciblees plus realistes
| case_id | description | fill_rate | ending_backlog | total_cost |
|---|---|---|---|---|
| disrupt_M1810_capacity_down30 | Targeted capacity reduction of 30% on M-1810. | 0.652827 | 516.419700 | 1271350.874900 |
| disrupt_773474_outage_5d | Temporary 5-day outage of 773474 lane from Gaillac. | 0.748994 | 373.371400 | 1271927.931200 |
| disrupt_730384_outage_5d | Temporary 5-day outage of 730384 lane (unit M). | 0.757184 | 361.188100 | 1272015.466600 |
| disrupt_007923_gaillac_outage_5d | Temporary 5-day outage of assumed 007923 lane from Gaillac. | 0.761459 | 354.830400 | 1272467.646600 |
| disrupt_042342_outage_5d | Temporary 5-day outage of supplier lane for 042342. | 0.778385 | 329.651700 | 1271908.945900 |
| disrupt_333362_outage_5d | Temporary 5-day outage of packaging item 333362. | 0.784531 | 320.510000 | 1273251.105200 |
| disrupt_042342_extreme_delay | Extreme delay on 042342 lane. | 0.787666 | 315.847600 | 1275083.573300 |

Lecture:
- Les ruptures les plus destructrices restent celles touchant les intrants critiques mono-source ou le pilotage.
- Les outages ponctuels sur `042342`, `773474` et `007923` sont nettement plus instructifs que des chocs globaux abstraits.
- Les tests packaging `730384` / `333362` ne degradent pas fortement la baseline actuelle, ce qui suggere que leur enjeu est aujourd'hui plus data-quality que capacitaire.

## 10) Conclusion operative
1. La representation actuelle est utile pour raisonner, mais une partie non negligeable de la performance baseline repose sur des hypotheses de preparation.
2. Les conclusions les plus robustes sont: fragilite mono-source, sensibilite forte a la revue/pilotage, importance de `M-1810` pour le service et de `M-1430` pour le cout.
3. Les conclusions les moins robustes sont: criticite absolue de `007923`, niveau absolu des couts et ampleur exacte de la resilience fournie par l'externe.
4. Le mode strict est la meilleure borne basse "supportee par la donnee brute".
5. Les ruptures ciblees et la carte de fragilite sont les sorties les plus utiles pour discuter concretement avec l'industriel sans surpromettre sur la precision du modele.
