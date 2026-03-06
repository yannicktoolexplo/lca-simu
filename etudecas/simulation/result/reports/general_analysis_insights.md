# Rapport d'insights: Sensibilite + Monte Carlo (30 jours)

Date: 2026-03-04 (UTC)

## 1) Baseline 30 jours
- `sim_days = 30`
- `total_demand = 1500`, `total_served = 1100`, `fill_rate = 0.733333`
- `ending_backlog = 400`
- `total_cost = 7392.806`
- `avg_inventory = 8081.6759`

Lecture:
- Le systeme est encore contraint (backlog final important), mais le service est nettement meilleur qu'en horizon court.

## 2) Structure des couts baseline (30 jours)
- `holding = 6526.9631` (~88.3%)
- `transport = 121.8` (~1.6%)
- `purchase = 744.0429` (~10.1%)

Lecture:
- Sur cet horizon et ce parametrage, le cout est surtout porte par le stock.

## 3) Qualite methodologique
- Sensibilite OAT: 18/18 cas executes, 18 succes.
- Test de determinisme: baseline vs baseline_repeat = 0 ecart sur tous les KPI.
- Monte Carlo: 121 runs (baseline + 120 tirages), 121 succes.

## 4) Drivers du service (fill rate)
Sensibilite normalisee (+/-20%):
- `capacity_node_scale::M-1430`: `+0.466`
- `capacity_node_scale::M-1810`: `+0.466`
- `lead_time_scale`: `-0.455`
- `demand_item_scale::item:268091`: `-0.429`
- `demand_item_scale::item:268967`: `-0.429`

Lecture:
- Le service est pilote par l'equilibre capacite/demande et les delais.

## 5) Drivers backlog et cout
Backlog (sensibilite):
- `demand_item_scale::*`: `+1.688`
- `capacity_node_scale::*`: `-1.281`
- `lead_time_scale`: `+1.250`

Cout total (sensibilite):
- `supplier_stock_scale`: `+0.669`
- `lead_time_scale`: `+0.656`
- `capacity_node_scale::M-1430`: `+0.272`

Lecture:
- Le backlog devient tres non-lineaire sur 30 jours.
- Le cout total est principalement sensible au stock fournisseur et aux delais.

## 6) Monte Carlo (30 jours)
Distribution des KPI (121 runs):
- Fill rate: baseline `0.7333`, moyenne `0.7124`, P05 `0.6063`, P95 `0.8655`
- Ending backlog: baseline `400`, moyenne `441.8`, P05 `191.2`, P95 `663.2`
- Total cost: baseline `7392.8`, moyenne `7968.0`, P05 `6460.2`, P95 `9730.1`

Probabilites utiles:
- `P(fill_rate >= baseline)` = `36.4%`
- `P(total_cost <= baseline)` = `31.4%`
- `P(ending_backlog <= baseline)` = `36.4%`
- `P(fill_rate >= baseline ET total_cost <= baseline)` = `14.9%`

Lecture:
- La baseline est encore plutot favorable, mais moins "exceptionnelle" qu'en 11 jours.

## 7) Frontiere cout-service observee
Points non domines (extraits):
- `run_0012`: cout `5930.3915`, fill `0.651354`
- `run_0050`: cout `6076.9945`, fill `0.746801`
- `run_0064`: cout `6174.0580`, fill `0.802190`
- `run_0067`: cout `6460.1765`, fill `0.864465`
- `run_0032`: cout `8812.3706`, fill `0.889238`

Lecture:
- Il existe des reglages strictement meilleurs que la baseline actuelle (cout plus bas et service plus haut).

## 8) Recommandations
1. Prioriser capacite effective + reduction lead time (impact direct service/backlog).
2. Piloter le stock fournisseur (driver cout principal en sensibilite).
3. Utiliser les points non domines Monte Carlo pour definir une baseline robuste.
