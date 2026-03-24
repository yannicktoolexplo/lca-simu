# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\reference_baseline_explicit_30_25_20_structural\cases\demand_item_268967_low\input_case.json
- Scenario: scn:BASE
- Horizon (days): 365
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 30.0 / 25.0 / 20.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 1.0 / True
- Unmodeled supplier source mode: estimated_replenishment
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 8.0 / 1.0
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0

## KPIs
- Total demand: 10440.0
- Total served: 10440.0
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 10432.875
- Total shipped: 56411.2688
- Avg inventory: 4265969.7929
- Ending inventory: 5398785.9882
- Transport cost: 116738.3957
- Holding cost (capital tied-up): 3208788.8241
- Warehouse operating cost: 4125585.631
- Inventory risk cost (obsolescence/compliance proxy): 1833593.6138
- Legacy raw holding cost before split: 9167968.0689
- Purchase cost (from order_terms sell_price): 2331.8462
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 9284706.4646
- Total cost: 9287038.3108
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 29477.2419
- Total estimated source replenished qty: 555661.1571
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.345513 / 0.44423 / 0.197436 / 0.01257 / 0.000251
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 793728.5399
- Total explicit initialization pipeline qty: 4743476.8755
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 0.0
- Economic consistency status: warn
- Economic consistency warnings: ['transport_cost_share_below_2pct']

## Top backlog pairs
[]

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
