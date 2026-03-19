# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/result/model_assumption_review/cases/policy_reactive_mrp/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 6.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 2.0
- Production stock-gap gain: 0.6
- Production smoothing factor: 0.05
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
- Total served: 1225.0
- Fill rate: 0.823529
- Ending backlog: 262.5
- Total produced: 4606.9093
- Total shipped: 54451.0806
- Avg inventory: 1043171.7615
- Ending inventory: 1024236.759
- Transport cost: 26510.1664
- Holding cost: 1245343.439
- Purchase cost (from order_terms sell_price): 3293.3093
- Logistics cost (transport + holding): 1271853.6054
- Total cost: 1275146.9147
- Total external procured ordered qty: 48166.1266
- Total external procured arrived qty: 44641.5
- Total external procured rejected qty (cap-limited): 19363.5
- Total external procurement cost premium: 3727.8535
- Cost share holding / transport / purchase: 0.976627 / 0.02079 / 0.002583
- Total opening stock bootstrap qty: 1060029.4897
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 143.75
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 118.75
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
