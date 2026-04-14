# First simulation report

## Run setup
- Input: C:\dev\lca-simu\etudecas\simulation\sensibility\reference_baseline_service96_no_prod_stop_365d_warmup260_fill96_threshold_all_suppliers\cases\supplier_reliability_scale_0_9\input_case.json
- Scenario: scn:BASE
- Measured horizon (days): 365
- Warm-up (days): 260
- Total simulated timeline (days): 625
- Output profile: compact
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 3.0 / 6.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 0.18 / True
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
- Total demand: 17400.0
- Total served: 13798.6537
- Fill rate: 0.677784
- Ending backlog: 6559.8412
- Total produced: 105158.4267
- Total shipped: 801243.0031
- Avg inventory: 4549797.9518
- Ending inventory: 4699182.7515
- Transport cost: 2946731.4674
- Holding cost (capital tied-up): 3701949.2546
- Warehouse operating cost: 4759649.0417
- Inventory risk cost (obsolescence/compliance proxy): 2115399.5741
- Legacy raw holding cost before split: 10576997.8704
- Purchase cost (from order_terms sell_price): 26099.8339
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 13523729.3377
- Total cost: 13549829.1716
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 777080.9373
- Total estimated source replenished qty: 777831.3231
- Total estimated source rejected qty: 45326520.5984
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.27321 / 0.35127 / 0.15612 / 0.217474 / 0.001926
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 168240.5218
- Total explicit initialization pipeline qty: 782660.9135
- Total unreliable supplier loss qty: 89027.0003
- Total supplier capacity binding qty: 1675815.125
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 3391.5487
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 3168.2925
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
