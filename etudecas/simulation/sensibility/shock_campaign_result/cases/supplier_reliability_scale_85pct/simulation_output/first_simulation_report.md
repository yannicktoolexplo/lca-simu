# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/shock_campaign_result/cases/supplier_reliability_scale_85pct/input_case.json
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
- Total served: 1110.3993
- Fill rate: 0.740266
- Ending backlog: 389.6007
- Total produced: 1425.1456
- Total shipped: 53362.4858
- Avg inventory: 22080.427
- Ending inventory: 17868.369
- Transport cost: 4280.3623
- Holding cost: 21253.7145
- Purchase cost (from order_terms sell_price): 3289.999
- Logistics cost (transport + holding): 25534.0768
- Total cost: 28824.0758
- Total external procured ordered qty: 63379.0142
- Total external procured arrived qty: 56220.6287
- Total external procured rejected qty (cap-limited): 22836.0981
- Total external procurement cost premium: 4707.5072
- Cost share holding / transport / purchase: 0.73736 / 0.1485 / 0.114141
- Total opening stock bootstrap qty: 29870.366
- Total unreliable supplier loss qty: 9416.9093
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 204.3719
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 185.2289
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
