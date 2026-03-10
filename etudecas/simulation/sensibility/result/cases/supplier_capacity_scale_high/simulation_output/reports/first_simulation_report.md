# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/result/cases/supplier_capacity_scale_high/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 23

## KPIs
- Total demand: 1487.5
- Total served: 1162.1606
- Fill rate: 0.781284
- Ending backlog: 325.3394
- Total produced: 2610.2267
- Total shipped: 45979.3243
- Avg inventory: 1044162.8445
- Ending inventory: 1033037.4477
- Transport cost: 22234.4145
- Holding cost: 1246482.8653
- Purchase cost (from order_terms sell_price): 2745.9355
- Logistics cost (transport + holding): 1268717.2798
- Total cost: 1271463.2153
- Total external procured ordered qty: 42861.7998
- Total external procured arrived qty: 42489.9504
- Total external procured rejected qty (cap-limited): 18129.5504
- Total external procurement cost premium: 3315.199
- Cost share holding / transport / purchase: 0.980353 / 0.017487 / 0.00216
- Total opening stock bootstrap qty: 1060029.4897
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 0.0
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 200.1697
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 125.1697
  }
]

## Files
- summaries/first_simulation_summary.json
- data/first_simulation_daily.csv
- data/production_input_stocks_daily.csv
- data/production_input_consumption_daily.csv
- data/production_input_replenishment_arrivals_daily.csv
- data/production_input_replenishment_shipments_daily.csv
- data/production_input_stocks_pivot.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- data/production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
