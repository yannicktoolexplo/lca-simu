# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\pipeline_search\supply_graph_reference_baseline_explicit_5_5_5_fr60_seedfalse_dc08_fi02.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 2.0 / 5.0 / 8.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 0.6 / False
- Unmodeled supplier source mode: estimated_replenishment
- Stochastic lead times: True
- Random seed: 4
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
- Total demand: 1487.5
- Total served: 1487.5
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 14052.1073
- Total shipped: 244703.0562
- Avg inventory: 274969.95
- Ending inventory: 470888.6656
- Transport cost: 14007881.9522
- Holding cost (capital tied-up): 14787.1086
- Warehouse operating cost: 19011.9967
- Inventory risk cost (obsolescence/compliance proxy): 8449.7763
- Legacy raw holding cost before split: 42248.8816
- Purchase cost (from order_terms sell_price): 2594102.467
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 14050130.8338
- Total cost: 16644233.3009
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 739194.2502
- Total estimated source replenished qty: 226827.5768
- Total estimated source rejected qty: 54878324.1064
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.000888 / 0.001142 / 0.000508 / 0.841606 / 0.155856
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 55482.542
- Total explicit initialization pipeline qty: 2529781.5736
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 4179.2739
- Economic consistency status: warn
- Economic consistency warnings: ['warehouse_operating_cost_share_below_10pct', 'inventory_risk_cost_share_below_5pct']

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
