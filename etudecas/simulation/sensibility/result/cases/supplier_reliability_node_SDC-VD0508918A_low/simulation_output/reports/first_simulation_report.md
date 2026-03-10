# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/result/cases/supplier_reliability_node_SDC-VD0508918A_low/input_case.json
- Scenario: scn:BASE
- Horizon (days): 365
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
- External procurement lead days: 5
- External procurement daily cap days: 1.6
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
- Total demand: 17400.0
- Total served: 15733.3876
- Fill rate: 0.904218
- Ending backlog: 1666.6124
- Total produced: 103536.9683
- Total shipped: 701950.1432
- Avg inventory: 1028085.7756
- Ending inventory: 1022315.608
- Transport cost: 348025.8963
- Holding cost: 14897491.0965
- Purchase cost (from order_terms sell_price): 55429.6887
- Logistics cost (transport + holding): 15245516.9928
- Total cost: 15300946.6815
- Total external procured ordered qty: 615685.2488
- Total external procured arrived qty: 605727.9225
- Total external procured rejected qty (cap-limited): 554918.1498
- Total external procurement cost premium: 56458.9286
- Cost share holding / transport / purchase: 0.973632 / 0.022745 / 0.003623
- Total opening stock bootstrap qty: 1064676.8487
- Total unreliable supplier loss qty: 29724.1205
- Total supplier capacity binding qty: 672742.3959
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 844.2502
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 822.3622
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
