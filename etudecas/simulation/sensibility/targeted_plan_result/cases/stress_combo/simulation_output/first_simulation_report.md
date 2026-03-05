# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/stress_combo/input_case.json
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
- Total demand: 1647.36
- Total served: 1009.4812
- Fill rate: 0.612787
- Ending backlog: 637.8788
- Total produced: 1350.0
- Total shipped: 50987.0763
- Avg inventory: 24000.9415
- Ending inventory: 18848.6061
- Transport cost: 4040.0929
- Holding cost: 23382.9747
- Purchase cost (from order_terms sell_price): 3112.0085
- Logistics cost (transport + holding): 27423.0676
- Total cost: 30535.0761
- Total external procured ordered qty: 59317.0231
- Total external procured arrived qty: 53702.9442
- Total external procured rejected qty (cap-limited): 23138.741
- Total external procurement cost premium: 4434.8191
- Cost share holding / transport / purchase: 0.765774 / 0.13231 / 0.101916
- Total opening stock bootstrap qty: 35284.3698
- Total unreliable supplier loss qty: 8997.7194
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 385.6913
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 252.1875
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
