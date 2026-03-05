# Analyse globale supply (synthese consolidee)

Date: 2026-03-05 (UTC)

## 1) Baseline actuelle (30 jours, modele economique ajuste)
- Fill rate: **0.945418** (1418.1264/1500.0)
- Backlog final: **81.8736**
- Cout total: **28723.7188** (holding=21768.5663, transport=3950.9269, purchase=3004.2256)
- Part des couts: holding=0.757860, transport=0.137549, purchase=0.104590
- Inventaire moyen: **22701.7116** | inventaire final: **14655.5045**
- Service journalier: **14** jours en sous-service, backlog max **90.5428** au jour **21**

## 2) Matieres d'entree les plus critiques (etat courant)
Definition pratique: criticite structurelle = consommation + mono-sourcing + delai (p95) + couverture.

| Rang | Factory | Item | Score | Conso totale | Nb fournisseurs | Couverture (jours) |
|---|---|---|---:|---:|---:|---:|
| 1 | M-1430 | item:042342 | 0.269 | 42997.924 | 1 | 9.687 |
| 2 | M-1430 | item:773474 | 0.185 | 6879.666 | 1 | 9.362 |
| 3 | M-1810 | item:693710 | 0.178 | 2314.444 | 1 | 7.701 |
| 4 | M-1430 | item:344135 | 0.172 | 712.570 | 1 | 8.786 |
| 5 | M-1430 | item:333362 | 0.171 | 712.570 | 1 | 9.196 |
| 6 | M-1810 | item:049371 | 0.171 | 1.070 | 1 | 8.489 |
| 7 | M-1810 | item:426331 | 0.171 | 7.838 | 1 | 8.760 |
| 8 | M-1430 | item:734545 | 0.170 | 5.701 | 1 | 8.984 |
| 9 | M-1810 | item:338929 | 0.170 | 712.575 | 1 | 9.959 |

## 3) Ce que revele l'analyse de sensibilite (OAT +/-20%)
- Fill rate: `supplier_stock_scale` (+0.260), `lead_time_scale` (-0.209), `demand_item_scale::item:268091` (-0.183), `demand_item_scale::item:268967` (-0.174), `capacity_node_scale::M-1810` (+0.142)
- Backlog: `supplier_stock_scale` (-4.512), `demand_item_scale::item:268091` (+3.970), `demand_item_scale::item:268967` (+3.835), `lead_time_scale` (+3.622), `capacity_node_scale::M-1810` (-2.455)
- Cout total: `capacity_node_scale::M-1430` (+0.921), `lead_time_scale` (+0.509), `demand_item_scale::item:268967` (-0.149), `transport_cost_scale` (+0.138), `supplier_stock_scale` (+0.073)

## 4) Ce que revele Monte Carlo (120 runs + baseline)
- p_fill_lt_0_90: **0.4132**
- p_fill_lt_0_85: **0.1322**
- p_backlog_gt_100: **0.5372**
- p_backlog_gt_200: **0.3058**
- p_cost_gt_24000: **0.9174**
- p_cost_gt_28000: **0.7190**
- Robustesse vs baseline:
  - p_fill_ge_baseline: **0.4050**
  - p_cost_le_baseline: **0.3223**
  - p_backlog_le_baseline: **0.4132**
  - p_fill_ge_baseline_and_cost_le_baseline: **0.1157**

## 5) Distribution des delais (reel simule, flux supplier->factory)
- N expeditions: **743**
- Delai moyen: **7.927 jours**
- Mediane: **7 jours**
- P95: **16 jours**
- Max observe: **26 jours**

| Tranche delai (jours) | Count | Part |
|---|---:|---:|
| 1-3 | 100 | 0.1346 |
| 4-6 | 207 | 0.2786 |
| 7-9 | 210 | 0.2826 |
| 10-12 | 115 | 0.1548 |
| 13-15 | 72 | 0.0969 |
| 16-20 | 32 | 0.0431 |
| 21-30 | 7 | 0.0094 |

