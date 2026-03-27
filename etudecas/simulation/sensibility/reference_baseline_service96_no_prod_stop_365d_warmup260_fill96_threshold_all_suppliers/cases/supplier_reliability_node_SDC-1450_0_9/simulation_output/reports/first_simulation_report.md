# First simulation report

## Run setup
- Input: C:\dev\lca-simu\etudecas\simulation\sensibility\reference_baseline_service96_no_prod_stop_365d_warmup260_fill96_threshold_all_suppliers\cases\supplier_reliability_node_SDC-1450_0_9\input_case.json
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
- Total served: 17057.875
- Fill rate: 0.939711
- Ending backlog: 1094.375
- Total produced: 105170.9267
- Total shipped: 759059.4456
- Avg inventory: 4658570.3474
- Ending inventory: 4827489.9727
- Transport cost: 2796401.4546
- Holding cost (capital tied-up): 3717440.6259
- Warehouse operating cost: 4779566.519
- Inventory risk cost (obsolescence/compliance proxy): 2124251.7862
- Legacy raw holding cost before split: 10621258.931
- Purchase cost (from order_terms sell_price): 25526.9608
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 13417660.3856
- Total cost: 13443187.3464
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 770865.295
- Total estimated source replenished qty: 774004.7683
- Total estimated source rejected qty: 30884345.9608
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.27653 / 0.355538 / 0.158017 / 0.208016 / 0.001899
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 168240.5218
- Total explicit initialization pipeline qty: 782660.9135
- Total unreliable supplier loss qty: 12433.3957
- Total supplier capacity binding qty: 624918.855
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 638.125
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 456.25
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
