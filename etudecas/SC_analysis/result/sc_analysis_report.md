# SC analysis from simulation results

## Run context
- Scenario: scn:BASE
- Horizon: 11 days
- Input graph: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json

## Service performance
- Fill rate: 1.0000
- Total demand: 2640.00
- Total served: 2640.00
- Ending backlog: 0.00
- Backlog days: 2
- Stockout days: 2 ([0, 1])
- Max backlog: 480.00 (day 1)
- Backlog clear day: 2

## Flow dynamics
- Total shipped: 10184.81
- Total arrived: 9223.09
- Total produced: 269.75
- Shipped spike days: []
- Demand volatility (std): 0.0000
- Shipped volatility (std): 688.7499
- Bullwhip proxy: None
- Arrivals/Shipped ratio: 0.9056
- Produced/Served ratio: 0.1022

## Inventory and costs
- Avg inventory: 79063.24
- Inventory p10 / p90: 77808.83 / 80570.00
- Ending inventory: 77537.96
- Total cost: 40074.61
- Holding cost: 34787.82 (86.81%)
- Transport cost: 5286.79 (13.19%)
- Avg daily cost: 3643.15
- Cost per served unit: 15.1798

## Model input signal
- Demand unique values observed: [240.0]
- Days simulated: 11

## Alerts
- Ruptures observées sur 2 jour(s): [0, 1].
- Le coût de stockage domine le coût total.
- Demande entièrement constante: la simulation ne teste pas la variabilité.
- Horizon court (<30 jours): vision partielle de la dynamique.

## Recommendations
- Le niveau de service est bon. Passer à des scénarios stress (retard fournisseur, hausse demande).
- Augmenter le stock de sécurité sur les couples critiques pour absorber le démarrage.
- Réduire les stocks initiaux et calibrer les politiques de réapprovisionnement.
- Ajouter une demande variable (step/seasonality) pour tester la robustesse.
- Allonger l'horizon (60-120 jours) pour observer les régimes stabilisés.

## Files
- sc_analysis_summary.json
- sc_analysis_report.md
- sc_analysis_daily_enriched.csv
