# Revue approfondie des hypotheses et de la robustesse du modele supply

## Perimetre
- Base de travail: input prepare avec hypothese conservee `item:693710 -> SDC-1450 / Gaillac`
- Objectif: distinguer ce qui est robuste, tester les hypotheses de completion, construire un mode strict, comparer des politiques de pilotage, decomposer les causes du backlog, cartographier la fragilite matiere, tracer des frontieres cout/service et tester des ruptures ciblees.

## 1) Baseline conservee
- Fill rate: **0.945418**
- Ending backlog: **81.8736**
- Total cost: **28723.7188**
- External procured ordered qty: **53342.6330**
- Opening stock bootstrap qty: **29870.3660**

## 2) Ce qui est robuste vs ce qui depend des hypotheses
| conclusion | confidence | hypothesis_dependency | observed_vs_assumed | evidence |
|---|---|---|---|---|
| Mono-sourcing de item:042342 sur M-1430 | high | low | Observed directly in Data_poc.xlsx relations and criticality table; no inferred supplier. | Supplier count = 1, highest criticality score. |
| Criticité élevée de item:693710 sur M-1810 | medium | high | Observed in BOM, but supplier mapping is assumed to SDC-1450/Gaillac. | No-supplier mapping fill 0.777; 5-day outage fill 0.886. |
| M-1810 agit comme goulot service/backlog | high | medium | Observed in sensitivity, policy tests and targeted capacity drop. | M-1810 capacity-down case fill 0.836. |
| M-1430 est le principal driver de coût | high | medium | Observed in OAT sensitivity on cost; absolute level still depends on cost assumptions. | capacity_node_scale::M-1430 remains top cost driver. |
| La baseline à 94.5% repose fortement sur stock bootstrap + appro externe | high | high | Observed via strict mode and external-off cases; both are model assumptions, not source data. | Strict mode fill 0.274; external off fill 0.808. |
| La fréquence de revue/pilotage est un levier majeur | high | medium | Observed across shocks, full exploration and policy cases. | Review 7d fill 0.539 vs baseline 0.945. |
| Le niveau absolu de coût reste moins robuste que les tendances relatives | medium | high | Transport/purchase/holding were calibrated and external procurement is stylized. | Baseline total cost 28723.7; external-expensive rises to 39124.6. |

## 3) Sensibilite des hypotheses de modelisation
| case_id | description | fill_rate | ending_backlog | total_cost | total_external_procured_ordered_qty | total_opening_stock_bootstrap_qty |
|---|---|---|---|---|---|---|
| hyp_693710_no_supplier_mapping | Remove assumed supplier mapping for 693710 but keep other baseline assumptions. | 0.777038 | 334.442700 | 27806.215200 | 52164.951000 | 29870.366000 |
| hyp_external_off | Disable external procurement. | 0.807853 | 288.219800 | 14136.020000 | 0.000000 | 29870.366000 |
| hyp_bootstrap_50pct | Reduce opening stock bootstrap by 50%. | 0.857726 | 213.411100 | 23496.535300 | 68348.215200 | 14935.183000 |
| hyp_external_limited | Keep external procurement but with tighter cap and slower lead. | 0.879219 | 181.172100 | 17595.401600 | 27334.112200 | 29870.366000 |
| hyp_693710_vd0519670a | Re-route 693710 to existing supplier SDC-VD0519670A instead of Gaillac. | 0.945418 | 81.873600 | 28723.883900 | 53342.633000 | 30469.566000 |
| hyp_693710_dedicated_local | Assign 693710 to a dedicated local assumed supplier near Avene. | 0.945418 | 81.873600 | 28677.338000 | 53342.633000 | 29870.366000 |
| hyp_bootstrap_150pct | Increase opening stock bootstrap by 50%. | 0.945418 | 81.873600 | 44234.200700 | 53342.633000 | 45155.549000 |
| hyp_external_expensive | Keep external procurement but make it much more expensive. | 0.945418 | 81.873600 | 39124.637500 | 53342.633000 | 29870.366000 |
| hyp_730384_tight_flow | Treat 730384 (unit M) as a tighter flow: lower supplier and factory opening stocks. | 0.980693 | 28.960000 | 29865.510200 | 53484.883000 | 29870.366000 |

