# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/capacity_m1430_minus_15pct/input_case.json
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
- Total served: 1017.5
- Fill rate: 0.678333
- Ending backlog: 482.5
- Total produced: 1387.5
- Total shipped: 52859.4447
- Avg inventory: 7850.7606
- Ending inventory: 4965.5131
- Transport cost: 121.8
- Holding cost: 6290.3741
- Purchase cost (from order_terms sell_price): 685.2676
- Logistics cost (transport + holding): 6412.1741
- Total cost: 7097.4417
- Total external procured qty (unmodeled upstream): 46442.4077
- Total opening stock bootstrap qty: 12767.9186
- Total unreliable supplier loss qty: 0.0

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 282.5
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
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
