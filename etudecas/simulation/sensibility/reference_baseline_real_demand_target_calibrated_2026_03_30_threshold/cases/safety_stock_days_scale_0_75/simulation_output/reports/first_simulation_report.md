# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\reference_baseline_real_demand_target_calibrated_2026_03_30_threshold\cases\safety_stock_days_scale_0_75\input_case.json
- Scenario: scn:BASE
- Measured horizon (days): 365
- Warm-up (days): 260
- Total simulated timeline (days): 625
- Output profile: compact
- Safety stock policy (days): 5.25
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
- Total served: 4710056.1453
- Fill rate: 0.888279
- Ending backlog: 592396.569
- Total produced: 17838450.1839
- Total shipped: 126827509.5243
- Avg inventory: 19951719.2753
- Ending inventory: 20345584.3392
- Transport cost: 11148404.7903
- Holding cost (capital tied-up): 4169083.166
- Warehouse operating cost: 5360249.7848
- Inventory risk cost (obsolescence/compliance proxy): 2382333.2377
- Legacy raw holding cost before split: 11911666.1884
- Purchase cost (from order_terms sell_price): 4780417.5609
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 23060070.9787
- Total cost: 27840488.5396
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 104470715.3364
- Total estimated source replenished qty: 102964888.9636
- Total estimated source rejected qty: 27152002.4113
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.149749 / 0.192534 / 0.085571 / 0.400439 / 0.171707
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 35076.3627
- Total explicit initialization pipeline qty: 0.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 1555776.2428
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 343521.345
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 248875.224
  }
]

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
