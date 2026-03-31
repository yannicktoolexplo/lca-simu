# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\result_reference_baseline_real_demand_target_calibrated_2026_03_30\cases\supplier_reliability_node_SDC-VD0525412A_low\input_case.json
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
- Total served: 3850924.2449
- Fill rate: 0.726253
- Ending backlog: 1451528.4694
- Total produced: 8551045.3199
- Total shipped: 61725071.1522
- Avg inventory: 25806127.9843
- Ending inventory: 27051859.5693
- Transport cost: 4908400.7344
- Holding cost (capital tied-up): 4302840.1203
- Warehouse operating cost: 5532223.0118
- Inventory risk cost (obsolescence/compliance proxy): 2458765.783
- Legacy raw holding cost before split: 12293828.915
- Purchase cost (from order_terms sell_price): 2876430.8862
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 17202229.6494
- Total cost: 20078660.5356
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 51505572.0644
- Total estimated source replenished qty: 51773087.1894
- Total estimated source rejected qty: 28404455.6882
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.214299 / 0.275527 / 0.122457 / 0.244459 / 0.143258
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 35076.3627
- Total explicit initialization pipeline qty: 0.0
- Total unreliable supplier loss qty: 1980043.6364
- Total supplier capacity binding qty: 1569564.7694
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 1220628.5403
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 230899.9291
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
