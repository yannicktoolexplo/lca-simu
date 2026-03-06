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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 23

## KPIs
- Total demand: 1500.0
- Total served: 1500.0
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 1500.0
- Total shipped: 58033.1003
- Avg inventory: 21984.0512
- Ending inventory: 14472.9037
- Transport cost: 4161.6116
- Holding cost: 20975.3762
- Purchase cost (from order_terms sell_price): 3165.8797
- Logistics cost (transport + holding): 25136.9878
- Total cost: 28302.8675
- Total external procured ordered qty: 56469.5564
- Total external procured arrived qty: 51399.8026
- Total external procured rejected qty (cap-limited): 22259.9154
- Total external procurement cost premium: 4228.6914
- Cost share holding / transport / purchase: 0.741104 / 0.147039 / 0.111857
- Total opening stock bootstrap qty: 29982.366
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

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
