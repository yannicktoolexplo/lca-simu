# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json
- Scenario: scn:BASE
- Measured horizon (days): 365
- Warm-up (days): 14
- Total simulated timeline (days): 379
- Output profile: compact
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 1.0 / 3.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 0.0 / False
- Unmodeled supplier source mode: estimated_replenishment
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
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
- Total demand: 5302452.7143
- Total served: 5302452.7143
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 53653600.0
- Total shipped: 324450554.9552
- Avg inventory: 536213260.1647
- Ending inventory: 611754324.5748
- Transport cost: 34491669.0494
- Holding cost (capital tied-up): 46637363.281
- Warehouse operating cost: 59962324.2184
- Inventory risk cost (obsolescence/compliance proxy): 26649921.8748
- Legacy raw holding cost before split: 133249609.3742
- Purchase cost (from order_terms sell_price): 52809696.1593
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 167741278.4237
- Total cost: 220550974.5829
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 281796609.5267
- Total estimated source replenished qty: 277232022.4273
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.211458 / 0.271875 / 0.120833 / 0.156389 / 0.239444
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 282432714.8916
- Total explicit initialization pipeline qty: 0.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 95229321118.4728
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Files
- summaries/first_simulation_summary.json
- data/production_input_stocks_daily.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- Additional detailed CSVs: skipped in compact mode
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
