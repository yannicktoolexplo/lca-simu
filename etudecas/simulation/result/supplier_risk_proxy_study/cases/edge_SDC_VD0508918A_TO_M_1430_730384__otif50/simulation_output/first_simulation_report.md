# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/result/supplier_risk_proxy_study/cases/edge_SDC_VD0508918A_TO_M_1430_730384__otif50/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
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
- Total served: 1447.9172
- Fill rate: 0.965278
- Ending backlog: 52.0828
- Total produced: 1425.1456
- Total shipped: 55409.3668
- Avg inventory: 22943.2134
- Ending inventory: 15829.7029
- Transport cost: 3954.2852
- Holding cost: 22114.9632
- Purchase cost (from order_terms sell_price): 3006.2338
- Logistics cost (transport + holding): 26069.2483
- Total cost: 29075.4821
- Total external procured ordered qty: 53465.1295
- Total external procured arrived qty: 49230.0625
- Total external procured rejected qty (cap-limited): 20059.857
- Total external procurement cost premium: 4007.1524
- Cost share holding / transport / purchase: 0.760605 / 0.136001 / 0.103394
- Total opening stock bootstrap qty: 29870.366
- Total unreliable supplier loss qty: 130.0483
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 50.6599
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 1.4229
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
