# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/result/model_assumption_review/cases/policy_stock_buffered/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 10.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 6.0
- Production stock-gap gain: 0.2
- Production smoothing factor: 0.3
- Opening stock bootstrap scale: 1.0
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- External procurement enabled: True
- External procurement lead days: 4
- External procurement daily cap days: 2.0
- External procurement min daily cap qty: 0.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 32
- Edges: 38
- Lanes (edge x item): 38
- Demand rows: 2
- Input material pairs tracked: 24
- Output product pairs tracked: 3 (M-1430 | item:268967, M-1810 | item:268091, SDC-1450 | item:773474)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 1 (edge:SDC-1450_TO_M-1810_007923_Q)
- External upstream sourcing for unmodeled source pairs: 33
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 24

## KPIs
- Total demand: 1487.5
- Total served: 1136.7997
- Fill rate: 0.764235
- Ending backlog: 350.7003
- Total produced: 2370.1921
- Total shipped: 45036.7141
- Avg inventory: 1045789.9855
- Ending inventory: 1039775.4187
- Transport cost: 21766.8195
- Holding cost: 1248598.626
- Purchase cost (from order_terms sell_price): 2737.7195
- Logistics cost (transport + holding): 1270365.4455
- Total cost: 1273103.165
- Total external procured ordered qty: 44570.813
- Total external procured arrived qty: 44300.813
- Total external procured rejected qty (cap-limited): 19063.5
- Total external procurement cost premium: 3401.4056
- Cost share holding / transport / purchase: 0.980752 / 0.017097 / 0.00215
- Total opening stock bootstrap qty: 1060141.4897
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 181.9503
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 168.75
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
- production_demand_service_daily.csv
- production_constraint_daily.csv
- production_supplier_shipments_daily.csv
- production_supplier_stocks_daily.csv
- production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
