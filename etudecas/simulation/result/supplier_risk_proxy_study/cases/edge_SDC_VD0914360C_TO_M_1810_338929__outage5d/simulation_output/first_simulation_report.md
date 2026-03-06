# First simulation report

## Run setup
- Input: /workspaces/lca-simu/etudecas/simulation/result/supplier_risk_proxy_study/cases/edge_SDC_VD0914360C_TO_M_1810_338929__outage5d/input_case.json
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
- Total served: 1446.8756
- Fill rate: 0.964584
- Ending backlog: 53.1244
- Total produced: 1425.1456
- Total shipped: 55382.4077
- Avg inventory: 22377.5694
- Ending inventory: 15926.0432
- Transport cost: 3948.3809
- Holding cost: 21665.0442
- Purchase cost (from order_terms sell_price): 2968.1924
- Logistics cost (transport + holding): 25613.4251
- Total cost: 28581.6174
- Total external procured ordered qty: 53306.6535
- Total external procured arrived qty: 49053.8304
- Total external procured rejected qty (cap-limited): 20258.3299
- Total external procurement cost premium: 3982.8311
- Cost share holding / transport / purchase: 0.758006 / 0.138144 / 0.10385
- Total opening stock bootstrap qty: 29870.366
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 47.7044
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 5.42
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
