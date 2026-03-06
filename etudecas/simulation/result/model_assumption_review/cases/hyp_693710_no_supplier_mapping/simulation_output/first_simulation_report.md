# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/result/model_assumption_review/cases/hyp_693710_no_supplier_mapping/input_case.json
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
- Nodes: 28
- Edges: 33
- Lanes (edge x item): 33
- Demand rows: 2
- Input material pairs tracked: 22
- Output product pairs tracked: 2 (M-1430 | item:268967, M-1810 | item:268091)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 0 (none)
- External upstream sourcing for unmodeled source pairs: 29
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 22

## KPIs
- Total demand: 1500.0
- Total served: 1165.5573
- Fill rate: 0.777038
- Ending backlog: 334.4427
- Total produced: 928.0877
- Total shipped: 51091.5281
- Avg inventory: 20622.5933
- Ending inventory: 14014.4379
- Transport cost: 3720.9237
- Holding cost: 21723.1926
- Purchase cost (from order_terms sell_price): 2362.099
- Logistics cost (transport + holding): 25444.1162
- Total cost: 27806.2152
- Total external procured ordered qty: 52164.951
- Total external procured arrived qty: 48240.2726
- Total external procured rejected qty (cap-limited): 19467.0278
- Total external procurement cost premium: 3576.6257
- Cost share holding / transport / purchase: 0.781235 / 0.133816 / 0.084949
- Total opening stock bootstrap qty: 29870.366
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 330.4828
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 3.96
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
