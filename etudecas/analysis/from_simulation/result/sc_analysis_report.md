# SC analysis from simulation results

## Run context
- Scenario: scn:BASE
- Horizon: 30 days
- Input graph: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json

## Service performance
- Fill rate: 0.7877
- Total demand: 1487.50
- Total served: 1171.65
- Ending backlog: 315.85
- Backlog days: 30
- Stockout days: 20 ([0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 12, 13, 15, 16, 19, 23, 24, 25, 27, 29])
- Max backlog: 365.89 (day 13)
- Backlog clear day: None

## Flow dynamics
- Total shipped: 45988.65
- Total arrived: 15989.34
- Total produced: 2610.23
- Shipped spike days: []
- Demand volatility (std): 6.1942
- Shipped volatility (std): 1101.0842
- Bullwhip proxy: 177.76065765606435
- Arrivals/Shipped ratio: 0.3477
- Produced/Served ratio: 2.2278

## Inventory and costs
- Avg inventory: 1045717.08
- Inventory p10 / p90: 1034246.60 / 1061923.10
- Ending inventory: 1035949.22
- Total cost: 1273360.32
- Holding cost: 1248373.79 (98.04%)
- Transport cost: 22239.97 (1.75%)
- Avg daily cost: 42445.34
- Cost per served unit: 1086.8072

## Model input signal
- Demand unique values observed: [40.0, 45.0, 47.5, 50.0, 52.5, 55.0, 60.0]
- Days simulated: 30

## Alerts
- Ruptures observées sur 20 jour(s): [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 12, 13, 15, 16, 19, 23, 24, 25, 27, 29].
- Le coût de stockage domine le coût total.
- Signal bullwhip potentiel (proxy=177.76).

## Recommendations
- Augmenter le stock de sécurité sur les couples critiques pour absorber le démarrage.
- Réduire les stocks initiaux et calibrer les politiques de réapprovisionnement.
- Limiter la variabilité des expéditions via politique de lissage.

## Files
- sc_analysis_summary.json
- sc_analysis_report.md
- sc_analysis_daily_enriched.csv
