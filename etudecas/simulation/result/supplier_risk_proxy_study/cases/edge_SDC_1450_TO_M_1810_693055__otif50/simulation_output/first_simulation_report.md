# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/result/supplier_risk_proxy_study/cases/edge_SDC_1450_TO_M_1810_693055__otif50/input_case.json
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
- Total served: 1157.8498
- Fill rate: 0.778386
- Ending backlog: 329.6502
- Total produced: 2614.8876
- Total shipped: 46212.5436
- Avg inventory: 1045440.3223
- Ending inventory: 1032666.226
- Transport cost: 22359.0313
- Holding cost: 1248099.6132
- Purchase cost (from order_terms sell_price): 2761.1528
- Logistics cost (transport + holding): 1270458.6445
- Total cost: 1273219.7973
- Total external procured ordered qty: 43156.0345
- Total external procured arrived qty: 42678.4664
- Total external procured rejected qty (cap-limited): 18362.3692
- Total external procurement cost premium: 3340.2139
- Cost share holding / transport / purchase: 0.98027 / 0.017561 / 0.002169
- Total opening stock bootstrap qty: 1060029.4897
- Total unreliable supplier loss qty: 250.2798
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 179.4805
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 150.1697
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
