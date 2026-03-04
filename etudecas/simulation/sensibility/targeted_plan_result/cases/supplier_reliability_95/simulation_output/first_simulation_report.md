# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/supplier_reliability_95/input_case.json
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
- Total served: 989.1875
- Fill rate: 0.659458
- Ending backlog: 510.8125
- Total produced: 1493.4211
- Total shipped: 60586.0271
- Avg inventory: 8008.1985
- Ending inventory: 4809.3611
- Transport cost: 121.3726
- Holding cost: 6516.5186
- Purchase cost (from order_terms sell_price): 739.7346
- Logistics cost (transport + holding): 6637.8912
- Total cost: 7377.6258
- Total external procured qty (unmodeled upstream): 57070.117
- Total opening stock bootstrap qty: 14935.183
- Total unreliable supplier loss qty: 3188.7383

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 256.0
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 254.8125
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
