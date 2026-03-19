# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/sensibility/reference_baseline_threshold_compact/cases/supplier_lead_time_node_SDC-VD0914690A_1_5/input_case.json
- Scenario: scn:BASE
- Horizon (days): 365
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Unmodeled supplier source mode: estimated_replenishment
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- External procurement enabled: False
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 25

## KPIs
- Total demand: 17400.0
- Total served: 17184.375
- Fill rate: 0.987608
- Ending backlog: 215.625
- Total produced: 100364.662
- Total shipped: 167775.6221
- Avg inventory: 8287822.7536
- Ending inventory: 8020169.409
- Transport cost: 75632.8295
- Holding cost: 19170695.2545
- Purchase cost (from order_terms sell_price): 14549.3157
- Logistics cost (transport + holding): 19246328.084
- Total cost: 19260877.3997
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 49583.9948
- Total estimated source replenished qty: 47801.4043
- Total estimated source rejected qty: 0.0
- Cost share holding / transport / purchase: 0.995318 / 0.003927 / 0.000755
- Total opening stock bootstrap qty: 8559987.1898
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 0.0
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 119.6875
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 95.9375
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
