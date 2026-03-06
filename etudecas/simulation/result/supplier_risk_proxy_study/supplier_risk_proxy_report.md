# Etude etendue proxy de risque fournisseur-matiere

## Perimetre
- Base: baseline preparee avec hypothese conservee `item:693710 -> SDC-1450 / Gaillac`
- Cible: couples `supplier -> factory -> item` de la supply amont
- Nombre de couples analyses: **30**
- Nature des probabilites: **proxy**, pas empirique. Elles servent a classer/prioriser tant que le score industriel 22 criteres n'est pas disponible.

## 1) Baseline de reference
- Fill rate: **0.945418**
- Ending backlog: **81.8736**
- Total cost: **28723.7188**

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
| SDC-1450 | M-1810 | item:693710 | 0.883013 | 0.123604 | 0.123604 | 0.002385 | 3.577441 | 1 | True |
| SDC-VD0914360C | M-1810 | item:338929 | 0.648196 | 0.110456 | 0.071785 | 0.001385 | 2.077660 | 1 | False |
| SDC-VD0901566A | M-1810 | item:338928 | 0.645831 | 0.109720 | 0.071307 | 0.001376 | 2.063819 | 1 | False |
| SDC-1450 | M-1430 | item:773474 | 0.557342 | 0.120828 | 0.051242 | 0.000989 | 1.483095 | 1 | False |
| SDC-VD0914690A | M-1430 | item:042342 | 0.515175 | 0.125366 | 0.040231 | 0.000776 | 1.164388 | 1 | False |
| SDC-VD0993480A | M-1430 | item:344135 | 0.319506 | 0.119402 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD0525412A | M-1430 | item:333362 | 0.309446 | 0.116272 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD0508918A | M-1430 | item:730384 | 0.307352 | 0.115621 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD0989480A | M-1810 | item:426331 | 0.286551 | 0.109149 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-1450 | M-1810 | item:693055 | 0.283630 | 0.108240 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD0520132A | M-1810 | item:049371 | 0.282158 | 0.107782 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD1095770A | M-1430 | item:734545 | 0.278956 | 0.106786 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD0520132A | M-1430 | item:038005 | 0.267096 | 0.103097 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD0520115A | M-1430 | item:708073 | 0.263277 | 0.101908 | 0.000000 | 0.000000 | 0.000000 | 1 | False |
| SDC-VD1096202A | M-1810 | item:039668 | 0.259223 | 0.100647 | 0.000000 | 0.000000 | 0.000000 | 1 | False |

Lecture:
- `combined_proxy_risk_score` classe les couples selon **probabilite proxy x impact proxy**.
- `expected_fill_loss_30d_proxy` et `expected_backlog_30d_proxy` donnent une lecture plus operationnelle.

## 4) Couples avec plus forte probabilite proxy d'incident
| supplier_id | factory_id | item_id | p_incident_30d_proxy | incident_probability_band | structural_proxy_score | mono_source_risk | uncertainty_penalty |
|---|---|---|---|---|---|---|---|
| SDC-VD0914690A | M-1430 | item:042342 | 0.125366 | high | 0.752613 | 1.000000 | 0.000000 |
| SDC-1450 | M-1810 | item:693710 | 0.123604 | high | 0.740030 | 1.000000 | 1.000000 |
| SDC-1450 | M-1430 | item:773474 | 0.120828 | high | 0.720202 | 1.000000 | 0.000000 |
| SDC-VD0993480A | M-1430 | item:344135 | 0.119402 | high | 0.710013 | 1.000000 | 0.000000 |
| SDC-VD0525412A | M-1430 | item:333362 | 0.116272 | high | 0.687657 | 1.000000 | 0.000000 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.115621 | high | 0.683004 | 1.000000 | 0.600000 |
| SDC-VD0914360C | M-1810 | item:338929 | 0.110456 | high | 0.646116 | 1.000000 | 0.000000 |
| SDC-VD0901566A | M-1810 | item:338928 | 0.109720 | high | 0.640861 | 1.000000 | 0.000000 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.109149 | high | 0.636780 | 1.000000 | 0.000000 |
| SDC-1450 | M-1810 | item:693055 | 0.108240 | high | 0.630289 | 1.000000 | 0.000000 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.107782 | high | 0.627017 | 1.000000 | 0.000000 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.106786 | high | 0.619902 | 1.000000 | 0.000000 |

