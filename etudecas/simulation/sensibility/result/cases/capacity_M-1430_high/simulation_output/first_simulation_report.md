# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/result/cases/capacity_M-1430_high/input_case.json
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
- Total served: 1195.0
- Fill rate: 0.796667
- Ending backlog: 305.0
- Total produced: 1650.0
- Total shipped: 72259.2583
- Avg inventory: 8403.7931
- Ending inventory: 4936.8879
- Transport cost: 121.8
- Holding cost: 6859.4915
- Purchase cost (from order_terms sell_price): 822.41
- Logistics cost (transport + holding): 6981.2915
- Total cost: 7803.7015
- Total external procured qty (unmodeled upstream): 65352.3462
- Total opening stock bootstrap qty: 17824.8689
- Total unreliable supplier loss qty: 0.0

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 200.0
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 105.0
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
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
