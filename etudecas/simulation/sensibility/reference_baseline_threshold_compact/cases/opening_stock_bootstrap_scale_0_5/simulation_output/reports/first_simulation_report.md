# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/sensibility/reference_baseline_threshold_compact/cases/opening_stock_bootstrap_scale_0_5/input_case.json
- Scenario: scn:BASE
- Horizon (days): 365
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 0.5
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
- Total served: 8715.646
- Fill rate: 0.500899
- Ending backlog: 8684.354
- Total produced: 38168.8967
- Total shipped: 102649.4913
- Avg inventory: 2036185.7957
- Ending inventory: 2030157.37
- Transport cost: 137120.4407
- Holding cost: 4815043.0023
- Purchase cost (from order_terms sell_price): 162799.0616
- Logistics cost (transport + holding): 4952163.4429
- Total cost: 5114962.5046
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 55764.4454
- Total estimated source replenished qty: 53815.2822
- Total estimated source rejected qty: 0.0
- Cost share holding / transport / purchase: 0.941364 / 0.026808 / 0.031828
- Total opening stock bootstrap qty: 2130150.4975
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 4057.9191
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 6649.2891
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 2035.0649
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
