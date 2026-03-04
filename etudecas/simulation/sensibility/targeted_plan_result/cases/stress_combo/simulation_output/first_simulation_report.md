# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/stress_combo/input_case.json
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
- Total demand: 1872.0
- Total served: 612.0645
- Fill rate: 0.326958
- Ending backlog: 1259.9355
- Total produced: 1334.3589
- Total shipped: 53560.4338
- Avg inventory: 9351.7489
- Ending inventory: 4826.524
- Transport cost: 108.3695
- Holding cost: 7907.0977
- Purchase cost (from order_terms sell_price): 658.8945
- Logistics cost (transport + holding): 8015.4672
- Total cost: 8674.3617
- Total external procured qty (unmodeled upstream): 56783.0773
- Total opening stock bootstrap qty: 18482.289
- Total unreliable supplier loss qty: 9451.8413

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 630.0
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 629.9355
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
