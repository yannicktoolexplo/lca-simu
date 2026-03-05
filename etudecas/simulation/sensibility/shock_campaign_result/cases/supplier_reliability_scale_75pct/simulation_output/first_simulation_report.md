# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/shock_campaign_result/cases/supplier_reliability_scale_75pct/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
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
- Nodes: 28
- Edges: 34
- Lanes (edge x item): 34
- Demand rows: 2
- Input material pairs tracked: 23
- Output product pairs tracked: 2 (M-1430 | item:268967, M-1810 | item:268091)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 1 (edge:SDC-1450_TO_M-1810_693710_Q)
- External upstream sourcing for unmodeled source pairs: 30
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 22

## KPIs
- Total demand: 1500.0
- Total served: 979.1767
- Fill rate: 0.652784
- Ending backlog: 520.8233
- Total produced: 1425.1456
- Total shipped: 53466.4497
- Avg inventory: 20973.4723
- Ending inventory: 13433.3303
- Transport cost: 4583.6545
- Holding cost: 20266.8853
- Purchase cost (from order_terms sell_price): 3561.6907
- Logistics cost (transport + holding): 24850.5399
- Total cost: 28412.2305
- Total external procured ordered qty: 70944.7133
- Total external procured arrived qty: 64515.6244
- Total external procured rejected qty (cap-limited): 24473.6496
- Total external procurement cost premium: 5291.7822
- Cost share holding / transport / purchase: 0.713316 / 0.161327 / 0.125358
- Total opening stock bootstrap qty: 29870.366
- Total unreliable supplier loss qty: 17822.1499
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 266.7853
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 254.038
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
- production_supplier_shipments_daily.csv
- production_supplier_stocks_daily.csv
- production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