Lecture:
- Les hypotheses qui changent le plus la lecture sont celles sur `693710`, l'appro externe et le bootstrap de stock initial.
- `730384` en unite `M` reste un point de vigilance de semantique/metier, mais sous les buffers actuels ce n'est pas un driver majeur de degradation.

## 4) Mode strict "sans hypotheses fortes"
- Cas strict: `strict_raw_supported_only`
- Fill rate: **0.273989**
- Ending backlog: **1089.0170**
- Total cost: **5746.8136**

Lecture:
- Cette vue montre ce que la donnee brute supporte reellement sans artifice fort.
- L'ecart avec la baseline mesure a quel point la performance actuelle depend des completions de preparation.

## 5) Comparaison des politiques de pilotage
| case_id | description | fill_rate | ending_backlog | total_cost | review_period_days | safety_stock_days | production_gap_gain | production_smoothing |
|---|---|---|---|---|---|---|---|---|
| policy_review_7d | Periodic review every 7 days. | 0.538728 | 691.908600 | 35266.351100 | 7.000000 | 7.000000 | 0.250000 | 0.200000 |
| policy_review_2d | Periodic review every 2 days. | 0.764753 | 352.870800 | 27719.433200 | 2.000000 | 7.000000 | 0.250000 | 0.200000 |
| policy_stock_buffered | More buffered policy: higher safety stock and FG target. | 1.000000 | 0.000000 | 28302.867500 | 1.000000 | 10.000000 | 0.200000 | 0.300000 |
| policy_reactive_mrp | More reactive policy: daily review, higher gap gain, lower smoothing. | 1.000000 | 0.000000 | 28302.733100 | 1.000000 | 6.000000 | 0.600000 | 0.050000 |

Lecture:
- La revue 7 jours degrade tres fortement le service.
- Une politique plus reactive de type MRP quotidien ameliorant le recalcul frequemment preserve mieux le service qu'une revue lente.
- Une politique plus bufferisee peut proteger le service, mais en poussant les couts et les stocks.

## 6) Decomposition fine des causes de backlog (baseline)
- Jours avec sous-service identifies: **14**
- Repartition dominante des causes: **{"capacity": 11, "downstream_stockout_or_distribution": 3}**
- Inputs dominants en contrainte: **{}**

### Jours principaux de sous-service
| day | demand | served | ending_backlog | dominant_factory | dominant_output_item | dominant_cause | dominant_binding_input | dominant_shortfall_vs_desired_qty |
|---|---|---|---|---|---|---|---|---|
| 8 | 52.000000 | 48.000000 | 4.000000 | M-1810 | item:268091 | capacity |  | 3.300100 |
| 9 | 48.000000 | 26.480000 | 25.520000 | M-1810 | item:268091 | capacity |  | 1.460000 |
| 11 | 44.000000 | 26.520000 | 22.904000 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 13 | 48.000000 | 28.520000 | 19.480000 | M-1430 | item:268967 | capacity |  | 0.508000 |
| 14 | 52.000000 | 24.000000 | 47.480000 | M-1430 | item:268967 | capacity |  | 2.501600 |
| 17 | 56.000000 | 11.226900 | 44.773100 | M-1810 | item:268091 | capacity |  | 4.500300 |
| 18 | 52.000000 | 24.492000 | 72.281100 | M-1810 | item:268091 | capacity |  | 3.300100 |
| 20 | 44.000000 | 20.000000 | 58.392800 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 21 | 44.000000 | 11.850000 | 90.542800 |  |  | downstream_stockout_or_distribution |  | 0.000000 |
| 24 | 52.000000 | 38.342000 | 13.658000 | M-1430 | item:268967 | capacity |  | 2.501600 |
| 25 | 56.000000 | 46.499700 | 23.158300 | M-1430 | item:268967 | capacity |  | 4.500300 |
| 26 | 56.000000 | 40.845200 | 38.313100 | M-1430 | item:268967 | capacity |  | 3.300100 |

