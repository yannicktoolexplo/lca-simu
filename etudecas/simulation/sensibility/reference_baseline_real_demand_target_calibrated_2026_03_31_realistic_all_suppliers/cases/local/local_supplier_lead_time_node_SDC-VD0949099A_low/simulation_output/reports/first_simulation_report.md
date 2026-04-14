# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\reference_baseline_real_demand_target_calibrated_2026_03_31_realistic_all_suppliers\cases\local\local_supplier_lead_time_node_SDC-VD0949099A_low\input_case.json
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
- Total served: 4708974.5176
- Fill rate: 0.888075
- Ending backlog: 593478.1966
- Total produced: 17869743.232
- Total shipped: 127074616.6123
- Avg inventory: 19777948.4634
- Ending inventory: 18945822.4203
- Transport cost: 11167921.4643
- Holding cost (capital tied-up): 4196600.8367
- Warehouse operating cost: 5395629.6472
- Inventory risk cost (obsolescence/compliance proxy): 2398057.621
- Legacy raw holding cost before split: 11990288.1049
- Purchase cost (from order_terms sell_price): 4790533.5394
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 23158209.5692
- Total cost: 27948743.1087
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 104693283.3055
- Total estimated source replenished qty: 103072199.171
- Total estimated source rejected qty: 28206355.8413
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.150153 / 0.193054 / 0.085802 / 0.399586 / 0.171404
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 35076.3627
- Total explicit initialization pipeline qty: 0.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 1580070.6283
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 342591.8672
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 250886.3295
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
