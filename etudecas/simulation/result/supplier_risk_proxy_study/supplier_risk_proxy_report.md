# Etude etendue proxy de risque fournisseur-matiere

## Perimetre
- Base: baseline preparee avec hypothese conservee `item:007923 -> SDC-1450 / Gaillac`
- Cible: couples `supplier -> factory -> item` de la supply amont
- Nombre de couples analyses: **30**
- Nature des probabilites: **proxy**, pas empirique. Elles servent a classer/prioriser tant que le score industriel 22 criteres n'est pas disponible.

## 1) Baseline de reference
- Fill rate: **0.787666**
- Ending backlog: **315.8476**
- Total cost: **1273360.3167**

## 2) Methode utilisee
Le score provisoire par couple fournisseur-matiere combine 3 couches:
1. **Structure observee**: mono/multi-source, exposition demande aval, volume consomme, couverture, delai, criticite existante.
2. **Impact simule**: pour chaque couple, simulation de:
   - outage 5 jours
   - delai x3
   - OTIF a 50%
3. **Probabilites proxy**:
   - `p_incident_30d_proxy` derivee du score structurel
   - `p_service_hit_30d_proxy` = probabilite proxy d'incident x severite proxy d'impact

Important:
- ces probabilites **ne sont pas des frequences observees**
- elles servent a construire une priorisation rationnelle avant d'avoir le score industriel et l'historique incident

## 3) Top couples fournisseur-matiere a surveiller
| supplier_id | factory_id | item_id | combined_proxy_risk_score | p_incident_30d_proxy | p_service_hit_30d_proxy | expected_fill_loss_30d_proxy | expected_backlog_30d_proxy | supplier_count_for_item | is_assumed_edge |
|---|---|---|---|---|---|---|---|---|---|
| SDC-1450 | M-1430 | item:773474 | 0.867240 | 0.118697 | 0.118697 | 0.002082 | 3.097006 | 1 | False |
| SDC-1450 | M-1810 | item:007923 | 0.850015 | 0.122166 | 0.115863 | 0.002032 | 3.023077 | 1 | True |
| SDC-VD0508918A | M-1430 | item:730384 | 0.806193 | 0.110967 | 0.103663 | 0.001818 | 2.704724 | 1 | False |
| SDC-1450 | M-1810 | item:693055 | 0.638753 | 0.109591 | 0.069896 | 0.001226 | 1.823674 | 1 | False |
| SDC-VD0914690A | M-1430 | item:042342 | 0.544041 | 0.126608 | 0.046355 | 0.000813 | 1.209450 | 1 | False |
| SDC-VD0989480A | M-1810 | item:426331 | 0.527004 | 0.101981 | 0.048857 | 0.000857 | 1.274763 | 1 | False |
| SDC-VD0505677A | M-1810 | item:099439 | 0.516719 | 0.098781 | 0.047324 | 0.000830 | 1.234765 | 1 | False |
| SDC-VD0951020A | M-1810 | item:001757 | 0.512283 | 0.097401 | 0.046663 | 0.000819 | 1.217514 | 1 | False |
| SDC-VD0514881A | M-1810 | item:016332 | 0.511241 | 0.097077 | 0.046508 | 0.000816 | 1.213461 | 1 | False |
| SDC-VD1096202A | M-1810 | item:039668 | 0.510100 | 0.096722 | 0.046337 | 0.000813 | 1.209024 | 1 | False |
| SDC-VD0519670A | M-1810 | item:029313 | 0.508686 | 0.096282 | 0.046127 | 0.000809 | 1.203525 | 1 | False |
| SDC-VD0520132A | M-1810 | item:049371 | 0.507188 | 0.095816 | 0.045904 | 0.000805 | 1.197701 | 1 | False |
| SDC-VD1095770A | M-1430 | item:734545 | 0.498603 | 0.100784 | 0.043784 | 0.000768 | 1.142395 | 1 | False |
| SDC-VD0520115A | M-1430 | item:708073 | 0.497644 | 0.100485 | 0.043655 | 0.000766 | 1.139015 | 1 | False |
| SDC-VD0520132A | M-1430 | item:038005 | 0.484946 | 0.096535 | 0.041938 | 0.000736 | 1.094235 | 1 | False |

Lecture:
- `combined_proxy_risk_score` classe les couples selon **probabilite proxy x impact proxy**.
- `expected_fill_loss_30d_proxy` et `expected_backlog_30d_proxy` donnent une lecture plus operationnelle.