Lecture:
- Cette decomposition est maintenant basee sur un diagnostic journalier de contrainte de production, pas seulement sur l'evolution du backlog.
- Elle reste une inference de modele, mais elle est beaucoup plus defensable qu'une lecture purement qualitative.

## 7) Carte de fragilite par matiere
| node | item_id | supplier_count | criticality_score | cover_days | total_consumed | structural_class | model_dependency | targeted_disruption_fill_delta | targeted_disruption_backlog_delta |
|---|---|---|---|---|---|---|---|---|---|
| M-1430 | item:042342 | 1 | 0.268714 | 9.687007 | 42997.923938 | mono_source | low | -0.024768 | 37.151700 |
| M-1430 | item:773474 | 1 | 0.185301 | 9.362300 | 6879.666404 | mono_source | low | -0.032732 | 49.097600 |
| M-1810 | item:693710 | 1 | 0.178368 | 7.701152 | 2314.444290 | mono_source | high_assumed_supplier | -0.058988 | 88.481100 |
| M-1430 | item:344135 | 1 | 0.172094 | 8.786246 | 712.570415 | mono_source | low | None | None |
| M-1430 | item:333362 | 1 | 0.171272 | 9.196203 | 712.570415 | mono_source | low | 0.019166 | -28.749200 |
| M-1810 | item:049371 | 1 | 0.171079 | 8.489062 | 1.070433 | mono_source | low | None | None |
| M-1810 | item:426331 | 1 | 0.170510 | 8.760144 | 7.838325 | mono_source | low | None | None |
| M-1430 | item:734545 | 1 | 0.170046 | 8.983685 | 5.700561 | mono_source | low | None | None |
| M-1810 | item:338929 | 1 | 0.169908 | 9.958662 | 712.575214 | mono_source | low | None | None |
| M-1810 | item:338928 | 1 | 0.169748 | 10.055186 | 712.575214 | mono_source | low | None | None |
| M-1430 | item:730384 | 1 | 0.169681 | 9.346712 | 151.064927 | mono_source | medium_unit_M_ambiguous | 0.018633 | -27.950800 |
| M-1810 | item:039668 | 1 | 0.169595 | 9.206547 | 0.028928 | mono_source | low | None | None |
| M-1810 | item:693055 | 1 | 0.168911 | 9.965821 | 289.305537 | mono_source | low | None | None |
| M-1430 | item:708073 | 1 | 0.168844 | 9.620624 | 5.650682 | mono_source | low | None | None |
| M-1430 | item:038005 | 1 | 0.168749 | 9.684033 | 12.469389 | mono_source | low | None | None |

Lecture:
- `item:042342` reste la fragilite structurelle majeure.
- `item:693710` est un cas particulier: criticite operationnelle visible, mais dependance forte a l'hypothese Gaillac.
- `item:730384` et `item:333362` ressortent davantage comme points de vigilance de donnees / semantique que comme fragilites operationnelles dominantes dans la baseline.

## 8) Frontiere cout / service

### Frontiere Pareto sur les cas cibles de cette revue
| case_id | category | fill_rate | ending_backlog | total_cost | total_external_procured_ordered_qty |
|---|---|---|---|---|---|
| policy_reactive_mrp | policy | 1.000000 | 0.000000 | 28302.733100 | 56469.556400 |
| disrupt_730384_outage_5d | targeted_disruption | 0.964051 | 53.922800 | 28145.133600 | 53342.633000 |
| disrupt_042342_outage_5d | targeted_disruption | 0.920650 | 119.025300 | 27168.748200 | 55765.009300 |
| hyp_external_limited | hypothesis | 0.879219 | 181.172100 | 17595.401600 | 27334.112200 |
| hyp_external_off | hypothesis | 0.807853 | 288.219800 | 14136.020000 | 0.000000 |
| strict_raw_supported_only | strict_mode | 0.273989 | 1089.017000 | 5746.813600 | 0.000000 |