## 6) What-if utiles pour le niveau de service (legacy)
Attention: `fill_rate_whatif_analysis.csv` n'est pas encore rejoue avec les nouveaux garde-fous economiques.
- `det_cap_120pct_plus_cust100`: fill_rate=0.993333, ending_backlog=10.0, stochastic=False
- `stoch_cust_init_200_each`: fill_rate=0.983333, ending_backlog=25.0, stochastic=True
- `stoch_cust_init_150_each`: fill_rate=0.916667, ending_backlog=125.0, stochastic=True
- `det_cap_130pct`: fill_rate=0.873333, ending_backlog=190.0, stochastic=False
- `baseline_det_60`: fill_rate=0.866667, ending_backlog=400.0, stochastic=False

## 7) Points de vigilance prioritaires
1. Mono-sourcing majoritaire sur les intrants critiques.
2. Queue de delai non-negligeable (P95=16j, max=26j).
3. Appro externe encore tres sollicitee (ordered/arrived elevés), meme bornee.
4. Arbitrage cout-service: la resilience se paie en stock/capacite/politique de pilotage.

## 8) Coherence des jeux d'analyse
- Campagnes alignees: sensibilite, montecarlo, full exploration, shocks, targeted plan.
- Baseline alignee: fill_rate=0.945418, backlog=81.8736, total_cost=28723.7188.
- `fill_rate_whatif_analysis.csv` reste legacy.

## 9) Exploration systeme large (757 runs)
- Composition: baseline=1, corners=256, random=500
- Mean fill rate: **0.6669** (baseline 0.945418)
- P(fill < 0.90): **0.9168**
- P(backlog > 100): **0.9313**
- P(fill >= baseline): **0.0555**

- Top correlations |corr|:
  - Fill: `factor::review_period_scale` (-0.507), `factor::demand_scale` (-0.429), `factor::supplier_stock_scale` (+0.421), `factor::supplier_reliability_scale` (+0.364), `demand_item::item:268967` (-0.251)
  - Backlog: `factor::demand_scale` (+0.608), `factor::review_period_scale` (+0.399), `demand_item::item:268967` (+0.342), `factor::supplier_stock_scale` (-0.322), `factor::supplier_reliability_scale` (-0.291)
  - Cout: `factor::lead_time_scale` (+0.498), `factor::capacity_scale` (+0.468), `factor::holding_cost_scale` (+0.384), `capacity_node::M-1430` (+0.342), `factor::external_procurement_daily_cap_days_scale` (+0.246)

## 10) Campagne de perturbations/chocs (55 scenarios)
- 55 scenarios executes, 0 echec.
Scenarios les plus degradants:
- `combo_extreme_black_swan`: fill=0.112177, backlog=3281.3953, cout=21225.5275
- `combo_systemic_stress`: fill=0.223371, backlog=2333.1040, cout=24839.0344
- `combo_supplier_crunch`: fill=0.417627, backlog=873.5598, cout=38409.4371
- `combo_logistics_strike`: fill=0.481107, backlog=778.3400, cout=53735.1567
- `review_period_scale_7d`: fill=0.538728, backlog=691.9086, cout=35266.3511
Scenarios les plus resilients:
- `demand_scale_down`: fill=1.000000, backlog=0.0000, cout=29422.2698
- `supplier_stock_scale_up_severe`: fill=1.000000, backlog=0.0000, cout=29496.6895
- `demand_drop_recovery_50`: fill=1.000000, backlog=0.0000, cout=32306.3012
- `combo_resilience_max`: fill=1.000000, backlog=0.0000, cout=51029.4450

## 11) Parametres du pire cas (exploration large)
- Run: `full_run_0703` | fill_rate=0.349634 | backlog=1195.9955 | cout=33622.0080
- Facteurs clefs: `demand_scale`=1.13931, `lead_time_scale`=1.138736, `review_period_scale`=6.0, `supplier_reliability_scale`=0.853576, `supplier_stock_scale`=0.981522, `capacity_scale`=0.991776, `external_procurement_daily_cap_days_scale`=1.527408, `external_procurement_lead_days_scale`=1.297422, `external_procurement_cost_multiplier_scale`=1.631393
- Demande item-level: `item:268091`=1.139726, `item:268967`=1.012403
- Capacite node-level: `M-1430`=0.958574, `M-1810`=0.840671
