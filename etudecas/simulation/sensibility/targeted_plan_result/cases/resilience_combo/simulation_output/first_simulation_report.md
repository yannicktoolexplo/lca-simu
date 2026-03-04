# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/resilience_combo/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 14.0
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
- Total served: 1210.0
- Fill rate: 0.806667
- Ending backlog: 290.0
- Total produced: 1650.0
- Total shipped: 67312.2299
- Avg inventory: 9613.4733
- Ending inventory: 6127.6925
- Transport cost: 133.98
- Holding cost: 7675.3925
- Purchase cost (from order_terms sell_price): 818.4472
- Logistics cost (transport + holding): 7809.3725
- Total cost: 8627.8196
- Total external procured qty (unmodeled upstream): 59870.2423
- Total opening stock bootstrap qty: 16428.7013
- Total unreliable supplier loss qty: 0.0

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 145.0
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 145.0
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