### Extrait de frontiere globale cout / service (full exploration)
| run_id | kpi::fill_rate | kpi::ending_backlog | kpi::total_cost |
|---|---|---|---|
| full_run_0201 | 1.0 | 0.0 | 20134.4071 |
| full_run_0605 | 0.916239 | 118.0403 | 18466.1946 |
| full_run_0073 | 0.90586 | 120.0289 | 15232.5544 |
| full_run_0272 | 0.756167 | 357.7311 | 14836.6855 |
| full_run_0075 | 0.686333 | 564.6 | 14655.3551 |
| full_run_0107 | 0.620914 | 682.3544 | 14184.137 |
| full_run_0099 | 0.596007 | 727.1867 | 14107.9931 |
| full_run_0011 | 0.530152 | 845.727 | 13958.7767 |
| full_run_0043 | 0.496372 | 906.531 | 13905.027 |
| full_run_0328 | 0.488327 | 1169.453 | 12517.0423 |

### Extrait de frontiere service / inventaire (full exploration)
| run_id | kpi::fill_rate | kpi::avg_inventory | kpi::total_cost |
|---|---|---|---|
| full_run_0201 | 1.0 | 16731.7679 | 20134.4071 |
| full_run_0069 | 0.98936 | 16324.4511 | 21397.2596 |
| full_run_0073 | 0.90586 | 11077.867 | 15232.5544 |
| full_run_0009 | 0.741876 | 10896.9643 | 14961.7817 |
| full_run_0075 | 0.686333 | 10560.5654 | 14655.3551 |
| full_run_0011 | 0.530152 | 9930.5481 | 13958.7767 |

Lecture:
- La baseline est performante, mais elle est surtout protectrice.
- Certaines politiques ou hypotheses peuvent battre la baseline sur un axe, rarement sur service + cout simultanement.
- La frontiere montre bien que le service est souvent achete par du stock, pas seulement par une meilleure reactivite.

## 9) Ruptures ciblees plus realistes
| case_id | description | fill_rate | ending_backlog | total_cost |
|---|---|---|---|---|
| disrupt_M1810_capacity_down30 | Targeted capacity reduction of 30% on M-1810. | 0.836360 | 245.459700 | 28265.258000 |
| disrupt_693710_gaillac_outage_5d | Temporary 5-day outage of assumed 693710 lane from Gaillac. | 0.886430 | 170.354700 | 29240.938900 |
| disrupt_773474_outage_5d | Temporary 5-day outage of 773474 lane from Gaillac. | 0.912686 | 130.971200 | 28549.870200 |
| disrupt_042342_outage_5d | Temporary 5-day outage of supplier lane for 042342. | 0.920650 | 119.025300 | 27168.748200 |
| disrupt_042342_extreme_delay | Extreme delay on 042342 lane. | 0.945418 | 81.873600 | 72137.424200 |
| disrupt_730384_outage_5d | Temporary 5-day outage of 730384 lane (unit M). | 0.964051 | 53.922800 | 28145.133600 |
| disrupt_333362_outage_5d | Temporary 5-day outage of packaging item 333362. | 0.964584 | 53.124400 | 28544.348700 |

Lecture:
- Les ruptures les plus destructrices restent celles touchant les intrants critiques mono-source ou le pilotage.
- Les outages ponctuels sur `042342`, `773474` et `693710` sont nettement plus instructifs que des chocs globaux abstraits.
- Les tests packaging `730384` / `333362` ne degradent pas fortement la baseline actuelle, ce qui suggere que leur enjeu est aujourd'hui plus data-quality que capacitaire.

## 10) Conclusion operative
1. La representation actuelle est utile pour raisonner, mais une partie non negligeable de la performance baseline repose sur des hypotheses de preparation.
2. Les conclusions les plus robustes sont: fragilite mono-source, sensibilite forte a la revue/pilotage, importance de `M-1810` pour le service et de `M-1430` pour le cout.
3. Les conclusions les moins robustes sont: criticite absolue de `693710`, niveau absolu des couts et ampleur exacte de la resilience fournie par l'externe.
4. Le mode strict est la meilleure borne basse "supportee par la donnee brute".
5. Les ruptures ciblees et la carte de fragilite sont les sorties les plus utiles pour discuter concretement avec l'industriel sans surpromettre sur la precision du modele.
