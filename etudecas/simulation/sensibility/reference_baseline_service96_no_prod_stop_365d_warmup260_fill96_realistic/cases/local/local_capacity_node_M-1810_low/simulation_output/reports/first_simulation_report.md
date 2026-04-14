# First simulation report

## Run setup
- Input: C:\dev\lca-simu\etudecas\simulation\sensibility\reference_baseline_service96_no_prod_stop_365d_warmup260_fill96_realistic\cases\local\local_capacity_node_M-1810_low\input_case.json
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
- Total served: 17423.75
- Fill rate: 0.95565
- Ending backlog: 808.6
- Total produced: 105499.3017
- Total shipped: 787966.0078
- Avg inventory: 4655425.3304
- Ending inventory: 4810200.9571
- Transport cost: 2908936.0759
- Holding cost (capital tied-up): 3720090.2707
- Warehouse operating cost: 4782973.2052
- Inventory risk cost (obsolescence/compliance proxy): 2125765.869
- Legacy raw holding cost before split: 10628829.3448
- Purchase cost (from order_terms sell_price): 25939.0775
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 13537765.4207
- Total cost: 13563704.4981
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 769050.8422
- Total estimated source replenished qty: 769843.4364
- Total estimated source rejected qty: 33722244.1558
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.274268 / 0.35263 / 0.156725 / 0.214465 / 0.001912
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 168156.3118
- Total explicit initialization pipeline qty: 782421.9154
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 674741.2492
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 488.85
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 319.75
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
