# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/annual_realistic_result/cases/local/local_demand_item_item_268091_low/input_case.json
- Scenario: scn:BASE
- Horizon (days): 365
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- External procurement enabled: True
- External procurement lead days: 5
- External procurement daily cap days: 1.6
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 24

## KPIs
- Total demand: 16530.0
- Total served: 14946.0948
- Fill rate: 0.90418
- Ending backlog: 1583.9052
- Total produced: 102694.576
- Total shipped: 696045.1651
- Avg inventory: 1029891.3154
- Ending inventory: 1020904.0529
- Transport cost: 346084.6387
- Holding cost: 14921978.7632
- Purchase cost (from order_terms sell_price): 54299.2344
- Logistics cost (transport + holding): 15268063.4019
- Total cost: 15322362.6363
- Total external procured ordered qty: 610125.9202
- Total external procured arrived qty: 600784.4017
- Total external procured rejected qty (cap-limited): 544124.6453
- Total external procurement cost premium: 55540.4032
- Cost share holding / transport / purchase: 0.973869 / 0.022587 / 0.003544
- Total opening stock bootstrap qty: 1064676.8487
- Total unreliable supplier loss qty: 29001.8819
- Total supplier capacity binding qty: 668460.4642
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 866.1382
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 717.767
  }
]

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