Lecture:
- cette table pousse surtout les couples structurellement fragiles:
  mono-source, forte exposition aval, couverture plus faible, delai plus long, ou incertitude modele.

## 5) Couples avec plus forte probabilite proxy de choc service
| supplier_id | factory_id | item_id | p_service_hit_30d_proxy | service_hit_probability_band | impact_proxy_score | expected_fill_loss_proxy | expected_backlog_delta_proxy |
|---|---|---|---|---|---|---|---|
| SDC-1450 | M-1810 | item:693710 | 0.123604 | high | 1.000000 | 0.019295 | 28.942725 |
| SDC-VD0914360C | M-1810 | item:338929 | 0.071785 | medium | 0.649898 | 0.012540 | 18.809790 |
| SDC-VD0901566A | M-1810 | item:338928 | 0.071307 | medium | 0.649898 | 0.012540 | 18.809790 |
| SDC-1450 | M-1430 | item:773474 | 0.051242 | low | 0.424093 | 0.008183 | 12.274400 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.040231 | low | 0.320907 | 0.006192 | 9.287925 |
| SDC-VD0993480A | M-1430 | item:344135 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0525412A | M-1430 | item:333362 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |
| SDC-1450 | M-1810 | item:693055 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.000000 | very_low | 0.000000 | 0.000000 | 0.000000 |

Lecture:
- cette table distingue les couples qui ne sont pas seulement fragiles "sur le papier", mais qui **cassent vraiment** le service quand on les secoue.

## 6) Plus gros impacts simules en outage 5 jours
| supplier_id | factory_id | item_id | outage5d_fill_loss | outage5d_backlog_delta | outage5d_total_cost | supplier_count_for_item |
|---|---|---|---|---|---|---|
| SDC-1450 | M-1810 | item:693710 | 0.058988 | 88.481100 | 29240.938900 | 1 |
| SDC-1450 | M-1430 | item:773474 | 0.032732 | 49.097600 | 28549.870200 | 1 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.024768 | 37.151700 | 27168.748200 | 1 |
| SDC-VD0914360C | M-1810 | item:338929 | 0.000000 | 0.000000 | 28581.617400 | 1 |
| SDC-VD0901566A | M-1810 | item:338928 | 0.000000 | 0.000000 | 28587.179900 | 1 |
| SDC-VD0993480A | M-1430 | item:344135 | 0.000000 | 0.000000 | 28590.143400 | 1 |
| SDC-VD0525412A | M-1430 | item:333362 | 0.000000 | 0.000000 | 28544.348700 | 1 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.000000 | 0.000000 | 28145.133600 | 1 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.000000 | 0.000000 | 28157.829000 | 1 |
| SDC-1450 | M-1810 | item:693055 | 0.000000 | 0.000000 | 28157.826500 | 1 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.000000 | 0.000000 | 28142.054100 | 1 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.000000 | 0.000000 | 28142.062700 | 1 |

## 7) Plus gros impacts simules en delai x3
| supplier_id | factory_id | item_id | delayx3_fill_loss | delayx3_backlog_delta | delayx3_total_cost | lead_mean_days |
|---|---|---|---|---|---|---|
| SDC-1450 | M-1810 | item:693710 | 0.000000 | 0.000000 | 28723.546600 | 1.000000 |
| SDC-VD0914360C | M-1810 | item:338929 | 0.000000 | 0.000000 | 29421.821200 | 8.000000 |
| SDC-VD0901566A | M-1810 | item:338928 | 0.000000 | 0.000000 | 29455.703900 | 8.000000 |
| SDC-1450 | M-1430 | item:773474 | 0.000000 | 0.000000 | 28730.794000 | 8.000000 |
| SDC-VD0914690A | M-1430 | item:042342 | 0.000000 | 0.000000 | 72137.424200 | 8.000000 |
| SDC-VD0993480A | M-1430 | item:344135 | 0.000000 | 0.000000 | 29439.363400 | 8.000000 |
| SDC-VD0525412A | M-1430 | item:333362 | 0.000000 | 0.000000 | 29468.298000 | 8.000000 |
| SDC-VD0508918A | M-1430 | item:730384 | 0.000000 | 0.000000 | 28872.321700 | 8.000000 |
| SDC-VD0989480A | M-1810 | item:426331 | 0.000000 | 0.000000 | 28731.390700 | 8.000000 |
| SDC-1450 | M-1810 | item:693055 | 0.000000 | 0.000000 | 28723.998500 | 8.000000 |
| SDC-VD0520132A | M-1810 | item:049371 | 0.000000 | 0.000000 | 28724.784100 | 8.000000 |
| SDC-VD1095770A | M-1430 | item:734545 | 0.000000 | 0.000000 | 28729.203900 | 8.000000 |

