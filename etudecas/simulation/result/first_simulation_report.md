# First simulation report

## Run setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Horizon (days): 11
- Nodes: 29
- Edges: 33
- Lanes (edge x item): 33
- Demand rows: 2
- Input material pairs tracked: 22
- Output product pairs tracked: 2 (M-1430 | item:268967, M-1810 | item:268091)
- Inputs non modelises par Relations_acteurs (non bloquants): 1 (M-1810 | item:693710)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0

## KPIs
- Total demand: 2640.0
- Total served: 2640.0
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 269.745
- Total shipped: 10184.8142
- Avg inventory: 79063.2387
- Ending inventory: 77537.9552
- Transport cost: 5286.7865
- Holding cost: 34787.825
- Total cost: 40074.6115

## Top backlog pairs
[]

## Files
- first_simulation_summary.json
- first_simulation_daily.csv
- production_input_stocks_daily.csv
- production_input_stocks_pivot.csv
- production_output_products_daily.csv
- production_input_stocks_by_material_*.png (etudecas/simulation/result/production_input_stocks_by_material_M-1430.png, etudecas/simulation/result/production_input_stocks_by_material_M-1810.png)
- production_output_products.png (etudecas/simulation/result/production_output_products.png)
- supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas/simulation/result/supply_graph_poc_geocoded_map_with_factory_hover.html)
