# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/resilience_combo/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 14.0
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 24

## KPIs
- Total demand: 1487.5
- Total served: 1152.3751
- Fill rate: 0.774706
- Ending backlog: 335.1249
- Total produced: 2818.4593
- Total shipped: 49829.5155
- Avg inventory: 1053833.2946
- Ending inventory: 1039384.9349
- Transport cost: 24085.1277
- Holding cost: 1256579.7354
- Purchase cost (from order_terms sell_price): 2899.4673
- Logistics cost (transport + holding): 1280664.8631
- Total cost: 1283564.3304
- Total external procured ordered qty: 44995.926
- Total external procured arrived qty: 44302.6825
- Total external procured rejected qty (cap-limited): 17207.3516
- Total external procurement cost premium: 3482.4277
- Cost share holding / transport / purchase: 0.978977 / 0.018764 / 0.002259
- Total opening stock bootstrap qty: 1068172.9187
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 179.1247
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 156.0002
  }
]

## Files
- first_simulation_summary.json
- first_simulation_daily.csv
- production_input_stocks_daily.csv
- production_input_consumption_daily.csv
- production_input_replenishment_arrivals_daily.csv
- production_input_replenishment_shipments_daily.csv
- production_input_stocks_pivot.csv
- production_output_products_daily.csv
- production_demand_service_daily.csv
- production_constraint_daily.csv
- production_supplier_shipments_daily.csv
- production_supplier_stocks_daily.csv
- production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
