# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\reference_baseline_real_demand_target_calibrated_2026_03_31_realistic_all_suppliers\cases\local\local_lead_time_scale_low\input_case.json
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
- Total served: 4711733.9579
- Fill rate: 0.888595
- Ending backlog: 590718.7563
- Total produced: 17858383.4872
- Total shipped: 126821127.7985
- Avg inventory: 18410958.2613
- Ending inventory: 16634410.8062
- Transport cost: 11135805.8515
- Holding cost (capital tied-up): 3876604.297
- Warehouse operating cost: 4984205.5247
- Inventory risk cost (obsolescence/compliance proxy): 2215202.4554
- Legacy raw holding cost before split: 11076012.2772
- Purchase cost (from order_terms sell_price): 4739950.3635
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 22211818.1287
- Total cost: 26951768.4922
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 104396208.5233
- Total estimated source replenished qty: 102650309.1025
- Total estimated source rejected qty: 663534.8724
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.143835 / 0.184931 / 0.082191 / 0.413175 / 0.175868
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 35076.3627
- Total explicit initialization pipeline qty: 0.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 4947675.835
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 351993.8738
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 238724.8825
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
