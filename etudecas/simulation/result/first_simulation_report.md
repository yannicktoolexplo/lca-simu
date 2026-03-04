# First simulation report

## Run setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
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
- Total served: 1100.0
- Fill rate: 0.733333
- Ending backlog: 400.0
- Total produced: 1500.0
- Total shipped: 61192.9362
- Avg inventory: 8081.6759
- Ending inventory: 4937.9023
- Transport cost: 121.8
- Holding cost: 6526.9631
- Purchase cost (from order_terms sell_price): 744.0429
- Logistics cost (transport + holding): 6648.7631
- Total cost: 7392.806
- Total external procured qty (unmodeled upstream): 54542.0385
- Total opening stock bootstrap qty: 14935.183
- Total unreliable supplier loss qty: 0.0

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 200.0
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 200.0
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