Lecture:
- certains couples reagissent surtout a la rupture franche,
- d'autres supportent une rupture courte mais deviennent tres couteux quand le delai s'allonge.

## 8) Vue agregée par fournisseur
| supplier_id | material_count | max_pair_combined_proxy_risk_score | mean_p_incident_30d_proxy | mean_p_service_hit_30d_proxy | expected_backlog_30d_proxy_sum | materials |
|---|---|---|---|---|---|---|
| SDC-1450 | 3 | 0.883013 | 0.117557 | 0.058282 | 5.060536 | item:693055, item:693710, item:773474 |
| SDC-VD0914360C | 1 | 0.648196 | 0.110456 | 0.071785 | 2.077660 | item:338929 |
| SDC-VD0901566A | 1 | 0.645831 | 0.109720 | 0.071307 | 2.063819 | item:338928 |
| SDC-VD0914690A | 1 | 0.515175 | 0.125366 | 0.040231 | 1.164388 | item:042342 |
| SDC-VD0993480A | 1 | 0.319506 | 0.119402 | 0.000000 | 0.000000 | item:344135 |
| SDC-VD0525412A | 1 | 0.309446 | 0.116272 | 0.000000 | 0.000000 | item:333362 |
| SDC-VD0508918A | 1 | 0.307352 | 0.115621 | 0.000000 | 0.000000 | item:730384 |
| SDC-VD0989480A | 1 | 0.286551 | 0.109149 | 0.000000 | 0.000000 | item:426331 |
| SDC-VD0520132A | 2 | 0.282158 | 0.105439 | 0.000000 | 0.000000 | item:038005, item:049371 |
| SDC-VD1095770A | 1 | 0.278956 | 0.106786 | 0.000000 | 0.000000 | item:734545 |
| SDC-VD0520115A | 1 | 0.263277 | 0.101908 | 0.000000 | 0.000000 | item:708073 |
| SDC-VD1096202A | 1 | 0.259223 | 0.100647 | 0.000000 | 0.000000 | item:039668 |

Lecture:
- cette vue permet de prioriser les **fournisseurs** et pas seulement les couples fournisseur-matiere.
- un fournisseur multi-matieres peut remonter haut meme si chaque matiere seule est moyenne.

## 9) Ce qu'on peut deja dire proprement
1. Ce classement est utile pour une **priorisation provisoire** avant le score industriel 22 criteres.
2. Les couples mono-source fortement exposes a la demande restent logiquement en tete.
3. `item:693710` reste un cas special: visible dans le classement, mais une partie du signal depend de l'hypothese Gaillac.
4. `item:730384` peut remonter via son ambiguite d'unite/semantique, mais son impact operationnel simule reste plus faible que les matieres majeures.
5. Cette etude est plus utile pour la **priorisation relative** que pour donner un pourcentage "vrai" d'incident.

## 10) Limites et prochaine etape
- Sans historique fournisseur ni score 22 criteres, les probabilites restent des **proba proxy**.
- La prochaine etape naturelle est de remplacer la couche probabilite proxy par:
  - le score industriel fournisseur-matiere,
  - puis idealement des historiques OTIF / retard / qualite.
- Le bloc impact simule, lui, est deja reutilisable quasiment tel quel.
