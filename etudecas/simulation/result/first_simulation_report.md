# First simulation report

## Run setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Stochastic lead times: True
- Random seed: 42
- Nodes: 28
- Edges: 34
- Lanes (edge x item): 34
- Demand rows: 2
- Input material pairs tracked: 23
- Output product pairs tracked: 2 (M-1430 | item:268967, M-1810 | item:268091)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 1 (edge:SDC-1450_TO_M-1810_693710_Q)
- External upstream sourcing for unmodeled source pairs: 30
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 22

## KPIs
- Total demand: 1500.0
- Total served: 1317.1757
- Fill rate: 0.878117
- Ending backlog: 182.8243
- Total produced: 1425.1456
- Total shipped: 58109.3646
- Avg inventory: 23523.4618
- Ending inventory: 21375.3242
- Transport cost: 115.7222
- Holding cost: 22587.4055
- Purchase cost (from order_terms sell_price): 706.9129
- Logistics cost (transport + holding): 22703.1277
- Total cost: 23410.0406
- Total external procured qty (unmodeled upstream): 51757.1871
- Total opening stock bootstrap qty: 29870.366
- Total unreliable supplier loss qty: 0.0

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 103.1644
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 79.6599
  }
]

## Files
- first_simulation_summary.json
- first_simulation_daily.csv
- production_input_stocks_daily.csv
- production_input_consumption_daily.csv
- production_input_replenishment_arrivals_daily.csv
- production_input_replenishment_shipments_daily.csv
- production_input_stocks_pivot.csv
- production_output_products_daily.csv
- production_input_stocks_by_material_*.png (etudecas/simulation/result/production_input_stocks_by_material_M-1430.png, etudecas/simulation/result/production_input_stocks_by_material_M-1810.png)
- production_output_products.png (etudecas/simulation/result/production_output_products.png)
- supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas/simulation/result/supply_graph_poc_geocoded_map_with_factory_hover.html)