## 4) Couples avec plus forte probabilite proxy d'incident
| supplier_id | factory_id | item_id | p_incident_30d_proxy | incident_probability_band | structural_proxy_score | mono_source_risk | uncertainty_penalty |
|---|---|---|---|---|---|---|---|
| SDC-VD0914690A | M-1430 | item:042342 | 0.126608 | high | 0.761485 | 1.000000 | 0.000000 |
| SDC-1450 | M-1810 | item:007923 | 0.122166 | high | 0.729755 | 1.000000 | 1.000000 |
| SDC-1450 | M-1430 | item:773474 | 0.118697 | high | 0.704977 | 1.000000 | 0.000000 |
| SDC-VD0914360C | M-1810 | item:338929 | 0.112442 | high | 0.660303 | 1.000000 | 0.000000 |
| SDC-VD0901566A | M-1810 | item:338928 | 0.111764 | high | 0.655454 | 1.000000 | 0.000000 |
| SDC-VD0993480A | M-1430 | item:344135 | 0.111536 | high | 0.653828 | 1.000000 | 0.000000 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.110967 | high | 0.649763 | 1.000000 | 0.600000 |
| SDC-VD0525412A | M-1430 | item:333362 | 0.110440 | high | 0.645997 | 1.000000 | 0.000000 |
| SDC-1450 | M-1810 | item:693055 | 0.109591 | high | 0.639933 | 1.000000 | 0.000000 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.101981 | high | 0.585579 | 1.000000 | 0.000000 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.100784 | high | 0.577026 | 1.000000 | 0.000000 |
| SDC-VD0520115A | M-1430 | item:708073 | 0.100485 | high | 0.574896 | 1.000000 | 0.000000 |

Lecture:
- cette table pousse surtout les couples structurellement fragiles:
  mono-source, forte exposition aval, couverture plus faible, delai plus long, ou incertitude modele.

## 5) Couples avec plus forte probabilite proxy de choc service
| supplier_id | factory_id | item_id | p_service_hit_30d_proxy | service_hit_probability_band | impact_proxy_score | expected_fill_loss_proxy | expected_backlog_delta_proxy |
|---|---|---|---|---|---|---|---|
| SDC-1450 | M-1430 | item:773474 | 0.118697 | high | 1.000000 | 0.017541 | 26.091750 |
| SDC-1450 | M-1810 | item:007923 | 0.115863 | high | 0.948410 | 0.016636 | 24.745700 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.103663 | high | 0.934181 | 0.016387 | 24.374175 |
| SDC-1450 | M-1810 | item:693055 | 0.069896 | medium | 0.637788 | 0.011187 | 16.640780 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.048857 | low | 0.479080 | 0.008404 | 12.500000 |
| SDC-VD0505677A | M-1810 | item:099439 | 0.047324 | low | 0.479080 | 0.008404 | 12.500000 |
| SDC-VD0951020A | M-1810 | item:001757 | 0.046663 | low | 0.479080 | 0.008404 | 12.500000 |
| SDC-VD0514881A | M-1810 | item:016332 | 0.046508 | low | 0.479080 | 0.008404 | 12.500000 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.046355 | low | 0.366132 | 0.006422 | 9.552725 |
| SDC-VD1096202A | M-1810 | item:039668 | 0.046337 | low | 0.479080 | 0.008404 | 12.500000 |
| SDC-VD0519670A | M-1810 | item:029313 | 0.046127 | low | 0.479080 | 0.008404 | 12.500000 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.045904 | low | 0.479080 | 0.008404 | 12.500000 |

Lecture:
- cette table distingue les couples qui ne sont pas seulement fragiles "sur le papier", mais qui **cassent vraiment** le service quand on les secoue.

## 6) Plus gros impacts simules en outage 5 jours
| supplier_id | factory_id | item_id | outage5d_fill_loss | outage5d_backlog_delta | outage5d_total_cost | supplier_count_for_item |
|---|---|---|---|---|---|---|
| SDC-1450 | M-1430 | item:773474 | 0.038672 | 57.523800 | 1271927.931200 | 1 |
| SDC-1450 | M-1810 | item:693055 | 0.033614 | 50.000000 | 1272052.135500 | 1 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.033614 | 50.000000 | 1272052.223100 | 1 |
| SDC-VD0505677A | M-1810 | item:099439 | 0.033614 | 50.000000 | 1272059.799200 | 1 |
| SDC-VD0951020A | M-1810 | item:001757 | 0.033614 | 50.000000 | 1272059.895300 | 1 |
| SDC-VD0514881A | M-1810 | item:016332 | 0.033614 | 50.000000 | 1272059.773900 | 1 |
| SDC-VD1096202A | M-1810 | item:039668 | 0.033614 | 50.000000 | 1272059.771400 | 1 |
| SDC-VD0519670A | M-1810 | item:029313 | 0.033614 | 50.000000 | 1272059.771800 | 1 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.033614 | 50.000000 | 1272059.791900 | 1 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.030482 | 45.340500 | 1272015.466600 | 1 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.030482 | 45.340500 | 1272013.860200 | 1 |
| SDC-VD0520115A | M-1430 | item:708073 | 0.030482 | 45.340500 | 1272012.822200 | 1 |

## 7) Plus gros impacts simules en delai x3
| supplier_id | factory_id | item_id | delayx3_fill_loss | delayx3_backlog_delta | delayx3_total_cost | lead_mean_days |
|---|---|---|---|---|---|---|
| SDC-1450 | M-1430 | item:773474 | 0.000000 | 0.000000 | 1273958.587400 | 10.000000 |
| SDC-1450 | M-1810 | item:007923 | 0.000000 | 0.000000 | 1273360.140200 | 1.000000 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.000000 | 0.000000 | 1273413.528700 | 56.000000 |
| SDC-1450 | M-1810 | item:693055 | 0.000000 | 0.000000 | 1273360.462800 | 70.000000 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.000000 | 0.000000 | 1275083.573300 | 21.000000 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.000000 | 0.000000 | 1273361.123800 | 28.000000 |
| SDC-VD0505677A | M-1810 | item:099439 | 0.000000 | 0.000000 | 1273360.574500 | 35.000000 |
| SDC-VD0951020A | M-1810 | item:001757 | 0.000000 | 0.000000 | 1273360.995800 | 84.000000 |
| SDC-VD0514881A | M-1810 | item:016332 | 0.000000 | 0.000000 | 1273360.426700 | 49.000000 |
| SDC-VD1096202A | M-1810 | item:039668 | 0.000000 | 0.000000 | 1273360.322200 | 35.000000 |
| SDC-VD0519670A | M-1810 | item:029313 | 0.000000 | 0.000000 | 1273360.327600 | 56.000000 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.000000 | 0.000000 | 1273361.441900 | 147.000000 |

Lecture:
- certains couples reagissent surtout a la rupture franche,
- d'autres supportent une rupture courte mais deviennent tres couteux quand le delai s'allonge.

## 8) Vue agregée par fournisseur
| supplier_id | material_count | max_pair_combined_proxy_risk_score | mean_p_incident_30d_proxy | mean_p_service_hit_30d_proxy | expected_backlog_30d_proxy_sum | materials |
|---|---|---|---|---|---|---|
| SDC-1450 | 3 | 0.867240 | 0.116818 | 0.101485 | 7.943757 | item:007923, item:693055, item:773474 |
| SDC-VD0508918A | 1 | 0.806193 | 0.110967 | 0.103663 | 2.704724 | item:730384 |
| SDC-VD0520132A | 2 | 0.507188 | 0.096175 | 0.043921 | 2.291936 | item:038005, item:049371 |
| SDC-VD0989480A | 1 | 0.527004 | 0.101981 | 0.048857 | 1.274763 | item:426331 |
| SDC-VD0505677A | 1 | 0.516719 | 0.098781 | 0.047324 | 1.234765 | item:099439 |
| SDC-VD0951020A | 2 | 0.512283 | 0.088321 | 0.023332 | 1.217514 | item:001757, item:001848 |
| SDC-VD0514881A | 1 | 0.511241 | 0.097077 | 0.046508 | 1.213461 | item:016332 |
| SDC-VD0914690A | 1 | 0.544041 | 0.126608 | 0.046355 | 1.209450 | item:042342 |
| SDC-VD1096202A | 1 | 0.510100 | 0.096722 | 0.046337 | 1.209024 | item:039668 |
| SDC-VD0519670A | 2 | 0.508686 | 0.086160 | 0.023064 | 1.203525 | item:001848, item:029313 |
| SDC-VD1095770A | 1 | 0.498603 | 0.100784 | 0.043784 | 1.142395 | item:734545 |
| SDC-VD0520115A | 1 | 0.497644 | 0.100485 | 0.043655 | 1.139015 | item:708073 |

Lecture:
- cette vue permet de prioriser les **fournisseurs** et pas seulement les couples fournisseur-matiere.
- un fournisseur multi-matieres peut remonter haut meme si chaque matiere seule est moyenne.

## 9) Ce qu'on peut deja dire proprement
1. Ce classement est utile pour une **priorisation provisoire** avant le score industriel 22 criteres.
2. Les couples mono-source fortement exposes a la demande restent logiquement en tete.
3. `item:007923` reste un cas special: visible dans le classement, mais une partie du signal depend de l'hypothese Gaillac.
4. `item:730384` peut remonter via son ambiguite d'unite/semantique, mais son impact operationnel simule reste plus faible que les matieres majeures.
5. Cette etude est plus utile pour la **priorisation relative** que pour donner un pourcentage "vrai" d'incident.

## 10) Limites et prochaine etape
- Sans historique fournisseur ni score 22 criteres, les probabilites restent des **proba proxy**.
- La prochaine etape naturelle est de remplacer la couche probabilite proxy par:
  - le score industriel fournisseur-matiere,
  - puis idealement des historiques OTIF / retard / qualite.
- Le bloc impact simule, lui, est deja reutilisable quasiment tel quel.
